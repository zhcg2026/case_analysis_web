# -*- coding: utf-8 -*-
"""创文「数据分析」接口本地验证：forged JWT + Flask test client + 合成数据。

覆盖：spot/road/dept 三维度榜单、点位×类型交叉榜、按天趋势、占比分母口径、
空区间、单日口径、非法区间（只传一端/起晚于止/超一年）、无 token 401、
admin 直通、普通用户按 cyw_analysis 权限列放行/拦截。

卫生约定：固定 2000 年测试日期 + CWTEST-/CWT 前缀，按前缀与范围定向删，不清任何整表。
本脚本只跑本地库，不连服务器。
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')

import jwt
import app as app_module
from sqlalchemy import text

SECRET = os.getenv('JWT_SECRET_KEY')
engine = app_module.engine
FAILS = []

# 固定 2000 年测试日期，绝不碰真实数据年份
D0, D1 = datetime.datetime(2000, 1, 10), datetime.datetime(2000, 1, 19)
PREFIX = 'CWTEST-'


def check(label, cond, detail=''):
    print(('  PASS ' if cond else '  FAIL ') + label + (f'  {detail}' if detail else ''))
    if not cond:
        FAILS.append(label)


def make_token(uid, uname, role):
    return jwt.encode({'user_id': uid, 'username': uname, 'role': role,
                       'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
                      SECRET, algorithm='HS256')


def cleanup():
    with engine.begin() as c:
        c.execute(text("DELETE FROM cyw_issue_log WHERE issue_id IN "
                       "(SELECT id FROM cyw_issue WHERE case_no LIKE :p)"), {'p': PREFIX + '%'})
        c.execute(text("DELETE FROM cyw_issue WHERE case_no LIKE :p"), {'p': PREFIX + '%'})
        c.execute(text("DELETE FROM cyw_spot WHERE monitor_no LIKE 'CWT%'"))


def seed():
    """两个合成点位 + 11 件案件（区间内 10 件 + 区间外 1 件）。

    预期分布（区间内 10 件）：甲点位 7 件（t0×2, t1×2, t2×3）、乙点位 3 件（t0×1, t1×1, t2×1）；
    已办结 5 件；01-10 当天 5 件（001/002/006/008/010）、01-19 当天 5 件；区间外 1 件（1999-12-31）不计入。
    按问题类型：机动车乱停放 4 件、垃圾不洁 3 件、非机动车乱停放 3 件（本地字典顺序与 id 顺序不同，勿按序推）。
    """
    with engine.begin() as c:
        c.execute(text("INSERT INTO cyw_spot (monitor_no, name, road) VALUES "
                       "('CWT01','测试高发点位甲','测试路甲'),('CWT02','测试点位乙',NULL)"))
        spots = {r[0]: r[1] for r in c.execute(text(
            "SELECT monitor_no, id FROM cyw_spot WHERE monitor_no LIKE 'CWT%'")).fetchall()}
        types = c.execute(text("SELECT id, name FROM cyw_type ORDER BY id")).fetchall()
        depts = c.execute(text("SELECT id, name FROM cyw_dept ORDER BY id")).fetchall()
        a, b = spots['CWT01'], spots['CWT02']
        t = {name: tid for tid, name in types}
        d = {name: did for did, name in depts}
        t0, t1, t2 = t['非机动车乱停放'], t['垃圾不洁'], t['机动车乱停放']
        d0, d1 = d['环卫中心'], d['执法队']
        plan = [  # (点位, 类型, 部门, 时间, 状态) —— 区间内 10 件
            (a, t0, d0, D0, '处置中'), (a, t0, d0, D0, '已办结'),
            (a, t1, d0, D1, '已办结'), (a, t1, d0, D1, '处置中'),
            (a, t2, d1, D1, '已办结'), (a, t2, d1, D0, '处置中'), (a, t2, d1, D1, '已办结'),
            (b, t0, d0, D0, '处置中'), (b, t1, d1, D1, '已办结'), (b, t2, d0, D0, '处置中'),
            (a, t0, d0, datetime.datetime(1999, 12, 31), '处置中'),  # 区间外，应被排除
        ]
        for n, (sid, tid, did, at, st) in enumerate(plan, 1):
            c.execute(text(
                "INSERT INTO cyw_issue (case_no, found_at, spot_id, type_id, dept_id, "
                "description, status, closed_at, created_by, created_at) "
                "VALUES (:c,:f,:s,:t,:d,'测试描述',:st,:ca,'冒烟',NOW())"),
                {'c': f'{PREFIX}{n:03d}', 'f': at, 's': sid, 't': tid, 'd': did, 'st': st,
                 'ca': at if st == '已办结' else None})
        return a, b, (t0, t1, t2)


def main():
    app = app_module.app
    app.config['TESTING'] = True
    client = app.test_client()
    H = {'Authorization': f'Bearer {make_token(1, "admin", "admin")}'}
    URL = '/api/cyw/report/analysis'
    Q = {'date_from': '2000-01-10', 'date_to': '2000-01-19'}

    cleanup(); a, b, _ = seed()
    print('合成：2 点位 / 11 件（区间内 10 件，其中 5 件已办结；区间外 1 件）')

    print('\n--- 1. 权限层 ---')
    r = client.get(URL, query_string=Q)
    check('无 token → 401', r.status_code == 401, f'code={r.status_code}')
    bad = client.get(URL, query_string=Q, headers={'Authorization': 'Bearer garbage'})
    check('假 token → 401', bad.status_code == 401, f'code={bad.status_code}')
    # 非 admin 且无 cyw_analysis 权限 → 403（user_id=999 无权限行）
    r2 = client.get(URL, query_string=Q,
                    headers={'Authorization': f'Bearer {make_token(999, "nobody", "user")}'})
    check('无权限普通用户 → 403', r2.status_code == 403, f'code={r2.status_code}')
    r3 = client.get(URL, query_string=Q, headers=H)
    check('admin → 200', r3.status_code == 200, f'code={r3.status_code}')
    check('非法 dimension → 400',
          client.get(URL, query_string={**Q, 'dimension': 'hack'}, headers=H).status_code == 400)
    check('只传 date_from → 400',
          client.get(URL, query_string={'date_from': '2000-01-10'}, headers=H).status_code == 400)
    check('起晚于止 → 400',
          client.get(URL, query_string={'date_from': '2000-01-19', 'date_to': '2000-01-10'},
                     headers=H).status_code == 400)
    check('超一年区间 → 400',
          client.get(URL, query_string={'date_from': '1990-01-01', 'date_to': '2000-01-01'},
                     headers=H).status_code == 400)

    print('\n--- 2. spot 维度契约 ---')
    body = r3.get_json()
    check('success 标志', body.get('success') is True)
    check('grand_total=10（区间外 1 件被排除）', body.get('grand_total') == 10, str(body.get('grand_total')))
    check('is_single=False', body.get('is_single') is False)
    check('date_from/to 回显', body.get('date_from') == '2000-01-10' and body.get('date_to') == '2000-01-19')
    check('dimension 回显', body.get('dimension') == 'spot')
    rk = body.get('ranking') or []
    check('ranking 榜首=测试高发点位甲 7 件',
          bool(rk) and rk[0]['label'] == '测试高发点位甲' and rk[0]['total'] == 7,
          str([(x['label'], x['total']) for x in rk]))
    check('ranking 第二=测试点位乙 3 件',
          len(rk) > 1 and rk[1]['label'] == '测试点位乙' and rk[1]['total'] == 3,
          str([(x['label'], x['total']) for x in rk]))
    check('spot 维度 total 求和 == 10', sum(x['total'] for x in rk) == 10)
    check('ranking 自带 closed/doing/ratio',
          all(set(x) >= {'label', 'total', 'closed', 'doing', 'ratio'} for x in rk))
    check('甲点位 closed=4/doing=3',
          rk and rk[0]['closed'] == 4 and rk[0]['doing'] == 3, f"{rk[0]['closed']}/{rk[0]['doing']}" if rk else '')
    check('乙点位 closed=1/doing=2',
          len(rk) > 1 and rk[1]['closed'] == 1 and rk[1]['doing'] == 2,
          f"{rk[1]['closed']}/{rk[1]['doing']}" if len(rk) > 1 else '')
    check('甲点位 ratio=70.0%', rk and rk[0]['ratio'] == 70.0, str(rk[0]['ratio']) if rk else '')
    check('ranking ≤ 10 条', len(rk) <= 10)
    check('榜单按 total 倒序', all(rk[i]['total'] >= rk[i + 1]['total'] for i in range(len(rk) - 1)))

    print('\n--- 3. 高发问题榜 + 交叉榜 ---')
    bt = body.get('by_type') or []
    check('by_type 三条 = 4/3/3（机动车乱停放×4, 垃圾不洁×3, 非机动车乱停放×3）',
          [x['total'] for x in bt] == [4, 3, 3], str([(x['label'], x['total']) for x in bt]))
    check('by_type 榜首 label=机动车乱停放',
          bool(bt) and bt[0]['label'] == '机动车乱停放', str(bt[0]['label']) if bt else '')
    check('by_type closed 合计 = 5', sum(x['closed'] for x in bt) == 5)
    check('by_type 不随 dimension 变（自带 label）', all('label' in x for x in bt))
    cr = body.get('cross') or []
    check('cross 榜首 = 甲点位 × 机动车乱停放 3 件',
          bool(cr) and cr[0]['spot_name'] == '测试高发点位甲' and cr[0]['total'] == 3,
          str([(x['spot_name'], x['total']) for x in cr]))
    check('cross 带 monitor_no/spot_road 供展示拼接',
          all('monitor_no' in x and 'spot_road' in x for x in cr))
    check('cross 各组合 total 求和 == 10', sum(x['total'] for x in cr) == 10)
    check('cross ≤ 10 条', len(cr) <= 10)

    print('\n--- 4. 按天趋势 ---')
    tr = body.get('trend') or []
    check('trend 2 天（01-10 / 01-19）', len(tr) == 2, str([x['day'] for x in tr]))
    check('trend 01-10 = 5 件、01-19 = 5 件',
          [x['total'] for x in tr] == [5, 5], str([(x['day'], x['total']) for x in tr]))
    check('trend 逐日 total 求和 == 10', sum(x['total'] for x in tr) == 10,
          str([(x['day'], x['total']) for x in tr]))
    check('trend 逐日 closed 求和 == 5', sum(x['closed'] for x in tr) == 5)
    check('trend 按天升序', all(tr[i]['day'] < tr[i + 1]['day'] for i in range(len(tr) - 1)))

    print('\n--- 5. road 维度（NULL 路段归「未填路段」）---')
    b2 = client.get(URL, query_string={**Q, 'dimension': 'road'}, headers=H).get_json()
    rk2 = b2.get('ranking') or []
    labels2 = [x['label'] for x in rk2]
    check('road 榜首=测试路甲 7 件', bool(rk2) and rk2[0]['label'] == '测试路甲' and rk2[0]['total'] == 7,
          str(labels2))
    check('road NULL 归入「未填路段」3 件', '未填路段' in labels2
          and [x for x in rk2 if x['label'] == '未填路段'][0]['total'] == 3, str(labels2))
    check('road 维度 total 求和 == 10', sum(x['total'] for x in rk2) == 10)
    check('road 维度 grand_total 仍为 10（分母口径一致）', b2.get('grand_total') == 10)
    check('road 维度 closed 合计 = 5', sum(x['closed'] for x in rk2) == 5)

    print('\n--- 6. dept 维度 ---')
    b3 = client.get(URL, query_string={**Q, 'dimension': 'dept'}, headers=H).get_json()
    rk3 = b3.get('ranking') or []
    check('dept 维度榜单非空且求和 == 10', bool(rk3) and sum(x['total'] for x in rk3) == 10,
          str([(x['label'], x['total']) for x in rk3]))
    check('dept 维度 grand_total 仍为 10', b3.get('grand_total') == 10)
    check('dept 维度 closed 合计 = 5', sum(x['closed'] for x in rk3) == 5)

    print('\n--- 7. 单日口径 + 空区间 ---')
    b4 = client.get(URL, query_string={'date': '2000-01-10'}, headers=H).get_json()
    check('单日 is_single=True', b4.get('is_single') is True)
    check('单日 grand_total=5', b4.get('grand_total') == 5, str(b4.get('grand_total')))
    check('单日 date 回显 2000-01-10', b4.get('date') == '2000-01-10')
    check('单日 ranking 求和 == 5', sum(x['total'] for x in (b4.get('ranking') or [])) == 5,
          str([(x['label'], x['total']) for x in (b4.get('ranking') or [])]))
    check('单日 by_type 求和 == 5', sum(x['total'] for x in (b4.get('by_type') or [])) == 5)
    check('单日 cross 求和 == 5', sum(x['total'] for x in (b4.get('cross') or [])) == 5)
    check('单日 trend 只有 1 天', len(b4.get('trend') or []) == 1)
    b5 = client.get(URL, query_string={'date': '1990-01-01'}, headers=H).get_json()
    check('空区间 grand_total=0', b5.get('grand_total') == 0, str(b5.get('grand_total')))
    check('空区间 ranking 空', b5.get('ranking') == [])
    check('空区间 trend 空', b5.get('trend') == [])

    print('\n--- 8. 起止同一天按单日走 ---')
    b6 = client.get(URL, query_string={'date_from': '2000-01-10', 'date_to': '2000-01-10'},
                    headers=H).get_json()
    check('起止同日 is_single=True', b6.get('is_single') is True)
    check('起止同日 grand_total=5', b6.get('grand_total') == 5, str(b6.get('grand_total')))

    print('\n--- 9. 只读性（不写库）---')
    with engine.connect() as c:
        before = c.execute(text("SELECT COUNT(*) FROM cyw_issue")).scalar()
        logs_before = c.execute(text("SELECT COUNT(*) FROM cyw_issue_log")).scalar()
    client.get(URL, query_string=Q, headers=H)
    client.get(URL, query_string={**Q, 'dimension': 'road'}, headers=H)
    with engine.connect() as c:
        after = c.execute(text("SELECT COUNT(*) FROM cyw_issue")).scalar()
        logs_after = c.execute(text("SELECT COUNT(*) FROM cyw_issue_log")).scalar()
    check('调用接口不新增案件', before == after, f'{before} → {after}')
    check('调用接口不写留痕', logs_before == logs_after, f'{logs_before} → {logs_after}')

    cleanup()
    with engine.connect() as c:
        left = c.execute(text("SELECT COUNT(*) FROM cyw_issue")).scalar()
        spots_left = c.execute(text("SELECT COUNT(*) FROM cyw_spot WHERE monitor_no LIKE 'CWT%'")).scalar()
    check('合成数据已清空', left == 0 and spots_left == 0, f'issue={left}, spot={spots_left}')

    print('\n' + ('=' * 46))
    print('全部通过' if not FAILS else f'失败 {len(FAILS)} 项: {FAILS}')
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
