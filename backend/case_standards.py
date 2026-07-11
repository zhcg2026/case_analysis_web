"""
立结案标准父子索引模块
- 子文档：按立案条件切片，用于精准检索
- 父文档：完整标准内容，用于LLM生成回答

本地调试模式（USE_LOCAL_MODE=true）：
- ChromaDB（嵌入式向量数据库）
- sentence-transformers 本地embedding
- LLM使用豆包API

服务器模式（USE_LOCAL_MODE=false或不设置）：
- Docker Milvus
- Ollama jina-embeddings-v2-base-zh + Qwen2.5-7B
"""

import os
import re
import json
import math
import hashlib
import requests
from typing import List, Dict, Optional, Tuple, Any
from dotenv import load_dotenv

# 加载环境变量（优先加载 .env.local）
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
elif os.path.exists('../.env.local'):
    load_dotenv('../.env.local')

# 设置离线模式，防止模型尝试联网下载
os.environ['HF_DATASETS_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

# 本地模式配置（在加载dotenv之后读取）
USE_LOCAL_MODE = os.getenv('USE_LOCAL_MODE', 'false').lower() == 'true'

# LLM提供商配置（doubao 或 ollama）
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama').lower()

# 服务器模式配置
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'EntropyYue/jina-embeddings-v2-base-zh')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')
MILVUS_HOST = os.getenv('MILVUS_HOST', 'localhost')
MILVUS_PORT = os.getenv('MILVUS_PORT', '19530')

# 本地模式特定配置
LOCAL_DB_PATH = os.getenv('LOCAL_DB_PATH', './chroma_db')
LOCAL_EMBED_MODEL = os.getenv('LOCAL_EMBED_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')

# 豆包API配置
DOUBAO_API_KEY = os.getenv('DOUBAO_API_KEY', '58a51ac5-3b75-4c5e-85ac-1fb4ef652bd0')
DOUBAO_API_URL = os.getenv('DOUBAO_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
DOUBAO_MODEL = os.getenv('DOUBAO_MODEL', 'doubao-seed-1-8-251228')

CASE_STANDARDS_COLLECTION = 'case_standards'
PARENT_COLLECTION = 'case_standards_parents'
CHILD_COLLECTION = 'case_standards_children'

# 全局连接状态
_chroma_client = None
_milvus_connected = False
_local_embed_model = None


def get_chroma_client():
    """获取 ChromaDB 客户端（本地模式）"""
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            _chroma_client = chromadb.PersistentClient(path=LOCAL_DB_PATH)
            print(f"[CaseStandards] ChromaDB 已连接，路径: {LOCAL_DB_PATH}")
        except Exception as e:
            print(f"[CaseStandards] ChromaDB 连接失败: {e}")
            return None
    return _chroma_client


def connect_milvus():
    """连接 Milvus 向量数据库（服务器模式）"""
    global _milvus_connected
    if _milvus_connected:
        return True

    try:
        from pymilvus import connections
        connections.connect(
            alias="default",
            host=MILVUS_HOST,
            port=MILVUS_PORT
        )
        _milvus_connected = True
        print(f"[CaseStandards] 已连接 Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
        return True
    except Exception as e:
        print(f"[CaseStandards] Milvus 连接失败: {e}")
        return False


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
                print(f"[CaseStandards] 豆包API调用失败: {response.status_code} {response.text[:200]}")
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
                print(f"[CaseStandards] Ollama调用失败: {response.status_code}")
                return None
    except Exception as e:
        print(f"[CaseStandards] LLM调用异常: {e}")
        return None


def get_local_embed_model():
    """获取本地embedding模型（延迟加载）"""
    global _local_embed_model
    if _local_embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[CaseStandards] 加载本地embedding模型: {LOCAL_EMBED_MODEL}")
            _local_embed_model = SentenceTransformer(LOCAL_EMBED_MODEL)
            print(f"[CaseStandards] 本地embedding模型加载完成")
        except ImportError:
            print("[CaseStandards] sentence-transformers 未安装，请运行: pip install sentence-transformers")
            return None
        except Exception as e:
            print(f"[CaseStandards] 本地embedding模型加载失败: {e}")
            return None
    return _local_embed_model


def get_embedding(text: str, max_retries: int = 3) -> Optional[List[float]]:
    """生成文本嵌入向量"""
    # 截断过长文本，避免超出 embedding 模型上下文长度限制
    MAX_EMBED_CHARS = 1500
    if len(text) > MAX_EMBED_CHARS:
        text = text[:MAX_EMBED_CHARS]

    # 动态检查本地模式（而不是使用模块级别的USE_LOCAL_MODE）
    use_local = os.getenv('USE_LOCAL_MODE', 'false').lower() == 'true'

    if use_local:
        # 本地模式：使用 sentence-transformers
        model = get_local_embed_model()
        if model is None:
            print("[CaseStandards] 本地embedding模型为None")
            return None
        try:
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"[CaseStandards] 本地embedding失败: {e}")
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

                print(f"[CaseStandards] Embedding失败: {response.status_code}, 尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)

            except Exception as e:
                print(f"[CaseStandards] Embedding异常: {e}, 尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)

        print(f"[CaseStandards] Embedding最终失败，文本长度: {len(text)}")
        return None


def get_embedding_dim() -> int:
    """获取embedding维度"""
    test_embedding = get_embedding("测试")
    if test_embedding:
        return len(test_embedding)
    return 384  # 默认维度（paraphrase-multilingual-MiniLM-L12-v2）


def parse_standard_file(file_path: str) -> Dict:
    """
    解析立结案标准txt文件
    返回结构化的标准数据
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 从文件名提取大类和小类
    filename = os.path.basename(file_path).replace('.txt', '')
    parts = filename.split('_')
    big_category = parts[0] if len(parts) > 0 else ''
    small_category = parts[1] if len(parts) > 1 else ''

    result = {
        'filename': filename,
        'big_category': big_category,
        'small_category': small_category,
        'case_type': '',
        'conditions': [],  # 立案条件列表
        'supervision_subject': '',  # 监管主体
        'responsibility_subject': '',  # 责任主体
        'legal_basis': '',  # 法律依据
        'collection_requirement': '',  # 采集要求
        'raw_content': content  # 原始内容
    }

    # 提取案件类型
    case_type_match = re.search(r'【案件类型】(.+?)(?=\n【|$)', content, re.DOTALL)
    if case_type_match:
        result['case_type'] = case_type_match.group(1).strip()

    # 提取立案条件（核心切片部分）
    conditions_match = re.search(r'【立案条件】(.+?)(?=\n【|$)', content, re.DOTALL)
    if conditions_match:
        conditions_text = conditions_match.group(1).strip()
        result['conditions'] = parse_conditions(conditions_text)

    # 提取监管主体
    supervision_match = re.search(r'【监管主体】(.+?)(?=\n【|$)', content, re.DOTALL)
    if supervision_match:
        result['supervision_subject'] = supervision_match.group(1).strip()

    # 提取责任主体
    responsibility_match = re.search(r'【责任主体】(.+?)(?=\n【|$)', content, re.DOTALL)
    if responsibility_match:
        result['responsibility_subject'] = responsibility_match.group(1).strip()

    # 提取法律依据
    legal_match = re.search(r'【法律依据】(.+?)(?=\n【|$)', content, re.DOTALL)
    if legal_match:
        result['legal_basis'] = legal_match.group(1).strip()

    # 提取采集要求
    collection_match = re.search(r'【采集要求】(.+?)(?=\n【|$)', content, re.DOTALL)
    if collection_match:
        result['collection_requirement'] = collection_match.group(1).strip()

    return result


def parse_conditions(conditions_text: str) -> List[Dict]:
    """
    解析立案条件文本，提取每个条件
    返回: [{index, description, time_limit, close_condition}, ...]
    """
    conditions = []

    # 按条件编号分割（如 "1:", "2:", "3:" 等）
    pattern = r'(\d+):\s*(.+?)(?=\n\d+:|\n处置时限:|$)'
    matches = re.findall(pattern, conditions_text, re.DOTALL)

    for match in matches:
        index = int(match[0])
        description = match[1].strip()

        # 查找处置时限和结案条件
        time_limit = ''
        close_condition = ''

        remaining_text = conditions_text[conditions_text.find(f"{index}:"):]
        time_match = re.search(r'处置时限:\s*(.+?)(?=\n结案条件:|$)', remaining_text)
        if time_match:
            time_limit = time_match.group(1).strip()

        close_match = re.search(r'结案条件:\s*(.+?)(?=\n\d+:|$)', remaining_text)
        if close_match:
            close_condition = close_match.group(1).strip()

        conditions.append({
            'index': index,
            'description': description,
            'time_limit': time_limit,
            'close_condition': close_condition
        })

    # 如果没有匹配到编号格式，尝试其他格式
    if not conditions:
        lines = conditions_text.strip().split('\n')
        current_condition = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if re.match(r'^\d+:', line):
                if current_condition:
                    conditions.append(current_condition)
                desc = re.sub(r'^\d+:\s*', '', line)
                current_condition = {
                    'index': len(conditions) + 1,
                    'description': desc,
                    'time_limit': '',
                    'close_condition': ''
                }
            elif line.startswith('处置时限:'):
                if current_condition:
                    current_condition['time_limit'] = line.replace('处置时限:', '').strip()
            elif line.startswith('结案条件:'):
                if current_condition:
                    current_condition['close_condition'] = line.replace('结案条件:', '').strip()

        if current_condition:
            conditions.append(current_condition)

    return conditions


def generate_doc_id(text: str) -> str:
    """生成文档ID（基于内容哈希）"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]


def build_child_chunk_text(condition: Dict, case_type: str) -> str:
    """
    构建子文档文本内容
    格式：案件类型 + 条件描述 + 处置时限 + 结案条件
    """
    parts = [case_type]

    if condition.get('description'):
        parts.append(condition['description'])

    if condition.get('time_limit'):
        parts.append(f"处置时限: {condition['time_limit']}")

    if condition.get('close_condition'):
        parts.append(f"结案条件: {condition['close_condition']}")

    return '，'.join(parts)


def index_standard_file_chroma(file_path: str) -> Dict:
    """
    索引单个立结案标准文件（ChromaDB 本地模式）
    返回: {"success": bool, "parent_id": str, "children": int, "message": str}
    """
    try:
        client = get_chroma_client()
        if client is None:
            return {"success": False, "parent_id": None, "children": 0, "message": "ChromaDB连接失败"}

        # 解析文件
        parsed = parse_standard_file(file_path)

        if not parsed['conditions']:
            return {
                "success": False,
                "parent_id": None,
                "children": 0,
                "message": f"未找到立案条件: {parsed['filename']}"
            }

        # 生成父文档ID
        parent_id = generate_doc_id(parsed['filename'])

        # 获取或创建集合
        parent_coll = client.get_or_create_collection(
            name=PARENT_COLLECTION,
            metadata={"description": "立结案标准父文档"}
        )
        child_coll = client.get_or_create_collection(
            name=CHILD_COLLECTION,
            metadata={"description": "立结案标准子文档"}
        )

        # 准备父文档
        parent_text = parsed['raw_content']
        parent_meta = {
            'big_category': parsed['big_category'],
            'small_category': parsed['small_category'],
            'case_type': parsed['case_type'],
            'supervision_subject': parsed['supervision_subject'],
            'responsibility_subject': parsed['responsibility_subject'],
            'condition_count': len(parsed['conditions']),
            'filename': parsed['filename']
        }

        # 准备子文档列表
        child_docs = []
        for condition in parsed['conditions']:
            child_id = f"{parent_id}_c{condition['index']}"
            child_text = build_child_chunk_text(condition, parsed['case_type'])
            child_meta = {
                'condition_index': condition['index'],
                'time_limit': condition['time_limit'],
                'close_condition': condition['close_condition'],
                'case_type': parsed['case_type'],
                'parent_id': parent_id
            }
            child_docs.append({
                'id': child_id,
                'text': child_text,
                'meta': child_meta
            })

        print(f"[CaseStandards] 处理文件: {parsed['filename']}, 父文档1个, 子文档{len(child_docs)}个")

        # 父文档embedding
        parent_embedding = get_embedding(parent_text)
        if not parent_embedding:
            return {
                "success": False,
                "parent_id": parent_id,
                "children": 0,
                "message": "父文档embedding生成失败"
            }

        # 先删除可能存在的旧数据
        try:
            parent_coll.delete(ids=[parent_id])
            child_coll.delete(ids=[c['id'] for c in child_docs])
        except:
            pass

        # 插入父文档
        parent_coll.add(
            ids=[parent_id],
            embeddings=[parent_embedding],
            documents=[parent_text],
            metadatas=[parent_meta]
        )

        # 子文档embedding
        child_embeddings = []
        child_ids = []
        child_texts = []
        child_metas = []

        for child in child_docs:
            emb = get_embedding(child['text'])
            if emb:
                child_embeddings.append(emb)
                child_ids.append(child['id'])
                child_texts.append(child['text'])
                child_metas.append(child['meta'])
            else:
                print(f"[CaseStandards] 警告: 子文档embedding失败 - {child['id']}")

        if child_embeddings:
            child_coll.add(
                ids=child_ids,
                embeddings=child_embeddings,
                documents=child_texts,
                metadatas=child_metas
            )

        return {
            "success": True,
            "parent_id": parent_id,
            "children": len(child_embeddings),
            "message": f"成功索引: {parsed['case_type']}, {len(child_embeddings)}个子文档"
        }

    except Exception as e:
        print(f"[CaseStandards] 索引失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "parent_id": None,
            "children": 0,
            "message": str(e)
        }


def index_standard_file_milvus(file_path: str) -> Dict:
    """
    索引单个立结案标准文件（Milvus 服务器模式）
    """
    try:
        from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility

        if not connect_milvus():
            return {"success": False, "parent_id": None, "children": 0, "message": "Milvus连接失败"}

        # 解析文件
        parsed = parse_standard_file(file_path)

        if not parsed['conditions']:
            return {
                "success": False,
                "parent_id": None,
                "children": 0,
                "message": f"未找到立案条件: {parsed['filename']}"
            }

        # 获取embedding维度
        embed_dim = get_embedding_dim()

        # 创建集合（如果不存在）
        if not utility.has_collection(CASE_STANDARDS_COLLECTION):
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
                FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="level", dtype=DataType.INT64),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embed_dim),
                FieldSchema(name="text_content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="case_type", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="meta_info", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields, description="立结案标准父子索引集合")
            collection = Collection(CASE_STANDARDS_COLLECTION, schema)
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            collection.create_index("embedding", index_params)
        else:
            collection = Collection(CASE_STANDARDS_COLLECTION)

        # 生成父文档ID
        parent_id = generate_doc_id(parsed['filename'])

        # 准备文档
        parent_text = parsed['raw_content']
        parent_meta = {
            'filename': parsed['filename'],
            'big_category': parsed['big_category'],
            'small_category': parsed['small_category'],
            'case_type': parsed['case_type'],
            'condition_count': len(parsed['conditions'])
        }

        child_docs = []
        for condition in parsed['conditions']:
            child_id = f"{parent_id}_c{condition['index']}"
            child_text = build_child_chunk_text(condition, parsed['case_type'])
            child_meta = {
                'condition_index': condition['index'],
                'time_limit': condition['time_limit'],
                'parent_id': parent_id
            }
            child_docs.append({
                'id': child_id,
                'text': child_text,
                'meta': child_meta
            })

        # 生成embeddings
        parent_embedding = get_embedding(parent_text)
        if not parent_embedding:
            return {"success": False, "parent_id": parent_id, "children": 0, "message": "父文档embedding失败"}

        child_embeddings = [get_embedding(c['text']) for c in child_docs]

        # 插入数据
        collection.insert([
            [parent_id],
            [parent_id],
            [1],
            [parent_embedding],
            [parent_text],
            [parsed['case_type']],
            [parent_meta]
        ])

        if child_embeddings:
            valid_children = [(c, e) for c, e in zip(child_docs, child_embeddings) if e]
            if valid_children:
                collection.insert([
                    [c['id'] for c, e in valid_children],
                    [parent_id] * len(valid_children),
                    [0] * len(valid_children),
                    [e for c, e in valid_children],
                    [c['text'] for c, e in valid_children],
                    [parsed['case_type']] * len(valid_children),
                    [c['meta'] for c, e in valid_children]
                ])

        collection.flush()

        return {
            "success": True,
            "parent_id": parent_id,
            "children": len([e for e in child_embeddings if e]),
            "message": f"成功索引: {parsed['case_type']}"
        }

    except Exception as e:
        print(f"[CaseStandards] 索引失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "parent_id": None, "children": 0, "message": str(e)}


def index_standard_file(file_path: str) -> Dict:
    """索引单个立结案标准文件（统一使用 Milvus）"""
    return index_standard_file_milvus(file_path)


def index_all_standards(directory: str) -> Dict:
    """
    索引目录下所有立结案标准文件
    返回: {"success": int, "failed": int, "total_children": int, "details": list}
    """
    results = {
        "success": 0,
        "failed": 0,
        "total_children": 0,
        "details": []
    }

    if not os.path.isdir(directory):
        results["details"].append(f"目录不存在: {directory}")
        return results

    # 获取所有txt文件
    txt_files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    print(f"[CaseStandards] 发现 {len(txt_files)} 个标准文件")

    for i, filename in enumerate(txt_files, 1):
        file_path = os.path.join(directory, filename)
        print(f"[CaseStandards] [{i}/{len(txt_files)}] 处理: {filename}")

        result = index_standard_file(file_path)

        if result['success']:
            results['success'] += 1
            results['total_children'] += result['children']
        else:
            results['failed'] += 1

        results['details'].append({
            'file': filename,
            'success': result['success'],
            'children': result['children'],
            'message': result['message']
        })

    print(f"[CaseStandards] 索引完成: 成功 {results['success']}, 失败 {results['failed']}, 总子文档 {results['total_children']}")
    return results


INTENT_KEYWORDS = {
    "time_limit": ["处置时限", "时限", "多久", "多长时间", "几小时", "几天", "限时", "完成时间"],
    "close_condition": ["结案条件", "结案", "如何结案", "达到什么算结案"],
    "responsibility_subject": ["责任主体", "谁负责", "哪个单位负责", "责任单位"],
    "supervision_subject": ["监管主体", "谁监管", "哪个部门监管", "监管单位"],
    "collection_requirement": ["采集要求", "采集标准", "采集口径", "如何采集", "取证要求"],
}

ENTITY_SYNONYMS = {
    "井盖": ["井盖", "窨井盖", "上水井盖", "雨水井盖", "污水井盖", "检查井盖"],
    "破损": ["破损", "损坏", "破裂", "破碎", "裂开", "缺损", "坏了"],
    "塌陷": ["塌陷", "塌方", "下陷", "沉降", "凹陷"],
    "垃圾": ["垃圾", "渣土", "建筑垃圾", "装修垃圾", "生活垃圾"],
    "立交桥": ["立交桥", "高架桥", "栈桥", "天桥", "桥梁", "立交"],
    "护栏": ["护栏", "栏杆", "防护栏", "隔离栏"],
    "脏污": ["脏污", "污损", "污染", "污渍", "积尘", "不洁"],
    "路灯": ["路灯", "灯杆", "照明灯", "灯具", "道路照明"],
}

NOISE_WORDS = {
    "请问", "帮我", "咨询", "一下", "一个", "这个", "那个", "相关", "情况", "问题",
    "标准", "规定", "要求", "处理", "处置", "立案", "结案", "查询", "搜索", "是什么", "案件",
    "怎么办", "如何", "怎么", "可以", "是否", "需要", "根据"
}

DISPATCH_INTENT_WORDS = [
    "处置部门", "归哪个部门", "归谁", "谁负责", "哪个单位", "由谁处置", "负责部门"
]

DEPARTMENT_KEYWORDS = {
    # 环卫类关键词：包含"遗撒/抛洒/洒落"，用于覆盖"道路遗撒/路面抛洒"等提问
    "市容环卫中心": ["环卫", "垃圾", "保洁", "清扫", "污物", "脏污", "果皮箱", "清运", "遗撒", "抛洒", "洒落", "不洁", "积存", "积冰", "积雪", "清洁", "粪便", "排泄物", "呕吐物", "动物尸体", "死禽", "死畜"],
    "园林绿化中心": ["园林", "绿化", "树木", "草坪", "花坛", "绿化带", "公园", "行道树", "绿化垃圾"],
    "综合行政执法队": ["执法", "占道", "违建", "商贩", "广告牌", "渣土车", "门头牌匾", "无照经营"],
    "市政公用服务中心": ["市政", "路灯", "灯杆", "道路", "路面", "井盖", "护栏", "交通设施"],
    "排水服务中心": ["排水", "雨水", "污水", "积水", "下水道", "雨污", "管网", "窨井"],
    "节水服务中心": ["节水", "用水", "漏水", "节约用水", "非常规水", "水资源"],
    "供热供气服务中心": ["供热", "供气", "燃气", "热力", "暖气", "管道燃气", "供暖"],
    "建筑资源化服务中心": ["建筑垃圾", "资源化", "装修垃圾", "再生利用", "渣土处置", "消纳场"],
}

# 环卫优先词：当问题中包含这些词时，即使匹配了市政的"道路/路面"，也强制归为环卫
_SANITATION_OVERRIDE = ["不洁", "脏", "污", "积存", "积冰", "积雪", "垃圾", "保洁", "清扫", "遗撒", "抛洒", "洒落", "清洁", "粪便", "排泄物", "呕吐物", "动物尸体", "死禽", "死畜"]

PARK_NAMES = ["人民公园", "航天公园", "禹都公园", "圣惠公园", "体育公园", "天逸公园", "南风广场"]

MAP_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist", "data")
)

DEPARTMENT_GEO_RULES = {
    "市容环卫中心": {
        "ready": True,
        "file": "guanxia.geojson",
        "geometry_mode": "polygon",
        "unit_type": "片区",
    },
    "园林绿化中心": {
        "ready": True,
        "file": "园林片区.geojson",
        "geometry_mode": "polygon",
        "unit_type": "片区",
        # 公园范围图层（你提到“公园的还没画”）：先预留配置位，未就绪时走片区兜底
        "park_ready": False,
        "park_file": None,
    },
    "综合行政执法队": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "分队"},
    "市政公用服务中心": {
        "ready": True,
        "file": "市政管辖道路.geojson",
        "geometry_mode": "line",
        "unit_type": "部门",
        "line_buffer_m": 80.0,
    },
    "排水服务中心": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "部门"},
    "节水服务中心": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "部门"},
    "供热供气服务中心": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "部门"},
    "建筑资源化服务中心": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "部门"},
}

