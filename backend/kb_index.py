"""
kb_index.py —— 统一知识库索引脚本（阶段0）
================================================
把 KB_SOURCE_DIR（默认 D:/常用/知识库）下所有知识内容全量灌入单一 Milvus
集合 unified_kb。按子目录映射 doc_type：
  - 立结案标准/      -> standard  （整条切块，不拆父子；结构化字段进 metadata）
  - 局属单位职责/    -> org
  - 科室职责/        -> org
  - 知识问答/        -> qa        （按「数字.」切每条 Q-A）
  - 制度/            -> general   （切块 1500 字 / overlap 100）
  - 城市管理法律法规/ -> law       （按「第X条」切块；frontmatter.status 进 law_status 防废止法条）

刻意不入库（非知识内容）：laws_corpus.jsonl（与 .md 冗余）/ 法规采集清单.csv（台账）/ build_jsonl.py（脚本）。

用法：
  python kb_index.py                 # 增量（集合已存在则追加；首次务必 --reset）
  python kb_index.py --reset         # 删除并重建集合后全量灌入
  python kb_index.py --doc-type law  # 仅处理某一类（调试用）
  python kb_index.py --source "D:/其它路径"
"""
import os
import re
import sys
import json
import hashlib
import argparse
import logging

# ⚠️ 必须在 import kb_common 之前加载 .env，否则 kb_common 顶部读到的
#    USE_LOCAL_MODE / LLM_PROVIDER 等都是 None，会误走远程 Milvus 分支。
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT  # noqa: E402
from kb_embed import embed  # noqa: E402

# jieba 分词：供 BM25 关键词召回用（混合检索的关键词一路）。
# 灌库时对每条 text 分词存 text_tokens 字段，检索时对 query 分词后算 BM25 分。
import jieba  # noqa: E402

# zhconv：繁->简。部分法规 md 正文为繁体（源站抓取，如「第二十條」「大氣污染」），
# 转入库时统一转简体，使 BM25 字面匹配（权重 1.5）对简体查询生效、展示也给一线人员简体。
# 注意：只转【入库文本】，md 源文件保持原样（忠实源）。
# 软依赖：未安装时降级保留原文，不影响主流程与接口可用性。
try:
    import zhconv
    _HAS_ZHCONV = True
except ImportError:
    zhconv = None
    _HAS_ZHCONV = False
    logging.warning("[kb_index] 警告：zhconv 未安装，繁体法规将保留原文（BM25 简体查询可能弱召回）。"
          "  修复：pip install zhconv")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [kb_index] %(levelname)s %(message)s")
logger = logging.getLogger("kb_index")

UNIFIED_COLLECTION = "unified_kb"
DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2 实际输出维度
KB_SOURCE_DIR = os.getenv("KB_SOURCE_DIR", r"D:/常用/知识库")

# 子目录 -> doc_type
DIR_DOC_TYPE = {
    "立结案标准": "standard",
    "局属单位职责": "org",
    "科室职责": "org",
    "知识问答": "qa",
    "制度": "general",
    "城市管理法律法规": "law",
}

# 刻意不入库的文件（非知识内容）
SKIP_FILES = {"laws_corpus.jsonl", "法规采集清单.csv", "build_jsonl.py"}

# 根目录下的局机关文档：不归属任何子目录，但属于 org 类知识，单独入库。
# 键为文件名，值为 org_category 标记（供「组织架构」类查询直接命中总览文档、答案按类分组）。
ROOT_ORG_FILES = {
    "运城市城市管理局组织架构.txt": "架构总览",
    "运城市城市管理局.txt": "局机关",
}


def get_client():
    from pymilvus import MilvusClient
    if USE_LOCAL_MODE:
        logger.info(f"本地模式：Milvus Lite @ {LOCAL_MILVUS_FILE}")
        return MilvusClient(LOCAL_MILVUS_FILE)
    logger.info(f"远程模式：Milvus @ {MILVUS_HOST}:{MILVUS_PORT}")
    return MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")


