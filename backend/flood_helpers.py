import os
import time
import datetime
import requests

QWEATHER_API_KEY = os.getenv('QWEATHER_API_KEY', '')
QWEATHER_API_HOST = os.getenv('QWEATHER_API_HOST', 'n77h2twnn4.re.qweatherapi.com')
QWEATHER_BASE_URL = f'https://{QWEATHER_API_HOST}/v7'
YUNCHENG_LOCATION = '110.976935,35.06161'

# 天气数据内存缓存
_weather_cache = {'data': None, 'timestamp': 0}
_hourly_cache = {'data': None, 'timestamp': 0}
CACHE_TTL = 300  # 5分钟缓存


def fetch_realtime_weather():
    """获取实时天气（和风天气 API v7）"""
    now = time.time()
    if _weather_cache['data'] and (now - _weather_cache['timestamp']) < CACHE_TTL:
        return _weather_cache['data']

    try:
        resp = requests.get(
            f'{QWEATHER_BASE_URL}/weather/now',
            params={'location': YUNCHENG_LOCATION, 'key': QWEATHER_API_KEY},
            timeout=10
        )
        data = resp.json()
        if data.get('code') == '200':
            result = data.get('now', {})
            _weather_cache['data'] = result
            _weather_cache['timestamp'] = now
            return result
    except Exception as e:
        print(f'获取实时天气失败: {e}')
    return None


def fetch_hourly_forecast():
    """获取24小时逐小时预报"""
    now = time.time()
    if _hourly_cache['data'] and (now - _hourly_cache['timestamp']) < CACHE_TTL:
        return _hourly_cache['data']

    try:
        resp = requests.get(
            f'{QWEATHER_BASE_URL}/weather/24h',
            params={'location': YUNCHENG_LOCATION, 'key': QWEATHER_API_KEY},
            timeout=10
        )
        data = resp.json()
        if data.get('code') == '200':
            hourly = data.get('hourly', [])
            _hourly_cache['data'] = hourly
            _hourly_cache['timestamp'] = now
            return hourly
    except Exception as e:
        print(f'获取逐小时预报失败: {e}')
    return []


def determine_rain_intensity(rainfall_mm):
    """根据1小时降雨量判断降雨强度等级"""
    try:
        val = float(rainfall_mm) if rainfall_mm else 0
    except (ValueError, TypeError):
        val = 0
    if val <= 0:
        return '无雨'
    elif val < 2.5:
        return '小雨'
    elif val < 8:
        return '中雨'
    elif val < 16:
        return '大雨'
    elif val < 50:
        return '暴雨'
    else:
        return '大暴雨'


def determine_water_level(depth_cm):
    """根据水位深度判断积水等级"""
    try:
        val = float(depth_cm) if depth_cm else 0
    except (ValueError, TypeError):
        val = 0
    if val <= 0:
        return 'normal'
    elif val < 30:
        return 'shallow'
    elif val < 50:
        return 'medium'
    elif val < 80:
        return 'deep'
    else:
        return 'severe'


def serialize_weather(weather_now):
    """序列化天气数据为标准格式"""
    if not weather_now:
        return None
    return {
        'temperature': weather_now.get('temp', ''),
        'feelsLike': weather_now.get('feelsLike', ''),
        'humidity': weather_now.get('humidity', ''),
        'windDir': weather_now.get('windDir', ''),
        'windScale': weather_now.get('windScale', ''),
        'windSpeed': weather_now.get('windSpeed', ''),
        'text': weather_now.get('text', ''),
        'icon': weather_now.get('icon', ''),
        'precip': weather_now.get('precip', '0'),
    }


def serialize_hourly_forecast(hourly_list):
    """序列化逐小时预报数据"""
    if not hourly_list:
        return []
    result = []
    for h in hourly_list[:24]:
        result.append({
            'time': h.get('fxTime', ''),
            'temp': h.get('temp', ''),
            'text': h.get('text', ''),
            'icon': h.get('icon', ''),
            'windDir': h.get('windDir', ''),
            'windScale': h.get('windScale', ''),
            'humidity': h.get('humidity', ''),
            'precip': h.get('precip', '0'),
        })
    return result


def recommend_additional_staff(session, FloodPersonnel, FloodDutyAssignment, FloodStaffingLog, target_time=None):
    """
    预警增援推荐算法
    返回: { name, phone, reason, score } 或 None
    """
    if target_time is None:
        target_time = datetime.datetime.now()

    target_date = target_time.date()
    yesterday = target_date - datetime.timedelta(days=1)
    seven_days_ago = target_date - datetime.timedelta(days=7)

    # 获取全量花名册
    all_persons = session.query(FloodPersonnel).filter_by(is_active=True).all()

    # 获取今日排班（已确定在岗的人）
    today_start = datetime.datetime.combine(target_date, datetime.time.min)
    today_end = datetime.datetime.combine(target_date, datetime.time.max)
    today_assignments = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= today_start,
        FloodDutyAssignment.assignment_date <= today_end,
    ).all()
    on_duty_today = {a.person_name for a in today_assignments}

    # 获取昨晚夜班人员（刚下班的）
    yesterday_start = datetime.datetime.combine(yesterday, datetime.time.min)
    yesterday_end = datetime.datetime.combine(yesterday, datetime.time.max)
    last_night_shift = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= yesterday_start,
        FloodDutyAssignment.assignment_date <= yesterday_end,
        FloodDutyAssignment.shift_name == '夜班',
    ).all()
    just_finished_night = {a.person_name for a in last_night_shift}

    # 获取今晚夜班人员（晚上要上班的）
    tonight_shift = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= today_start,
        FloodDutyAssignment.assignment_date <= today_end,
        FloodDutyAssignment.shift_name == '夜班',
    ).all()
    tonight_night_shift = {a.person_name for a in tonight_shift}

    # 获取近7天增援记录
    seven_days_ago_dt = datetime.datetime.combine(seven_days_ago, datetime.time.min)
    recent_additions = session.query(FloodStaffingLog).filter(
        FloodStaffingLog.created_at >= seven_days_ago_dt,
        FloodStaffingLog.status.in_(['recommended', 'confirmed']),
    ).all()
    addition_count = {}
    for log in recent_additions:
        addition_count[log.recommended_person] = addition_count.get(log.recommended_person, 0) + 1

    # 获取近7天总工作天数
    recent_work_days = {}
    recent_assignments = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= seven_days_ago_dt,
    ).all()
    for a in recent_assignments:
        recent_work_days[a.person_name] = recent_work_days.get(a.person_name, 0) + 1

    # 筛选候选人
    candidates = []
    for person in all_persons:
        name = person.name

        # 硬约束排除
        if name in on_duty_today:
            continue
        if name in tonight_night_shift:
            continue
        if name in just_finished_night:
            continue

        # 计算得分（越低越优先）
        score = 0
        score += addition_count.get(name, 0) * 100
        score += recent_work_days.get(name, 0) * 20

        candidates.append({
            'name': name,
            'phone': person.phone,
            'group_type': person.group_type,
            'score': score,
            'recent_additions': addition_count.get(name, 0),
            'recent_work_days': recent_work_days.get(name, 0),
        })

    if not candidates:
        return None

    # 排序并选最优
    candidates.sort(key=lambda x: x['score'])
    best = candidates[0]

    # 生成推荐理由
    reason_parts = []
    if best['recent_additions'] == 0:
        reason_parts.append('近7天未被增援')
    else:
        reason_parts.append(f'近7天已被增援{best["recent_additions"]}次')
    reason_parts.append(f'近7天工作{best["recent_work_days"]}天')

    best['reason'] = '；'.join(reason_parts)

    return best
