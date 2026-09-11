# -*- coding: utf-8 -*-
"""字典路由：大类/小类/立结案标准查询（供考核录入等使用）"""
import logging
from flask import request, jsonify
from sqlalchemy import text

logger = logging.getLogger(__name__)

try:
    from common import protected as _protected, admin_required as _admin_required
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required


def register_dict_routes(app, engine=None, protected=None, admin_required=None):
    protected = protected or _protected
    admin_required = admin_required or _admin_required

    @app.route('/api/dict/categories', methods=['GET'])
    @protected
    def dict_categories():
        """大类列表。可选 domain=part|event|service"""
        domain = (request.args.get('domain') or '').strip()
        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500
            sql = "SELECT id, domain, cat_code, cat_name, sort_order FROM dict_category"
            params = {}
            if domain:
                sql += " WHERE domain = :domain"
                params['domain'] = domain
            sql += " ORDER BY domain, sort_order, id"
            with engine.connect() as conn:
                rows = conn.execute(text(sql), params).fetchall()
            return jsonify({
                'success': True,
                'categories': [
                    {'id': r[0], 'domain': r[1], 'cat_code': r[2], 'cat_name': r[3], 'sort_order': r[4]}
                    for r in rows
                ],
            })
        except Exception as e:
            logger.error(f"获取大类字典失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/dict/subcategories', methods=['GET'])
    @protected
    def dict_subcategories():
        """小类列表。参数：category_id 或 domain，可选 q 模糊名"""
        category_id = (request.args.get('category_id') or '').strip()
        domain = (request.args.get('domain') or '').strip()
        q = (request.args.get('q') or '').strip()
        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500
            clauses = []
            params = {}
            if category_id:
                clauses.append('s.category_id = :category_id')
                params['category_id'] = int(category_id)
            if domain:
                clauses.append('s.domain = :domain')
                params['domain'] = domain
            if q:
                clauses.append('s.sub_name LIKE :q')
                params['q'] = f'%{q}%'
            where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
            sql = (
                "SELECT s.id, s.category_id, s.domain, s.sub_code, s.sub_name, s.is_active, "
                "c.cat_name, s.regulator, s.responsible, s.collect_note "
                "FROM dict_subcategory s "
                "LEFT JOIN dict_category c ON c.id = s.category_id"
                + where +
                " ORDER BY s.domain, s.sort_order, s.id LIMIT 500"
            )
            with engine.connect() as conn:
                rows = conn.execute(text(sql), params).fetchall()
            return jsonify({
                'success': True,
                'subcategories': [
                    {
                        'id': r[0], 'category_id': r[1], 'domain': r[2],
                        'sub_code': r[3], 'sub_name': r[4], 'is_active': r[5],
                        'cat_name': r[6],
                        'regulator': r[7] or '',
                        'responsible': r[8] or '',
                        'collect_note': r[9] or '',
                    }
                    for r in rows
                ],
            })
        except Exception as e:
            logger.error(f"获取小类字典失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/dict/standards', methods=['GET'])
    @protected
    def dict_standards():
        """按小类查立结案标准。参数：subcategory_id 或 sub_name。

        返回：
        - subcategory: 小类级（监管主体/责任主体/采集要求 只出现一次）
        - conditions: 多条立案条件（条件/时限/结案）
        """
        subcategory_id = (request.args.get('subcategory_id') or '').strip()
        sub_name = (request.args.get('sub_name') or '').strip()
        domain = (request.args.get('domain') or '').strip()
        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            # 先定位小类
            clauses = []
            params = {}
            if subcategory_id:
                clauses.append('s.id = :sid')
                params['sid'] = int(subcategory_id)
            if sub_name:
                clauses.append('s.sub_name = :sn')
                params['sn'] = sub_name
            if domain:
                clauses.append('s.domain = :domain')
                params['domain'] = domain
            if not clauses:
                return jsonify({'success': False, 'error': '请提供 subcategory_id 或 sub_name'}), 400

            sub_sql = (
                "SELECT s.id, s.category_id, s.domain, s.sub_code, s.sub_name, "
                "c.cat_name, s.regulator, s.responsible, s.collect_note, s.legal_basis "
                "FROM dict_subcategory s "
                "LEFT JOIN dict_category c ON c.id = s.category_id "
                "WHERE " + ' AND '.join(clauses) +
                " LIMIT 1"
            )
            with engine.connect() as conn:
                srow = conn.execute(text(sub_sql), params).fetchone()
                if not srow:
                    return jsonify({'success': False, 'error': '未找到小类'}), 404

                sub = {
                    'id': srow[0],
                    'category_id': srow[1],
                    'domain': srow[2],
                    'sub_code': srow[3],
                    'sub_name': srow[4],
                    'cat_name': srow[5],
                    'regulator': srow[6] or '',
                    'responsible': srow[7] or '',
                    'collect_note': srow[8] or '',
                    'legal_basis': srow[9] or '',
                }

                cond_sql = (
                    "SELECT cs.id, cs.condition_order, cs.case_condition, "
                    "cs.time_limit_text, cs.time_limit_hours, cs.close_condition, cs.source_sheet "
                    "FROM case_standard cs "
                    "WHERE cs.subcategory_id = :sid "
                    "ORDER BY cs.condition_order, cs.id"
                )
                crows = conn.execute(text(cond_sql), {'sid': sub['id']}).fetchall()

            conditions = []
            for r in crows:
                hours = float(r[4]) if r[4] is not None else None
                conditions.append({
                    'id': r[0],
                    'condition_order': r[1],
                    'case_condition': r[2] or '',
                    'time_limit_text': r[3] or '',
                    'time_limit_hours': hours,
                    'close_condition': r[4 + 1] or '',
                    'source_sheet': r[6] or '',
                })

            return jsonify({
                'success': True,
                'subcategory': sub,
                'conditions': conditions,
                # 兼容旧字段名
                'standards': conditions,
            })
        except Exception as e:
            logger.error(f"获取立结案标准失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
