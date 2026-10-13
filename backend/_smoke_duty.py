# -*- coding: utf-8 -*-
"""值班表接口冒烟测试：forged JWT + Flask test client，跑完即清库"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import jwt
import app as app_module
from app import Session as _S, DutySchedule as _DS
TEST_YEAR = 2000  # 专用测试年份, 避免触碰用户真实录入

SECRET = os.getenv('JWT_SECRET_KEY')
token = jwt.encode({'user_id': 1, 'username': 'admin', 'role': 'admin',
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')
H = {'Authorization': f'Bearer {token}'}
client = app_module.app.test_client()

print('1) GET /api/duty/today (admin token)')
r = client.get('/api/duty/today', headers=H)
print('  ', r.status_code, r.get_json())
assert r.status_code == 200

print('2) GET /api/duty/today without token -> 401')
r = client.get('/api/duty/today')
print('  ', r.status_code, r.get_json())
assert r.status_code == 401

print('3) POST /api/duty/preview')
text = '2000-9-13 白班：张三、李四、王五，夜班：赵六\n2000-9-14 白班：王五，夜班：张三'
r = client.post('/api/duty/preview', headers=H, json={'text': text})
print('  ', r.status_code, r.get_json())
assert r.status_code == 200 and r.get_json()['total'] == 4

print('4) POST /api/duty/upload replace (含一条节假日)')
text2 = text + '\n2000-10-1（国庆节） 白班：张三'
r = client.post('/api/duty/upload', headers=H, json={'text': text2, 'mode': 'replace'})
print('  ', r.status_code, {k: v for k, v in r.get_json().items() if k != 'entries'})
assert r.status_code == 200 and r.get_json()['inserted'] == 5

print('5) GET /api/duty/schedule list')
r = client.get('/api/duty/schedule', headers=H)
data = r.get_json()
print('  ', r.status_code, 'entries:', len(data['entries']), 'first:', data['entries'][0])
assert len(data['entries']) == 5

print('6) GET /api/duty/roster reflects schedule (测试日期2000-9-13)')
r = client.get('/api/duty/roster?date=2000-09-13', headers=H)
d = r.get_json()
print('  ', r.status_code, d)
assert [(x['shift'], x['members']) for x in d['shifts']] == [('白班', ['张三', '李四', '王五']), ('夜班', ['赵六'])]

print('7) DELETE single entry')
eid = [e for e in data['entries'] if e['note']][0]['id']
r = client.delete(f'/api/duty/schedule/{eid}', headers=H)
print('  ', r.status_code, r.get_json())
assert r.status_code == 200

print('8) POST /api/duty/upload append')
r = client.post('/api/duty/upload', headers=H, json={'text': '2000-9-20 白班：钱七', 'mode': 'append'})
print('  ', r.status_code, r.get_json()['inserted'])
assert r.get_json()['inserted'] == 1

print('9) POST bad text -> 400')
r = client.post('/api/duty/upload', headers=H, json={'text': '无班次无日期的乱文本'})
print('  ', r.status_code, r.get_json())
assert r.status_code == 400

print('10) 清理(只删2000年测试数据, 不动用户录入)')
with _S() as _s:
    n = _s.query(_DS).filter(_DS.duty_date < datetime.date(2020, 1, 1)).delete(synchronize_session=False)
    _s.commit()
print('   deleted', n)
assert n > 0

print('\nALL 10 SMOKE TESTS PASSED')