def define_schema():
    from pymilvus import DataType, CollectionSchema, FieldSchema
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=16),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=16000),
        # 仅法律法规填充；检索时可用 expr 直接排除「已废止/已修改」，防误当作现行有效
        FieldSchema(name="law_status", dtype=DataType.VARCHAR, max_length=16),
        # 立结案标准的「案件类型」实体（如“污水井盖”“路灯”），抽成独立可查询字段，
        # 用于用户点名某标准时确定性召回，不依赖语义排名。
        FieldSchema(name="case_type", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=8192),
        # BM25 关键词召回用：对 text 做 jieba 分词后的 token 列表（JSON 数组字符串）。
        # 混合检索（向量语义 + BM25 关键词）的关键词一路，解决纯向量对「站亭↔站台」
        # 字序不同、「报修↔处置」同义不同字的漏召，无需手工维护别名表。
        FieldSchema(name="text_tokens", dtype=DataType.VARCHAR, max_length=8192),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
    ]
    return CollectionSchema(fields, description="统一知识库：立结案标准/职责/问答/制度/法律法规")


# ------------------------- 解析函数 -------------------------

def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_standard(path):
    """立结案标准 txt：每个标准产出**一个**业务块。

    设计演进（踩坑记录）：
    - v1 整条切块：案件类型+立案条件+长法规依据混成一向量，业务语义被法规稀释，
      同模板标准（污水/上水/雨水井盖）向量挤在一起，分不清实体。
    - v2 拆「business + law_ref」两块：解决了稀释，但 law_ref（多为同一段
      《城市道路管理条例》第二十三条）约 200 份几乎 identical，成为 boilerplate 噪声，
      把真正相关的 business 块挤出分桶 top4，导致“路灯不亮了找哪个部门”类查询召回不到。
    - v3（当前）：每标准只留**一个** business 块（向量仅含业务文本），把“法律依据 /
      采集要求”收进 metadata（供溯源展示、拼 prompt 时附上），同时把「案件类型」实体
      抽成独立可查询字段 case_type，供用户点名时确定性召回。
    """
    content = _read(path).strip()
    fn = os.path.splitext(os.path.basename(path))[0]
    parts = fn.split("_")
    big = parts[0] if parts else ""
    small = parts[1] if len(parts) > 1 else ""

    def field(name):
        m = re.search(rf"【{name}】(.*?)(?=\n【|$)", content, re.DOTALL)
        return m.group(1).strip() if m else ""

    case_type = field("案件类型")
    supervision = field("监管主体")
    responsibility = field("责任主体")
    legal_basis = field("法律依据")
    collection_req = field("采集要求")

    # 业务块：案件类型实体重复 3 遍（标题已含 1 次，共 4 次），强化实体权重，
    # 缓解同模板标准无法靠语义区分实体的问题。
    business = []
    if case_type:
        business.append(f"【案件类型】{case_type}")
        business.append(case_type)
        business.append(case_type)
    for name in ("立案条件", "监管主体", "责任主体"):
        v = field(name)
        if v:
            business.append(f"【{name}】{v}")
    business_text = "\n".join(business)

    meta_common = {
        "big_category": big,
        "small_category": small,
        "case_type": case_type,
        "supervision_subject": supervision,
        "responsibility_subject": responsibility,
        "legal_basis": legal_basis,
        "collection_requirement": collection_req,
    }

    chunks = [{
        "text": business_text,
        "title": fn,
        "case_type": case_type,   # 抽成独立字段，供 kb_store 点名确定性召回
        "meta": meta_common,
    }]
    return {"chunks": chunks}


def parse_org(path, category: str = ""):
    """单位/科室职责 txt：整条切块，org_name = 文件名；category 标记机构类别
    （内设科室 / 下属单位 / 架构总览 / 局机关），供答案按类分组。"""
    content = _read(path).strip()
    fn = os.path.splitext(os.path.basename(path))[0]
    return {
        "chunks": [{
            "text": content,
            "title": fn,
            "meta": {"org_name": fn, "org_category": category},
        }],
    }


