import os
import time
import datetime
import requests
import json
from dotenv import load_dotenv

# 加载环境变量
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
elif os.path.exists('../.env.local'):
    load_dotenv('../.env.local')
load_dotenv()

QWEATHER_API_KEY = os.getenv('QWEATHER_API_KEY', '')
QWEATHER_API_HOST = os.getenv('QWEATHER_API_HOST', 'n77h2twnn4.re.qweatherapi.com')
QWEATHER_BASE_URL = f'https://{QWEATHER_API_HOST}/v7'
YUNCHENG_LOCATION = '110.976935,35.06161'

# 天气数据内存缓存
_weather_cache = {'data': None, 'timestamp': 0}
_hourly_cache = {'data': None, 'timestamp': 0}
_satellite_cache = {'data': None, 'timestamp': 0}
_alert_cache = {'data': None, 'timestamp': 0}
CACHE_TTL = 300  # 5分钟缓存
SATELLITE_CACHE_TTL = 600  # 10分钟缓存（卫星云图更新频率较低）
ALERT_CACHE_TTL = 300  # 5分钟缓存（预警数据）


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


def fetch_weather_alerts():
    """获取气象预警信息（和风天气 天气预警API v1）
    API路径: GET /weatheralert/v1/current/{latitude}/{longitude}
    文档: https://dev.qweather.com/docs/api/weather-alert/
    """
    now = time.time()
    if _alert_cache['data'] and (now - _alert_cache['timestamp']) < ALERT_CACHE_TTL:
        return _alert_cache['data']

    try:
        # 运城坐标: 纬度35.06, 经度110.98
        lat, lon = YUNCHENG_LOCATION.split(',')
        # 使用天气预警API v1
        alert_url = f'https://{QWEATHER_API_HOST}/weatheralert/v1/current/{lat}/{lon}'
        params = {
            'key': QWEATHER_API_KEY,
            'lang': 'zh',
            'localTime': 'true'
        }
        resp = requests.get(alert_url, params=params, timeout=10)
        data = resp.json()
        if data.get('code') == '200':
            alerts = data.get('alert', [])
            result = []
            for alert in alerts:
                result.append({
                    'id': alert.get('id', ''),
                    'sender': alert.get('sender', ''),
                    'title': alert.get('title', ''),
                    'startTime': alert.get('startTime', ''),
                    'endTime': alert.get('endTime', ''),
                    'status': alert.get('status', ''),
                    'level': alert.get('level', ''),
                    'type': alert.get('type', ''),
                    'text': alert.get('text', ''),
                })
            _alert_cache['data'] = result
            _alert_cache['timestamp'] = now
            return result
    except Exception as e:
        print(f'获取气象预警失败: {e}')
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


