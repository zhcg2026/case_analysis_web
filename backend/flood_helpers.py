import os
import time
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
