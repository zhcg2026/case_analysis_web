# -*- coding: utf-8 -*-
"""文件资料路由 - 其他单位发给平台的文件/通知归集(台账管理-文件资料标签页)

条目=标题+类型标签+发文单位+文件日期+说明+多附件(JSON存储);
附件本体走既有 /api/upload/file 上传、/uploads/ 静态下载。
权限与台账模块一致:登录用户均可查看和维护(protected)。
"""
import json
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)


def register_notice_routes(app, Session, NoticeDoc, protected):

    def _parse_attachments(raw):
        try:
            data = json.loads(raw or '[]')
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _dict(r):
        return {
            'id': r.id,
            'title': r.title,
            'tag': r.tag,
            'source': r.source,
            'doc_date': r.doc_date.isoformat() if r.doc_date else None,
            'content': r.content,
            'attachments': _parse_attachments(r.attachments),
            'pinned': r.pinned or 0,
        }

    def _clean(data):
        title = (data.get('title') or '').strip()
        if not title:
            return None, '标题不能为空'
        doc_date = (data.get('doc_date') or '').strip() or None
        return {
            'title': title[:200],
            'tag': (data.get('tag') or '').strip()[:50] or None,
            'source': (data.get('source') or '').strip()[:100] or None,
            'doc_date': doc_date,
            'content': (data.get('content') or '').strip() or None,
            'attachments': json.dumps(data.get('attachments') or [], ensure_ascii=False)[:100000],
            'pinned': 1 if data.get('pinned') else 0,
        }, None

    @app.route('/api/notice-docs', methods=['GET'])
    @protected
    def notice_doc_list():
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            keyword = (request.args.get('keyword') or '').strip()
            tag = (request.args.get('tag') or '').strip()
            with Session() as session:
                q = session.query(NoticeDoc)
                if tag:
                    q = q.filter(NoticeDoc.tag == tag)
                if keyword:
                    like = f'%{keyword}%'
                    from sqlalchemy import or_
                    q = q.filter(or_(NoticeDoc.title.like(like),
                                     NoticeDoc.source.like(like),
                                     NoticeDoc.content.like(like)))
                rows = (q.order_by(NoticeDoc.pinned.desc(), NoticeDoc.doc_date.desc(), NoticeDoc.id.desc())
                        .all())
                docs = [_dict(r) for r in rows]
            return jsonify({'docs': docs, 'total': len(docs)})
        except Exception as e:
            logger.warning(f"获取文件资料失败: {e}")
            return jsonify({'error': '获取失败'}), 500

    @app.route('/api/notice-docs', methods=['POST'])
    @protected
    def notice_doc_create():
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            fields, err = _clean(request.get_json(silent=True) or {})
            if err:
                return jsonify({'error': err}), 400
            with Session() as session:
                row = NoticeDoc(**fields, created_by=getattr(request, 'user_id', None))
                session.add(row)
                session.commit()
                return jsonify({'message': '添加成功', 'doc': _dict(row)}), 201
        except Exception as e:
            logger.warning(f"添加文件资料失败: {e}")
            return jsonify({'error': '添加失败'}), 500

    @app.route('/api/notice-docs/<int:doc_id>', methods=['PUT'])
    @protected
    def notice_doc_update(doc_id):
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            fields, err = _clean(request.get_json(silent=True) or {})
            if err:
                return jsonify({'error': err}), 400
            with Session() as session:
                row = session.query(NoticeDoc).filter_by(id=doc_id).first()
                if not row:
                    return jsonify({'error': '记录不存在'}), 404
                for k, v in fields.items():
                    setattr(row, k, v)
                session.commit()
                return jsonify({'message': '更新成功', 'doc': _dict(row)})
        except Exception as e:
            logger.warning(f"更新文件资料失败: {e}")
            return jsonify({'error': '更新失败'}), 500

    @app.route('/api/notice-docs/<int:doc_id>', methods=['DELETE'])
    @protected
    def notice_doc_delete(doc_id):
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            with Session() as session:
                row = session.query(NoticeDoc).filter_by(id=doc_id).first()
                if not row:
                    return jsonify({'error': '记录不存在'}), 404
                session.delete(row)
                session.commit()
            return jsonify({'message': '删除成功'})
        except Exception as e:
            logger.warning(f"删除文件资料失败: {e}")
            return jsonify({'error': '删除失败'}), 500
