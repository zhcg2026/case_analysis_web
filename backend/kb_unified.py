"""
统一知识库入口模块
整合通用知识库 (rag.py) 和立结案标准库 (case_standards.py)

核心能力：
1. 智能问答：理解问题意图，自动选择检索策略
2. 统一检索：同时搜索两库，合并结果
3. 统计信息：综合两库的统计
4. 数据迁移：通用知识库迁移到统一库
"""

import os
import re
from typing import List, Dict, Optional, Any

# 尝试导入两套系统的模块
try:
    from backend.rag import (
        search_similar as general_search,
        ask_question as general_ask,
        get_collection_stats as general_stats,
        insert_document as general_insert,
    )
except ImportError:
    from rag import (
        search_similar as general_search,
        ask_question as general_ask,
        get_collection_stats as general_stats,
        insert_document as general_insert,
    )

try:
    from backend.case_standards import (
        search_case_standards,
        ask_case_standard,
        get_case_standards_stats,
        match_department_dispatch,
        _pick_types_hybrid,
        _search_by_case_type,
        _extract_answer_from_text,
        _refine_with_llm,
        build_query_profile,
        normalize_cn_text,
        pre_analyze_question,
    )
except ImportError:
    from case_standards import (
        search_case_standards,
        ask_case_standard,
        get_case_standards_stats,
        match_department_dispatch,
        _pick_types_hybrid,
        _search_by_case_type,
        _extract_answer_from_text,
        _refine_with_llm,
        build_query_profile,
        normalize_cn_text,
        pre_analyze_question,
    )


# ==================== 意图识别 ====================

# 立结案标准相关关键词
STANDARDS_KEYWORDS = [
    "处置时限", "结案条件", "时限", "结案", "立案", "立案条件",
    "责任主体", "监管主体", "采集要求", "归哪个部门", "哪个单位",
    "由谁处置", "负责部门", "管辖", "归属",
]

# 城市设施问题关键词（涉及这些词也走立结案标准库）
FACILITY_KEYWORDS = [
    # 交通设施
    "护栏", "井盖", "路灯", "信号灯", "红绿灯", "公交站", "公交站亭", "交通标志",
    # 园林绿化
    "树木", "草坪", "绿化", "绿化带", "绿地", "行道树", "古树", "修剪",
    # 广告招牌
    "广告牌", "招牌", "门头", "小广告",
    # 环卫设施
    "垃圾桶", "果皮箱", "垃圾箱", "垃圾站", "垃圾中转站",
    "公共厕所", "公厕", "厕所", "如厕",
    # 道路/路面
    "路面", "道路", "坑洼", "不平", "破损", "路面破损", "道路破损",
    "人行道", "盲道",
    # 排水/水务
    "排水", "下水道", "下水", "积水", "污水", "雨水", "水管", "管道", "破裂", "漏水",
    "供水", "供水管道", "外溢",
    # 市政设施
    "健身器材", "围栏", "交通设施", "市政", "设施",
    # 环卫作业
    "环卫", "保洁", "作业", "清扫", "洒水", "清洁", "环卫车", "作业车",
    # 城市秩序
    "投诉", "举报", "建议", "求助", "赔偿",
    "辱骂", "态度恶劣", "服务态度",
    "占道", "流动摊贩", "游商",
    # 施工
    "工地", "施工", "围挡", "扬尘",
    # 照明
    "灯", "景观灯", "地灯",
    # 共享单车
    "共享单车", "共享电动车", "共享电瓶车", "单车", "停放", "乱停放",
    # 通用设施状态词
    "损坏", "破损", "缺失", "丢失", "断裂", "弯曲", "变形",
    "脏污", "不洁", "积存", "垃圾", "污染", "倾斜", "倒塌",
    "松动", "脱落", "堵塞", "溢水", "噪音", "异味",
    "粪便", "排泄物", "呕吐物", "动物尸体", "遗撒", "抛洒", "洒落",
    # 能源
    "天然气", "燃气", "停气", "供气", "暖气", "供热", "供暖",
    "水电", "供电", "消防",
    # 绿化问题
    "病虫害", "虫害", "虫子",
]

# 通用知识相关关键词
GENERAL_KEYWORDS = [
    "职责", "职能", "政策", "法规", "法律", "规定", "制度",
    "流程", "办法", "条例", "规范", "标准",
]

# 部门归属相关关键词（需要位置信息）
DISPATCH_KEYWORDS = [
    "归哪个部门", "哪个单位负责", "由谁处置", "负责部门",
    "处置部门", "谁负责", "归谁", "管辖范围",
]


