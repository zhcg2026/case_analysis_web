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
