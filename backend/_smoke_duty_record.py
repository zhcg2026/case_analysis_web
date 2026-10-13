# -*- coding: utf-8 -*-
"""值班记录接口冒烟测试：forged JWT + Flask test client，跑完即清库"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import jwt
import app as app_module

SECRET = os.getenv('JWT_SECRET_KEY')
TODAY = datetime.date.today()
today = datetime.date(2000, 9, 13)  # 专用测试日期(2000年), 避免触碰用户真实录入.isoformat()
H_ADMIN = {'Authorization': 'Bearer ' + jwt.encode(
    {'user_id': 1, 'username': 'admin', 'role': 'admin',
     'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')}
H_USER = {'Authorization': 'Bearer ' + jwt.encode(
    {'user_id': 7, 'username': '值班员', 'role': 'user',
     'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')}
client = app_module.app.test_client()

print('1) POST 白班记录(user)')
payload_day = {
    'date': today.isoformat(), 'shift': '白班', 'members': '展晓瑞、李瑞瑶', 'is_normal': False,
    'note': '8:57 系统故障',
    'stats': {'stat_reported': 740, 'stat_accepted': 723, 'stat_completed': 666,
              'src_collector': 677, 'src_patrol': 0, 'src_12345': 15, 'src_minhu': 0,
              'src_video': 39, 'src_ai': 0, 'src_public': 1},
    'events': [
        {'category': '关注问题', 'ticket_no': '202609110661', 'location': '涑水东街河东码头西侧非机动车道',
         'description': '污水井盖污水外溢', 'timeline': [{'time': '14:03', 'text': '12345热线反映'}],
         'result': '已电话对接排水裴健核实，案件派遣至排水服务中心'},
    ],
}
r = client.post('/api/duty-record', headers=H_USER, json=payload_day)
print('  ', r.status_code, r.get_json()['record']['shift'], 'events:', len(r.get_json()['record']['events']))
assert r.status_code == 200 and len(r.get_json()['record']['events']) == 1
day_id = r.get_json()['record']['id']

print('2) POST 夜班记录 一切正常(user)')
r = client.post('/api/duty-record', headers=H_USER, json={
    'date': today.isoformat(), 'shift': '夜班', 'members': '王康乐', 'is_normal': True, 'note': '', 'stats': {}, 'events': []
})
print('  ', r.status_code, r.get_json()['record']['is_normal'])
assert r.status_code == 200 and r.get_json()['record']['is_normal'] == 1

print('3) POST 夜班记录 改为有事件(覆盖同一记录)')
r = client.post('/api/duty-record', headers=H_USER, json={
    'date': today.isoformat(), 'shift': '夜班', 'members': '王康乐', 'is_normal': False,
    'stats': {},
    'events': [
        {'category': '12345', 'ticket_no': '44', 'caller_name': '刘先生', 'caller_phone': '17203599998',
         'location': '城市花园小区东门桥洞', 'description': '路面有石子，市民骑车摔倒',
         'timeline': [{'time': '22:47', 'text': '来电反映'}, {'time': '22:51', 'text': '联系环卫周秀枝主任'},
                      {'time': '6:03', 'text': '次日清晨环卫已清理'}],
         'result': '已回复12345'},
        {'category': '市民来电', 'caller_name': '蔺女士', 'caller_phone': '15582961781',
         'location': '盐湖城小区加油站附近', 'description': '垃圾桶冒烟',
         'timeline': [{'time': '7:40', 'text': '来电反映'}, {'time': '7:44', 'text': '联系环卫，已派人处理'}],
         'result': '已回复市民'},
    ],
})
rec = r.get_json()['record']
print('  ', r.status_code, 'events:', len(rec['events']), 'timeline[0]:', rec['events'][0]['timeline'])
assert r.status_code == 200 and len(rec['events']) == 2
assert [t['time'] for t in rec['events'][0]['timeline']] == ['22:47', '22:51', '06:03']  # 全角冒号规整

print('4) admin 修改 user 的记录 -> 200')
r = client.post('/api/duty-record', headers=H_ADMIN, json={
    'date': today.isoformat(), 'shift': '白班', 'members': '展晓瑞、李瑞瑶、茹佳兆', 'stats': payload_day['stats'], 'events': payload_day['events'], 'note': ''
})
assert r.status_code == 200 and r.get_json()['record']['members'].endswith('茹佳兆')

print('5) user2 修改 user 的白班记录 -> 403')
H_USER2 = {'Authorization': 'Bearer ' + jwt.encode(
    {'user_id': 8, 'username': '别人', 'role': 'user',
     'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')}
r = client.post('/api/duty-record', headers=H_USER2, json={'date': today.isoformat(), 'shift': '白班', 'members': 'x'})
print('  ', r.status_code, r.get_json())
assert r.status_code == 403

print('6) GET month')
month = today.isoformat()[:7]
r = client.get(f'/api/duty-record/month?month={month}', headers=H_ADMIN)
data = r.get_json()
print('  ', r.status_code, 'records:', len(data['records']))
assert r.status_code == 200 and len(data['records']) == 2

print('7) GET status')
r = client.get(f'/api/duty-record/status?date={today}', headers=H_ADMIN)
d = r.get_json()
print('  ', r.status_code, d)
assert d['白班']['filled'] and d['夜班']['filled'] and d['夜班']['is_normal'] == 0

print('8) GET /api/duty/roster (带出值班人员)')
r = client.post('/api/duty/upload', headers=H_ADMIN, json={'text': f'{today.isoformat()} 白班：张三、李四，夜班：赵六', 'mode': 'replace'})
# 直接用日期写法避免解析歧义
r = client.post('/api/duty/upload', headers=H_ADMIN, json={'text': f'{today} 白班：张三、李四，夜班：赵六', 'mode': 'replace'})
assert r.get_json()['inserted'] == 2, r.get_json()
r = client.get(f'/api/duty/roster?date={today}', headers=H_ADMIN)
d = r.get_json()
print('  ', r.status_code, [(s['shift'], s['members']) for s in d['shifts']])
assert [(s['shift'], s['members']) for s in d['shifts']] == [('白班', ['张三', '李四']), ('夜班', ['赵六'])]

print('9) DELETE 记录 需admin (user -> 403)')
night_id = [x for x in data['records'] if x['shift'] == '夜班'][0]['id']
r = client.delete(f'/api/duty-record/{night_id}', headers=H_USER)
print('  ', r.status_code)
assert r.status_code == 403
r = client.delete(f'/api/duty-record/{night_id}', headers=H_ADMIN)
print('  ', r.status_code, r.get_json())
assert r.status_code == 200

print('10) 清理(只删2000年测试数据, 不动用户录入)')
from app import Session as _S, DutyRecord as _DR, DutyRecordEvent as _DRE, DutySchedule as _DS
with _S() as _s:
    ids = [x.id for x in _s.query(_DR).filter(_DR.record_date < datetime.date(2020, 1, 1)).all()]
    for i in ids:
        _s.query(_DRE).filter_by(record_id=i).delete()
    _s.query(_DR).filter(_DR.record_date < datetime.date(2020, 1, 1)).delete(synchronize_session=False)
    _s.query(_DS).filter(_DS.duty_date < datetime.date(2020, 1, 1)).delete(synchronize_session=False)
    _s.commit()
r = client.get(f'/api/duty-record/day?date={today}', headers=H_ADMIN)
assert len(r.get_json()['records']) == 0

print('\nALL 10 DUTY-RECORD SMOKE TESTS PASSED')