def parse_qa(path):
    """12345 知识问答 txt：按「数字.」切每条 Q-A。"""
    lines = _read(path).splitlines()
    entries, cur = [], None
    for line in lines:
        m = re.match(r"^(\d+)\.\s*(.*)$", line)
        if m:
            if cur is not None:
                entries.append(cur)
            cur = {"num": m.group(1), "q": m.group(2).strip(), "a": []}
        elif cur is not None:
            cur["a"].append(line)
    if cur is not None:
        entries.append(cur)

    chunks = []
    for e in entries:
        q, a = e["q"], "\n".join(e["a"]).strip()
        if not q and not a:
            continue
        text = f"问题：{q}\n答案：{a}" if a else f"问题：{q}"
        chunks.append({
            "text": text,
            "title": f"12345问答 {e['num']}",
            "meta": {"q": q, "a": a, "num": e["num"]},
        })
    return {"chunks": chunks}


def chunk_general(text, size=1500, overlap=100):
    """通用文档（制度等大合集）：按空行分段聚合成 ~size 字块。"""
    segments = [s.strip() for s in re.split(r"\n\s*\n", text) if s.strip()]
    chunks, cur = [], ""
    for seg in segments:
        if len(cur) + len(seg) + 1 <= size:
            cur = (cur + "\n" + seg).strip() if cur else seg
        else:
            if cur:
                chunks.append(cur)
            while len(seg) > size:
                chunks.append(seg[:size])
                seg = seg[size - overlap:]
            cur = seg
    if cur:
        chunks.append(cur)
    return chunks


def parse_general(path):
    content = _read(path).strip()
    fn = os.path.splitext(os.path.basename(path))[0]
    return {
        "chunks": [{
            "text": t,
            "title": fn,
            "meta": {},
        } for t in chunk_general(content)],
    }


def parse_law_md(path):
    """法律法规 md：frontmatter 进 metadata；正文按「第X条」切块；status 进 law_status。"""
    raw = _read(path)
    meta, body = {}, raw
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            fm = raw[3:end]
            body = raw[end + 3:]
            for line in fm.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')

    # 兼容简繁「条/條」：部分法规 md 正文为繁体（源站抓取），如「第二十條」，
    # 仅匹配简体「条」会导致整部法切块失败、退化成「全文」单块（且被 embed 截断）。
    pat = re.compile(r"第[一二三四五六七八九十百零0-9]+[条條]")
    matches = list(pat.finditer(body))
    articles = []
    if not matches:
        articles.append(("全文", body.strip()))
    else:
        pre = body[: matches[0].start()].strip()
        if pre:
            articles.append(("概述", pre))
        for i, m in enumerate(matches):
            label = m.group(0)
            start = m.end()
            end2 = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            txt = body[start:end2].strip().lstrip(" \u3000\t")
            articles.append((label, txt))

    title = meta.get("title", os.path.splitext(os.path.basename(path))[0])
    law_status = meta.get("status", "")
    chunks = []
    for label, txt in articles:
        if not txt:
            continue
        # 繁->简（仅入库文本，md 源不动）；缺 zhconv 时保留原文
        if _HAS_ZHCONV:
            s_title = zhconv.convert(title, "zh-cn")
            s_label = zhconv.convert(label, "zh-cn")
            s_txt = zhconv.convert(txt, "zh-cn")
        else:
            s_title, s_label, s_txt = title, label, txt
        chunks.append({
            "text": f"{s_title} {s_label} {s_txt}",
            "title": f"{s_title} {s_label}",
            "meta": {
                "article_no": s_label,
                "title": s_title,
                "level": meta.get("level", ""),
                "authority": meta.get("authority", ""),
                "effective_date": meta.get("effective_date", ""),
                "source_url": meta.get("source_url", ""),
                "need_review": meta.get("need_review", ""),
            },
            "law_status": law_status,
        })
    return {"chunks": chunks}