_department_geojson_cache: Dict[str, Dict[str, Any]] = {}


def normalize_cn_text(text: str) -> str:
    """中文归一化：移除空白和常见标点，提升匹配稳定性"""
    if not text:
        return ''
    return re.sub(r'[\s，。；：、,.!?！？()（）【】\[\]{}"\'“”‘’\-—_/\\]+', '', text)


def _is_dispatch_question(question: str) -> bool:
    normalized = normalize_cn_text(question)
    return any(normalize_cn_text(w) in normalized for w in DISPATCH_INTENT_WORDS)


def _classify_department(question: str) -> Optional[str]:
    normalized = normalize_cn_text(question)
    # 对"遗撒/抛洒/洒落"这类典型环卫问题，直接优先归类到环卫中心，
    # 避免"道路/路面"等市政关键词抢占最高分。
    if "遗撒" in normalized or "抛洒" in normalized or "洒落" in normalized:
        return "市容环卫中心"

    best_dept = None
    best_score = 0
    for dept, words in DEPARTMENT_KEYWORDS.items():
        score = sum(1 for w in words if normalize_cn_text(w) in normalized)
        if score > best_score:
            best_score = score
            best_dept = dept

    # 环卫优先覆盖：如果问题包含环卫核心词（如"不洁""积存"），
    # 即使市政的"道路/路面"得分更高，也强制归为环卫
    if best_dept == "市政公用服务中心" and best_score > 0:
        has_sanitation = any(normalize_cn_text(w) in normalized for w in _SANITATION_OVERRIDE)
        if has_sanitation:
            return "市容环卫中心"

    return best_dept if best_score > 0 else None


