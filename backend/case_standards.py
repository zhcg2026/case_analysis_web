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
- Ollama nomic-embed-text + Qwen2.5-7B
"""

import os
import re
import json
import hashlib
import requests
from typing import List, Dict, Optional, Tuple

# 设置离线模式，防止模型尝试联网下载
os.environ['HF_DATASETS_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

# 本地模式配置
USE_LOCAL_MODE = os.getenv('USE_LOCAL_MODE', 'false').lower() == 'true'

# 服务器模式配置
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')
MILVUS_HOST = os.getenv('MILVUS_HOST', 'localhost')
MILVUS_PORT = os.getenv('MILVUS_PORT', '19530')

# 本地模式特定配置
LOCAL_DB_PATH = os.getenv('LOCAL_DB_PATH', './chroma_db')
LOCAL_EMBED_MODEL = os.getenv('LOCAL_EMBED_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')

# 豆包API配置（本地模式使用）
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
    """索引单个立结案标准文件（自动选择模式）"""
    if USE_LOCAL_MODE:
        return index_standard_file_chroma(file_path)
    else:
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


def search_case_standards_chroma(query: str, top_k: int = 5) -> List[Dict]:
    """搜索立结案标准（ChromaDB 本地模式）- 混合检索：向量+关键词"""
    try:
        client = get_chroma_client()
        if client is None:
            return []

        child_coll = client.get_or_create_collection(name=CHILD_COLLECTION)
        parent_coll = client.get_or_create_collection(name=PARENT_COLLECTION)

        # 获取查询向量
        query_embedding = get_embedding(query)
        if not query_embedding:
            return []

        # 提取关键词（用于文本匹配增强）
        # 预定义案件类型关键词（核心匹配词）
        case_type_keywords = [
            # 市容环境类
            '建筑垃圾', '道路遗撒', '积存垃圾', '垃圾渣土', '装修垃圾', '废弃渣土',
            '生活垃圾', '暴露垃圾', '垃圾堆积', '乱倒垃圾', '卫生死角',
            '占道经营', '店外经营', '流动摊贩', '乱摆摊', '露天烧烤',
            '乱贴乱画', '非法广告', '小广告', '张贴广告', '涂写广告',
            '私搭乱建', '违章建筑', '临时建筑', '违法建设',
            # 公用设施类
            '井盖', '破损', '缺失', '移位', '下沉', '塌陷', '变形', '锈蚀',
            '天桥', '裂缝', '路灯', '护栏', '标志', '信号灯', '交通标志',
            '高架', '立交', '桥梁', '跨河', '栈桥', '过街',
            '上水', '下水', '供水', '排水', '燃气', '供热', '供电',
            '道牙', '路牙', '人行道', '路面', '道路破损',
            # 其他常见类型
            '绿化', '树木', '草坪', '花坛', '裸露绿地',
            '油烟', '噪声', '异味', '扬尘', '粉尘',
            '违章停车', '乱停乱放', '停车占道',
        ]
        # 从查询中提取匹配的案件类型关键词（核心词优先）
        keywords = []
        for kw in case_type_keywords:
            if kw in query and kw not in keywords:
                keywords.append(kw)

        # 提取单字重要词（如破损中的"破"、"损"）
        important_chars = ['井', '盖', '破', '损', '缺', '失', '移', '位', '裂', '陷', '桥', '灯', '牌', '栏', '杆', '漏', '堵', '锈']
        for c in query:
            if c in important_chars and c not in keywords:
                keywords.append(c)

        # 1. 向量搜索（获取更多候选）
        vec_results = child_coll.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 3  # 获取更多候选
        )

        # 2. 关键词搜索（如果有关键词）
        keyword_matches = []
        if keywords:
            all_docs = child_coll.get(include=['documents', 'metadatas'])
            for i, doc in enumerate(all_docs['documents']):
                match_count = sum(1 for kw in keywords if kw in doc)
                if match_count > 0:
                    keyword_matches.append({
                        'id': all_docs['ids'][i],
                        'doc': doc,
                        'meta': all_docs['metadatas'][i] if all_docs['metadatas'] else {},
                        'keyword_score': match_count / len(keywords)
                    })
            # 按关键词匹配度排序
            keyword_matches.sort(key=lambda x: x['keyword_score'], reverse=True)

        # 3. 合并结果：关键词匹配优先
        combined_ids = set()
        parent_ids = set()
        child_results = []

        # 先添加关键词匹配的（最多top_k个）
        for km in keyword_matches[:top_k]:
            if km['id'] not in combined_ids:
                combined_ids.add(km['id'])
                parent_id = km['meta'].get('parent_id', '')
                if parent_id:
                    parent_ids.add(parent_id)
                child_results.append({
                    "child_id": km['id'],
                    "parent_id": parent_id,
                    "child_text": km['doc'],
                    "case_type": km['meta'].get('case_type', ''),
                    "meta_info": km['meta'],
                    "score": 0.8 + km['keyword_score'] * 0.2,  # 关键词匹配给予高分
                    "match_type": "keyword"
                })

        # 再添加向量搜索的（补充未匹配的）
        if vec_results['ids'] and vec_results['ids'][0]:
            for i, child_id in enumerate(vec_results['ids'][0]):
                if child_id not in combined_ids and len(child_results) < top_k:
                    combined_ids.add(child_id)
                    meta = vec_results['metadatas'][0][i] if vec_results['metadatas'] else {}
                    parent_id = meta.get('parent_id', '')
                    if parent_id:
                        parent_ids.add(parent_id)
                    child_results.append({
                        "child_id": child_id,
                        "parent_id": parent_id,
                        "child_text": vec_results['documents'][0][i] if vec_results['documents'] else '',
                        "case_type": meta.get('case_type', ''),
                        "meta_info": meta,
                        "score": max(0, 1 - vec_results['distances'][0][i] / 10) if vec_results['distances'] else 0,
                        "match_type": "vector"
                    })

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

        return child_results

    except Exception as e:
        print(f"[CaseStandards] 搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def search_case_standards_milvus(query: str, top_k: int = 5) -> List[Dict]:
    """搜索立结案标准（Milvus 服务器模式）"""
    try:
        from pymilvus import Collection, utility

        if not connect_milvus():
            return []

        if not utility.has_collection(CASE_STANDARDS_COLLECTION):
            return []

        collection = Collection(CASE_STANDARDS_COLLECTION)
        collection.load()

        query_embedding = get_embedding(query)
        if not query_embedding:
            return []

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
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
                    "score": hit.distance
                })

        if parent_ids:
            parent_results = collection.query(
                expr=f'level == 1 and parent_id in {list(parent_ids)}',
                output_fields=["parent_id", "text_content", "meta_info"]
            )

            parent_map = {}
            for pr in parent_results:
                parent_map[pr['parent_id']] = {
                    'text': pr['text_content'],
                    'meta': pr['meta_info']
                }

            for cr in child_results:
                parent_info = parent_map.get(cr['parent_id'], {})
                cr['parent_text'] = parent_info.get('text', '')
                cr['parent_meta'] = parent_info.get('meta', {})

        return child_results

    except Exception as e:
        print(f"[CaseStandards] 搜索失败: {e}")
        return []


def search_case_standards(query: str, top_k: int = 5) -> List[Dict]:
    """搜索立结案标准（自动选择模式）"""
    # 动态检查本地模式
    use_local = os.getenv('USE_LOCAL_MODE', 'false').lower() == 'true'
    if use_local:
        return search_case_standards_chroma(query, top_k)
    else:
        return search_case_standards_milvus(query, top_k)


def ask_case_standard(question: str, top_k: int = 5) -> Dict:
    """
    基于立结案标准回答问题（父子索引RAG）
    返回: {"answer": str, "sources": list, "success": bool}
    """
    try:
        results = search_case_standards(question, top_k)

        if not results:
            return {
                "answer": "立结案标准库中没有找到相关信息。",
                "sources": [],
                "success": True
            }

        # 构建上下文（使用父文档的完整内容）
        context_parts = []
        seen_parents = set()
        sources = []

        for r in results:
            parent_id = r['parent_id']
            if parent_id not in seen_parents:
                seen_parents.add(parent_id)
                case_type = r.get('case_type', '')
                parent_text = r.get('parent_text', '')

                context_parts.append(f"【案件类型】{case_type}\n{parent_text}")
                sources.append(case_type)

        context = "\n\n---\n\n".join(context_parts)

        prompt = f"""你是一个智慧城市管理专家，专门负责立结案标准的咨询。

