# -*- coding: utf-8 -*-
"""挂账功能冒烟测试：片区挂账存取 + 部门合计校验 + 月报挂账列条件显示

测试卫生：只用无案件数据的 209912 写 assessment_manual_*；月报渲染验证借用
202609（只插 assessment_manual_pending 行，验完即删），不碰其他表。
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import jwt
import app as app_module
from app import engine

SECRET = os.getenv('JWT_SECRET_KEY')
H_ADMIN = {'Authorization': 'Bearer ' + jwt.encode(
    {'user_id': 1, 'username': 'admin', 'role': 'admin',
     'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')}
client = app_module.app.test_client()

TEST_BATCH = '209912'   # 无案件数据的测试月
REAL_BATCH = '202609'   # 有案件数据，用于月报挂账列渲染
SMOKE_DOCX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports',
                          f'_smoke_pending_{REAL_BATCH}.docx')

from sqlalchemy import text
from assessment_manual_routes import (
    ensure_manual_tables, check_pending_totals, _pending_dept_group, _pending_unit_group,
)


def save_platform(pending_counts, ledger_pending):
    return client.post('/api/assessment/manual/save-platform', headers=H_ADMIN, json={
        'batch': TEST_BATCH,
        'monthly': {'assessment_case_cnt': 100, 'work_note': '', 'extra_note': ''},
        'scores': [],
        'pending_counts': pending_counts,
        'ledgers': {'pending': ledger_pending, 'backlog': [], 'praise': []},
    })


try:
    ensure_manual_tables(engine)
    print('0) 建表 + 表结构')
    with engine.connect() as conn:
        cols = {r[0] for r in conn.execute(text("SHOW COLUMNS FROM assessment_manual_pending"))}
    assert {'batch', 'unit_name', 'unit_type', 'pending_cnt'} <= cols, cols
    print('   assessment_manual_pending 列:', sorted(cols))

    print('1) 模板接口返回挂账分组')
    tpl = client.get('/api/assessment/manual/template', headers=H_ADMIN).get_json()
    assert tpl['success'] and set(tpl['pending_groups']) == {'dispatch', 'sanitation', 'garden', 'municipal'}
    print('   pending_groups:', {g: c['label'] for g, c in tpl['pending_groups'].items()})

    print('2) 保存：片区合计 = 部门数量 → 无警告')
    r = save_platform(
        [{'unit_type': 'dispatch', 'unit_name': '姚孟执法分队', 'pending_cnt': 3},
         {'unit_type': 'sanitation', 'unit_name': '环卫东片区', 'pending_cnt': 2},
         {'unit_type': 'garden', 'unit_name': '园林东片区', 'pending_cnt': 10},
         {'unit_type': 'garden_park', 'unit_name': '人民公园', 'pending_cnt': 5},
         {'unit_type': 'municipal', 'unit_name': '城市照明部', 'pending_cnt': 4}],
        [{'unit_name': '运城市城市综合行政执法队', 'piece_cnt': 3},
         {'unit_name': '运城市市容环卫中心', 'piece_cnt': 2},
         {'unit_name': '运城市园林绿化服务中心', 'piece_cnt': 15},
         {'unit_name': '排水服务中心', 'piece_cnt': 4}])
    j = r.get_json()
    print('   ', r.status_code, 'warnings =', j.get('warnings'))
    assert r.status_code == 200 and j['success'] and j['warnings'] == []

    print('3) 保存：园林合计 20 ≠ 部门 15 → 仅园林警告（其余组随全量替换清零）')
    r = save_platform(
        [{'unit_type': 'garden', 'unit_name': '园林东片区', 'pending_cnt': 20}],
        [{'unit_name': '运城市园林绿化服务中心', 'piece_cnt': 15}])
    j = r.get_json()
    print('   ', r.status_code, 'warnings =', j.get('warnings'))
    assert r.status_code == 200 and len(j['warnings']) == 1 and '园林绿化' in j['warnings'][0]

    print('4) 读回 pending_counts（上一轮只保存了园林，其他组被清空）')
    d = client.get(f'/api/assessment/manual?batch={TEST_BATCH}', headers=H_ADMIN).get_json()
    pcs = {(p['unit_type'], p['unit_name']): p['pending_cnt'] for p in d['pending_counts']}
    print('   ', pcs)
    assert pcs == {('garden', '园林东片区'): 20}

    print('5) 负数挂账 → 400 且不清掉已存数据')
    r = save_platform([{'unit_type': 'garden', 'unit_name': '园林东片区', 'pending_cnt': -1}], [])
    print('   ', r.status_code, r.get_json().get('error'))
    assert r.status_code == 400
    d = client.get(f'/api/assessment/manual?batch={TEST_BATCH}', headers=H_ADMIN).get_json()
    pcs = {(p['unit_type'], p['unit_name']): p['pending_cnt'] for p in d['pending_counts']}
    assert pcs == {('garden', '园林东片区'): 20}, pcs
    print('    已存数据保留 ✓')

    print('6) check_pending_totals / 分组匹配')
    msgs = check_pending_totals(engine, TEST_BATCH)
    print('   ', msgs)
    assert len(msgs) == 1 and '园林绿化' in msgs[0]  # 库中残留：园林20 vs 部门15
    assert _pending_dept_group('运城市园林绿化服务中心') == 'garden'
    assert _pending_dept_group('园林绿化服务中心') == 'garden'
    assert _pending_dept_group('执法队') == 'dispatch'
    assert _pending_dept_group('市容环卫中心') == 'sanitation'
    assert _pending_dept_group('市政公用服务中心') == 'municipal'
    assert _pending_dept_group('排水服务中心') == 'municipal'
    assert _pending_dept_group('园林东片区') is None      # 片区级名称不算部门
    assert _pending_dept_group('人民公园') is None
    assert _pending_dept_group('应急执法分队') is None
    assert _pending_dept_group('未知单位') is None
    assert _pending_unit_group('人民公园') == 'garden'
    assert _pending_unit_group('未知单位') is None

    print('7) 月报挂账列：全 0 时隐藏')
    from assessment_report.report_data import collect_report_data
    from assessment_report.make_docx import generate_word
    data = collect_report_data(engine, REAL_BATCH)
    assert data['pending_cnt_by_unit'] == {}, data['pending_cnt_by_unit']
    generate_word(data, '', '', SMOKE_DOCX)
    from docx import Document
    doc = Document(SMOKE_DOCX)
    tbl_headers = [[c.text.strip() for c in t.rows[0].cells] for t in doc.tables]
    for idx, name in [(1, '市容秩序'), (2, '环境卫生'), (3, '园林片区'), (4, '公园广场'), (5, '市政公用')]:
        assert '挂账' not in tbl_headers[idx], (name, tbl_headers[idx])
    print('   五张表均无挂账列 ✓  (表1末列:', tbl_headers[1][-1], ')')

    print('8) 月报挂账列：有数据时显示（仅插 pending 行，验完即删）')
    teams = [n for n in data['scores'] if n in (
        '姚孟执法分队', '大渠执法分队', '西城执法分队', '南城执法分队',
        '北城执法分队', '中城执法分队', '东城执法分队', '安邑执法分队')]
    sans = [n for n in data['scores'] if n in (
        '环卫东片区', '环卫西片区', '环卫南片区', '环卫北片区', '环卫中片区')]
    gardens = [n for n in data['scores'] if n in (
        '园林东片区', '园林西片区', '园林南片区', '园林北片区', '园林中片区')]
    parks = [n for n in data['scores'] if n in (
        '人民公园', '体育公园', '南风广场', '天逸公园', '圣惠公园', '禹都公园', '航天公园')]
    munis = [n for n in ('城市照明部', '排水服务中心', '市政设施维护部', '应急执法分队')
             if n in data['scores']]
    print('   results 单位数: 执法', len(teams), '环卫', len(sans), '园林', len(gardens),
          '公园', len(parks), '市政', len(munis))
    assert teams and sans and gardens and parks and munis, '本地 202609 结果单位不全，无法验证'
    ins = [
        (teams[0], 'dispatch', 7),
        (sans[0], 'sanitation', 3),
        (gardens[0], 'garden', 9),
        (parks[0], 'garden_park', 4),
        (munis[0], 'municipal', 5),
    ]
    with engine.begin() as conn:
        for un, ut, cnt in ins:
            conn.execute(text(
                "INSERT INTO assessment_manual_pending (batch, unit_name, unit_type, pending_cnt, updated_by) "
                "VALUES (:b,:u,:t,:c,:by)"), {'b': REAL_BATCH, 'u': un, 't': ut, 'c': cnt, 'by': 'smoke'})
    data = collect_report_data(engine, REAL_BATCH)
    assert data['pending_cnt_by_unit'][teams[0]] == 7
    generate_word(data, '', '', SMOKE_DOCX)
    doc = Document(SMOKE_DOCX)
    tbl_headers = [[c.text.strip() for c in t.rows[0].cells] for t in doc.tables]
    for idx, name in [(1, '市容秩序'), (2, '环境卫生'), (3, '园林片区'), (4, '公园广场'), (5, '市政公用')]:
        assert tbl_headers[idx][-1] == '挂账', (name, tbl_headers[idx])
    # 校验数据行挂账值落在正确行
    def row_of(tbl_idx, unit):
        for row in doc.tables[tbl_idx].rows[1:]:
            if row.cells[0].text.strip() == unit:
                return row.cells[-1].text.strip()
        return None
    assert row_of(1, teams[0]) == '7', row_of(1, teams[0])
    assert row_of(2, sans[0]) == '3'
    assert row_of(3, gardens[0]) == '9'
    assert row_of(4, parks[0]) == '4'
    assert row_of(5, munis[0]) == '5'
    print('   五张表挂账列与数值均正确 ✓')

    print('9) 部分组有数据：无数据组仍隐藏挂账列')
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM assessment_manual_pending WHERE batch=:b AND unit_type='sanitation'"),
            {'b': REAL_BATCH})
    data = collect_report_data(engine, REAL_BATCH)
    generate_word(data, '', '', SMOKE_DOCX)
    doc = Document(SMOKE_DOCX)
    tbl_headers = [[c.text.strip() for c in t.rows[0].cells] for t in doc.tables]
    assert '挂账' not in tbl_headers[2], tbl_headers[2]      # 环卫全 0 → 隐藏
    assert tbl_headers[1][-1] == '挂账'                       # 市容仍有数据 → 显示
    assert tbl_headers[3][-1] == '挂账' and tbl_headers[5][-1] == '挂账'
    print('   环卫隐藏、市容/园林/市政显示 ✓')

    print('\n全部通过 ✅')
finally:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM assessment_manual_pending WHERE batch=:b"), {'b': TEST_BATCH})
        conn.execute(text("DELETE FROM assessment_manual_ledger WHERE batch=:b"), {'b': TEST_BATCH})
        conn.execute(text("DELETE FROM assessment_manual_score WHERE batch=:b"), {'b': TEST_BATCH})
        conn.execute(text("DELETE FROM assessment_manual_monthly WHERE batch=:b"), {'b': TEST_BATCH})
        conn.execute(text("DELETE FROM assessment_manual_pending WHERE batch=:b"), {'b': REAL_BATCH})
    if os.path.exists(SMOKE_DOCX):
        os.remove(SMOKE_DOCX)
    print('测试数据已清理')