def pre_analyze_question(question: str) -> Dict[str, Any]:
    """
    预分析市民问题，提取关键信息，辅助LLM分析

    Returns:
        {
            "location_area": str,      # 区域（如"盐湖区"）
            "location_road": str,      # 道路（如"圣惠路"）
            "location_landmark": str,  # 地标（如"明珠快捷酒店门口"）
            "problem_type": str,       # 问题类型（如"损坏""脏污""缺失"）
            "facility": str,           # 涉及设施（如"护栏""井盖""路灯"）
            "department": str,         # 匹配的部门（如"市政公用服务中心"）
            "keywords": list,          # 关键词列表
        }
    """
    result = {
        "location_area": "",
        "location_road": "",
        "location_landmark": "",
        "problem_type": "",
        "facility": "",
        "department": "",
        "keywords": [],
    }

    # 提取区域信息
    area_patterns = [
        r'([\u4e00-\u9fa5]{2,4}区)',  # 盐湖区、临猗县
        r'([\u4e00-\u9fa5]{2,4}县)',
        r'([\u4e00-\u9fa5]{2,4}市)',
    ]
    for pattern in area_patterns:
        match = re.search(pattern, question)
        if match:
            result["location_area"] = match.group(1)
            break

    # 提取道路信息
    road_match = re.search(r'([\u4e00-\u9fa5]{2,8}(?:路|街|巷|道|大道|街道))', question)
    if road_match:
        result["location_road"] = road_match.group(1)

    # 提取地标信息（门口、附近、旁边等）
    landmark_match = re.search(r'([\u4e00-\u9fa5]{2,15}(?:门口|附近|旁边|对面|处|侧))', question)
    if landmark_match:
        result["location_landmark"] = landmark_match.group(1)

    # 提取问题类型
    problem_types = ["损坏", "破损", "缺失", "丢失", "断裂", "弯曲", "变形",
                     "脏污", "不洁", "积存", "垃圾", "污染",
                     "倾斜", "倒塌", "松动", "脱落",
                     "堵塞", "积水", "漏水", "溢水",
                     "噪音", "异味", "扬尘",
                     "坑洼", "不平", "凸起", "凹陷"]
    for pt in problem_types:
        if pt in question:
            result["problem_type"] = pt
            break

    # 提取涉及设施
    facility_keywords = {
        "护栏": ["护栏", "交通护栏", "隔离栏", "围栏"],
        "井盖": ["井盖", "窨井盖", "下水道盖"],
        "路灯": ["路灯", "灯杆", "照明", "灯"],
        "树木": ["树木", "行道树", "树枝", "绿化"],
        "广告牌": ["广告牌", "招牌", "门头牌匾", "户外广告"],
        "垃圾桶": ["垃圾桶", "果皮箱", "垃圾箱"],
        "路面": ["路面", "道路", "地面", "人行道"],
        "排水": ["排水", "下水道", "雨水", "污水", "管网"],
        "健身器材": ["健身器材", "体育设施", "运动器材"],
    }
    for facility, keywords in facility_keywords.items():
        if any(kw in question for kw in keywords):
            result["facility"] = facility
            break

    # 匹配部门
    result["department"] = _classify_department(question) or ""

    # 提取关键词（用于辅助搜索）
    # 移除常见停用词
    stop_words = ["市民", "建议", "反映", "问题", "希望", "予以", "采纳", "及时",
                  "维护", "处理", "解决", "相关", "部门", "单位", "应该", "需要"]
    keywords = question
    for sw in stop_words:
        keywords = keywords.replace(sw, "")
    # 提取2-4字词组
    extracted_kw = []
    for length in [4, 3, 2]:
        for i in range(len(keywords) - length + 1):
            seg = keywords[i:i+length]
            if all('\u4e00' <= c <= '\u9fa5' for c in seg) and seg not in extracted_kw:
                extracted_kw.append(seg)
                if len(extracted_kw) >= 5:
                    break
        if len(extracted_kw) >= 5:
            break
    result["keywords"] = extracted_kw

    return result


def _extract_location_point(location: Any) -> Optional[Tuple[float, float]]:
    if isinstance(location, dict):
        lng = location.get("lng", location.get("lon", location.get("longitude")))
        lat = location.get("lat", location.get("latitude"))
    elif isinstance(location, (list, tuple)) and len(location) >= 2:
        lng, lat = location[0], location[1]
    else:
        return None
    try:
        return float(lng), float(lat)
    except (TypeError, ValueError):
        return None


def _load_department_geojson(file_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not file_name:
        return None
    if file_name in _department_geojson_cache:
        return _department_geojson_cache[file_name]
    file_path = os.path.join(MAP_DATA_DIR, file_name)
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _department_geojson_cache[file_name] = data
            return data
    except Exception as e:
        print(f"[CaseStandards] 读取地图文件失败 {file_name}: {e}")
        return None


def _point_in_ring(lng: float, lat: float, ring: List[List[float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-15) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def _point_in_polygon(lng: float, lat: float, polygon_coords: List[List[List[float]]]) -> bool:
    if not polygon_coords:
        return False
    if not _point_in_ring(lng, lat, polygon_coords[0]):
        return False
    for hole in polygon_coords[1:]:
        if _point_in_ring(lng, lat, hole):
            return False
    return True


def _point_segment_distance_m(lng: float, lat: float, a: List[float], b: List[float]) -> float:
    lon_scale = 111320.0 * math.cos(math.radians(lat))
    lat_scale = 110540.0
    px, py = lng * lon_scale, lat * lat_scale
    ax, ay = a[0] * lon_scale, a[1] * lat_scale
    bx, by = b[0] * lon_scale, b[1] * lat_scale
    abx, aby = bx - ax, by - ay
    ab_len2 = abx * abx + aby * aby
    if ab_len2 <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len2
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * abx
    proj_y = ay + t * aby
    return math.hypot(px - proj_x, py - proj_y)


def _point_near_line_m(lng: float, lat: float, line_coords: List[List[float]], threshold_m: float) -> bool:
    if not line_coords or len(line_coords) < 2:
        return False
    for idx in range(len(line_coords) - 1):
        if _point_segment_distance_m(lng, lat, line_coords[idx], line_coords[idx + 1]) <= threshold_m:
            return True
    return False


def _extract_unit_name(department: str, props: Dict[str, Any]) -> str:
    if department == "市容环卫中心":
        area = props.get("name") or props.get("zone_name")
        if area:
            return f"环卫{str(area).replace('环卫', '').replace('片区', '')}片区"
    if department == "园林绿化中心":
        zone_name = props.get("zone_name") or props.get("name") or props.get("manager_org")
        if zone_name:
            return zone_name
    if department == "综合行政执法队":
        return props.get("zone_name") or props.get("name") or "综合行政执法队"
    if department == "市政公用服务中心":
        return "市政公用服务中心"
    return department


def _is_park_feature(props: Dict[str, Any]) -> bool:
    joined = " ".join([str(props.get(k, "")) for k in ["name", "zone_name", "manager_org", "remark"]])
    return any(p in joined for p in PARK_NAMES) or ("公园" in joined) or ("广场" in joined)


def _question_mentions_park(question: str) -> bool:
    """判断用户是否在问某个公园的责任单位/管辖"""
    normalized = normalize_cn_text(question)
    if not normalized:
        return False
    if "公园" in normalized or "广场" in normalized:
        return True
    return any(normalize_cn_text(p) in normalized for p in PARK_NAMES)


def match_department_dispatch(question: str, location: Any, force_dispatch: bool = False) -> Optional[Dict[str, Any]]:
    if not force_dispatch and not _is_dispatch_question(question):
        return None
    point = _extract_location_point(location)
    if not point:
        # 没有位置信息时，返回通用部门分类结果
        department = _classify_department(question)
        if department:
            return {
                "success": True,
                "department": department,
                "unit": None,
                "in_jurisdiction": False,
                "layer_status": "no_location",
                "answer": f"根据问题描述，该问题可能由{department}负责。如需精确判断管辖区域，请在地图上点选具体位置。",
            }
        return {
            "success": True,
            "department": None,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "missing_location",
            "answer": "请先在地图上定位后再查询处置部门。",
        }

    department = _classify_department(question)
    if not department:
        return {
            "success": True,
            "department": None,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "unknown_department",
            "answer": "未能识别处置部门，请补充更具体的问题描述。",
        }

    rule = DEPARTMENT_GEO_RULES.get(department, {})
    if not rule.get("ready"):
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "not_ready",
            "answer": f"{department}范围数据未完善（暂按人工研判）。",
        }

    # 园林：分“片区”与“公园”两类。公园图层未就绪时，先按片区兜底，并给出提示。
    ask_park = (department == "园林绿化中心") and _question_mentions_park(question)
    geojson_data = None
    using_park_layer = False
    if ask_park and rule.get("park_ready") and rule.get("park_file"):
        geojson_data = _load_department_geojson(rule.get("park_file"))
        using_park_layer = geojson_data is not None
    if geojson_data is None:
        geojson_data = _load_department_geojson(rule.get("file"))

    if not geojson_data:
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "missing_layer_file",
            "answer": f"{department}范围数据文件缺失，暂无法自动判定。",
        }

    lng, lat = point
    polygon_hits = []
    normal_hits = []
    mode = rule.get("geometry_mode", "polygon")
    line_buffer_m = float(rule.get("line_buffer_m", 80.0))

    for feature in geojson_data.get("features", []):
        geometry = feature.get("geometry", {}) or {}
        props = feature.get("properties", {}) or {}
        geo_type = geometry.get("type")
        coords = geometry.get("coordinates", [])
        matched = False

        if mode == "polygon":
            if geo_type == "Polygon":
                matched = _point_in_polygon(lng, lat, coords)
            elif geo_type == "MultiPolygon":
                matched = any(_point_in_polygon(lng, lat, poly) for poly in coords)
        elif mode == "line":
            if geo_type == "LineString":
                matched = _point_near_line_m(lng, lat, coords, line_buffer_m)
            elif geo_type == "MultiLineString":
                matched = any(_point_near_line_m(lng, lat, line, line_buffer_m) for line in coords)

        if matched:
            unit_name = _extract_unit_name(department, props)
            hit = {"unit": unit_name, "properties": props}
            if department == "园林绿化中心" and _is_park_feature(props):
                polygon_hits.append(hit)
            else:
                normal_hits.append(hit)

    selected = None
    if polygon_hits:
        selected = polygon_hits[0]
    elif normal_hits:
        selected = normal_hits[0]

    if not selected:
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "ready",
            "answer": "不属于我局管辖范围",
        }

    unit = selected["unit"]
    # 园林问公园但公园图层未画：用片区结果兜底，并明确提示（避免用户误以为是精确到公园管理方）
    if ask_park and not using_park_layer:
        return {
            "success": True,
            "department": department,
            "unit": unit,
            "in_jurisdiction": True,
            "layer_status": "park_not_ready_fallback_zone",
            "answer": f"{unit}（公园范围图层未完善，当前按园林片区兜底）",
        }

    return {
        "success": True,
        "department": department,
        "unit": unit,
        "in_jurisdiction": True,
        "layer_status": "ready",
        "answer": unit,
    }


def detect_query_intent(query: str) -> Dict[str, Any]:
    """识别用户问题意图与目标字段"""
    normalized = normalize_cn_text(query)
    target_fields = []
    intent_name = "general"

    for field, words in INTENT_KEYWORDS.items():
        if any(normalize_cn_text(w) in normalized for w in words):
            target_fields.append(field)

    if target_fields:
        intent_name = target_fields[0]

    return {
        "intent": intent_name,
        "target_fields": target_fields,
    }


def extract_entities_and_terms(query: str) -> Dict[str, Any]:
    """
    提取实体词并做同义词扩展，返回用于检索重排的关键词集合
    """
    chinese_blocks = re.findall(r'[\u4e00-\u9fa5]+', query)
    terms = set()
    entities = set()
    core_terms = set()

    # 先剥离意图词/噪声词，提取“核心实体短语”
    noise_pool = set(NOISE_WORDS)
    for words in INTENT_KEYWORDS.values():
        noise_pool.update(words)
    cleaned_query = query
    for w in sorted(noise_pool, key=len, reverse=True):
        if w:
            cleaned_query = cleaned_query.replace(w, " ")
    for block in re.findall(r'[\u4e00-\u9fa5]{2,12}', cleaned_query):
        if block and block not in NOISE_WORDS:
            core_terms.add(block)
            # 将长核心词拆分为2-4字的子片段，提升匹配灵活性
            if len(block) > 4:
                for seg_len in [4, 3, 2]:
                    for i in range(0, len(block) - seg_len + 1):
                        seg = block[i:i+seg_len]
                        if seg and seg not in NOISE_WORDS:
                            core_terms.add(seg)

    for block in chinese_blocks:
        text = block.strip()
        if not text:
            continue

        # 先做同义词实体识别
        norm_text = normalize_cn_text(text)
        for canonical, syns in ENTITY_SYNONYMS.items():
            if any(normalize_cn_text(s) in norm_text for s in syns):
                entities.add(canonical)
                terms.update(syns)
                core_terms.add(canonical)

        # 按长度切分，提取潜在关键词
        for win_size in range(2, 7):
            if len(text) < win_size:
                continue
            for i in range(0, len(text) - win_size + 1):
                piece = text[i:i + win_size].strip()
                if not piece or piece in NOISE_WORDS:
                    continue
                terms.add(piece)

        if 2 <= len(text) <= 12 and text not in NOISE_WORDS:
            terms.add(text)

    # 将规范实体也加入检索词，增强稳定召回
    terms.update(entities)

    # 长词优先，便于打分
    sorted_terms = sorted(terms, key=len, reverse=True)
    return {
        "entities": sorted(entities, key=len, reverse=True),
        "terms": sorted_terms,
        "core_terms": sorted(core_terms, key=len, reverse=True)
    }


def build_query_profile(query: str) -> Dict[str, Any]:
    """构建查询画像：意图 + 实体 + 扩展词 + 改写查询"""
    intent_info = detect_query_intent(query)
    term_info = extract_entities_and_terms(query)
    rewritten_query = " ".join([query] + term_info["entities"][:3])
    return {
        "raw_query": query,
        "rewritten_query": rewritten_query.strip(),
        "intent": intent_info["intent"],
        "target_fields": intent_info["target_fields"],
        "entities": term_info["entities"],
        "terms": term_info["terms"],
        "core_terms": term_info["core_terms"],
    }


