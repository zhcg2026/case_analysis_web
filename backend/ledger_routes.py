# -*- coding: utf-8 -*-
"""台账路由模块 - 运维台账、会议台账、培训台账"""
from flask import request, jsonify
from datetime import datetime
import logging
from helpers import protected

logger = logging.getLogger(__name__)


def parse_datetime(dt_str):
    """将ISO格式日期转换为datetime对象，支持多种格式"""
    if not dt_str:
        return None
    if isinstance(dt_str, datetime):
        return dt_str
    try:
        # 处理ISO格式: 2026-08-24T00:00:00.000Z
        if 'T' in dt_str:
            dt_str = dt_str.replace('Z', '').replace('T', ' ')
            # 去掉毫秒部分
            if '.' in dt_str:
                dt_str = dt_str.split('.')[0]
        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d')
        except ValueError:
            return None


def register_ledger_routes(app, Session, MaintenanceLedger, MeetingLedger, TrainingLedger, protected):
    """注册台账相关路由"""

    # ==================== 运维台账路由 ====================

    @app.route('/api/ledger/maintenance', methods=['GET'])
    @protected
    def get_maintenance_list():
        session = Session()
        try:
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('pageSize', 20, type=int)
            keyword = request.args.get('keyword', '').strip()
            status = request.args.get('status', '').strip()
            fault_level = request.args.get('fault_level', '').strip()

            query = session.query(MaintenanceLedger)

            if keyword:
                query = query.filter(
                    (MaintenanceLedger.title.contains(keyword)) |
                    (MaintenanceLedger.reporter.contains(keyword)) |
                    (MaintenanceLedger.assignee.contains(keyword))
                )
            if status:
                query = query.filter(MaintenanceLedger.status == status)
            if fault_level:
                query = query.filter(MaintenanceLedger.fault_level == fault_level)

            total = query.count()
            items = query.order_by(MaintenanceLedger.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

            data = []
            for item in items:
                data.append({
                    'id': item.id,
                    'title': item.title,
                    'fault_level': item.fault_level,
                    'reporter': item.reporter,
                    'assignee': item.assignee,
                    'description': item.description,
                    'solution': item.solution,
                    'status': item.status,
                    'reported_at': item.reported_at.strftime('%Y-%m-%d %H:%M:%S') if item.reported_at else None,
                    'resolved_at': item.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if item.resolved_at else None,
                    'notes': item.notes,
                    'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else None,
                    'updated_at': item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else None
                })

            session.commit()
            return jsonify({'success': True, 'data': data, 'total': total, 'page': page, 'pageSize': page_size}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in get_maintenance_list')
            return jsonify({'error': '操作失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/maintenance', methods=['POST'])
    @protected
    def create_maintenance():
        session = Session()
        try:
            data = request.get_json()
            title = data.get('title', '').strip()
            reporter = data.get('reporter', '').strip()

            if not title:
                return jsonify({'error': '故障标题不能为空'}), 400
            if not reporter:
                return jsonify({'error': '提报人不能为空'}), 400

            item = MaintenanceLedger(
                title=title,
                fault_level=data.get('fault_level', '中'),
                reporter=reporter,
                assignee=data.get('assignee', ''),
                description=data.get('description', ''),
                solution=data.get('solution', ''),
                status=data.get('status', '待处理'),
                reported_at=parse_datetime(data.get('reported_at')),
                resolved_at=parse_datetime(data.get('resolved_at')),
                notes=data.get('notes', ''),
                created_by=request.user_id
            )
            session.add(item)
            session.commit()

            return jsonify({'success': True, 'id': item.id, 'message': '创建成功'}), 201
        except Exception as e:
            session.rollback()
            logger.exception('Error in create_maintenance')
            return jsonify({'error': '创建失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/maintenance/<int:id>', methods=['PUT'])
    @protected
    def update_maintenance(id):
        session = Session()
        try:
            item = session.query(MaintenanceLedger).filter_by(id=id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404

            data = request.get_json()
            if 'title' in data:
                item.title = data['title'].strip()
            if 'fault_level' in data:
                item.fault_level = data['fault_level']
            if 'reporter' in data:
                item.reporter = data['reporter'].strip()
            if 'assignee' in data:
                item.assignee = data['assignee']
            if 'description' in data:
                item.description = data['description']
            if 'solution' in data:
                item.solution = data['solution']
            if 'status' in data:
                item.status = data['status']
            if 'reported_at' in data:
                item.reported_at = parse_datetime(data['reported_at'])
            if 'resolved_at' in data:
                item.resolved_at = parse_datetime(data['resolved_at'])
            if 'notes' in data:
                item.notes = data['notes']

            session.commit()
            return jsonify({'success': True, 'message': '更新成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in update_maintenance')
            return jsonify({'error': '更新失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/maintenance/<int:id>', methods=['DELETE'])
    @protected
    def delete_maintenance(id):
        session = Session()
        try:
            item = session.query(MaintenanceLedger).filter_by(id=id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404

            session.delete(item)
            session.commit()
            return jsonify({'success': True, 'message': '删除成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in delete_maintenance')
            return jsonify({'error': '删除失败'}), 500
        finally:
            session.close()

    # ==================== 会议台账路由 ====================

    @app.route('/api/ledger/meeting', methods=['GET'])
    @protected
    def get_meeting_list():
        session = Session()
        try:
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('pageSize', 20, type=int)
            keyword = request.args.get('keyword', '').strip()

            query = session.query(MeetingLedger)

            if keyword:
                query = query.filter(
                    (MeetingLedger.title.contains(keyword)) |
                    (MeetingLedger.host.contains(keyword)) |
                    (MeetingLedger.attendees.contains(keyword))
                )

            total = query.count()
            items = query.order_by(MeetingLedger.meeting_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

            data = []
            for item in items:
                data.append({
                    'id': item.id,
                    'meeting_time': item.meeting_time.strftime('%Y-%m-%d %H:%M:%S') if item.meeting_time else None,
                    'title': item.title,
                    'location': item.location,
                    'attendees': item.attendees,
                    'host': item.host,
                    'minutes': item.minutes,
                    'images': item.images,
                    'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else None,
                    'updated_at': item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else None
                })

            session.commit()
            return jsonify({'success': True, 'data': data, 'total': total, 'page': page, 'pageSize': page_size}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in get_meeting_list')
            return jsonify({'error': '操作失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/meeting', methods=['POST'])
    @protected
    def create_meeting():
        session = Session()
        try:
            data = request.get_json()
            title = data.get('title', '').strip()
            meeting_time = data.get('meeting_time')

            if not title:
                return jsonify({'error': '会议主题不能为空'}), 400
            if not meeting_time:
                return jsonify({'error': '会议时间不能为空'}), 400

            item = MeetingLedger(
                meeting_time=parse_datetime(meeting_time),
                title=title,
                location=data.get('location', ''),
                attendees=data.get('attendees', ''),
                host=data.get('host', ''),
                minutes=data.get('minutes', ''),
                images=data.get('images', ''),
                created_by=request.user_id
            )
            session.add(item)
            session.commit()

            return jsonify({'success': True, 'id': item.id, 'message': '创建成功'}), 201
        except Exception as e:
            session.rollback()
            logger.exception('Error in create_meeting')
            return jsonify({'error': '创建失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/meeting/<int:id>', methods=['PUT'])
    @protected
    def update_meeting(id):
        session = Session()
        try:
            item = session.query(MeetingLedger).filter_by(id=id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404

            data = request.get_json()
            if 'meeting_time' in data:
                item.meeting_time = parse_datetime(data['meeting_time'])
            if 'title' in data:
                item.title = data['title'].strip()
            if 'location' in data:
                item.location = data['location']
            if 'attendees' in data:
                item.attendees = data['attendees']
            if 'host' in data:
                item.host = data['host']
            if 'minutes' in data:
                item.minutes = data['minutes']
            if 'images' in data:
                item.images = data['images']

            session.commit()
            return jsonify({'success': True, 'message': '更新成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in update_meeting')
            return jsonify({'error': '更新失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/meeting/<int:id>', methods=['DELETE'])
    @protected
    def delete_meeting(id):
        session = Session()
        try:
            item = session.query(MeetingLedger).filter_by(id=id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404

            session.delete(item)
            session.commit()
            return jsonify({'success': True, 'message': '删除成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in delete_meeting')
            return jsonify({'error': '删除失败'}), 500
        finally:
            session.close()

    # ==================== 培训台账路由 ====================

    @app.route('/api/ledger/training', methods=['GET'])
    @protected
    def get_training_list():
        session = Session()
        try:
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('pageSize', 20, type=int)
            keyword = request.args.get('keyword', '').strip()

            query = session.query(TrainingLedger)

            if keyword:
                query = query.filter(
                    (TrainingLedger.title.contains(keyword)) |
                    (TrainingLedger.trainer.contains(keyword)) |
                    (TrainingLedger.attendees.contains(keyword))
                )

            total = query.count()
            items = query.order_by(TrainingLedger.training_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

            data = []
            for item in items:
                data.append({
                    'id': item.id,
                    'training_time': item.training_time.strftime('%Y-%m-%d %H:%M:%S') if item.training_time else None,
                    'title': item.title,
                    'location': item.location,
                    'attendees': item.attendees,
                    'trainer': item.trainer,
                    'content': item.content,
                    'images': item.images,
                    'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else None,
                    'updated_at': item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else None
                })

            session.commit()
            return jsonify({'success': True, 'data': data, 'total': total, 'page': page, 'pageSize': page_size}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in get_training_list')
            return jsonify({'error': '操作失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/training', methods=['POST'])
    @protected
    def create_training():
        session = Session()
        try:
            data = request.get_json()
            title = data.get('title', '').strip()
            trainer = data.get('trainer', '').strip()
            training_time = data.get('training_time')

            if not title:
                return jsonify({'error': '培训主题不能为空'}), 400
            if not trainer:
                return jsonify({'error': '培训人不能为空'}), 400
            if not training_time:
                return jsonify({'error': '培训时间不能为空'}), 400

            item = TrainingLedger(
                training_time=parse_datetime(training_time),
                title=title,
                location=data.get('location', ''),
                attendees=data.get('attendees', ''),
                trainer=trainer,
                content=data.get('content', ''),
                images=data.get('images', ''),
                created_by=request.user_id
            )
            session.add(item)
            session.commit()

            return jsonify({'success': True, 'id': item.id, 'message': '创建成功'}), 201
        except Exception as e:
            session.rollback()
            logger.exception('Error in create_training')
            return jsonify({'error': '创建失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/training/<int:id>', methods=['PUT'])
    @protected
    def update_training(id):
        session = Session()
        try:
            item = session.query(TrainingLedger).filter_by(id=id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404

            data = request.get_json()
            if 'training_time' in data:
                item.training_time = parse_datetime(data['training_time'])
            if 'title' in data:
                item.title = data['title'].strip()
            if 'location' in data:
                item.location = data['location']
            if 'attendees' in data:
                item.attendees = data['attendees']
            if 'trainer' in data:
                item.trainer = data['trainer'].strip()
            if 'content' in data:
                item.content = data['content']
            if 'images' in data:
                item.images = data['images']

            session.commit()
            return jsonify({'success': True, 'message': '更新成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in update_training')
            return jsonify({'error': '更新失败'}), 500
        finally:
            session.close()

    @app.route('/api/ledger/training/<int:id>', methods=['DELETE'])
    @protected
    def delete_training(id):
        session = Session()
        try:
            item = session.query(TrainingLedger).filter_by(id=id).first()
            if not item:
                return jsonify({'error': '记录不存在'}), 404

            session.delete(item)
            session.commit()
            return jsonify({'success': True, 'message': '删除成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception('Error in delete_training')
            return jsonify({'error': '删除失败'}), 500
        finally:
            session.close()
