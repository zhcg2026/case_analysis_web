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
    MilvusClient  # Milvus Lite支持
)

# 本地模式配置（在加载dotenv之后读取）
USE_LOCAL_MODE = os.getenv('USE_LOCAL_MODE', 'false').lower() == 'true'

# LLM提供商配置（doubao 或 ollama）
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama').lower()

# 配置
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')
OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'EntropyYue/jina-embeddings-v2-base-zh')
MILVUS_HOST = os.getenv('MILVUS_HOST', 'localhost')
MILVUS_PORT = os.getenv('MILVUS_PORT', '19530')
COLLECTION_NAME = os.getenv('MILVUS_COLLECTION', 'knowledge_base')

# 本地模式特定配置
LOCAL_MILVUS_FILE = os.getenv('LOCAL_MILVUS_FILE', './local_milvus.db')
LOCAL_EMBED_MODEL = os.getenv('LOCAL_EMBED_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')

# 豆包API配置
DOUBAO_API_KEY = os.getenv('DOUBAO_API_KEY', '58a51ac5-3b75-4c5e-85ac-1fb4ef652bd0')
DOUBAO_API_URL = os.getenv('DOUBAO_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
DOUBAO_MODEL = os.getenv('DOUBAO_MODEL', 'doubao-seed-1-8-251228')

# 全局连接状态和本地embedding模型
_milvus_connected = False
_local_embed_model = None


def connect_milvus():
    """连接Milvus向量数据库"""
    global _milvus_connected
    if _milvus_connected:
        return True

    if USE_LOCAL_MODE:
        # 本地模式：使用 Milvus Lite
        try:
            client = MilvusClient(LOCAL_MILVUS_FILE)
            # Milvus Lite 通过 client 操作，不需要单独 connect
            _milvus_connected = True
            _milvus_client = client
            print(f"[RAG] 本地模式：已连接 Milvus Lite，文件: {LOCAL_MILVUS_FILE}")
            return True
        except Exception as e:
            print(f"[RAG] Milvus Lite 连接失败: {e}")
            return False
    else:
        # 服务器模式：连接 Docker Milvus
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
    global _milvus_connected, _milvus_client
    if _milvus_connected:
        try:
            if USE_LOCAL_MODE and _milvus_client:
                # Milvus Lite 不需要显式断开
                pass
            else:
                connections.disconnect("default")
            _milvus_connected = False
            _milvus_client = None
        except:
            pass


def call_llm(prompt: str, provider: str = None, timeout: int = 120) -> Optional[str]:
    """
    统一LLM调用函数，支持豆包API和Ollama

    Args:
        prompt: 提示词
        provider: LLM提供商（doubao/ollama），None则使用全局配置
        timeout: 超时时间（秒）

    Returns:
        LLM返回的文本，失败返回None
    """
    if provider is None:
        provider = LLM_PROVIDER

    try:
        if provider == 'doubao':
            # 调用豆包API
            response = requests.post(
                DOUBAO_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DOUBAO_API_KEY}"
                },
                json={
                    "model": DOUBAO_MODEL,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=timeout
            )
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                print(f"[RAG] 豆包API调用失败: {response.status_code}")
                return None
        else:
            # 调用Ollama
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_ctx": 4096, "temperature": 0.3}
                },
                timeout=timeout
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                print(f"[RAG] Ollama调用失败: {response.status_code}")
                return None
    except Exception as e:
        print(f"[RAG] LLM调用异常: {e}")
        return None

# Milvus Lite client 全局变量
_milvus_client = None


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


def get_local_embed_model():
    """获取本地embedding模型（延迟加载）"""
    global _local_embed_model
    if _local_embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[RAG] 加载本地embedding模型: {LOCAL_EMBED_MODEL}")
            _local_embed_model = SentenceTransformer(LOCAL_EMBED_MODEL)
            print(f"[RAG] 本地embedding模型加载完成")
        except ImportError:
            print("[RAG] sentence-transformers 未安装，请运行: pip install sentence-transformers")
            return None
        except Exception as e:
            print(f"[RAG] 本地embedding模型加载失败: {e}")
            return None
    return _local_embed_model