def compute_keyword_field_score(
    query_profile: Dict[str, Any],
    doc_text: str,
    meta: Dict[str, Any]
) -> Tuple[float, float, float, int, List[str]]:
    """
    计算关键词得分与字段意图得分
    返回: (keyword_score, field_score, reasons)
    """
    reasons = []
    norm_doc = normalize_cn_text(doc_text)
    terms = query_profile.get("terms", [])
    hit_terms = []

    for term in terms:
        norm_term = normalize_cn_text(term)
        if not norm_term:
            continue
        if norm_term in norm_doc:
            hit_terms.append(term)

    query_len = max(1, len(normalize_cn_text(query_profile.get("raw_query", ""))))
    hit_len = sum(len(t) for t in set(hit_terms))
    keyword_score = min(1.0, hit_len / query_len) if hit_terms else 0.0
    if hit_terms:
        reasons.append(f"关键词命中: {','.join(list(dict.fromkeys(hit_terms))[:4])}")

    # 核心词命中：用于强约束结果相关性，避免被“时限”等泛词带偏
    core_terms = query_profile.get("core_terms", [])
    core_hits = []
    for c in core_terms:
        nc = normalize_cn_text(c)
        if nc and nc in norm_doc:
            core_hits.append(c)
    core_total_len = max(1, sum(len(c) for c in core_terms[:6]))
    core_hit_len = sum(len(c) for c in set(core_hits))
    core_score = min(1.0, core_hit_len / core_total_len) if core_terms else 0.0
    if core_hits:
        reasons.append(f"核心词命中: {','.join(list(dict.fromkeys(core_hits))[:4])}")

    # 意图字段加权：用户问时限/结案时，把对应字段命中显著提权
    field_score = 0.0
    target_fields = query_profile.get("target_fields", [])
    if "time_limit" in target_fields and meta.get("time_limit"):
        field_score += 0.35
        reasons.append("匹配处置时限意图")
    if "close_condition" in target_fields and meta.get("close_condition"):
        field_score += 0.35
        reasons.append("匹配结案条件意图")
    if "responsibility_subject" in target_fields:
        if meta.get("responsibility_subject") or "责任主体" in doc_text:
            field_score += 0.25
            reasons.append("匹配责任主体意图")
    if "supervision_subject" in target_fields:
        if meta.get("supervision_subject") or "监管主体" in doc_text:
            field_score += 0.25
            reasons.append("匹配监管主体意图")
    if "collection_requirement" in target_fields:
        if "采集要求" in doc_text:
            field_score += 0.35
            reasons.append("匹配采集要求意图")

    return keyword_score, min(field_score, 0.6), core_score, len(set(core_hits)), reasons


def search_collection_requirement_chroma(
    query_profile: Dict[str, Any],
    parent_coll,
    top_k: int
) -> List[Dict]:
    """
    采集要求专用检索：直接检索父文档，避免子文档(立案条件)漏召回
    """
    parent_docs = parent_coll.get(include=['documents', 'metadatas'])
    results = []
    terms = query_profile.get("terms", [])
    core_terms = [t for t in query_profile.get("core_terms", []) if len(t) >= 2]
    query_len = max(1, len(normalize_cn_text(query_profile.get("raw_query", ""))))

    for i, pid in enumerate(parent_docs.get('ids', [])):
        doc = parent_docs['documents'][i] if parent_docs.get('documents') else ''
        meta = parent_docs['metadatas'][i] if parent_docs.get('metadatas') else {}
        if not doc:
            continue

        norm_doc = normalize_cn_text(doc)
        hit_terms = []
        for t in terms:
            nt = normalize_cn_text(t)
            if nt and nt in norm_doc:
                hit_terms.append(t)

        core_hits = []
        for ct in core_terms:
            nct = normalize_cn_text(ct)
            if nct and nct in norm_doc:
                core_hits.append(ct)

        if not hit_terms and not core_hits:
            continue

        keyword_score = min(1.0, sum(len(t) for t in set(hit_terms)) / query_len) if hit_terms else 0.0
        core_score = min(1.0, sum(len(t) for t in set(core_hits)) / max(1, sum(len(t) for t in core_terms[:6]))) if core_terms else 0.0

        # 采集要求字段存在时加权
        collection_match = re.search(r'【采集要求】(.+?)(?=\n【|$)', doc, re.DOTALL)
        field_score = 0.25 if collection_match and collection_match.group(1).strip() else 0.0

        score = round(min(1.0, core_score * 0.5 + keyword_score * 0.3 + field_score * 0.2), 4)
        case_type = meta.get('case_type', '')
        reasons = []
        if core_hits:
            reasons.append(f"核心词命中: {','.join(list(dict.fromkeys(core_hits))[:4])}")
        if hit_terms:
            reasons.append(f"关键词命中: {','.join(list(dict.fromkeys(hit_terms))[:4])}")
        if field_score > 0:
            reasons.append("匹配采集要求意图")
        case_type_norm = normalize_cn_text(case_type)
        for entity in query_profile.get("entities", []):
            if normalize_cn_text(entity) and normalize_cn_text(entity) in case_type_norm:
                score = min(1.0, score + 0.2)
                reasons.append(f"案件类型命中实体: {entity}")
                break

        results.append({
            "child_id": f"{pid}_parent",
            "parent_id": pid,
            "child_text": f"{case_type} 采集要求检索命中",
            "case_type": case_type,
            "meta_info": meta,
            "parent_text": doc,
            "parent_meta": meta,
            "score": score,
            "keyword_score": keyword_score,
            "core_score": core_score,
            "field_score": field_score,
            "core_hit_count": len(set(core_hits)),
            "match_type": "parent_keyword",
            "match_reasons": reasons
        })

    results.sort(key=lambda x: (x.get("core_hit_count", 0), x.get("score", 0)), reverse=True)
    return results[:top_k]


def search_case_standards_chroma(query: str, top_k: int = 5) -> List[Dict]:
    """搜索立结案标准（ChromaDB 本地模式）- 意图识别 + 混合召回 + 重排"""
    try:
        client = get_chroma_client()
        if client is None:
            return []

        child_coll = client.get_or_create_collection(name=CHILD_COLLECTION)
        parent_coll = client.get_or_create_collection(name=PARENT_COLLECTION)

        query_profile = build_query_profile(query)

        # 采集要求类问题直接走父文档检索，避免子文档缺字段导致漏检
        if query_profile.get("intent") == "collection_requirement":
            return search_collection_requirement_chroma(query_profile, parent_coll, top_k)

        # 获取查询向量（使用改写查询提升语义召回稳定性）
        query_embedding = get_embedding(query_profile["rewritten_query"])
        if not query_embedding:
            return []

        # 1. 向量搜索（获取更多候选）
        vec_results = child_coll.query(
            query_embeddings=[query_embedding],
            n_results=max(top_k * 8, 20)  # 获取更多候选用于重排
        )

        # 2. 关键词召回（全量扫描 child 文档）
        all_docs = child_coll.get(include=['documents', 'metadatas'])
        keyword_candidates = []
        for i, doc in enumerate(all_docs.get('documents', [])):
            meta = all_docs['metadatas'][i] if all_docs.get('metadatas') else {}
            keyword_score, field_score, core_score, core_hit_count, reasons = compute_keyword_field_score(query_profile, doc, meta)
            if keyword_score > 0 or field_score > 0 or core_score > 0:
                keyword_candidates.append({
                    "id": all_docs['ids'][i],
                    "doc": doc,
                    "meta": meta,
                    "keyword_score": keyword_score,
                    "field_score": field_score,
                    "core_score": core_score,
                    "core_hit_count": core_hit_count,
                    "reasons": reasons
                })
        keyword_candidates.sort(
            key=lambda x: (x["core_score"], x["keyword_score"] + x["field_score"], x["keyword_score"]),
            reverse=True
        )

        # 3. 融合召回结果
        candidates = {}
        parent_ids = set()
        for km in keyword_candidates[:max(top_k * 8, 30)]:
            parent_id = km['meta'].get('parent_id', '')
            if parent_id:
                parent_ids.add(parent_id)
            candidates[km['id']] = {
                "child_id": km['id'],
                "parent_id": parent_id,
                "child_text": km['doc'],
                "case_type": km['meta'].get('case_type', ''),
                "meta_info": km['meta'],
                "keyword_score": km["keyword_score"],
                "field_score": km["field_score"],
                "core_score": km["core_score"],
                "core_hit_count": km["core_hit_count"],
                "vector_score": 0.0,
                "match_reasons": km["reasons"],
                "match_type": "keyword"
            }

        if vec_results.get('ids') and vec_results['ids'][0]:
            for i, child_id in enumerate(vec_results['ids'][0]):
                meta = vec_results['metadatas'][0][i] if vec_results.get('metadatas') else {}
                parent_id = meta.get('parent_id', '')
                if parent_id:
                    parent_ids.add(parent_id)
                vector_score = max(0.0, 1.0 - (vec_results['distances'][0][i] / 10.0)) if vec_results.get('distances') else 0.0

                if child_id not in candidates:
                    candidates[child_id] = {
                        "child_id": child_id,
                        "parent_id": parent_id,
                        "child_text": vec_results['documents'][0][i] if vec_results.get('documents') else '',
                        "case_type": meta.get('case_type', ''),
                        "meta_info": meta,
                        "keyword_score": 0.0,
                        "field_score": 0.0,
                        "core_score": 0.0,
                        "core_hit_count": 0,
                        "vector_score": vector_score,
                        "match_reasons": ["向量语义召回"],
                        "match_type": "vector"
                    }
                else:
                    candidates[child_id]["vector_score"] = max(candidates[child_id]["vector_score"], vector_score)
                    if "向量语义召回" not in candidates[child_id]["match_reasons"]:
                        candidates[child_id]["match_reasons"].append("向量语义召回")
                    if candidates[child_id]["match_type"] == "keyword":
                        candidates[child_id]["match_type"] = "hybrid"

        # 4. 重排打分：关键词 + 向量 + 意图字段
        child_results = []
        for _, item in candidates.items():
            final_score = (
                item["core_score"] * 0.45 +
                item["keyword_score"] * 0.25 +
                item["vector_score"] * 0.20 +
                item["field_score"] * 0.10
            )
            item["score"] = round(min(1.0, final_score), 4)
            child_results.append(item)

        # 核心词强约束：
        # 旧逻辑：达不到阈值就直接清空候选，容易在“核心词抽取过长/不完全匹配”时把正确答案误杀。
        # 新逻辑：如果候选里完全没有核心词命中，则不做强约束；如果命中过，但不满足阈值，则放宽到 >=1 命中。
        if query_profile.get("core_terms"):
            non_trivial_core_terms = [t for t in query_profile.get("core_terms", []) if len(t) >= 2]
            required_core_hits = 2 if len(non_trivial_core_terms) >= 3 else 1
            core_matched = [r for r in child_results if r.get("core_hit_count", 0) >= required_core_hits]
            if core_matched:
                child_results = core_matched
            else:
                has_any_core_hit = any(r.get("core_hit_count", 0) > 0 for r in child_results)
                if has_any_core_hit:
                    # 放宽：至少保留命中过一个核心词的结果
                    child_results = [r for r in child_results if r.get("core_hit_count", 0) > 0]
                # else：完全没有核心词命中时，不清空，交给 keyword/vector 排序兜底

        # 意图字段兜底：如果问时限/结案，优先保留有对应字段值的结果
        target_fields = set(query_profile.get("target_fields", []))
        if target_fields:
            def has_target_field(r: Dict[str, Any]) -> int:
                meta = r.get("meta_info", {}) or {}
                if "time_limit" in target_fields and meta.get("time_limit"):
                    return 1
                if "close_condition" in target_fields and meta.get("close_condition"):
                    return 1
                return 0

            child_results.sort(
                key=lambda x: (has_target_field(x), x.get("score", 0), x.get("keyword_score", 0)),
                reverse=True
            )
        else:
            child_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        child_results = child_results[:top_k]

        # 回表查询父文档
        if parent_ids:
            parent_results = parent_coll.get(ids=list(parent_ids))

            parent_map = {}
            for i, pid in enumerate(parent_results['ids']):
                parent_map[pid] = {
                    'text': parent_results['documents'][i] if parent_results['documents'] else '',
                    'meta': parent_results['metadatas'][i] if parent_results['metadatas'] else {}
                }

            for cr in child_results:
                parent_info = parent_map.get(cr['parent_id'], {})
                cr['parent_text'] = parent_info.get('text', '')
                cr['parent_meta'] = parent_info.get('meta', {})
                # 补充从父文档可拿到的字段，便于意图匹配
                if not cr["meta_info"].get("responsibility_subject"):
                    cr["meta_info"]["responsibility_subject"] = cr["parent_meta"].get("responsibility_subject", "")
                if not cr["meta_info"].get("supervision_subject"):
                    cr["meta_info"]["supervision_subject"] = cr["parent_meta"].get("supervision_subject", "")

        return child_results

    except Exception as e:
        print(f"[CaseStandards] 搜索失败: {e}")
        return []


