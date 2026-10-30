# -*- coding: utf-8 -*-
"""整改清单回填：把「已整改问题汇总台账」按位置+问题匹配回已有案件，匹配不上的作新案入库。

与普通导入的区别（需求方 2026-10-22 确认）：
- 整改清单的日期横跨历史多日，绝大多数是已入库旧案的整改回填，不是新案件
- 若直接走 /api/inspection/import，问题图与库内相同的行会全部进「疑似重复」队列
  （实测 144 行里 107 行会中），且点「是全新案件」反而制造重复案件
- 故本脚本用「归一化位置 + 归一化问题」精确匹配库内案件：
    * 命中唯一一条  -> 回填：只更新 result/status/rectified_at，追加整改图，不改位置/问题/日期/单位
    * 命中多条      -> 不回填，落 ambiguous.json 由人工指定（不猜）
    * 一条都没命中  -> 作新案入库（这些旧案从没进过库）
- 幂等：已回填过的行（status 已改 + 整改图已挂）重跑不重复加图
- 只动 insp_ 两张新表，绝不碰 case_data / cyw_* 等现有表

用法：
  python _apply_rectify.py <import_payload.json> [--dry-run]
      --dry-run 只打印将要做什么，不写库
"""
import argparse
import io
import json
import os
import shutil
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

from PIL import Image
from sqlalchemy import text

import app as app_module
from inspection_routes import (
    INSP_PHOTO_DIR, MAX_EDGE, JPEG_QUALITY, _photo_subdir,
    normalize_text, judge_status, _phash_hex, _hamming, PHASH_DUP_DISTANCE,
)

engine = app_module.engine
SRC_KEY = 'RECTIFY-BATCH'


def load_payload(path):
    payload = json.load(open(path, encoding='utf-8'))
    photo_dir = os.path.join(os.path.dirname(os.path.abspath(path)), 'photos')
    return payload, photo_dir


def build_index():
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT id, case_date, location, problem, status, dept, result "
            "FROM insp_case")).fetchall()
    idx = {}
    for r in rows:
        idx.setdefault((normalize_text(r[2]), normalize_text(r[3])), []).append(r)
    return idx


def existing_rectify_hashes(case_id):
    with engine.connect() as c:
        return {r[0] for r in c.execute(text(
            "SELECT phash FROM insp_photo WHERE case_id = :i AND kind = 'rectify' "
            "AND phash IS NOT NULL"), {'i': case_id}).fetchall()}


