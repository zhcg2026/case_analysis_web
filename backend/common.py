# -*- coding: utf-8 -*-
"""
集中导出常用依赖，供路由模块直接导入。
各 routes 模块用法：
    from common import protected, admin_required, call_llm_api, ...
"""
import os

# ==================== 工具函数 ====================
try:
    from backend.helpers import (
        protected, admin_required,
        get_json_payload, get_case_or_404,
        call_llm_api,
        hash_password, verify_password, is_strong_password,
        check_login_attempts, record_failed_login, clear_login_attempts,
        generate_token, verify_token,
        generate_slug, convert_nan_to_null,
        desensitize_name, desensitize_phone, desensitize_landline, desensitize_address,
        extract_location_from_text, clean_problem_description, clean_and_desensitize_data,
    )
except ImportError:
    from helpers import (
        protected, admin_required,
        get_json_payload, get_case_or_404,
        call_llm_api,
        hash_password, verify_password, is_strong_password,
        check_login_attempts, record_failed_login, clear_login_attempts,
        generate_token, verify_token,
        generate_slug, convert_nan_to_null,
        desensitize_name, desensitize_phone, desensitize_landline, desensitize_address,
        extract_location_from_text, clean_problem_description, clean_and_desensitize_data,
    )

# ==================== 案件辅助函数 ====================
try:
    from backend.cases_helpers import (
        CASE_CATEGORIES, parse_pending_deadline, serialize_case,
        apply_case_category_fields,
    )
except ImportError:
    from cases_helpers import (
        CASE_CATEGORIES, parse_pending_deadline, serialize_case,
        apply_case_category_fields,
    )

# ==================== 评分函数 ====================
try:
    from backend.scoring import (
        calculate_law_enforcement_score, calculate_huanwei_score,
        calculate_garden_score, calculate_park_score, calculate_generic_score,
        calculate_law_enforcement_score_v2, calculate_huanwei_score_v2,
        calculate_garden_score_v2, calculate_park_score_v2,
    )
except ImportError:
    from scoring import (
        calculate_law_enforcement_score, calculate_huanwei_score,
        calculate_garden_score, calculate_park_score, calculate_generic_score,
        calculate_law_enforcement_score_v2, calculate_huanwei_score_v2,
        calculate_garden_score_v2, calculate_park_score_v2,
    )

# ==================== LLM 配置 ====================
API_KEY = os.getenv('ARK_API_KEY', '')
API_URL = os.getenv('ARK_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
MODEL = os.getenv('ARK_MODEL', 'doubao-seed-1-8-251228')

BAILIAN_GENERAL_API_KEY = os.getenv('BAILIAN_GENERAL_API_KEY', '')
BAILIAN_GENERAL_API_URL = os.getenv('BAILIAN_GENERAL_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
BAILIAN_GENERAL_MODEL = os.getenv('BAILIAN_GENERAL_MODEL', 'qwen-plus')

BAILIAN_CHENGGUANTONG_API_KEY = os.getenv('BAILIAN_CHENGGUANTONG_API_KEY', '')
BAILIAN_CHENGGUANTONG_API_URL = os.getenv('BAILIAN_CHENGGUANTONG_API_URL', 'https://dashscope.aliyuncs.com/api/v1/apps/b608e4ed05c44c19bf7e71679c859689/completion')

# ==================== 知识库辅助 ====================
try:
    from backend.rag import get_collection_stats, list_documents, delete_document, insert_document, search_similar, ask_question, init_rag
except ImportError:
    try:
        from rag import get_collection_stats, list_documents, delete_document, insert_document, search_similar, ask_question, init_rag
    except ImportError:
        get_collection_stats = list_documents = delete_document = None
        insert_document = search_similar = ask_question = init_rag = None

try:
    from backend.kb_unified import unified_ask, unified_search, get_unified_stats, migrate_general_to_unified, get_migration_status
except ImportError:
    try:
        from kb_unified import unified_ask, unified_search, get_unified_stats, migrate_general_to_unified, get_migration_status
    except ImportError:
        unified_ask = unified_search = get_unified_stats = None
        migrate_general_to_unified = get_migration_status = None
