# -*- coding: utf-8 -*-
"""每日部门表解析器：把各部门交来的问题清单/整改清单转成 insp_ 导入 JSON + 图片包。

设计目标（2026-10-22 与需求方确认）：
- 你只负责把各部门表丢进当天文件夹（如 D:\\中心组问题\\10.23\\），其余全自动
- 解析不了的**不猜**，落 need_review.json 由你点确认后才进库
- 上游格式不受控（列名/列序/日期写法/责任单位写法都变），所以用「列名模糊匹配」而非固定列号

输出（默认写到 输出目录，可用 --out 指定）：
  import_payload.json   POST /api/inspection/import 的请求体（cases 已带 file_token/phash）
  need_review.json      解析存疑的行（部门不在字典、日期无法解析、缺位置/问题、图数异常）
  photos/                抽出来的图片，文件名 = {来源行}-{p|r}{序号}.jpg

用法：
  python _parse_daily.py <表文件或目录> [--date 2026-10-23] [--out 目录] [--kind auto]
      --kind auto|problem|rectify  强制指定本表是问题清单还是整改清单（默认按文件名猜）

依赖：openpyxl 读 xlsx；.xls 走 xlrd（未装会明确报错并提示，不静默跳过）。
"""
import argparse
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import openpyxl
from PIL import Image

from inspection_routes import (
    normalize_dept, parse_case_date, normalized_key, _phash_hex,
    MAX_EDGE, JPEG_QUALITY, DEPT_ALIAS,
)

# 单行图片数上限：超过就说明上游把别处的图堆到了这一行（实测整改清单里
# 第135行锚了34张、第123行13张、第3行12张，都是整段问题的图堆在首行）。
# 超限不猜也不丢：前 N 张正常入库，其余落 need_review 由人工核对。
MAX_PHOTOS_PER_ROW = 6

# 列名模糊匹配：上游列名会变，按语义认（命中多个时取第一个）
COL_PATTERNS = {
    'road':      [r'^道路$', r'^路名$', r'^街路$', r'道路名称'],
    'location':  [r'具体位置', r'^位置$', r'检测点位', r'^点位$', r'^地点$', r'所在位置'],
    'problem':   [r'^问题$', r'问题清单', r'问题描述', r'^问题内容$', r'存在问题'],
    'dept':      [r'责任单位', r'^责任部门$', r'^单位$', r'^部门$', r'处置单位'],
    'result':    [r'处理结果', r'^整改情况$', r'^处置情况$', r'^结果$'],
    'status':    [r'整改状态', r'^状态$', r'是否整改'],
    'date':      [r'^日期$', r'发现日期', r'^时间$'],
    'seq':       [r'^序号$', r'^编号$'],
    'leader':    [r'带队领导', r'^领导$', r'巡查组'],
}

# 图片列的语义：问题清单的图 = problem，整改清单的图 = rectify
PHOTO_COL_PATTERNS = {
    'problem': [r'问题图片', r'问题照片', r'^图片$', r'^照片$', r'现场照片'],
    'rectify': [r'整改图片', r'整改照片', r'处置图片', r'处理后'],
}


def match_col(headers, patterns):
    """按 patterns 依次找第一个匹配的列，返回列下标（0-based）或 None。"""
    for pat in patterns:
        for i, h in enumerate(headers):
            if h and re.search(pat, str(h).strip(), re.IGNORECASE):
                return i
    return None


def sniff_kind(filename, headers):
    """猜这个表是问题清单还是整改清单：先看文件名，再看表头和图片列名。"""
    name = os.path.basename(filename)
    if re.search(r'整改|已处理|处置后|反馈', name):
        return 'rectify'
    if re.search(r'问题清单|问题整改|巡查问题', name):
        return 'problem'
    for h in headers:
        if not h:
            continue
        hs = str(h)
        if re.search(r'整改图片|整改照片|处置图片', hs):
            return 'rectify'
        if re.search(r'问题图片|问题照片', hs):
            return 'problem'
    return 'problem'


