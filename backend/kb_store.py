"""
kb_store.py —— 统一知识库检索 / 问答（阶段0 重写核心）
================================================
取代 rag.py / case_standards.py 的检索段 + kb_unified 假合并。

设计要点（直接回应用户约束）：
1. 真统一：单一 Milvus 集合 unified_kb，靠 doc_type 区分 5 类（standard/org/qa/general/law）。
2. 不用同义词 / 不靠关键词门控：检索**只走语义向量**（COSINE 召回），
   千奇百怪的问法靠向量泛化，不再因"同义词表没覆盖"而误报"暂无相关"。
3. 法律防误用：召回默认排除 status=已废止/已修改 的法条，prompt 强约束不引用废止法规。
4. 可溯源：LLM 必须返回带 citations 的结构化 JSON，前端可点开核验。
5. 保留业务派单：召回后调用 kb_dispatch.match_department_dispatch（平移自 case_standards）。

依赖：kb_common（call_llm / 连接常量）、kb_embed（统一 embedding）、kb_dispatch（派单）。
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional

import jieba
from rank_bm25 import BM25Okapi

from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT  # noqa: E402
from kb_embed import embed  # noqa: E402
from kb_dispatch import match_department_dispatch, is_dispatch_question  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [kb_store] %(levelname)s %(message)s")
logger = logging.getLogger("kb_store")

UNIFIED_COLLECTION = "unified_kb"
DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2 实际维度

# 法律召回默认排除这些状态（防误把废止/已修改法规当现行有效作答）
LAW_EXCLUDE_STATUS = ["已废止", "已修改"]

_client = None


def get_client():
    global _client
    if _client is None:
        from pymilvus import MilvusClient
        if USE_LOCAL_MODE:
            _client = MilvusClient(LOCAL_MILVUS_FILE)
        else:
            _client = MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")
    return _client


# ------------------------- 语义检索 -------------------------

def build_filter(doc_type: Optional[str] = None,
                 include_invalid_laws: bool = False) -> Optional[str]:
    """构造 Milvus boolean expr。"""
    parts = []
    if doc_type:
        parts.append(f'doc_type == "{doc_type}"')
    if not include_invalid_laws:
        # 非 law 记录 law_status 为空串，不影响；law 且状态在排除列表的被剔除
        excl = ", ".join(f'"{s}"' for s in LAW_EXCLUDE_STATUS)
        parts.append(f'(doc_type != "law" or law_status not in [{excl}])')
    return " and ".join(parts) if parts else None


# 文档类别（分桶召回用，顺序即合并后的优先级兜底）
DOC_TYPES = ["standard", "org", "qa", "general", "law"]


def _hit_to_dict(h) -> Dict[str, Any]:
    """兼容 pymilvus 3.0 的 Hit 对象与旧版 dict 两种返回形态。

    实测：pymilvus 3.0 的 search 返回 HybridHits，直接 `for h in hits[0]`
    迭代得到的元素类型不稳定（有时是 Hit、有时被当成 str），且其元素并非
    dict、没有 .get 方法，会导致解析静默失败、召回返回空。故统一用索引访问
    并兼容属性/字典两种取值。
    """
    if isinstance(h, dict):
        e = h.get("entity", {}) or {}
        meta_raw = e.get("metadata", "") or "{}"
        try:
            meta = json.loads(meta_raw) if meta_raw else {}
        except Exception:
            meta = {}
        return {
            "id": h.get("id"),
            "score": h.get("distance"),
            "doc_id": e.get("doc_id"),
            "chunk_id": e.get("chunk_id"),
            "doc_type": e.get("doc_type"),
            "source": e.get("source"),
            "title": e.get("title"),
            "text": e.get("text"),
            "law_status": e.get("law_status") or "",
            "case_type": e.get("case_type") or "",
            "metadata": meta,
        }
    # Hit 对象：属性访问
    e = getattr(h, "entity", {}) or {}
    def _g(d, k):
        return d.get(k) if isinstance(d, dict) else getattr(d, k, None)
    meta_raw = _g(e, "metadata") or "{}"
    try:
        meta = json.loads(meta_raw) if meta_raw else {}
    except Exception:
        meta = {}
    return {
        "id": getattr(h, "id", None),
        "score": getattr(h, "distance", None),
        "doc_id": _g(e, "doc_id"),
        "chunk_id": _g(e, "chunk_id"),
        "doc_type": _g(e, "doc_type"),
        "source": _g(e, "source"),
        "title": _g(e, "title"),
        "text": _g(e, "text"),
        "law_status": _g(e, "law_status") or "",
        "case_type": _g(e, "case_type") or "",
        "metadata": meta,
    }


def _raw_search(client, qvec, limit, flt) -> List[Dict[str, Any]]:
    """执行一次 MilvusClient.search 并解析为结构化命中列表。"""
    try:
        hits = client.search(
            collection_name=UNIFIED_COLLECTION,
            data=[qvec],
            limit=limit,
            filter=flt,
            output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                            "text", "law_status", "case_type", "metadata"],
        )
    except Exception as e:
        logger.error(f"[kb_store] search 失败: {e}")
        return []

    # pymilvus 3.0 下 hits[0] 用索引访问才稳定拿到 Hit/实体；迭代易拿错类型
    hh = hits[0] if len(hits) > 0 else []
    results = []
    for i in range(len(hh)):
        results.append(_hit_to_dict(hh[i]))
    return results


# ------------------------- BM25 关键词召回（混合检索的关键词一路） -------------------------
# 背景：纯向量（MiniLM）对「站亭↔站台」字序不同、「报修↔处置」同义不同字的匹配很弱，
# 导致市民口语叫法查不出对应标准/问答。此前靠手工维护别名表/主题词表兜底，
# 但 202 个标准 × 市民自由叫法是无底洞（"碰一个改一个"）。
# 改为业界标准的「向量语义 + BM25 关键词」混合检索：BM25 对字面匹配天然友好，
# 字序不同、同义不同字都能命中，且无需维护任何别名表。两路召回用 RRF 融合排序。
#
# 2026-07-29 修正：BM25 的 token 改为「jieba 词 + 中文 bigram」混合。
# 原因：纯 jieba 词级分词有粒度陷阱——「公交站亭」被切成「公交站/亭」，
# 而 query「公交站台」切成「公交/站台」，两边零重叠（"公交"≠"公交站"），
# BM25 分为 0，正确条目照样召回不到。bigram 下「公交站台」={公交,交站,站台}、
# 「公交站亭」={公交,交站,站亭}，有 2/3 重叠，可稳定命中（Lucene CJK 同款做法）。
# 同时索引语料改为现场对 title+text 分词（不再读灌库时存的 text_tokens 字段），
# 以后调整分词策略无需重灌库。

_BM25_INDEX = None  # BM25Okapi 实例（对全库 title+text 建索引）
_BM25_ROWS = None   # 与索引平行的原始行数据（doc_id/chunk_id/doc_type/...）

_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def _tokenize_for_bm25(text: str) -> List[str]:
    """BM25 专用分词：jieba 词 + 中文连续段的字符 bigram（单字段保留单字）。

    bigram 解决中文词级分词的字序/粒度零重叠问题（站亭↔站台、候车亭↔站亭）。
    """
    text = text or ""
    tokens = list(jieba.lcut(text))
    for seg in _CJK_RE.findall(text):
        if len(seg) == 1:
            tokens.append(seg)
        else:
            tokens.extend(seg[i:i + 2] for i in range(len(seg) - 1))
    return tokens


def _load_bm25_index(client):
    """从集合加载所有记录的 title+text，现场分词构建 BM25 索引（首次 search 时执行一次）。

    语料用 title+text 现场 _tokenize_for_bm25（而非灌库时存的 text_tokens 字段），
    这样分词策略升级不需要重灌库。
    返回 (BM25Okapi, rows)。rows 与索引平行，存每条的 doc_id/chunk_id/doc_type/
    source/title/text/law_status/case_type/metadata，供命中后还原结构化结果。
    """
    global _BM25_INDEX, _BM25_ROWS
    if _BM25_INDEX is not None and _BM25_ROWS is not None:
        return _BM25_INDEX, _BM25_ROWS
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter="",  # 全量（BM25 索引需覆盖所有 doc_type）
            output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                           "text", "law_status", "case_type", "metadata"],
            limit=100000,
        )
    except Exception as e:
        logger.error(f"[kb_store] 加载 BM25 语料失败: {e}")
        return None, None
    corpus, meta_rows = [], []
    for r in rows:
        tokens = _tokenize_for_bm25(f"{r.get('title') or ''} {r.get('text') or ''}")
        if not tokens:
            continue
        corpus.append(tokens)
        meta_rows.append({
            "doc_id": r.get("doc_id"),
            "chunk_id": r.get("chunk_id"),
            "doc_type": r.get("doc_type"),
            "source": r.get("source"),
            "title": r.get("title"),
            "text": r.get("text"),
            "law_status": r.get("law_status") or "",
            "case_type": r.get("case_type") or "",
            "metadata": json.loads(r.get("metadata") or "{}"),
        })
    if not corpus:
        logger.warning("[kb_store] BM25 语料为空，降级为纯向量检索")
        return None, None
    _BM25_INDEX = BM25Okapi(corpus)
    _BM25_ROWS = meta_rows
    logger.info(f"[kb_store] BM25 索引已构建：{len(corpus)} 条语料（jieba词+bigram）")
    return _BM25_INDEX, _BM25_ROWS


def _bm25_search(client, query: str, top_k: int = 12) -> List[Dict[str, Any]]:
    """BM25 关键词召回：对 query 分词（jieba词+bigram）后算 BM25 分，取 top_k。

    返回与 _hit_to_dict 一致的结构（score 为 BM25 原始分，仅用于 RRF 排名，不直接展示）。
    """
    bm25, rows = _load_bm25_index(client)
    if bm25 is None or rows is None:
        return []
    q_tokens = _tokenize_for_bm25(query)
    if not q_tokens:
        return []
    scores = bm25.get_scores(q_tokens)
    # 取 top_k 个最高分（BM25 分非负，0 分即无关键词重叠，不纳入）
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    results = []
    for rank, i in enumerate(top_idx):
        if scores[i] <= 0:
            break
        r = dict(rows[i])
        r["id"] = None  # BM25 召回无向量 id，用 doc_id+chunk_id 唯一标识
        r["score"] = float(scores[i])
        r["bm25_rank"] = rank + 1  # RRF 融合用：BM25 一路的排名（1-based）
        results.append(r)
    return results


def _rrf_fuse(vector_hits: List[Dict[str, Any]],
              bm25_hits: List[Dict[str, Any]],
              k: int = 60,
              bm25_weight: float = 1.5) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion 融合两路召回结果。

    RRF 公式：score = Σ weight/(k + rank)，k=60 是业界经验值（原论文推荐）。
    对每条命中的 (doc_id, chunk_id)，把它在向量一路和 BM25 一路的排名分别代入求和。
    只出现在一路的命中，另一路排名视为无穷大（贡献 0）。

    bm25_weight=1.5：给 BM25 一路更高权重。背景：向量（MiniLM）对「字序不同」
    （公交站亭↔公交站台）、「同义不同字」（报修↔处置）匹配弱，且易把语义相近但
    主题无关的法规顶到前面；BM25 对关键词匹配更可靠，提高其权重可让字面匹配强的
    结果（如含"公交站亭"的标准条目）在融合后稳定排在泛法规之前。
    返回按 RRF 分降序的合并列表，每条带 rrf_score / vector_rank / bm25_rank。
    """
    fused = {}
    # 向量一路：按 score（COSINE 相似度）降序排名
    for rank, h in enumerate(sorted(vector_hits, key=lambda x: x.get("score") or 0, reverse=True), 1):
        key = (h["doc_id"], h["chunk_id"])
        if key not in fused:
            fused[key] = dict(h)
            fused[key]["rrf_score"] = 0.0
        fused[key]["rrf_score"] += 1.0 / (k + rank)
        fused[key]["vector_rank"] = rank
    # BM25 一路：按 bm25_rank（已按 BM25 分降序）排名，权重 bm25_weight
    for h in bm25_hits:
        key = (h["doc_id"], h["chunk_id"])
        rank = h.get("bm25_rank") or 999
        if key not in fused:
            fused[key] = dict(h)
            fused[key]["rrf_score"] = 0.0
        fused[key]["rrf_score"] += bm25_weight / (k + rank)
        fused[key]["bm25_rank"] = rank
    # 按 RRF 分降序
    return sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)



