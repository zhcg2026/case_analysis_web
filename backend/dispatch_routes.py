# -*- coding: utf-8 -*-
"""
dispatch_routes.py —— 案件归属判断 API 路由
=============================================
提供两个接口：
  POST /api/dispatch/query   - 归属查询（案件类型+坐标 → 处置单位）
  GET  /api/dispatch/types   - 案件类型列表（供前端下拉选择）
"""
import logging
from flask import request, jsonify

try:
    from common import protected as _protected
except ImportError:
    from helpers import protected as _protected

logger = logging.getLogger(__name__)


def register_dispatch_routes(app, protected=None):
    """注册案件归属判断路由"""
    protected = protected or _protected

    @app.route('/api/dispatch/query', methods=['POST'])
    @protected
    def dispatch_query():
        """归属查询：根据案件类型/问题描述 + 坐标，返回处置单位"""
        try:
            from dispatch_engine import dispatch
            data = request.get_json(force=True, silent=True) or {}
            case_type_id = data.get('case_type_id')
            question = (data.get('question') or '').strip()
            location = data.get('location')

            if not case_type_id and not question:
                return jsonify({'error': '请选择案件类型或输入问题描述'}), 400

            result = dispatch(
                case_type_id=case_type_id,
                question=question,
                location=location,
            )
            return jsonify(result), 200
        except Exception as e:
            logger.exception("dispatch query error")
            return jsonify({'error': '归属判断失败'}), 500

    @app.route('/api/dispatch/types', methods=['GET'])
    @protected
    def dispatch_types():
        """返回案件类型列表和大类列表"""
        try:
            from dispatch_engine import get_case_types, get_case_categories
            return jsonify({
                'types': get_case_types(),
                'categories': get_case_categories(),
            }), 200
        except Exception as e:
            logger.exception("dispatch types error")
            return jsonify({'error': '获取案件类型失败'}), 500