def fetch_satellite_image():
    """
    获取卫星云图（中央气象台风云四号B星）
    返回: { url, updateTime, type } 或 None
    """
    now = time.time()
    if _satellite_cache['data'] and (now - _satellite_cache['timestamp']) < SATELLITE_CACHE_TTL:
        return _satellite_cache['data']

    try:
        now_time = datetime.datetime.now()

        # 中央气象台风云四号B星卫星云图
        # URL格式: https://image.nmc.cn/product/{date}/WXBL/medium/SEVP_NSMC_WXBL_FY4B_ETCC_ACHN_LNO_PY_{timestamp}000000.JPG
        # 时间戳格式: YYYYMMDDHHMMSSSSSS（如 20260707003000000）
        date_str = now_time.strftime('%Y/%m/%d')
        hour = now_time.strftime('%H')

        # 生成最近几个时间点的URL（每15分钟一张）
        satellite_urls = []
        for minutes in [30, 15, 0]:
            ts = f"{now_time.strftime('%Y%m%d')}{hour}{minutes:02d}000000"
            url = f'https://image.nmc.cn/product/{date_str}/WXBL/medium/SEVP_NSMC_WXBL_FY4B_ETCC_ACHN_LNO_PY_{ts}.JPG'
            satellite_urls.append(url)

        result = {
            'urls': satellite_urls,
            'updateTime': now_time.strftime('%Y-%m-%d %H:%M'),
            'source': '中央气象台风云四号B星'
        }

        _satellite_cache['data'] = result
        _satellite_cache['timestamp'] = now
        return result

    except Exception as e:
        print(f'获取卫星云图失败: {e}')
    return None


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

    # 今日
    today_start = datetime.datetime.combine(target_date, datetime.time.min)
    today_end = datetime.datetime.combine(target_date, datetime.time.max)
    today_assignments = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= today_start,
        FloodDutyAssignment.assignment_date <= today_end,
    ).all()
    on_duty_today = {a.person_name for a in today_assignments}

    # 明天
    tomorrow = target_date + datetime.timedelta(days=1)
    tomorrow_start = datetime.datetime.combine(tomorrow, datetime.time.min)
    tomorrow_end = datetime.datetime.combine(tomorrow, datetime.time.max)
    tomorrow_assignments = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= tomorrow_start,
        FloodDutyAssignment.assignment_date <= tomorrow_end,
    ).all()
    on_duty_tomorrow = {a.person_name for a in tomorrow_assignments}

    # 昨晚夜班（刚下班）
    yesterday = target_date - datetime.timedelta(days=1)
    yesterday_start = datetime.datetime.combine(yesterday, datetime.time.min)
    yesterday_end = datetime.datetime.combine(yesterday, datetime.time.max)
    last_night_shift = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= yesterday_start,
        FloodDutyAssignment.assignment_date <= yesterday_end,
        FloodDutyAssignment.shift_name == '夜班',
    ).all()
    just_finished_night = {a.person_name for a in last_night_shift}

    # 今晚夜班（晚上要上班）
    tonight_shift = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= today_start,
        FloodDutyAssignment.assignment_date <= today_end,
        FloodDutyAssignment.shift_name == '夜班',
    ).all()
    tonight_night_shift = {a.person_name for a in tonight_shift}

    # 明晚夜班（明晚要上班，今天叫来也累）
    tomorrow_night = session.query(FloodDutyAssignment).filter(
        FloodDutyAssignment.assignment_date >= tomorrow_start,
        FloodDutyAssignment.assignment_date <= tomorrow_end,
        FloodDutyAssignment.shift_name == '夜班',
    ).all()
    tomorrow_night_shift = {a.person_name for a in tomorrow_night}

    # 获取近7天增援记录
    seven_days_ago_dt = datetime.datetime.combine(seven_days_ago, datetime.time.min)
    recent_additions = session.query(FloodStaffingLog).filter(
        FloodStaffingLog.created_at >= seven_days_ago_dt,
        FloodStaffingLog.status.in_(['recommended', 'confirmed']),
    ).all()
    addition_count = {}
    for log in recent_additions:
        addition_count[log.recommended_person] = addition_count.get(log.recommended_person, 0) + 1

    # 筛选候选人
    candidates = []
    for person in all_persons:
        name = person.name

        # 硬约束：排除夜班疲劳 + 明天白班的AB组人员
        if name in just_finished_night:
            continue
        if name in tonight_night_shift:
            continue
        if name in tomorrow_night_shift:
            continue
        # AB组人员如果明天有白班，排除（行政人员明天上班不排除）
        if person.group_type in ('group_a', 'group_b') and name in on_duty_tomorrow:
            continue

        # 轮流排序：近7天被增援次数越少越优先，同次数随机
        score = addition_count.get(name, 0) * 100

        candidates.append({
            'name': name,
            'phone': person.phone,
            'group_type': person.group_type,
            'score': score,
            'recent_additions': addition_count.get(name, 0),
        })

    if not candidates:
        return None

    # 排序并选最优（同分时随机选一个，避免总是同一个人）
    import random
    candidates.sort(key=lambda x: (x['score'], random.random()))
    best = candidates[0]

    # 生成推荐理由
    if best['recent_additions'] == 0:
        best['reason'] = '近7天未被增援，轮空优先'
    else:
        best['reason'] = f'近7天已被增援{best["recent_additions"]}次，增援次数最少'

    return best
