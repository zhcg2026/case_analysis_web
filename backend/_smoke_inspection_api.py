# -*- coding: utf-8 -*-
"""HTTP 接口实测：用 Flask test client + forged JWT 真实调用 7 个接口。

覆盖：
1. 照片上传 -> 拿 file_token + phash
2. 导入 -> 七项对账计数逐项核对
3. 重复导入同一份表同一行 -> duplicates_skipped 拦截（幂等）
4. 文字相同但照片不同 -> 直接入库不进队列（韩信路4行场景）
5. 照片与库内完全相同 -> 进 insp_dup_candidate（判重生效）
6. 判定 merged -> 整改图挂到目标案件
7. 判定 new -> 正式插入为新案
8. 查询/统计接口
9. 导出 xlsx（默认文件名版 + with_images=1 嵌图版）

卫生约定：测试数据固定前缀 INSPTEST-，用完按 ID 精确删除，不清整表。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import jwt
from PIL import Image
from sqlalchemy import text

import app as app_module
from inspection_routes import STAGE_DIR, _hamming

SECRET = os.getenv('JWT_SECRET_KEY')
engine = app_module.engine
client = app_module.app.test_client()

H = {'Authorization': f'Bearer {jwt.encode({"user_id": 1, "username": "admin", "role": "admin"}, SECRET, algorithm="HS256")}'}
H_USER = {'Authorization': f'Bearer {jwt.encode({"user_id": 999001, "username": "noperm", "role": "user"}, SECRET, algorithm="HS256")}'}

FAILS = []


def check(label, actual, expect):
    ok = actual == expect
    print(f'  [{"PASS" if ok else "FAIL"}] {label}: 实际={actual} 期望={expect}')
    if not ok:
        FAILS.append(f'{label}: 实际={actual} 期望={expect}')
    return ok


def make_photo(color, size=(400, 300), seed=0):
    """造一张带内容的测试图（加噪点，避免纯色导致 phash 退化）"""
    import random
    random.seed(seed)
    im = Image.new('RGB', size, color)
    px = im.load()
    for _ in range(800):
        x = random.randrange(size[0])
        y = random.randrange(size[1])
        px[x, y] = (random.randrange(256), random.randrange(256), random.randrange(256))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=90)
    return buf.getvalue()


def upload(photos):
    """photos: [(filename, bytes)] -> {filename: (token, phash)}"""
    data = {}
    for fn, raw in photos:
        data[f'file_{fn}'] = (io.BytesIO(raw), fn)
    r = client.post('/api/inspection/photos', headers=H,
                    data={'files': [(io.BytesIO(raw), fn) for fn, raw in photos]},
                    content_type='multipart/form-data')
    assert r.status_code == 200, f'上传失败: {r.status_code} {r.get_data(as_text=True)[:300]}'
    body = r.get_json()
    out = {}
    for item in body['saved']:
        out[item['orig_name']] = (item['file_token'], item['phash'])
    return out, body


def cleanup():
    """删掉两拨残留：
    1) source_file 带 INSPTEST- 前缀的案件（含 merged 判定时被并图的目标案件）
    2) 上一轮 merged 之后，源案件的记录虽已删，但目标案件若是历史案件则不应动——
       故这里只删测试案件，靠 location 前缀 INSPTEST- 精确圈定，绝不碰 539 条历史数据。
    """
    with engine.begin() as conn:
        ids = [r[0] for r in conn.execute(text(
            "SELECT id FROM insp_case WHERE location LIKE 'INSPTEST-%' "
            "OR source_file LIKE 'INSPTEST-%'")).fetchall()]
        for i in ids:
            conn.execute(text("DELETE FROM insp_photo WHERE case_id = :i"), {'i': i})
            conn.execute(text("DELETE FROM insp_case WHERE id = :i"), {'i': i})
        # merged 时整改图被挂到目标案件上，若目标是历史案件，要把多加的 rect 图摘掉
        # （本次测试 merged 的目标就是测试案件自己，故上面的删除已覆盖）
        conn.execute(text("DELETE FROM insp_dup_candidate WHERE batch_no LIKE 'INSPTEST-%'"))
    # 清掉测试暂存图
    n = 0
    for fn in os.listdir(STAGE_DIR):
        if fn.endswith('.jpg'):
            os.remove(os.path.join(STAGE_DIR, fn))
            n += 1
    if ids or n:
        print(f'  (清理测试案件 {len(ids)} 条、暂存图 {n} 张)')


def main():
    cleanup()
    print('=' * 72)
    print('1. 照片上传')
    pa = make_photo((200, 30, 30), seed=1)
    pb = make_photo((30, 200, 30), seed=2)
    pc = make_photo((30, 30, 200), seed=3)
    up, upbody = upload([('a.jpg', pa), ('b.jpg', pb), ('c.jpg', pc)])
    check('上传成功数', len(up), 3)
    check('上传 errors 数', len(upbody['errors']), 0)
    tokens = {k: v[0] for k, v in up.items()}
    hashes = {k: v[1] for k, v in up.items()}
    print(f'     phash: a={hashes["a.jpg"][:8]} b={hashes["b.jpg"][:8]} c={hashes["c.jpg"][:8]}')

    print('\n2. 导入：3 件（1件带2张问题图+1张整改图，2件各1张问题图）')
    pg = make_photo((90, 90, 90), seed=7)
    upg, _ = upload([('g.jpg', pg)])
    payload = {
        'batch_no': 'INSPTEST-1',
        'source_file': 'INSPTEST-表1.xlsx',
        'cases': [
            {'source_row': 1, 'case_date': '2026-10-22', 'road': '测试路甲',
             'location': 'INSPTEST-位置甲', 'problem': 'INSPTEST-问题甲',
             'dept': '市政', 'result': '', 'status': '待整改',
             'photos': [{'kind': 'problem', 'seq': 1, 'file_token': tokens['a.jpg'], 'phash': hashes['a.jpg']},
                        {'kind': 'problem', 'seq': 2, 'file_token': tokens['b.jpg'], 'phash': hashes['b.jpg']},
                        {'kind': 'rectify', 'seq': 1, 'file_token': tokens['c.jpg'], 'phash': hashes['c.jpg']}]},
            {'source_row': 2, 'case_date': '10月22日', 'road': '测试路乙',
             'location': 'INSPTEST-位置乙', 'problem': 'INSPTEST-问题乙',
             'dept': '执法', 'result': '已处理', 'status': '已整改',
             'photos': [{'kind': 'problem', 'seq': 1, 'file_token': upg['g.jpg'][0], 'phash': upg['g.jpg'][1]}]},
            {'source_row': 3, 'case_date': '2026-10-22', 'road': '测试路丙',
             'location': 'INSPTEST-位置丙', 'problem': 'INSPTEST-问题丙',
             'dept': '园林绿化服务中心', 'result': '', 'status': '整改中',
             'photos': []},
        ],
    }
    r = client.post('/api/inspection/import', headers=H, json=payload)
    body = r.get_json()
    print('   ', json.dumps({k: v for k, v in body.items() if k != 'errors'}, ensure_ascii=False))
    for e in body['errors']:
        print('     error:', e)
    check('status_code', r.status_code, 200)
    check('inserted', body['inserted'], 3)
    check('updated', body['updated'], 0)
    check('duplicates_skipped', body['duplicates_skipped'], 0)
    check('pending_review', body['pending_review'], 0)
    check('photos_received', body['photos_received'], 4)
    check('photos_saved', body['photos_saved'], 4)
    # dept 归一化 + 状态两值化
    with engine.connect() as conn:
        rows = {r[0]: r[1:] for r in conn.execute(text(
            "SELECT location, dept, status, case_date FROM insp_case "
            "WHERE source_file = 'INSPTEST-表1.xlsx'")).fetchall()}
    check('执法→执法队', rows['INSPTEST-位置乙'][0], '执法队')
    check('园林绿化服务中心→园林', rows['INSPTEST-位置丙'][0], '园林')
    check('整改中→待整改', rows['INSPTEST-位置丙'][1], '待整改')
    check('10月22日→2026-10-22', str(rows['INSPTEST-位置乙'][2]), '2026-10-22')

    print('\n3. 重复导入同一份表（幂等拦截）')
    r = client.post('/api/inspection/import', headers=H, json=payload)
    body2 = r.get_json()
    check('duplicates_skipped', body2['duplicates_skipped'], 3)
    check('inserted', body2['inserted'], 0)
    check('photos_saved', body2['photos_saved'], 0)

    print('\n4. 文字相同但照片不同 -> 直接入库（韩信路4行场景）')
    pd = make_photo((200, 200, 30), seed=4)
    pe = make_photo((200, 30, 200), seed=5)
    up2, _ = upload([('d.jpg', pd), ('e.jpg', pe)])
    payload4 = {
        'batch_no': 'INSPTEST-2', 'source_file': 'INSPTEST-表2.xlsx',
        'cases': [
            {'source_row': 10, 'case_date': '2026-10-22', 'road': '韩信路',
             'location': '韩信路（金海湾-御景华庭）', 'problem': '路面破损4处',
             'dept': '市政', 'status': '待整改',
             'photos': [{'kind': 'problem', 'seq': 1, 'file_token': up2['d.jpg'][0], 'phash': up2['d.jpg'][1]}]},
            {'source_row': 11, 'case_date': '2026-10-22', 'road': '韩信路',
             'location': '韩信路（金海湾-御景华庭）', 'problem': '路面破损4处',
             'dept': '市政', 'status': '待整改',
             'photos': [{'kind': 'problem', 'seq': 1, 'file_token': up2['e.jpg'][0], 'phash': up2['e.jpg'][1]}]},
        ],
    }
    r = client.post('/api/inspection/import', headers=H, json=payload4)
    b4 = r.get_json()
    print('   ', json.dumps({k: v for k, v in b4.items() if k != 'errors'}, ensure_ascii=False))
    check('两行全入库', b4['inserted'], 2)
    check('不进重复队列', b4['pending_review'], 0)

    print('\n5. 照片与库内完全相同 -> 进人工确认队列')
    # 用第2步已入库的 a.jpg（INSPTEST-位置甲 的问题图1）
    payload5 = {
        'batch_no': 'INSPTEST-3', 'source_file': 'INSPTEST-表3.xlsx',
        'cases': [
            {'source_row': 20, 'case_date': '2026-10-22', 'road': '测试路丁',
             'location': 'INSPTEST-位置丁', 'problem': 'INSPTEST-问题丁',
             'dept': '市政', 'status': '待整改',
             'photos': [{'kind': 'problem', 'seq': 1, 'file_token': tokens['a.jpg'], 'phash': hashes['a.jpg']}]},
        ],
    }
    r = client.post('/api/inspection/import', headers=H, json=payload5)
    b5 = r.get_json()
    print('   ', json.dumps({k: v for k, v in b5.items() if k != 'errors'}, ensure_ascii=False))
    check('inserted', b5['inserted'], 0)
    check('pending_review', b5['pending_review'], 1)
    with engine.connect() as conn:
        cand = conn.execute(text(
            "SELECT id, matched_case_id, match_reason, decision FROM insp_dup_candidate "
            "WHERE batch_no = 'INSPTEST-3'")).fetchall()
    check('候选条数', len(cand), 1)
    cand_id, matched_id = cand[0][0], cand[0][1]
    check('match_reason', cand[0][2], 'phash')
    print(f'     候选#{cand_id} 命中案件#{matched_id}')

    print('\n6. 查询候选清单')
    r = client.get('/api/inspection/dup-candidates?batch_no=INSPTEST-3', headers=H)
    items = r.get_json()['items']
    check('候选接口返回数', len(items), 1)
    check('matched_case 有内容', items[0]['matched_case'] is not None, True)

    print('\n7. 判定 merged：整改图挂到目标案件')
    pf = make_photo((30, 200, 200), seed=6)
    up3, _ = upload([('f.jpg', pf)])
    r = client.post(f'/api/inspection/dup-candidates/{cand_id}', headers=H,
                    json={'decision': 'merged'})
    b7 = r.get_json()
    print('   ', json.dumps(b7, ensure_ascii=False))
    check('merged 成功', b7.get('ok'), True)
    with engine.connect() as conn:
        n_rect = conn.execute(text(
            "SELECT COUNT(*) FROM insp_photo WHERE case_id = :i AND kind = 'rectify'"
        ), {'i': matched_id}).scalar()
    check('目标案件整改图数', n_rect, 1)
    # 重复判定应被拒
    r = client.post(f'/api/inspection/dup-candidates/{cand_id}', headers=H, json={'decision': 'new'})
    check('重复判定返回409', r.status_code, 409)

    print('\n8. 判定 new：正式插入为新案')
    payload8 = {
        'batch_no': 'INSPTEST-4', 'source_file': 'INSPTEST-表4.xlsx',
        'cases': [
            {'source_row': 30, 'case_date': '2026-10-22', 'road': '测试路戊',
             'location': 'INSPTEST-位置戊', 'problem': 'INSPTEST-问题戊',
             'dept': '市容秩序科', 'status': '待整改',
             'photos': [{'kind': 'problem', 'seq': 1, 'file_token': tokens['a.jpg'], 'phash': hashes['a.jpg']}]},
        ],
    }
    r = client.post('/api/inspection/import', headers=H, json=payload8)
    b8 = r.get_json()
    check('pending_review', b8['pending_review'], 1)
    with engine.connect() as conn:
        c2 = conn.execute(text(
            "SELECT id FROM insp_dup_candidate WHERE batch_no = 'INSPTEST-4'")).fetchone()
    r = client.post(f'/api/inspection/dup-candidates/{c2[0]}', headers=H, json={'decision': 'new'})
    b8b = r.get_json()
    print('   ', json.dumps(b8b, ensure_ascii=False))
    check('new 成功', b8b.get('ok'), True)
    new_id = b8b['case_id']
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT location, dept, status FROM insp_case WHERE id = :i"), {'i': new_id}).fetchone()
    check('新案位置', row[0], 'INSPTEST-位置戊')
    check('新案部门', row[1], '市容秩序科')
    with engine.connect() as conn:
        np_ = conn.execute(text(
            "SELECT COUNT(*) FROM insp_photo WHERE case_id = :i"), {'i': new_id}).scalar()
    check('新案照片数', np_, 1)

    print('\n9. 查询与统计')
    r = client.get('/api/inspection/cases?keyword=INSPTEST&size=100', headers=H)
    b9 = r.get_json()
    # keyword 只匹配 location/problem/result，不含 source_file：
    # 表1 三件（位置甲/乙/丙）+ 第8步 new 一件（位置戊）= 4；
    # 表2 两件的 location 是"韩信路（金海湾-御景华庭）"，不含 INSPTEST 故不计入
    check('查询总数', b9['total'], 4)
    check('查询返回带照片', all('photos' in x for x in b9['items']), True)
    r = client.get('/api/inspection/stats?keyword=INSPTEST', headers=H)
    print('   stats:', json.dumps({k: v for k, v in r.get_json().items() if k != 'by_road'},
                                  ensure_ascii=False)[:300])
    r = client.get('/api/inspection/cases?date_from=2026-10-01&date_to=2026-10-22&size=1', headers=H)
    total_all = r.get_json()['total']
    check('全库案件总数(含历史539)', total_all, 545)

    print('\n10. 权限：无权限用户应被拒')
    r = client.get('/api/inspection/cases', headers=H_USER)
    check('无权限返回403', r.status_code, 403)
    r = client.get('/api/inspection/cases')
    check('无 token 返回401', r.status_code, 401)

    print('\n11. 导出 xlsx')
    r = client.get('/api/inspection/export', headers=H)
    check('导出状态码', r.status_code, 200)
    raw = r.get_data()
    check('导出非空', len(raw) > 2000, True)
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw))
    ws = wb.active
    check('标题行', ws.cell(1, 1).value, '领导巡查发现问题及各部门处置情况汇总台账')
    check('表头10列', [ws.cell(2, i).value for i in range(1, 11)],
          ['序号', '日期', '道路', '具体位置', '问题', '责任单位', '处理结果', '整改状态', '问题图片', '整改图片'])
    check('数据行数', ws.max_row - 2, 545)
    check('日期格式(第3行)', ws.cell(3, 2).value.count('月'), 1)
    r2 = client.get('/api/inspection/export?with_images=1&date_from=2026-10-22', headers=H)
    wb2 = openpyxl.load_workbook(io.BytesIO(r2.get_data()))
    check('带图版能生成', wb2.active.max_row >= 3, True)

    print('\n12. 单条回填整改 PUT /api/inspection/cases/{id}')
    with engine.connect() as conn:
        target = conn.execute(text(
            "SELECT id, location FROM insp_case WHERE location = 'INSPTEST-位置甲'")).fetchone()
    check('找到待回填案件', target is not None, True)
    if target:
        tid = target[0]
        # 12.1 正常回填：result 有实质内容 + status=已整改 -> 应变成已整改
        r = client.put(f'/api/inspection/cases/{tid}', headers=H,
                       json={'result': '已更换完毕', 'status': '已整改'})
        b12 = r.get_json()
        print('   ', json.dumps(b12, ensure_ascii=False))
        check('回填状态码', r.status_code, 200)
        check('回填后 status', b12.get('status'), '已整改')
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT status, result, rectified_at, location FROM insp_case WHERE id = :i"),
                {'i': tid}).fetchone()
        check('库里 status', row[0], '已整改')
        check('库里 result', row[1], '已更换完毕')
        check('rectified_at 已填', row[2] is not None, True)
        check('位置未被改', row[3], 'INSPTEST-位置甲')

        # 12.2 拒绝口径：即使传已整改，result 命中"不属于"也要按待整改
        r = client.put(f'/api/inspection/cases/{tid}', headers=H,
                       json={'result': '不属于我中心管理范围', 'status': '已整改'})
        b12b = r.get_json()
        check('拒接口径下 status', b12b.get('status'), '待整改')
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT status, rectified_at FROM insp_case WHERE id = :i"), {'i': tid}).fetchone()
        check('库里 status 被推翻', row[0], '待整改')
        check('rectified_at 被清空', row[1], None)

        # 12.3 只传 result 不传 status：status 应保持待整改
        r = client.put(f'/api/inspection/cases/{tid}', headers=H, json={'result': '已清理'})
        b12c = r.get_json()
        check('只改 result 时 status', b12c.get('status'), '待整改')

        # 12.4 空 body 应 400；不存在的 id 应 404
        r = client.put(f'/api/inspection/cases/{tid}', headers=H, json={})
        check('空 body 返回400', r.status_code, 400)
        r = client.put('/api/inspection/cases/99999999', headers=H, json={'result': 'x'})
        check('不存在 id 返回404', r.status_code, 404)

        # 12.5 无权限用户应 403
        r = client.put(f'/api/inspection/cases/{tid}', headers=H_USER, json={'result': 'x'})
        check('无权限返回403', r.status_code, 403)

    cleanup()
    print('\n' + '=' * 72)
    if FAILS:
        print(f'接口实测失败 {len(FAILS)} 项：')
        for f in FAILS:
            print('  -', f)
        sys.exit(1)
    print('接口实测全部通过')
    sys.exit(0)


if __name__ == '__main__':
    main()
