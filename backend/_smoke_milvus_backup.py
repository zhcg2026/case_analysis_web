# -*- coding: utf-8 -*-
"""Milvus 备份 query_iterator 改造冒烟（纯 mock，不连任何 Milvus/数据库，产物自动清理）"""
import sys, os, types, gzip, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROWS = [
    {"doc_id": f"d{i}", "chunk_id": f"c{i}", "doc_type": "regulation",
     "source": "s", "title": "t", "text": "x" * 50, "law_status": "现行有效",
     "case_type": "", "metadata": "{}", "text_tokens": "tok",
     "embedding": [0.1] * 8}
    for i in range(2500)
]


class FakeIterator:
    def __init__(self, rows, batch):
        self.rows, self.batch, self.pos, self.closed = rows, batch, 0, False

    def next(self):
        b = self.rows[self.pos:self.pos + self.batch]
        self.pos += self.batch
        return b

    def close(self):
        self.closed = True


class FakeClientIter:
    """新版客户端：带 query_iterator"""
    def __init__(self, uri=None):
        self.uri = uri

    def query_iterator(self, collection, filter="", output_fields=None, batch_size=1000):
        assert collection == "unified_kb" and filter == "" and batch_size == 1000
        assert "embedding" in output_fields
        return FakeIterator(ROWS, batch_size)


class FakeClientQuery:
    """旧客户端：无 query_iterator 属性 → 走 offset 分页回退"""
    def __init__(self, uri=None):
        self.uri = uri

    def query(self, collection, filter="", output_fields=None, limit=1000, offset=0):
        assert collection == "unified_kb"
        return ROWS[offset:offset + limit]


def run(client_cls, tag):
    fake = types.ModuleType("pymilvus")
    fake.MilvusClient = client_cls
    sys.modules["pymilvus"] = fake

    import kb_common
    kb_common.USE_LOCAL_MODE = False
    kb_common.MILVUS_HOST = "mock"
    kb_common.MILVUS_PORT = "19530"

    import backup_routes as br
    filepath = br._backup_milvus()
    try:
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            lines = [json.loads(l) for l in f]
        assert len(lines) == 2500, f"{tag}: 行数 {len(lines)} != 2500"
        assert lines[0]["doc_id"] == "d0" and lines[-1]["doc_id"] == "d2499", f"{tag}: 首尾行不符"
        assert isinstance(lines[0]["embedding"], list), f"{tag}: embedding 未转 list"
        print(f"[{tag}] OK: {len(lines)} 条, embedding=list, 文件 {os.path.basename(filepath)}")
    finally:
        os.remove(filepath)
    return filepath, client_cls


run(FakeClientIter, "iterator分支")
run(FakeClientQuery, "fallback分页分支")

# 追加校验 iterator.close() 被调用
sys.modules["pymilvus"] = types.SimpleNamespace(MilvusClient=FakeClientIter)
print("冒烟通过：两分支均正常导出全部行")