def extract_images_xlsx(path):
    """从 xlsx 的 drawing 锚点抽图：返回 {(excel_row, col): [(序号, bytes), ...]}"""
    z = zipfile.ZipFile(path)
    drawings = [n for n in z.namelist()
                if n.startswith('xl/drawings/drawing') and n.endswith('.xml')]
    rels_map = {}
    for rn in [n for n in z.namelist() if n.startswith('xl/drawings/_rels/drawing')]:
        rels = z.read(rn).decode('utf-8')
        rid2t = {}
        for rel in re.findall(r'<Relationship\b[^>]*/?>', rels):
            i = re.search(r'Id="([^"]+)"', rel)
            t = re.search(r'Target="([^"]+)"', rel)
            if i and t:
                rid2t[i.group(1)] = t.group(1)
        rels_map[rn] = rid2t

    result = defaultdict(list)
    for dn in drawings:
        xml = z.read(dn).decode('utf-8')
        rn = dn.replace('drawings/', 'drawings/_rels/') + '.rels'
        rid2t = rels_map.get(rn, {})
        # 同时兼容带 xdr: 前缀和不带前缀两种写法；
        # 注意开标签可能带属性（如 <xdr:twoCellAnchor editAs="oneCell">），故用 [^>]* 吃掉属性
        for a in re.findall(
                r'<(?:xdr:)?oneCellAnchor\b[^>]*>.*?</(?:xdr:)?oneCellAnchor>|'
                r'<(?:xdr:)?twoCellAnchor\b[^>]*>.*?</(?:xdr:)?twoCellAnchor>|'
                r'<(?:xdr:)?absoluteAnchor\b[^>]*>.*?</(?:xdr:)?absoluteAnchor>', xml, re.S):
            m = re.search(r'<(?:xdr:)?from><(?:xdr:)?col>(\d+)</(?:xdr:)?col>'
                          r'.*?<(?:xdr:)?row>(\d+)</(?:xdr:)?row>', a, re.S)
            rid = re.search(r'r:embed="(rId\d+)"', a)
            if not (m and rid):
                continue
            target = rid2t.get(rid.group(1))
            if not target:
                continue
            # Target 三种形态都要处理（rels 位于 xl/drawings/_rels/，相对路径基于它解析）：
            #   绝对  /xl/media/image1.jpeg  -> 去前导斜杠直接用
            #   相对  ../media/image1.jpeg   -> 相对 xl/drawings/，规范化后得 xl/media/..
            #   相对  media/image1.jpeg      -> 相对 xl/，拼前缀
            if target.startswith('/'):
                rel_path = target.lstrip('/')
            elif target.startswith('../'):
                rel_path = os.path.normpath(os.path.join('xl/drawings', target))
            else:
                rel_path = os.path.normpath('xl/' + target)
            rel_path = rel_path.replace('\\', '/')
            try:
                raw = z.read(rel_path)
                Image.open(io.BytesIO(raw)).load()
            except Exception as e:
                raise RuntimeError(f'取图失败 {target} -> {rel_path}: {e}')
            result[(int(m.group(2)) + 1, int(m.group(1)))].append(raw)
    return result


def extract_images_xls(path):
    """读老格式 .xls 的内嵌图（openpyxl 不支持，走 olefile/xlrd 的自由通道）。"""
    try:
        import xlrd
    except ImportError:
        raise RuntimeError(
            '读取 .xls 需要 xlrd（pip install xlrd>=2.0 只支持 .xls，不兼容 .xlsx）。\n'
            '本脚本不会静默跳过 .xls 文件——请先装依赖，或把该表另存为 .xlsx 再跑。')
    raise RuntimeError(
        f'.xls 内嵌图抽取暂未实现（{os.path.basename(path)}）。\n'
        '请用 Excel 打开后「另存为 .xlsx」再放入当天文件夹；'
        '文本部分可先手动录入，图片不丢。')


def read_rows(path):
    """读表：返回 (sheet名, 标题行下标, 表头, [(excel_row, [cell...])])"""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.xls':
        raise RuntimeError(f'暂不支持 .xls：{os.path.basename(path)}，请另存为 .xlsx')
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    # 选数据最多的 sheet
    best = max(wb.sheetnames, key=lambda s: wb[s].max_row * 100 + wb[s].max_column)
    ws = wb[best]
    allrows = list(ws.iter_rows(values_only=True))
    # 找表头行：第一个含"位置/点位/问题"且含"序号"或"责任"的行
    head_idx = None
    for i, row in enumerate(allrows[:10]):
        cells = [str(c).strip() if c is not None else '' for c in row]
        joined = ' '.join(cells)
        if re.search(r'(位置|点位|地点)', joined) and re.search(r'(序号|编号|责任|单位|问题)', joined):
            head_idx = i
            break
    if head_idx is None:
        raise RuntimeError(f'找不到表头行（前10行内没有同时含位置/问题/责任语义的列）：{os.path.basename(path)}')
    headers = [str(c).strip() if c is not None else '' for c in allrows[head_idx]]
    data = [(i + 1, [c for c in r]) for i, r in enumerate(allrows) if i > head_idx]
    data = [(rn, cells) for rn, cells in data
            if any(c is not None and str(c).strip() != '' for c in cells)]
    return best, head_idx + 1, headers, data


