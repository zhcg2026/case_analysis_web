"""
RAG (Retrieval-Augmented Generation) 核心模块
支持：文档上传、向量化、存储、检索、问答
"""

import os
import re
import json
import requests
from typing import List, Dict, Optional, Tuple
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)

# 配置
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')
OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text')
MILVUS_HOST = os.getenv('MILVUS_HOST', 'localhost')
MILVUS_PORT = os.getenv('MILVUS_PORT', '19530')
COLLECTION_NAME = os.getenv('MILVUS_COLLECTION', 'knowledge_base')

# 全局连接状态
_milvus_connected = False


def connect_milvus():
    """连接Milvus向量数据库"""
    global _milvus_connected
    if _milvus_connected:
        return True

    try:
        connections.connect(
            alias="default",
            host=MILVUS_HOST,
            port=MILVUS_PORT
        )
        _milvus_connected = True
        print(f"[RAG] 已连接Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
        return True
    except Exception as e:
        print(f"[RAG] Milvus连接失败: {e}")
        return False


def disconnect_milvus():
    """断开Milvus连接"""
    global _milvus_connected
    if _milvus_connected:
        try:
            connections.disconnect("default")
            _milvus_connected = False
        except:
            pass


def create_collection(dim: int = 768) -> Collection:
    """创建或获取向量集合"""
    connect_milvus()

    # 检查集合是否存在
    if utility.has_collection(COLLECTION_NAME):
        return Collection(COLLECTION_NAME)

    # 创建集合
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="chunk_id", dtype=DataType.INT64),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=1024),
    ]

    schema = CollectionSchema(fields, description="知识库向量集合")
    collection = Collection(COLLECTION_NAME, schema)

    # 创建索引（IVF_FLAT，适合中小规模数据）
    index_params = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index("embedding", index_params)

    print(f"[RAG] 创建集合: {COLLECTION_NAME}, 维度: {dim}")
    return collection


def get_embedding(text: str) -> Optional[List[float]]:
    """使用Ollama生成文本嵌入向量"""
    try:
        # 首先尝试使用embedding模型
        response = requests.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={
                "model": OLLAMA_EMBED_MODEL,
                "prompt": text
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json().get("embedding")

        # 如果embedding模型不存在，尝试使用主模型的embedding功能
        print(f"[RAG] Embedding模型不可用，尝试使用 {OLLAMA_MODEL}")
        response = requests.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={
                "model": OLLAMA_MODEL,
                "prompt": text
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json().get("embedding")

        print(f"[RAG] Embedding失败: {response.status_code}")
        return None

    except Exception as e:
        print(f"[RAG] Embedding异常: {e}")
        return None


def get_embedding_dim() -> int:
    """获取embedding维度"""
    # 测试文本获取维度
    test_embedding = get_embedding("测试")
    if test_embedding:
        return len(test_embedding)
    # 默认维度
    return 768


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Tuple[int, str]]:
    """
    文本分块
    返回: [(chunk_id, chunk_text), ...]
    """
    # 按段落分割
    paragraphs = re.split(r'\n\n+', text)

    chunks = []
    chunk_id = 0
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) <= chunk_size:
            current_chunk += "\n" + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append((chunk_id, current_chunk.strip()))
                chunk_id += 1
                # overlap: 保留部分前文
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_text + "\n" + para
            else:
                # 单个段落超过chunk_size，强制分割
                for i in range(0, len(para), chunk_size - overlap):
                    sub_chunk = para[i:i + chunk_size]
                    if sub_chunk.strip():
                        chunks.append((chunk_id, sub_chunk.strip()))
                        chunk_id += 1

    if current_chunk.strip():
        chunks.append((chunk_id, current_chunk.strip()))

    return chunks


def insert_document(doc_id: str, content: str, source: str = "", metadata: Dict = None) -> Dict:
    """
    插入文档到向量库
    返回: {"success": bool, "chunks": int, "message": str}
    """
    try:
        # 获取embedding维度并创建集合
        embed_dim = get_embedding_dim()
        collection = create_collection(embed_dim)

        # 文本分块
        chunks = chunk_text(content)

        if not chunks:
            return {"success": False, "chunks": 0, "message": "文档内容为空"}

        # 准备插入数据
        embeddings = []
        doc_ids = []
        chunk_ids = []
        contents = []
        sources = []
        metadatas = []

        metadata_str = json.dumps(metadata or {}, ensure_ascii=False)

        for chunk_id, content in chunks:
            embedding = get_embedding(content)
            if embedding:
                embeddings.append(embedding)
                doc_ids.append(doc_id)
                chunk_ids.append(chunk_id)
                contents.append(content)
                sources.append(source)
                metadatas.append(metadata_str)

        if not embeddings:
            return {"success": False, "chunks": 0, "message": "无法生成向量嵌入"}

        # 插入数据
        collection.insert([
            embeddings,
            doc_ids,
            chunk_ids,
            contents,
            sources,
            metadatas
        ])
        collection.flush()

        print(f"[RAG] 文档插入成功: doc_id={doc_id}, chunks={len(embeddings)}")
        return {
            "success": True,
            "chunks": len(embeddings),
            "message": f"成功插入{len(embeddings)}个文本块"
        }

    except Exception as e:
        print(f"[RAG] 文档插入失败: {e}")
        return {"success": False, "chunks": 0, "message": str(e)}


