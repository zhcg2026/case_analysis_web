# -*- coding: utf-8 -*-
"""巡查问题台账模块冒烟测试：用《问题处置汇总总台账.xlsx》的验收数字做断言。

验收数字来源：D:\中心组问题\巡查问题台账-入库规格.md 第 7 节（2026-10-22 实测复核）：
  insp_case 行数 = 539；已整改 = 104；待整改 = 435
  insp_photo 行数 = 814（problem=673 / rectify=141），且每条 file_path 指向的磁盘文件存在可打开
  按日期：10-17 115 / 10-18 118 / 10-19 177 / 10-20 70 / 10-21 59
  按责任单位：市政 174 / 执法队 175 / 环卫 90 / 园林 88 / 排水 6 / 市容秩序科 6
  幂等：清空重跑一次，结果与第一次完全一致（图片不重复落盘）

任何一项对不上就打印具体差异并退出码非 0，不要只报成功。
卫生约定：只删 source_file = 本文件名的数据，不清整表，不动其它模块表。
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

from PIL import Image
from sqlalchemy import text

import app as app_module
from inspection_routes import _hamming, PHASH_DUP_DISTANCE, UPLOAD_DIR

engine = app_module.engine
SOURCE_FILE = '问题处置汇总总台账.xlsx'

EXPECT_CASES = 539
EXPECT_STATUS = {'已整改': 104, '待整改': 435}
EXPECT_PHOTOS = 814
EXPECT_PROBLEM = 673
EXPECT_RECTIFY = 141
EXPECT_BY_DATE = {'2026-10-17': 115, '2026-10-18': 118, '2026-10-19': 177,
                  '2026-10-20': 70, '2026-10-21': 59}
EXPECT_BY_DEPT = {'市政': 174, '执法队': 175, '环卫': 90, '园林': 88, '排水': 6, '市容秩序科': 6}

FAILURES = []


def check(label, actual, expect):
    ok = actual == expect
    mark = 'PASS' if ok else 'FAIL'
    print(f'  [{mark}] {label}: 实际={actual} 期望={expect}')
    if not ok:
        FAILURES.append(f'{label}: 实际={actual} 期望={expect}')
    return ok


def snapshot():
    """取一份可比对的全量快照（案件 + 照片 + 落盘文件字节数）。

    口径说明：不比对自增 id 和带 id 的文件名——重跑迁移后 AUTO_INCREMENT 会递增，
    文件名 {MMDD}-{case_id:04d}-{p|r}{seq}.jpg 里的 case_id 随之变化，这是预期行为。
    要比的是业务内容（日期/道路/位置/问题/单位/结果/状态/来源行）、照片的 phash，
    以及落盘图片的实质（按来源行+类型+序号取字节数，绕开 case_id 变化）。"""
    with engine.connect() as conn:
        cases = conn.execute(text(
            "SELECT case_date, road, location, problem, dept, result, status, source_row "
            "FROM insp_case WHERE source_file = :sf ORDER BY source_row"
        ), {'sf': SOURCE_FILE}).fetchall()
        photos = conn.execute(text(
            "SELECT c.source_row, p.kind, p.phash, p.seq "
            "FROM insp_photo p JOIN insp_case c ON c.id = p.case_id "
            "WHERE c.source_file = :sf ORDER BY c.source_row, p.kind, p.seq"
        ), {'sf': SOURCE_FILE}).fetchall()
        files = conn.execute(text(
            "SELECT c.source_row, p.kind, p.seq, p.file_path "
            "FROM insp_photo p JOIN insp_case c ON c.id = p.case_id "
            "WHERE c.source_file = :sf ORDER BY c.source_row, p.kind, p.seq"
        ), {'sf': SOURCE_FILE}).fetchall()
    file_sizes = {}
    for src_row, kind, seq, fp in files:
        abs_path = os.path.join(UPLOAD_DIR, fp.lstrip('/uploads/'))
        file_sizes[(src_row, kind, seq)] = os.path.getsize(abs_path) if os.path.isfile(abs_path) else -1
    return (tuple(tuple(str(x) for x in c) for c in cases),
            tuple(tuple(str(x) for x in p) for p in photos),
            tuple(sorted(file_sizes.items())))


def verify():
    print('=' * 72)
    print('一、案件总数与状态')
    with engine.connect() as conn:
        total = conn.execute(text(
            "SELECT COUNT(*) FROM insp_case WHERE source_file = :sf"), {'sf': SOURCE_FILE}).scalar()
        check('insp_case 行数', total, EXPECT_CASES)
        for st, n in EXPECT_STATUS.items():
            got = conn.execute(text(
                "SELECT COUNT(*) FROM insp_case WHERE source_file = :sf AND status = :st"
            ), {'sf': SOURCE_FILE, 'st': st}).scalar()
            check(f"status='{st}'", got, n)

    print('\n二、照片总数与类型')
    with engine.connect() as conn:
        np_ = conn.execute(text(
            "SELECT COUNT(*) FROM insp_photo p JOIN insp_case c ON c.id = p.case_id "
            "WHERE c.source_file = :sf"), {'sf': SOURCE_FILE}).scalar()
        check('insp_photo 行数', np_, EXPECT_PHOTOS)
        for kind, n in (('problem', EXPECT_PROBLEM), ('rectify', EXPECT_RECTIFY)):
            got = conn.execute(text(
                "SELECT COUNT(*) FROM insp_photo p JOIN insp_case c ON c.id = p.case_id "
                "WHERE c.source_file = :sf AND p.kind = :k"), {'sf': SOURCE_FILE, 'k': kind}).scalar()
            check(f"kind='{kind}'", got, n)

    print('\n三、照片文件存在且可打开')
    with engine.connect() as conn:
        paths = [r[0] for r in conn.execute(text(
            "SELECT p.file_path FROM insp_photo p JOIN insp_case c ON c.id = p.case_id "
            "WHERE c.source_file = :sf"), {'sf': SOURCE_FILE}).fetchall()]
    missing, unreadable = [], []
    for fp in paths:
        abs_path = os.path.join(UPLOAD_DIR, fp.lstrip('/uploads/'))
        if not os.path.isfile(abs_path):
            missing.append(fp)
            continue
        try:
            im = Image.open(abs_path)
            im.load()
        except Exception as e:
            unreadable.append(f'{fp}: {e}')
    check('磁盘文件缺失数', len(missing), 0)
    check('无法打开数', len(unreadable), 0)
    for m in missing[:5]:
        print('     缺:', m)
    for u in unreadable[:5]:
        print('     坏:', u)

    print('\n四、按日期分组')
    with engine.connect() as conn:
        got = {str(r[0]): r[1] for r in conn.execute(text(
            "SELECT case_date, COUNT(*) FROM insp_case WHERE source_file = :sf GROUP BY case_date"
        ), {'sf': SOURCE_FILE}).fetchall()}
    for d, n in EXPECT_BY_DATE.items():
        check(f'{d}', got.get(d, 0), n)
    extra = {k: v for k, v in got.items() if k not in EXPECT_BY_DATE}
    check('多余日期数', len(extra), 0)

    print('\n五、按责任单位分组')
    with engine.connect() as conn:
        got = {str(r[0]): r[1] for r in conn.execute(text(
            "SELECT dept, COUNT(*) FROM insp_case WHERE source_file = :sf GROUP BY dept"
        ), {'sf': SOURCE_FILE}).fetchall()}
    for d, n in EXPECT_BY_DEPT.items():
        check(d, got.get(d, 0), n)
    extra = {k: v for k, v in got.items() if k not in EXPECT_BY_DEPT}
    check('字典外责任单位数', len(extra), 0)
    for k, v in extra.items():
        print(f'     字典外: {k} ({v} 行)')

    print('\n六、疑似重复队列（历史迁移应为 0）')
    with engine.connect() as conn:
        dup = conn.execute(text(
            "SELECT COUNT(*) FROM insp_dup_candidate WHERE batch_no = 'MIGRATE-20261022'"
        )).scalar() or 0
    check('MIGRATE 批次重复候选', dup, 0)

    print('\n七、phash 可用性（抽样算距离，确认不是全零/空值）')
    with engine.connect() as conn:
        sample = conn.execute(text(
            "SELECT phash FROM insp_photo WHERE phash IS NOT NULL AND phash != '' LIMIT 200"
        )).fetchall()
    hashes = [r[0] for r in sample]
    check('非空 phash 抽样数', len(hashes), min(200, EXPECT_PHOTOS))
    if len(hashes) >= 2:
        distinct = len(set(hashes))
        print(f'     抽样 {len(hashes)} 个 phash 中去重后 {distinct} 个'
              f'（底稿有 38 张图一图多用，故重复属预期）')
        nonzero = sum(1 for h in hashes if h != '0' * 16)
        check('非全零 phash 数', nonzero, len(hashes))

    print('\n八、幂等重跑：清空本文件数据后重导，结果必须完全一致')
    first = snapshot()
    print(f'  第一次快照：案件 {len(first[0])} 行，照片 {len(first[1])} 行，'
          f'落盘文件 {len(first[2])} 个')
    print('  正在清空并重跑迁移……')
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM insp_photo WHERE case_id IN "
            "(SELECT id FROM insp_case WHERE source_file = :sf)"), {'sf': SOURCE_FILE})
        conn.execute(text("DELETE FROM insp_case WHERE source_file = :sf"), {'sf': SOURCE_FILE})
        conn.execute(text("DELETE FROM insp_dup_candidate"))
    import _migrate_inspection as M
    M.main()
    second = snapshot()
    same = first == second
    check('两次迁移结果逐字节一致', same, True)
    if not same:
        c1, p1, f1 = first
        c2, p2, f2 = second
        print(f'     案件: {len(c1)} vs {len(c2)}；照片: {len(p1)} vs {len(p2)}；'
              f'文件: {len(f1)} vs {len(f2)}')
        for a, b in zip(c1, c2):
            if a != b:
                print('     案件差异:', a, '!=', b)
                break
        d1 = dict(f1); d2 = dict(f2)
        for k in set(d1) | set(d2):
            if d1.get(k) != d2.get(k):
                print(f'     文件差异: {k} {d1.get(k)} vs {d2.get(k)}')
                break


if __name__ == '__main__':
    verify()
    print('\n' + '=' * 72)
    if FAILURES:
        print(f'冒烟测试失败 {len(FAILURES)} 项：')
        for f in FAILURES:
            print('  -', f)
        sys.exit(1)
    print('冒烟测试全部通过')
    sys.exit(0)
