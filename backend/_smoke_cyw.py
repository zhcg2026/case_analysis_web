# -*- coding: utf-8 -*-
"""创文问题处置模块冒烟测试：forged JWT + Flask test client。
覆盖：序号带出→登记(即处置中)→照片上传→编辑边界→反馈即办结→已办结后再反馈(更正通道)→
详单JPG生成→日报→Excel导入两段式→权限分层(cyw_input/cyw_ledger拆分)→
坐标(带出/校验/导入)→AI照片识别(降级不阻断)→历史台账一键导入(幂等/自动建点位单位)。
2026-10-16 流程简化后：无「标记已派发/核销/退回」，无超时口径，状态只剩「处置中/已办结」。
卫生约定：固定测试数据(CYW-TEST-前缀/smoke_import标记)，按ID精确删除，不清任何整表。
"""
import sys, os, io, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import jwt
from PIL import Image
from openpyxl import Workbook
import app as app_module
from sqlalchemy import text

SECRET = os.getenv('JWT_SECRET_KEY')
engine = app_module.engine

def make_token(uid, uname, role):
    return jwt.encode({'user_id': uid, 'username': uname, 'role': role,
                       'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
                      SECRET, algorithm='HS256')

H = {'Authorization': f'Bearer {make_token(1, "admin", "admin")}'}
H_USER = {'Authorization': f'Bearer {make_token(999001, "smoke_user", "user")}'}  # 无权限普通用户
# 权限拆分测试用户：仅 cyw_input / 仅 cyw_ledger
H_INPUT = {'Authorization': f'Bearer {make_token(999002, "smoke_input", "user")}'}
H_LEDGER = {'Authorization': f'Bearer {make_token(999003, "smoke_ledger", "user")}'}
PERM_USERS = [999001, 999002, 999003]
client = app_module.app.test_client()

created = {'issues': [], 'spots': [], 'slips': [], 'photos': [], 'check_batches': []}
ok = lambda name: print(f'  [PASS] {name}')

def fail(name, extra=''):
    print(f'  [FAIL] {name} {extra}')
    raise SystemExit(1)

def sweep_test_data(conn):
    """按测试标记 + 孤儿数据精确清理崩溃轮次残留（禁整表清空）"""
    conn.execute(text("DELETE FROM cyw_issue_log WHERE issue_id IN "
                      "(SELECT id FROM cyw_issue WHERE description LIKE '冒烟测试%' OR spot_id NOT IN (SELECT id FROM cyw_spot))"))
    conn.execute(text("DELETE FROM cyw_issue WHERE description LIKE '冒烟测试%' OR spot_id NOT IN (SELECT id FROM cyw_spot)"))
    conn.execute(text("DELETE FROM cyw_spot WHERE monitor_no LIKE 'CYW-TEST%'"))
    conn.execute(text("DELETE FROM cyw_spot_contact WHERE spot_id NOT IN (SELECT id FROM cyw_spot)"))
    # 抽查：只删本脚本这一轮新建的批次（记录起始 id，删 id 大于它的），禁整表清空。
    # 不用 created_by 兜底——冒烟用的就是 admin 令牌，和真实数据同一个操作人，分不开。
    for bid in list(created.get('check_batches') or []):
        conn.execute(text("DELETE FROM cyw_check_item WHERE batch_id = :b"), {'b': bid})
        conn.execute(text("DELETE FROM cyw_check_batch WHERE id = :b"), {'b': bid})
    base = created.get('check_id_base')
    if base is not None:
        stale = [r[0] for r in conn.execute(
            text("SELECT id FROM cyw_check_batch WHERE id > :b"), {'b': base})]
        for bid in stale:
            conn.execute(text("DELETE FROM cyw_check_item WHERE batch_id = :b"), {'b': bid})
            conn.execute(text("DELETE FROM cyw_check_batch WHERE id = :b"), {'b': bid})

def set_perm(uid, col):
    """给测试用户授单项权限（先清后插，行级精确操作）"""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM permissions WHERE user_id = :u"), {'u': uid})
        conn.execute(text(f"INSERT INTO permissions (user_id, {col}) VALUES (:u, 1)"), {'u': uid})

# 预清扫：崩溃轮次可能留下引用了已删点位的孤儿问题，会被日报 JOIN 静默漏计
with engine.begin() as conn:
    sweep_test_data(conn)

try:
    # 0) 字典就位（种子 7 部门 / 11 类型，按 2026.1-5 台账梳理）
    print('0) 字典种子')
    r = client.get('/api/cyw/depts', headers=H)
    depts = r.get_json()['depts']
    dept_map = {d['name']: d for d in depts}
    assert r.status_code == 200 and len(depts) >= 7, '部门种子不足'
    r = client.get('/api/cyw/types', headers=H)
    types = r.get_json()['types']
    type_map = {t['name']: t for t in types}
    assert r.status_code == 200 and len(types) >= 11, '类型种子不足'
    hs = type_map['垃圾不洁']
    assert dept_map[hs['default_dept_name']]['color'] == '#2E7D32', '类型默认映射不符'
    fb = type_map['其他']
    ok(f'部门 {len(depts)} 个 / 类型 {len(types)} 个，默认映射符合台账口径')

    # 1) 测试点位（高德坐标 + 管理单位 + 结构化联系人）
    print('1) 建测试点位 + 坐标 + 联系人')
    r = client.post('/api/cyw/spots', headers=H, json={
        'monitor_no': 'CYW-TEST-01', 'name': '冒烟测试点位', 'road': '冒烟测试路',
        'manage_unit': '开发区',
        'is_key': True, 'lng': 110.983652, 'lat': 35.140218,
        'contacts': [
            {'dept_label': '环卫中心·片区负责人', 'person': '测试甲', 'phone': '13500000001'},
            {'dept_label': '执法队·东城分队三中队', 'person': '测试乙', 'phone': '13500000002'},
        ]})
    assert r.status_code == 200 and r.get_json()['success'], r.get_json()
    spot_id = r.get_json()['id']
    created['spots'].append(spot_id)

    # 2) 序号带出（快速录入核心）
    print('2) 序号带出')
    r = client.get('/api/cyw/spot-by-no', query_string={'no': 'CYW-TEST-01'}, headers=H)
    j = r.get_json()
    assert j['hit'] and j['spot']['id'] == spot_id, j
    assert float(j['spot']['lng']) == 110.983652 and float(j['spot']['lat']) == 35.140218, j
    assert j['spot']['manage_unit'] == '开发区', j
    assert [c['dept_label'] for c in j['contacts']] == ['环卫中心·片区负责人', '执法队·东城分队三中队'], j
    assert j['contacts'][0]['person'] == '测试甲' and j['contacts'][0]['phone'] == '13500000001', j
    assert any(t['name'] == '垃圾不洁' and t['default_dept_name'] for t in j['types']), j
    r = client.get('/api/cyw/spot-by-no', query_string={'no': 'CYW-TEST-不存在'}, headers=H)
    assert r.status_code == 404 and not r.get_json()['hit'], r.get_json()
    r = client.get('/api/cyw/spot-by-no', query_string={'no': ''}, headers=H)
    assert r.status_code == 400, r.status_code
    r = client.get('/api/cyw/spot-by-no', query_string={'no': 'CYW-TEST-01'}, headers=H_USER)
    assert r.status_code == 200, '登录用户应可序号带出'
    ok('序号带出：点位+坐标+管理单位+联系人(按部门逐条)+类型默认部门齐备；未命中404；空序号400；登录即可用')

    # 3) 照片上传（普通权限用户不可传，admin 可传）
    print('3) POST /api/cyw/upload-image')
    def make_img():
        b = io.BytesIO()
        Image.new('RGB', (80, 60), (200, 30, 30)).save(b, format='JPEG')
        b.seek(0)
        return b
    r = client.post('/api/cyw/upload-image', data={'file': (make_img(), 'scene.jpg')}, headers=H_USER)
    assert r.status_code == 403, f'无权限用户上传应 403，实际 {r.status_code}'
    r = client.post('/api/cyw/upload-image', data={'file': (make_img(), 'scene.jpg')}, headers=H)
    assert r.status_code == 200 and r.get_json()['success'], r.get_json()
    photo_url = r.get_json()['url']
    created['photos'].append(photo_url)
    ok('照片上传 + 无权限用户 403 拦截')

    # 4) 登记（无权限用户 403）
    print('4) POST /api/cyw/issues')
    payload = {
        'spot_id': spot_id, 'type_id': hs['id'], 'dept_id': dept_map['环卫中心']['id'],
        'found_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'description': '冒烟测试：广场地面散落垃圾',
    }
    r = client.post('/api/cyw/issues', json=payload, headers=H_USER)
    assert r.status_code == 403, f'无权限用户登记应 403，实际 {r.status_code}'
    r = client.post('/api/cyw/issues', json=payload, headers=H)
    assert r.status_code == 200, r.get_json()
    issue1 = r.get_json()
    created['issues'].append(issue1['id'])
    assert issue1['case_no'].startswith('CW') and issue1['issue']['status'] == '处置中', issue1
    assert issue1['issue']['dept_name'] == '环卫中心', issue1
    assert 'deadline_at' not in issue1['issue'] and 'is_overdue' not in issue1['issue'], issue1['issue']
    # issue2：派发夜市（供反馈/更正通道用例）
    payload2 = dict(payload, description='冒烟测试：公园长椅破损', type_id=type_map['市政设施']['id'],
                    dept_id=dept_map['夜市']['id'])
    r = client.post('/api/cyw/issues', json=payload2, headers=H)
    issue2 = r.get_json()
    created['issues'].append(issue2['id'])
    # 参数校验：缺部门(传不存在id)/缺描述/缺点位
    assert client.post('/api/cyw/issues', json={**payload, 'dept_id': 999999}, headers=H).status_code == 400
    assert client.post('/api/cyw/issues', json={**payload, 'description': ''}, headers=H).status_code == 400
    assert client.post('/api/cyw/issues', json={**payload, 'spot_id': 999999}, headers=H).status_code == 400
    ok('登记 2 条（编号 CW 开头/默认即处置中/单部门）+ 无权限 403 + 缺部门/描述/点位 400')

    # 5) 编辑边界（仅处置中可编辑，响应里不再带时限/超时字段）
    print('5) 编辑边界')
    r = client.put(f"/api/cyw/issues/{issue1['id']}", headers=H, json={
        **payload, 'description': '冒烟测试：广场地面散落垃圾(已更正)'})
    assert r.status_code == 200, r.get_json()
    r = client.get(f"/api/cyw/issues/{issue1['id']}", headers=H)
    assert r.get_json()['issue']['description'].endswith('(已更正)'), r.get_json()
    ok('处置中状态可编辑')

    # 5b) 点位联系人整表替换语义（带 contacts 键才动，避免误清空）
    print('5b) 点位联系人替换语义')
    r = client.put(f'/api/cyw/spots/{spot_id}', headers=H, json={
        'monitor_no': 'CYW-TEST-01', 'name': '冒烟测试点位', 'road': '冒烟测试路',
        'manage_unit': '开发区', 'contacts': [
            {'dept_label': '点位主管', 'person': '测试己', 'phone': '13500000006'}]})
    assert r.status_code == 200, r.get_json()
    j = client.get('/api/cyw/spot-by-no', query_string={'no': 'CYW-TEST-01'}, headers=H).get_json()
    assert [c['person'] for c in j['contacts']] == ['测试己'], j['contacts']
    r = client.put(f'/api/cyw/spots/{spot_id}', headers=H, json={
        'monitor_no': 'CYW-TEST-01', 'name': '冒烟测试点位', 'road': '冒烟测试路', 'manage_unit': '开发区'})
    assert r.status_code == 200, r.get_json()
    j = client.get('/api/cyw/spot-by-no', query_string={'no': 'CYW-TEST-01'}, headers=H).get_json()
    assert [c['person'] for c in j['contacts']] == ['测试己'], '不带 contacts 键的更新不应清空联系人'
    r = client.get('/api/cyw/spots', query_string={'keyword': 'CYW-TEST-01'}, headers=H)
    lst = r.get_json()['spots']
    assert len(lst) == 1 and len(lst[0]['contacts']) == 1, lst
    ok('带 contacts 键整表替换；不带该键不清空；列表接口同样带出联系人')

    # 6) 反馈即办结（无派发/核销/退回环节）
    print('6) 反馈即办结')
    r = client.post(f"/api/cyw/issues/{issue1['id']}/feedback", headers=H, json={
        'feedback_note': '已清扫干净'})
    j = r.get_json()
    assert r.status_code == 200 and j['status'] == '已办结', j
    detail = client.get(f"/api/cyw/issues/{issue1['id']}", headers=H).get_json()['issue']
    actions = [lg['action'] for lg in detail['logs']]
    assert actions == ['登记', '编辑', '反馈'], actions
    assert detail['is_fed'] and detail['feedback_note'] == '已清扫干净', detail
    assert detail['status'] == '已办结' and detail['closed_by'] == 'admin' and detail['closed_at'], detail
    assert detail['dept_name'] == '环卫中心' and detail['fed_at'], detail
    # 已办结后禁编辑/禁删除（全程留痕）
    r = client.put(f"/api/cyw/issues/{issue1['id']}", headers=H, json={**payload, 'description': 'x'})
    assert r.status_code == 400, '已办结不可编辑'
    r = client.delete(f"/api/cyw/issues/{issue1['id']}", headers=H)
    assert r.status_code == 400, '已办结不可删除'
    ok('反馈即转已办结 + 办结人/办结时间落库 + 留痕链完整 + 已办结禁编辑/禁删除')

    # 7) 未反馈的案件也可直接反馈办结（issue2 从未走过任何中间态）
    print('7) 直接反馈办结')
    r = client.post(f"/api/cyw/issues/{issue2['id']}/feedback", headers=H, json={
        'feedback_note': '长椅已更换'})
    assert r.status_code == 200 and r.get_json()['status'] == '已办结', r.get_json()
    detail2 = client.get(f"/api/cyw/issues/{issue2['id']}", headers=H).get_json()['issue']
    assert detail2['status'] == '已办结' and detail2['is_fed'], detail2
    ok('未反馈案件一次反馈即办结')

    # 8) 已办结后再反馈 = 更正通道：内容更新，首次办结时间保留
    print('8) 已办结后更正反馈')
    first_closed_at = detail2['closed_at']
    r = client.post(f"/api/cyw/issues/{issue2['id']}/feedback", headers=H, json={
        'feedback_note': '更正：长椅已更换并加固'})
    assert r.status_code == 200 and r.get_json()['status'] == '已办结', r.get_json()
    detail2 = client.get(f"/api/cyw/issues/{issue2['id']}", headers=H).get_json()['issue']
    assert detail2['feedback_note'] == '更正：长椅已更换并加固', detail2
    assert detail2['closed_at'] == first_closed_at, '更正反馈不得改动首次办结时间'
    assert [lg['action'] for lg in detail2['logs']] == ['登记', '反馈', '补充反馈'], detail2['logs']
    # 空反馈（无说明无照片）应 400
    r = client.post(f"/api/cyw/issues/{issue2['id']}/feedback", headers=H, json={})
    assert r.status_code == 400, '空反馈应 400'
    ok('更正反馈只改内容不改首次办结时间 + 留痕标「补充反馈」+ 空反馈 400')

    # 10) 详单 JPG 生成（含全部现场照片）
    print('10) 生成详单 JPG（多照片）')
    r = client.post(f"/api/cyw/issues/{issue1['id']}/slip", headers=H)
    assert r.status_code == 200 and r.get_json()['success'], r.get_json()
    slip_rel = r.get_json()['url']
    slip_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), slip_rel.lstrip('/'))
    assert os.path.exists(slip_path) and os.path.getsize(slip_path) > 3000, '详单文件过小或不存在'
    with open(slip_path, 'rb') as f:
        magic = f.read(3)
    assert magic == b'\xff\xd8\xff', '详单不是 JPEG'
    created['slips'].append(slip_rel)

    # 三张纯色照片建一条新案件：抽样像素即可证明每张都真的画进了详单
    # （历史坑：详单取的是 path 键，上传接口返回的是 url 键，照片从来没渲染成功过）
    colors = {'red': (230, 20, 20), 'green': (20, 200, 40), 'blue': (20, 60, 220)}
    photo_items = []
    for cname, rgbv in colors.items():
        b = io.BytesIO()
        Image.new('RGB', (640, 480), rgbv).save(b, format='JPEG')
        b.seek(0)
        r = client.post('/api/cyw/upload-image', data={'file': (b, f'{cname}.jpg')}, headers=H)
        assert r.status_code == 200 and r.get_json()['success'], r.get_json()
        photo_items.append({'name': f'{cname}.jpg', 'url': r.get_json()['url']})
        created['photos'].append(r.get_json()['url'])
    r = client.post('/api/cyw/issues', json=dict(payload, description='冒烟测试：详单多照片',
                                                 photos=photo_items), headers=H)
    assert r.status_code == 200, r.get_json()
    issue_slip = r.get_json()
    created['issues'].append(issue_slip['id'])
    r = client.post(f"/api/cyw/issues/{issue_slip['id']}/slip", headers=H)
    assert r.status_code == 200 and r.get_json()['success'], r.get_json()
    created['slips'].append(r.get_json()['url'])

    slip2_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              r.get_json()['url'].lstrip('/'))
    simg = Image.open(slip2_path).convert('RGB')
    px = simg.load()
    found = set()
    for yy in range(0, simg.height, 3):
        for xx in range(0, simg.width, 3):
            p = px[xx, yy]
            for cname, rgbv in colors.items():
                if cname not in found and all(abs(p[i] - rgbv[i]) <= 40 for i in range(3)):
                    found.add(cname)
    assert found == set(colors), f'详单照片未全部渲染：应有 {set(colors)}，实际 {found}'
    ok(f'详单 {os.path.getsize(slip_path)} 字节，JPEG；多照片案件详单 '
       f'{simg.size[0]}x{simg.height}，3 张照片全部渲染')

    # 11) 超时口径已下线：响应无 is_overdue/deadline_at，only_overdue 参数不再生效
    print('11) 超时口径下线')
    payload_over = dict(payload)
    payload_over['found_at'] = '2000-01-01 09:00:00'
    payload_over['description'] = '冒烟测试：超时口径已下线案件'
    r = client.post('/api/cyw/issues', headers=H, json=payload_over)
    issue3 = r.get_json()
    created['issues'].append(issue3['id'])
    r = client.get('/api/cyw/issues', query_string={'status': '处置中', 'keyword': '冒烟测试'}, headers=H)
    hit = [i for i in r.get_json()['issues'] if i['id'] == issue3['id']][0]
    assert hit['status'] == '处置中' and 'is_overdue' not in hit and 'deadline_at' not in hit, hit
    # 旧参数即使传了也不报错、不改变筛选结果（老前端残留调用不会 500）
    r_old = client.get('/api/cyw/issues', query_string={'only_overdue': '1', 'keyword': '冒烟测试'}, headers=H)
    assert r_old.status_code == 200, r_old.status_code
    ok('2000 年案件也只是普通处置中：无 is_overdue/deadline_at 字段，only_overdue 旧参数被忽略')

    # 12) 日报（issue3 故意用 2000 年发现时间，不计入今日新增；无超时栏目）
    print('12) 日报统计')
    today = datetime.date.today().strftime('%Y-%m-%d')
    r = client.get('/api/cyw/report/daily', query_string={'date': today}, headers=H)
    j = r.get_json()
    assert j['counts']['new'] >= 2 and j['counts']['closed'] >= 2, j['counts']
    assert 'overdue' not in j['counts'] and 'overdue' not in j['details'], j
    assert any(i['case_no'] == issue1['case_no'] for i in j['details']['new']), '新增明细缺 issue1'
    assert any(i['case_no'] == issue2['case_no'] for i in j['details']['closed']), '已办结明细缺 issue2'
    assert j['counts']['open_total'] >= 1, j['counts']
    ok(f"新增 {j['counts']['new']} / 已办结 {j['counts']['closed']} / 处置中 {j['counts']['doing']} / 未办结总数 {j['counts']['open_total']}（无超时栏目）")

    # 12b) 时间段统计（起止日期）：与单日同口径、跨天可累加、非法区间 400
    print('12b) 时间段统计')
    d0 = datetime.date.today() - datetime.timedelta(days=1)
    d1 = datetime.date.today() + datetime.timedelta(days=1)
    s0, s1 = d0.strftime('%Y-%m-%d'), d1.strftime('%Y-%m-%d')
    # 起止同一天 = 单日结果，必须逐字段一致（is_single 也回 True，前端据此切文案）
    r = client.get('/api/cyw/report/daily',
                   query_string={'date_from': today, 'date_to': today}, headers=H)
    j_eq = r.get_json()
    assert j_eq['is_single'] is True and j_eq['date'] == today, j_eq
    assert j_eq['counts'] == j['counts'], (j_eq['counts'], j['counts'])
    assert ([i['case_no'] for i in j_eq['details']['new']]
            == [i['case_no'] for i in j['details']['new']]), '同日区间与单日明细不一致'
    # 跨天区间：覆盖当日的区间必须把当日新增全部包住，found_at 带月-日
    r = client.get('/api/cyw/report/daily', query_string={'date_from': s0, 'date_to': s1}, headers=H)
    jr = r.get_json()
    assert jr['is_single'] is False, jr
    assert jr['date_from'] == s0 and jr['date_to'] == s1, jr
    assert jr['date'] == s0, '时间段模式下 date 回落为统计起始日（兼容老字段）'
    assert jr['counts']['new'] >= j['counts']['new'], (jr['counts'], j['counts'])
    for it in j['details']['new']:
        assert any(x['case_no'] == it['case_no'] for x in jr['details']['new']), f"跨天区间漏了 {it}"
    for x in jr['details']['new']:
        if x['found_at']:
            assert len(x['found_at']) == 11 and x['found_at'][2] == '-' and x['found_at'][5] == ' ', x
    # 2000 年案件单独成区间：证明真的按起止过滤，不是把所有数据都返回
    r = client.get('/api/cyw/report/daily',
                   query_string={'date_from': '2000-01-01', 'date_to': '2000-01-01'}, headers=H)
    j2k = r.get_json()
    assert j2k['is_single'] is True and j2k['counts']['new'] >= 1, j2k
    assert any(i['case_no'] == issue3['case_no'] for i in j2k['details']['new']), '2000 区间缺 issue3'
    assert not any(i['case_no'] == issue1['case_no'] for i in j2k['details']['new']), '不该带上今日案件'
    # 非法区间一律 400 + 中文提示（前端直接透传）
    for qs, why in (({'date_from': today}, '只给起'),
                    ({'date_to': today}, '只给止'),
                    ({'date_from': s1, 'date_to': s0}, '起晚于止'),
                    ({'date_from': '2019-01-01', 'date_to': today}, '超过一年'),
                    ({'date_from': 'abc', 'date_to': today}, '日期格式错')):
        rr = client.get('/api/cyw/report/daily', query_string=qs, headers=H)
        assert rr.status_code == 400 and rr.get_json().get('error'), (why, rr.get_json())
    ok(f"同日区间=单日；跨天 {s0}~{s1} 新增 {jr['counts']['new']} ≥ 当日 {j['counts']['new']}，"
       f"found_at 带月-日；2000 区间只含 issue3；5 类非法区间全 400")

    # 12c) 时间段导出 txt（单日格式逐字不变 + 周期格式 + BOM + 文件名）
    print('12c) 时间段导出')
    r = client.get('/api/cyw/report/daily/export', query_string={'date': today}, headers=H)
    assert r.status_code == 200 and r.data[:3] == b'\xef\xbb\xbf', '缺 UTF-8 BOM'
    txt_day = r.data.decode('utf-8-sig')
    assert '统计日期：' in txt_day and '【一、当日概况】' in txt_day, txt_day
    assert '统计周期' not in txt_day and '周期概况' not in txt_day, '单日导出混入周期文案'
    assert f"cyw_stats_{today.replace('-', '')}.txt" in r.headers.get('Content-Disposition', '')
    # 起止同一天仍按单日格式导出，文件名不带横杠
    r = client.get('/api/cyw/report/daily/export',
                   query_string={'date_from': today, 'date_to': today}, headers=H)
    assert r.data.decode('utf-8-sig') == txt_day, '同日区间导出与单日不一致'
    assert f"cyw_stats_{today.replace('-', '')}.txt" in r.headers.get('Content-Disposition', '')
    # 真正的多日区间
    r = client.get('/api/cyw/report/daily/export',
                   query_string={'date_from': s0, 'date_to': s1}, headers=H)
    assert r.status_code == 200, r.status_code
    txt_rng = r.data.decode('utf-8-sig')
    assert '统计周期：' in txt_rng and '【一、周期概况】' in txt_rng, txt_rng
    assert f'共{(d1 - d0).days + 1}天' in txt_rng, txt_rng
    assert '（本周期无派发案件）' not in txt_rng, txt_rng
    cd = r.headers.get('Content-Disposition', '')
    assert f'cyw_stats_{s0.replace("-", "")}-{s1.replace("-", "")}.txt' in cd, cd
    # 中文名走 RFC5987 的 filename*=UTF-8''，是百分号编码（前端 decodeURIComponent）
    assert "filename*=UTF-8''%E5%88%9B%E6%96%87" in cd, cd
    # 空区间：周期文案的空态分支
    r = client.get('/api/cyw/report/daily/export',
                   query_string={'date_from': '1999-01-01', 'date_to': '1999-01-31'}, headers=H)
    txt_empty = r.data.decode('utf-8-sig')
    assert '（本周期无派发案件）' in txt_empty and '共0件，办结0件' in txt_empty, txt_empty
    # 导出同样拦非法区间
    r = client.get('/api/cyw/report/daily/export',
                   query_string={'date_from': s1, 'date_to': s0}, headers=H)
    assert r.status_code == 400, r.status_code
    ok(f"单日导出逐字未变；周期导出带「统计周期/周期概况/共{(d1 - d0).days + 1}天」；"
       f"文件名 {s0.replace('-', '')}-{s1.replace('-', '')}；空区间走空态；非法区间 400")

    # 13) Excel 导入两段式（含经度/纬度列 + 管理单位列 + 中国范围外坐标警告 + 「联系人」sheet）
    print('13) 点位 Excel 导入')
    wb = Workbook(); ws = wb.active
    ws.append(['监控序号', '点位编号', '点位名称', '所在路段', '管理单位', '是否重点', '经度', '纬度'])
    ws.append(['CYW-TEST-02', 'CYW-TEST-SPOT2', '冒烟导入点位', '导入路', '开发区', '是', '110.983652', '35.140218'])
    ws.append(['CYW-TEST-03', 'CYW-TEST-SPOT3', '冒烟境外坐标点位', '导入路', '', '否', '10.5', '10.5'])  # 全球合法但不在中国；管理单位留空应落默认
    ws.append(['', '', '缺序号行', '', '', '', '', ''])  # 无效行
    ws2 = wb.create_sheet('联系人')
    ws2.append(['监控序号', '部门', '人员', '电话'])
    ws2.append(['CYW-TEST-02', '环卫中心·片区负责人', '测试丙', '13500000003'])
    ws2.append(['CYW-TEST-02', '执法队·姚孟分队二十中队', '测试丁', '13500000004'])
    ws2.append(['CYW-TEST-99', '点位总负责人', '测试戊', '13500000005'])  # 主表无此序号 → 只警告
    xb = io.BytesIO(); wb.save(xb); xb.seek(0)
    r = client.post('/api/cyw/spots/import', data={'file': (xb, 'spots.xlsx')}, headers=H)
    j = r.get_json()
    assert r.status_code == 200 and j['total'] == 2 and len(j['invalid']) == 1, j
    warn_reasons = '；'.join(w['reason'] for w in j['warnings'])
    assert '不在中国范围' in warn_reasons and 'CYW-TEST-99' in warn_reasons, j['warnings']
    assert j['contact_count'] == 3, j['contact_count']
    r02 = [x for x in j['rows'] if x['monitor_no'] == 'CYW-TEST-02'][0]
    r03 = [x for x in j['rows'] if x['monitor_no'] == 'CYW-TEST-03'][0]
    assert float(r02['lng']) == 110.983652 and float(r03['lng']) == 10.5, j['rows']
    assert r02['manage_unit'] == '开发区' and r03['manage_unit'] == '', j['rows']
    assert len(r02['contacts']) == 2 and r03['contacts'] == [], j['rows']  # 无联系人 sheet 行的点位落空数组
    r = client.post('/api/cyw/spots/import/confirm', headers=H, json={'rows': j['rows']})
    j2 = r.get_json()
    assert j2['success'] and j2['inserted'] == 2, j2
    with engine.connect() as conn:
        for mno in ('CYW-TEST-02', 'CYW-TEST-03'):
            sid = conn.execute(text("SELECT id FROM cyw_spot WHERE monitor_no = :m"), {'m': mno}).scalar()
            created['spots'].append(sid)
    r = client.get('/api/cyw/spot-by-no', query_string={'no': 'CYW-TEST-02'}, headers=H)
    assert r.get_json()['hit'], '导入点位未生效'
    assert float(r.get_json()['spot']['lng']) == 110.983652, '导入点位坐标未落库'
    assert r.get_json()['spot']['manage_unit'] == '开发区', '导入点位管理单位未落库'
    cts = r.get_json()['contacts']
    assert [c['person'] for c in cts] == ['测试丙', '测试丁'], cts
    assert cts[1]['dept_label'] == '执法队·姚孟分队二十中队' and cts[1]['phone'] == '13500000004', cts
    r = client.get('/api/cyw/spot-by-no', query_string={'no': 'CYW-TEST-03'}, headers=H)
    assert r.get_json()['spot']['manage_unit'] == '城市管理局', '管理单位留空应落默认城市管理局'
    assert r.get_json()['contacts'] == [], '主表未列联系人的点位应落空数组'
    ok('导入预览(2有效/1无效/境外坐标+未知序号联系人提醒/联系人3条) → 确认导入 + 联系人按序号归组落库')

    # 14) 权限分层：input/ledger 拆分，录入与台账共用接口取「或」
    print('14) 权限分层（cyw_input / cyw_ledger）')
    set_perm(999002, 'cyw_input')
    set_perm(999003, 'cyw_ledger')
    # 读台账：登录即可（三个测试用户都放行）
    for hh in (H_USER, H_INPUT, H_LEDGER):
        r = client.get('/api/cyw/issues', headers=hh)
        assert r.status_code == 200, '登录用户应可读台账'
    # 登记：仅 input 可；ledger 403
    r = client.post('/api/cyw/issues', headers=H_INPUT, json=payload)
    assert r.status_code == 200, f'仅录入权限用户登记应放行，实际 {r.status_code}'
    issue_p = r.get_json()
    created['issues'].append(issue_p['id'])
    r = client.post('/api/cyw/issues', headers=H_LEDGER, json=payload)
    assert r.status_code == 403, f'仅台账权限用户登记应 403，实际 {r.status_code}'
    # 照片上传 / 详单：input 与 ledger 都可（共用接口取或）
    for hh in (H_INPUT, H_LEDGER):
        r = client.post('/api/cyw/upload-image', data={'file': (make_img(), 'scene.jpg')}, headers=hh)
        assert r.status_code == 200, f'共用上传口应对 input/ledger 均放行，实际 {r.status_code}'
        created['photos'].append(r.get_json()['url'])
        r = client.post(f"/api/cyw/issues/{issue_p['id']}/slip", headers=hh)
        assert r.status_code == 200, f'共用详单口应对 input/ledger 均放行，实际 {r.status_code}'
        created['slips'].append(r.get_json()['url'])
    # 反馈：仅 ledger 可；input 403
    r = client.post(f"/api/cyw/issues/{issue_p['id']}/feedback", headers=H_INPUT,
                    json={'feedback_note': 'x'})
    assert r.status_code == 403, f'仅录入权限用户反馈应 403，实际 {r.status_code}'
    r = client.post(f"/api/cyw/issues/{issue_p['id']}/feedback", headers=H_LEDGER,
                    json={'feedback_note': '冒烟测试：权限分层反馈'})
    assert r.status_code == 200, r.get_json()
    # 无权限用户：写接口全 403
    r = client.post('/api/cyw/issues', headers=H_USER, json=payload)
    assert r.status_code == 403, f'无权限用户登记应 403，实际 {r.status_code}'
    r = client.post('/api/cyw/spots', headers=H_USER, json={'monitor_no': 'X', 'name': 'X'})
    assert r.status_code == 403, '普通用户建点位应 403'
    # 字典：admin 直通，普通用户（含有 cyw_input）403
    r = client.post('/api/cyw/types', headers=H_INPUT, json={'name': 'x'})
    assert r.status_code == 403, f'普通用户维护类型字典应 403，实际 {r.status_code}'
    ok('读=登录即可；登记=cyw_input；反馈=cyw_ledger；上传/详单=或；字典=admin')

    # 15) AI 照片识别（私有化 Qwen2.5-VL；无 GPU/服务不可用时静默降级不阻断）
    print('15) AI 照片识别（parse-photo，私有化 Qwen2.5-VL）')
    r = client.post('/api/cyw/parse-photo', headers=H, json={'url': photo_url})
    j = r.get_json()
    assert r.status_code == 200 and 'success' in j, j
    if j['success']:
        assert j.get('description'), f'识别成功但描述为空: {j}'
        ok(f"AI 识别成功：{j['description'][:30]}（类型={j.get('type_name') or '未匹配'}，{j.get('elapsed_ms')}ms）")
    else:
        assert j.get('error'), f'降级应带原因: {j}'
        ok(f"无可用模型时静默降级（{j['error']}），登记流程不受影响")
    for bad in ('/etc/passwd', '/uploads/cyw/photos/notexist.jpg', '/uploads/cyw/photos/../secret.jpg'):
        r = client.post('/api/cyw/parse-photo', headers=H, json={'url': bad})
        assert r.status_code == 400, f'{bad} 应 400，实际 {r.status_code}'
    r = client.post('/api/cyw/parse-photo', headers=H_USER, json={'url': photo_url})
    assert r.status_code == 403, f'无权限用户识别应 403，实际 {r.status_code}'
    for hh in (H_INPUT, H_LEDGER):
        r = client.post('/api/cyw/parse-photo', headers=hh, json={'url': photo_url})
        assert r.status_code == 200, f'识别口应对 input/ledger 均放行，实际 {r.status_code}'
    ok('非法地址 400/404 + 无权限 403 + input/ledger 共用放行 + 降级不阻断')

    # 16) 历史台账 Excel 一键导入（仿真实台账格式：标题行+表头第二行+日期仅首行+序号名称连写+
    #     单位别名+全角冒号+分号手误+空结果+文件内重复+未识别类型+非月份sheet跳过+无序号点位合成编号）
    print('16) 历史台账一键导入（两段式）')
    H_IMP = {'Authorization': f'Bearer {make_token(1, "smoke_import", "admin")}'}
    r = client.post('/api/cyw/spots', headers=H, json={
        'monitor_no': '99001', 'name': '冒烟导入已有点位', 'road': '导入路'})
    imp_spot_id = r.get_json()['id']
    created['spots'].append(imp_spot_id)

    wb = Workbook(); ws = wb.active; ws.title = '1月'
    ws.append(['2026年创建文明城市视频摄像头测评问题（冒烟）'])
    ws.append(['日期', '序号', '时间', '摄像头点位', '问题描述', '处置单位', '处置结果',
               '', '', '', '', '', '机动车乱停放', '110件'])  # 右侧统计列应被忽略
    ws.append(['2026.1.6', 1, '17:35:00', '99001冒烟已有点位', '机动车乱停放', '交警队', '19:37已整改'])
    ws.append([None, 2, '18:01:00', '99002冒烟新点位甲', '路面有垃圾', '环卫中心', '18：30已清理'])  # 全角冒号
    ws.append([None, 3, '07;39', '冒烟无序号点位乙', '电动车乱停放', '冒烟新单位', ''])  # 分号手误+无序号+空结果
    ws.append(['2026.1.7早高峰', 1, '08:00:00', '99001冒烟已有点位', '机动车乱停放', '交警队', '19:37已整改'])
    ws.append([None, 2, '08:00:00', '99001冒烟已有点位', '机动车乱停放', '交警队', '19:37已整改'])  # 文件内重复
    ws.append([None, 3, '08:10:00', '99001冒烟已有点位', '环卫工人长时间停留', '执法队', '已整治'])  # 未识别类型（真实台账里唯一匹配不上的一条）
    ws2 = wb.create_sheet('本周重复率')  # 非月份 sheet 应跳过
    ws2.append(['日期', '点位', '问题描述'])
    ws2.append(['2026.1.6', '某点位', '机动车乱停放'])
    xb = io.BytesIO(); wb.save(xb); xb.seek(0)
    r = client.post('/api/cyw/issues/import', data={'file': (xb, 'ledger.xlsx')}, headers=H_IMP)
    j = r.get_json()
    assert r.status_code == 200 and j['success'], j
    assert j['sheets'] == ['1月'] and j['skipped_sheets'][0]['sheet'] == '本周重复率', j
    assert j['total'] == 6, j['total']
    assert j['stats']['closed_count'] == 5 and j['stats']['no_result'] == 1, j['stats']
    assert j['stats']['unmatched_type'] == 1 and j['stats']['dup_in_file'] == 1, j['stats']
    assert '冒烟新单位' in j['new_depts'] and '冒烟新点位甲' in j['new_spots'], j
    r1 = [x for x in j['rows'] if x['description'] == '机动车乱停放']
    assert all(x['spot_id'] == imp_spot_id and not x['spot_new'] for x in r1), '已有点位应按序号命中'
    flagged = [x['found_at'] for x in r1 if x['dup_in_file']]
    assert len(flagged) == 1 and flagged[0] == r1[-1]['found_at'] == '2026-01-07 08:00:00', flagged
    ok('预览：6 行/已办结 5/处置中(未反馈) 1/未识别类型 1/文件内重复 1，非月份 sheet 跳过，单位别名+全角冒号+分号均解析')

    # 未选回退类型应 400 拦截
    r = client.post('/api/cyw/issues/import/confirm', headers=H_IMP, json={'rows': j['rows']})
    assert r.status_code == 400 and '回退类型' in r.get_json()['error'], r.get_json()
    r = client.post('/api/cyw/issues/import/confirm', headers=H_IMP,
                    json={'rows': j['rows'], 'fallback_type_id': fb['id']})
    j2 = r.get_json()
    assert r.status_code == 200 and j2['success'], j2
    assert j2['inserted'] == 5 and j2['skipped_dup'] == 1, j2
    assert j2['created_spots'] == 2 and j2['created_depts'] == 1, j2
    # 幂等：原样再导全部判重跳过
    r = client.post('/api/cyw/issues/import/confirm', headers=H_IMP,
                    json={'rows': j['rows'], 'fallback_type_id': fb['id']})
    j3 = r.get_json()
    assert j3['inserted'] == 0 and j3['skipped_dup'] == 6, j3
    ok('确认导入 5 条（重复跳 1）+ 自动建点位 2/单位 1 + 未选回退类型 400 + 原样重导 0 新增全判重')

    # 落库抽验：状态/处理时间/反馈/编号日期/合成序号
    with engine.connect() as conn:
        imp_rows = conn.execute(text(
            "SELECT i.id, i.case_no, i.description, i.status, i.found_at, i.closed_at, i.closed_by, "
            "i.is_fed, i.feedback_note, s.monitor_no, d.name AS dept_name, t.name AS type_name "
            "FROM cyw_issue i JOIN cyw_spot s ON s.id = i.spot_id JOIN cyw_type t ON t.id = i.type_id "
            "JOIN cyw_dept d ON d.id = i.dept_id "
            "WHERE i.created_by = 'smoke_import' ORDER BY i.found_at")).mappings().fetchall()
        xc = conn.execute(text(
            "SELECT monitor_no, name, note FROM cyw_spot WHERE name = '冒烟无序号点位乙'")).mappings().first()
    assert len(imp_rows) == 5, len(imp_rows)
    jzc = [r_ for r_ in imp_rows if r_['description'] == '机动车乱停放']
    assert len(jzc) == 2 and all(r_['status'] == '已办结' and r_['closed_by'] == '历史导入'
                                 and r_['is_fed'] and r_['feedback_note'] == '19:37已整改' for r_ in jzc), jzc
    assert str(jzc[0]['closed_at']) == '2026-01-06 19:37:00', jzc[0]
    assert jzc[0]['case_no'].startswith('CW20260106-') and jzc[1]['case_no'].startswith('CW20260107-'), jzc
    assert jzc[0]['type_name'] == '机动车乱停放' and jzc[0]['dept_name'] == '交警队', jzc[0]
    lm = [r_ for r_ in imp_rows if r_['description'] == '路面有垃圾'][0]
    assert lm['status'] == '已办结' and str(lm['closed_at']) == '2026-01-06 18:30:00', lm  # 全角冒号解析
    assert lm['type_name'] == '垃圾不洁' and lm['dept_name'] == '环卫中心', lm  # 单位按台账原名入库
    ddc = [r_ for r_ in imp_rows if r_['description'] == '电动车乱停放'][0]
    assert ddc['status'] == '处置中' and not ddc['is_fed'] and ddc['dept_name'] == '冒烟新单位', ddc
    assert ddc['type_name'] == '非机动车乱停放', ddc
    assert ddc['found_at'].strftime('%H:%M') == '07:39', ddc  # 分号手误时间
    lg = [r_ for r_ in imp_rows if r_['description'] == '环卫工人长时间停留'][0]
    assert lg['type_name'] == '其他', lg  # 未识别行走回退类型
    assert xc['monitor_no'].startswith('XC-') and '自动创建' in xc['note'], xc
    ok('落库抽验：办结态/处理时间(含全角冒号)/反馈说明/编号按发现日期/无序号点位合成 XC- 编号')

    # ==================== 17) 在岗抽查 ====================
    # 关键不变量：只抽城市管理局点位、倒计时截止时间由服务端写、过期自动判不在岗、
    # 刷新可恢复、管理员修正留痕
    print('17) 在岗抽查（管理单位筛选/随机抽点/去电倒计时/自动判定/修正留痕/报告导出）')

    # 取人规则单测：一个点位出两条——环卫一条、执法一条，缺的那侧记「无联系人」
    from cyw_routes import _pick_contacts_for_check as _pick2, _now
    R = _pick2([{'dept_label': '环卫中心·点位主管', 'person': '张三', 'phone': '1'},
                {'dept_label': '执法队·东城分队三中队', 'person': '赵六', 'phone': '4'}])
    assert R == [{'dept_label': '环卫中心·点位主管', 'person': '张三', 'phone': '1', 'pick_rule': '环卫点位主管'},
                 {'dept_label': '执法队·东城分队三中队', 'person': '赵六', 'phone': '4', 'pick_rule': '执法首位'}], R
    # 建投在前也不能被选中；没有点位主管时退回任一环卫联系人
    R = _pick2([{'dept_label': '建投', 'person': '李四', 'phone': '2'},
                {'dept_label': '环卫中心', 'person': '王五', 'phone': '3'}])
    assert [r['pick_rule'] for r in R] == ['环卫联系人', '无联系人'], R
    assert R[0]['person'] == '王五' and R[1]['person'] is None, R
    # 只有执法、没有环卫：环卫那侧留一条「未登记」，不悄悄少打一个电话
    R = _pick2([{'dept_label': '建投', 'person': '李四', 'phone': '2'},
                {'dept_label': '执法队·东城分队三中队', 'person': '赵六', 'phone': '4'}])
    assert [r['pick_rule'] for r in R] == ['无联系人', '执法首位'], R
    assert R[1]['person'] == '赵六', R
    # 盬街点位的执法 label 用「盬街」前缀
    R = _pick2([{'dept_label': '盬街北口·中城分队十三中队', 'person': '孙七', 'phone': '5'}])
    assert [r['pick_rule'] for r in R] == ['无联系人', '执法首位'], R
    # 两侧都没有（夜市只有点位总负责人/点位责任人）：兜底一条，
    # 不把同一个人拆成环卫/执法两行各打一遍
    R = _pick2([{'dept_label': '点位总负责人', 'person': '周八', 'phone': '6'}])
    assert R == [{'dept_label': '点位总负责人', 'person': '周八', 'phone': '6', 'pick_rule': '点位兜底'}], R
    # 联系人表全空时退回点位档案上的负责人
    R = _pick2([], ('点位负责人老吴', '137'))
    assert R == [{'dept_label': '点位负责人', 'person': '点位负责人老吴', 'phone': '137', 'pick_rule': '点位兜底'}], R
    assert _pick2([]) == [{'dept_label': '点位', 'person': None, 'phone': None, 'pick_rule': '无联系人'}], _pick2
    ok('取人规则单测：环卫/执法各一行、缺侧记无联系人、盬街前缀、点位兜底/档案兜底/全空 七种形态正确')

    # 记录当前最大批次 id：清理时只删 id 大于它的，绝不碰冒烟之前已存在的真实抽查记录
    with engine.begin() as conn:
        created['check_id_base'] = conn.execute(
            text("SELECT COALESCE(MAX(id), 0) FROM cyw_check_batch")).scalar()
        mu_total = conn.execute(text(
            "SELECT COUNT(*) FROM cyw_spot WHERE manage_unit = '城市管理局'")).scalar()

    # 建一个城市管理局的测试点位（带联系人）供状态机断言用：
    # 随机抽中的点位有无联系人不确定，行为断言必须跑在可控数据上
    r = client.post('/api/cyw/spots', headers=H, json={
        'monitor_no': 'CYW-TEST-CHK', 'name': '冒烟抽查点位', 'road': '冒烟抽查路',
        'manage_unit': '城市管理局', 'is_key': False, 'lng': 110.981, 'lat': 35.141,
        'contacts': [
            {'dept_label': '环卫中心·点位主管', 'person': '测试甲', 'phone': '13500000001'},
            {'dept_label': '执法队·东城分队三中队', 'person': '测试乙', 'phone': '13500000002'},
        ]})
    assert r.status_code == 200 and r.get_json().get('success'), r.get_json()
    chk_spot_id = r.get_json()['id']
    created['spots'].append(chk_spot_id)

    r = client.post('/api/cyw/check/start', json={'spot_count': 5}, headers=H)
    assert r.status_code == 200, r.data
    b = r.get_json()['batch']
    created['check_batches'].append(b['id'])
    expect_n = min(5, mu_total)
    spot_ids = {i['spot_id'] for i in b['items']}
    assert len(spot_ids) == expect_n, (len(spot_ids), mu_total)
    # 一个点位出两条：环卫一条、执法一条；夜市那类只有负责人的点位出一条
    grp = {}
    for i in b['items']:
        grp.setdefault(i['spot_id'], []).append(i)
    assert all(1 <= len(v) <= 2 for v in grp.values()), grp
    sys_cnt = len(b['items'])
    assert sys_cnt >= expect_n, (sys_cnt, expect_n)
    assert b['status'] == '进行中' and b['batch_no'].startswith('CC'), b
    assert b['wait_count'] == sys_cnt and b['on_count'] == 0 and b['off_count'] == 0, b
    ok(f'发起抽查：从 {mu_total} 个城市管理局点位随机抽 {expect_n} 个、共 {sys_cnt} 项'
       f'（每点位环卫/执法各一行），批次号 CC 前缀，全部待抽查')

    # 每个点位都必须有取人规则；有 person 的必须带电话
    for it in b['items']:
        assert it['pick_rule'] in ('环卫点位主管', '环卫联系人', '执法首位', '点位兜底', '无联系人'), it
        if it['person']:
            assert it['phone'], it
    # 出两条的点位，两条必须分属环卫侧与执法侧（规则不会重复）
    for sid, v in grp.items():
        if len(v) == 2:
            assert len({i['pick_rule'] for i in v}) == 2, v
    # 关键新要求：抽中的点位管理单位必须全是「城市管理局」
    with engine.begin() as conn:
        bad = conn.execute(text(
            "SELECT COUNT(*) FROM cyw_check_item i JOIN cyw_spot s ON s.id = i.spot_id "
            "WHERE i.batch_id = :b AND s.manage_unit <> '城市管理局'"), {'b': b['id']}).scalar()
    assert bad == 0, f'抽中了 {bad} 个非城市管理局点位'
    ok('管理单位筛选：抽中的点位全部是「城市管理局」，开发区点位被排除')

    # 两侧取人交叉核对：随机抽到哪个点位不确定，所以不比对具体人名，
    # 而是把系统落库的每一行与取人函数对该点位联系人的计算结果逐条对齐。
    # 这个断言在本地稀疏数据（点位无联系人）和服务器真实数据上都成立。
    with engine.begin() as conn:
        for sid in sorted(spot_ids):
            rows = conn.execute(text(
                "SELECT dept_label, person, phone FROM cyw_spot_contact "
                "WHERE spot_id=:s ORDER BY sort_order, id"), {'s': sid}).fetchall()
            srow = conn.execute(text(
                "SELECT contact_name, contact_phone FROM cyw_spot WHERE id=:s"), {'s': sid}).fetchone()
            want = _pick2([{'dept_label': r[0], 'person': r[1], 'phone': r[2]} for r in rows],
                          (srow[0], srow[1]) if srow else None)
            got = grp[sid]
            assert len(got) == len(want), (sid, got, want)
            for g, w in zip(got, want):
                assert (g['person'], g['phone'], g['pick_rule']) == (w['person'], w['phone'], w['pick_rule']), (g, w)
    ok('两侧取人交叉核对：落库行与取人函数对同一点位联系人的计算结果逐条一致（环卫/执法各一行）')

    # 往本批次追加两行确定性明细，指向刚建的城市管理局测试点位。
    # 先记 item 最大 id：随机抽取可能恰好命中同名的历史残留点位，
    # 靠 id 增量取行才不会把别人的行一起圈进来
    with engine.begin() as conn:
        item_id_base = conn.execute(text(
            "SELECT COALESCE(MAX(id), 0) FROM cyw_check_item")).scalar()
    with engine.begin() as conn:
        for label, person, phone, rule in [
            ('环卫中心·点位主管', '测试甲', '13500000001', '环卫点位主管'),
            ('执法队·东城分队三中队', '测试乙', '13500000002', '执法首位'),
        ]:
            conn.execute(text(
                "INSERT INTO cyw_check_item "
                "(batch_id, spot_id, spot_no, spot_name, dept_label, person, phone, pick_rule, status) "
                "VALUES (:b, :s, :no, :nm, :dl, :p, :ph, :rule, '待抽查')"),
                {'b': b['id'], 's': chk_spot_id, 'no': 'CYW-TEST-CHK', 'nm': '冒烟抽查点位',
                 'dl': label, 'p': person, 'ph': phone, 'rule': rule})
        det = conn.execute(text(
            "SELECT id, person FROM cyw_check_item WHERE id > :base ORDER BY id"),
            {'base': item_id_base}).fetchall()
    assert len(det) == 2, det
    target_id, victim_id = det[0][0], det[1][0]

    # 去电 -> 服务端写 deadline_at = now + 5 分钟
    r = client.post(f'/api/cyw/check/item/{target_id}/call', headers=H)
    assert r.status_code == 200, r.data
    jd = r.get_json()
    assert jd['window_minutes'] == 5, jd
    assert jd['called_at'] and jd['deadline_at'], jd
    delta = (datetime.datetime.strptime(jd['deadline_at'], '%Y-%m-%d %H:%M:%S')
             - datetime.datetime.strptime(jd['called_at'], '%Y-%m-%d %H:%M:%S')).total_seconds()
    assert 295 <= delta <= 305, jd  # 5 分钟整（容 5 秒执行误差）
    ok('去电：服务端写入 called_at 与 deadline_at，间隔恰为 5 分钟')

    # 重复去电应被拒——否则 5 分钟窗口可被无限续期，「到点自动判不在岗」永远不触发
    r = client.post(f'/api/cyw/check/item/{target_id}/call', headers=H)
    assert r.status_code == 400, (r.status_code, r.data)
    assert '倒计时' in r.get_json()['error'], r.data
    ok('重复去电被拒（400），倒计时窗口不可续期')

    # 倒计时内点「在岗」-> 在岗
    r = client.post(f'/api/cyw/check/item/{target_id}/on-duty', headers=H)
    assert r.status_code == 200, r.data
    assert r.get_json()['status'] == '在岗', r.data
    r = client.get('/api/cyw/check/current', headers=H)
    cur = r.get_json()['batch']
    me = [i for i in cur['items'] if i['id'] == target_id][0]
    assert me['status'] == '在岗' and me['result_by'] == 'admin', me
    assert cur['on_count'] == 1, cur
    ok('倒计时内点在岗：状态置在岗，current 接口刷新后仍在')

    # 已判在岗再点 -> 拒
    r = client.post(f'/api/cyw/check/item/{target_id}/on-duty', headers=H)
    assert r.status_code == 400, (r.status_code, r.data)
    ok('重复点在岗被拒（400）')

    # 关键路径：把 deadline_at 改到过去 -> 读时兜底扫必须自动判「不在岗」
    client.post(f'/api/cyw/check/item/{victim_id}/call', headers=H)
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE cyw_check_item SET deadline_at = :d WHERE id = :i"),
            {'d': _now() - datetime.timedelta(minutes=1), 'i': victim_id})
    # 不点「在岗」，只读一次 current —— 兜底扫应把它结掉
    r = client.get('/api/cyw/check/current', headers=H)
    cur = r.get_json()['batch']
    vv = [i for i in cur['items'] if i['id'] == victim_id][0]
    assert vv['status'] == '不在岗', vv
    assert vv['result_by'] == '系统自动判定', vv
    assert cur['off_count'] == 1, cur
    ok('倒计时归零未点在岗：读时兜底扫自动判「不在岗」，判定人=系统自动判定')

    # 归零后再点「在岗」-> 409 need_correct，引导走修正通道
    r = client.post(f'/api/cyw/check/item/{victim_id}/on-duty', headers=H)
    assert r.status_code == 409, (r.status_code, r.data)
    assert r.get_json().get('need_correct') is True, r.data
    ok('归零后点在岗被拒（409 need_correct），不静默改判')

    # 管理员修正：普通用户无权（admin_required）
    r = client.put(f'/api/cyw/check/item/{victim_id}/correct',
                   json={'status': '在岗', 'reason': '监控目视确认'}, headers=H_USER)
    assert r.status_code == 403, (r.status_code, r.data)
    ok('普通用户调用修正接口被拒（403，admin_required）')

    r = client.put(f'/api/cyw/check/item/{victim_id}/correct',
                   json={'status': '在岗', 'reason': '监控目视确认'}, headers=H)
    assert r.status_code == 200, r.data
    r = client.get(f'/api/cyw/check/batch/{cur["id"]}', headers=H)
    vv = [i for i in r.get_json()['batch']['items'] if i['id'] == victim_id][0]
    assert vv['status'] == '在岗' and vv['corrected'] is True, vv
    assert vv['corrected_by'] == 'admin' and vv['corrected_reason'] == '监控目视确认', vv
    assert vv['result_by'] == '系统自动判定', vv  # 原判定人保留，修正信息单独记
    ok('管理员修正：判定被覆盖，corrected/修正人/原因全部留痕')

    # 修正值不合法 -> 400
    r = client.put(f'/api/cyw/check/item/{victim_id}/correct',
                   json={'status': '迟到'}, headers=H)
    assert r.status_code == 400, (r.status_code, r.data)
    ok('修正值非法被拒（400）')

    # 结束抽查：未判定的一律不在岗
    r = client.post(f'/api/cyw/check/batch/{cur["id"]}/finish', headers=H)
    assert r.status_code == 200, r.data
    fin = r.get_json()['batch']
    assert fin['status'] == '已结束' and fin['wait_count'] == 0, fin
    assert fin['finished_at'], fin
    assert all(i['status'] in ('在岗', '不在岗') for i in fin['items']), fin
    ok('结束抽查：未判定明细全部按不在岗结掉，wait_count=0')

    # 结束后 current 应为空，历史里能查到这批
    r = client.get('/api/cyw/check/current', headers=H)
    assert r.get_json()['batch'] is None, r.data
    r = client.get('/api/cyw/check/history', headers=H)
    hj = r.get_json()
    assert hj['total'] >= 1, hj
    mine = [x for x in hj['list'] if x['id'] == cur['id']]
    assert mine and mine[0]['item_cnt'] == sys_cnt + 2, mine  # 随机抽的 + 确定性 2
    ok('结束后 current 为空，history 可回溯该批次')

    # 报告导出：BOM + 中文文件名 + 汇总与明细齐全
    r = client.get(f'/api/cyw/check/batch/{cur["id"]}/export', headers=H)
    assert r.status_code == 200, r.data
    cd = r.headers.get('Content-Disposition', '')
    assert "filename*=UTF-8''%E5%88%9B%E6%96%87" in cd, cd
    assert '.txt' in cd, cd
    txt = r.data.decode('utf-8-sig')
    assert '创文点位在岗抽查报告' in txt and '抽查批次' in txt, txt[:200]
    assert '【抽查汇总】' in txt and '【抽查明细】' in txt, txt[:300]
    person_cnt = sum(1 for i in fin['items'] if i['person'])
    assert f'共{len(fin["items"])}项' in txt and f'{person_cnt}人）' in txt, txt[:300]
    assert f'抽查 {len({i["spot_id"] for i in fin["items"]})} 个点位' in txt, txt[:300]
    # 明细只打「点位名称 + 两侧在岗情况」：人名、电话、去电时间、修正过程一律不进去
    for nm in {i['spot_name'] for i in fin['items']}:
        assert nm in txt, (nm, txt[:400])
    # 点位行格式 = 完整点位名称（含道路）+（监控序号）：点名「冒烟抽查点位」不含路，
    # 必须拼上 road「冒烟抽查路」并带监控序号；点名自带路名的（禹都东街…）不叠字
    assert '冒烟抽查路冒烟抽查点位（CYW-TEST-CHK）' in txt, txt[:400]
    for it_ in fin['items']:
        assert it_['status'] in txt, (it_['status'], txt[:400])
    assert '测试甲' not in txt and '测试乙' not in txt, txt[:400]
    assert '13500000001' not in txt and '13500000002' not in txt, txt[:400]
    assert '监控目视确认' not in txt and '原判定' not in txt and '去电时间' not in txt, txt[:400]
    # 被修正过的那个明细，状态要如实反映成修正后的值
    vv_status = [i for i in fin['items'] if i['id'] == victim_id][0]['status']
    assert f'执法：{vv_status}' in txt, (vv_status, txt[:400])
    ok('报告导出：BOM + RFC5987 中文文件名 + 汇总不变 + 明细简化（点位=完整名称含道路+监控序号）')
    # 权限分层：无权限普通用户 403
    r = client.post('/api/cyw/check/start', json={'spot_count': 3}, headers=H_USER)
    assert r.status_code == 403, (r.status_code, r.data)
    ok('无 cyw_check 权限的普通用户发起抽查被拒（403）')



    print('\n全部通过 ✔  清理测试数据...')
