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
import os
import re
import time
import tempfile
from typing import List, Dict, Any, Optional

import jieba
import jieba.posseg  # 词性标注（误拒闸门按名词性取实体词，需显式导入子模块）
from rank_bm25 import BM25Okapi

from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT, LLM_PROVIDER  # noqa: E402
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
_BM25_BUILD_TIME = 0.0  # 本进程索引构建时刻，用于和失效标记文件的 mtime 比对

# 跨进程失效标记：管理端重建索引 / 删除文档时写此文件。gunicorn 多 worker 下
# 每个 worker 各有一份 BM25 进程内缓存，重建/删除只发生在其中一个 worker，
# 其余 worker 在检索前对比标记文件 mtime 晚于本进程构建时间即自动重建，
# 避免"新灌的内容查不到、已删的内容还在"（此前必须重启进程才恢复）。
_BM25_STAMP_FILE = os.path.join(tempfile.gettempdir(), "kb_bm25_version.stamp")

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


# ------------------------- 受控实体别名扩展（解决"市民口语/品牌词 → 库内标准实体"） -------------------------
# 背景：部分市民高频叫法在库内**完全没有字面**（如库里只有「共享单车管理」，
# 没有「小蓝车/共享电动车/哈啰/青桔」字样）。纯向量（语义泛化）与 BM25（靠字面）
# 都接不住，召回只能落到上位类（如「非机动车乱停放」），答非所问。
# 与 2026-07 已废弃的 kb_synonyms（硬门槛同义词：必须命中否则判无内容，导致误判）
# 本质不同：本表只做 **query 扩展**（把别名展开成标准实体词后再检索），
# 仅提高召回概率，不强制命中、不阻断、不影响"无内容"判定。
#
# 收录铁律（防滑回"无限别名表"）：① 库内该实体无字面对应；② 指向单一明确实体、无歧义；
# ③ 高频（市民日常叫法/常见品牌）。只放这一类封闭词集，不覆盖千变万化的同义改写。
ENTITY_ALIASES = {
    # —— 共享出行：运城市民口语/品牌词 → 共享单车（电瓶车）实体 ——
    "小蓝车": "共享单车 电瓶车 共享电动车",
    "小绿车": "共享单车 电瓶车",
    "共享单车": "共享单车 电瓶车",
    "共享电动车": "共享电动车 电瓶车",
    "共享电瓶车": "共享电动车 电瓶车",
    "哈啰": "共享单车 电瓶车 哈啰出行",
    "哈啰单车": "共享单车 电瓶车",
    "哈啰电单车": "共享电动车 电瓶车",
    "青桔": "共享单车 电瓶车 青桔单车",
    "青桔单车": "共享单车 电瓶车",
    "美团单车": "共享单车 电瓶车 美团电单车",
    "美团电单车": "共享电动车 电瓶车",
    "ofo": "共享单车 电瓶车 小黄车",
    "小黄车": "共享单车 电瓶车 ofo",
    "摩拜": "共享单车 电瓶车",
    # —— 立案项近义表述：市民口语「路面」≈ 办案口径的「道路」 ——
    # 市民报「路面破损」通常即指市政道路破损（市容环境_道路破损）；只扩展加词不替换，
    # 「路面塌陷」「施工工地出入口道路破损」等其它项仍正常召回。指向单一明确，符合收录铁律。
    # canonical 用「道路破损标准」文本里的特异词（破损/开裂/坑凹），精准拉高该条在 BM25+向量两路的得分，
    # 使其从 RRF 第7挤进 top6（与「不明井盖」仅差 0.0003）。注意用「坑凹」而非「坑洼」（坑洼帮到公交站亭条）。
    "路面破损": "道路破损 破损 开裂 坑凹",
}


def expand_query(q: str) -> str:
    """把 query 中的市民口语/品牌别名，扩展为对应的标准实体词，提升召回。

    例如「小蓝车乱摆放归谁管理」→「小蓝车乱摆放归谁管理 共享单车 电瓶车 共享电动车」。
    返回扩展后的 query（未命中别名则原样返回）。
    """
    if not q:
        return q
    extra = []
    for alias, canonical in ENTITY_ALIASES.items():
        if alias in q and alias not in extra:
            extra.append(alias)
            for c in canonical.split():
                if c not in extra:
                    extra.append(c)
    if not extra:
        return q
    return q + " " + " ".join(extra)