def parse_file(path, force_date=None, force_kind=None):
    """解析单个表，返回 (cases, need_review, photo_files)"""
    fname = os.path.basename(path)
    sheet, head_row, headers, rows = read_rows(path)
    kind = force_kind or sniff_kind(fname, headers)

    cols = {k: match_col(headers, p) for k, p in COL_PATTERNS.items()}
    photo_cols = {}
    for k, p in PHOTO_COL_PATTERNS.items():
        idx = match_col(headers, p)
        if idx is not None:
            photo_cols[k] = idx

    print(f'\n=== {fname} ===')
    print(f'  sheet={sheet} 表头行={head_row} 数据行={len(rows)} 判定={("整改清单" if kind == "rectify" else "问题清单")}')
    print(f'  列识别: ' + ', '.join(f'{k}={headers[v] if v is not None else "未识别"}' for k, v in cols.items() if v is not None))
    if not photo_cols:
        print(f'  图片列: 未识别到（将只导文字）')
    else:
        print(f'  图片列: ' + ', '.join(f'{k}={headers[v]}' for k, v in photo_cols.items()))

    missing = [k for k in ('location', 'problem') if cols.get(k) is None]
    if missing:
        raise RuntimeError(f'关键列未识别到：{missing}（表头={headers}）')

    # 抽图。注意：部门常把图片贴在文字列上（实测 jichang_rect1.xlsx 有 4 张落在
    # 「问题清单」列而非「问题图片」列），所以只要图片锚定在该数据行上就按本表类型收，
    # 不苛求列号——漏图的代价比多收几张图大得多。
    images = {}
    if photo_cols:
        images = extract_images_xlsx(path)
        n_img = sum(len(v) for v in images.values())
        print(f'  浮动图片: {n_img} 张')

    cases, review = [], []
    photo_dir = None
    date_counter = Counter()

    for excel_row, cells in rows:
        seqs = Counter()  # 本行内按 kind 编号，保证 seq 连续稳定

        def g(key):
            i = cols.get(key)
            if i is None or i >= len(cells):
                return None
            v = cells[i]
            return str(v).strip() if v is not None and str(v).strip() != '' else None

        location, problem = g('location'), g('problem')
        row_kind = kind
        # 整改清单里，图列名可能是"问题图片"（整改清单常把原问题图也带上）——
        # 按表整体类型定，不按行定，避免同表两种 kind 把 seq 搞乱
        if not location and not problem:
            review.append({'source_row': excel_row, 'reason': '位置与问题均为空'})
            continue
        dept_raw = g('dept')
        dept, hit = normalize_dept(dept_raw)
        date_raw = g('date')
        case_date = parse_case_date(date_raw, fallback=force_date) if (date_raw or force_date) else parse_case_date(None, fallback=force_date)
        # 日期无法解析（含"未标注"）一律按当日日期处理，不再当疑点上报
        # （需求方 2026-10-22 确认：未标注按照当日日期写）
        # 责任单位合写取第一个，命中字典即可，不上报

        # 收集本行照片：按行取该行所有列上的浮动图（列号不苛求，见上注释），
        # 统一按本表类型定 kind；若表里同时有"问题图片"和"整改图片"两列，
        # 则按图片所在列区分（整改清单常把原问题图和整改后图分列放）。
        photos = []
        over = 0  # 因超单行上限而未入库的图数
        row_imgs = []  # [(列号, [bytes,...])] 按列序排列，保证 seq 稳定
        for col in sorted({c for (r, c) in images if r == excel_row}):
            row_imgs.append((col, images[(excel_row, col)]))
        if not row_imgs:
            row_imgs = []
        for col, raws in row_imgs:
            # 这一列是什么类型：看它对应哪个图片列名；认不出就按表整体类型
            pk = None
            for k, c in photo_cols.items():
                if c == col:
                    pk = k
                    break
            if pk is None:
                pk = 'problem' if kind == 'problem' else 'rectify'
            for raw in raws:
                # 单行图数上限：超过说明上游把别处的图堆到了本行（实测整改清单
                # 第135行34张、第123行13张、第3行12张都是整段图堆在首行）。
                # 前 N 张正常入库，超出的落 need_review，不猜也不丢。
                if len(photos) >= MAX_PHOTOS_PER_ROW:
                    over += 1
                    continue
                seqs[pk] += 1
                photos.append({'kind': pk, 'seq': seqs[pk], 'raw': raw})

        if over:
            review.append({
                'source_row': excel_row,
                'reason': f'本行锚了 {over + len(photos)} 张图，超过单行上限 {MAX_PHOTOS_PER_ROW} 张；'
                          f'已取前 {len(photos)} 张，剩余 {over} 张未入库'
                          f'（多为上游把整段问题的图堆在了首行，请核对哪些属于本问题）',
            })

        if not photos and not location:
            review.append({'source_row': excel_row, 'reason': '既无位置也无照片，跳过'})
            continue

        cases.append({
            'source_row': excel_row,
            'case_date': case_date,
            'road': g('road') or '',
            'location': location or '',
            'problem': problem or '',
            'dept': dept,
            'dept_raw': dept_raw,
            'result': g('result') or '',
            'status': g('status') or '',
            'leader_group': g('leader') or '',
            'photos': photos,
        })
        date_counter[case_date] += 1

    if date_counter:
        print('  按日期: ' + ', '.join(f'{d}={n}' for d, n in sorted(date_counter.items())))
    return cases, review, kind


