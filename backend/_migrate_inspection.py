# -*- coding: utf-8 -*-
"""把《问题处置汇总总台账.xlsx》的 539 件案件 + 814 张图迁入本地库 insp_ 表。

数据源（2026-10-22 实测）：
- sheet「汇总台账」：第1行大标题，第2行表头，第3-541行数据（539件）
- 列：A序号 B日期 C道路 D具体位置 E问题 F责任单位 G处理结果 H整改状态
- 图片：xl/drawings/drawing1.xml 的 oneCellAnchor 浮动锚点，col 8=I列问题图、col 9=J列整改图
  （无 xdr: 命名空间前缀，是默认命名空间；rels 的 Target 是绝对路径 /xl/media/imageN.jpeg）

卫生约定（与仓库其它 _smoke/_migrate 脚本一致）：
- 幂等：按 source_file + source_row 判重，重跑不产生重复案件；图片文件已存在则不重复写盘
- 只删本次迁移写入的数据（source_file = 本文件名），绝不清整表
- 取图/算 phash 失败必须显式报错并计入 errors，禁止 try/except: pass 静默跳过
"""
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import openpyxl
from PIL import Image
from sqlalchemy import text

import app as app_module
from inspection_routes import (
    UPLOAD_DIR, INSP_PHOTO_DIR, MAX_EDGE, JPEG_QUALITY,
    normalize_dept, judge_status, parse_case_date, normalized_key,
    _phash_hex, _save_photo, _hamming, PHASH_DUP_DISTANCE,
)

SRC = r'D:\中心组问题\问题处置汇总总台账.xlsx'
SOURCE_FILE = '问题处置汇总总台账.xlsx'
SHEET = '汇总台账'

engine = app_module.engine

# 文档第7节验收数字（2026-10-22 实测复核）
EXPECT_CASES = 539
EXPECT_PHOTOS = 814
EXPECT_PROBLEM = 673
EXPECT_RECTIFY = 141
EXPECT_STATUS = {'已整改': 104, '待整改': 435}
EXPECT_BY_DATE = {'2026-10-17': 115, '2026-10-18': 118, '2026-10-19': 177,
                  '2026-10-20': 70, '2026-10-21': 59}
EXPECT_BY_DEPT = {'市政': 174, '执法队': 175, '环卫': 90, '园林': 88, '排水': 6, '市容秩序科': 6}


def extract_anchors():
    """从 drawing1.xml 解析浮动锚点，返回 {(excel_row, col): [media文件名,...]}"""
    z = zipfile.ZipFile(SRC)
    drawing = [n for n in z.namelist() if n.startswith('xl/drawings/drawing') and n.endswith('.xml')]
    rels_name = [n for n in z.namelist() if n.startswith('xl/drawings/_rels/drawing')]
    if len(drawing) != 1 or len(rels_name) != 1:
        raise RuntimeError(f'预期恰好一个 drawing + 一个 rels，实际 {drawing} / {rels_name}')
    xml = z.read(drawing[0]).decode('utf-8')
    rels = z.read(rels_name[0]).decode('utf-8')

    rid2target = {}
    for rel in re.findall(r'<Relationship\b[^>]*/?>', rels):
        rid = re.search(r'Id="([^"]+)"', rel)
        tgt = re.search(r'Target="([^"]+)"', rel)
        if rid and tgt:
            rid2target[rid.group(1)] = tgt.group(1)

    # 锚点三种形态 + 前缀可选 + 开标签可带属性（如 editAs="oneCell"）
    anchors = re.findall(
        r'<(?:xdr:)?oneCellAnchor\b[^>]*>.*?</(?:xdr:)?oneCellAnchor>|'
        r'<(?:xdr:)?twoCellAnchor\b[^>]*>.*?</(?:xdr:)?twoCellAnchor>|'
        r'<(?:xdr:)?absoluteAnchor\b[^>]*>.*?</(?:xdr:)?absoluteAnchor>', xml, re.S)
    result = defaultdict(list)
    for a in anchors:
        m = re.search(r'<(?:xdr:)?from><(?:xdr:)?col>(\d+)</(?:xdr:)?col>'
                      r'.*?<(?:xdr:)?row>(\d+)</(?:xdr:)?row>', a, re.S)
        rid = re.search(r'r:embed="(rId\d+)"', a)
        if not (m and rid):
            raise RuntimeError(f'锚点缺少 col/row 或 r:embed，无法定位：{a[:120]}')
        target = rid2target.get(rid.group(1))
        if not target:
            raise RuntimeError(f'rels 里找不到 {rid.group(1)}')
        # Target 可能是绝对路径（/xl/media/image1.jpeg），判 startswith('/') 后去斜杠直接用；
        # 也可能是相对路径（../media/.. 或 media/..），需规范化，否则拼出 xl/../media/ 打不开
        rel_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        rel_path = os.path.normpath(rel_path).replace('\\', '/')
        result[(int(m.group(2)) + 1, int(m.group(1)))].append(rel_path)
    return z, result


