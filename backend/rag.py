"""
RAG (Retrieval-Augmented Generation) 核心模块
支持：文档上传、向量化、存储、检索、问答

本地调试模式（USE_LOCAL_MODE=true）：
- Milvus Lite（文件存储）
- sentence-transformers 本地embedding
- LLM使用豆包API

服务器模式（USE_LOCAL_MODE=false或不设置）：
- Docker Milvus
- Ollama nomic-embed-text
- LLM使用Qwen2.5-7B
"""

import os
import re
import json
import requests
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

# 加载环境变量（优先加载 .env.local）
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
elif os.path.exists('../.env.local'):
    load_dotenv('../.env.local')

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
    MilvusClient
)

# 从共享模块导入
try:
    from kb_common import (
        call_llm, get_embedding, get_local_embed_model, connect_milvus,
        disconnect_milvus, get_embedding_dim,
        USE_LOCAL_MODE, LLM_PROVIDER,
        OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_EMBED_MODEL,
        MILVUS_HOST, MILVUS_PORT,
        LOCAL_MILVUS_FILE, LOCAL_EMBED_MODEL,
        DOUBAO_API_KEY, DOUBAO_API_URL, DOUBAO_MODEL,
    )
except ImportError:
    from backend.kb_common import (
        call_llm, get_embedding, get_local_embed_model, connect_milvus,
        disconnect_milvus, get_embedding_dim,
        USE_LOCAL_MODE, LLM_PROVIDER,
        OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_EMBED_MODEL,
        MILVUS_HOST, MILVUS_PORT,
        LOCAL_MILVUS_FILE, LOCAL_EMBED_MODEL,
        DOUBAO_API_KEY, DOUBAO_API_URL, DOUBAO_MODEL,
    )

# 本模块特有配置
COLLECTION_NAME = os.getenv('MILVUS_COLLECTION', 'knowledge_base')


