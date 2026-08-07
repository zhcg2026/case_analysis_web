"""将导出的 unified_kb JSONL 文件导入到服务器 Milvus Standalone。"""
import json
import sys
import os

sys.path.insert(0, "/app/backend")
os.environ.setdefault("MILVUS_HOST", "192.168.101.3")
os.environ.setdefault("MILVUS_PORT", "19530")
os.environ.setdefault("USE_LOCAL_MODE", "false")

from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema

UNIFIED_COLLECTION = "unified_kb"
DIM = 384
INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/unified_kb_export.jsonl"

client = MilvusClient(uri=f"http://192.168.101.3:19530")

# 创建集合（如果不存在）
if client.has_collection(UNIFIED_COLLECTION):
    print(f"集合 {UNIFIED_COLLECTION} 已存在，先删除")
    client.drop_collection(UNIFIED_COLLECTION)

# 定义 schema
fields = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=512),
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),
    FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1024),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=48000),
    FieldSchema(name="law_status", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="case_type", dtype=DataType.VARCHAR, max_length=256),
    FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=24000),
    FieldSchema(name="text_tokens", dtype=DataType.VARCHAR, max_length=24000),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
]
schema = CollectionSchema(fields, description="统一知识库")
client.create_collection(UNIFIED_COLLECTION, schema=schema)

# 创建索引
from pymilvus.milvus_client.index import IndexParams
idx = IndexParams()
idx.add_index("embedding", index_type="FLAT", metric_type="COSINE")
client.create_index(UNIFIED_COLLECTION, idx)
print(f"集合 {UNIFIED_COLLECTION} 已创建（FLAT + COSINE）")

# 读取并导入
rows = []
total = 0
batch_size = 500

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line.strip())
        # 确保 embedding 是 list
        if "embedding" in row and not isinstance(row["embedding"], list):
            row["embedding"] = list(row["embedding"])
        # 截断超长字段（Milvus VARCHAR 长度按字节计算，中文3字节）
        FIELD_LIMITS = {"id": 128, "doc_id": 512, "chunk_id": 64, "doc_type": 32,
                        "source": 1024, "title": 1024, "text": 48000, "law_status": 64,
                        "case_type": 256, "metadata": 24000, "text_tokens": 24000}
        for key, max_len in FIELD_LIMITS.items():
            val = row.get(key, "")
            if isinstance(val, str) and len(val.encode("utf-8")) > max_len:
                while len(val.encode("utf-8")) > max_len:
                    val = val[:max(1, len(val) * max_len // len(val.encode("utf-8")))]
                row[key] = val
        rows.append(row)
        if len(rows) >= batch_size:
            client.insert(UNIFIED_COLLECTION, rows)
            total += len(rows)
            print(f"已导入 {total} 条...")
            rows = []

if rows:
    client.insert(UNIFIED_COLLECTION, rows)
    total += len(rows)

# flush
try:
    client.flush(UNIFIED_COLLECTION)
except Exception:
    pass

print(f"导入完成：共 {total} 条")