finally:
    # 按 ID 精确清理（禁整表清空）
    with engine.begin() as conn:
        for iid in created['issues']:
            conn.execute(text("DELETE FROM cyw_issue_log WHERE issue_id = :i"), {'i': iid})
            conn.execute(text("DELETE FROM cyw_issue WHERE id = :i"), {'i': iid})
        for sid in created['spots']:
            conn.execute(text("DELETE FROM cyw_spot_contact WHERE spot_id = :s"), {'s': sid})
            conn.execute(text("DELETE FROM cyw_spot WHERE id = :s"), {'s': sid})
        # 清理权限测试行（按 user_id 精确删，不影响真实账号）
        for uid in PERM_USERS:
            conn.execute(text("DELETE FROM permissions WHERE user_id = :u"), {'u': uid})
        # 清理导入测试数据（created_by 标记 + 冒烟名称标记 + 单位名，禁整表清空；
        # 不按 note='历史台账导入自动创建%' 删——用户真实导入的点位也是这备注，会误删）
        imp_ids = [r[0] for r in conn.execute(
            text("SELECT id FROM cyw_issue WHERE created_by = 'smoke_import'"))]
        for iid in imp_ids:
            conn.execute(text("DELETE FROM cyw_issue_log WHERE issue_id = :i"), {'i': iid})
        conn.execute(text("DELETE FROM cyw_issue WHERE created_by = 'smoke_import'"))
        conn.execute(text("DELETE FROM cyw_spot WHERE name LIKE '冒烟%'"))
        conn.execute(text("DELETE FROM cyw_dept WHERE name = '冒烟新单位'"))
        # 兜底：本脚本中途崩溃时 created 列表可能不全，按标记再扫一遍
        sweep_test_data(conn)
    for url in created['slips']:
        try:
            os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), url.lstrip('/')))
        except OSError:
            pass
    for url in created['photos']:
        try:
            os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), url.lstrip('/')))
        except OSError:
            pass
    # 清理上传的测试照片
    photo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'cyw', 'photos')
    try:
        for fn in os.listdir(photo_dir):
            fp = os.path.join(photo_dir, fn)
            if os.path.isfile(fp) and os.path.getsize(fp) < 20000:
                os.remove(fp)  # 仅清冒烟产生的小图
    except OSError:
        pass
    print('清理完成')