def search_similar(query: str, top_k: int = 5) -> List[Dict]:
    """
    搜索相似内容
    返回: [{"content": str, "source": str, "score": float, "metadata": dict}, ...]
    """
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return []

        collection = Collection(COLLECTION_NAME)
        collection.load()

        # 获取查询向量
        query_embedding = get_embedding(query)
        if not query_embedding:
            return []

        # 搜索
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["content", "source", "metadata", "doc_id", "chunk_id"]
        )

        # 解析结果
        similar_docs = []
        for hits in results:
            for hit in hits:
                similar_docs.append({
                    "content": hit.entity.get("content"),
                    "source": hit.entity.get("source"),
                    "doc_id": hit.entity.get("doc_id"),
                    "chunk_id": hit.entity.get("chunk_id"),
                    "score": hit.distance,
                    "metadata": json.loads(hit.entity.get("metadata") or "{}")
                })

        return similar_docs

    except Exception as e:
        print(f"[RAG] 搜索失败: {e}")
        return []


def delete_document(doc_id: str) -> Dict:
    """
    删除文档（按doc_id删除所有相关向量）
    """
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return {"success": True, "message": "集合不存在"}

        collection = Collection(COLLECTION_NAME)

        # 查询该文档的所有向量ID
        expr = f'doc_id == "{doc_id}"'
        results = collection.query(expr=expr, output_fields=["id"])

        if not results:
            return {"success": True, "message": "文档不存在"}

        # 删除
        ids_to_delete = [r["id"] for r in results]
        collection.delete(expr=expr)
        collection.flush()

        return {
            "success": True,
            "deleted": len(ids_to_delete),
            "message": f"删除了{len(ids_to_delete)}个向量"
        }

    except Exception as e:
        print(f"[RAG] 删除失败: {e}")
        return {"success": False, "message": str(e)}


def ask_question(question: str, top_k: int = 5) -> Dict:
    """
    RAG问答：检索相关内容 + LLM生成回答
    返回: {"answer": str, "sources": list, "success": bool}
    """
    try:
        # 检索相关内容
        similar_docs = search_similar(question, top_k)

        if not similar_docs:
            return {
                "answer": "知识库中没有找到相关信息。",
                "sources": [],
                "success": True
            }

        # 构建上下文
        context_parts = []
        sources = []
        for doc in similar_docs:
            context_parts.append(doc["content"])
            if doc["source"] not in sources:
                sources.append(doc["source"])

        context = "\n\n---\n\n".join(context_parts)

        # 调用Ollama生成回答
        prompt = f"""基于以下参考资料回答问题。如果资料中没有相关信息，请说明。

参考资料：
{context}

问题：{question}

请给出准确、简洁的回答："""

        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        if response.status_code == 200:
            answer = response.json().get("response", "")
            return {
                "answer": answer,
                "sources": sources,
                "success": True
            }
        else:
            return {
                "answer": f"LLM调用失败: {response.status_code}",
                "sources": sources,
                "success": False
            }

    except Exception as e:
        print(f"[RAG] 问答失败: {e}")
        return {"answer": str(e), "sources": [], "success": False}


def list_documents() -> List[Dict]:
    """
    列出所有文档（按doc_id聚合）
    返回: [{"doc_id": str, "chunks": int, "sources": list}, ...]
    """
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return []

        collection = Collection(COLLECTION_NAME)
        collection.load()

        # 查询所有数据
        results = collection.query(
            expr="id >= 0",
            output_fields=["doc_id", "source", "chunk_id"]
        )

        # 按doc_id聚合
        doc_map = {}
        for r in results:
            doc_id = r["doc_id"]
            if doc_id not in doc_map:
                doc_map[doc_id] = {"doc_id": doc_id, "chunks": 0, "sources": set()}
            doc_map[doc_id]["chunks"] += 1
            if r["source"]:
                doc_map[doc_id]["sources"].add(r["source"])

        # 转换为列表
        docs = []
        for doc_id, info in doc_map.items():
            docs.append({
                "doc_id": doc_id,
                "chunks": info["chunks"],
                "sources": list(info["sources"])
            })

        return docs

    except Exception as e:
        print(f"[RAG] 列出文档失败: {e}")
        return []


def get_collection_stats() -> Dict:
    """获取向量集合统计信息"""
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return {"exists": False, "count": 0}

        collection = Collection(COLLECTION_NAME)
        collection.load()

        return {
            "exists": True,
            "name": COLLECTION_NAME,
            "count": collection.num_entities,
            "ollama_host": OLLAMA_HOST,
            "ollama_model": OLLAMA_MODEL,
            "milvus_host": MILVUS_HOST
        }

    except Exception as e:
        return {"exists": False, "error": str(e)}


# 初始化时测试连接
def init_rag():
    """初始化RAG模块"""
    print("[RAG] 初始化...")

    # 测试Ollama连接
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"[RAG] Ollama可用，模型: {[m['name'] for m in models]}")
        else:
            print("[RAG] Ollama连接异常")
    except Exception as e:
        print(f"[RAG] Ollama连接失败: {e}")

    # 测试Milvus连接
    if connect_milvus():
        print("[RAG] Milvus连接成功")
        if utility.has_collection(COLLECTION_NAME):
            collection = Collection(COLLECTION_NAME)
            print(f"[RAG] 集合 '{COLLECTION_NAME}' 存在，向量数: {collection.num_entities}")

    print("[RAG] 初始化完成")