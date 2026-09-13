# -*- coding: utf-8 -*-
"""本地知识库链路分段计时（诊断用，不改任何业务逻辑）
用法：python backend/check_kb_perf.py
分解 ask 链路各环节耗时：Milvus打开 / MiniLM加载 / embed / BM25构建 / 混合检索 / 分类过滤检索 / 豆包LLM。
"""
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
# kb_common.LOCAL_MILVUS_FILE="./local_milvus.db" 按 CWD 解析：实际活库在 backend/ 下
# （根目录那个 local_milvus.db 是空的遗留文件），故 chdir 到 backend 与 app 启动一致。
os.chdir(BACKEND)


def timed(label, fn):
    t0 = time.perf_counter()
    out = fn()
    print(f"[timer] {label}: {time.perf_counter() - t0:.2f}s", flush=True)
    return out


print("=" * 60)
print("== 1) Milvus 本地库 ==")
import kb_common
from pymilvus import MilvusClient, DataType


def milvus_info():
    c = MilvusClient(kb_common.LOCAL_MILVUS_FILE)
    name = "unified_kb"
    if not c.has_collection(name):
        print("!! 集合 unified_kb 不存在")
        return c
    desc = c.describe_collection(name)
    for f in desc.get("fields", []):
        try:
            if f.get("type") == DataType.FLOAT_VECTOR:
                print("   embedding dim =", (f.get("params") or {}).get("dim"))
        except Exception:
            pass
    try:
        c.load_collection(name)
    except Exception:
        pass
    rows = c.query(name, filter="", output_fields=["doc_type"], limit=16000)
    print("   总行数 =", len(rows))
    print("   by_type =", dict(Counter(r["doc_type"] for r in rows)))
    return c


client = timed("Milvus 打开+load+统计", milvus_info)

print("=" * 60)
print("== 2) 本地 embedding (MiniLM) ==")
model = timed("MiniLM 冷加载", kb_common.get_local_embed_model)
vec = timed("单条 embed（warm）", lambda: kb_common.get_embedding("井盖破损的立案条件是什么"))
print("   向量维度 =", len(vec) if vec else None)

print("=" * 60)
print("== 3) BM25 索引构建（首次检索一次性成本，之后进程内缓存）==")
import kb_store

bm25, bm25_rows = timed("BM25 全库加载+分词建索引", lambda: kb_store._load_bm25_index(kb_store.get_client()))
print("   BM25 语料条数 =", len(bm25_rows) if bm25_rows else 0)

print("=" * 60)
print("== 4) 检索计时（warm）==")
QUERIES = [
    "井盖破损的立案条件",
    "公交站台破损归谁管",        # 字序陷阱：库里写的是“公交站亭”
    "小蓝车乱摆放归哪个部门",     # 别名扩展路径
]
for q in QUERIES:
    res = timed(f"search(混合检索)「{q}」", lambda q=q: kb_store.search(q, top_k=6))
    for h in res[:3]:
        print(f"   - {h['doc_type']} | {(h['title'] or '')[:44]} | rrf={round(h.get('rrf_score') or 0, 4)}")

q = QUERIES[1]
res = timed(f"search(doc_type=standard 过滤路径)「{q}」", lambda: kb_store.search(q, top_k=6, doc_type="standard"))
for h in res[:3]:
    print(f"   - {h['doc_type']} | {(h['title'] or '')[:44]} | cos={round(h.get('score') or 0, 4)}")

print("=" * 60)
print("== 5) LLM (doubao) 延迟 ==")
r1 = timed("豆包短 prompt", lambda: kb_common.call_llm("只回答两个字：你好", provider="doubao"))
print("   返回:", (r1 or "(空)")[:40])
real_prompt = (
    "你是运城市城市管理局智慧城管知识库问答助手。请仅依据下方检索片段回答问题，"
    "输出JSON：{\"answer\": \"...（150字左右）\", \"citations\": [{\"title\": \"...\", \"doc_type\": \"...\", \"source\": \"...\", \"excerpt\": \"...\"}]}。\n"
    + ("【片段】井盖破损：责任主体为市政公用服务中心，处置时限24小时，法律依据《城市道路管理条例》第二十三条。\n" * 15)
    + "问题：井盖破损的处置时限是多少？"
)
r2 = timed(f"豆包模拟真实问答 prompt（约{len(real_prompt)}字，要求JSON输出）", lambda: kb_common.call_llm(real_prompt, provider="doubao"))
print("   返回长度:", len(r2 or ""), "| 预览:", (r2 or "(空)")[:80].replace("\n", " "))

print("=" * 60)
print("完成")
