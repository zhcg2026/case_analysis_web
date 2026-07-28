"""
统一知识库入口模块
整合通用知识库 (rag.py) 和立结案标准库 (case_standards.py)

核心能力：
1. 统一问答：同时搜索两库，合并结果，LLM统一回答
2. 统一检索：同时搜索两库，合并结果
3. 统计信息：综合两库的统计
4. 数据迁移：通用知识库迁移到统一库
"""

import os
import re
from typing import List, Dict, Optional, Any

try:
    from kb_common import call_llm, connect_milvus, SCORE_WEIGHT_CORE, SCORE_WEIGHT_KEYWORD, SCORE_WEIGHT_VECTOR, SCORE_WEIGHT_FIELD
    from kb_synonyms import has_specific_facility
    from rag import (
        search_similar as general_search,
        ask_question as general_ask,
        get_collection_stats as general_stats,
        insert_document as general_insert,
    )
    from case_standards import (
        search_case_standards,
        ask_case_standard,
        get_case_standards_stats,
        match_department_dispatch,
        build_query_profile,
        normalize_cn_text,
        pre_analyze_question,
        find_all_matching_types,
        _group_types_by_category,
        _extract_answer_from_text,
        build_structured_intent_answer,
    )
except ImportError:
    from backend.kb_common import call_llm, connect_milvus, SCORE_WEIGHT_CORE, SCORE_WEIGHT_KEYWORD, SCORE_WEIGHT_VECTOR, SCORE_WEIGHT_FIELD
    from backend.kb_synonyms import has_specific_facility
    from backend.rag import (
        search_similar as general_search,
        ask_question as general_ask,
        get_collection_stats as general_stats,
        insert_document as general_insert,
    )
    from backend.case_standards import (
        search_case_standards,
        ask_case_standard,
        get_case_standards_stats,
        match_department_dispatch,
        build_query_profile,
        normalize_cn_text,
        pre_analyze_question,
        find_all_matching_types,
        _group_types_by_category,
        _extract_answer_from_text,
        build_structured_intent_answer,
    )


# ==================== 统一问答 ====================

