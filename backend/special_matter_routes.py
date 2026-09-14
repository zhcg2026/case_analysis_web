# -*- coding: utf-8 -*-
"""特殊事项处置对照路由 - 大小类标准之外的特例清单(移交历史等原因"谁实际管")

案件归属页左侧面板纯展示;查看需登录,维护(增改删)仅 admin。
"""
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)


def register_special_matter_routes(app, Session, SpecialMatter, protected, admin_required):

    def _dict(r):
        return {
            'id': r.id,
            'matter': r.matter,
            'dept': r.dept,
            'contact': r.contact,
            'phone': r.phone,
            'note': r.note,
        }

    def _clean(data):
        matter = (data.get('matter') or '').strip()
        dept = (data.get('dept') or '').strip()
        if not matter:
            return None, '事项/路段不能为空'
        if not dept:
            return None, '处置部门不能为空'
        return {
            'matter': matter[:200],
            'dept': dept[:100],
            'contact': (data.get('contact') or '').strip()[:50] or None,
            'phone': (data.get('phone') or '').strip()[:30] or None,
            'note': (data.get('note') or '').strip()[:500] or None,
        }, None

    @app.route('/api/special-matters', methods=['GET'])
    @protected
    def special_matter_list():
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            with Session() as session:
                rows = session.query(SpecialMatter).order_by(SpecialMatter.id.desc()).all()
                matters = [_dict(r) for r in rows]
            return jsonify({'matters': matters})
        except Exception as e:
            logger.warning(f"获取特殊事项失败: {e}")
            return jsonify({'error': '获取失败'}), 500

    @app.route('/api/special-matters', methods=['POST'])
    @admin_required
    def special_matter_create():
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            data = request.get_json(silent=True) or {}
            fields, err = _clean(data)
            if err:
                return jsonify({'error': err}), 400
            with Session() as session:
                row = SpecialMatter(**fields, created_by=getattr(request, 'user_id', None))
                session.add(row)
                session.commit()
                return jsonify({'message': '添加成功', 'matter': _dict(row)}), 201
        except Exception as e:
            logger.warning(f"添加特殊事项失败: {e}")
            return jsonify({'error': '添加失败'}), 500

    @app.route('/api/special-matters/<int:matter_id>', methods=['PUT'])
    @admin_required
    def special_matter_update(matter_id):
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            data = request.get_json(silent=True) or {}
            fields, err = _clean(data)
            if err:
                return jsonify({'error': err}), 400
            with Session() as session:
                row = session.query(SpecialMatter).filter_by(id=matter_id).first()
                if not row:
                    return jsonify({'error': '记录不存在'}), 404
                for k, v in fields.items():
                    setattr(row, k, v)
                session.commit()
                return jsonify({'message': '更新成功', 'matter': _dict(row)})
        except Exception as e:
            logger.warning(f"更新特殊事项失败: {e}")
            return jsonify({'error': '更新失败'}), 500

    @app.route('/api/special-matters/<int:matter_id>', methods=['DELETE'])
    @admin_required
    def special_matter_delete(matter_id):
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            with Session() as session:
                row = session.query(SpecialMatter).filter_by(id=matter_id).first()
                if not row:
                    return jsonify({'error': '记录不存在'}), 404
                session.delete(row)
                session.commit()
            return jsonify({'message': '删除成功'})
        except Exception as e:
            logger.warning(f"删除特殊事项失败: {e}")
            return jsonify({'error': '删除失败'}), 500