请根据以下【参考标准】回答用户的问题。回答要求：
1. **优先判断语义包含关系**：如果用户问题中的案件类型（如"建筑垃圾"）属于参考标准中案件类型的子类或具体形式（如"积存垃圾渣土"包含建筑垃圾、装修垃圾等），应当直接给出标准答案
2. 直接回答用户关心的问题，重点给出：处置时限、结案条件
3. 如果有责任主体或监管主体信息，可以补充说明
4. 回答要简洁准确，引用标准中的原文
5. 只有当参考标准与用户问题完全无关时，才回复"未找到相关标准"

【参考标准】:
{context}

【用户问题】:
{question}

请给出准确、简洁的回答："""

        # 动态检查本地模式
        use_local = os.getenv('USE_LOCAL_MODE', 'false').lower() == 'true'

        if use_local:
            # 本地模式：调用豆包API
            response = requests.post(
                DOUBAO_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DOUBAO_API_KEY}"
                },
                json={
                    "model": DOUBAO_MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=180
            )

            if response.status_code == 200:
                data = response.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {
                    "answer": answer,
                    "sources": sources,
                    "success": True,
                    "matches": results
                }
            else:
                return {
                    "answer": f"豆包API调用失败: {response.status_code}",
                    "sources": sources,
                    "success": False
                }
        else:
            # 服务器模式：调用Ollama
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=180
            )

            if response.status_code == 200:
                answer = response.json().get("response", "")
                return {
                    "answer": answer,
                    "sources": sources,
                    "success": True,
                    "matches": results
                }
            else:
                return {
                    "answer": f"LLM调用失败: {response.status_code}",
                    "sources": sources,
                    "success": False
                }

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
    """获取立结案标准集合统计信息（自动选择模式）"""
    if USE_LOCAL_MODE:
        return get_case_standards_stats_chroma()
    else:
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
    """清空立结案标准集合（自动选择模式）"""
    if USE_LOCAL_MODE:
        return clear_case_standards_chroma()
    else:
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


if __name__ == "__main__":
    # 测试解析
    test_parse_file()