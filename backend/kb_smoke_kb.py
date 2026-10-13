# -*- coding: utf-8 -*-
"""知识库问答修复·API 冒烟测试（容器内执行）

    docker exec case-analysis-web python backend/kb_smoke_kb.py

用 helpers.generate_token 合成 admin/普通用户 token（与仓库 _smoke_*.py 同模式），
验证：ask 结构化返回 + log_id、feedback 回写、admin/logs 汇总、search similarity 字段、
need_location 分支。只读+一条 feedback 写入，不动业务数据。
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

BASE = 'http://127.0.0.1:5000'


def _req(method, path, body=None, token=None, timeout=300):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode('utf-8') if body is not None else None,
        headers={'Content-Type': 'application/json',
                 **({'Authorization': f'Bearer {token}'} if token else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def main():
    from helpers import generate_token
    admin = generate_token(1, 'smoke_admin', 'admin')
    user = generate_token(999, 'smoke_user', 'user')

    ok = True

    def check(name, cond, detail=''):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ''))
        if not cond:
            ok = False

    print('== 1) /api/kb/ask 结构化返回 ==')
    st, r = _req('POST', '/api/kb/ask',
                 {'question': '在哪里交水费', 'history': [
                     {'role': 'user', 'content': '你好'},
                     {'role': 'assistant', 'content': '您好，请讲'}]}, token=user)
    check('http 200', st == 200)
    for k in ('answer', 'citations', 'retrieved', 'log_id', 'need_location', 'degraded'):
        check(f'返回含 {k}', k in r)
    check('answer 非空', bool(r.get('answer')))
    check('citations 标题来自召回',
          all(c.get('title') in {h.get('title') for h in r.get('retrieved') or []}
              for c in r.get('citations') or []),
          str([c.get('title') for c in r.get('citations') or []]))
    check('log_id 已生成', isinstance(r.get('log_id'), int), f"log_id={r.get('log_id')}")
    check('degraded=False', r.get('degraded') is False)
    log_id = r.get('log_id')

    print('== 2) /api/kb/search similarity 字段 ==')
    st, r = _req('POST', '/api/kb/search', {'query': '井盖破损的立案条件'}, token=user)
    results = r.get('results') or []
    check('有结果', len(results) > 0)
    sims = [x.get('similarity') for x in results if isinstance(x.get('similarity'), (int, float))]
    check('向量命中带 0~1 相似度', all(0 <= s <= 1 for s in sims), f'sim={sims[:3]}')

    print('== 3) /api/kb/feedback 回写 ==')
    st, r = _req('POST', '/api/kb/feedback', {'log_id': log_id, 'useful': True}, token=user)
    check('saved=True', r.get('saved') is True, json.dumps(r, ensure_ascii=False))

    print('== 4) /api/kb/admin/logs 汇总 ==')
    st, r = _req('GET', '/api/kb/admin/logs?page=1&page_size=10', token=admin)
    s = r.get('summary') or {}
    check('available=True', r.get('available') is True)
    check('total>=1', (s.get('total') or 0) >= 1, f"total={s.get('total')}")
    check('useful>=1', (s.get('useful') or 0) >= 1, f"useful={s.get('useful')}")
    check('top_questions 非空', len(r.get('top_questions') or []) > 0)
    mine = [it for it in r.get('items') or [] if it.get('id') == log_id]
    check('明细含本次提问', bool(mine))
    if mine:
        it = mine[0]
        check('明细 feedback=1', it.get('feedback') == 1)
        check('明细 json_ok=1', it.get('json_ok') == 1, f"json_ok={it.get('json_ok')}")
        check('明细 username 记录', it.get('username') == 'smoke_user', f"username={it.get('username')}")

    print('== 5) admin/logs 权限（普通用户应 403） ==')
    try:
        st, r = _req('GET', '/api/kb/admin/logs', token=user)
        check('普通用户被拒', False, f'status={st}')
    except urllib.error.HTTPError as e:
        check('普通用户 403', e.code == 403, f'code={e.code}')

    print('== 6) need_location 分支 ==')
    st, r = _req('POST', '/api/kb/ask', {'question': '盐湖区中银大道与河东东街交叉口的道路破损归哪个部门管'}, token=user)
    check('返回 need_location 字段', 'need_location' in r)
    check('缺坐标时 need_location=True', r.get('need_location') is True,
          f"need_location={r.get('need_location')} message={str(r.get('message'))[:40]}")
    st, r2 = _req('POST', '/api/kb/ask',
                  {'question': '盐湖区中银大道与河东东街交叉口的道路破损归哪个部门管',
                   'location': {'lng': 110.98, 'lat': 35.06}}, token=user)
    check('带坐标后可正常作答', bool(r2.get('answer')) and r2.get('need_location') is False)
    check('带坐标有派单结果', bool(r2.get('dispatch')), json.dumps(r2.get('dispatch') or {}, ensure_ascii=False)[:120])

    print()
    print('SMOKE ' + ('ALL PASS' if ok else 'HAS FAILURES'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