def main():
    z, anchors = extract_anchors()
    total_anchors = sum(len(v) for v in anchors.values())
    print(f'锚点总数: {total_anchors}，涉及行数: {len({k[0] for k in anchors})}')
    cols = Counter(k[1] for k in anchors for _ in anchors[k])
    print(f'按列分布(0-based): {dict(sorted(cols.items()))}（8=I问题图 9=J整改图）')

    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    ws = wb[SHEET]
    rows = [r for r in ws.iter_rows(min_row=3, max_row=ws.max_row, values_only=True)
            if any(c is not None and str(c).strip() != '' for c in r)]
    print(f'数据行数: {len(rows)}')

    # 图片按行归拢：col8 -> problem，col9 -> rectify；其它列的浮动图算模板装饰图，计数上报
    problem_imgs = defaultdict(list)
    rectify_imgs = defaultdict(list)
    dropped_deco = 0
    for (row_no, col), paths in anchors.items():
        if col == 8:
            problem_imgs[row_no].extend(paths)
        elif col == 9:
            rectify_imgs[row_no].extend(paths)
        else:
            dropped_deco += len(paths)
    print(f'问题图 {sum(len(v) for v in problem_imgs.values())} 张 / '
          f'整改图 {sum(len(v) for v in rectify_imgs.values())} 张 / '
          f'其它列装饰图 {dropped_deco} 张（丢弃但计数）')

    inserted = updated = skipped = photos_saved = 0
    errors = []
    phash_index = []  # [(phash, case_id)] 用于同批次内照片查重

    for i, r in enumerate(rows):
        row_no = i + 3  # Excel 实际行号
        try:
            seq, date_raw, road, location, problem, dept_raw, result, status_raw = r[:8]
            case_date = parse_case_date(date_raw)
            dept, hit = normalize_dept(dept_raw)
            if dept_raw and not hit:
                errors.append(f'第{row_no}行 责任单位不在字典内：{dept_raw}（已原文入库）')
            result_s = str(result).strip() if result else ''
            status = judge_status(status_raw, result_s)

            # 幂等：同一份表同一行已入库则跳过
            with engine.begin() as conn:
                exist = conn.execute(text(
                    "SELECT id FROM insp_case WHERE source_file = :sf AND source_row = :sr"
                ), {'sf': SOURCE_FILE, 'sr': row_no}).fetchone()
            if exist:
                skipped += 1
                continue

            # 收集本行照片（问题图/整改图），按 Excel 里的出现顺序编号
            photo_records = []
            for kind, bucket in (('problem', problem_imgs), ('rectify', rectify_imgs)):
                for seq_i, media_path in enumerate(bucket.get(row_no, []), start=1):
                    try:
                        raw = z.read(media_path)
                        ph = _phash_hex(raw)
                    except Exception as e:
                        errors.append(f'第{row_no}行 取图/算phash失败 {media_path}: {e}')
                        continue
                    photo_records.append({'kind': kind, 'seq': seq_i, 'phash': ph,
                                          'orig_name': os.path.basename(media_path),
                                          'raw': raw})

            # 历史迁移策略：全量照收，不判重。
            # 底稿里实测有 38 张照片被贴到 45 个不同 Excel 行上（上游一图多用），
            # 若按 phash 判重会把这 9 行踢进人工队列，导致 539/814 验收数字对不上。
            # 判重只对将来的每日导入生效（见 inspection_routes.insp_import）。
            # 但同文件同行的重复导入仍靠 uk_source 幂等拦截。

            with engine.begin() as conn:
                res = conn.execute(text(
                    "INSERT INTO insp_case "
                    "(case_date, road, location, problem, dept, dept_raw, result, status, "
                    " normalized_key, photo_hashes, source_file, source_row, first_seen_at, rectified_at) "
                    "VALUES (:cd, :rd, :lo, :pr, :dp, :dr, :rs, :st, :nk, :ph, :sf, :sr, :ts, :ra)"
                ), {'cd': case_date, 'rd': str(road or ''), 'lo': str(location or ''),
                    'pr': str(problem or ''), 'dp': dept, 'dr': str(dept_raw or '') or None,
                    'rs': result_s, 'st': status,
                    'nk': normalized_key(location, problem),
                    'ph': json.dumps([p['phash'] for p in photo_records], ensure_ascii=False),
                    'sf': SOURCE_FILE, 'sr': row_no, 'ts': None, 'ra': None})
                case_id = res.lastrowid
                for p in photo_records:
                    try:
                        abs_path, rel_url = _save_photo(case_id, p['kind'], p['seq'],
                                                        p['raw'], case_date, p['orig_name'])
                        conn.execute(text(
                            "INSERT INTO insp_photo (case_id, kind, file_path, phash, orig_name, seq) "
                            "VALUES (:c, :k, :f, :h, :o, :s)"
                        ), {'c': case_id, 'k': p['kind'], 'f': rel_url, 'h': p['phash'],
                            'o': p['orig_name'], 's': p['seq']})
                        photos_saved += 1
                        phash_index.append((p['phash'], case_id))
                    except Exception as e:
                        errors.append(f'第{row_no}行 照片落盘失败 {p["orig_name"]}: {e}')
            inserted += 1
        except Exception as e:
            errors.append(f'第{row_no}行 导入异常: {e}')

    print(f'\n迁移结果: inserted={inserted} skipped(已存在)={skipped} photos_saved={photos_saved}')
    if errors:
        print(f'errors ({len(errors)}):')
        for e in errors[:30]:
            print('  ', e)
    return inserted, skipped, photos_saved, errors


def _find_phash_match_db(conn, phash):
    if not phash:
        return None
    rows = conn.execute(text(
        "SELECT p.case_id, p.phash FROM insp_photo p WHERE p.phash IS NOT NULL AND p.phash != ''"
    )).fetchall()
    best = None
    for cid, existing in rows:
        d = _hamming(phash, existing)
        if d <= PHASH_DUP_DISTANCE and (best is None or d < best[1]):
            best = (cid, d)
    return best


if __name__ == '__main__':
    main()