def save_rectify_photo(case_id, case_date, seq, raw):
    """整改图落盘，命名规则与导入一致：{MMDD}-{case_id}-r{seq}.jpg"""
    subdir = _photo_subdir(str(case_date))
    os.makedirs(subdir, exist_ok=True)
    prefix = str(case_date)[5:].replace('-', '')
    save_name = f'{prefix}-{case_id:04d}-r{seq}.jpg'
    abs_path = os.path.join(subdir, save_name)
    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.mode not in ('RGB', 'L'):
        im = im.convert('RGB')
    w, h = im.size
    if max(w, h) > MAX_EDGE:
        ratio = MAX_EDGE / max(w, h)
        im = im.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
    im.save(abs_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)
    rel = f'/uploads/inspection/{str(case_date).replace("-", "")}/{save_name}'
    return rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('payload')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    payload, photo_dir = load_payload(args.payload)
    src = payload['source_file']
    idx = build_index()
    print(f'来源文件: {src}')
    print(f'待处理: {len(payload["cases"])} 件；库内案件 {sum(len(v) for v in idx.values())} 件')

    filled = skipped_dup = new_inserted = 0
    ambiguous, errors = [], []
    new_cases = []

    for c in payload['cases']:
        key = (normalize_text(c['location']), normalize_text(c['problem']))
        hits = idx.get(key, [])
        result = (c.get('result') or '').strip()
        status = judge_status(c.get('status'), result)
        rects = [p for p in c.get('photos', []) if p['kind'] == 'rectify']

        if len(hits) == 1:
            target = hits[0][0]
            if args.dry_run:
                print(f'  [回填] 行{c["source_row"]} -> 案件#{target} '
                      f'({hits[0][1]} {hits[0][4]}->{status}, 整改图{len(rects)}张)')
                filled += 1
                continue
            # 幂等：已挂过的整改图（phash 相同）不重复加
            have = existing_rectify_hashes(target)
            to_add = []
            for p in rects:
                ph = (p.get('phash') or '').lower()
                if ph and any(_hamming(ph, h) <= PHASH_DUP_DISTANCE for h in have):
                    skipped_dup += 1
                    continue
                to_add.append(p)
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        "UPDATE insp_case SET result = COALESCE(NULLIF(:rs, ''), result), "
                        "status = :st, rectified_at = COALESCE(rectified_at, :ra) "
                        "WHERE id = :i"
                    ), {'rs': result, 'st': status,
                        'ra': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        if status == '已整改' else None, 'i': target})
                    base = conn.execute(text(
                        "SELECT COALESCE(MAX(seq), 0) FROM insp_photo "
                        "WHERE case_id = :i AND kind = 'rectify'"), {'i': target}).scalar()
                    for p in to_add:
                        raw_path = os.path.join(photo_dir, os.path.basename(p['file_token']))
                        if not os.path.isfile(raw_path):
                            errors.append(f'行{c["source_row"]} 整改图缺失: {p["file_token"]}')
                            continue
                        with open(raw_path, 'rb') as fh:
                            raw = fh.read()
                        ph = p.get('phash') or _phash_hex(raw)
                        base += 1
                        rel = save_rectify_photo(target, str(hits[0][1]), base, raw)
                        conn.execute(text(
                            "INSERT INTO insp_photo (case_id, kind, file_path, phash, orig_name, seq) "
                            "VALUES (:c, 'rectify', :f, :h, :o, :s)"
                        ), {'c': target, 'f': rel, 'h': ph,
                            'o': os.path.basename(p['file_token']), 's': base})
                filled += 1
            except Exception as e:
                errors.append(f'行{c["source_row"]} 回填异常: {e}')

        elif len(hits) > 1:
            ambiguous.append({
                'source_row': c['source_row'], 'location': c['location'],
                'problem': c['problem'], 'status': status,
                'candidates': [{'id': h[0], 'case_date': str(h[1]), 'dept': h[5],
                                'status': h[4]} for h in hits],
            })
        else:
            new_cases.append(c)

    # 匹配不到的作新案入库
    if new_cases:
        print(f'\n匹配不到、将作新案入库: {len(new_cases)} 件')
        by_date = Counter(c['case_date'] for c in new_cases)
        print('  按日期:', dict(sorted(by_date.items())))
        if not args.dry_run:
            for c in new_cases:
                try:
                    with engine.begin() as conn:
                        r = conn.execute(text(
                            "INSERT INTO insp_case "
                            "(case_date, road, location, problem, dept, dept_raw, result, status, "
                            " normalized_key, photo_hashes, source_file, source_row, first_seen_at, rectified_at) "
                            "VALUES (:cd, :rd, :lo, :pr, :dp, :dr, :rs, :st, :nk, :ph, :sf, :sr, :ts, :ra)"
                        ), {'cd': c['case_date'], 'rd': c.get('road') or '',
                            'lo': c['location'], 'pr': c['problem'],
                            'dp': c.get('dept'), 'dr': c.get('dept_raw'),
                            'rs': (c.get('result') or '').strip(),
                            'st': judge_status(c.get('status'), c.get('result')),
                            'nk': '', 'ph': json.dumps(
                                [p.get('phash') for p in c.get('photos', []) if p.get('phash')]),
                            'sf': src, 'sr': c['source_row'],
                            'ts': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'ra': None})
                        cid = r.lastrowid
                        seqs = Counter()
                        for p in c.get('photos', []):
                            raw_path = os.path.join(photo_dir, os.path.basename(p['file_token']))
                            if not os.path.isfile(raw_path):
                                errors.append(f'行{c["source_row"]} 图缺失: {p["file_token"]}')
                                continue
                            with open(raw_path, 'rb') as fh:
                                raw = fh.read()
                            kind = p.get('kind') or 'problem'
                            seqs[kind] += 1
                            ph = p.get('phash') or _phash_hex(raw)
                            if kind == 'rectify':
                                rel = save_rectify_photo(cid, c['case_date'], seqs[kind], raw)
                            else:
                                subdir = _photo_subdir(c['case_date'])
                                os.makedirs(subdir, exist_ok=True)
                                prefix = str(c['case_date'])[5:].replace('-', '')
                                save_name = f'{prefix}-{cid:04d}-p{seqs[kind]}.jpg'
                                im = Image.open(io.BytesIO(raw)); im.load()
                                if im.mode not in ('RGB', 'L'):
                                    im = im.convert('RGB')
                                w, h = im.size
                                if max(w, h) > MAX_EDGE:
                                    ratio = MAX_EDGE / max(w, h)
                                    im = im.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
                                im.save(os.path.join(subdir, save_name), 'JPEG',
                                        quality=JPEG_QUALITY, optimize=True)
                                rel = f'/uploads/inspection/{str(c["case_date"]).replace("-", "")}/{save_name}'
                            conn.execute(text(
                                "INSERT INTO insp_photo (case_id, kind, file_path, phash, orig_name, seq) "
                                "VALUES (:c, :k, :f, :h, :o, :s)"
                            ), {'c': cid, 'k': kind, 'f': rel, 'h': ph,
                                'o': os.path.basename(p['file_token']), 's': seqs[kind]})
                    new_inserted += 1
                except Exception as e:
                    errors.append(f'行{c["source_row"]} 新案入库异常: {e}')
        else:
            new_inserted = len(new_cases)

    out_dir = os.path.dirname(os.path.abspath(args.payload))
    if ambiguous:
        ap_path = os.path.join(out_dir, 'ambiguous.json')
        json.dump(ambiguous, open(ap_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'\n命中多条、需人工指定: {len(ambiguous)} 件 -> {ap_path}')
        for a in ambiguous[:5]:
            print(f'  行{a["source_row"]} {a["location"][:24]} | 候选: '
                  + ', '.join(f'#{x["id"]}({x["case_date"]},{x["dept"]},{x["status"]})' for x in a['candidates']))

    print('\n' + '=' * 60)
    print(f'回填旧案: {filled} 件')
    print(f'跳过重复整改图: {skipped_dup} 张')
    print(f'新案入库: {new_inserted} 件')
    print(f'需人工指定: {len(ambiguous)} 件')
    print(f'错误: {len(errors)} 条')
    for e in errors[:10]:
        print('  -', e)
    if args.dry_run:
        print('\n（dry-run，未写库）')
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
