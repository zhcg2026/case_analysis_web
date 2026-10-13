# -*- coding: utf-8 -*-
"""特殊事项处置对照冒烟测试：专用测试数据，结尾只删自己建的行"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import jwt
import app as app_module
from app import Session, SpecialMatter

SECRET = os.getenv('JWT_SECRET_KEY')
H_ADMIN = {'Authorization': 'Bearer ' + jwt.encode(
    {'user_id': 1, 'username': 'admin', 'role': 'admin',
     'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')}
H_USER = {'Authorization': 'Bearer ' + jwt.encode(
    {'user_id': 7, 'username': '值班员', 'role': 'user',
     'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')}
client = app_module.app.test_client()
MARK = '__smoke__'  # 测试数据标记, 结尾按备注精确清理

try:
    print('1) POST 添加(admin)')
    r = client.post('/api/special-matters', headers=H_ADMIN, json={
        'matter': '圣惠南路' + MARK, 'dept': '市政工程部', 'contact': '裴健',
        'phone': '13800000000', 'note': '未移交，暂由市政工程部负责'})
    print('  ', r.status_code, r.get_json()['matter'])
    assert r.status_code == 201
    mid = r.get_json()['matter']['id']

    print('2) POST 添加(user) -> 403')
    r = client.post('/api/special-matters', headers=H_USER, json={'matter': 'x', 'dept': 'y'})
    print('  ', r.status_code)
    assert r.status_code == 403

    print('3) GET 列表(登录用户可见)')
    r = client.get('/api/special-matters', headers=H_USER)
    rows = r.get_json()['matters']
    mine = [x for x in rows if x['id'] == mid][0]
    print('  ', r.status_code, 'total:', len(rows), '|', mine['matter'], '->', mine['dept'], mine['contact'])
    assert r.status_code == 200 and mine['dept'] == '市政工程部'

    print('4) PUT 修改(admin)')
    r = client.put(f'/api/special-matters/{mid}', headers=H_ADMIN, json={
        'matter': '双桥路' + MARK, 'dept': '市政技术部', 'contact': '', 'phone': '', 'note': ''})
    print('  ', r.status_code, r.get_json()['matter']['dept'])
    assert r.status_code == 200 and r.get_json()['matter']['dept'] == '市政技术部'

    print('5) PUT 修改(user) -> 403')
    r = client.put(f'/api/special-matters/{mid}', headers=H_USER, json={'matter': 'x', 'dept': 'y'})
    assert r.status_code == 403

    print('6) 必填校验 -> 400')
    r = client.post('/api/special-matters', headers=H_ADMIN, json={'matter': '', 'dept': ''})
    print('  ', r.status_code, r.get_json())
    assert r.status_code == 400

    print('7) DELETE(user) -> 403, DELETE(admin) -> 200')
    assert client.delete(f'/api/special-matters/{mid}', headers=H_USER).status_code == 403
    r = client.delete(f'/api/special-matters/{mid}', headers=H_ADMIN)
    print('  ', r.status_code)
    assert r.status_code == 200

    print('\nALL 7 SPECIAL-MATTER SMOKE TESTS PASSED')
finally:
    # 只删带标记的测试行, 不动用户数据
    with Session() as s:
        n = s.query(SpecialMatter).filter(SpecialMatter.note.like('%' + MARK + '%')).delete(synchronize_session=False)
        n += s.query(SpecialMatter).filter(SpecialMatter.matter.like('%' + MARK + '%')).delete(synchronize_session=False)
        s.commit()
        print(f'cleanup: removed {n} test rows, remaining {s.query(SpecialMatter).count()}')