def create_collection(dim: int = 768) -> Collection:
    """创建或获取向量集合"""
    connect_milvus()

    if utility.has_collection(COLLECTION_NAME):
        return Collection(COLLECTION_NAME)

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

    index_params = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index("embedding", index_params)

    print(f"[RAG] 创建集合: {COLLECTION_NAME}, 维度: {dim}")
    return collection


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 100) -> List[Tuple[int, str]]:
    """
    文本分块
    返回: [(chunk_id, chunk_text), ...]
    """
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
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_text + "\n" + para
            else:
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
        embed_dim = get_embedding_dim()
        collection = create_collection(embed_dim)

        chunks = chunk_text(content)

        if not chunks:
            return {"success": False, "chunks": 0, "message": "文档内容为空"}

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
    搜索相似内容（混合搜索：向量 + 关键词）
    返回: [{"content": str, "source": str, "score": float, "metadata": dict}, ...]
    """
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return []

        collection = Collection(COLLECTION_NAME)
        collection.load()

        query_embedding = get_embedding(query)
        if not query_embedding:
            return []

        # 1. 向量搜索：扩大候选集
        search_limit = max(top_k * 4, 15)
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=search_limit,
            output_fields=["content", "source", "metadata", "doc_id", "chunk_id"]
        )

        all_docs = []
        seen_contents = set()
        for hits in results:
            for hit in hits:
                content = hit.entity.get("content", "")
                content_key = content[:50]
                if content_key in seen_contents:
                    continue
                seen_contents.add(content_key)
                all_docs.append({
                    "content": content,
                    "source": hit.entity.get("source"),
                    "doc_id": hit.entity.get("doc_id"),
                    "chunk_id": hit.entity.get("chunk_id"),
                    "vector_score": hit.distance,
                    "keyword_score": 0.0,
                    "metadata": json.loads(hit.entity.get("metadata") or "{}")
                })

        # 2. 关键词搜索
        try:
            keywords = []
            for length in [4, 3, 2]:
                for i in range(len(query) - length + 1):
                    segment = query[i:i+length]
                    if all('一' <= c <= '龥' for c in segment) and segment not in keywords:
                        keywords.append(segment)

            for kw in keywords[:5]:
                if len(kw) < 2:
                    continue
                try:
                    keyword_results = collection.query(
                        expr=f'content like "%{kw}%"',
                        output_fields=["content", "source", "metadata", "doc_id", "chunk_id"],
                        limit=5
                    )
                    for kr in keyword_results:
                        content = kr.get("content", "")
                        content_key = content[:50]
                        if content_key in seen_contents:
                            continue
                        seen_contents.add(content_key)
                        all_docs.append({
                            "content": content,
                            "source": kr.get("source"),
                            "doc_id": kr.get("doc_id"),
                            "chunk_id": kr.get("chunk_id"),
                            "vector_score": 0.0,
                            "keyword_score": 0.6,
                            "metadata": json.loads(kr.get("metadata") or "{}")
                        })
                except Exception:
                    pass
        except Exception:
            pass

        # 3. 加权融合排序
        for doc in all_docs:
            doc['score'] = (
                doc.get('vector_score', 0) * 0.7 +
                doc.get('keyword_score', 0) * 0.3
            )

        all_docs.sort(key=lambda x: x.get('score', 0), reverse=True)

        return all_docs[:top_k]

    except Exception as e:
        print(f"[RAG] 搜索失败: {e}")
        return []


def delete_document(doc_id: str) -> Dict:
    """删除文档（按doc_id删除所有相关向量）"""
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return {"success": True, "message": "集合不存在"}

        collection = Collection(COLLECTION_NAME)

        expr = f'doc_id == "{doc_id}"'
        results = collection.query(expr=expr, output_fields=["id"])

        if not results:
            return {"success": True, "message": "文档不存在"}

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


def delete_all_documents() -> Dict:
    """删除所有文档"""
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return {"success": True, "message": "集合不存在，无需删除"}

        utility.drop_collection(COLLECTION_NAME)
        print(f"[RAG] 已删除集合: {COLLECTION_NAME}")

        return {"success": True, "message": "已删除所有文档"}

    except Exception as e:
        print(f"[RAG] 删除所有文档失败: {e}")
        return {"success": False, "message": str(e)}


def ask_question(question: str, top_k: int = 15, min_score: float = 0.45, history: list = None) -> Dict:
    """
    RAG问答：检索相关内容 + LLM生成回答
    返回: {"answer": str, "sources": list, "success": bool}
    """
    try:
        similar_docs = search_similar(question, top_k)

        if not similar_docs:
            return {
                "answer": "知识库中没有找到相关信息。",
                "sources": [],
                "success": True
            }

        # 提取核心关键词（用于标题匹配）
        stop_words = ["职能", "中心", "服务中心", "运城市", "哪个", "部门", "管理", "负责", "是什么", "有哪些", "职责", "工作", "的", "是", "归", "属于"]
        keywords_text = question
        for w in stop_words:
            keywords_text = keywords_text.replace(w, "")

        keywords = []
        if keywords_text.strip():
            text = keywords_text.strip()
            if len(text) >= 2:
                keywords.append(text[:2])
            if len(text) >= 4:
                keywords.append(text[:4])
            keywords.append(text)

        title_matched = []
        score_matched = []
        for doc in similar_docs:
            source = doc.get("source", "")
            score = doc.get("score", 0)

            matched = False
            for kw in keywords:
                if kw and kw in source:
                    matched = True
                    break
            if matched and len(title_matched) < 3:
                title_matched.append(doc)
            elif score >= min_score:
                score_matched.append(doc)

        filtered_docs = title_matched[:2] + score_matched[:3-len(title_matched)]

        if not filtered_docs:
            return {
                "answer": "知识库中没有找到足够相关的信息。",
                "sources": [],
                "success": True
            }

        context_parts = []
        sources = []
        for i, doc in enumerate(filtered_docs, 1):
            score = doc.get("score", 0)
            source = doc.get("source", "未知")
            content = doc.get("content", "")
            if len(content) > 500:
                content = content[:500] + "..."
            matched_kw = [kw for kw in keywords if kw and kw in source]
            match_tag = "【标题匹配:" + ",".join(matched_kw) + "】" if matched_kw else ""
            context_parts.append(f"[资料{i}] {match_tag}来源: {source} (相似度: {score:.2f})\n内容: {content}")
            if source not in sources:
                sources.append(source)

        context = "\n\n---\n\n".join(context_parts)

        history_text = ""
        if history:
            for msg in history[-4:]:
                role = "用户" if msg.get("role") == "user" else "助手"
                history_text += f"- {role}：{msg.get('content', '')}\n"

        prompt = f"""你是运城市城市管理局的政策专家。请根据以下参考资料回答问题。

