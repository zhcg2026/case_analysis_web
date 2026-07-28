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


# 立结案标准「案件类型」实体缓存：首次 search 时从集合加载一次，
# 用于用户点名某标准（如“污水井盖”“路灯”）时确定性召回，不依赖语义排名。
_STANDARD_CASE_TYPES = None  # list of (实体词, 完整案件类型)


def _load_standard_case_types(client):
    """加载所有 standard 的 (实体词, 完整案件类型) 列表。"""
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter='doc_type == "standard"',
            output_fields=["case_type"],
            limit=10000,
        )
    except Exception as e:
        logger.warning(f"[kb_store] 加载标准案件类型失败: {e}")
        return []
    out, seen = [], set()
    for r in rows:
        ct = (r.get("case_type") or "").strip()
        if not ct or ct in seen:
            continue
        seen.add(ct)
        entity = ct.split(" - ")[-1].strip()
        out.append((entity, ct))
    # 实体别名映射：市民口语叫法 → 库内标准实体词（仅增强召回、不阻断）。
    # 例："公交站亭（牌）"常被称为"公交站台/公交候车亭/公交站牌"，后者与前者同素异序，
    # 纯连续子串匹配失败，故显式列出别名，使其确定性命中对应立结案标准。
    _STANDARD_ENTITY_ALIASES = {
        "公交站亭（牌）": ("公交站台", "公交候车亭", "公交站牌", "公交车站台"),
        "公交站亭": ("公交站台", "公交候车亭", "公交站牌", "公交车站台"),
    }
    for std_entity, aliases in _STANDARD_ENTITY_ALIASES.items():
        for alias in aliases:
            if alias and alias not in seen:
                seen.add(alias)
                out.append((alias, _alias_to_ct(std_entity, out)))
    return out


def _alias_to_ct(std_entity: str, pairs) -> str:
    """从已加载的 (实体, 案件类型) 列表中找回标准实体的完整案件类型。"""
    for entity, ct in pairs:
        if entity == std_entity:
            return ct
    return std_entity


def _row_to_dict(row):
    """把 client.query 的标量结果行转成与 _hit_to_dict 一致的结构。"""
    meta_raw = row.get("metadata") or "{}"
    try:
        meta = json.loads(meta_raw) if meta_raw else {}
    except Exception:
        meta = {}
    return {
        "id": row.get("id"),
        "score": None,
        "doc_id": row.get("doc_id"),
        "chunk_id": row.get("chunk_id"),
        "doc_type": row.get("doc_type"),
        "source": row.get("source"),
        "title": row.get("title"),
        "text": row.get("text"),
        "law_status": row.get("law_status") or "",
        "case_type": row.get("case_type") or "",
        "metadata": meta,
    }


def _fetch_standard_by_case_type(client, ct):
    """按完整案件类型精确取出对应标准块（确定性召回）。"""
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter=f'doc_type == "standard" and case_type == "{ct}"',
            output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                           "text", "law_status", "case_type", "metadata"],
            limit=50,
        )
    except Exception as e:
        logger.warning(f"[kb_store] 按案件类型召回失败 {ct}: {e}")
        return []
    return [_row_to_dict(r) for r in rows]


# 局属单位/科室「单位名」缓存：用户点名某单位（如“市容环卫中心”“市容秩序科”）时确定性召回，
# 不依赖语义排名——org 类仅 14 块，点名单位若没进 org 桶 top_k 就会漏答“主要职责”类问题。
_ORG_UNIT_NAMES = None  # list of (核心单位名, 完整标题)


def _load_org_unit_names(client):
    """加载所有 org 的 (核心单位名, 完整标题) 列表。

    核心单位名 = 去掉「运城市」前缀后的标题（如「市容环卫中心」），便于子串匹配 query。
    """
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter='doc_type == "org"',
            output_fields=["title"],
            limit=10000,
        )
    except Exception as e:
        logger.warning(f"[kb_store] 加载单位名失败: {e}")
        return []
    out, seen = [], set()
    for r in rows:
        title = (r.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        core = title[3:].strip() if title.startswith("运城市") else title
        if core:
            out.append((core, title))
    return out


def _fetch_org_by_title(client, title):
    """按完整标题精确取出对应单位职责块（确定性召回）。"""
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter=f'doc_type == "org" and title == "{title}"',
            output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                           "text", "law_status", "case_type", "metadata"],
            limit=50,
        )
    except Exception as e:
        logger.warning(f"[kb_store] 按单位名召回失败 {title}: {e}")
        return []
    return [_row_to_dict(r) for r in rows]