# ------------------------- 入库 -------------------------

def doc_id_of(rel_path):
    return rel_path.replace("\\", "/")[:256]


def make_row(doc_id, idx, chunk, doc_type, source):
    text = chunk["text"]
    vec = embed(text)
    if vec is None:
        logger.warning(f"embedding 失败，跳过：{doc_id}#{idx}")
        return None
    mid = hashlib.md5(f"{doc_id}|{idx}".encode("utf-8")).hexdigest()[:16]
    # jieba 分词：供 BM25 关键词召回用。title 也拼进去（标题含实体词，如"公交站亭"），
    # 提升关键词一路对实体的命中率。去重保序，避免重复 token 稀释 BM25 的 tf 分。
    title = chunk.get("title") or ""
    tokens = list(dict.fromkeys(jieba.lcut(f"{title} {text}")))
    return {
        "id": mid,
        "doc_id": doc_id[:256],
        "chunk_id": str(idx),
        "doc_type": doc_type,
        "source": source[:512],
        "title": title[:512],
        "text": text[:16000],
        "law_status": (chunk.get("law_status") or "")[:16],
        "case_type": (chunk.get("case_type") or "")[:128],
        "metadata": json.dumps(chunk.get("meta", {}) or {}, ensure_ascii=False)[:8192],
        "text_tokens": json.dumps(tokens, ensure_ascii=False)[:8192],
        "embedding": vec,
    }


def _dispatch_parse(path, doc_type, category: str = ""):
    try:
        if doc_type == "standard":
            return parse_standard(path)
        if doc_type == "org":
            return parse_org(path, category)
        if doc_type == "qa":
            return parse_qa(path)
        if doc_type == "general":
            return parse_general(path)
        if doc_type == "law":
            return parse_law_md(path)
    except Exception as e:
        logger.error(f"解析失败 {path}: {e}")
        return None
    return None


def index_directory(client, base_dir, only_types=None):
    total = 0
    for sub, doc_type in DIR_DOC_TYPE.items():
        if only_types and doc_type not in only_types:
            continue
        d = os.path.join(base_dir, sub)
        if not os.path.isdir(d):
            logger.warning(f"目录不存在，跳过：{d}")
            continue
        # org 子目录 -> 机构类别标记（区分内设科室 / 下属单位，供答案按类分组）
        org_cat = ""
        if doc_type == "org":
            org_cat = "内设科室" if sub == "科室职责" else "下属单位"
        for root, _, files in os.walk(d):
            for fname in sorted(files):
                if fname in SKIP_FILES:
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if doc_type == "law":
                    if ext != ".md":
                        continue
                elif ext != ".txt":
                    continue
                path = os.path.join(root, fname)
                rel = os.path.relpath(path, base_dir)
                parsed = _dispatch_parse(path, doc_type, org_cat)
                if not parsed:
                    continue
                rows = []
                for idx, chunk in enumerate(parsed["chunks"]):
                    row = make_row(doc_id_of(rel), idx, chunk, doc_type, rel)
                    if row:
                        rows.append(row)
                if rows:
                    client.insert(UNIFIED_COLLECTION, rows)
                    total += len(rows)
                    logger.info(f"[{doc_type}] {rel} -> {len(rows)} chunks（累计 {total}）")

    # 根目录下的局机关文档（组织架构总览、局简介等）：同样入库为 org 类，
    # 标记 org_category，供「组织架构」类查询直接命中总览文档、答案按类分组。
    if not (only_types and "org" not in only_types):
        for fname, cat in ROOT_ORG_FILES.items():
            path = os.path.join(base_dir, fname)
            if not os.path.isfile(path):
                continue
            rel = fname
            parsed = _dispatch_parse(path, "org", cat)
            if not parsed:
                continue
            rows = []
            for idx, chunk in enumerate(parsed["chunks"]):
                row = make_row(doc_id_of(rel), idx, chunk, "org", rel)
                if row:
                    rows.append(row)
            if rows:
                client.insert(UNIFIED_COLLECTION, rows)
                total += len(rows)
                logger.info(f"[org/root] {rel} -> {len(rows)} chunks（累计 {total}）")
    return total


