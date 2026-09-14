# -*- coding: utf-8 -*-
"""值班记录路由 - 白班(系统运行统计+关注问题) / 夜班(12345/市民来电事件流水)

数据结构:
- duty_records 一天两条, (record_date, shift) 唯一; 夜班跨天事件按值班开始日期归档;
- duty_record_events 白班"关注问题"与夜班"12345/市民来电"事件共用, 时间线JSON存事件内;
- 系统运行统计为手动填报(案件库按月导入, 日粒度对不上, 不做自动带出)。
权限: 登录用户可填报; 修改/删除限定 记录创建人 或 admin。
"""
import re
import io
import json
import datetime
import logging
from flask import request, jsonify, send_file

try:
    from backend.duty_record_export import build_shift_doc, build_month_doc, MIMETYPE
except ImportError:
    from duty_record_export import build_shift_doc, build_month_doc, MIMETYPE

logger = logging.getLogger(__name__)

SHIFTS = ('白班', '夜班')
EVENT_CATEGORIES = ('12345', '市民来电', '关注问题')
# 白班统计字段(与 duty_records 列一一对应)
STAT_FIELDS = ('stat_reported', 'stat_accepted', 'stat_completed',
               'src_collector', 'src_patrol', 'src_12345', 'src_minhu',
               'src_video', 'src_ai', 'src_public')


def _to_int(v):
    if v is None or v == '':
        return None
    try:
        i = int(v)
        return max(0, min(i, 10 ** 7))
    except (TypeError, ValueError):
        return None


def _clean_events(events):
    """清洗提交的事件列表; 返回[(字段dict, timeline_list)]"""
    result = []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        category = (e.get('category') or '').strip()
        if category not in EVENT_CATEGORIES:
            continue
        timeline = []
        for t in e.get('timeline') or []:
            if not isinstance(t, dict):
                continue
            time_s = (t.get('time') or '').strip()
            text = (t.get('text') or '').strip()
            if not time_s and not text:
                continue
            m = re.match(r'^(\d{1,2})[:：](\d{1,2})', time_s)
            if m:
                time_s = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
            timeline.append({'time': time_s[:5], 'text': text[:500]})
        fields = {
            'category': category,
            'ticket_no': (e.get('ticket_no') or '').strip()[:50] or None,
            'caller_name': (e.get('caller_name') or '').strip()[:50] or None,
            'caller_phone': (e.get('caller_phone') or '').strip()[:30] or None,
            'location': (e.get('location') or '').strip()[:200] or None,
            'description': (e.get('description') or '').strip() or None,
            'result': (e.get('result') or '').strip() or None,
        }
        result.append((fields, timeline))
    return result[:100]  # 单条记录事件上限, 防误提交超大payload


