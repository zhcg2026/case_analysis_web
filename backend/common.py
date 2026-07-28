# -*- coding: utf-8 -*-
"""集中导出常用依赖，供路由模块直接导入。"""
import os

# ==================== 工具函数 ====================
try:
    from backend.helpers import (
        protected, admin_required,
        get_json_payload,
        hash_password, verify_password, is_strong_password,
        check_login_attempts, record_failed_login, clear_login_attempts,
        generate_token, verify_token,
    )
except ImportError:
    from helpers import (
        protected, admin_required,
        get_json_payload,
        hash_password, verify_password, is_strong_password,
        check_login_attempts, record_failed_login, clear_login_attempts,
        generate_token, verify_token,
    )

# ==================== LLM 配置 ====================
API_KEY = os.getenv('ARK_API_KEY', '')
API_URL = os.getenv('ARK_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
MODEL = os.getenv('ARK_MODEL', 'doubao-seed-1-8-251228')

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