def _ensure_collection(client, reset):
    """创建/重建集合（带 FLAT 精确索引）。reset=True 时先删后建。返回是否新建。"""
    if client.has_collection(UNIFIED_COLLECTION):
        if reset:
            logger.info(f"删除旧集合 {UNIFIED_COLLECTION}")
            client.drop_collection(UNIFIED_COLLECTION)
        else:
            logger.info(f"集合 {UNIFIED_COLLECTION} 已存在，增量追加（首次建议 --reset）")
    created = False
    if not client.has_collection(UNIFIED_COLLECTION):
        from pymilvus.milvus_client.index import IndexParams
        client.create_collection(UNIFIED_COLLECTION, schema=define_schema())
        idx = IndexParams()
        # 本地库仅 6402 条 384 维，用 FLAT 精确检索（非 AUTOINDEX 近似）。
        # 实测 AUTOINDEX 在 milvus_lite 下对小库有严重召回失败：会把真实第 2 名
        # 的“污水井盖”标准块漏出 top60，导致“污水井盖立案条件”查不到。
        # FLAT 暴力检索零召回损失、毫秒级完成，本地场景最优。
        idx.add_index("embedding", index_type="FLAT", metric_type="COSINE")
        client.create_index(UNIFIED_COLLECTION, idx)
        logger.info(f"已创建集合 {UNIFIED_COLLECTION}（dim={DIM}, COSINE, FLAT 精确索引）")
        created = True
    return created


def rebuild_index(source=None, reset=False, only_types=None, progress_cb=None):
    """可被 Web 接口调用的重灌函数（供系统管理「重建索引」复用，替代旧 zip 批量上传死代码）。

    参数：
      source: 知识库根目录（默认 KB_SOURCE_DIR）
      reset: 是否删除并重建集合（全量重灌务必 True）
      only_types: 仅处理的 doc_type 集合（None=全部）
      progress_cb: 进度回调，签名 (phase:str, done:int, total:int, msg:str) -> None
    返回：dict {added, total_docs, stats}
    """
    source = source or KB_SOURCE_DIR
    if not os.path.isdir(source):
        raise FileNotFoundError(f"知识库目录不存在：{source}")

    client = get_client()
    _ensure_collection(client, reset)

    if progress_cb:
        progress_cb("parsing", 0, 0, "开始扫描知识库目录…")

    total = index_directory(client, source, only_types=only_types)

    if progress_cb:
        progress_cb("inserting", total, total, f"已插入 {total} 条，正在落盘…")

    try:
        client.flush(UNIFIED_COLLECTION)  # pymilvus 3.0：flush 接收单个集合名，非列表
    except Exception:
        pass
    try:
        stats = client.get_collection_stats(UNIFIED_COLLECTION)
    except Exception as e:
        stats = f"(stats 获取失败: {e})"
    logger.info(f"灌库完成：本次新增 {total} 条；集合统计：{stats}")
    return {"added": total, "stats": stats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="删除并重建集合后全量灌入")
    ap.add_argument("--source", default=KB_SOURCE_DIR, help="知识库根目录")
    ap.add_argument("--doc-type", default=None, help="仅处理指定 doc_type（调试），可逗号分隔")
    args = ap.parse_args()

    source = args.source
    if not os.path.isdir(source):
        logger.error(f"知识库目录不存在：{source}")
        sys.exit(1)

    only = set(args.doc_type.split(",")) if args.doc_type else None
    res = rebuild_index(source=source, reset=args.reset, only_types=only)
    logger.info(f"退出：本次新增 {res['added']} 条")


if __name__ == "__main__":
    main()