def search(query: str,
           top_k: int = 6,
           doc_type: Optional[str] = None,
           include_invalid_laws: bool = False,
           per_type_top_k: int = 6) -> List[Dict[str, Any]]:
    """混合检索：向量语义召回 + BM25 关键词召回，RRF 融合排序。

    架构演进（回应"碰一个改一个"的痛点）：
    - 旧版：纯向量 + 手工别名表/主题词表兜底，市民每换一种叫法就得加一条规则。
    - 新版：向量（语义）+ BM25（关键词）双路并行，RRF 融合。字序不同（站亭↔站台）、
      同义不同字（报修↔处置）、口语叫法，BM25 一路天然兜住，无需维护任何别名表。
    保留：分桶召回（避免 law 大类淹没小类）、法律防误用（排除废止法规）。
    """
    qvec = embed(query)
    if qvec is None:
        logger.error("[kb_store] query embedding 失败")
        return []
    client = get_client()
    # Milvus Lite 在独立进程/重启后集合处于 released 状态，search 前必须先 load 到内存
    try:
        client.load_collection(UNIFIED_COLLECTION)
    except Exception as e:
        logger.warning(f"load_collection 可能已加载，忽略: {e}")

    # 指定单类时，走原逻辑（不做分桶/混合）
    if doc_type:
        flt = build_filter(doc_type, include_invalid_laws)
        return _raw_search(client, qvec, top_k, flt)

    # ---- 第一路：向量语义召回（按 doc_type 分桶，避免大类淹没小类） ----
    vector_merged = {}
    for t in DOC_TYPES:
        flt = build_filter(t, include_invalid_laws)
        for h in _raw_search(client, qvec, per_type_top_k, flt):
            key = (h["doc_id"], h["chunk_id"])
            if key not in vector_merged or h["score"] > vector_merged[key]["score"]:
                vector_merged[key] = h
    vector_hits = list(vector_merged.values())

    # ---- 第二路：BM25 关键词召回（对 query 分词后算 BM25 分） ----
    # 字序不同（公交站亭↔公交站台）、同义不同字（报修↔处置）都能命中，
    # 无需手工别名表。BM25 索引首次 search 时从 text_tokens 构建并缓存。
    bm25_hits = _bm25_search(client, query, top_k=max(top_k * 2, 12))

    # ---- RRF 融合：两路召回按排名加权融合 ----
    # RRF 公式 score = Σ 1/(60 + rank)，k=60 是业界经验值。
    # 向量一路按 COSINE 相似度排名，BM25 一路按 BM25 分排名，融合后按 RRF 分降序。
    fused = _rrf_fuse(vector_hits, bm25_hits, k=60)

    # ---- 法律防误用：排除已废止/已修改法规（若非显式包含） ----
    if not include_invalid_laws:
        fused = [h for h in fused if not (
            h.get("doc_type") == "law" and h.get("law_status") in LAW_EXCLUDE_STATUS
        )]

    # ---- 按类均衡采样：保证 standard/org/qa 各至少 1 个代表进 top_k ----
    # 背景：RRF 融合后若纯按分数排序，小类低分项仍可能被 law/qa 高分挤出 top_k。
    # 给 standard/org/qa 各保留 1 个代表（RRF 分 > 阈值才纳入，避免注入纯噪声）。
    MIN_RRF_SCORE = 0.008  # RRF 分经验阈值（约等于两路都在 top50 内）
    final = []
    final_keys = set()
    rest_by_type = {t: [] for t in DOC_TYPES}
    for h in fused:
        rest_by_type[h.get("doc_type")].append(h)

    # 先给 standard/org/qa 各塞 1 个最高分代表
    for t in ("standard", "org", "qa"):
        for h in rest_by_type.get(t, []):
            key = (h["doc_id"], h["chunk_id"])
            if h["rrf_score"] > MIN_RRF_SCORE and key not in final_keys:
                final.append(h)
                final_keys.add(key)
                break

    # 剩余位置按 RRF 分全局填满
    for h in fused:
        if len(final) >= top_k:
            break
        key = (h["doc_id"], h["chunk_id"])
        if key not in final_keys:
            final.append(h)
            final_keys.add(key)

    return final[:top_k]