def get_embedding(text: str, max_retries: int = 3) -> Optional[List[float]]:
    """生成文本嵌入向量"""
    if USE_LOCAL_MODE:
        # 本地模式：使用 sentence-transformers
        model = get_local_embed_model()
        if model is None:
            return None
        try:
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"[RAG] 本地embedding失败: {e}")
            return None
    else:
        # 服务器模式：使用 Ollama
        import time

        for attempt in range(max_retries):
            try:
                # 尝试新版API (/api/embed)
                response = requests.post(
                    f"{OLLAMA_HOST}/api/embed",
                    json={
                        "model": OLLAMA_EMBED_MODEL,
                        "input": text
                    },
                    timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    embeddings = data.get("embeddings", [])
                    if embeddings and len(embeddings) > 0:
                        emb = embeddings[0]
                        if isinstance(emb, list) and all(isinstance(x, (int, float)) for x in emb):
                            return emb

                # 尝试旧版API (/api/embeddings)
                response = requests.post(
                    f"{OLLAMA_HOST}/api/embeddings",
                    json={
                        "model": OLLAMA_EMBED_MODEL,
                        "prompt": text
                    },
                    timeout=60
                )

                if response.status_code == 200:
                    emb = response.json().get("embedding")
                    if emb and isinstance(emb, list):
                        if isinstance(emb[0], list):
                            flat = []
                            for item in emb:
                                if isinstance(item, list):
                                    flat.extend(item)
                                else:
                                    flat.append(item)
                            return flat
                        elif all(isinstance(x, (int, float)) for x in emb):
                            return emb

                print(f"[RAG] Embedding失败: {response.status_code}, 尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)

            except Exception as e:
                print(f"[RAG] Embedding异常: {e}, 尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)

        print(f"[RAG] Embedding最终失败，文本长度: {len(text)}")
        return None


def get_embedding_dim() -> int:
    """获取embedding维度"""
    # 测试文本获取维度
    test_embedding = get_embedding("测试")
    if test_embedding:
        return len(test_embedding)
    # 默认维度
    return 768


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 100) -> List[Tuple[int, str]]:
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


def delete_all_documents() -> Dict:
    """删除所有文档"""
    try:
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return {"success": True, "message": "集合不存在，无需删除"}

        # 删除整个集合
        utility.drop_collection(COLLECTION_NAME)
        print(f"[RAG] 已删除集合: {COLLECTION_NAME}")

        return {
            "success": True,
            "message": "已删除所有文档"
        }

    except Exception as e:
        print(f"[RAG] 删除所有文档失败: {e}")
        return {"success": False, "message": str(e)}


def ask_question(question: str, top_k: int = 15, min_score: float = 0.45) -> Dict:
    """
    RAG问答：检索相关内容 + LLM生成回答
    返回: {"answer": str, "sources": list, "success": bool}
    min_score: 相似度阈值，低于此值的结果将被过滤（标题匹配除外）
    """
    try:
        # 检索更多内容
        similar_docs = search_similar(question, top_k)

        if not similar_docs:
            return {
                "answer": "知识库中没有找到相关信息。",
                "sources": [],
                "success": True
            }

        # 提取核心关键词（用于标题匹配）
        # 常见无关词过滤
        stop_words = ["职能", "中心", "服务中心", "运城市", "哪个", "部门", "管理", "负责", "是什么", "有哪些", "职责", "工作", "的", "是", "归", "属于"]
        keywords_text = question
        for w in stop_words:
            keywords_text = keywords_text.replace(w, "")

        # 生成多个关键词候选：原词、前2字、前4字等
        keywords = []
        if keywords_text.strip():
            text = keywords_text.strip()
            # 尝试多种长度匹配
            if len(text) >= 2:
                keywords.append(text[:2])  # 前2字，如"供热"
            if len(text) >= 4:
                keywords.append(text[:4])  # 前4字
            keywords.append(text)  # 完整词

        # 分两组：标题匹配的 + 相似度高的
        title_matched = []
        score_matched = []
        for doc in similar_docs:
            source = doc.get("source", "")
            score = doc.get("score", 0)

            # 标题包含任一关键词，强制包含（最多3个）
            matched = False
            for kw in keywords:
                if kw and kw in source:
                    matched = True
                    break
            if matched and len(title_matched) < 3:
                title_matched.append(doc)
            # 相似度达标
            elif score >= min_score:
                score_matched.append(doc)

        # 合并结果，标题匹配优先，总共最多3个
        filtered_docs = title_matched[:2] + score_matched[:3-len(title_matched)]

        if not filtered_docs:
            return {
                "answer": "知识库中没有找到足够相关的信息。",
                "sources": [],
                "success": True
            }

        # 构建上下文，标注来源和相似度（截断过长内容）
        context_parts = []
        sources = []
        for i, doc in enumerate(filtered_docs, 1):
            score = doc.get("score", 0)
            source = doc.get("source", "未知")
            content = doc.get("content", "")
            # 截断过长内容，保留前500字
            if len(content) > 500:
                content = content[:500] + "..."
            # 标注是否标题匹配
            matched_kw = [kw for kw in keywords if kw and kw in source]
            match_tag = "【标题匹配:" + ",".join(matched_kw) + "】" if matched_kw else ""
            context_parts.append(f"[资料{i}] {match_tag}来源: {source} (相似度: {score:.2f})\n内容: {content}")
            if source not in sources:
                sources.append(source)

        context = "\n\n---\n\n".join(context_parts)

        # 调用LLM生成回答
        prompt = f"""你是运城市城市管理局的政策专家。请根据以下参考资料回答问题。

回答要求（必须严格遵守）：
1. **只能使用参考资料中的信息回答**，不要添加参考资料中没有的内容
2. 如果参考资料中有明确答案，直接给出，并注明来源
3. 如果涉及部门归属，说明负责部门和依据（必须来自参考资料）
4. 如果参考资料中没有相关内容，明确说明"根据现有知识库，未找到相关信息，建议咨询相关部门"
5. **禁止根据常识或推测补充知识库中没有的内容**
6. 回答要简洁准确，有理有据

参考资料：
{context}

问题：{question}

请回答："""

        # 调用LLM生成回答
        answer = call_llm(prompt, timeout=120)
        if answer:
            return {
                "answer": answer,
                "sources": sources,
                "success": True
            }
        else:
            return {
                "answer": "LLM调用失败，请稍后重试",
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

        if USE_LOCAL_MODE:
            # Milvus Lite 模式
            client = MilvusClient(LOCAL_MILVUS_FILE)
            collections = client.list_collections()
            if COLLECTION_NAME in collections:
                # 获取统计信息
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
            # 服务器模式
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


# 初始化时测试连接
def init_rag():
    """初始化RAG模块"""
    print("[RAG] 初始化...")

    if USE_LOCAL_MODE:
        # 本地模式
        print("[RAG] 本地模式：使用 Milvus Lite + sentence-transformers + 豆包API")

        # 测试本地embedding模型
        model = get_local_embed_model()
        if model:
            print("[RAG] 本地embedding模型加载成功")

        # 测试Milvus Lite
        if connect_milvus():
            print("[RAG] Milvus Lite连接成功")
    else:
        # 服务器模式
        print("[RAG] 服务器模式：使用 Docker Milvus + Ollama")

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