回答要求（必须严格遵守）：
1. **只能使用参考资料中的信息回答**，不要添加参考资料中没有的内容
2. 如果参考资料中有明确答案，直接给出，并注明来源
3. 如果涉及部门归属，说明负责部门和依据（必须来自参考资料）
4. 如果参考资料中没有相关内容，明确说明"根据现有知识库，未找到相关信息，建议咨询相关部门"
5. **禁止根据常识或推测补充知识库中没有的内容**
6. 回答要简洁准确，有理有据
7. 如果用户的问题是在追问之前的回答，结合对话历史理解上下文

{f"## 对话历史" + chr(10) + history_text if history_text else ""}

参考资料：
{context}

问题：{question}

请回答："""

        answer = call_llm(prompt, timeout=120)
        if answer:
            return {"answer": answer, "sources": sources, "success": True}
        else:
            return {"answer": "LLM调用失败，请稍后重试", "sources": sources, "success": False}

    except Exception as e:
        print(f"[RAG] 问答失败: {e}")
        return {"answer": str(e), "sources": [], "success": False}


def list_documents() -> List[Dict]:
    """列出所有文档（按doc_id聚合）"""
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return []

        collection = Collection(COLLECTION_NAME)
        collection.load()

        results = collection.query(
            expr="id >= 0",
            output_fields=["doc_id", "source", "chunk_id"]
        )

        doc_map = {}
        for r in results:
            doc_id = r["doc_id"]
            if doc_id not in doc_map:
                doc_map[doc_id] = {"doc_id": doc_id, "chunks": 0, "sources": set()}
            doc_map[doc_id]["chunks"] += 1
            if r["source"]:
                doc_map[doc_id]["sources"].add(r["source"])

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

        if USE_LOCAL_MODE:
            client = MilvusClient(LOCAL_MILVUS_FILE)
            collections = client.list_collections()
            if COLLECTION_NAME in collections:
                stats = client.get_collection_stats(COLLECTION_NAME)
                docs = list_documents()
                return {
                    "exists": True,
                    "name": COLLECTION_NAME,
                    "count": stats.get('row_count', 0),
                    "doc_count": len(docs),
                    "mode": "local (Milvus Lite)",
                    "embed_model": LOCAL_EMBED_MODEL,
                    "llm": f"豆包API ({DOUBAO_MODEL})"
                }
            else:
                return {"exists": False, "count": 0, "mode": "local"}
        else:
            if not utility.has_collection(COLLECTION_NAME):
                return {"exists": False, "count": 0}

            collection = Collection(COLLECTION_NAME)
            collection.load()

            docs = list_documents()
            return {
                "exists": True,
                "name": COLLECTION_NAME,
                "count": collection.num_entities,
                "doc_count": len(docs),
                "mode": "server",
                "ollama_host": OLLAMA_HOST,
                "ollama_model": OLLAMA_MODEL,
                "milvus_host": MILVUS_HOST
            }

    except Exception as e:
        return {"exists": False, "error": str(e)}


def init_rag():
    """初始化RAG模块"""
    print("[RAG] 初始化...")

    if USE_LOCAL_MODE:
        print("[RAG] 本地模式：使用 Milvus Lite + sentence-transformers + 豆包API")
        model = get_local_embed_model()
        if model:
            print("[RAG] 本地embedding模型加载成功")
        if connect_milvus():
            print("[RAG] Milvus Lite连接成功")
    else:
        print("[RAG] 服务器模式：使用 Docker Milvus + Ollama")
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                print(f"[RAG] Ollama可用，模型: {[m['name'] for m in models]}")
            else:
                print("[RAG] Ollama连接异常")
        except Exception as e:
            print(f"[RAG] Ollama连接失败: {e}")

        if connect_milvus():
            print("[RAG] Milvus连接成功")
            if utility.has_collection(COLLECTION_NAME):
                collection = Collection(COLLECTION_NAME)
                print(f"[RAG] 集合 '{COLLECTION_NAME}' 存在，向量数: {collection.num_entities}")

    print("[RAG] 初始化完成")
