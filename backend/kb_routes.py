# -*- coding: utf-8 -*-
"""统一知识库路由模块"""
from flask import request, jsonify

try:
    from common import (
        protected as _protected, admin_required as _admin_required,
        unified_ask as _unified_ask, unified_search as _unified_search,
        get_unified_stats as _get_unified_stats,
        migrate_general_to_unified as _migrate_general_to_unified,
        get_migration_status as _get_migration_status,
    )
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required
    _unified_ask = _unified_search = _get_unified_stats = None
    _migrate_general_to_unified = _get_migration_status = None

def register_kb_routes(app, protected=None, admin_required=None, unified_ask=None, unified_search=None, get_unified_stats=None, migrate_general_to_unified=None, get_migration_status=None):
    protected = protected or _protected
    admin_required = admin_required or _admin_required
    unified_ask = unified_ask or _unified_ask
    unified_search = unified_search or _unified_search
    get_unified_stats = get_unified_stats or _get_unified_stats
    migrate_general_to_unified = migrate_general_to_unified or _migrate_general_to_unified
    get_migration_status = get_migration_status or _get_migration_status
    """注册统一知识库相关路由"""

    @app.route('/api/kb/ask', methods=['POST'])
    @protected
    def kb_unified_ask():
        """统一知识库问答"""
        try:
            data = request.get_json(silent=True) or {}
            question = data.get('question', '')
            location = data.get('location')
            history = data.get('history', [])
            top_k = data.get('top_k', 5)

            if not question:
                return jsonify({'error': '请提供问题'}), 400

            result = unified_ask(question, location, history, top_k)
            return jsonify(result), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/search', methods=['POST'])
    @protected
    def kb_unified_search():
        """统一知识库检索"""
        try:
            data = request.get_json(silent=True) or {}
            query = data.get('query', '')
            top_k = data.get('top_k', 10)

            if not query:
                return jsonify({'error': '请提供搜索内容'}), 400

            results = unified_search(query, top_k)
            return jsonify({'results': results, 'total': len(results)}), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/stats', methods=['GET'])
    @protected
    def kb_unified_stats():
        """获取统一知识库统计信息"""
        try:
            stats = get_unified_stats()
            return jsonify(stats), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/migrate', methods=['POST'])
    @admin_required
    def kb_unified_migrate():
        """迁移通用知识库到统一库"""
        try:
            result = migrate_general_to_unified()
            return jsonify(result), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/migration-status', methods=['GET'])
    @admin_required
    def kb_migration_status():
        """获取迁移状态"""
        try:
            status = get_migration_status()
            return jsonify(status), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