def search_case_standards_milvus(query: str, top_k: int = 5) -> List[Dict]:
    """搜索立结案标准（Milvus 服务器模式），混合搜索+加权重排"""
    try:
        from pymilvus import Collection, utility

        if not connect_milvus():
            return []

        if not utility.has_collection(CASE_STANDARDS_COLLECTION):
            return []

        collection = Collection(CASE_STANDARDS_COLLECTION)
        collection.load()

        # 构建查询画像（复用ChromaDB模式的查询改写）
        query_profile = build_query_profile(query)
        rewritten_query = query_profile["rewritten_query"]
        core_terms = query_profile.get("core_terms", [])
        terms = query_profile.get("terms", [])

        # 用改写后的查询做embedding（包含扩展实体，提升语义匹配）
        query_embedding = get_embedding(rewritten_query)
        if not query_embedding:
            return []

        # 1. 向量搜索：扩大候选集（top_k * 8，至少20个）
        search_limit = max(top_k * 8, 20)
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=search_limit,
            expr="level == 0",
            output_fields=["id", "parent_id", "text_content", "case_type", "meta_info"]
        )

        parent_ids = set()
        child_results = []

        for hits in results:
            for hit in hits:
                parent_id = hit.entity.get("parent_id")
                parent_ids.add(parent_id)
                child_results.append({
                    "child_id": hit.entity.get("id"),
                    "parent_id": parent_id,
                    "child_text": hit.entity.get("text_content"),
                    "case_type": hit.entity.get("case_type"),
                    "meta_info": hit.entity.get("meta_info"),
                    "score": hit.distance,
                    "vector_score": hit.distance
                })

        # 2. 同义词映射：补充关键词召回
        synonym_map = {
            '粪便': ['道路不洁', '暴露生活垃圾', '积存垃圾'],
            '碎玻璃': ['道路不洁', '积存垃圾'],
            '玻璃': ['道路不洁', '积存垃圾'],
            '路面垃圾': ['道路不洁', '暴露生活垃圾', '积存垃圾'],
            '垃圾': ['道路不洁', '暴露生活垃圾', '积存垃圾', '垃圾满溢'],
            '无人清扫': ['道路不洁', '暴露生活垃圾'],
            '动物尸体': ['动物尸体'],
            '死': ['动物尸体'],
            '尸体': ['动物尸体'],
            '噪音': ['施工扰民', '商业噪音'],
            '扰民': ['施工扰民', '商业噪音'],
            '夜间施工': ['施工扰民'],
            '施工噪音': ['施工扰民'],
            '护栏': ['交通护栏', '交通设施'],
            '开口': ['交通护栏', '违章开设道口'],
            '红绿灯': ['交通信号灯'],
            '信号灯': ['交通信号灯'],
            '公交站': ['公交站亭', '公交站牌'],
            '天然气': ['供气管理', '燃气'],
            '燃气': ['供气管理', '燃气管道', '燃气调压', '燃气井盖'],
            '停气': ['供气管理'],
            '供气': ['供气管理'],
            '气费': ['供气管理'],
            '暖气': ['供热管理'],
            '供暖': ['供热管理'],
            '共享单车': ['共享单车管理'],
            '共享电动车': ['共享单车管理'],
            '共享电瓶车': ['共享单车管理'],
            '单车': ['共享单车管理'],
            '乱停放': ['共享单车管理', '占道经营'],
            '停放': ['共享单车管理', '停车管理'],
            '坑洼': ['道路破损', '路面塌陷', '路面不平'],
            '不平': ['道路破损', '路面塌陷'],
            '破损': ['道路破损', '园路破损'],
            '道路破损': ['市容环境 - 道路破损', '施工管理 - 施工工地出入口道路破损'],
            '路面破损': ['市容环境 - 道路破损'],
            '路破损': ['市容环境 - 道路破损'],
            '路不平': ['市容环境 - 道路破损'],
            '路坑洼': ['市容环境 - 道路破损'],
            '路开裂': ['市容环境 - 道路破损'],
            '路面开裂': ['市容环境 - 道路破损'],
            '路面裂': ['市容环境 - 道路破损'],
            '路面坑': ['市容环境 - 道路破损'],
            '路面塌陷': ['市容环境 - 道路破损', '突发事件 - 路面塌陷'],
            '园路破损': ['市容环境 - 园路破损'],
            '道路不洁': ['市容环境 - 道路不洁'],
            '路面不洁': ['市容环境 - 道路不洁'],
            '道路': ['道路破损', '道路不洁'],
            '路面': ['道路破损', '道路不洁'],
            '水管': ['绿地附属设施', '供水管道破裂'],
            '管道': ['绿地附属设施', '供水管道破裂', '排水管道堵塞'],
            '破裂': ['绿地附属设施', '供水管道破裂', '道路破损'],
            '漏水': ['绿地附属设施', '供水管道破裂'],
            '绿化带': ['绿地附属设施', '绿地脏乱'],
            '绿地': ['绿地附属设施', '绿地脏乱'],
            '树木': ['行道树', '护树设施', '古树名木'],
            '行道树': ['行道树', '护树设施'],
            '树': ['行道树', '护树设施', '古树名木'],
            '修剪': ['行道树', '护树设施'],
            '喷泉': ['喷泉'],
            '井盖': ['上水井盖', '污水井盖', '雨水井盖', '路灯井盖', '燃气井盖', '热力井盖', '园林井盖', '化粪池井盖', '不明井盖'],
            '下水道': ['污水井盖', '排水管道堵塞'],
            '下水': ['污水井盖', '排水管道堵塞'],
            '排水': ['污水井盖', '排水管道堵塞', '雨水井盖'],
            '积水': ['排水管道堵塞', '道路积水'],
            '外溢': ['污水井盖', '排水管道堵塞', '雨水井盖'],
            '垃圾桶': ['垃圾箱', '垃圾满溢'],
            '果皮箱': ['垃圾箱', '垃圾满溢'],
            '路灯': ['路灯', '景观灯', '地灯'],
            '灯': ['路灯', '景观灯', '地灯'],
            '工地': ['施工扰民', '施工工地出入口道路破损', '施工工地围挡', '施工占道'],
            '施工': ['施工扰民', '施工占道'],
            '广告': ['户外广告', '违规户外广告', '违规牌匾标识'],
            '招牌': ['违规牌匾标识'],
            '小广告': ['非法小广告'],
            '占道': ['占道经营', '占道促销宣传'],
            '流动摊贩': ['无照经营游商'],
            '游商': ['无照经营游商'],
            '拖欠': ['投诉', '投诉拖欠农民工工资'],
            '工资': ['投诉', '投诉拖欠农民工工资'],
            '评审费': ['投诉', '投诉拖欠农民工工资'],
            '欠薪': ['投诉', '投诉拖欠农民工工资'],
            '农民工': ['投诉', '投诉拖欠农民工工资'],
            '供水': ['供水管道破裂', '供水管理'],
            '污水': ['排水管道堵塞', '污水井盖'],
            '雨水': ['雨水井盖', '排水管道堵塞'],
            '害虫': ['病虫害'],
            '虫子': ['病虫害'],
            '虫害': ['病虫害'],
            '喷洒': ['病虫害'],
        }

        # 关键词兜底：提取查询中的中文片段
        query_keywords = []
        for length in [4, 3, 2]:
            for i in range(len(query) - length + 1):
                segment = query[i:i+length]
                if all('\u4e00' <= c <= '\u9fa5' for c in segment) and segment not in query_keywords:
                    query_keywords.append(segment)
        existing_types = set(cr.get('case_type', '') for cr in child_results)

        # 用同义词映射搜索补充
        if query_keywords:
            for kw in query_keywords:
                if len(kw) < 2:
                    continue
                targets = synonym_map.get(kw, [kw])
                for synonym in targets:
                    try:
                        extra = collection.query(
                            expr=f'level == 1 and case_type like "%{synonym}%"',
                            output_fields=["parent_id", "text_content", "case_type", "meta_info"],
                            limit=5
                        )
                        for er in extra:
                            ct = er.get('case_type', '')
                            if ct not in existing_types:
                                existing_types.add(ct)
                                parent_text_content = er.get('text_content', '')
                                child_results.append({
                                    "child_id": er.get('parent_id'),
                                    "parent_id": er.get('parent_id'),
                                    "child_text": parent_text_content,
                                    "parent_text": parent_text_content,
                                    "case_type": ct,
                                    "meta_info": er.get('meta_info'),
                                    "score": 0.6,
                                    "vector_score": 0.0
                                })
                                parent_ids.add(er.get('parent_id'))
                    except Exception:
                        pass

        # 3. 计算关键词+核心词+意图字段得分（复用ChromaDB模式的评分函数）
        # 提取查询中的核心实体用于类型匹配
        query_entities = []
        for kw in query_keywords:
            if len(kw) >= 2 and kw in synonym_map:
                query_entities.append(kw)
        if not query_entities:
            query_entities = [kw for kw in query_keywords if len(kw) >= 2]

        for cr in child_results:
            doc_text = cr.get('child_text', '') + ' ' + cr.get('case_type', '')
            meta_str = cr.get('meta_info', '')
            # 尝试解析meta_info为dict
            meta = {}
            if meta_str:
                try:
                    import json
                    meta = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
                except Exception:
                    pass

            keyword_score, field_score, core_score, core_hit_count, reasons = compute_keyword_field_score(
                query_profile, doc_text, meta
            )
            cr['keyword_score'] = keyword_score
            cr['field_score'] = field_score
            cr['core_score'] = core_score
            cr['core_hit_count'] = core_hit_count

        # 4. 加权重排序
        for cr in child_results:
            # 实体类型匹配加成：case_type包含查询核心实体时加分
            entity_boost = 0.0
            ct = cr.get('case_type', '')
            for ent in query_entities:
                if ent in ct:
                    entity_boost = 0.15
                    break

            cr['final_score'] = (
                cr.get('core_score', 0) * 0.45 +
                cr.get('keyword_score', 0) * 0.25 +
                cr.get('vector_score', 0) * 0.20 +
                cr.get('field_score', 0) * 0.10 +
                entity_boost
            )

        child_results.sort(key=lambda x: x.get('final_score', 0), reverse=True)

        # 5. 核心词强约束：如果有核心词命中，排除完全没命中的结果
        if core_terms:
            non_trivial_core = [t for t in core_terms if len(t) >= 2]
            any_core_hit = any(cr.get('core_hit_count', 0) > 0 for cr in child_results)
            if any_core_hit:
                required_hits = 2 if len(non_trivial_core) >= 3 else 1
                filtered = [cr for cr in child_results if cr.get('core_hit_count', 0) >= required_hits]
                if filtered:
                    child_results = filtered

        # 6. 截断到top_k
        child_results = child_results[:top_k]

        # 7. 回表查询父文档
        if parent_ids:
            quoted_ids = [f'"{pid}"' for pid in parent_ids]
            parent_results = collection.query(
                expr=f'level == 1 and parent_id in [{",".join(quoted_ids)}]',
                output_fields=["parent_id", "text_content", "meta_info"],
                limit=len(parent_ids) + 10
            )
            parent_map = {}
            for pr in parent_results:
                parent_map[pr['parent_id']] = {
                    'text': pr['text_content'],
                    'meta': pr['meta_info']
                }
            for cr in child_results:
                parent_info = parent_map.get(cr['parent_id'], {})
                # 只在 parent_text 为空时才从回表结果填充
                if not cr.get('parent_text'):
                    cr['parent_text'] = parent_info.get('text', '')
                cr['parent_meta'] = parent_info.get('meta', '') or cr.get('parent_meta', '')

        return child_results

    except Exception as e:
        print(f"[CaseStandards] 搜索失败: {e}")
        return []


def search_case_standards(query: str, top_k: int = 5) -> List[Dict]:
    """搜索立结案标准（统一使用 Milvus）"""
    return search_case_standards_milvus(query, top_k)


