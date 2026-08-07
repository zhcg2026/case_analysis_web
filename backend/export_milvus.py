"""从本地 Milvus Lite 导出 unified_kb 集合的所有记录为 JSONL 文件，
供后续导入到服务器 Milvus Standalone 使用。"""
import json
import sys
import os

LOCAL_MILVUS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_milvus.db")

from pymilvus import MilvusClient
UNIFIED_COLLECTION = "unified_kb"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "unified_kb_export.jsonl")

client = MilvusClient(LOCAL_MILVUS_PATH)
client.load_collection(UNIFIED_COLLECTION)

# 查询所有记录
rows = client.query(
    UNIFIED_COLLECTION,
    filter="",
    output_fields=["doc_id", "chunk_id", "doc_type", "source", "title",
                    "text", "law_status", "case_type", "metadata", "text_tokens",
                    "embedding"],
    limit=100000,
)

print(f"导出 {len(rows)} 条记录到 {OUTPUT_FILE}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for row in rows:
        # MilvusClient 返回的 embedding 可能是 list
        if "embedding" in row and not isinstance(row["embedding"], str):
            row["embedding"] = list(row["embedding"])
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

print("导出完成")
