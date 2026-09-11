# -*- coding: utf-8 -*-
"""
dispatch_routes.py —— 案件归属判断 API 路由
=============================================
POST /api/dispatch/query   - 归属查询（案件类型+坐标 → 处置单位）
GET  /api/dispatch/types   - 案件类型列表（优先读 dict_subcategory 大小类）
"""
import logging
from typing import Any, Dict, List, Optional

from flask import request, jsonify
from sqlalchemy import text

try:
    from common import protected as _protected
except ImportError:
    from helpers import protected as _protected

logger = logging.getLogger(__name__)

DOMAIN_LABEL = {
    'part': '部件',
    'event': '事件',
    'service': '服务事项',
}


def _fallback_types():
    try:
        from dispatch_engine import get_case_types, get_case_categories
        return get_case_types(), get_case_categories()
    except Exception:
        return [], []


def load_types_from_db(engine) -> Optional[Dict[str, Any]]:
    """从 dict_category / dict_subcategory 读取案件类型列表"""
    if not engine:
        return None
    with engine.connect() as conn:
        exists = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'dict_subcategory'"
        )).scalar()
        if not exists:
            return None
        rows = conn.execute(text("""
            SELECT s.id, s.sub_name, s.domain, COALESCE(c.cat_name, '未分类'),
                   s.responsible, s.regulator
            FROM dict_subcategory s
            LEFT JOIN dict_category c ON c.id = s.category_id
            WHERE s.is_active = 1
            ORDER BY s.domain, c.sort_order, s.sort_order, s.id
        """)).fetchall()

    types = []
    cat_order = []
    seen_cats = set()
    for r in rows:
        sub_id, sub_name, domain, cat_name, responsible, regulator = r
        # 防同名大类跨域冲突
        domain_lbl = DOMAIN_LABEL.get(domain, domain or '')
        cat_key = f"{domain}|{cat_name}"
        if cat_key not in seen_cats:
            seen_cats.add(cat_key)
            cat_order.append({
                'name': cat_name,
                'domain': domain,
                'domain_label': domain_lbl,
                'key': cat_key,
            })
        types.append({
            'id': f'sub:{sub_id}',
            'name': sub_name,
            'category': cat_name,
            'category_key': cat_key,
            'domain': domain,
            'domain_label': domain_lbl,
            'responsible': responsible or '',
            'regulator': regulator or '',
            'source': 'dict',
        })
    return {
        'types': types,
        'categories': cat_order,
    }


def resolve_case_type(case_type_id: str, engine=None) -> Optional[Dict[str, Any]]:
    """case_type_id 可为 sub:123 或旧式硬编码 id"""
    if not case_type_id:
        return None
    # 字典小类
    if str(case_type_id).startswith('sub:'):
        sub_id = str(case_type_id)[4:]
        if engine:
            try:
                with engine.connect() as conn:
                    row = conn.execute(text("""
                        SELECT s.id, s.sub_name, s.domain, COALESCE(c.cat_name, '未分类'),
                               s.responsible, s.regulator
                        FROM dict_subcategory s
                        LEFT JOIN dict_category c ON c.id = s.category_id
                        WHERE s.id = :id
                        LIMIT 1
                    """), {'id': int(sub_id)}).fetchone()
                if row:
                    return {
                        'id': f'sub:{row[0]}',
                        'name': row[1],
                        'category': row[3],
                        'domain': row[2],
                        'responsible': row[4] or '',
                        'regulator': row[5] or '',
                        'department': None,  # 由调用方 resolve
                    }
            except Exception as e:
                logger.warning(f'解析字典小类失败: {e}')
        return None
    # 兼容旧 CASE_TYPES
    from dispatch_engine import CASE_TYPES
    return next((ct for ct in CASE_TYPES if ct['id'] == case_type_id), None)


def register_dispatch_routes(app, protected=None, engine=None):
    """注册案件归属判断路由"""
    protected = protected or _protected

    @app.route('/api/dispatch/query', methods=['POST'])
    @protected
    def dispatch_query():
        try:
            from dispatch_engine import dispatch, resolve_department
            data = request.get_json(force=True, silent=True) or {}
            case_type_id = data.get('case_type_id')
            question = (data.get('question') or '').strip()
            location = data.get('location')

            if not case_type_id and not question:
                return jsonify({'error': '请选择案件类型或输入问题描述'}), 400

            # 预解析字典小类，把责任主体映射为部门
            ct = resolve_case_type(case_type_id, engine=engine) if case_type_id else None
            expected_dept = None
            if ct and ct.get('responsible'):
                expected_dept = resolve_department(ct['responsible'])
                if not expected_dept and ct.get('name'):
                    expected_dept = resolve_department(ct['name'])

            result = dispatch(
                case_type_id=case_type_id,
                question=question,
                location=location,
                case_type_info=ct,
                expected_department=expected_dept,
            )
            return jsonify(result), 200
        except Exception as e:
            logger.exception("dispatch query error")
            return jsonify({'error': '归属判断失败'}), 500

    @app.route('/api/dispatch/types', methods=['GET'])
    @protected
    def dispatch_types():
        try:
            data = load_types_from_db(engine)
            if data is None or not data.get('types'):
                types, cats = _fallback_types()
                return jsonify({'types': types, 'categories': cats, 'source': 'fallback'}), 200
            return jsonify({**data, 'source': 'dict'}), 200
        except Exception as e:
            logger.exception("dispatch types error")
            return jsonify({'error': '获取案件类型失败'}), 500