def build_structured_intent_answer(question: str, results: List[Dict]) -> Optional[str]:
    """
    对强意图问题直接结构化回答，减少LLM误判“未找到”
    """
    if not results:
        return None

    profile = build_query_profile(question)
    intent = profile.get("intent")
    top = results[0]
    case_type = top.get("case_type", "未识别案件类型")
    meta = top.get("meta_info", {}) or {}

    if intent == "time_limit":
        time_limit = meta.get("time_limit", "")
        close_condition = meta.get("close_condition", "")
        if not time_limit:
            return None
        answer = [f"【案件类型】{case_type}", f"【处置时限】{time_limit}"]
        if close_condition:
            answer.append(f"【结案条件】{close_condition}")
        return "\n".join(answer)

    if intent == "close_condition":
        close_condition = meta.get("close_condition", "")
        time_limit = meta.get("time_limit", "")
        if not close_condition:
            return None
        answer = [f"【案件类型】{case_type}", f"【结案条件】{close_condition}"]
        if time_limit:
            answer.append(f"【处置时限】{time_limit}")
        return "\n".join(answer)

    if intent == "responsibility_subject":
        responsibility = meta.get("responsibility_subject") or top.get("parent_meta", {}).get("responsibility_subject", "")
        supervision = meta.get("supervision_subject") or top.get("parent_meta", {}).get("supervision_subject", "")
        if not responsibility:
            return None
        answer = [f"【案件类型】{case_type}", f"【责任主体】{responsibility}"]
        if supervision:
            answer.append(f"【监管主体】{supervision}")
        return "\n".join(answer)

    if intent == "supervision_subject":
        supervision = meta.get("supervision_subject") or top.get("parent_meta", {}).get("supervision_subject", "")
        responsibility = meta.get("responsibility_subject") or top.get("parent_meta", {}).get("responsibility_subject", "")
        if not supervision:
            return None
        answer = [f"【案件类型】{case_type}", f"【监管主体】{supervision}"]
        if responsibility:
            answer.append(f"【责任主体】{responsibility}")
        return "\n".join(answer)

    if intent == "collection_requirement":
        parent_text = top.get("parent_text", "")
        if not parent_text:
            return None
        match = re.search(r'【采集要求】(.+?)(?=\n【|$)', parent_text, re.DOTALL)
        if not match:
            return None
        collection_requirement = match.group(1).strip()
        if not collection_requirement:
            return None
        return f"【案件类型】{case_type}\n【采集要求】{collection_requirement}"

    return None


def _extract_answer_from_text(question: str, results: List[Dict], dept_info: str) -> str:
    """从知识库文本直接提取答案，按案件类型聚合所有相关条目"""
    q_norm = normalize_cn_text(question)
    answer_parts = [dept_info]

    # 从问题中提取场景关键词
    scenario_keywords = ["破损", "缺失", "移位", "开裂", "弹跳", "沉降", "丢失", "被盗",
                         "积冰", "积雪", "积水", "堵塞", "溢出", "倒塌", "倾斜",
                         "不洁", "脏", "污", "积存", "垃圾", "保洁", "清扫",
                         "私搭乱建", "违建", "占道", "抛洒", "遗撒"]

    # 按案件类型聚合：{case_type: [matched_entries_text]}
    type_entries = {}
    type_parent_text = {}

    for r in results:
        case_type = r.get('case_type', '')
        parent_text = r.get('parent_text', '')

        # 每个case_type只处理一次（取最完整的parent_text）
        if case_type in type_parent_text:
            continue
        type_parent_text[case_type] = parent_text

        # 按条目拆分
        entries = re.findall(r'(\d+:\s*.+?)(?=\n\d+:|\n【|$)', parent_text, re.DOTALL)

        # 检查case_type是否包含问题关键词
        case_type_norm = normalize_cn_text(case_type)
        # 匹配条件1：场景关键词匹配
        case_type_match = any(kw in case_type_norm for kw in scenario_keywords if kw in q_norm)
        # 匹配条件2：问题中的2-4字词组出现在case_type中（如"小广告"匹配"非法小广告"）
        if not case_type_match:
            for length in [4, 3, 2]:
                for i in range(len(question) - length + 1):
                    seg = question[i:i+length]
                    if all('\u4e00' <= c <= '\u9fa5' for c in seg) and seg in case_type_norm:
                        case_type_match = True
                        break
                if case_type_match:
                    break

        matched = []
        for entry in entries:
            entry_norm = normalize_cn_text(entry)
            # 匹配条件：条目包含关键词 或 case_type包含关键词（整个类型匹配）
            if case_type_match or any(kw in entry_norm for kw in scenario_keywords if kw in q_norm):
                time_m = re.search(r'处置时限:\s*(.+?)(?:\n|$)', entry)
                cond_m = re.search(r'结案条件:\s*(.+?)(?:\n|$)', entry)
                desc_m = re.search(r'\d+:\s*(.+?)(?:\n处置|$)', entry)
                if time_m and cond_m:
                    desc = desc_m.group(1).strip() if desc_m else ""
                    matched.append(f"  {desc} → 处置时限 {time_m.group(1).strip()}，结案条件 {cond_m.group(1).strip()}")

        if matched:
            # 每个类型最多保留3个最相关的条目
            type_entries[case_type] = matched[:3]
            # 同时提取监管/责任主体
            supervisor = re.search(r'【监管主体】(.+?)(?:\r?\n【|$)', parent_text)
            responsible = re.search(r'【责任主体】(.+?)(?:\r?\n【|$)', parent_text)
            sup_text = supervisor.group(1).strip() if supervisor else ""
            res_text = responsible.group(1).strip() if responsible else ""
            if sup_text and sup_text != "未指定":
                type_entries[case_type].append(f"  监管主体：{sup_text}")
            if res_text and res_text != "未指定":
                type_entries[case_type].append(f"  责任主体：{res_text}")

    # 按类型输出，最多3个类型，优先case_type精确匹配的
    sorted_types = sorted(type_entries.keys(), key=lambda ct: -sum(1 for seg in [
        question[i:i+l] for l in [4,3,2] for i in range(len(question)-l+1)
        if all('\u4e00' <= c <= '\u9fa5' for c in seg)
    ] if seg in normalize_cn_text(ct)))
    for case_type in sorted_types[:3]:
        entries = type_entries[case_type]
        answer_parts.append(f"\n【{case_type}】")
        answer_parts.extend(entries)

    return "\n".join(answer_parts)


def _refine_with_llm(question: str, extracted: str, history: list = None, dispatch_info: dict = None) -> str:
    """用LLM将提取的条目精炼成简洁回答，支持多轮对话"""
    history_text = ""
    if history:
        for msg in history[-6:]:  # 最多保留最近6轮
            role = "用户" if msg.get("role") == "user" else "助手"
            history_text += f"- {role}：{msg.get('content', '')}\n"

    # 检查是否需要追问
    all_matched = find_all_matching_types(question)
    type_groups = _group_types_by_category(all_matched)
    need_clarify = False
    clarify_options = []

    # 对于作业类投诉，不触发追问，优先匹配作业管理标准
    normalized_q = normalize_cn_text(question)
    is_operation_complaint = any(kw in normalized_q for kw in [
        "作业", "清扫", "洒水", "环卫", "未设置警示", "警示标识",
        "未设置", "不规范", "作业车", "导致", "投诉", "举报"
    ])

    if not is_operation_complaint:
        for category, subtypes in type_groups.items():
            if len(subtypes) > 3:
                need_clarify = True
                clarify_options = subtypes
                break

    # 构建地理匹配信息
    geo_info = ""
    if dispatch_info:
        unit = dispatch_info.get("unit")
        department = dispatch_info.get("department", "")
        geo_info = f"""
## 地理定位结果
用户已点选位置，系统自动匹配结果：
- 所属片区/单位：{unit if unit else '未匹配到具体片区'}
- 责任部门：{department if department else '未确定'}

注意：地理定位结果仅供参考，不决定由哪个部门处理。请根据参考标准中的案件类型，判断该问题应由哪个部门负责（如路面垃圾、碎玻璃渣等环卫问题归市容环卫中心，护栏损坏等市政问题归市政公用服务中心）。如果匹配到了片区，请在回答中注明具体片区。
"""

    prompt = f"""你是运城市城市管理局的资深专家。请根据以下立结案标准数据，分析市民反映的问题并给出专业答复。

## 分析步骤
1. 从市民描述中提取关键信息（**地点场景**、问题类型、涉及设施）
2. **重点理解用户的核心诉求**：识别问题的根本原因，而不是表面现象
   - 常见格式："XXX问题，建议XXX"（问题本质在前，"建议"只是表达方式）
   - 例如："树木害虫过多，建议喷洒药物" → 本质是"病虫害"，不是"建议"
   - 例如："道路坑洼，建议修复" → 本质是"道路破损"，不是"建议"
   - 例如："井盖缺失，建议更换" → 本质是"井盖缺失"，不是"建议"
3. **关键：根据场景上下文选择最匹配的标准**（如"绿化带内水管破裂"应选"绿地附属设施"而非"供水管道破裂"，因为场景是绿化带而非市政供水管网）
4. 在下方参考标准中找到最匹配的案件类型
5. 根据该案件类型的【监管主体】和【责任主体】判断归属部门
6. 给出处置建议和参考时限

## 重要规则（必须严格遵守）
- **只能使用参考标准中的信息回答**，不要添加参考标准中没有的内容
- **归属部门判断**：必须从参考标准中提取【监管主体】和【责任主体】字段，格式为"【监管主体】xxx"和"【责任主体】xxx"，直接复制使用，不要自己编造
- 处置建议和参考时限必须来自参考标准中的【立案条件】和【处置时限】
- 如果参考标准中没有相关信息，明确说明"根据现有知识库，未找到相关信息，建议咨询相关部门"
- **禁止根据常识或推测补充知识库中没有的内容**
- **场景优先原则**：问题中提到的场景（绿化带、公园、道路、工地等）是选择标准的关键依据
- **本质优先原则**：识别问题的本质（如病虫害、设施损坏等），不要被表面上的"建议"、"投诉"等词误导
- **"建议"不等于"建议类问题"**：市民说"建议修复XX"不是在提建议，而是在反映XX问题需要修复
- **对于投诉类问题**：优先理解用户的因果诉求（"因XX导致YY"），识别核心问题是什么
- **对于设施类问题**：如果涉及设施有多种子类型，且无法从问题中确定具体是哪种，应该先列出所有子类型让用户选择
- **责任主体定位规则（最高优先级）**：
  1. 当责任主体中同时包含我局单位（如排水服务中心、市容环卫中心等）和外单位（如所属街办、属地行政执法部门）时，**必须立即追问具体地点**，回答格式为："该问题可能涉及排水服务中心或所属街办，请问您反映的问题具体在哪个位置？（如：xx路xx小区附近），以便确定责任单位。"
  2. 当责任主体全部是我局单位时，直接给出答案
  3. 当责任主体全部是外单位时，说明不属于我局职责
  4. **绝对不要在不确定时就断言"属于我局职责"**
- 回答要简洁准确，有理有据

## 回答格式

### 问题分析
- 问题类型：xxx
- 涉及设施：xxx

### 归属判断
- 是否属于我局职责：是/否
- 判断依据：xxx

### 处置建议
- 责任部门：xxx
- 处置措施：xxx
- 参考时限：xxx

{f"## 可选子类型{chr(10)}问题涉及的设施有以下子类型，请先让用户确认具体是哪种：{chr(10)}{chr(10).join('- ' + t for t in clarify_options[:15])}" if need_clarify and clarify_options else ""}{geo_info}## 立结案标准数据
{extracted}

{f"对话历史：{chr(10)}{history_text}" if history_text else ""}市民问题：{question}

## 特别提醒（最重要）
**参考标准数据中已经包含了完整的【监管主体】和【责任主体】信息。你必须直接从参考标准中复制这些字段的内容，绝对不要说"未找到"或"缺少信息"。**

**示例：如果参考标准中写着"【责任主体】运城市市容环卫中心、各环卫部门"，你的回答中责任部门就应该写"运城市市容环卫中心、各环卫部门"，一字不差地复制。**

请按上述格式分析回答："""

    result = call_llm(prompt, timeout=120)
    if result:
        return result

    # LLM失败，返回原始提取的数据
    return extracted if extracted else "抱歉，处理您的问题时出现错误，请稍后重试。"

    return extracted


def _get_all_case_types() -> List[str]:
    """获取所有案件类型名称（缓存）"""
    if hasattr(_get_all_case_types, '_cache') and _get_all_case_types._cache:
        return _get_all_case_types._cache
    try:
        from pymilvus import Collection
        if not connect_milvus():
            return []
        collection = Collection(CASE_STANDARDS_COLLECTION)
        results = collection.query(
            expr='level == 1',
            output_fields=['case_type'],
            limit=500
        )
        types = list(set(r.get('case_type', '') for r in results if r.get('case_type')))
        _get_all_case_types._cache = types
        return types
    except Exception:
        return []


def _get_case_type_embeddings() -> Dict[str, list]:
    """获取所有案件类型的embedding（缓存）"""
    if hasattr(_get_case_type_embeddings, '_cache') and _get_case_type_embeddings._cache:
        return _get_case_type_embeddings._cache
    try:
        from pymilvus import Collection
        if not connect_milvus():
            return {}
        collection = Collection(CASE_STANDARDS_COLLECTION)
        results = collection.query(
            expr='level == 1',
            output_fields=['case_type', 'embedding'],
            limit=500
        )
        cache = {}
        for r in results:
            ct = r.get('case_type', '')
            emb = r.get('embedding', None)
            if ct and emb:
                cache[ct] = emb
        _get_case_type_embeddings._cache = cache
        return cache
    except Exception:
        return {}