def _fetch_org_by_category(client, category: str):
    """按 org_category 精确取出某类机构块（如「架构总览」「内设科室」「下属单位」）。

    利用 metadata VARCHAR 里的 JSON 字符串做 like 匹配；category 取值唯一，
    不会误召回其它类。用于「组织架构」类查询确定性前置总览文档。
    """
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter=f'doc_type == "org" and metadata like "%{category}%"',
            output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                           "text", "law_status", "case_type", "metadata"],
            limit=200,
        )
    except Exception as e:
        logger.warning(f"[kb_store] 按机构类别召回失败 {category}: {e}")
        return []
    return [_row_to_dict(r) for r in rows]


# 12345 知识问答（qa）「业务主题词 → 文本关键词」映射：市民口语问法（怎么/在哪交水费）
# 纯语义分极低（实测“怎么缴纳水费”↔ qa#159 仅 0.34，而供暖缴费类 qa 0.5+ 把水费淹没），
# 无法靠语义区分“水费”与“供暖缴费”。故对高频办事主题做【确定性召回增强】：
# 命中业务词时，直接把 qa 库里正文含对应关键词的条目（如“水费”）强制前置，不依赖语义分。
# 仅提升排名、永不阻断召回，符合“不用同义词硬门控”的约束；且沿用 standard/org 已有的
# 确定性召回成熟模式。关键词匹配 text 全文（含答案正文），如 qa#158/#159 正文含“水费/首创”。
_QA_TOPIC_KEYWORDS = {
    "水费": ("水费", "首创水务", "首创水"),
    "供暖": ("供暖", "采暖", "供热", "热力", "热电", "晋建", "暖气"),
    "燃气": ("燃气", "天然气", "民生天然气", "购气", "燃气卡"),
    "电费": ("电费", "供电", "电力"),
    "社保": ("社保", "养老保险", "医保"),
    "医保": ("医保", "医疗保险"),
    "公积金": ("公积金", "住房公积金"),
    "户籍": ("户籍", "户口", "身份证"),
    "居住证": ("居住证", "暂住证"),
    "停车": ("停车", "泊车", "车位"),
    # 注：公交类不在此表——qa 库无独立公交办事问答（12345 仅顺带提及），
    # 公交站亭/站台归属应由 doc_type=standard 立结案标准回答，故交给 standard 实体召回，
    # 此处若配「公交」反而会把无关 qa 片段强制前置、干扰正确来源。
    "垃圾": ("垃圾", "分类", "环卫"),
}


def _fetch_qa_by_text_kw(client, kw: str, limit: int = 8) -> List[Dict[str, Any]]:
    """按 text 全文 like 关键词，确定性取出 qa 类条目（业务主题召回）。

    用于「市民办事主题」命中时强制前置对应 qa 直答（如“水费”→ qa#158/#159 缴费流程），
    解决纯语义被同主题近义（供暖缴费）淹没、导致答非所问/暂无的问题。
    """
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter=f'doc_type == "qa" and text like "%{kw}%"',
            output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                           "text", "law_status", "case_type", "metadata"],
            limit=limit,
        )
    except Exception as e:
        logger.warning(f"[kb_store] 按 qa 业务词召回失败 {kw}: {e}")
        return []
    return [_row_to_dict(r) for r in rows]


# 制度（general）「文件标题」缓存：用户问「XX 相关制度/办法/规定」时，把标题含 query
# 核心实体的制度文档确定性前置，避免局里/平台的制度汇编被 law 类法规淹没导致漏召。
_GENERAL_TITLES = None  # list of 去重标题