# ------------------------- 问答（LLM + citations） -------------------------

_SYSTEM_TEMPLATE = """你是运城市城市管理局智慧城管知识库问答助手。请【仅】依据下方「检索片段」回答用户问题。

硬性规则：
1. 检索片段与问题主题相关（如同属某一设施、单位、法规或职责）时，必须基于片段给出可操作的答复，
   可综合：立案/处置标准、责任部门、反映渠道（如 12345）等。不要把“问法不同”
   （如“怎么报修”“怎么处理”“归谁管”“有什么标准”）当成“没有内容”而拒答——
   只要片段和问题是同一主题，就应从片段提炼答案。
2. 仅当检索片段与问题主题完全无关时，才回答“知识库中暂无相关内容”；禁止编造片段之外的内容。
3. 法律条文：片段里的 law_status 若标注为“已废止/已修改”，必须说明该法规已废止/已修改，不作为现行依据；不要据此给出现行处置建议。
4. 每条事实性陈述尽量对应一个引用，引用内联写成 [来源标题]。
5. 面向一线城管人员或市民，回答简洁、可操作。
6. 涉及「组织架构 / 内设机构 / 下属单位 / 科室职责」的问题，回答须按机构类别分组列示：
   先列「内设业务科室」（片段机构类别为“内设科室”），再列「下属单位”（类别为“下属单位”）；
   若检索到「架构总览」类片段，应以其为准给出完整机构清单，并注明来源；
   不要把这些机构混在一大段里平铺，要分点、分组、清晰可扫读。
7. 涉及市民「怎么办 / 怎么交 / 在哪里办 / 如何申请 / 流程 / 步骤 / 网点 / 电话」
   等办事类问法时：**优先采用检索片段中 doc_type 为 qa（12345 知识问答）的条目**
   作为答案——这类片段是人工整理的高信噪比直答（含微信/支付宝/线下营业厅等
   具体办理方法），应直接据此作答，而不要把其改写为泛泛的法规原则（如仅答
   “应按规定缴纳”却不给办理渠道）。即便 qa 片段标题与问法字面略有差异
   （如问“在哪里交水费”而 qa 标题是“缴费流程”），只要片段正文含办理方法，
   即视为同主题、必须据此作答。若检索片段中已包含【业务主题召回】的 qa 条目
   （如“水费”主题对应的运城首创缴费流程，含微信/支付宝/线下营业厅渠道），
   应优先采用该条目作答，不得改用无关的供暖缴费类 qa 或泛法规条文。
8. 当且仅当所有检索片段（含 qa/standard/org/law）经核对都确实与问题主题无关时，
   才输出“知识库中暂无相关内容”；只要存在任一同主题片段（尤其 qa 直答），
   就必须基于它作答，严禁以“问法不同”为由拒答。
9. 当用户要求「梳理 / 列举 / 有哪些 XX 相关制度 / 规定 / 办法」时：
   - 只从知识库内的**内部制度文件**（检索片段中类型为 general、且标注「内部制度·局机关」或
     「内部制度·平台服务中心」的）归纳，按**归属分组**列示：
       · 局机关（运城市城市管理局）：列出相关制度文件名称
       · 平台服务中心（运城市智慧城市管理平台服务中心）：列出相关制度文件名称
   - 以**文件名为准**列举制度名称；文件内的某条细则（如「密码管理」「岗位责任制」）不是独立制度文件，
     可附在文件名后用括号简述该汇编所含主要制度项，但不要把细则单独列成制度名称。
   - **不要把法律法规（law 类，如《XX条例》《XX法》）当作局里/平台的内部制度名称**。若检索到相关法规，
     可在末尾单列「相关法律法规参考」，不要混入制度清单。
   - 若某归属下未检索到相关制度文件，明确说明「未检索到该归属下相关制度」，不要编造。

=== 检索片段（按相关性从高到低）===
{context}

=== 用户问题 ===
{query}
"""