def invalidate_bm25_cache():
    """知识库内容变更（重建索引/删除文档）后调用：失效本进程缓存，并写标记文件
    通知其它 gunicorn worker 在下次检索时自动重建。"""
    global _BM25_INDEX, _BM25_ROWS
    _BM25_INDEX = None
    _BM25_ROWS = None
    try:
        with open(_BM25_STAMP_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        logger.warning(f"[kb_store] 写 BM25 失效标记失败: {e}")


def _load_bm25_index(client):
    """从集合加载所有记录的 title+text，现场分词构建 BM25 索引（首次 search 时执行一次）。

    语料用 title+text 现场 _tokenize_for_bm25（而非灌库时存的 text_tokens 字段），
    这样分词策略升级不需要重灌库。
    缓存失效：标记文件 mtime 晚于本进程构建时间（其它 worker 做过重建/删除）时重建。
    返回 (BM25Okapi, rows)。rows 与索引平行，存每条的 doc_id/chunk_id/doc_type/
    source/title/text/law_status/case_type/metadata，供命中后还原结构化结果。
    """
    global _BM25_INDEX, _BM25_ROWS, _BM25_BUILD_TIME
    if _BM25_INDEX is not None and _BM25_ROWS is not None:
        try:
            if os.path.getmtime(_BM25_STAMP_FILE) <= _BM25_BUILD_TIME:
                return _BM25_INDEX, _BM25_ROWS
        except OSError:
            return _BM25_INDEX, _BM25_ROWS  # 标记文件不存在（从未变更过）→ 沿用缓存
        logger.info("[kb_store] 检测到知识库内容已变更，重建 BM25 索引")
    try:
        # Milvus Standalone 限制 offset+limit <= 16384，需分批查询
        all_rows = []
        batch_size = 16000
        offset = 0
        while True:
            batch = client.query(
                UNIFIED_COLLECTION,
                filter="",  # 全量（BM25 索引需覆盖所有 doc_type）
                output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                               "text", "law_status", "case_type", "metadata"],
                limit=batch_size,
                offset=offset,
            )
            all_rows.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        rows = all_rows
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
    _BM25_BUILD_TIME = time.time()
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
    # 向量一路：按 score（Milvus COSINE 返回即相似度，0~1 越大越像；自查实测精确命中 1.0）降序排名
    for rank, h in enumerate(sorted(vector_hits, key=lambda x: x.get("score") or 0, reverse=True), 1):
        key = (h["doc_id"], h["chunk_id"])
        if key not in fused:
            fused[key] = dict(h)
            fused[key]["rrf_score"] = 0.0
        fused[key]["rrf_score"] += 1.0 / (k + rank)
        fused[key]["vector_rank"] = rank
        # similarity 透传给前端展示：向量一路的 score 本身就是 0~1 相似度
        fused[key]["similarity"] = h.get("score")
    # BM25 一路：按 bm25_rank（已按 BM25 分降序）排名，权重 bm25_weight
    for h in bm25_hits:
        key = (h["doc_id"], h["chunk_id"])
        rank = h.get("bm25_rank") or 999
        if key not in fused:
            fused[key] = dict(h)
            fused[key]["rrf_score"] = 0.0
            # 纯 BM25 命中没有向量相似度（score 是 BM25 原始分，量纲完全不同），
            # 置 None 让前端隐藏百分比，避免把 BM25 分当相似度展示成 "630%"
            fused[key]["similarity"] = None
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
    qvec = embed(expand_query(query))
    if qvec is None:
        logger.error("[kb_store] query embedding 失败")
        return []
    client = get_client()
    # Milvus Lite 在独立进程/重启后集合处于 released 状态，search 前必须先 load 到内存
    try:
        client.load_collection(UNIFIED_COLLECTION)
    except Exception as e:
        logger.warning(f"load_collection 可能已加载，忽略: {e}")

    # 指定单类时：同样走混合检索（向量 + BM25 RRF），只是把两路都限制在该 doc_type。
    # 旧版此处直接返回纯向量结果——实测「公交站台破损归谁管」+ standard 过滤连正确
    # 条目都进不了 top3（MiniLM 对字序不同/同义改写匹配弱），必须吃到混合检索的收益。
    if doc_type:
        flt = build_filter(doc_type, include_invalid_laws)
        vector_hits = _raw_search(client, qvec, max(top_k, per_type_top_k), flt)
        bm25_hits = [h for h in _bm25_search(client, expand_query(query), top_k=max(top_k * 2, 12))
                     if h.get("doc_type") == doc_type]
        fused = _rrf_fuse(vector_hits, bm25_hits)
        if not include_invalid_laws:
            fused = [h for h in fused if not (
                h.get("doc_type") == "law" and h.get("law_status") in LAW_EXCLUDE_STATUS
            )]
        return fused[:top_k]

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
    # 市民口语/品牌别名（如「小蓝车」）已在 search 入口经 expand_query 展开为标准实体词。
    # BM25 索引首次 search 时现场对 title+text 分词并缓存（不读灌库时的 text_tokens 字段）。
    bm25_hits = _bm25_search(client, expand_query(query), top_k=max(top_k * 2, 12))

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

