import os
import json
import uuid
import datetime
from flask import jsonify, request, send_file
from sqlalchemy import func
from flood_helpers import (
    fetch_realtime_weather,
    fetch_hourly_forecast,
    determine_rain_intensity,
    determine_water_level,
    serialize_weather,
    serialize_hourly_forecast,
)


def register_flood_monitor_routes(
    app,
    Session,
    FloodWeatherRecord,
    FloodRainEvent,
    FloodWaterloggingPoint,
    FloodDispatchRecord,
    FloodDutyShift,
    FloodEmergencySupply,
    protected,
):
    # ============================================================
    # 天气相关接口
    # ============================================================

    @app.route('/api/flood/weather/realtime', methods=['GET'])
    @protected
    def flood_weather_realtime():
        try:
            weather_now = fetch_realtime_weather()
            result = serialize_weather(weather_now)
            return jsonify({'weather': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/flood/weather/hourly', methods=['GET'])
    @protected
    def flood_weather_hourly():
        try:
            hourly = fetch_hourly_forecast()
            result = serialize_hourly_forecast(hourly)
            return jsonify({'hourly': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/flood/weather/record', methods=['POST'])
    @protected
    def flood_weather_record():
        """手动记录当前天气快照（或由定时任务自动调用）"""
        session = Session()
        try:
            weather_now = fetch_realtime_weather()
            if not weather_now:
                return jsonify({'error': '获取天气数据失败'}), 500

            record = FloodWeatherRecord(
                city_code='101100801',
                weather_data=json.dumps(weather_now, ensure_ascii=False),
                temperature=weather_now.get('temp', ''),
                humidity=weather_now.get('humidity', ''),
                wind_direction=weather_now.get('windDir', ''),
                wind_power=weather_now.get('windScale', ''),
                weather_text=weather_now.get('text', ''),
                rainfall_1h=weather_now.get('precip', '0'),
                recorded_at=datetime.datetime.now(),
            )
            session.add(record)

            # 检测降雨事件
            rainfall = weather_now.get('precip', '0')
            try:
                rainfall_val = float(rainfall)
            except (ValueError, TypeError):
                rainfall_val = 0

            if rainfall_val > 0:
                active_event = session.query(FloodRainEvent).filter_by(status='active').first()
                if active_event:
                    # 更新现有事件
                    max_rain = float(active_event.max_rainfall_1h or 0)
                    if rainfall_val > max_rain:
                        active_event.max_rainfall_1h = rainfall
                    active_event.intensity = determine_rain_intensity(rainfall_val)
                else:
                    # 创建新降雨事件
                    new_event = FloodRainEvent(
                        start_time=datetime.datetime.now(),
                        max_rainfall_1h=rainfall,
                        total_rainfall=rainfall,
                        intensity=determine_rain_intensity(rainfall_val),
                        status='active',
                    )
                    session.add(new_event)
            else:
                # 无雨，结束进行中的事件
                active_event = session.query(FloodRainEvent).filter_by(status='active').first()
                if active_event:
                    active_event.end_time = datetime.datetime.now()
                    active_event.status = 'ended'

            session.commit()
            return jsonify({'message': '天气记录已保存'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/weather/history', methods=['GET'])
    @protected
    def flood_weather_history():
        session = Session()
        try:
            limit = request.args.get('limit', 50, type=int)
            records = session.query(FloodWeatherRecord).order_by(
                FloodWeatherRecord.recorded_at.desc()
            ).limit(limit).all()
            result = []
            for r in records:
                result.append({
                    'id': r.id,
                    'temperature': r.temperature,
                    'humidity': r.humidity,
                    'windDirection': r.wind_direction,
                    'windPower': r.wind_power,
                    'weatherText': r.weather_text,
                    'rainfall1h': r.rainfall_1h,
                    'recordedAt': r.recorded_at.isoformat() if r.recorded_at else None,
                })
            return jsonify({'records': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ============================================================
    # 降雨事件接口
    # ============================================================

    @app.route('/api/flood/rain-events', methods=['GET'])
    @protected
    def flood_rain_events():
        session = Session()
        try:
            status = request.args.get('status')
            limit = request.args.get('limit', 20, type=int)
            query = session.query(FloodRainEvent)
            if status:
                query = query.filter_by(status=status)
            events = query.order_by(FloodRainEvent.start_time.desc()).limit(limit).all()
            result = []
            for e in events:
                result.append({
                    'id': e.id,
                    'startTime': e.start_time.isoformat() if e.start_time else None,
                    'endTime': e.end_time.isoformat() if e.end_time else None,
                    'maxRainfall1h': e.max_rainfall_1h,
                    'totalRainfall': e.total_rainfall,
                    'intensity': e.intensity,
                    'status': e.status,
                })
            return jsonify({'events': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/rain-events/active', methods=['GET'])
    @protected
    def flood_rain_events_active():
        session = Session()
        try:
            event = session.query(FloodRainEvent).filter_by(status='active').first()
            if event:
                result = {
                    'id': event.id,
                    'startTime': event.start_time.isoformat() if event.start_time else None,
                    'endTime': event.end_time.isoformat() if event.end_time else None,
                    'maxRainfall1h': event.max_rainfall_1h,
                    'totalRainfall': event.total_rainfall,
                    'intensity': event.intensity,
                    'status': event.status,
                }
            else:
                result = None
            return jsonify({'event': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ============================================================
    # 积水点接口
    # ============================================================

    @app.route('/api/flood/waterlogging-points', methods=['GET'])
    @protected
    def flood_get_waterlogging_points():
        session = Session()
        try:
            points = session.query(FloodWaterloggingPoint).all()
            result = []
            for p in points:
                result.append({
                    'id': p.id,
                    'name': p.name,
                    'longitude': p.longitude,
                    'latitude': p.latitude,
                    'dutyPerson': p.duty_person,
                    'dutyPhone': p.duty_phone,
                    'waterLevel': p.water_level,
                    'waterDepth': p.water_depth,
                    'lastUpdated': p.last_updated.isoformat() if p.last_updated else None,
                })
            return jsonify({'points': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/waterlogging-points', methods=['POST'])
    @protected
    def flood_create_waterlogging_point():
        session = Session()
        try:
            data = request.json
            point = FloodWaterloggingPoint(
                name=data.get('name', ''),
                longitude=data.get('longitude', ''),
                latitude=data.get('latitude', ''),
                duty_person=data.get('dutyPerson', ''),
                duty_phone=data.get('dutyPhone', ''),
                water_level=data.get('waterLevel', 'normal'),
                water_depth=data.get('waterDepth', '0'),
                last_updated=datetime.datetime.now(),
            )
            session.add(point)
            session.commit()
            return jsonify({'message': '积水点已添加', 'id': point.id}), 201
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/waterlogging-points/<int:point_id>', methods=['PUT'])
    @protected
    def flood_update_waterlogging_point(point_id):
        session = Session()
        try:
            point = session.query(FloodWaterloggingPoint).get(point_id)
            if not point:
                return jsonify({'error': '积水点不存在'}), 404
            data = request.json
            point.name = data.get('name', point.name)
            point.longitude = data.get('longitude', point.longitude)
            point.latitude = data.get('latitude', point.latitude)
            point.duty_person = data.get('dutyPerson', point.duty_person)
            point.duty_phone = data.get('dutyPhone', point.duty_phone)
            point.last_updated = datetime.datetime.now()
            session.commit()
            return jsonify({'message': '积水点已更新'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/waterlogging-points/<int:point_id>', methods=['DELETE'])
    @protected
    def flood_delete_waterlogging_point(point_id):
        session = Session()
        try:
            point = session.query(FloodWaterloggingPoint).get(point_id)
            if not point:
                return jsonify({'error': '积水点不存在'}), 404
            session.delete(point)
            session.commit()
            return jsonify({'message': '积水点已删除'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/waterlogging-points/<int:point_id>/water-level', methods=['PUT'])
    @protected
    def flood_update_water_level(point_id):
        session = Session()
        try:
            point = session.query(FloodWaterloggingPoint).get(point_id)
            if not point:
                return jsonify({'error': '积水点不存在'}), 404
            data = request.json
            depth = data.get('waterDepth', '0')
            point.water_depth = depth
            point.water_level = determine_water_level(depth)
            point.last_updated = datetime.datetime.now()
            session.commit()
            return jsonify({'message': '水位已更新', 'waterLevel': point.water_level}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ============================================================
    # 调度台账接口
    # ============================================================

    @app.route('/api/flood/dispatch-records', methods=['GET'])
    @protected
    def flood_get_dispatch_records():
        session = Session()
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            record_type = request.args.get('type')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            query = session.query(FloodDispatchRecord)
            if record_type:
                query = query.filter(FloodDispatchRecord.record_type == record_type)
            if start_date:
                query = query.filter(FloodDispatchRecord.event_time >= start_date)
            if end_date:
                query = query.filter(FloodDispatchRecord.event_time <= end_date)

            total = query.count()
            records = query.order_by(FloodDispatchRecord.event_time.desc()).offset(
                (page - 1) * per_page
            ).limit(per_page).all()

            result = []
            for r in records:
                images = []
                if r.images:
                    try:
                        images = json.loads(r.images)
                    except (json.JSONDecodeError, TypeError):
                        pass
                result.append({
                    'id': r.id,
                    'recordType': r.record_type,
                    'title': r.title,
                    'content': r.content,
                    'eventTime': r.event_time.isoformat() if r.event_time else None,
                    'weatherSnapshot': json.loads(r.weather_snapshot) if r.weather_snapshot else None,
                    'location': r.location,
                    'images': images,
                    'operator': r.operator,
                    'status': r.status,
                    'createdAt': r.created_at.isoformat() if r.created_at else None,
                })
            return jsonify({'records': result, 'total': total, 'page': page, 'per_page': per_page}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/dispatch-records', methods=['POST'])
    @protected
    def flood_create_dispatch_record():
        session = Session()
        try:
            data = request.json
            # 自动获取当前天气快照
            weather_now = fetch_realtime_weather()
            weather_snapshot = json.dumps(weather_now, ensure_ascii=False) if weather_now else None

            record = FloodDispatchRecord(
                record_type=data.get('recordType', ''),
                title=data.get('title', ''),
                content=data.get('content', ''),
                event_time=datetime.datetime.fromisoformat(data['eventTime']) if data.get('eventTime') else datetime.datetime.now(),
                weather_snapshot=weather_snapshot,
                location=data.get('location', ''),
                images=json.dumps(data.get('images', []), ensure_ascii=False),
                operator=data.get('operator', ''),
                status=data.get('status', 'active'),
            )
            session.add(record)
            session.commit()
            return jsonify({'message': '台账记录已创建', 'id': record.id}), 201
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/dispatch-records/<int:record_id>', methods=['PUT'])
    @protected
    def flood_update_dispatch_record(record_id):
        session = Session()
        try:
            record = session.query(FloodDispatchRecord).get(record_id)
            if not record:
                return jsonify({'error': '记录不存在'}), 404
            data = request.json
            record.record_type = data.get('recordType', record.record_type)
            record.title = data.get('title', record.title)
            record.content = data.get('content', record.content)
            if data.get('eventTime'):
                record.event_time = datetime.datetime.fromisoformat(data['eventTime'])
            record.location = data.get('location', record.location)
            if data.get('images') is not None:
                record.images = json.dumps(data['images'], ensure_ascii=False)
            record.operator = data.get('operator', record.operator)
            record.status = data.get('status', record.status)
            session.commit()
            return jsonify({'message': '台账记录已更新'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/dispatch-records/<int:record_id>', methods=['DELETE'])
    @protected
    def flood_delete_dispatch_record(record_id):
        session = Session()
        try:
            record = session.query(FloodDispatchRecord).get(record_id)
            if not record:
                return jsonify({'error': '记录不存在'}), 404
            session.delete(record)
            session.commit()
            return jsonify({'message': '台账记录已删除'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/dispatch-report', methods=['GET'])
    @protected
    def flood_dispatch_report():
        """生成汛期调度报告（按时间范围统计）"""
        session = Session()
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            query = session.query(FloodDispatchRecord)
            if start_date:
                query = query.filter(FloodDispatchRecord.event_time >= start_date)
            if end_date:
                query = query.filter(FloodDispatchRecord.event_time <= end_date)

            records = query.order_by(FloodDispatchRecord.event_time.asc()).all()

            # 按类型统计
            type_stats = {}
            for r in records:
                t = r.record_type or '其他'
                type_stats[t] = type_stats.get(t, 0) + 1

            # 降雨事件统计
            rain_query = session.query(FloodRainEvent)
            if start_date:
                rain_query = rain_query.filter(FloodRainEvent.start_time >= start_date)
            if end_date:
                rain_query = rain_query.filter(FloodRainEvent.start_time <= end_date)
            rain_events = rain_query.all()
            rain_count = len(rain_events)

            # 积水点统计
            water_points = session.query(FloodWaterloggingPoint).count()

            report = {
                'summary': {
                    'totalRecords': len(records),
                    'typeStats': type_stats,
                    'rainEventCount': rain_count,
                    'waterPointCount': water_points,
                },
                'records': [{
                    'id': r.id,
                    'recordType': r.record_type,
                    'title': r.title,
                    'content': r.content,
                    'eventTime': r.event_time.isoformat() if r.event_time else None,
                    'location': r.location,
                    'operator': r.operator,
                } for r in records],
                'rainEvents': [{
                    'startTime': e.start_time.isoformat() if e.start_time else None,
                    'endTime': e.end_time.isoformat() if e.end_time else None,
                    'intensity': e.intensity,
                    'maxRainfall1h': e.max_rainfall_1h,
                } for e in rain_events],
            }
            return jsonify({'report': report}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ============================================================
    # 值班排班接口
    # ============================================================

    @app.route('/api/flood/duty-shifts', methods=['GET'])
    @protected
    def flood_get_duty_shifts():
        session = Session()
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            query = session.query(FloodDutyShift)
            if start_date:
                query = query.filter(FloodDutyShift.shift_date >= start_date)
            if end_date:
                query = query.filter(FloodDutyShift.shift_date <= end_date)
            shifts = query.order_by(FloodDutyShift.shift_date.asc()).all()
            result = []
            for s in shifts:
                result.append({
                    'id': s.id,
                    'shiftDate': s.shift_date.isoformat() if s.shift_date else None,
                    'shiftName': s.shift_name,
                    'person1': s.person1,
                    'person1Phone': s.person1_phone,
                    'person2': s.person2,
                    'person2Phone': s.person2_phone,
                })
            return jsonify({'shifts': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/duty-shifts', methods=['POST'])
    @protected
    def flood_create_duty_shift():
        session = Session()
        try:
            data = request.json
            shift = FloodDutyShift(
                shift_date=datetime.datetime.fromisoformat(data['shiftDate']) if data.get('shiftDate') else datetime.datetime.now(),
                shift_name=data.get('shiftName', '白班'),
                person1=data.get('person1', ''),
                person1_phone=data.get('person1Phone', ''),
                person2=data.get('person2', ''),
                person2_phone=data.get('person2Phone', ''),
            )
            session.add(shift)
            session.commit()
            return jsonify({'message': '排班已创建', 'id': shift.id}), 201
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/duty-shifts/<int:shift_id>', methods=['PUT'])
    @protected
    def flood_update_duty_shift(shift_id):
        session = Session()
        try:
            shift = session.query(FloodDutyShift).get(shift_id)
            if not shift:
                return jsonify({'error': '排班不存在'}), 404
            data = request.json
            if data.get('shiftDate'):
                shift.shift_date = datetime.datetime.fromisoformat(data['shiftDate'])
            shift.shift_name = data.get('shiftName', shift.shift_name)
            shift.person1 = data.get('person1', shift.person1)
            shift.person1_phone = data.get('person1Phone', shift.person1_phone)
            shift.person2 = data.get('person2', shift.person2)
            shift.person2_phone = data.get('person2Phone', shift.person2_phone)
            session.commit()
            return jsonify({'message': '排班已更新'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/duty-shifts/<int:shift_id>', methods=['DELETE'])
    @protected
    def flood_delete_duty_shift(shift_id):
        session = Session()
        try:
            shift = session.query(FloodDutyShift).get(shift_id)
            if not shift:
                return jsonify({'error': '排班不存在'}), 404
            session.delete(shift)
            session.commit()
            return jsonify({'message': '排班已删除'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/duty-shifts/today', methods=['GET'])
    @protected
    def flood_today_duty():
        session = Session()
        try:
            today = datetime.date.today()
            start = datetime.datetime.combine(today, datetime.time.min)
            end = datetime.datetime.combine(today, datetime.time.max)
            shifts = session.query(FloodDutyShift).filter(
                FloodDutyShift.shift_date >= start,
                FloodDutyShift.shift_date <= end,
            ).all()
            result = []
            for s in shifts:
                result.append({
                    'id': s.id,
                    'shiftDate': s.shift_date.isoformat() if s.shift_date else None,
                    'shiftName': s.shift_name,
                    'person1': s.person1,
                    'person1Phone': s.person1_phone,
                    'person2': s.person2,
                    'person2Phone': s.person2_phone,
                })
            return jsonify({'shifts': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/duty-shifts/upload', methods=['POST'])
    @protected
    def flood_upload_duty_shifts():
        """上传Excel排班表（批量导入）"""
        session = Session()
        try:
            if 'file' not in request.files:
                return jsonify({'error': '未上传文件'}), 400
            file = request.files['file']
            if not file.filename.endswith(('.xlsx', '.xls')):
                return jsonify({'error': '仅支持Excel文件'}), 400

            import tempfile
            import openpyxl

            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
                file.save(temp.name)
                temp_path = temp.name

            try:
                wb = openpyxl.load_workbook(temp_path)
                ws = wb.active
                created = 0
                # 跳过表头行，假设列顺序: 日期 | 班次 | 人员1 | 电话1 | 人员2 | 电话2
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row[0]:
                        continue
                    shift_date = row[0]
                    if isinstance(shift_date, datetime.datetime):
                        pass
                    elif isinstance(shift_date, str):
                        try:
                            shift_date = datetime.datetime.fromisoformat(shift_date)
                        except ValueError:
                            continue
                    else:
                        continue

                    shift = FloodDutyShift(
                        shift_date=shift_date,
                        shift_name=str(row[1] or '白班'),
                        person1=str(row[2] or ''),
                        person1_phone=str(row[3] or ''),
                        person2=str(row[4] or ''),
                        person2_phone=str(row[5] or ''),
                    )
                    session.add(shift)
                    created += 1

                session.commit()
                return jsonify({'message': f'成功导入 {created} 条排班记录', 'created': created}), 201
            finally:
                os.unlink(temp_path)
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ============================================================
    # 图片上传
    # ============================================================

    @app.route('/api/flood/upload-image', methods=['POST'])
    @protected
    def flood_upload_image():
        session = Session()
        try:
            if 'file' not in request.files:
                return jsonify({'error': '未上传文件'}), 400
            file = request.files['file']
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                return jsonify({'error': '仅支持图片文件(jpg/png/gif/webp)'}), 400

            unique_filename = f"flood_{uuid.uuid4().hex}{ext}"
            upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'flood')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)

            return jsonify({'url': f'/uploads/flood/{unique_filename}', 'filename': unique_filename}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ============================================================
    # 应急物资管理接口
    # ============================================================

    @app.route('/api/flood/emergency-supplies', methods=['GET'])
    @protected
    def flood_get_emergency_supplies():
        session = Session()
        try:
            supplies = session.query(FloodEmergencySupply).all()
            result = []
            for s in supplies:
                items = []
                if s.supplies_list:
                    try:
                        items = json.loads(s.supplies_list)
                    except (json.JSONDecodeError, TypeError):
                        pass
                result.append({
                    'id': s.id,
                    'name': s.name,
                    'longitude': s.longitude,
                    'latitude': s.latitude,
                    'suppliesList': items,
                    'contactPerson': s.contact_person,
                    'contactPhone': s.contact_phone,
                    'remark': s.remark,
                })
            return jsonify({'supplies': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/emergency-supplies', methods=['POST'])
    @protected
    def flood_create_emergency_supply():
        session = Session()
        try:
            data = request.json
            supply = FloodEmergencySupply(
                name=data.get('name', ''),
                longitude=data.get('longitude', ''),
                latitude=data.get('latitude', ''),
                supplies_list=json.dumps(data.get('suppliesList', []), ensure_ascii=False),
                contact_person=data.get('contactPerson', ''),
                contact_phone=data.get('contactPhone', ''),
                remark=data.get('remark', ''),
            )
            session.add(supply)
            session.commit()
            return jsonify({'message': '物资点已添加', 'id': supply.id}), 201
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/emergency-supplies/<int:supply_id>', methods=['PUT'])
    @protected
    def flood_update_emergency_supply(supply_id):
        session = Session()
        try:
            supply = session.query(FloodEmergencySupply).get(supply_id)
            if not supply:
                return jsonify({'error': '物资点不存在'}), 404
            data = request.json
            supply.name = data.get('name', supply.name)
            supply.longitude = data.get('longitude', supply.longitude)
            supply.latitude = data.get('latitude', supply.latitude)
            if data.get('suppliesList') is not None:
                supply.supplies_list = json.dumps(data['suppliesList'], ensure_ascii=False)
            supply.contact_person = data.get('contactPerson', supply.contact_person)
            supply.contact_phone = data.get('contactPhone', supply.contact_phone)
            supply.remark = data.get('remark', supply.remark)
            session.commit()
            return jsonify({'message': '物资点已更新'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/emergency-supplies/<int:supply_id>', methods=['DELETE'])
    @protected
    def flood_delete_emergency_supply(supply_id):
        session = Session()
        try:
            supply = session.query(FloodEmergencySupply).get(supply_id)
            if not supply:
                return jsonify({'error': '物资点不存在'}), 404
            session.delete(supply)
            session.commit()
            return jsonify({'message': '物资点已删除'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ============================================================
    # 应急预案接口
    # ============================================================

    @app.route('/api/flood/emergency-plan', methods=['GET'])
    @protected
    def flood_get_emergency_plan():
        """获取应急预案文件列表"""
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'flood', 'plan')
        os.makedirs(upload_dir, exist_ok=True)
        files = []
        for f in os.listdir(upload_dir):
            if not f.startswith('.'):
                stat = os.stat(os.path.join(upload_dir, f))
                files.append({
                    'filename': f,
                    'size': stat.st_size,
                    'url': f'/uploads/flood/plan/{f}'
                })
        return jsonify({'files': files}), 200

    @app.route('/api/flood/emergency-plan/upload', methods=['POST'])
    @protected
    def flood_upload_emergency_plan():
        """上传应急预案文件"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': '未上传文件'}), 400
            file = request.files['file']
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ('.pdf', '.doc', '.docx', '.txt'):
                return jsonify({'error': '仅支持 pdf/doc/docx/txt 文件'}), 400

            # 保留原始文件名，加UUID避免冲突
            original_name = os.path.splitext(file.filename)[0]
            unique_filename = f"{original_name}_{uuid.uuid4().hex[:8]}{ext}"
            upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'flood', 'plan')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)

            return jsonify({'message': '上传成功', 'filename': unique_filename, 'url': f'/uploads/flood/plan/{unique_filename}'}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/flood/emergency-plan/<filename>', methods=['DELETE'])
    @protected
    def flood_delete_emergency_plan(filename):
        """删除应急预案文件"""
        try:
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'flood', 'plan', filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                return jsonify({'message': '文件已删除'}), 200
            return jsonify({'error': '文件不存在'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    print("汛情值守路由注册成功")