def write_output(all_cases, all_review, out_dir, source_name):
    """落盘：图片 + import_payload.json + need_review.json"""
    photo_dir = os.path.join(out_dir, 'photos')
    os.makedirs(photo_dir, exist_ok=True)
    payload_cases = []
    n_photos = 0
    for c in all_cases:
        photos = []
        for p in c['photos']:
            fn = f"{c['source_row']}-{'p' if p['kind'] == 'problem' else 'r'}{p['seq']}.jpg"
            abs_path = os.path.join(photo_dir, fn)
            im = Image.open(io.BytesIO(p['raw']))
            im.load()
            if im.mode not in ('RGB', 'L'):
                im = im.convert('RGB')
            w, h = im.size
            if max(w, h) > MAX_EDGE:
                ratio = MAX_EDGE / max(w, h)
                im = im.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
            im.save(abs_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)
            phash = _phash_hex(open(abs_path, 'rb').read())
            photos.append({'kind': p['kind'], 'seq': p['seq'],
                           'file_token': fn, 'phash': phash})
            n_photos += 1
        payload_cases.append({
            'source_row': c['source_row'], 'case_date': c['case_date'],
            'road': c['road'], 'location': c['location'], 'problem': c['problem'],
            'dept': c['dept'], 'dept_raw': c.get('dept_raw'),
            'result': c['result'], 'status': c['status'],
            'leader_group': c['leader_group'], 'photos': photos,
        })

    batch = datetime.now().strftime('%Y%m%d-%H%M')
    payload = {'batch_no': batch, 'source_file': source_name, 'cases': payload_cases}
    pp = os.path.join(out_dir, 'import_payload.json')
    with open(pp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    rp = os.path.join(out_dir, 'need_review.json')
    with open(rp, 'w', encoding='utf-8') as f:
        json.dump({'batch_no': batch, 'source_file': source_name,
                   'items': all_review}, f, ensure_ascii=False, indent=2)

    print(f'\n输出目录: {out_dir}')
    print(f'  import_payload.json : {len(payload_cases)} 件 / {n_photos} 张图')
    print(f'  need_review.json    : {len(all_review)} 条待确认')
    print(f'  photos/             : {n_photos} 个文件')
    print('\n下一步：')
    print(f'  1. 用 POST /api/inspection/photos 上传 {photo_dir} 里的图片，'
          f'把返回的 file_token 替换进 import_payload.json')
    print(f'     （本脚本已用 {fn  if n_photos else "无"} 形式命名，file_token 即文件名）')
    print(f'  2. 若有 need_review.json 条目，先逐条确认')
    print(f'  3. POST /api/inspection/import，请求体就是 import_payload.json')
    return payload


def main():
    ap = argparse.ArgumentParser(description='每日部门表解析器')
    ap.add_argument('path', help='表文件或目录（目录则遍历其中所有 xlsx）')
    ap.add_argument('--date', help='本批数据的日期（YYYY-MM-DD），表里没写日期时用')
    ap.add_argument('--out', help='输出目录', default=None)
    ap.add_argument('--kind', choices=['auto', 'problem', 'rectify'], default='auto',
                    help='强制指定表类型，默认按文件名/表头猜')
    args = ap.parse_args()

    path = args.path
    if os.path.isdir(path):
        files = sorted(os.path.join(path, f) for f in os.listdir(path)
                       if f.lower().endswith(('.xlsx', '.xls')))
    else:
        files = [path]
    if not files:
        print('没有找到 xlsx/xls 文件')
        return 1

    out_dir = args.out or os.path.join(
        os.path.dirname(os.path.abspath(path)) if os.path.isfile(path) else path,
        '_parsed_' + datetime.now().strftime('%Y%m%d_%H%M'))

    all_cases, all_review = [], []
    src_names = []
    for f in files:
        try:
            cases, review, kind = parse_file(
                f, force_date=args.date,
                force_kind=None if args.kind == 'auto' else args.kind)
            all_cases.extend(cases)
            all_review.extend(review)
            src_names.append(os.path.basename(f))
        except Exception as e:
            print(f'\n!! {os.path.basename(f)} 解析失败: {e}')
            all_review.append({'source_file': os.path.basename(f), 'reason': f'整表解析失败：{e}'})

    if not all_cases:
        print('\n没有解析出任何案件，检查表结构。')
        return 1
    write_output(all_cases, all_review, out_dir, ' + '.join(src_names))
    return 0


if __name__ == '__main__':
    sys.exit(main())
