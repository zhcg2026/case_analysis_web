# -*- coding: utf-8 -*-
"""台账扩展：外单位调取监控 + 无人机飞行登记"""
from datetime import datetime
import logging
from flask import request, jsonify
from helpers import protected

logger = logging.getLogger(__name__)


def _dt(s):
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    s = str(s).strip().replace('T', ' ')
    if '.' in s:
        s = s.split('.')[0]
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _fmt(v):
    if isinstance(v, datetime):
        return v.strftime('%Y-%m-%d %H:%M:%S')
    return v


def register_ledger_extra_routes(app, Session, MonitorAccessLedger, DroneFlightLedger, SystemConfig, protected=protected):
    # ========== 外单位调取监控 ==========

    @app.route('/api/ledger/monitor-access', methods=['GET'])
    @protected
    def monitor_access_list():
        session = Session()
        try:
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('pageSize', 20, type=int)
            keyword = request.args.get('keyword', '').strip()
            status = request.args.get('status', '').strip()
            q = session.query(MonitorAccessLedger)
            if keyword:
                like = f'%{keyword}%'
                q = q.filter(
                    (MonitorAccessLedger.unit_name.like(like)) |
                    (MonitorAccessLedger.visitor_name.like(like)) |
                    (MonitorAccessLedger.purpose.like(like)) |
                    (MonitorAccessLedger.video_location.like(like))
                )
            if status:
                q = q.filter(MonitorAccessLedger.status == status)
            total = q.count()
            items = q.order_by(MonitorAccessLedger.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
            data = [{
                'id': i.id,
                'unit_name': i.unit_name,
                'visitor_name': i.visitor_name,
                'id_type': i.id_type,
                'id_no': i.id_no,
                'has_intro_letter': int(i.has_intro_letter or 0),
                'visit_time': _fmt(i.visit_time),
                'purpose': i.purpose,
                'video_location': i.video_location,
                'video_time_range': i.video_time_range,
                'has_application': int(i.has_application or 0),
                'leader_signed': int(i.leader_signed or 0),
                'operator': i.operator,
                'status': i.status,
                'notes': i.notes,
            } for i in items]
            return jsonify({'success': True, 'data': data, 'total': total})
        except Exception as e:
            logger.exception('monitor_access_list')
            return jsonify({'error': '加载失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/monitor-access', methods=['POST'])
    @protected
    def monitor_access_create():
        session = Session()
        try:
            d = request.get_json(silent=True) or {}
            if not (d.get('unit_name') or '').strip():
                return jsonify({'error': '请填写外单位名称'}), 400
            if not (d.get('visitor_name') or '').strip():
                return jsonify({'error': '请填写来访人'}), 400
            item = MonitorAccessLedger(
                unit_name=d['unit_name'].strip(),
                visitor_name=d['visitor_name'].strip(),
                id_type=(d.get('id_type') or '').strip() or None,
                id_no=(d.get('id_no') or '').strip() or None,
                has_intro_letter=1 if d.get('has_intro_letter') else 0,
                visit_time=_dt(d.get('visit_time')),
                purpose=d.get('purpose'),
                video_location=(d.get('video_location') or '').strip() or None,
                video_time_range=(d.get('video_time_range') or '').strip() or None,
                has_application=1 if d.get('has_application') else 0,
                leader_signed=1 if d.get('leader_signed') else 0,
                operator=(d.get('operator') or '').strip() or None,
                status=(d.get('status') or '接待中').strip() or '接待中',
                notes=d.get('notes'),
                created_by=getattr(request, 'user_id', None),
            )
            session.add(item)
            session.commit()
            return jsonify({'success': True, 'id': item.id}), 201
        except Exception as e:
            session.rollback()
            logger.exception('monitor_access_create')
            return jsonify({'error': '保存失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/monitor-access/<int:item_id>', methods=['PUT'])
    @protected
    def monitor_access_update(item_id):
        session = Session()
        try:
            item = session.query(MonitorAccessLedger).filter_by(id=item_id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404
            d = request.get_json(silent=True) or {}
            if 'unit_name' in d:
                item.unit_name = (d.get('unit_name') or '').strip()
            if 'visitor_name' in d:
                item.visitor_name = (d.get('visitor_name') or '').strip()
            if 'id_type' in d:
                item.id_type = (d.get('id_type') or '').strip() or None
            if 'id_no' in d:
                item.id_no = (d.get('id_no') or '').strip() or None
            if 'has_intro_letter' in d:
                item.has_intro_letter = 1 if d.get('has_intro_letter') else 0
            if 'visit_time' in d:
                item.visit_time = _dt(d.get('visit_time'))
            if 'purpose' in d:
                item.purpose = d.get('purpose')
            if 'video_location' in d:
                item.video_location = (d.get('video_location') or '').strip() or None
            if 'video_time_range' in d:
                item.video_time_range = (d.get('video_time_range') or '').strip() or None
            if 'has_application' in d:
                item.has_application = 1 if d.get('has_application') else 0
            if 'leader_signed' in d:
                item.leader_signed = 1 if d.get('leader_signed') else 0
            if 'operator' in d:
                item.operator = (d.get('operator') or '').strip() or None
            if 'status' in d:
                item.status = (d.get('status') or '').strip() or item.status
            if 'notes' in d:
                item.notes = d.get('notes')
            session.commit()
            return jsonify({'success': True})
        except Exception as e:
            session.rollback()
            logger.exception('monitor_access_update')
            return jsonify({'error': '保存失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/monitor-access/<int:item_id>', methods=['DELETE'])
    @protected
    def monitor_access_delete(item_id):
        session = Session()
        try:
            item = session.query(MonitorAccessLedger).filter_by(id=item_id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404
            session.delete(item)
            session.commit()
            return jsonify({'success': True})
        except Exception:
            session.rollback()
            logger.exception('monitor_access_delete')
            return jsonify({'error': '删除失败'}), 500
        finally:
            session.close()

    # ========== 无人机飞行登记 ==========

    @app.route('/api/ledger/drone-equipment', methods=['GET'])
    @protected
    def drone_equipment_get():
        session = Session()
        try:
            model = session.query(SystemConfig).filter_by(config_key='drone_model').first()
            keeper = session.query(SystemConfig).filter_by(config_key='drone_keeper').first()
            return jsonify({
                'success': True,
                'drone_model': (model.config_value if model else '') or '',
                'keeper': (keeper.config_value if keeper else '') or '',
            })
        except Exception:
            logger.exception('drone_equipment_get')
            return jsonify({'error': '加载失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/drone-equipment', methods=['POST'])
    @protected
    def drone_equipment_put():
        session = Session()
        try:
            d = request.get_json(silent=True) or {}
            for key in ('drone_model', 'drone_keeper'):
                val = (d.get(key) or '').strip()
                row = session.query(SystemConfig).filter_by(config_key=key).first()
                if row:
                    row.config_value = val
                else:
                    session.add(SystemConfig(config_key=key, config_value=val))
            session.commit()
            return jsonify({'success': True})
        except Exception:
            session.rollback()
            logger.exception('drone_equipment_put')
            return jsonify({'error': '保存失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/drone', methods=['GET'])
    @protected
    def drone_list():
        session = Session()
        try:
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('pageSize', 20, type=int)
            keyword = request.args.get('keyword', '').strip()
            status = request.args.get('status', '').strip()
            q = session.query(DroneFlightLedger)
            if keyword:
                like = f'%{keyword}%'
                q = q.filter(
                    (DroneFlightLedger.location.like(like)) |
                    (DroneFlightLedger.purpose.like(like)) |
                    (DroneFlightLedger.applicant.like(like)) |
                    (DroneFlightLedger.approver.like(like))
                )
            if status:
                q = q.filter(DroneFlightLedger.status == status)
            total = q.count()
            items = q.order_by(DroneFlightLedger.flight_date.desc(), DroneFlightLedger.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
            data = [{
                'id': i.id,
                'flight_date': i.flight_date.strftime('%Y-%m-%d') if i.flight_date else None,
                'location': i.location,
                'purpose': i.purpose,
                'start_time': _fmt(i.start_time),
                'end_time': _fmt(i.end_time),
                'applicant': i.applicant,
                'approver': i.approver,
                'drone_model': i.drone_model,
                'keeper': i.keeper,
                'status': i.status,
                'notes': i.notes,
            } for i in items]
            return jsonify({'success': True, 'data': data, 'total': total})
        except Exception:
            logger.exception('drone_list')
            return jsonify({'error': '加载失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/drone', methods=['POST'])
    @protected
    def drone_create():
        session = Session()
        try:
            d = request.get_json(silent=True) or {}
            if not (d.get('location') or '').strip():
                return jsonify({'error': '请填写飞行地点'}), 400
            if not (d.get('purpose') or '').strip():
                return jsonify({'error': '请填写飞行目的'}), 400
            fd = _dt(d.get('flight_date'))
            if not fd:
                return jsonify({'error': '请填写飞行日期'}), 400
            # 默认带出设备信息
            model = session.query(SystemConfig).filter_by(config_key='drone_model').first()
            keeper = session.query(SystemConfig).filter_by(config_key='drone_keeper').first()
            item = DroneFlightLedger(
                flight_date=fd.date(),
                location=d['location'].strip(),
                purpose=d['purpose'].strip(),
                start_time=_dt(d.get('start_time')),
                end_time=_dt(d.get('end_time')),
                applicant=(d.get('applicant') or '').strip() or None,
                approver=(d.get('approver') or '').strip() or None,
                drone_model=(d.get('drone_model') or '').strip() or (model.config_value if model else None),
                keeper=(d.get('keeper') or '').strip() or (keeper.config_value if keeper else None),
                status=(d.get('status') or '待批准').strip() or '待批准',
                notes=d.get('notes'),
                created_by=getattr(request, 'user_id', None),
            )
            session.add(item)
            session.commit()
            return jsonify({'success': True, 'id': item.id}), 201
        except Exception:
            session.rollback()
            logger.exception('drone_create')
            return jsonify({'error': '保存失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/drone/<int:item_id>', methods=['PUT'])
    @protected
    def drone_update(item_id):
        session = Session()
        try:
            item = session.query(DroneFlightLedger).filter_by(id=item_id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404
            d = request.get_json(silent=True) or {}
            if 'flight_date' in d:
                fd = _dt(d.get('flight_date'))
                if fd:
                    item.flight_date = fd.date()
            if 'location' in d:
                item.location = (d.get('location') or '').strip()
            if 'purpose' in d:
                item.purpose = (d.get('purpose') or '').strip()
            if 'start_time' in d:
                item.start_time = _dt(d.get('start_time'))
            if 'end_time' in d:
                item.end_time = _dt(d.get('end_time'))
            if 'applicant' in d:
                item.applicant = (d.get('applicant') or '').strip() or None
            if 'approver' in d:
                item.approver = (d.get('approver') or '').strip() or None
            if 'drone_model' in d:
                item.drone_model = (d.get('drone_model') or '').strip() or None
            if 'keeper' in d:
                item.keeper = (d.get('keeper') or '').strip() or None
            if 'status' in d:
                item.status = (d.get('status') or '').strip() or item.status
            if 'notes' in d:
                item.notes = d.get('notes')
            session.commit()
            return jsonify({'success': True})
        except Exception:
            session.rollback()
            logger.exception('drone_update')
            return jsonify({'error': '保存失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/drone/<int:item_id>', methods=['DELETE'])
    @protected
    def drone_delete(item_id):
        session = Session()
        try:
            item = session.query(DroneFlightLedger).filter_by(id=item_id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404
            session.delete(item)
            session.commit()
            return jsonify({'success': True})
        except Exception:
            session.rollback()
            logger.exception('drone_delete')
            return jsonify({'error': '删除失败'}), 500
        finally:
            session.close()