def register_duty_record_routes(app, Session, DutyRecord, DutyRecordEvent, protected, admin_required):

    def _timeline_parse(raw):
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _record_dict(session, r, with_events=True):
        d = {
            'id': r.id,
            'date': r.record_date.isoformat() if r.record_date else None,
            'shift': r.shift,
            'members': r.members,
            'is_normal': r.is_normal or 0,
            'note': r.note,
            'created_by': r.created_by,
            'can_edit': (r.created_by is None or r.created_by == getattr(request, 'user_id', None)
                         or getattr(request, 'role', '') == 'admin'),
            'stats': {f: getattr(r, f) for f in STAT_FIELDS},
        }
        if with_events:
            evs = (session.query(DutyRecordEvent)
                   .filter_by(record_id=r.id)
                   .order_by(DutyRecordEvent.sort_order, DutyRecordEvent.id)
                   .all())
            d['events'] = [{
                'id': ev.id,
                'category': ev.category,
                'ticket_no': ev.ticket_no,
                'caller_name': ev.caller_name,
                'caller_phone': ev.caller_phone,
                'location': ev.location,
                'description': ev.description,
                'timeline': _timeline_parse(ev.timeline),
                'result': ev.result,
            } for ev in evs]
        return d

    def _parse_date(s, default=None):
        try:
            return datetime.date.fromisoformat((s or '').strip())
        except (TypeError, ValueError):
            return default

    @app.route('/api/duty-record/month', methods=['GET'])
    @protected
    def duty_record_month():
        """某月全部值班记录(月历+当月数据分析用)"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            month = (request.args.get('month') or datetime.date.today().strftime('%Y-%m')).strip()
            try:
                year, mon = int(month[:4]), int(month[5:7])
                first = datetime.date(year, mon, 1)
            except (TypeError, ValueError):
                return jsonify({'error': '月份格式应为 YYYY-MM'}), 400
            last = (datetime.date(year + (mon == 12), (mon % 12) + 1, 1) - datetime.timedelta(days=1))
            with Session() as session:
                recs = (session.query(DutyRecord)
                        .filter(DutyRecord.record_date >= first, DutyRecord.record_date <= last)
                        .order_by(DutyRecord.record_date, DutyRecord.id)
                        .all())
                records = [_record_dict(session, r) for r in recs]
            return jsonify({'month': f'{year:04d}-{mon:02d}', 'records': records})
        except Exception as e:
            logger.warning(f"查询值班记录月数据失败: {e}")
            return jsonify({'error': '查询失败'}), 500

    @app.route('/api/duty-record/day', methods=['GET'])
    @protected
    def duty_record_day():
        """某日两条班次记录(含事件)"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            d = _parse_date(request.args.get('date'))
            if d is None:
                return jsonify({'error': '日期无效'}), 400
            with Session() as session:
                recs = (session.query(DutyRecord)
                        .filter(DutyRecord.record_date == d)
                        .order_by(DutyRecord.id)
                        .all())
                records = [_record_dict(session, r) for r in recs]
            return jsonify({'date': d.isoformat(), 'records': records})
        except Exception as e:
            logger.warning(f"查询值班记录失败: {e}")
            return jsonify({'error': '查询失败'}), 500

    @app.route('/api/duty-record/status', methods=['GET'])
    @protected
    def duty_record_status():
        """某日填写状态+当日白班统计+当月汇总（首页值班数据块用, 轻量）"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            d = _parse_date(request.args.get('date'), datetime.date.today())
            first = datetime.date(d.year, d.month, 1)
            last = (datetime.date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
                    - datetime.timedelta(days=1))
            with Session() as session:
                recs = session.query(DutyRecord).filter(DutyRecord.record_date == d).all()
                by_shift = {r.shift: r for r in recs}

                def _st(shift):
                    r = by_shift.get(shift)
                    if not r:
                        return {'filled': False, 'is_normal': 0, 'stats': None}
                    return {'filled': True, 'is_normal': r.is_normal or 0,
                            'stats': {f: getattr(r, f) for f in STAT_FIELDS}}

                month_recs = (session.query(DutyRecord)
                              .filter(DutyRecord.record_date >= first, DutyRecord.record_date <= last,
                                      DutyRecord.shift == '白班')
                              .all())
                month_sums = {
                    'reported': sum(r.stat_reported or 0 for r in month_recs),
                    'accepted': sum(r.stat_accepted or 0 for r in month_recs),
                    'completed': sum(r.stat_completed or 0 for r in month_recs),
                }

            return jsonify({'date': d.isoformat(),
                            '白班': _st('白班'), '夜班': _st('夜班'),
                            'month_sums': month_sums})
        except Exception as e:
            logger.warning(f"查询值班记录状态失败: {e}")
            return jsonify({'error': '查询失败'}), 500

    @app.route('/api/duty-record', methods=['POST'])
    @protected
    def duty_record_save():
        """填报/修改一条班次记录(upsert by 日期+班次); 事件全量重建"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            data = request.get_json(silent=True) or {}
            d = _parse_date(data.get('date'))
            if d is None:
                return jsonify({'error': '日期无效'}), 400
            shift = (data.get('shift') or '').strip()
            if shift not in SHIFTS:
                return jsonify({'error': '班次应为 白班/夜班'}), 400

            user_id = getattr(request, 'user_id', None)
            role = getattr(request, 'role', '')
            with Session() as session:
                rec = session.query(DutyRecord).filter_by(record_date=d, shift=shift).first()
                if rec and rec.created_by not in (None, user_id) and role != 'admin':
                    return jsonify({'error': '只有记录创建人或管理员可以修改'}), 403
                if not rec:
                    rec = DutyRecord(record_date=d, shift=shift, created_by=user_id)
                    session.add(rec)

                rec.members = (data.get('members') or '').strip()[:500] or None
                rec.is_normal = 1 if (shift == '夜班' and data.get('is_normal')) else 0
                rec.note = (data.get('note') or '').strip() or None
                stats = data.get('stats') or {}
                for f in STAT_FIELDS:
                    setattr(rec, f, _to_int(stats.get(f)))
                session.flush()

                session.query(DutyRecordEvent).filter_by(record_id=rec.id).delete()
                if not rec.is_normal:
                    for i, (fields, timeline) in enumerate(_clean_events(data.get('events'))):
                        session.add(DutyRecordEvent(
                            record_id=rec.id,
                            sort_order=i,
                            timeline=json.dumps(timeline, ensure_ascii=False) if timeline else None,
                            **fields,
                        ))
                session.commit()
                return jsonify({'success': True, 'record': _record_dict(session, rec)})
        except Exception as e:
            logger.warning(f"保存值班记录失败: {e}")
            return jsonify({'error': '保存失败'}), 500

    @app.route('/api/duty-record/export', methods=['GET'])
    @protected
    def duty_record_export():
        """导出 Word：?date=YYYY-MM-DD&shift=白班/夜班 → 单日单班次；?month=YYYY-MM → 整月"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            month_arg = (request.args.get('month') or '').strip()
            shift = (request.args.get('shift') or '').strip()

            def _events_for(session, rec):
                evs = (session.query(DutyRecordEvent)
                       .filter_by(record_id=rec.id)
                       .order_by(DutyRecordEvent.sort_order, DutyRecordEvent.id)
                       .all())
                return [{'category': ev.category, 'ticket_no': ev.ticket_no,
                         'caller_name': ev.caller_name, 'caller_phone': ev.caller_phone,
                         'location': ev.location, 'description': ev.description,
                         'timeline': _timeline_parse(ev.timeline), 'result': ev.result}
                        for ev in evs]

            if month_arg:
                try:
                    year, mon = int(month_arg[:4]), int(month_arg[5:7])
                except (TypeError, ValueError):
                    return jsonify({'error': '月份格式应为 YYYY-MM'}), 400
                first = datetime.date(year, mon, 1)
                last = (datetime.date(year + (mon == 12), (mon % 12) + 1, 1)
                        - datetime.timedelta(days=1))
                with Session() as session:
                    recs = (session.query(DutyRecord)
                            .filter(DutyRecord.record_date >= first, DutyRecord.record_date <= last)
                            .order_by(DutyRecord.record_date, DutyRecord.id)
                            .all())
                    if not recs:
                        return jsonify({'error': '该月暂无值班记录'}), 404
                    day_records = [(r.record_date, r.shift, r, _events_for(session, r)) for r in recs]
                doc_bytes = build_month_doc(year, mon, day_records)
                filename = f'值班记录_{year}年{mon}月.docx'
            else:
                d = _parse_date(request.args.get('date'))
                if d is None:
                    return jsonify({'error': '日期无效'}), 400
                if shift not in SHIFTS:
                    return jsonify({'error': '班次应为 白班/夜班'}), 400
                with Session() as session:
                    rec = session.query(DutyRecord).filter_by(record_date=d, shift=shift).first()
                    if not rec:
                        return jsonify({'error': f'该日{shift}暂无值班记录'}), 404
                    events = _events_for(session, rec)
                doc_bytes = build_shift_doc(d, shift, rec, events)
                filename = f'值班记录_{shift}_{d.isoformat()}.docx'

            resp = send_file(io.BytesIO(doc_bytes), as_attachment=True,
                             download_name=filename, mimetype=MIMETYPE)
            return resp
        except Exception as e:
            logger.warning(f"导出值班记录失败: {e}")
            return jsonify({'error': '导出失败'}), 500

    @app.route('/api/duty-record/<int:record_id>', methods=['DELETE'])
    @admin_required
    def duty_record_delete(record_id):
        """删除一条班次记录(含事件), 仅管理员"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            with Session() as session:
                rec = session.query(DutyRecord).filter_by(id=record_id).first()
                if not rec:
                    return jsonify({'error': '记录不存在'}), 404
                session.query(DutyRecordEvent).filter_by(record_id=rec.id).delete()
                session.delete(rec)
                session.commit()
            return jsonify({'message': '删除成功'})
        except Exception as e:
            logger.warning(f"删除值班记录失败: {e}")
            return jsonify({'error': '删除失败'}), 500