=== 对话历史（仅供理解追问的指代对象，回答依据仍仅限于检索片段）===
{history_section}

=== 输出格式（硬性要求，违反即任务失败）===
必须且只能输出一个 JSON 对象，不要输出 JSON 以外的任何文字，不要用 ``` 代码块包裹：
{{"answer":"给用户的完整答复","citations":[{{"title":"片段标题","doc_type":"片段类型","excerpt":"支撑该结论的片段原文摘录，80字以内"}}]}}
- citations 只能使用「检索片段」中出现过的标题，最多 5 条；无引用则为 []。
- answer 中每处事实性陈述都要有引用，内联写成 [标题]，与 citations 一一对应。
- answer 可用 markdown 列表/加粗，面向一线城管人员或市民，简洁、可操作。

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


def _degraded_answer(hits: List[Dict[str, Any]], reason: str = "大模型暂时未响应") -> str:
    """LLM 全部不可用时，把检索到的前几条片段直出，作为降级答案。

    绝不返回“知识库中暂无相关内容”——那种话只在「检索本身为空」时才是真话。
    LLM 挂了但内容明明召回到了，应如实把片段摆出来，避免掩盖真实故障。
    reason 说明为何走原文直出（超时/未按 JSON 出/误拒被闸门放行），
    让用户知道眼前不是大模型的综合答案。
    """
    lines = [f"（已检索到 {len(hits)} 条相关内容，但{reason}，以下为原文片段供参考）", ""]
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


# 误拒兜底倒出 qa 原文时的框定语：让用户知道这不是大模型的综合答案，
# 而是知识库条目的原文摘录，避免把“没组织的库中内容”当成正式答复。
_QA_FALLBACK_PREFIX = "（大模型未能给出综合回答，以下为知识库中相关问答条目原文，供参考）\n\n"


def _refusal_is_false(query: str, hits: List[Dict[str, Any]]) -> bool:
    """判断 LLM 的“暂无相关内容”是否为误拒：问题的最稀有实体词是否真实出现在命中片段里。

    背景：拒答有两种，必须区分——
      ① 误拒：问题实体就在命中片段里（问“在哪里交水费”，158/159 正文含“水费”），
         此时倒出片段原文是有用的补救；
      ② 正确拒绝：知识库确实没有该实体（问“银龙水务电话”，全库 0 处“银龙”），
         此时倒出的是首创水费/供热电话等不相关原文，比诚实拒答更糟。
    旧版不区分，两种都覆盖，用户拿到过不相关片段的生硬堆砌。

    判定用“文档频率”而非人工通用词表：查询分词后在知识库全量语料里统计每个词
    出现在多少条片段中，取最稀有的词——越稀越可能是指名实体（“银龙”df=0 ＜
    “水务”df=11 ＜ “电话”df=高）。最稀有的词在任一命中片段的标题/正文中原文
    出现，才认为片段与问题同主题，允许覆盖拒答；否则保留 LLM 的诚实拒答。
    只取名词性词（银龙→nr、解放南路→nz、水费/水务→n）：疑问词（哪个/哪里→r）、
    动词、语气词不参与——否则“哪个”这类全库不出现的功能词会抢走“最稀有”名额，
    把本该放行的误拒也拦掉。
    """
    if not hits:
        return False
    words = {w for w, f in jieba.posseg.cut(query or "")
             if len(w) >= 2 and f.startswith("n") and not w.isspace()}
    if not words:
        return False
    rows = _BM25_ROWS or []
    if not rows:
        # 语料未加载（异常路径）：无法证明同主题，保守保留拒答
        return False
    blobs = [f"{r.get('title') or ''}\n{r.get('text') or ''}" for r in rows]

    def _df(w: str) -> int:
        return sum(1 for b in blobs if w in b)

    dfs = {w: _df(w) for w in words}
    rarest_df = min(dfs.values())
    rarest_words = sorted(w for w, d in dfs.items() if d == rarest_df)
    if rarest_df == 0:
        # 实体词全库不存在——LLM 拒答成立
        logger.info(f"[kb_store] 误拒闸门：实体词{rarest_words}全库不存在，保留 LLM 拒答")
        return False
    hit_blobs = [f"{h.get('title') or ''}\n{h.get('text') or ''}" for h in hits]
    if any(rw in b for rw in rarest_words for b in hit_blobs):
        return True
    logger.info(f"[kb_store] 误拒闸门：实体词{rarest_words}未出现在命中片段，保留 LLM 拒答")
    return False


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
    """带硬超时的 LLM 调用（requests 拆分超时 + 线程池兜底，真·限时）。

    背景：ask() 主 provider 失败还会顺序回退再调一次，旧版最坏两次累计 240s，
    远超前端 180s 的 abort 阈值——后端干等到超时却被前端中断，既慢又浪费已召回的片段。
    旧版另一个致命伤：`with ThreadPoolExecutor` 块退出会 shutdown(wait=True) 等
    底层 requests（timeout=120s）跑完，"50s 预算"实际最长阻塞 120s+，超时是假的。

    现在：
    1. 给 call_llm 传 requests 超时元组 (connect=5s, read=per_call_timeout)，底层请求自身被真正限时；
    2. 线程池 fut.result 再给 per_call_timeout+10s 兜底，超时后 shutdown(wait=False)
       立即返回、不等残留线程（残留线程最坏活到自身 read 超时后自行结束，不阻塞当前请求）。
    超时不抛异常、不污染外层。
    """
    from kb_common import call_llm
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    ex = ThreadPoolExecutor(max_workers=1)
    try:
        fut = ex.submit(call_llm, prompt, provider, (5, per_call_timeout))
        try:
            return fut.result(timeout=per_call_timeout + 10)
        except FuturesTimeout:
            logger.warning(f"[kb_store] LLM({provider}) 调用超过 {per_call_timeout}s 超时，放弃")
            return None
        except Exception as e:
            logger.warning(f"[kb_store] LLM({provider}) 调用异常: {e}")
            return None
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 输出里尽量抠出 JSON。

    模型偶发不守"只输出 JSON"的约定：包 ```json 代码块、JSON 字符串里写字面
    换行、对象末尾多逗号都见过。这里按代价从低到高逐级兜底，尽量把结构化答案
    救回来——解析失败只会让答案退化成"片段直出"，用户体感明显变差。
    """
    if not text:
        return None
    s = text.strip()
    # 去 ```json / ``` 包裹
    s = re.sub(r"^```(?:json|JSON)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    s = s.strip()

    candidates = [s]
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b > a:
        candidates.append(s[a:b + 1])

    # 1) 直接解析；strict=False 放行字符串里的字面换行/制表符
    for cand in candidates:
        for strict in (True, False):
            try:
                obj = json.loads(cand, strict=strict)
                if isinstance(obj, dict) and obj.get("answer"):
                    return obj
            except Exception:
                pass
    # 2) 去掉对象/数组末尾多余的逗号再试（模型常见手滑）
    for cand in candidates:
        fixed = re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            obj = json.loads(fixed, strict=False)
            if isinstance(obj, dict) and obj.get("answer"):
                return obj
        except Exception:
            pass
    return None


def _format_history(history: Optional[List[Dict[str, Any]]]) -> str:
    """把前端传来的对话历史压成 prompt 用的文本段（只取最近 6 条，每条截 300 字）。

    没有 history 时返回占位文案——模板里该段固定存在，避免 .format 缺键报错。
    """
    if not history:
        return "（无，本轮为对话首问）"
    lines = []
    for m in history[-6:]:
        if not isinstance(m, dict):
            continue
        content = (m.get("content") or "").strip()
        if not content:
            continue
        who = "用户" if m.get("role") == "user" else "助手"
        lines.append(f"{who}：{content[:300]}")
    return "\n".join(lines) if lines else "（无，本轮为对话首问）"


def _log_query(session_factory: Any, **fields: Any) -> Optional[int]:
    """把一次问答的检索/生成质量指标写入 kb_query_log（best-effort，失败不影响回答）。

    session_factory 为 app.py 注入的 SQLAlchemy sessionmaker；未注入（本地单测 KB 模块）
    时直接跳过。任何异常只 warning，绝不向上抛——日志是观测手段，不能变成新故障点。
    """
    if session_factory is None:
        return None
    try:
        from sqlalchemy import text
        session = session_factory()
        try:
            res = session.execute(text(
                "INSERT INTO kb_query_log "
                "(question, username, hit_count, top_titles, doc_types, llm_ok, json_ok, "
                " degraded, no_answer_fixed, dispatch_status, llm_ms, total_ms) "
                "VALUES (:question, :username, :hit_count, :top_titles, :doc_types, :llm_ok, "
                "        :json_ok, :degraded, :no_answer_fixed, :dispatch_status, :llm_ms, :total_ms)"
            ), {
                "question": (fields.get("question") or "")[:500],
                "username": (fields.get("username") or None),
                "hit_count": int(fields.get("hit_count") or 0),
                "top_titles": json.dumps(fields.get("top_titles") or [], ensure_ascii=False),
                "doc_types": json.dumps(fields.get("doc_types") or [], ensure_ascii=False),
                "llm_ok": 1 if fields.get("llm_ok") else 0,
                "json_ok": 1 if fields.get("json_ok") else 0,
                "degraded": 1 if fields.get("degraded") else 0,
                "no_answer_fixed": 1 if fields.get("no_answer_fixed") else 0,
                "dispatch_status": (fields.get("dispatch_status") or None),
                "llm_ms": int(fields.get("llm_ms") or 0),
                "total_ms": int(fields.get("total_ms") or 0),
            })
            session.commit()
            return getattr(res, "lastrowid", None)
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"[kb_store] 查询日志写入失败（不影响回答）: {e}")
        return None


def ask(query: str,
        location: Any = None,
        top_k: int = 6,
        provider: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        session_factory: Any = None,
        username: Optional[str] = None) -> Dict[str, Any]:
    """
    统一问答入口。
    返回：
    {
      "answer": str,
      "citations": [{"title","doc_type","source","excerpt"}],
      "dispatch": dict|None,   # 地理派单结果（若有坐标/派单意图）
      "retrieved": [...]       # 原始召回，供调试
      "log_id": int|None,      # kb_query_log 主键（供前端"有用/没用"反馈关联）
      "need_location": bool,   # 派单需要坐标时为 True，前端弹地图点选
      "message": str           # need_location 时的提示语
    }
    """
    from kb_common import call_llm

    _t0 = time.time()
    _llm_ms = 0
    _llm_ok = False       # LLM 是否有响应（含超时/失败）
    _json_ok = False      # LLM 是否按 prompt 要求输出结构化 JSON
    _no_answer_fixed = False  # LLM 误报"暂无相关内容"是否被兜底纠正

    # 1) 地理派单（与检索解耦，独立业务）
    dispatch = None
    if location is not None or is_dispatch_question(query):
        try:
            dispatch = match_department_dispatch(query, location)
        except Exception as e:
            logger.warning(f"[kb_store] 派单调用异常: {e}")

    # 派单判定为"部门已识别但缺坐标"时，通知前端弹地图点选（旧版前端等的
    # need_location 后端从不返回，地图弹窗实际点不动，此处补上）
    need_location = bool(dispatch and dispatch.get("layer_status") == "no_location")
    dispatch_status = (dispatch or {}).get("layer_status")

    def _finish(result: Dict[str, Any], degraded: bool) -> Dict[str, Any]:
        """统一出口：补 degraded/log_id/need_location 并落查询日志。"""
        result.setdefault("dispatch", dispatch)
        result.setdefault("need_location", need_location)
        result["degraded"] = degraded
        if need_location:
            result.setdefault("message", (dispatch or {}).get("answer") or "请在地图上点选具体位置")
        result["log_id"] = _log_query(
            session_factory,
            question=query, username=username,
            hit_count=len(result.get("retrieved") or []),
            top_titles=[h.get("title") for h in (result.get("retrieved") or [])[:3]],
            doc_types=sorted({h.get("doc_type") for h in (result.get("retrieved") or []) if h.get("doc_type")}),
            llm_ok=_llm_ok, json_ok=_json_ok, degraded=degraded,
            no_answer_fixed=_no_answer_fixed, dispatch_status=dispatch_status,
            llm_ms=_llm_ms, total_ms=int((time.time() - _t0) * 1000),
        )
        return result

    # 2) 语义召回（默认排除废止法规；分桶后检索量放大，保证小类标准进入上下文）
    hits = search(query, top_k=max(int(top_k), 12))
    retrieved = hits

    if not hits:
        return _finish({
            "answer": "知识库中暂无相关内容",
            "citations": [],
            "retrieved": [],
        }, degraded=False)

    # 3) 拼 prompt + 调 LLM（带硬超时，避免慢 LLM 把请求拖到前端 abort）
    context = _format_context(hits)
    prompt = _SYSTEM_TEMPLATE.format(context=context, query=query,
                                     history_section=_format_history(history))
    # 主 provider（路由层不传时为 kb_common.LLM_PROVIDER，本地/生产均配 doubao）
    # 先调，单次预算 50s；失败（含超时）才回退到【不同的】provider 再给 50s。
    # 旧版用参数原值 `provider != "doubao"` 判断——provider=None 时实际主调已是
    # 豆包，却仍判定"非豆包"又重打一次豆包，豆包一抖就是两次串行长等。
    _llm_t0 = time.perf_counter()
    raw = _call_llm_timeout(prompt, provider, per_call_timeout=50)
    if raw is None and (provider or LLM_PROVIDER) != "doubao":
        logger.warning("[kb_store] 主 LLM provider 调用失败/超时，自动回退豆包（预算 50s）")
        raw = _call_llm_timeout(prompt, "doubao", per_call_timeout=50)
    _llm_ms = int((time.perf_counter() - _llm_t0) * 1000)
    _llm_ok = raw is not None
    parsed = _extract_json(raw) if raw else None

    if parsed and isinstance(parsed, dict) and parsed.get("answer"):
        _json_ok = True
        answer = parsed["answer"]
        citations = parsed.get("citations", []) or []
        # ---- LLM 误拒兜底：检索明明召回到了内容，LLM 却谎报“暂无” ----
        # 背景：检索成功（hits 非空）但 LLM 把“问法不同（怎么交/在哪里交）”
        # 误判成“没有内容”，返回“知识库中暂无相关内容”。这会浪费已召回的
        # qa 直答（如 12345 第 159 条缴费流程），让用户拿到假空答案——体感即
        # “召回不到”，其实内容召回到了。旧版兜底只认 qa 命中，standard/org/law
        # 被谎报时假空照样透传；现泛化为：有 qa 用 qa 直出，否则用片段直出，
        # 绝不让“LLM 误判”伪装成“知识库无内容”。
        # 但拒答分“误拒”与“正确拒绝”（知识库确实没有该实体），必须经
        # _refusal_is_false 主题闸门确认片段与问题同主题才覆盖——否则问
        # “银龙水务电话”会倒出首创水费/供热电话等不相关原文，比诚实拒答更糟。
        if _looks_like_no_answer(answer) and _refusal_is_false(query, hits):
            _no_answer_fixed = True
            qa_hits = [h for h in hits if h.get("doc_type") == "qa"]
            if qa_hits:
                logger.warning("[kb_store] LLM 误判为暂无，闸门确认同主题，强制改用 qa 片段直出")
                answer = _QA_FALLBACK_PREFIX + _qa_direct_answer(qa_hits)
                citations = [{
                    "title": h["title"],
                    "doc_type": h["doc_type"],
                    "source": h["source"],
                    "excerpt": (h["text"] or "")[:80],
                } for h in qa_hits[:3]]
            else:
                logger.warning("[kb_store] LLM 误判为暂无，闸门确认同主题，改用检索片段直出（不返回假空）")
                answer = _degraded_answer(hits, reason="大模型未能给出综合回答")
                citations = [{
                    "title": h["title"],
                    "doc_type": h["doc_type"],
                    "source": h["source"],
                    "excerpt": (h["text"] or "")[:80],
                } for h in hits[:3]]
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

    # degraded = LLM 没按 JSON 出（答案走原文/片段直出兜底）或误报暂无被纠正——
    # 两者都意味着"用户拿到的不是 LLM 结构化答案"，是查询日志里要重点盯的指标
    return _finish({
        "answer": answer,
        "citations": norm_citations,
        "retrieved": retrieved,
    }, degraded=(not _json_ok) or _no_answer_fixed)