def _analyze_intent(question: str) -> Dict[str, Any]:
    """
    分析用户问题的意图
    返回: {
        "is_standards": bool,  # 是否涉及立结案标准
        "is_dispatch": bool,   # 是否涉及部门归属
        "need_location": bool, # 是否需要位置信息
        "intent": str,         # 具体意图
    }
    """
    normalized = normalize_cn_text(question)

    # 检查是否涉及立结案标准（显式关键词）
    is_standards = any(
        normalize_cn_text(kw) in normalized
        for kw in STANDARDS_KEYWORDS
    )

    # 如果没有显式关键词，检查是否涉及城市设施问题
    if not is_standards:
        is_standards = any(
            normalize_cn_text(kw) in normalized
            for kw in FACILITY_KEYWORDS
        )

    # 检查是否涉及部门归属
    is_dispatch = any(
        normalize_cn_text(kw) in normalized
        for kw in DISPATCH_KEYWORDS
    )

    # 判断是否需要位置信息
    need_location = is_dispatch

    # 识别具体意图
    intent = "general"
    if is_standards:
        if any(kw in normalized for kw in ["时限", "多久", "几小时", "几天"]):
            intent = "time_limit"
        elif any(kw in normalized for kw in ["结案", "结案条件"]):
            intent = "close_condition"
        elif any(kw in normalized for kw in ["责任", "谁负责"]):
            intent = "responsibility"
        elif any(kw in normalized for kw in ["监管", "哪个部门"]):
            intent = "supervision"
        elif any(kw in normalized for kw in ["采集", "取证"]):
            intent = "collection"
        else:
            intent = "standards_general"

    return {
        "is_standards": is_standards,
        "is_dispatch": is_dispatch,
        "need_location": need_location,
        "intent": intent,
    }


def _need_location_for_dispatch(question: str) -> bool:
    """判断问题是否需要位置信息来判断部门归属"""
    normalized = normalize_cn_text(question)
    return any(normalize_cn_text(kw) in normalized for kw in DISPATCH_KEYWORDS)


# ==================== 统一问答 ====================

