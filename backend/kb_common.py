"""
知识库共享模块
抽取 rag.py 和 case_standards.py 的公共函数，统一维护
"""

import os
import logging
import requests
from typing import List, Optional
from dotenv import load_dotenv

logger = logging.getLogger("kb_common")

# 加载环境变量：
#   1) 先加载 backend/.env（本地开发 base 配置，含 LLM_PROVIDER=doubao 等）；
#      不覆盖进程已有环境变量，故服务器若用 shell 注入 LLM_PROVIDER=ollama 不受影响。
#   2) 再用 backend/.env.local 覆盖（本地/服务器差异配置最高优先级）。
# 之前只加载 .env.local 导致本地 .env 里的 LLM_PROVIDER 等配置完全不生效，
# 使本地测试默认走 ollama(localhost:11434) 而失败。
_HERE = os.path.dirname(os.path.abspath(__file__))
_base = os.path.join(_HERE, '.env')
if os.path.exists(_base):
    load_dotenv(_base)
_local = os.path.join(_HERE, '.env.local')
if os.path.exists(_local):
    load_dotenv(_local, override=True)

USE_LOCAL_MODE = os.getenv('USE_LOCAL_MODE', 'false').lower() == 'true'
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama').lower()

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')
OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'EntropyYue/jina-embeddings-v2-base-zh')
MILVUS_HOST = os.getenv('MILVUS_HOST', 'localhost')
MILVUS_PORT = os.getenv('MILVUS_PORT', '19530')

LOCAL_MILVUS_FILE = os.getenv('LOCAL_MILVUS_FILE', './local_milvus.db')
LOCAL_EMBED_MODEL = os.getenv('LOCAL_EMBED_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')

DOUBAO_API_KEY = os.getenv('DOUBAO_API_KEY', '58a51ac5-3b75-4c5e-85ac-1fb4ef652bd0')
DOUBAO_API_URL = os.getenv('DOUBAO_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
DOUBAO_MODEL = os.getenv('DOUBAO_MODEL', 'doubao-seed-1-8-251228')

# 评分权重（可通过环境变量覆盖）
SCORE_WEIGHT_CORE = float(os.getenv('SCORE_WEIGHT_CORE', '0.45'))
SCORE_WEIGHT_KEYWORD = float(os.getenv('SCORE_WEIGHT_KEYWORD', '0.25'))
SCORE_WEIGHT_VECTOR = float(os.getenv('SCORE_WEIGHT_VECTOR', '0.20'))
SCORE_WEIGHT_FIELD = float(os.getenv('SCORE_WEIGHT_FIELD', '0.10'))

_milvus_connected = False
_milvus_client = None
_local_embed_model = None


def connect_milvus():
    """连接 Milvus 向量数据库"""
    global _milvus_connected, _milvus_client
    if _milvus_connected:
        return True

    if USE_LOCAL_MODE:
        try:
            from pymilvus import MilvusClient
            _milvus_client = MilvusClient(LOCAL_MILVUS_FILE)
            _milvus_connected = True
            print(f"[KB] 本地模式：已连接 Milvus Lite，文件: {LOCAL_MILVUS_FILE}")
            return True
        except Exception as e:
            print(f"[KB] Milvus Lite 连接失败: {e}")
            return False
    else:
        try:
            from pymilvus import connections
            connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
            _milvus_connected = True
            print(f"[KB] 已连接 Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
            return True
        except Exception as e:
            print(f"[KB] Milvus 连接失败: {e}")
            return False


def disconnect_milvus():
    """断开 Milvus 连接"""
    global _milvus_connected, _milvus_client
    if _milvus_connected:
        try:
            if USE_LOCAL_MODE and _milvus_client:
                pass
            else:
                from pymilvus import connections
                connections.disconnect("default")
            _milvus_connected = False
            _milvus_client = None
        except:
            pass


def get_local_embed_model():
    """获取本地 embedding 模型（延迟加载）"""
    global _local_embed_model
    if _local_embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[KB] 加载本地 embedding 模型: {LOCAL_EMBED_MODEL}")
            try:
                # 优先离线加载：仅用本地缓存，避免运行期联网校验 HuggingFace
                # 导致首问卡顿 / 超时（尤其在出网受限的环境）。
                _local_embed_model = SentenceTransformer(LOCAL_EMBED_MODEL, local_files_only=True)
            except (OSError, FileNotFoundError, ValueError):
                # 本地无缓存时退回联网下载（首次灌库场景）。
                logger.warning("[KB] 本地 embedding 缓存未命中，回退联网下载模型")
                _local_embed_model = SentenceTransformer(LOCAL_EMBED_MODEL)
            print(f"[KB] 本地 embedding 模型加载完成")
        except ImportError:
            print("[KB] sentence-transformers 未安装")
            return None
        except Exception as e:
            print(f"[KB] 本地 embedding 模型加载失败: {e}")
            return None
    return _local_embed_model


def get_embedding(text: str, max_retries: int = 3, max_chars: int = 1500) -> Optional[List[float]]:
    """生成文本嵌入向量，max_chars 截断过长文本"""
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]

    use_local = os.getenv('USE_LOCAL_MODE', 'false').lower() == 'true'

    if use_local:
        model = get_local_embed_model()
        if model is None:
            return None
        try:
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"[KB] 本地 embedding 失败: {e}")
            return None
    else:
        import time
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{OLLAMA_HOST}/api/embed",
                    json={"model": OLLAMA_EMBED_MODEL, "input": text},
                    timeout=60
                )
                if response.status_code == 200:
                    data = response.json()
                    embeddings = data.get("embeddings", [])
                    if embeddings and len(embeddings) > 0:
                        emb = embeddings[0]
                        if isinstance(emb, list) and all(isinstance(x, (int, float)) for x in emb):
                            return emb

                response = requests.post(
                    f"{OLLAMA_HOST}/api/embeddings",
                    json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
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

                print(f"[KB] Embedding 失败: {response.status_code}, 尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)
            except Exception as e:
                print(f"[KB] Embedding 异常: {e}, 尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)

        print(f"[KB] Embedding 最终失败，文本长度: {len(text)}")
        return None


def get_embedding_dim() -> int:
    """获取 embedding 维度"""
    test_embedding = get_embedding("测试")
    if test_embedding:
        return len(test_embedding)
    return 768


def call_llm(prompt: str, provider: str = None, timeout: int = 120) -> Optional[str]:
    """统一 LLM 调用，支持豆包 API 和 Ollama"""
    if provider is None:
        provider = LLM_PROVIDER

    try:
        if provider == 'doubao':
            response = requests.post(
                DOUBAO_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DOUBAO_API_KEY}"
                },
                json={
                    "model": DOUBAO_MODEL,
                    "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
                },
                timeout=timeout
            )
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                print(f"[KB] 豆包 API 调用失败: {response.status_code}")
                return None
        else:
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
                print(f"[KB] Ollama 调用失败: {response.status_code}")
                return None
    except Exception as e:
        print(f"[KB] LLM 调用异常: {e}")
        return None