def _format_context(hits: List[Dict[str, Any]]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        status_note = ""
        if h["doc_type"] == "law" and h["law_status"]:
            status_note = f"（法规状态：{h['law_status']}）"
        # 机构类：标注机构类别（内设科室 / 下属单位 / 架构总览 / 局机关），供按类分组
        cat_note = ""
        meta = h.get("metadata") or {}
        if h["doc_type"] == "org" and meta.get("org_category"):
            cat_note = f"（机构类别：{meta['org_category']}）"
        # 制度类：标注归属（局机关 / 平台服务中心），供「梳理XX制度」时按归属分组
        gen_note = ""
        if h["doc_type"] == "general":
            t = h["title"] or ""
            if "平台服务中心" in t:
                gen_note = "（内部制度·平台服务中心）"
            elif "运城市城市管理局" in t:
                gen_note = "（内部制度·局机关）"
        # 立结案标准的「法律依据」存在 metadata，拼进上下文供 LLM 引用溯源
        legal = ""
        if h["doc_type"] == "standard" and meta.get("legal_basis"):
            legal = f"\n（该标准法律依据：{meta['legal_basis']}）"
        lines.append(
            f"[{i}] (类型:{h['doc_type']}{status_note}{cat_note}{gen_note}) 标题:{h['title']}\n{h['text']}{legal}\n"
        )
    return "\n".join(lines)


def _degraded_answer(hits: List[Dict[str, Any]]) -> str:
    """LLM 全部不可用时，把检索到的前几条片段直出，作为降级答案。

    绝不返回“知识库中暂无相关内容”——那种话只在「检索本身为空」时才是真话。
    LLM 挂了但内容明明召回到了，应如实把片段摆出来，避免掩盖真实故障。
    """
    lines = [f"（已检索到 {len(hits)} 条相关内容，但大模型暂时未响应，以下为原文片段供参考）", ""]
    for i, h in enumerate(hits[:3], 1):
        lines.append(f"{i}. 【{h['title']}】（{h['doc_type']}）")
        lines.append((h["text"] or "").strip()[:300])
        lines.append("")
    return "\n".join(lines).strip()


def _looks_like_no_answer(answer: str) -> bool:
    """判断 LLM 的 answer 是否本质上在说“知识库里没内容”。

    用于兜底：检索成功但 LLM 误以「问法不同」为由谎报暂无时，据此识别并拦截，
    改用已召回的 qa 直答。命中即视为谎报（不区分 LLM 是否还啰嗦解释）。
    """
    if not answer:
        return True
    s = answer.strip()
    markers = (
        "知识库中暂无相关内容",
        "暂无相关内容",
        "知识库中暂无",
        "暂无相关",
        "未检索到相关内容",
        "没有相关内容",
        "没有找到相关内容",
        "知识库中未找到",
    )
    return any(m in s for m in markers)


def _qa_direct_answer(qa_hits: List[Dict[str, Any]]) -> str:
    """从 qa 类检索片段里提取「答案」正文，拼成市民办事直答。

    qa 片段文本形如「问题：xxx\\n答案：yyy」。优先摘「答案：」之后的内容；
    若无该结构则回退整段文本。保留换行，最多取前 3 条 qa 拼接，避免超长。
    """
    blocks = []
    for h in qa_hits[:3]:
        text = (h.get("text") or "").strip()
        if not text:
            continue
        # 解析「问题：…\n答案：…」结构，只取答案部分
        m = re.search(r"答案[:：]\s*(.*)", text, re.DOTALL)
        body = m.group(1).strip() if m else text
        title = h.get("title") or "12345知识问答"
        blocks.append(f"【{title}】\n{body}")
    if not blocks:
        return "知识库中暂无相关内容"
    return "\n\n".join(blocks).strip()


def _call_llm_timeout(prompt: str, provider: Optional[str], per_call_timeout: int = 50) -> Optional[str]:
    """带硬超时的 LLM 调用（线程池包裹）。

    背景：call_llm 默认 timeout=120s，且 ask() 主 provider 失败还会顺序回退豆包再调一次，
    最坏两次累计 240s，远超前端 90s 的 abort 阈值——后端干等到 120s+ 却被前端中断，
    既超时又白白浪费已召回的 qa 片段。
    这里把单次调用预算压到 50s，超时即视作失败返回 None，让 ask() 快速落到降级直出
    （检索片段/qa 直答），避免无谓长等。超时不抛异常、不污染外层。
    """
    from kb_common import call_llm
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(call_llm, prompt, provider)
        try:
            return fut.result(timeout=per_call_timeout)
        except FuturesTimeout:
            logger.warning(f"[kb_store] LLM({provider}) 调用超过 {per_call_timeout}s 超时，放弃")
            return None
        except Exception as e:
            logger.warning(f"[kb_store] LLM({provider}) 调用异常: {e}")
            return None


def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 输出里尽量抠出 JSON。"""
    if not text:
        return None
    s = text.strip()
    # 去 ```json 包裹
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    try:
        return json.loads(s)
    except Exception:
        pass
    # 找第一个 { 到最后一个 }
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1 and b > a:
        try:
            return json.loads(s[a:b + 1])
        except Exception:
            return None
    return None


def ask(query: str,
        location: Any = None,
        top_k: int = 6,
        provider: Optional[str] = None) -> Dict[str, Any]:
    """
    统一问答入口。
    返回：
    {
      "answer": str,
      "citations": [{"title","doc_type","source","excerpt"}],
      "dispatch": dict|None,   # 地理派单结果（若有坐标/派单意图）
      "retrieved": [...]       # 原始召回，供调试
    }
    """
    from kb_common import call_llm

    # 1) 地理派单（与检索解耦，独立业务）
    dispatch = None
    if location is not None or is_dispatch_question(query):
        try:
            dispatch = match_department_dispatch(query, location)
        except Exception as e:
            logger.warning(f"[kb_store] 派单调用异常: {e}")

    # 2) 语义召回（默认排除废止法规；分桶后检索量放大，保证小类标准进入上下文）
    hits = search(query, top_k=max(int(top_k), 12))
    retrieved = hits

    if not hits:
        return {
            "answer": "知识库中暂无相关内容",
            "citations": [],
            "dispatch": dispatch,
            "retrieved": [],
        }

    # 3) 拼 prompt + 调 LLM（带硬超时，避免慢 LLM 把请求拖到前端 abort）
    context = _format_context(hits)
    prompt = _SYSTEM_TEMPLATE.format(context=context, query=query)
    # 主 provider（默认 doubao，见 kb_common）先调，单次预算 50s；
    # 失败（含超时）再回退豆包再给 50s。都失败 → raw=None → 落降级直出（qa 片段）。
    # 不在这里用 call_llm 默认值（120s）顺序双调，否则最坏 240s 必超时。
    raw = _call_llm_timeout(prompt, provider, per_call_timeout=50)
    if raw is None and provider != "doubao":
        logger.warning("[kb_store] 主 LLM provider 调用失败/超时，自动回退豆包（预算 50s）")
        raw = _call_llm_timeout(prompt, "doubao", per_call_timeout=50)
    parsed = _extract_json(raw) if raw else None

    if parsed and isinstance(parsed, dict) and parsed.get("answer"):
        answer = parsed["answer"]
        citations = parsed.get("citations", []) or []
        # ---- LLM 误拒兜底：检索明明召回到了内容，LLM 却谎报“暂无” ----
        # 背景：检索成功（hits 非空）但 LLM 把“问法不同（怎么交/在哪里交）”
        # 误判成“没有内容”，返回“知识库中暂无相关内容”。这会浪费已召回的 qa
        # 直答（如 12345 第 159 条缴费流程），让市民拿到假空答案。
        # 兜底：只要 hits 里存在 qa 类（市民问答直答）片段，即视为有答案源，
        # 强制改用 qa 片段直出（带微信/支付宝/线下营业厅等办理方法），
        # 绝不让“LLM 误判”伪装成“知识库无内容”。
        if _looks_like_no_answer(answer) and any(h.get("doc_type") == "qa" for h in hits):
            logger.warning("[kb_store] LLM 误判为暂无，但命中 qa 直答，强制改用 qa 片段直出")
            qa_hits = [h for h in hits if h.get("doc_type") == "qa"]
            answer = _qa_direct_answer(qa_hits)
            citations = [{
                "title": h["title"],
                "doc_type": h["doc_type"],
                "source": h["source"],
                "excerpt": (h["text"] or "")[:80],
            } for h in qa_hits[:3]]
    else:
        if not raw:
            # LLM 全部不可用但检索成功：降级为检索片段直出，绝不谎报“暂无相关内容”
            # —— 否则会掩盖“其实是 LLM 没响应”的真实故障，误导成“知识库空”。
            logger.warning("[kb_store] LLM 全部不可用，降级为检索结果直出（不谎报无内容）")
            answer = _degraded_answer(hits)
            citations = [{
                "title": h["title"],
                "doc_type": h["doc_type"],
                "source": h["source"],
                "excerpt": (h["text"] or "")[:80],
            } for h in hits[:3]]
        else:
            # 容错：LLM 没按 JSON 出，直接把原文当答案，并基于召回构造引用
            answer = (raw or "知识库中暂无相关内容").strip()
            citations = [{
            "title": h["title"],
            "doc_type": h["doc_type"],
            "source": h["source"],
            "excerpt": (h["text"] or "")[:80],
        } for h in hits[:3]]

    # 规范化 citations 字段
    norm_citations = []
    for c in citations:
        if not isinstance(c, dict):
            continue
        norm_citations.append({
            "title": c.get("title", ""),
            "doc_type": c.get("doc_type", ""),
            "source": c.get("source", ""),
            "excerpt": c.get("excerpt", ""),
        })

    return {
        "answer": answer,
        "citations": norm_citations,
        "dispatch": dispatch,
        "retrieved": retrieved,
    }