def _pick_types_hybrid(question: str, top_n: int = 3) -> List[str]:
    """混合选类型：先关键词匹配，再embedding兜底"""
    # 第一步：关键词精确匹配（从问题中提取2-4字词组，匹配case_type）
    all_types = _get_all_case_types()
    keyword_matches = []
    for length in [4, 3, 2]:
        for i in range(len(question) - length + 1):
            seg = question[i:i+length]
            if not all('\u4e00' <= c <= '\u9fa5' for c in seg):
                continue
            # 跳过通用词
            if seg in ["处置", "时限", "结案", "条件", "找谁", "是谁", "哪个", "破损", "缺失", "管理"]:
                continue
            for ct in all_types:
                ct_norm = normalize_cn_text(ct)
                if seg in ct_norm and ct not in keyword_matches:
                    keyword_matches.append(ct)
                    if len(keyword_matches) >= top_n:
                        return keyword_matches

    if keyword_matches:
        return keyword_matches[:top_n]

    # 第二步：embedding相似度兜底
    return _pick_types_by_embedding(question, top_n)


def find_all_matching_types(question: str) -> List[str]:
    """查找所有匹配的案件类型（不限数量），用于判断是否需要追问"""
    all_types = _get_all_case_types()
    keyword_matches = []
    for length in [4, 3, 2]:
        for i in range(len(question) - length + 1):
            seg = question[i:i+length]
            if not all('\u4e00' <= c <= '\u9fa5' for c in seg):
                continue
            if seg in ["处置", "时限", "结案", "条件", "找谁", "是谁", "哪个", "破损", "缺失", "管理"]:
                continue
            for ct in all_types:
                ct_norm = normalize_cn_text(ct)
                if seg in ct_norm and ct not in keyword_matches:
                    keyword_matches.append(ct)
    return keyword_matches


def _group_types_by_category(types: List[str]) -> Dict[str, List[str]]:
    """将案件类型按大类分组，用于判断是否需要追问"""
    groups = {}
    for ct in types:
        parts = ct.split(' - ')
        if len(parts) >= 2:
            category = parts[0]
            sub_type = parts[1]
            if category not in groups:
                groups[category] = []
            groups[category].append(ct)
    return groups
    return _pick_types_by_embedding(question, top_n)


def _search_by_case_type(case_type: str, top_k: int = 5) -> List[Dict]:
    """按案件类型精确搜索"""
    try:
        from pymilvus import Collection
        if not connect_milvus():
            return []
        collection = Collection(CASE_STANDARDS_COLLECTION)
        results = collection.query(
            expr=f'level == 1 and case_type == "{case_type}"',
            output_fields=["parent_id", "text_content", "case_type", "meta_info"],
            limit=1
        )
        if not results:
            return []
        parent_id = results[0].get('parent_id')
        # 获取子条目
        children = collection.query(
            expr=f'level == 0 and parent_id == "{parent_id}"',
            output_fields=["id", "parent_id", "text_content", "case_type", "meta_info"],
            limit=top_k
        )
        for c in children:
            c['parent_text'] = results[0].get('text_content', '')
            c['parent_meta'] = results[0].get('meta_info', {})
            c['score'] = 1.0
        return children
    except Exception as e:
        print(f"[CaseStandards] 按类型搜索失败: {e}")
        return []


def ask_case_standard(question: str, top_k: int = 5, location: Any = None, history: list = None) -> Dict:
    """
    基于立结案标准回答问题
    流程：搜索知识库 → LLM分析回答
    """
    try:
        # 如果有位置信息，走地理匹配链路
        dispatch_info = None
        if location is not None:
            dispatch_result = match_department_dispatch(question, location, force_dispatch=True)
            if dispatch_result is not None:
                dispatch_info = dispatch_result
                # 有位置时，也搜索知识库补充信息
                results = search_case_standards(question, top_k)
                if results:
                    extracted = _extract_answer_from_text(question, results, dispatch_result.get("answer", ""))
                    answer = _refine_with_llm(question, extracted, history, dispatch_info)
                    sources = [r.get("case_type", "") for r in results[:3] if r.get("case_type")]
                    return {"answer": answer, "sources": list(dict.fromkeys(sources)), "success": True, "matches": results}
                dispatch_result["sources"] = []
                dispatch_result["matches"] = []
                return dispatch_result

        # === 核心流程：搜索知识库 → LLM分析回答 ===

        # 1. 向量搜索知识库
        results = search_case_standards(question, top_k=top_k)

        # 2. 检查是否需要追问：匹配到的类型属于同一子类但有多个子类型
        all_matched = find_all_matching_types(question)
        type_groups = _group_types_by_category(all_matched)
        need_clarify = False
        clarify_options = []
        for category, subtypes in type_groups.items():
            if len(subtypes) > 10:  # 同一大类下超过10个子类型，才需要追问
                need_clarify = True
                clarify_options = subtypes
                break

        if not results:
            return {"answer": "知识库中没有找到相关信息。", "sources": [], "success": True}

        # 4. 构建上下文给LLM总结
        context_parts = []
        seen = set()
        sources = []
        for r in results:
            ct = r.get('case_type', '')
            if ct in seen:
                continue
            seen.add(ct)
            parent_text = r.get('parent_text', '')
            context_parts.append(f"【{ct}】\n{parent_text}")
            sources.append(ct)

        context = "\n\n---\n\n".join(context_parts)

        history_text = ""
        if history:
            for msg in history[-4:]:
                role = "用户" if msg.get("role") == "user" else "助手"
                history_text += f"- {role}：{msg.get('content', '')}\n"

        prompt = f"""你是运城市城市管理局的资深专家。请根据以下立结案标准数据，分析市民反映的问题并给出专业答复。

## 分析步骤
1. 从市民描述中提取关键信息（**地点场景**、问题类型、涉及设施）
2. **重点理解用户的核心诉求**：识别问题的根本原因，而不是表面现象
   - 常见格式："XXX问题，建议XXX"（问题本质在前，"建议"只是表达方式）
   - 例如："树木害虫过多，建议喷洒药物" → 本质是"病虫害"，不是"建议"
   - 例如："道路坑洼，建议修复" → 本质是"道路破损"，不是"建议"
   - 例如："井盖缺失，建议更换" → 本质是"井盖缺失"，不是"建议"
3. **关键：根据场景上下文选择最匹配的标准**（如"绿化带内水管破裂"应选"绿地附属设施"而非"供水管道破裂"，因为场景是绿化带而非市政供水管网）
4. 在下方参考标准中找到最匹配的案件类型
5. **从该案件类型的【监管主体】和【责任主体】字段中提取归属部门信息**
6. 给出处置建议和参考时限

## 参考标准格式说明
每条标准包含以下字段：
- 【案件类型】：标准名称
- 【立案条件】：具体情形和处置时限
- 【监管主体】：管理部门（如：运城市城市管理局、盐湖区政府）
- 【责任主体】：具体处置部门（如：运城市市容环卫中心、各环卫部门）
- 【法律依据】：相关法规

**你必须从【监管主体】和【责任主体】字段中提取信息，不要自己编造部门名称**

## 重要规则（必须严格遵守）
- **只能使用参考标准中的信息回答**，不要添加参考标准中没有的内容
- **归属部门判断**：必须从参考标准中提取【监管主体】和【责任主体】字段，格式为"【监管主体】xxx"和"【责任主体】xxx"，直接复制使用，不要自己编造
- 处置建议和参考时限必须来自参考标准中的【立案条件】和【处置时限】
- 如果参考标准中没有相关信息，明确说明"根据现有知识库，未找到相关信息，建议咨询相关部门"
- **禁止根据常识或推测补充知识库中没有的内容**
- **场景优先原则**：问题中提到的场景（绿化带、公园、道路、工地等）是选择标准的关键依据
- **本质优先原则**：识别问题的本质（如病虫害、设施损坏等），不要被表面上的"建议"、"投诉"等词误导
- **"建议"不等于"建议类问题"**：市民说"建议修复XX"不是在提建议，而是在反映XX问题需要修复
- **对于投诉类问题**：优先理解用户的因果诉求（"因XX导致YY"），识别核心问题是什么
- **对于设施类问题**：如果涉及设施有多种子类型，且无法从问题中确定具体是哪种，应该先列出所有子类型让用户选择
- **责任主体定位规则（最高优先级）**：
  1. 当责任主体中同时包含我局单位（如排水服务中心、市容环卫中心等）和外单位（如所属街办、属地行政执法部门）时，**必须立即追问具体地点**，回答格式为："该问题可能涉及排水服务中心或所属街办，请问您反映的问题具体在哪个位置？（如：xx路xx小区附近），以便确定责任单位。"
  2. 当责任主体全部是我局单位时，直接给出答案
  3. 当责任主体全部是外单位时，说明不属于我局职责
  4. **绝对不要在不确定时就断言"属于我局职责"**
- 回答要简洁准确，有理有据

## 回答格式

### 问题分析
- 问题类型：xxx
- 涉及设施：xxx

### 归属判断
- 是否属于我局职责：是/否
- 判断依据：xxx

### 处置建议
- 责任部门：xxx
- 处置措施：xxx
- 参考时限：xxx

{f"## 可选子类型{chr(10)}问题涉及的设施有以下子类型，请先让用户确认具体是哪种：{chr(10)}{chr(10).join('- ' + t for t in clarify_options[:15])}" if need_clarify and clarify_options else ""}## 立结案标准数据
{context}

{f"对话历史：{chr(10)}{history_text}" if history_text else ""}市民问题：{question}

## 特别提醒（最重要）
**参考标准数据中已经包含了完整的【监管主体】和【责任主体】信息。你必须直接从参考标准中复制这些字段的内容，绝对不要说"未找到"或"缺少信息"。**

**示例：如果参考标准中写着"【责任主体】运城市市容环卫中心、各环卫部门"，你的回答中责任部门就应该写"运城市市容环卫中心、各环卫部门"，一字不差地复制。**

请按上述格式分析回答："""

        # 5. LLM生成回答
        answer = call_llm(prompt, timeout=120)
        if answer:
            return {"answer": answer, "sources": list(dict.fromkeys(sources)), "success": True}

        # LLM失败，返回提取的原始数据
        extracted = _extract_answer_from_text(question, results, "")
        if extracted and len(extracted.strip()) > 5:
            return {"answer": extracted, "sources": list(dict.fromkeys(sources)), "success": True}

        return {"answer": "抱歉，处理您的问题时出现错误，请稍后重试。", "sources": [], "success": False}

    except Exception as e:
        print(f"[CaseStandards] 问答失败: {e}")
        return {"answer": str(e), "sources": [], "success": False}


def get_case_standards_stats_chroma() -> Dict:
    """获取统计信息（ChromaDB 本地模式）"""
    try:
        client = get_chroma_client()
        if client is None:
            return {"exists": False, "error": "ChromaDB连接失败"}

        collections = client.list_collections()

        parent_count = 0
        child_count = 0

        for coll in collections:
            coll_name = coll.name if hasattr(coll, 'name') else str(coll)
            if coll_name == PARENT_COLLECTION:
                parent_count = coll.count()
            elif coll_name == CHILD_COLLECTION:
                child_count = coll.count()

        if parent_count == 0 and child_count == 0:
            return {"exists": False, "count": 0, "mode": "local (ChromaDB)"}

        return {
            "exists": True,
            "name": CASE_STANDARDS_COLLECTION,
            "count": parent_count + child_count,
            "parents": parent_count,
            "children": child_count,
            "mode": "local (ChromaDB)",
            "db_path": LOCAL_DB_PATH,
            "embed_model": LOCAL_EMBED_MODEL,
            "llm": f"豆包API ({DOUBAO_MODEL})"
        }

    except Exception as e:
        return {"exists": False, "error": str(e)}


def get_case_standards_stats_milvus() -> Dict:
    """获取统计信息（Milvus 服务器模式）"""
    try:
        from pymilvus import Collection, utility

        if not connect_milvus():
            return {"exists": False, "error": "Milvus连接失败"}

        if not utility.has_collection(CASE_STANDARDS_COLLECTION):
            return {"exists": False, "count": 0}

        collection = Collection(CASE_STANDARDS_COLLECTION)
        collection.load()

        parent_count = len(collection.query(expr="level == 1", output_fields=["id"]))
        child_count = len(collection.query(expr="level == 0", output_fields=["id"]))

        return {
            "exists": True,
            "name": CASE_STANDARDS_COLLECTION,
            "count": collection.num_entities,
            "parents": parent_count,
            "children": child_count,
            "mode": "server"
        }

    except Exception as e:
        return {"exists": False, "error": str(e)}


def get_case_standards_stats() -> Dict:
    """获取立结案标准集合统计信息（统一使用 Milvus）"""
    return get_case_standards_stats_milvus()


def clear_case_standards_chroma() -> Dict:
    """清空立结案标准库（ChromaDB 本地模式）"""
    try:
        client = get_chroma_client()
        if client is None:
            return {"success": False, "message": "ChromaDB连接失败"}

        # 删除集合
        try:
            client.delete_collection(PARENT_COLLECTION)
            client.delete_collection(CHILD_COLLECTION)
            print(f"[CaseStandards] 已删除集合")
        except:
            pass

        return {"success": True, "message": "已清空立结案标准库"}

    except Exception as e:
        return {"success": False, "message": str(e)}