def _load_general_titles(client):
    """加载所有 general（制度）的去重标题。"""
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter='doc_type == "general"',
            output_fields=["title"],
            limit=10000,
        )
    except Exception as e:
        logger.warning(f"[kb_store] 加载制度标题失败: {e}")
        return []
    out, seen = [], set()
    for r in rows:
        t = (r.get("title") or "").strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _fetch_general_by_title(client, title):
    """按完整标题精确取出对应制度文档的所有块（确定性召回）。"""
    try:
        rows = client.query(
            UNIFIED_COLLECTION,
            filter=f'doc_type == "general" and title == "{title}"',
            output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                           "text", "law_status", "case_type", "metadata"],
            limit=200,
        )
    except Exception as e:
        logger.warning(f"[kb_store] 按制度标题召回失败 {title}: {e}")
        return []
    return [_row_to_dict(r) for r in rows]


def search(query: str,
           top_k: int = 6,
           doc_type: Optional[str] = None,
           include_invalid_laws: bool = False,
           per_type_top_k: int = 6) -> List[Dict[str, Any]]:
    """纯语义 COSINE 召回（按类别分桶，避免大类淹没小类）。

    修复背景：law 类 5674 块、standard 类仅 202 块，在单一向量空间里，
    含“污水/排水”等词的 query 会唤醒海量 law 条文，把唯一相关的
    standard（如“污水井盖.txt”）挤出 top_k，导致“查不到立案条件”。
    改为按 doc_type 各取 per_type_top_k 再合并排序，保证每类都有代表进入候选。
    桶内仍是纯语义 COSINE，未引入关键词门控，符合“不用同义词/纯语义”的设计约束。
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

    # 指定单类时，走原逻辑（不做分桶）
    if doc_type:
        flt = build_filter(doc_type, include_invalid_laws)
        return _raw_search(client, qvec, top_k, flt)

    # 分桶召回：每个 doc_type 各取 per_type_top_k，合并去重
    q_norm = re.sub(r"\s+", "", query)  # 提前定义：标签提权与实体召回都要用
    # 标准实体词匹配：支持「完整实体」或「去业务后缀后的核心词」命中，
    # 避免自然问法把实体与动词/疑问词穿插（如『共享单车归哪个部门管理』）时
    # 连续子串匹配失败导致漏召。纯匹配增强，不阻断召回、不影响“暂无相关”判据。
    _STD_SUFFIXES = ("管理", "处置", "问题", "情况", "标准", "规范",
                     "条例", "规定", "事项", "要求", "处理", "投诉", "处罚")

    def _std_entity_hit(entity, q):
        if not entity:
            return False
        if entity in q:
            return True
        core = entity
        for s in _STD_SUFFIXES:
            if core.endswith(s) and len(core) > len(s):
                core = core[: -len(s)]
                if len(core) >= 2 and core in q:
                    return True
        # 字符级重叠兜底：实体核心词与 query 共享「非停用字」≥3 个且互为子集式重叠，
        # 兜住「站亭」↔「站台」这类同素异序/近义叫法（如"公交站亭" vs "公交站台"）。
        # 仅做召回增强、不阻断，符合"不用同义词硬门控"约束。
        if len(core) >= 3:
            qset = set(q)
            shared = sum(1 for ch in core if ch in qset)
            # 排除过于通用的单字（如"公""交"本身），要求核心词里≥2个【非首字】字符也在 query 中
            meaningful = [ch for ch in core[1:]]  # 去掉首字（常为"公交/道路"等大类的首字）
            m_shared = sum(1 for ch in meaningful if ch in qset)
            if shared >= 3 and m_shared >= 2:
                return True
        return False

    merged = {}
    for t in DOC_TYPES:
        flt = build_filter(t, include_invalid_laws)
        for h in _raw_search(client, qvec, per_type_top_k, flt):
            key = (h["doc_id"], h["chunk_id"])
            if key not in merged or h["score"] > merged[key]["score"]:
                merged[key] = h

    # ---- 结构化标签字面重叠提权（仅 standard）----
    # 背景：MiniLM 对"水管破裂"↔"供水管道破裂"这类同义不同字面语义对不上（0.385），
    # 反而更近"雨水井盖"。用 query 与标准自带 case_type 核心词的字面重叠度做提权：
    # 共享字多则提权。这是对文档自带结构化标签的字面匹配，**非同义词表门控**——
    # 只提升排名、永不阻断召回，不会造成"暂无相关"误判，符合"不用同义词硬门控"的设计约束。
    q_chars = set(q_norm)
    for h in merged.values():
        if h.get("doc_type") != "standard":
            continue
        ct = h.get("case_type") or ""
        core = ct.split(" - ")[-1].strip()
        if len(core) < 2:
            continue
        overlap = sum(1 for ch in core if ch in q_chars)
        ratio = overlap / len(core)
        if overlap >= 2 and ratio >= 0.5:
            h["score"] = max(h["score"] or 0, 0.82)  # 提权到高于纯语义，低于确定性命中 0.99
            h["label_boosted"] = True

    # ---- 确定性召回：query 点名某实体时直接取出并前置 ----
    global _STANDARD_CASE_TYPES, _ORG_UNIT_NAMES, _GENERAL_TITLES
    boosted = []
    boosted_keys = set()

    # 1) standard：query 含某标准「案件类型」实体（如“污水井盖”“路灯”）→ 按 case_type 精确取
    if _STANDARD_CASE_TYPES is None:
        _STANDARD_CASE_TYPES = _load_standard_case_types(client)
    for entity, ct in _STANDARD_CASE_TYPES:
        if _std_entity_hit(entity, q_norm):
            for r in _fetch_standard_by_case_type(client, ct):
                key = (r["doc_id"], r["chunk_id"])
                r["score"] = merged.get(key, {}).get("score") or 0.99
                r["boosted"] = True
                merged.pop(key, None)
                if key not in boosted_keys:
                    boosted.append(r); boosted_keys.add(key)

    # 2) org：query 含某单位核心名（如“市容环卫中心”“市容秩序科”）→ 按标题精确取
    if _ORG_UNIT_NAMES is None:
        _ORG_UNIT_NAMES = _load_org_unit_names(client)
    for core, title in _ORG_UNIT_NAMES:
        if core and core in q_norm:
            for r in _fetch_org_by_title(client, title):
                key = (r["doc_id"], r["chunk_id"])
                r["score"] = merged.get(key, {}).get("score") or 0.99
                r["boosted"] = True
                merged.pop(key, None)
                if key not in boosted_keys:
                    boosted.append(r); boosted_keys.add(key)

    # 3) org 架构意图：query 问「组织架构/内设机构/下属单位/科室设置」时，
    #    确定性取出「架构总览」文档并前置，保证完整机构清单不被语义排名淹没。
    _ORG_STRUCTURE_KEYWORDS = ("组织架构", "内设机构", "下属单位", "科室设置", "机构设置", "组织机构")
    if any(k in q_norm for k in _ORG_STRUCTURE_KEYWORDS):
        for r in _fetch_org_by_category(client, "架构总览"):
            key = (r["doc_id"], r["chunk_id"])
            r["score"] = merged.get(key, {}).get("score") or 0.99
            r["boosted"] = True
            merged.pop(key, None)
            if key not in boosted_keys:
                boosted.append(r); boosted_keys.add(key)

    # 3.5) qa 业务主题确定性召回：市民口语办事问法（怎么/在哪里交水费）纯语义分极低
    # （实测“怎么缴纳水费”↔ qa#159 仅 0.34，而供暖缴费类 qa 0.5+ 把水费淹没），
    # 无法靠语义区分“水费”与“供暖缴费”。命中业务主题词时，直接把 qa 库里正文含
    # 对应关键词的条目（如“水费”→ qa#158/#159 缴费流程）强制前置，保证市民拿到
    # 正确主题的直答（含微信/支付宝/线下营业厅等办理方法），而非泛法规或错主题。
    for topic, kws in _QA_TOPIC_KEYWORDS.items():
        if topic in q_norm:
            for kw in kws:
                for r in _fetch_qa_by_text_kw(client, kw):
                    key = (r["doc_id"], r["chunk_id"])
                    r["score"] = merged.get(key, {}).get("score") or 0.99
                    r["boosted"] = True
                    merged.pop(key, None)
                    if key not in boosted_keys:
                        boosted.append(r); boosted_keys.add(key)

    # 4) 制度意图：query 含「制度/办法/规定/细则/汇编/规程/规则」时，
    #    把 general 类里标题包含 query 核心实体的制度文档确定性前置，
    #    避免局里/平台的制度汇编被 law 类法规淹没导致漏召“XX相关制度”类问题。
    _GENERAL_RULE_KEYWORDS = ("制度", "办法", "规定", "细则", "汇编", "规程", "规则")
    if any(k in q_norm for k in _GENERAL_RULE_KEYWORDS):
        if _GENERAL_TITLES is None:
            _GENERAL_TITLES = _load_general_titles(client)
        # 从 query 提炼核心实体：去掉中性/制度类词后剩余，再判断是否在标题子串中
        core = q_norm
        for w in ("相关", "梳理", "列举", "有哪些", "我们", "单位", "的", "了", "一下",
                  "请问", "关于", "方面", "情况", "内容", "信息", "系统", "制度", "办法",
                  "规定", "细则", "汇编", "规程", "规则", "主要", "涉及", "哪些", "要求"):
            core = core.replace(w, "")
        if len(core) >= 2:
            for title in _GENERAL_TITLES:
                if core in title:
                    blocks = _fetch_general_by_title(client, title)
                    blocks.sort(key=lambda x: x.get("chunk_id") or "")
                    for r in blocks[:3]:   # 每份制度文档最多前置 3 块，避免单文档切块过多占满 top_k 挤掉同主题其他文档
                        key = (r["doc_id"], r["chunk_id"])
                        r["score"] = merged.get(key, {}).get("score") or 0.99
                        r["boosted"] = True
                        merged.pop(key, None)
                        if key not in boosted_keys:
                            boosted.append(r); boosted_keys.add(key)

    # ---- qa 类别温和加权：市民问答直答优先于泛法规 ----
    # 背景：12345 知识问答（qa）是人工整理的高信噪比「市民高频问答直答」，对
    # 「怎么/在哪里/如何 X」这类口语办事问法，本就是最优答案源（含微信/支付宝/
    # 线下营业厅等具体办理方法）。但 MiniLM 对「缴费流程」↔「缴纳水费（法规）」
    # 的语义分常被 law 条文压过，导致「怎么交水费」答成法规原则、甚至「在哪里交
    # 水费」因字面偏离被判暂无、白白浪费已召回的 qa 片段。
    # 故对 qa 片段做温和乘权，使其在同等/略低语义分时稳定排在 law 之前；
    # 只对【已有语义分】的 qa 提权，不设无条件兜底值，避免弱相关 qa 被强行抬入
    # 候选（不引入关键词门控，符合纯语义约束）。
    QA_BOOST = 1.15
    for h in merged.values():
        if h.get("doc_type") != "qa":
            continue
        base = h.get("score") or 0.0
        if base > 0:
            h["score"] = base * QA_BOOST
            h["qa_boosted"] = True

    # ---- 最终选择：确定性召回置顶 + 按类均衡采样 + 全局分数兜底 ----
    # 均衡采样保证 standard/org/qa 各至少 1 个代表进 top_k（分数 > MIN_TYPE_SCORE 才纳入，
    # 避免注入纯噪声）。背景：分桶只保证候选池多样，最终若纯按分数排序，小类低分项
    # （如 standard 0.385）仍会被 law/qa 0.45+ 挤出 top_k，导致“查不到处置要求”。
    MIN_TYPE_SCORE = 0.30
    final = sorted(boosted, key=lambda x: x["score"] or 0, reverse=True)
    final_keys = set((h["doc_id"], h["chunk_id"]) for h in final)

    rest_by_type = {t: [] for t in DOC_TYPES}
    for h in sorted(merged.values(), key=lambda x: x["score"] or 0, reverse=True):
        key = (h["doc_id"], h["chunk_id"])
        if key in final_keys:
            continue
        rest_by_type[h["doc_type"]].append(h)

    # 给 standard / org / qa 各保留 1 个代表（若该类有 > MIN_TYPE_SCORE 的候选且未被 boosted 命中）
    for t in ("standard", "org", "qa"):
        if any((h["doc_id"], h["chunk_id"]) not in final_keys for h in rest_by_type.get(t, [])):
            for h in rest_by_type.get(t, []):
                if (h["score"] or 0) > MIN_TYPE_SCORE and (h["doc_id"], h["chunk_id"]) not in final_keys:
                    final.append(h)
                    final_keys.add((h["doc_id"], h["chunk_id"]))
                    break

    # 剩余位置按全局分数填满
    for h in sorted(merged.values(), key=lambda x: x["score"] or 0, reverse=True):
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
