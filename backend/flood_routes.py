import os
import json
import uuid
import datetime
from flask import jsonify, request, send_file
from sqlalchemy import func
try:
    from backend.flood_helpers import (
        fetch_realtime_weather,
        fetch_hourly_forecast,
        determine_rain_intensity,
        determine_water_level,
        serialize_weather,
        serialize_hourly_forecast,
    )
except ImportError:
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
    FloodWarning=None,
    FloodDutyLeader=None,
):

    def generate_report_text(report_data):
        """将报告数据格式化为文本"""
        level_map = {'blue': '蓝色', 'yellow': '黄色', 'orange': '橙色', 'red': '红色'}
        level_label = lambda lv: level_map.get(lv, lv or '-')

        def fmt(iso):
            if not iso:
                return '-'
            d = datetime.datetime.fromisoformat(iso) if isinstance(iso, str) else iso
            return f"{d.year}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d}"

        def fmt_date(iso):
            if not iso:
                return '-'
            d = datetime.datetime.fromisoformat(iso) if isinstance(iso, str) else iso
            return f"{d.year}年{d.month}月{d.day}日"

        w = report_data.get('warning')
        level_name = level_label(w['level']) if w else ''
        date_str = fmt_date(w['startTime']) if w else ''

        text = f"运城市智慧城市管理平台防汛指挥调度系统\n"
        text += f"{level_name}预警调度报告\n"
        text += "=" * 50 + "\n\n"

        # 一、预警信息
        text += "【一、预警信息】\n"
        if w:
            text += f"  预警等级: {level_name}预警\n"
            text += f"  启动时间: {fmt(w['startTime'])}\n"
            text += f"  结束时间: {fmt(w['endTime']) if w.get('endTime') else '进行中'}\n"
            text += f"  当前状态: {'进行中' if w.get('status') == 'active' else '已结束'}\n"
        else:
            text += "  暂无预警信息\n"

        # 二、人员信息
        text += "\n【二、人员信息】\n"
        text += "  带班领导:\n"
        duty_leader = report_data.get('dutyLeader')
        if duty_leader:
            text += f"    {duty_leader.get('title', '带班领导')}: {duty_leader.get('name', '-')}"
            if duty_leader.get('phone'):
                text += f" ({duty_leader['phone']})"
            text += "\n"
        else:
            text += "    暂未设置\n"

        text += "  值班人员:\n"
        duty_shifts = report_data.get('dutyShifts', [])
        if duty_shifts:
            for s in duty_shifts:
                shift_name = s.get('shiftName', '-')
                person1 = s.get('person1', '-')
                person1_phone = s.get('person1Phone', '')
                person2 = s.get('person2', '-')
                person2_phone = s.get('person2Phone', '')
                text += f"    {shift_name}: {person1}"
                if person1_phone:
                    text += f" ({person1_phone})"
                text += f" / {person2}"
                if person2_phone:
                    text += f" ({person2_phone})"
                text += "\n"
        else:
            text += "    暂无排班记录\n"

        # 三、天气情况
        text += "\n【三、天气情况】\n"
        weather_summary = report_data.get('weatherSummary', [])
        if weather_summary:
            latest = weather_summary[0]
            text += "  最新气象:\n"
            text += f"    天气: {latest.get('weatherText', '-')}\n"
            text += f"    温度: {latest.get('temperature', '-')}°C  湿度: {latest.get('humidity', '-')}\n"
            text += f"    风向: {latest.get('windDirection', '-')}  风力: {latest.get('windPower', '-')}级\n"
            text += f"    近1h降雨量: {latest.get('rainfall1h', '0')}mm\n\n"
            text += f"  观测记录(共{len(weather_summary)}条):\n"
            for item in weather_summary[:20]:
                text += f"    [{fmt(item.get('recordedAt'))}] {item.get('weatherText', '-')} {item.get('temperature', '-')}°C 降雨{item.get('rainfall1h', '0')}mm\n"
        else:
            text += "  暂无天气观测记录\n"

        rain_events = report_data.get('rainEvents', [])
        if rain_events:
            text += "\n  降雨事件:\n"
            for i, e in enumerate(rain_events):
                text += f"    第{i+1}次: {fmt(e.get('startTime'))} ~ {fmt(e.get('endTime')) if e.get('endTime') else '进行中'}\n"
                text += f"      强度: {e.get('intensity', '-')}  最大1h雨量: {e.get('maxRainfall1h', '-')}mm\n"

        # 四、调度台账
        text += "\n【四、调度台账】\n"
        summary = report_data.get('summary', {})
        text += f"  共{summary.get('totalRecords', 0)}条记录\n"
        type_stats = summary.get('typeStats', {})
        if type_stats:
            text += "  按类型: "
            text += "、".join([f"{k}{v}条" for k, v in type_stats.items()])
            text += "\n\n"

        records = report_data.get('records', [])
        if records:
            for r in records:
                text += f"  [{fmt(r.get('eventTime'))}] {r.get('recordType', '其他')}\n"
                text += f"    {r.get('content', '-')}\n"
                if r.get('location'):
                    text += f"    地点: {r['location']}"
                if r.get('operator'):
                    text += f" | 操作人: {r['operator']}"
                text += "\n"
        else:
            text += "  暂无调度记录\n"

        # 五、积水点信息
        text += "\n【五、积水点信息】\n"
        water_points = report_data.get('waterPoints', [])
        if water_points:
            level_order = {'severe': 0, 'deep': 1, 'medium': 2, 'shallow': 3, 'normal': 4}
            sorted_wp = sorted(water_points, key=lambda x: level_order.get(x.get('waterLevel'), 5))
            water_level_labels = {'normal': '正常', 'shallow': '浅水', 'medium': '中等', 'deep': '较深', 'severe': '严重'}
            text += f"  共{len(water_points)}个积水点\n"
            for wp in sorted_wp:
                label = water_level_labels.get(wp.get('waterLevel'), wp.get('waterLevel', '正常'))
                text += f"  {wp.get('name', '-')}: {label}({wp.get('waterDepth', '0')}cm)"
                duty_persons = wp.get('dutyPersons', [])
                if duty_persons:
                    names = "、".join([d.get('name', '') for d in duty_persons if d.get('name')])
                    if names:
                        text += f" 值守:{names}"
                text += "\n"
        else:
            text += "  暂无积水点\n"

        text += "\n" + "=" * 50 + "\n"
        text += f"报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        text += "运城市智慧城市管理平台防汛指挥调度系统\n"

        return text

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
                duty_persons = []
                if p.duty_persons:
                    try:
                        duty_persons = json.loads(p.duty_persons)
                    except (json.JSONDecodeError, TypeError):
                        pass
                result.append({
                    'id': p.id,
                    'name': p.name,
                    'roadType': p.road_type,
                    'longitude': p.longitude,
                    'latitude': p.latitude,
                    'responsiblePerson': p.responsible_person,
                    'responsiblePhone': p.responsible_phone,
                    'dutyPersons': duty_persons,
                    'trafficPolice': p.traffic_police,
                    'trafficPolicePhone': p.traffic_police_phone,
                    'waterLevel': p.water_level,
                    'waterDepth': p.water_depth,
                    'managementUnit': p.management_unit,
                    'monitoringPoints': json.loads(p.monitoring_points) if p.monitoring_points else [],
                    'remarks': p.remarks,
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
                road_type=data.get('roadType', ''),
                longitude=data.get('longitude', ''),
                latitude=data.get('latitude', ''),
                responsible_person=data.get('responsiblePerson', ''),
                responsible_phone=data.get('responsiblePhone', ''),
                duty_persons=json.dumps(data.get('dutyPersons', []), ensure_ascii=False),
                traffic_police=data.get('trafficPolice', ''),
                traffic_police_phone=data.get('trafficPolicePhone', ''),
                water_level=data.get('waterLevel', 'normal'),
                water_depth=data.get('waterDepth', '0'),
                management_unit=data.get('managementUnit', ''),
                monitoring_points=json.dumps(data.get('monitoringPoints', []), ensure_ascii=False),
                remarks=data.get('remarks', ''),
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
            point.road_type = data.get('roadType', point.road_type)
            point.longitude = data.get('longitude', point.longitude)
            point.latitude = data.get('latitude', point.latitude)
            point.responsible_person = data.get('responsiblePerson', point.responsible_person)
            point.responsible_phone = data.get('responsiblePhone', point.responsible_phone)
            if 'dutyPersons' in data:
                point.duty_persons = json.dumps(data['dutyPersons'], ensure_ascii=False)
            point.traffic_police = data.get('trafficPolice', point.traffic_police)
            point.traffic_police_phone = data.get('trafficPolicePhone', point.traffic_police_phone)
            point.management_unit = data.get('managementUnit', point.management_unit)
            if 'monitoringPoints' in data:
                point.monitoring_points = json.dumps(data['monitoringPoints'], ensure_ascii=False)
            point.remarks = data.get('remarks', point.remarks)
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
            warning_id = request.args.get('warning_id', type=int)

            query = session.query(FloodDispatchRecord)
            if record_type:
                query = query.filter(FloodDispatchRecord.record_type == record_type)
            if start_date:
                query = query.filter(FloodDispatchRecord.event_time >= start_date)
            if end_date:
                query = query.filter(FloodDispatchRecord.event_time <= end_date)
            if warning_id is not None:
                query = query.filter(FloodDispatchRecord.warning_id == warning_id)

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
                    'warningId': r.warning_id,
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
            # 自动获取当前天气快照并保存到天气记录表
            save_weather_snapshot(session)

            record = FloodDispatchRecord(
                record_type=data.get('recordType', ''),
                title=data.get('title', ''),
                content=data.get('content', ''),
                event_time=datetime.datetime.fromisoformat(data['eventTime']) if data.get('eventTime') else datetime.datetime.now(),
                location=data.get('location', ''),
                images=json.dumps(data.get('images', []), ensure_ascii=False),
                operator=data.get('operator', ''),
                warning_id=data.get('warningId'),
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
        """生成调度报告，支持按预警ID或时间范围"""
        session = Session()
        try:
            warning_id = request.args.get('warning_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            # 如果指定了预警ID，优先返回已保存的报告
            if warning_id and FloodWarning:
                w = session.query(FloodWarning).get(warning_id)
                if w and w.report_snapshot:
                    return jsonify({'report': json.loads(w.report_snapshot) if w.report_snapshot.startswith('{') else {'text': w.report_snapshot}}), 200

            # 如果指定了预警ID，以其时间范围为准
            warning_info = None
            if warning_id and FloodWarning:
                w = session.query(FloodWarning).get(warning_id)
                if w:
                    warning_info = {
                        'id': w.id,
                        'level': w.level,
                        'status': w.status,
                        'startTime': w.start_time.isoformat() if w.start_time else None,
                        'endTime': w.end_time.isoformat() if w.end_time else None,
                    }
                    start_date = w.start_time.isoformat() if w.start_time else start_date
                    end_date = w.end_time.isoformat() if w.end_time else end_date

            # 调度记录
            query = session.query(FloodDispatchRecord)
            if warning_id:
                query = query.filter(FloodDispatchRecord.warning_id == warning_id)
            elif start_date:
                query = query.filter(FloodDispatchRecord.event_time >= start_date)
            if end_date and not warning_id:
                query = query.filter(FloodDispatchRecord.event_time <= end_date)
            records = query.order_by(FloodDispatchRecord.event_time.asc()).all()

            # 按类型统计
            type_stats = {}
            for r in records:
                t = r.record_type or '其他'
                type_stats[t] = type_stats.get(t, 0) + 1

            # 带班领导（优先从预警快照读取）
            duty_leader = None
            if w and w.duty_leader_snapshot:
                try:
                    duty_leader = json.loads(w.duty_leader_snapshot)
                except:
                    pass
            if not duty_leader and FloodDutyLeader:
                leader = session.query(FloodDutyLeader).order_by(FloodDutyLeader.id.desc()).first()
                if leader and leader.name:
                    duty_leader = {
                        'title': leader.title,
                        'name': leader.name,
                        'phone': leader.phone,
                    }

            # 值班人员
            duty_shifts = []
            shift_query = session.query(FloodDutyShift)
            if start_date:
                shift_query = shift_query.filter(FloodDutyShift.shift_date >= start_date)
            if end_date:
                shift_query = shift_query.filter(FloodDutyShift.shift_date <= end_date)
            for s in shift_query.all():
                duty_shifts.append({
                    'shiftDate': s.shift_date.isoformat() if s.shift_date else None,
                    'shiftName': s.shift_name,
                    'person1': s.person1,
                    'person1Phone': s.person1_phone,
                    'person2': s.person2,
                    'person2Phone': s.person2_phone,
                })

            # 天气记录
            weather_query = session.query(FloodWeatherRecord)
            if start_date:
                weather_query = weather_query.filter(FloodWeatherRecord.recorded_at >= start_date)
            if end_date:
                weather_query = weather_query.filter(FloodWeatherRecord.recorded_at <= end_date)
            weather_records = weather_query.order_by(FloodWeatherRecord.recorded_at.desc()).limit(50).all()
            weather_summary = []
            for wr in weather_records:
                weather_summary.append({
                    'temperature': wr.temperature,
                    'humidity': wr.humidity,
                    'weatherText': wr.weather_text,
                    'rainfall1h': wr.rainfall_1h,
                    'windDirection': wr.wind_direction,
                    'windPower': wr.wind_power,
                    'recordedAt': wr.recorded_at.isoformat() if wr.recorded_at else None,
                })

            # 降雨事件
            rain_query = session.query(FloodRainEvent)
            if start_date:
                rain_query = rain_query.filter(FloodRainEvent.start_time >= start_date)
            if end_date:
                rain_query = rain_query.filter(FloodRainEvent.start_time <= end_date)
            rain_events = rain_query.all()

            # 积水点（优先从预警快照读取）
            water_points_detail = []
            if w and w.water_points_snapshot:
                try:
                    water_points_detail = json.loads(w.water_points_snapshot)
                except:
                    pass
            if not water_points_detail:
                water_points = session.query(FloodWaterloggingPoint).all()
                for wp in water_points:
                    duty_persons = []
                    if wp.duty_persons:
                        try:
                            duty_persons = json.loads(wp.duty_persons)
                        except:
                            pass
                    water_points_detail.append({
                        'name': wp.name,
                        'waterLevel': wp.water_level,
                        'waterDepth': wp.water_depth,
                        'dutyPersons': duty_persons,
                        'responsiblePerson': wp.responsible_person,
                        'responsiblePhone': wp.responsible_phone,
                        'lastUpdated': wp.last_updated.isoformat() if wp.last_updated else None,
                    })

            report = {
                'warning': warning_info,
                'dutyLeader': duty_leader,
                'dutyShifts': duty_shifts,
                'summary': {
                    'totalRecords': len(records),
                    'typeStats': type_stats,
                    'rainEventCount': len(rain_events),
                    'waterPointCount': len(water_points_detail),
                },
                'weatherSummary': weather_summary,
                'waterPoints': water_points_detail,
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

    # ============================================================
    # 带班领导接口
    # ============================================================

    @app.route('/api/flood/duty-leader', methods=['GET'])
    @protected
    def flood_get_duty_leader():
        if not FloodDutyLeader:
            return jsonify({'leader': None}), 200
        session = Session()
        try:
            today = datetime.date.today()
            start = datetime.datetime.combine(today, datetime.time.min)
            end = datetime.datetime.combine(today, datetime.time.max)
            leader = session.query(FloodDutyLeader).filter(
                FloodDutyLeader.duty_date >= start,
                FloodDutyLeader.duty_date <= end,
            ).first()
            if not leader:
                leader = session.query(FloodDutyLeader).order_by(FloodDutyLeader.id.desc()).first()
            if leader:
                result = {
                    'id': leader.id,
                    'title': leader.title,
                    'name': leader.name,
                    'phone': leader.phone,
                    'dutyDate': leader.duty_date.isoformat() if leader.duty_date else None,
                }
            else:
                result = None
            return jsonify({'leader': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/duty-leader', methods=['POST'])
    @protected
    def flood_save_duty_leader():
        if not FloodDutyLeader:
            return jsonify({'error': '带班领导模块未启用'}), 500
        session = Session()
        try:
            data = request.json
            today = datetime.date.today()
            start = datetime.datetime.combine(today, datetime.time.min)
            end = datetime.datetime.combine(today, datetime.time.max)
            leader = session.query(FloodDutyLeader).filter(
                FloodDutyLeader.duty_date >= start,
                FloodDutyLeader.duty_date <= end,
            ).first()
            if not leader:
                leader = session.query(FloodDutyLeader).order_by(FloodDutyLeader.id.desc()).first()
            if leader:
                leader.title = data.get('title', leader.title)
                leader.name = data.get('name', leader.name)
                leader.phone = data.get('phone', leader.phone)
                leader.duty_date = datetime.datetime.now()
            else:
                leader = FloodDutyLeader(
                    title=data.get('title', '带班领导'),
                    name=data.get('name', ''),
                    phone=data.get('phone', ''),
                    duty_date=datetime.datetime.now(),
                )
                session.add(leader)
            session.commit()
            return jsonify({'message': '带班领导已保存', 'id': leader.id}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ============================================================
    # 预警管理接口
    # ============================================================

    @app.route('/api/flood/warnings/active', methods=['GET'])
    @protected
    def flood_get_active_warning():
        """获取当前激活的预警状态"""
        if not FloodWarning:
            return jsonify({'warning': None}), 200
        session = Session()
        try:
            warning = session.query(FloodWarning).filter_by(status='active').first()
            if warning:
                result = {
                    'id': warning.id,
                    'level': warning.level,
                    'status': warning.status,
                    'startTime': warning.start_time.isoformat() if warning.start_time else None,
                }
            else:
                result = None
            return jsonify({'warning': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    def save_weather_snapshot(session):
        """保存当前天气快照到数据库"""
        try:
            weather_now = fetch_realtime_weather()
            if not weather_now:
                return
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
        except Exception as e:
            print(f"保存天气快照失败: {e}")

    @app.route('/api/flood/warnings/start', methods=['POST'])
    @protected
    def flood_start_warning():
        """启动预警"""
        if not FloodWarning:
            return jsonify({'error': '预警模块未启用'}), 500
        session = Session()
        try:
            data = request.json
            level = data.get('level', 'blue')
            if level not in ('blue', 'yellow', 'orange', 'red'):
                return jsonify({'error': '预警等级无效'}), 400

            # 结束当前激活的预警
            active = session.query(FloodWarning).filter_by(status='active').first()
            if active:
                active.status = 'ended'
                active.end_time = datetime.datetime.now()

            # 创建新预警
            now = datetime.datetime.now()
            warning = FloodWarning(
                level=level,
                status='active',
                start_time=now,
            )
            session.add(warning)
            session.flush()

            # 自动记录天气快照
            save_weather_snapshot(session)

            # 自动创建"预警发布"调度记录
            level_names = {'blue': '蓝色', 'yellow': '黄色', 'orange': '橙色', 'red': '红色'}
            dispatch = FloodDispatchRecord(
                record_type='预警发布',
                title=f'{level_names.get(level, level)}预警启动',
                content=f'{level_names.get(level, level)}预警于{now.strftime("%Y-%m-%d %H:%M")}启动',
                event_time=now,
                warning_id=warning.id,
                status='active',
            )
            session.add(dispatch)
            session.commit()
            return jsonify({'message': '预警已启动', 'id': warning.id, 'level': level}), 201
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/warnings/end', methods=['POST'])
    @protected
    def flood_end_warning():
        """结束预警"""
        if not FloodWarning:
            return jsonify({'error': '预警模块未启用'}), 500
        session = Session()
        try:
            active = session.query(FloodWarning).filter_by(status='active').first()
            if active:
                now = datetime.datetime.now()

                # ===== 先收集报告数据（在清空之前） =====
                # 带班领导
                duty_leader = None
                if FloodDutyLeader:
                    leader = session.query(FloodDutyLeader).order_by(FloodDutyLeader.id.desc()).first()
                    if leader and leader.name:
                        duty_leader = {
                            'title': leader.title,
                            'name': leader.name,
                            'phone': leader.phone,
                        }

                # 积水点
                water_points_data = []
                if FloodWaterloggingPoint:
                    water_points = session.query(FloodWaterloggingPoint).all()
                    for wp in water_points:
                        duty_persons = []
                        if wp.duty_persons:
                            try:
                                duty_persons = json.loads(wp.duty_persons)
                            except:
                                pass
                        water_points_data.append({
                            'name': wp.name,
                            'waterLevel': wp.water_level,
                            'waterDepth': wp.water_depth,
                            'dutyPersons': duty_persons,
                            'responsiblePerson': wp.responsible_person,
                            'responsiblePhone': wp.responsible_phone,
                        })

                # 调度记录
                records = session.query(FloodDispatchRecord).filter_by(warning_id=active.id).order_by(FloodDispatchRecord.event_time.asc()).all()
                type_stats = {}
                for r in records:
                    t = r.record_type or '其他'
                    type_stats[t] = type_stats.get(t, 0) + 1

                # 值班人员
                duty_shifts = []
                start_date = active.start_time.isoformat() if active.start_time else None
                end_date = now.isoformat()
                if FloodDutyShift:
                    shift_query = session.query(FloodDutyShift)
                    if start_date:
                        shift_query = shift_query.filter(FloodDutyShift.shift_date >= start_date)
                    if end_date:
                        shift_query = shift_query.filter(FloodDutyShift.shift_date <= end_date)
                    for s in shift_query.all():
                        duty_shifts.append({
                            'shiftDate': s.shift_date.isoformat() if s.shift_date else None,
                            'shiftName': s.shift_name,
                            'person1': s.person1,
                            'person1Phone': s.person1_phone,
                            'person2': s.person2,
                            'person2Phone': s.person2_phone,
                        })

                # 天气记录
                weather_summary = []
                if FloodWeatherRecord:
                    weather_records = session.query(FloodWeatherRecord).filter(
                        FloodWeatherRecord.recorded_at >= start_date,
                        FloodWeatherRecord.recorded_at <= end_date
                    ).order_by(FloodWeatherRecord.recorded_at.desc()).limit(50).all()
                    for wr in weather_records:
                        weather_summary.append({
                            'temperature': wr.temperature,
                            'humidity': wr.humidity,
                            'weatherText': wr.weather_text,
                            'rainfall1h': wr.rainfall_1h,
                            'windDirection': wr.wind_direction,
                            'windPower': wr.wind_power,
                            'recordedAt': wr.recorded_at.isoformat() if wr.recorded_at else None,
                        })

                # 降雨事件
                rain_events = []
                if FloodRainEvent:
                    rain_query = session.query(FloodRainEvent).filter(
                        FloodRainEvent.start_time >= start_date,
                        FloodRainEvent.start_time <= end_date
                    )
                    for e in rain_query.all():
                        rain_events.append({
                            'startTime': e.start_time.isoformat() if e.start_time else None,
                            'endTime': e.end_time.isoformat() if e.end_time else None,
                            'intensity': e.intensity,
                            'maxRainfall1h': e.max_rainfall_1h,
                        })

                # ===== 生成报告 =====
                report_data = {
                    'warning': {
                        'id': active.id,
                        'level': active.level,
                        'status': 'ended',
                        'startTime': active.start_time.isoformat() if active.start_time else None,
                        'endTime': now.isoformat(),
                    },
                    'dutyLeader': duty_leader,
                    'dutyShifts': duty_shifts,
                    'summary': {
                        'totalRecords': len(records),
                        'typeStats': type_stats,
                    },
                    'weatherSummary': weather_summary,
                    'waterPoints': water_points_data,
                    'records': [{
                        'id': r.id,
                        'recordType': r.record_type,
                        'content': r.content,
                        'eventTime': r.event_time.isoformat() if r.event_time else None,
                        'location': r.location,
                        'operator': r.operator,
                    } for r in records],
                    'rainEvents': rain_events,
                }
                report_text = generate_report_text(report_data)

                # ===== 更新预警状态并保存报告 =====
                active.status = 'ended'
                active.end_time = now
                active.report_snapshot = report_text

                # 自动创建"预警结束"调度记录
                level_names = {'blue': '蓝色', 'yellow': '黄色', 'orange': '橙色', 'red': '红色'}
                dispatch = FloodDispatchRecord(
                    record_type='预警结束',
                    title=f'{level_names.get(active.level, active.level)}预警结束',
                    content=f'{level_names.get(active.level, active.level)}预警于{now.strftime("%Y-%m-%d %H:%M")}结束',
                    event_time=now,
                    warning_id=active.id,
                    status='active',
                )
                session.add(dispatch)

                # 清空带班领导
                if FloodDutyLeader:
                    leader = session.query(FloodDutyLeader).order_by(FloodDutyLeader.id.desc()).first()
                    if leader:
                        leader.name = ''
                        leader.phone = ''

                # 将所有积水点水位归零
                if FloodWaterloggingPoint:
                    session.query(FloodWaterloggingPoint).update({
                        FloodWaterloggingPoint.water_depth: '0',
                        FloodWaterloggingPoint.water_level: 'normal',
                        FloodWaterloggingPoint.last_updated: now
                    })

                session.commit()
                return jsonify({'message': '预警已结束', 'report': report_text}), 200
            return jsonify({'message': '当前无激活预警'}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/flood/warnings/history', methods=['GET'])
    @protected
    def flood_warnings_history():
        """获取预警历史列表（含调度记录数）"""
        if not FloodWarning:
            return jsonify({'warnings': []}), 200
        session = Session()
        try:
            warnings = session.query(FloodWarning).order_by(FloodWarning.start_time.desc()).all()
            result = []
            for w in warnings:
                record_count = session.query(FloodDispatchRecord).filter_by(warning_id=w.id).count()
                result.append({
                    'id': w.id,
                    'level': w.level,
                    'status': w.status,
                    'startTime': w.start_time.isoformat() if w.start_time else None,
                    'endTime': w.end_time.isoformat() if w.end_time else None,
                    'recordCount': record_count,
                })
            return jsonify({'warnings': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    print("汛情值守路由注册成功")