def clear_case_standards_milvus() -> Dict:
    """清空立结案标准库（Milvus 服务器模式）"""
    try:
        from pymilvus import utility

        if not connect_milvus():
            return {"success": False, "message": "Milvus连接失败"}

        if utility.has_collection(CASE_STANDARDS_COLLECTION):
            utility.drop_collection(CASE_STANDARDS_COLLECTION)
            print(f"[CaseStandards] 已删除集合: {CASE_STANDARDS_COLLECTION}")

        return {"success": True, "message": "已清空立结案标准库"}

    except Exception as e:
        return {"success": False, "message": str(e)}


def clear_case_standards() -> Dict:
    """清空立结案标准集合（统一使用 Milvus）"""
    return clear_case_standards_milvus()


# 测试函数
def test_parse_file():
    """测试文件解析"""
    test_file = "D:/常用/立案结案标准/公用设施_上水井盖.txt"
    if os.path.exists(test_file):
        result = parse_standard_file(test_file)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"测试文件不存在: {test_file}")


# ==================== 索引管理功能 ====================

def list_indexed_standards_chroma() -> List[Dict]:
    """列出已索引的立结案标准（ChromaDB本地模式）"""
    try:
        client = get_chroma_client()
        if client is None:
            return []

        # 获取父文档集合
        parent_coll = client.get_or_create_collection(name=PARENT_COLLECTION)
        child_coll = client.get_or_create_collection(name=CHILD_COLLECTION)

        # 获取所有父文档
        parent_docs = parent_coll.get(include=['metadatas', 'documents'])

        results = []
        for i, parent_id in enumerate(parent_docs['ids']):
            meta = parent_docs['metadatas'][i] if parent_docs['metadatas'] else {}
            doc = parent_docs['documents'][i] if parent_docs['documents'] else ''

            # 统计子文档数量
            child_count = 0
            try:
                # 通过metadata中的parent_id筛选
                all_children = child_coll.get(include=['metadatas'])
                child_count = sum(1 for m in all_children['metadatas']
                                 if m and m.get('parent_id') == parent_id)
            except:
                pass

            results.append({
                'parent_id': parent_id,
                'filename': meta.get('filename', ''),
                'case_type': meta.get('case_type', ''),
                'big_category': meta.get('big_category', ''),
                'small_category': meta.get('small_category', ''),
                'child_count': child_count,
                'supervision_subject': meta.get('supervision_subject', ''),
                'responsibility_subject': meta.get('responsibility_subject', '')
            })

        # 按大类、小类排序
        results.sort(key=lambda x: (x.get('big_category', ''), x.get('small_category', '')))

        return results

    except Exception as e:
        print(f"[CaseStandards] 列出标准失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def list_indexed_standards_milvus() -> List[Dict]:
    """列出已索引的立结案标准（Milvus服务器模式）"""
    try:
        from pymilvus import Collection, utility

        if not connect_milvus():
            return []

        if not utility.has_collection(CASE_STANDARDS_COLLECTION):
            return []

        collection = Collection(CASE_STANDARDS_COLLECTION)
        collection.load()

        # 查询父文档（level == 1）
        parent_results = collection.query(
            expr="level == 1",
            output_fields=["id", "parent_id", "text_content", "case_type", "meta_info"]
        )

        # 查询子文档数量
        child_results = collection.query(
            expr="level == 0",
            output_fields=["parent_id"]
        )

        # 统计每个父文档的子文档数量
        child_count_map = {}
        for cr in child_results:
            pid = cr.get('parent_id')
            if pid:
                child_count_map[pid] = child_count_map.get(pid, 0) + 1

        results = []
        for pr in parent_results:
            parent_id = pr.get('id')
            meta = pr.get('meta_info', {})
            if isinstance(meta, str):
                meta = json.loads(meta)

            results.append({
                'parent_id': parent_id,
                'filename': meta.get('filename', ''),
                'case_type': pr.get('case_type', '') or meta.get('case_type', ''),
                'big_category': meta.get('big_category', ''),
                'small_category': meta.get('small_category', ''),
                'child_count': child_count_map.get(parent_id, 0),
                'supervision_subject': meta.get('supervision_subject', ''),
                'responsibility_subject': meta.get('responsibility_subject', '')
            })

        # 按大类、小类排序
        results.sort(key=lambda x: (x.get('big_category', ''), x.get('small_category', '')))

        return results

    except Exception as e:
        print(f"[CaseStandards] 列出标准失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def list_indexed_standards() -> List[Dict]:
    """列出已索引的立结案标准（统一使用 Milvus）"""
    return list_indexed_standards_milvus()


def delete_single_standard_chroma(parent_id: str) -> Dict:
    """删除单个立结案标准（ChromaDB本地模式）"""
    try:
        client = get_chroma_client()
        if client is None:
            return {"success": False, "message": "ChromaDB连接失败"}

        parent_coll = client.get_or_create_collection(name=PARENT_COLLECTION)
        child_coll = client.get_or_create_collection(name=CHILD_COLLECTION)

        # 获取所有子文档，找出属于该父文档的
        all_children = child_coll.get(include=['metadatas'])
        child_ids_to_delete = []
        for i, cid in enumerate(all_children['ids']):
            meta = all_children['metadatas'][i] if all_children['metadatas'] else {}
            if meta.get('parent_id') == parent_id:
                child_ids_to_delete.append(cid)

        # 删除子文档
        if child_ids_to_delete:
            child_coll.delete(ids=child_ids_to_delete)
            print(f"[CaseStandards] 删除了 {len(child_ids_to_delete)} 个子文档")

        # 删除父文档
        try:
            parent_coll.delete(ids=[parent_id])
            print(f"[CaseStandards] 删除了父文档: {parent_id}")
        except:
            pass

        return {
            "success": True,
            "deleted_children": len(child_ids_to_delete),
            "message": f"成功删除标准，共删除 {len(child_ids_to_delete)} 个子文档"
        }

    except Exception as e:
        print(f"[CaseStandards] 删除失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


def delete_single_standard_milvus(parent_id: str) -> Dict:
    """删除单个立结案标准（Milvus服务器模式）"""
    try:
        from pymilvus import Collection, utility

        if not connect_milvus():
            return {"success": False, "message": "Milvus连接失败"}

        if not utility.has_collection(CASE_STANDARDS_COLLECTION):
            return {"success": True, "message": "集合不存在"}

        collection = Collection(CASE_STANDARDS_COLLECTION)

        # 查询该标准的子文档数量
        child_results = collection.query(
            expr=f'level == 0 and parent_id == "{parent_id}"',
            output_fields=["id"]
        )
        child_count = len(child_results)

        # 删除该父文档和所有子文档
        collection.delete(expr=f'parent_id == "{parent_id}"')
        collection.flush()

        return {
            "success": True,
            "deleted_children": child_count,
            "message": f"成功删除标准，共删除 {child_count} 个子文档"
        }

    except Exception as e:
        print(f"[CaseStandards] 删除失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


def delete_single_standard(parent_id: str) -> Dict:
    """删除单个立结案标准（统一使用 Milvus）"""
    return delete_single_standard_milvus(parent_id)


def incremental_index_chroma(directory: str, progress_callback=None) -> Dict:
    """
    增量索引（ChromaDB本地模式）
    只索引新增或修改的文件
    progress_callback: 进度回调函数 callback(current, total, filename, status)
    """
    try:
        client = get_chroma_client()
        if client is None:
            return {"success": 0, "failed": 0, "skipped": 0, "message": "ChromaDB连接失败"}

        parent_coll = client.get_or_create_collection(name=PARENT_COLLECTION)

        # 获取已索引的文件名列表
        existing_docs = parent_coll.get(include=['metadatas'])
        indexed_filenames = set()
        indexed_hashes = {}  # filename -> doc_id

        for i, doc_id in enumerate(existing_docs['ids']):
            meta = existing_docs['metadatas'][i] if existing_docs['metadatas'] else {}
            filename = meta.get('filename', '')
            if filename:
                indexed_filenames.add(filename)
                indexed_hashes[filename] = doc_id

        # 获取目录中的所有txt文件
        if not os.path.isdir(directory):
            return {"success": 0, "failed": 0, "skipped": 0, "message": f"目录不存在: {directory}"}

        txt_files = [f for f in os.listdir(directory) if f.endswith('.txt')]
        total_files = len(txt_files)

        results = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total_children": 0,
            "details": []
        }

        print(f"[CaseStandards] 增量索引开始，已有 {len(indexed_filenames)} 个标准，发现 {total_files} 个文件")

        for i, filename in enumerate(txt_files, 1):
            file_path = os.path.join(directory, filename)
            status = "processing"

            if progress_callback:
                progress_callback(i, total_files, filename, status)

            # 检查是否已索引
            if filename in indexed_filenames:
                # 可选：检查文件是否被修改（通过文件大小或修改时间）
                # 这里简单跳过已索引的文件
                status = "skipped"
                results['skipped'] += 1
                results['details'].append({
                    'file': filename,
                    'status': 'skipped',
                    'message': '已存在，跳过'
                })
                print(f"[CaseStandards] [{i}/{total_files}] 跳过: {filename}")

                if progress_callback:
                    progress_callback(i, total_files, filename, status)
                continue

            # 索引新文件
            print(f"[CaseStandards] [{i}/{total_files}] 新文件: {filename}")
            result = index_standard_file(file_path)

            if result['success']:
                results['success'] += 1
                results['total_children'] += result['children']
                status = "success"
            else:
                results['failed'] += 1
                status = "failed"

            results['details'].append({
                'file': filename,
                'status': status,
                'children': result['children'],
                'message': result['message']
            })

            if progress_callback:
                progress_callback(i, total_files, filename, status)

        print(f"[CaseStandards] 增量索引完成: 新增 {results['success']}, 失败 {results['failed']}, 跳过 {results['skipped']}")
        return results

    except Exception as e:
        print(f"[CaseStandards] 增量索引失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": 0, "failed": 0, "skipped": 0, "message": str(e)}


def incremental_index_milvus(directory: str, progress_callback=None) -> Dict:
    """
    增量索引（Milvus服务器模式）
    只索引新增或修改的文件
    """
    try:
        from pymilvus import Collection, utility

        if not connect_milvus():
            return {"success": 0, "failed": 0, "skipped": 0, "message": "Milvus连接失败"}

        # 获取已索引的文件名列表
        indexed_filenames = set()
        indexed_hashes = {}

        if utility.has_collection(CASE_STANDARDS_COLLECTION):
            collection = Collection(CASE_STANDARDS_COLLECTION)
            collection.load()

            parent_results = collection.query(
                expr="level == 1",
                output_fields=["id", "meta_info"]
            )

            for pr in parent_results:
                meta = pr.get('meta_info', {})
                if isinstance(meta, str):
                    meta = json.loads(meta)
                filename = meta.get('filename', '')
                if filename:
                    indexed_filenames.add(filename)
                    indexed_hashes[filename] = pr['id']

        # 获取目录中的所有txt文件
        if not os.path.isdir(directory):
            return {"success": 0, "failed": 0, "skipped": 0, "message": f"目录不存在: {directory}"}

        txt_files = [f for f in os.listdir(directory) if f.endswith('.txt')]
        total_files = len(txt_files)

        results = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total_children": 0,
            "details": []
        }

        print(f"[CaseStandards] 增量索引开始，已有 {len(indexed_filenames)} 个标准")

        for i, filename in enumerate(txt_files, 1):
            file_path = os.path.join(directory, filename)
            status = "processing"

            if progress_callback:
                progress_callback(i, total_files, filename, status)

            if filename[:-4] in indexed_filenames:  # Strip .txt for comparison
                status = "skipped"
                results['skipped'] += 1
                results['details'].append({
                    'file': filename,
                    'status': 'skipped',
                    'message': '已存在，跳过'
                })
                if progress_callback:
                    progress_callback(i, total_files, filename, status)
                continue

            result = index_standard_file(file_path)

            if result['success']:
                results['success'] += 1
                results['total_children'] += result['children']
                status = "success"
            else:
                results['failed'] += 1
                status = "failed"

            results['details'].append({
                'file': filename,
                'status': status,
                'children': result['children'],
                'message': result['message']
            })

            if progress_callback:
                progress_callback(i, total_files, filename, status)

        return results

    except Exception as e:
        print(f"[CaseStandards] 增量索引失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": 0, "failed": 0, "skipped": 0, "message": str(e)}


def incremental_index(directory: str, progress_callback=None) -> Dict:
    """增量索引（统一使用 Milvus）"""
    return incremental_index_milvus(directory, progress_callback)


def index_single_file_upload(file_content: str, filename: str) -> Dict:
    """
    索引单个上传的文件（通过内容而非文件路径）
    用于前端上传单个txt文件直接索引
    """
    try:
        # 临时保存文件
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, filename)

        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(file_content)

        # 索引文件
        result = index_standard_file(temp_path)

        # 删除临时文件
        try:
            os.remove(temp_path)
        except:
            pass

        return result

    except Exception as e:
        print(f"[CaseStandards] 单文件索引失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    # 测试解析
    test_parse_file()