def unified_ask(
    question: str,
    location: Any = None,
    history: Optional[List[Dict]] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    统一问答入口

    Args:
        question: 用户问题
        location: 位置信息 {lng, lat} 或 None
        history: 对话历史
        top_k: 返回结果数量

    Returns:
        {
            "answer": str,
            "sources": list,
            "success": bool,
            "need_location": bool,  # 是否需要位置信息
            "message": str,        # 提示信息（当需要位置时）
        }
    """
    try:
        # 1. 预分析问题，提取关键信息
        pre_analysis = pre_analyze_question(question)
        print(f"[KB Unified] 预分析结果: {pre_analysis}")

        # 2. 分析意图
        intent = _analyze_intent(question)

        # 3. 对于投诉类问题，优先搜索作业管理相关标准
        normalized = normalize_cn_text(question)
        is_complaint = any(kw in normalized for kw in ["投诉", "举报", "导致", "希望", "赔偿"])
        is_operation_issue = any(kw in normalized for kw in [
            "作业", "清扫", "洒水", "环卫", "未设置警示", "警示标识",
            "未设置", "不规范", "作业车"
        ])

        if is_complaint and is_operation_issue:
            # 投诉+作业问题，优先搜索作业管理标准
            print("[KB Unified] 检测到作业类投诉，优先搜索作业管理标准")
            try:
                from case_standards import _search_by_case_type
                # 直接搜索作业车辆管理相关标准
                operation_results = _search_by_case_type("市容环境", "作业车辆管理", top_k=3)
                if operation_results:
                    # 使用立结案标准问答，但传入增强的搜索结果
                    result = ask_case_standard(
                        question, top_k=top_k, location=location, history=history
                    )
                    # 将作业管理结果放在最前面
                    if "sources" not in result:
                        result["sources"] = []
                    result["need_location"] = False
                    result["message"] = ""
                    result["pre_analysis"] = pre_analysis
                    return result
            except Exception as e:
                print(f"[KB Unified] 作业管理搜索失败: {e}")

        # 4. 根据意图选择检索策略
        if intent["is_standards"]:
            # 立结案标准问答
            result = ask_case_standard(
                question, top_k=top_k, location=location, history=history
            )
            result["need_location"] = False
            result["message"] = ""
            result["pre_analysis"] = pre_analysis
            return result
        else:
            # 通用知识问答
            result = general_ask(question, top_k=top_k)
            result["need_location"] = False
            result["message"] = ""
            result["pre_analysis"] = pre_analysis
            return result

    except Exception as e:
        print(f"[KB Unified] 问答失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "answer": f"问答失败: {str(e)}",
            "sources": [],
            "success": False,
            "need_location": False,
            "message": "",
        }


# ==================== 统一检索 ====================

def unified_search(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    统一检索：同时搜索两库，合并结果

    Args:
        query: 搜索关键词
        top_k: 每个库返回的最大结果数

    Returns:
        合并后的结果列表，按相关性排序
    """
    try:
        results = []

        # 1. 通用知识库搜索
        try:
            general_results = general_search(query, top_k=top_k)
            for r in general_results:
                r["source_type"] = "general"
                r["source_label"] = "通用知识库"
            results.extend(general_results)
        except Exception as e:
            print(f"[KB Unified] 通用知识库搜索失败: {e}")

        # 2. 立结案标准搜索
        try:
            standards_results = search_case_standards(query, top_k=top_k)
            for r in standards_results:
                r["source_type"] = "standards"
                r["source_label"] = "立结案标准库"
            results.extend(standards_results)
        except Exception as e:
            print(f"[KB Unified] 立结案标准搜索失败: {e}")

        # 3. 合并去重（按内容相似度）
        merged = _merge_results(results)

        return merged[:top_k]

    except Exception as e:
        print(f"[KB Unified] 搜索失败: {e}")
        return []


def _merge_results(results: List[Dict]) -> List[Dict]:
    """合并去重搜索结果"""
    if not results:
        return []

    # 按分数排序
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 简单去重：内容前50字相同则视为重复
    seen = set()
    merged = []
    for r in results:
        content = r.get("content", "") or r.get("child_text", "") or r.get("parent_text", "")
        key = content[:50] if content else ""
        if key and key not in seen:
            seen.add(key)
            merged.append(r)
        elif not key:
            merged.append(r)

    return merged


# ==================== 统计信息 ====================

def get_unified_stats() -> Dict[str, Any]:
    """获取两库的综合统计"""
    try:
        general = general_stats()
    except Exception as e:
        print(f"[KB Unified] 获取通用知识库统计失败: {e}")
        general = {"exists": False, "count": 0, "doc_count": 0}

    try:
        standards = get_case_standards_stats()
    except Exception as e:
        print(f"[KB Unified] 获取立结案标准库统计失败: {e}")
        standards = {"exists": False, "count": 0, "parents": 0, "children": 0}

    return {
        "general": general,
        "standards": standards,
        "total_vectors": general.get("count", 0) + standards.get("count", 0),
        "total_docs": general.get("doc_count", 0) + standards.get("parents", 0),
    }


# ==================== 数据迁移 ====================

def migrate_general_to_unified() -> Dict[str, Any]:
    """
    迁移通用知识库到统一向量库

    注意：目前两套系统使用相同的Milvus实例，但集合不同。
    此函数将通用知识库的文档重新索引到立结案标准库的集合中。
    """
    try:
        # 获取通用知识库的所有文档
        from backend.rag import list_documents, connect_milvus, COLLECTION_NAME
        from pymilvus import Collection, utility

        # 连接Milvus
        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return {"success": False, "message": "通用知识库集合不存在"}

        # 读取通用知识库的所有数据
        collection = Collection(COLLECTION_NAME)
        collection.load()

        # 查询所有数据
        results = collection.query(
            expr="id >= 0",
            output_fields=["doc_id", "content", "source", "embedding", "metadata"]
        )

        if not results:
            return {"success": True, "message": "通用知识库为空，无需迁移", "migrated": 0}

        # 将每个文档重新索引到立结案标准库
        migrated = 0
        failed = 0

        for r in results:
            try:
                content = r.get("content", "")
                source = r.get("source", "通用知识库")
                metadata = r.get("metadata", "{}")

                if not content:
                    continue

                # 使用通用知识库的索引方式插入
                from backend.rag import insert_document
                doc_id = f"migrated_{r.get('doc_id', '')}"
                result = insert_document(
                    doc_id=doc_id,
                    content=content,
                    source=source,
                    metadata={"migrated_from": "general", "original_source": source}
                )

                if result.get("success"):
                    migrated += 1
                else:
                    failed += 1
                    print(f"[KB Unified] 迁移文档失败: {result.get('message')}")

            except Exception as e:
                failed += 1
                print(f"[KB Unified] 迁移文档异常: {e}")

        return {
            "success": True,
            "message": f"迁移完成：成功 {migrated}，失败 {failed}",
            "migrated": migrated,
            "failed": failed,
        }

    except Exception as e:
        print(f"[KB Unified] 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


def get_migration_status() -> Dict[str, Any]:
    """获取迁移状态"""
    try:
        from backend.rag import list_documents, COLLECTION_NAME
        from pymilvus import utility, Collection

        # 检查通用知识库
        has_general = utility.has_collection(COLLECTION_NAME)
        general_count = 0
        if has_general:
            collection = Collection(COLLECTION_NAME)
            general_count = collection.num_entities

        # 检查立结案标准库
        from backend.case_standards import CASE_STANDARDS_COLLECTION
        has_standards = utility.has_collection(CASE_STANDARDS_COLLECTION)
        standards_count = 0
        if has_standards:
            collection = Collection(CASE_STANDARDS_COLLECTION)
            standards_count = collection.num_entities

        return {
            "general_exists": has_general,
            "general_count": general_count,
            "standards_exists": has_standards,
            "standards_count": standards_count,
        }

    except Exception as e:
        return {"error": str(e)}
