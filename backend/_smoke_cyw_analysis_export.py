# -*- coding: utf-8 -*-
"""创文「数据分析」Excel 导出接口本地验证：forged JWT + Flask test client + 合成数据。

覆盖：交叉榜/高发问题两 sheet 的内容与排序、与 /analysis 接口逐格一致（防 SQL 漂移）、
单日/空区间/起止同日、非法区间 400、权限层（无 token 401 / 无权限 403 / admin 200）、
只读性（不写库不建表）、文件名 RFC5987。

卫生约定：固定 2000 年测试日期 + CWTEST-/CWT 前缀，按前缀与范围定向删，不清任何整表。
本脚本只跑本地库，不连服务器。

跑法：cd backend && python _smoke_cyw_analysis_export.py
"""
import sys, os, io, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')

import jwt
import app as app_module
from sqlalchemy import text

import openpyxl

SECRET = os.getenv('JWT_SECRET_KEY')
engine = app_module.engine
FAILS = []

# 固定 2000 年测试日期，绝不碰真实数据年份（与 _smoke_cyw_analysis 同一套种子）
D0, D1 = datetime.datetime(2000, 1, 10), datetime.datetime(2000, 1, 19)
PREFIX = 'CWTEST-'
URL = '/api/cyw/report/analysis/export'
ANALYSIS_URL = '/api/cyw/report/analysis'
Q = {'date_from': '2000-01-10', 'date_to': '2000-01-19'}


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
    """与 _smoke_cyw_analysis.seed 完全一致：甲点位 7 件 / 乙点位 3 件，区间内共 10 件。

    交叉榜预期（区间内）：甲×机动车乱停放 3、甲×垃圾不洁 2、甲×非机动车乱停放 2、
    乙×非机动车乱停放 1、乙×垃圾不洁 1、乙×机动车乱停放 1（共 6 行，合计 10）。
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
        plan = [
            (a, t0, d0, D0, '处置中'), (a, t0, d0, D0, '已办结'),
            (a, t1, d0, D1, '已办结'), (a, t1, d0, D1, '处置中'),
            (a, t2, d1, D1, '已办结'), (a, t2, d1, D0, '处置中'), (a, t2, d1, D1, '已办结'),
            (b, t0, d0, D0, '处置中'), (b, t1, d1, D1, '已办结'), (b, t2, d0, D0, '处置中'),
            (a, t0, d0, datetime.datetime(1999, 12, 31), '处置中'),
        ]
        for n, (sid, tid, did, at, st) in enumerate(plan, 1):
            c.execute(text(
                "INSERT INTO cyw_issue (case_no, found_at, spot_id, type_id, dept_id, "
                "description, status, closed_at, created_by, created_at) "
                "VALUES (:c,:f,:s,:t,:d,'测试描述',:st,:ca,'冒烟',NOW())"),
                {'c': f'{PREFIX}{n:03d}', 'f': at, 's': sid, 't': tid, 'd': did, 'st': st,
                 'ca': at if st == '已办结' else None})


def read_sheet(resp, sheet_name):
    wb = openpyxl.load_workbook(io.BytesIO(resp.data))
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    title = rows[0][0]
    header = rows[1]
    body = [r for r in rows[2:] if r[0] is not None]
    return wb, ws, title, header, body


def main():
    app = app_module.app
    app.config['TESTING'] = True
    client = app.test_client()
    H = {'Authorization': f'Bearer {make_token(1, "admin", "admin")}'}

    cleanup(); seed()
    print('合成：2 点位 / 11 件（区间内 10 件，其中 5 件已办结；区间外 1 件）')

    print('\n--- 1. 权限层 ---')
    r = client.get(URL, query_string=Q)
    check('无 token → 401', r.status_code == 401, f'code={r.status_code}')
    bad = client.get(URL, query_string=Q, headers={'Authorization': 'Bearer garbage'})
    check('假 token → 401', bad.status_code == 401, f'code={bad.status_code}')
    r2 = client.get(URL, query_string=Q,
                    headers={'Authorization': f'Bearer {make_token(999, "nobody", "user")}'})
    check('无权限普通用户 → 403', r2.status_code == 403, f'code={r2.status_code}')
    r3 = client.get(URL, query_string=Q, headers=H)
    check('admin → 200', r3.status_code == 200, f'code={r3.status_code}')

    print('\n--- 2. 非法区间 400 ---')
    for label, qs in [
        ('只传 date_from', {'date_from': '2000-01-10'}),
        ('只传 date_to', {'date_to': '2000-01-10'}),
        ('起晚于止', {'date_from': '2000-01-19', 'date_to': '2000-01-10'}),
        ('超一年', {'date_from': '1990-01-01', 'date_to': '2000-01-01'}),
    ]:
        rr = client.get(URL, query_string=qs, headers=H)
        check(f'{label} → 400', rr.status_code == 400, f'code={rr.status_code}')

    print('\n--- 3. 响应头与文件类型 ---')
    cd = r3.headers.get('Content-Disposition', '')
    check('Content-Type 是 xlsx',
          'spreadsheetml' in (r3.headers.get('Content-Type') or ''), r3.headers.get('Content-Type'))
    check('Content-Disposition 带附件与 RFC5987 文件名',
          'attachment' in cd and "filename*=UTF-8''" in cd, cd)
    check('文件名含时段 20000110-20000119', '20000110-20000119' in cd, cd)
    check('文件头是 xlsx（PK zip 魔数）', r3.data[:2] == b'PK', r3.data[:8].hex())

    print('\n--- 4. sheet 结构 ---')
    wb, ws1, title1, header1, body1 = read_sheet(r3, '点位×问题交叉榜')
    check('两个 sheet（交叉榜 + 高发问题）', wb.sheetnames == ['点位×问题交叉榜', '高发问题TOP10'],
          str(wb.sheetnames))
    check('标题行含中文时段文案', '2000年01月10日' in str(title1) and '2000年01月19日' in str(title1),
          str(title1))
    check('标题标注 TOP 10', 'TOP 10' in str(title1), str(title1))
    check('交叉榜表头齐全',
          list(header1) == ['排名', '点位', '监控序号', '所属道路', '问题类型', '件数', '已办结',
                            '处置中', '占周期比'], str(header1))
    check('交叉榜 6 行', len(body1) == 6, f'rows={len(body1)}')
    check('交叉榜件数合计 = 10', sum(int(r[5] or 0) for r in body1) == 10,
          str([r[5] for r in body1]))
    check('交叉榜已办结合计 = 5', sum(int(r[6] or 0) for r in body1) == 5)
    check('交叉榜件数倒序（含并列）',
          all(int(body1[i][5]) >= int(body1[i + 1][5]) for i in range(len(body1) - 1)),
          str([r[5] for r in body1]))
    check('榜首 = 甲 × 机动车乱停放 3 件',
          body1 and body1[0][1] == '测试路甲测试高发点位甲' and body1[0][5] == 3,
          f'{body1[0][1] if body1 else ""} / {body1[0][5] if body1 else ""}')
    check('榜首监控序号 CWT01 / 道路 测试路甲',
          body1 and body1[0][2] == 'CWT01' and body1[0][3] == '测试路甲')
    check('乙点位（road 为空）点名不拼路、道路列留空',
          any(r[1] == '测试点位乙' and (r[3] or '') == '' for r in body1),
          str([(r[1], r[3]) for r in body1]))
    check('处置中 = 件数 - 已办结',
          all(int(r[7]) == int(r[5]) - int(r[6]) for r in body1))
    check('占比列形如 30.0%',
          all(str(r[8]).endswith('%') for r in body1), str([r[8] for r in body1]))
    check('榜首占比 = 30.0%（3/10）', body1 and body1[0][8] == '30.0%', str(body1[0][8]) if body1 else '')
    check('排名列从 1 连续递增', [r[0] for r in body1] == list(range(1, len(body1) + 1)))
    check('冻结窗格在表头下一行', ws1.freeze_panes == 'A3', str(ws1.freeze_panes))

    print('\n--- 5. 高发问题 sheet ---')
    _, _, title2, header2, body2 = read_sheet(r3, '高发问题TOP10')
    check('表头齐全', list(header2) == ['排名', '问题类型', '件数', '已办结', '处置中', '占周期比'],
          str(header2))
    check('三行（三个类型都进了 TOP10）', len(body2) == 3, f'rows={len(body2)}')
    check('件数 4/3/3', [int(r[2]) for r in body2] == [4, 3, 3], str([r[2] for r in body2]))
    check('榜首 = 机动车乱停放 4 件',
          bool(body2) and body2[0][1] == '机动车乱停放' and body2[0][2] == 4,
          str(body2[0]) if body2 else '')
    check('已办结合计 = 5', sum(int(r[3]) for r in body2) == 5)

    print('\n--- 6. 与 /analysis 接口逐格一致（防 SQL 漂移）---')
    ana = client.get(ANALYSIS_URL, query_string=Q, headers=H).get_json()
    ac = ana.get('cross') or []
    check('接口 cross 行数 == Excel 行数', len(ac) == len(body1), f'{len(ac)} vs {len(body1)}')
    same = all(
        ac[i]['spot_name'] in body1[i][1] and ac[i]['type_name'] == body1[i][4]
        and ac[i]['total'] == body1[i][5] and ac[i]['closed'] == body1[i][6]
        and f"{ac[i]['ratio']}%" == body1[i][8]
        for i in range(len(ac)))
    check('交叉榜逐格一致（点名/类型/件数/办结/占比）', same)
    at = ana.get('by_type') or []
    check('高发问题逐格一致',
          len(at) == len(body2) and all(
              at[i]['label'] == body2[i][1] and at[i]['total'] == body2[i][2]
              and at[i]['closed'] == body2[i][3] for i in range(len(at))))

    print('\n--- 7. 单日口径 ---')
    rs = client.get(URL, query_string={'date': '2000-01-10'}, headers=H)
    check('单日 → 200', rs.status_code == 200, f'code={rs.status_code}')
    check('单日文件名带 20000110', '20000110' in rs.headers.get('Content-Disposition', ''))
    _, _, ts, _, bs1 = read_sheet(rs, '点位×问题交叉榜')
    check('单日标题是「统计日期」口径的单日文案',
          '2000年01月10日' in str(ts) and '2000年01月19日' not in str(ts), str(ts))
    check('单日交叉榜件数合计 = 5', sum(int(r[5] or 0) for r in bs1) == 5,
          str([r[5] for r in bs1]))
    _, _, _, _, bs2 = read_sheet(rs, '高发问题TOP10')
    check('单日高发问题件数合计 = 5', sum(int(r[2] or 0) for r in bs2) == 5)

    print('\n--- 8. 起止同一天按单日走 ---')
    rd = client.get(URL, query_string={'date_from': '2000-01-10', 'date_to': '2000-01-10'}, headers=H)
    check('起止同日 → 200', rd.status_code == 200, f'code={rd.status_code}')
    _, _, td, _, bd1 = read_sheet(rd, '点位×问题交叉榜')
    check('起止同日件数合计 = 5', sum(int(r[5] or 0) for r in bd1) == 5)
    check('起止同日标题不带「至」', '至' not in str(td), str(td))

    print('\n--- 9. 空区间 ---')
    re_ = client.get(URL, query_string={'date': '1990-01-01'}, headers=H)
    check('空区间 → 200', re_.status_code == 200, f'code={re_.status_code}')
    _, _, _, _, be1 = read_sheet(re_, '点位×问题交叉榜')
    check('空区间交叉榜 0 行', len(be1) == 0, f'rows={len(be1)}')
    _, _, _, _, be2 = read_sheet(re_, '高发问题TOP10')
    check('空区间高发问题 0 行', len(be2) == 0, f'rows={len(be2)}')
    check('空区间仍能打开成合法 xlsx', be1 is not None and be2 is not None)

    print('\n--- 10. 只读性（不写库不建表）---')
    with engine.connect() as c:
        before = c.execute(text("SELECT COUNT(*) FROM cyw_issue")).scalar()
        logs_before = c.execute(text("SELECT COUNT(*) FROM cyw_issue_log")).scalar()
        tables_before = {r[0] for r in c.execute(text("SHOW TABLES")).fetchall()}
    client.get(URL, query_string=Q, headers=H)
    client.get(URL, query_string={'date': '2000-01-10'}, headers=H)
    with engine.connect() as c:
        after = c.execute(text("SELECT COUNT(*) FROM cyw_issue")).scalar()
        logs_after = c.execute(text("SELECT COUNT(*) FROM cyw_issue_log")).scalar()
        tables_after = {r[0] for r in c.execute(text("SHOW TABLES")).fetchall()}
    check('导出不新增案件', before == after, f'{before} → {after}')
    check('导出不写留痕', logs_before == logs_after, f'{logs_before} → {logs_after}')
    check('导出不建新表', tables_before == tables_after,
          str(tables_after - tables_before))

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