def unified_ask(
    question: str,
    location: Any = None,
    history: Optional[List[Dict]] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    统一问答入口：同时搜两库 → 合并排序 → LLM统一回答

    不再做意图路由，LLM自己判断怎么回答。
    """
    try:
        # 1. 预分析问题，提取关键信息
        pre_analysis = pre_analyze_question(question)
        print(f"[KB Unified] 预分析结果: {pre_analysis}")

        # 2. 地理匹配（如果有位置信息）
        dispatch_info = None
        if location is not None:
            dispatch_result = match_department_dispatch(question, location, force_dispatch=True)
            if dispatch_result:
                dispatch_info = dispatch_result
                print(f"[KB Unified] 地理匹配: dept={dispatch_result.get('department')}, in_jurisdiction={dispatch_result.get('in_jurisdiction')}")

        # 3. 同时搜索两库
        general_results = []
        standards_results = []

        try:
            general_results = general_search(question, top_k=top_k)
            for r in general_results:
                r["source_type"] = "general"
                r["source_label"] = "通用知识库"
        except Exception as e:
            print(f"[KB Unified] 通用知识库搜索失败: {e}")

        try:
            standards_results = search_case_standards(question, top_k=top_k)
            for r in standards_results:
                r["source_type"] = "standards"
                r["source_label"] = "立结案标准库"
        except Exception as e:
            print(f"[KB Unified] 立结案标准库搜索失败: {e}")

        # 4. 合并结果
        all_results = _merge_and_rank(question, general_results, standards_results)

        # 5. 判断是否需要追问
        need_clarify, clarify_options = _check_need_clarify(question, all_results)

        # 6. 如果没有搜索结果
        if not all_results:
            return {
                "answer": "知识库中没有找到相关信息。",
                "sources": [],
                "success": True,
                "need_location": False,
                "message": "",
                "pre_analysis": pre_analysis,
            }

        # 7. 尝试结构化回答（强意图问题直接给答案）
        structured_answer = build_structured_intent_answer(question, standards_results)
        if structured_answer and not need_clarify:
            sources = [r.get("case_type", "") for r in standards_results[:3] if r.get("case_type")]
            return {
                "answer": structured_answer,
                "sources": list(dict.fromkeys(sources)),
                "success": True,
                "need_location": False,
                "message": "",
                "pre_analysis": pre_analysis,
            }

        # 8. 构建上下文，调用LLM统一回答
        context = _build_context(all_results)
        answer = _ask_llm_unified(question, context, history, dispatch_info, need_clarify, clarify_options)

        # 9. 收集来源
        sources = []
        for r in all_results:
            src = r.get("case_type") or r.get("source") or r.get("source_label", "")
            if src and src not in sources:
                sources.append(src)

        return {
            "answer": answer,
            "sources": sources[:5],
            "success": True,
            "need_location": False,
            "message": "",
            "pre_analysis": pre_analysis,
        }

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


def _merge_and_rank(question: str, general_results: List[Dict], standards_results: List[Dict]) -> List[Dict]:
    """合并两库结果，统一排序（分数归一化到[0,1]）"""
    all_results = []

    # 立结案标准库结果归一化
    # 标准库的score/final_score范围通常在0-1之间，但分布不均
    for r in standards_results:
        score = r.get("final_score", r.get("score", 0))
        # 归一化：标准库score通常在0.3-0.8之间，映射到0-1
        normalized_score = min(1.0, max(0.0, (score - 0.2) / 0.6)) if score > 0.2 else score * 0.5
        r["unified_score"] = min(1.0, normalized_score + 0.05)  # 微弱提权
        all_results.append(r)

    # 通用知识库结果归一化
    # 通用库的score通常是cosine similarity，范围0-1
    for r in general_results:
        score = r.get("score", 0)
        r["unified_score"] = score
        all_results.append(r)

    # 按统一分数排序
    all_results.sort(key=lambda x: x.get("unified_score", 0), reverse=True)

    # 去重
    seen = set()
    merged = []
    for r in all_results:
        content = r.get("content", "") or r.get("child_text", "") or r.get("parent_text", "")
        key = content[:50] if content else ""
        if key and key not in seen:
            seen.add(key)
            merged.append(r)
        elif not key:
            merged.append(r)

    return merged


def _check_need_clarify(question: str, results: List[Dict]) -> tuple:
    """
    统一追问逻辑：
    - 搜索结果≥3个不同案件类型 + 问题无具体设施词 → 追问
    """
    need_clarify = False
    clarify_options = []

    # 从搜索结果提取案件类型
    result_types = list(dict.fromkeys(
        r.get('case_type', '') for r in results
        if r.get('case_type') and r.get('source_type') == 'standards'
    ))

    if len(result_types) >= 3 and not has_specific_facility(question):
        need_clarify = True
        clarify_options = result_types
        return need_clarify, clarify_options

    # 也检查全局匹配
    all_matched = find_all_matching_types(question)
    type_groups = _group_types_by_category(all_matched)
    for category, subtypes in type_groups.items():
        if len(subtypes) > 10:
            need_clarify = True
            clarify_options = subtypes
            break

    return need_clarify, clarify_options


def _build_context(results: List[Dict]) -> str:
    """构建LLM上下文，合并两库结果（通用化处理）"""
    context_parts = []
    seen_types = set()

    for r in results:
        source_type = r.get("source_type", "")
        unified_score = r.get("unified_score", 0)

        if source_type == "standards":
            case_type = r.get("case_type", "")
            if case_type in seen_types:
                continue
            seen_types.add(case_type)
            parent_text = r.get("parent_text", "")
            child_text = r.get("child_text", "")

            # 提取meta_info中的关键信息
            meta_info = r.get("meta_info", {})
            time_limit = meta_info.get("time_limit", "")
            supervision = meta_info.get("supervision", "")
            responsibility = meta_info.get("responsibility", "")

            # 构建更丰富的上下文
            context_parts.append(f"【{case_type}】（立结案标准库，相关度: {unified_score:.2f}）")
            if parent_text:
                context_parts.append(f"标准内容：{parent_text}")
            if child_text:
                context_parts.append(f"详细说明：{child_text}")
            if supervision:
                context_parts.append(f"监管主体：{supervision}")
            if responsibility:
                context_parts.append(f"责任主体：{responsibility}")
            if time_limit:
                context_parts.append(f"处置时限：{time_limit}")

        elif source_type == "general":
            content = r.get("content", "")
            source = r.get("source", "未知")
            score = r.get("score", 0)
            if len(content) > 500:
                content = content[:500] + "..."

            # 根据来源类型判断内容类型
            content_type = "通用知识"
            if "法律" in source or "法规" in source:
                content_type = "法律法规"
            elif "职责" in source or "部门" in source:
                content_type = "职责划分"
            elif "考核" in source:
                content_type = "考核办法"
            elif "规章" in source or "制度" in source:
                content_type = "规章制度"

            context_parts.append(f"【{source}】（{content_type}，相关度: {score:.2f}）\n{content}")

    return "\n\n---\n\n".join(context_parts)


def _ask_llm_unified(
    question: str,
    context: str,
    history: list = None,
    dispatch_info: dict = None,
    need_clarify: bool = False,
    clarify_options: list = None,
) -> str:
    """精简的统一LLM Prompt"""

    history_text = ""
    if history:
        for msg in history[-4:]:
            role = "用户" if msg.get("role") == "user" else "助手"
            history_text += f"- {role}：{msg.get('content', '')}\n"

    geo_info = ""
    if dispatch_info:
        unit = dispatch_info.get("unit")
        department = dispatch_info.get("department", "")
        geo_info = f"""
## 地理定位结果
- 所属片区/单位：{unit if unit else '未匹配到具体片区'}
- 责任部门：{department if department else '未确定'}
注意：地理定位仅供参考，请根据参考标准中的案件类型判断该问题应由哪个部门负责。
"""

    prompt = f"""你是运城市城市管理局的资深专家。根据以下参考资料回答市民问题。

## 规则
1. **只用参考资料中的信息回答**，禁止编造或推测
2. **反幻觉约束**：如果参考资料中没有相关信息，明确说"知识库中暂无相关信息"，不要补充常识
3. **场景优先**：问题中的场景（绿化带、公园、道路等）是选择标准的关键依据
4. **本质优先**：识别问题本质，不被"建议""投诉"等表面词误导
5. **归属部门**：必须从参考标准的【监管主体】【责任主体】字段复制，不要自己编造
6. **笼统描述**（如"脏乱差""环境差"）必须追问具体类型
7. **根据问题类型调整回答风格**：
   - 法规咨询：引用具体条款，说明法律依据
   - 业务办理：说明办理流程、所需材料、注意事项
   - 权责所属：明确责任部门、监管主体
   - 问题投诉：给出处置建议、参考时限
8. **整合多个来源**：如果参考资料中有多个相关内容，整合成完整回答，注明来源

{f"## 可选子类型{chr(10)}请先让用户确认具体是哪种：{chr(10)}{chr(10).join('- ' + t for t in clarify_options[:15])}" if need_clarify and clarify_options else ""}{geo_info}
## 参考资料
{context}

{f"对话历史：{chr(10)}{history_text}" if history_text else ""}
市民问题：{question}

请简洁直接回答："""

    result = call_llm(prompt, timeout=120)
    if result:
        return result

    return "抱歉，处理您的问题时出现错误，请稍后重试。"


# ==================== 统一检索 ====================

def unified_search(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """统一检索：同时搜索两库，合并结果"""
    try:
        results = []

        try:
            general_results = general_search(query, top_k=top_k)
            for r in general_results:
                r["source_type"] = "general"
                r["source_label"] = "通用知识库"
            results.extend(general_results)
        except Exception as e:
            print(f"[KB Unified] 通用知识库搜索失败: {e}")

        try:
            standards_results = search_case_standards(query, top_k=top_k)
            for r in standards_results:
                r["source_type"] = "standards"
                r["source_label"] = "立结案标准库"
            results.extend(standards_results)
        except Exception as e:
            print(f"[KB Unified] 立结案标准库搜索失败: {e}")

        merged = _merge_results(results)
        return merged[:top_k]

    except Exception as e:
        print(f"[KB Unified] 搜索失败: {e}")
        return []


def _merge_results(results: List[Dict]) -> List[Dict]:
    """合并去重搜索结果"""
    if not results:
        return []

    results.sort(key=lambda x: x.get("score", 0), reverse=True)

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
    """迁移通用知识库到统一向量库"""
    try:
        from rag import list_documents, connect_milvus, COLLECTION_NAME
        from pymilvus import Collection, utility

        connect_milvus()

        if not utility.has_collection(COLLECTION_NAME):
            return {"success": False, "message": "通用知识库集合不存在"}

        collection = Collection(COLLECTION_NAME)
        collection.load()

        results = collection.query(
            expr="id >= 0",
            output_fields=["doc_id", "content", "source", "embedding", "metadata"]
        )

        if not results:
            return {"success": True, "message": "通用知识库为空，无需迁移", "migrated": 0}

        migrated = 0
        failed = 0

        for r in results:
            try:
                content = r.get("content", "")
                source = r.get("source", "通用知识库")
                metadata = r.get("metadata", "{}")

                if not content:
                    continue

                from rag import insert_document
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

            except Exception as e:
                failed += 1

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
        from rag import list_documents, COLLECTION_NAME
        from pymilvus import utility, Collection

        has_general = utility.has_collection(COLLECTION_NAME)
        general_count = 0
        if has_general:
            collection = Collection(COLLECTION_NAME)
            general_count = collection.num_entities

        from case_standards import CASE_STANDARDS_COLLECTION
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
