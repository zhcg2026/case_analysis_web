# -*- coding: utf-8 -*-
"""文件资料冒烟测试：CRUD + 附件 + 筛选，测试数据带标记精确清理"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import jwt
import app as app_module
from app import Session, NoticeDoc

SECRET = os.getenv('JWT_SECRET_KEY')
H = {'Authorization': 'Bearer ' + jwt.encode(
    {'user_id': 7, 'username': '值班员', 'role': 'user',
     'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')}
client = app_module.app.test_client()
MARK = '__smoke__'

def cleanup():
    with Session() as s:
        rows = s.query(NoticeDoc).filter(NoticeDoc.title.like('%' + MARK + '%')).all()
        for r in rows:
            s.delete(r)
        s.commit()
        return len(rows)

try:
    print('1) POST 添加(登录用户即可, 与台账模块一致)')
    r = client.post('/api/notice-docs', headers=H, json={
        'title': '关于某某路段开挖施工的通知' + MARK, 'tag': '暂不采集', 'source': '市城管局',
        'doc_date': '2026-09-14', 'content': '圣惠南路开挖施工，暂不采集。',
        'attachments': [{'name': '通知.pdf', 'path': '/uploads/abc.pdf'}], 'pinned': 1})
    print('  ', r.status_code, r.get_json()['doc']['title'])
    assert r.status_code == 201
    d1 = r.get_json()['doc']['id']

    print('2) POST 标题必填 -> 400')
    r = client.post('/api/notice-docs', headers=H, json={'title': '', 'tag': 'x'})
    print('  ', r.status_code, r.get_json())
    assert r.status_code == 400

    print('3) PUT 修改(含附件更新)')
    r = client.put(f'/api/notice-docs/{d1}', headers=H, json={
        'title': '关于某某事项不考核的通知' + MARK, 'tag': '考核豁免', 'source': '考核办',
        'doc_date': '2026-09-10', 'content': '门头招牌整治事项不考核。',
        'attachments': [{'name': '通知.pdf', 'path': '/uploads/abc.pdf'}, {'name': '细则.docx', 'path': '/uploads/def.docx'}],
        'pinned': 0})
    d = r.get_json()['doc']
    print('  ', r.status_code, d['tag'], 'attachments:', len(d['attachments']))
    assert r.status_code == 200 and len(d['attachments']) == 2

    print('4) GET 列表 + keyword/tag 筛选')
    r = client.get('/api/notice-docs', headers=H, json=None)
    # test client GET 不支持 json；直接拼参数
    r = client.get('/api/notice-docs?keyword=不考核', headers=H)
    rows = r.get_json()['docs']
    print('  keyword筛选:', len(rows), [x['title'][:12] for x in rows])
    assert any(x['id'] == d1 for x in rows)
    r = client.get('/api/notice-docs?tag=考核豁免', headers=H)
    assert any(x['id'] == d1 for x in r.get_json()['docs'])
    r = client.get('/api/notice-docs?tag=采集豁免', headers=H)
    assert not any(x['id'] == d1 for x in r.get_json()['docs'])

    print('5) DELETE')
    r = client.delete(f'/api/notice-docs/{d1}', headers=H)
    print('  ', r.status_code)
    assert r.status_code == 200

    print('\nALL 5 NOTICE-DOC SMOKE TESTS PASSED')
finally:
    n = cleanup()
    with Session() as s:
        print(f'cleanup: removed {n}, remaining {s.query(NoticeDoc).count()}')
