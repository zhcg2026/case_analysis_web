# -*- coding: utf-8 -*-
"""领导巡查问题台账模块（insp_ 前缀新表，与现有案件/创文模块完全解耦）。

安全约定（与创文 cyw_routes 一致）：
- 仅 CREATE TABLE IF NOT EXISTS 新建 insp_ 前缀表，不改 users/case_data/cyw_* 等既有业务表
- 不 DROP 任何业务数据表；权限位新增列走 app.py 既有 ensure_columns 流程（可空+默认值0）
- 照片落 backend/uploads/inspection/ 子目录，经 app.py 既有 /uploads/ 静态路由访问
- 本文件不自建 SQLAlchemy 模型类，全部走 engine 原生 SQL（避免字段顺序与 SQL 漂移）

业务口径（2026-10-22 与需求方确认）：
- status 只有两值：待整改 / 已整改。其它写法（整改中/正在处理/部分完成）一律归为待整改
- 没有实际整改结果的都按待整改入库，不判断"是否属于本中心职责"
- 一次导入内不去重（同一张表里两条文字完全相同的记录是不同点位，照片不同，如韩信路4行）
- 幂等键 = source_file + source_row：同一份表重复导入不会翻倍，但不同日期的同文字案件各自成案
- 疑似重复只认照片：新案某张问题图 phash 与库内某案照片距离<=2 才进人工确认队列，文字相同不问
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import quote

from flask import request, jsonify, Response, send_file
from PIL import Image
from sqlalchemy import text
from functools import wraps

logger = logging.getLogger(__name__)

try:
    from common import protected as _protected, admin_required as _admin_required
    from common import verify_token as _verify_token
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required
    from helpers import verify_token as _verify_token

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
INSP_PHOTO_DIR = os.path.join(UPLOAD_DIR, 'inspection')
# 导入暂存区：上传的照片先落这里，导入时按 file_token 取；判重/落盘都在入库同一步完成
STAGE_DIR = os.path.join(UPLOAD_DIR, 'inspection_stage')
os.makedirs(INSP_PHOTO_DIR, exist_ok=True)
os.makedirs(STAGE_DIR, exist_ok=True)

ALLOWED_IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}

# 压缩落盘参数：最长边 1280、质量 80（汇报看图够用，单张约 100-200KB）
MAX_EDGE = 1280
JPEG_QUALITY = 80

# 责任单位归一化字典（上游各部门表格式不受控，命中即归一）
DEPT_ALIAS = {
    '执法': '执法队', '执法队': '执法队', '城管执法': '执法队', '综合执法': '执法队',
    '市政公用服务中心': '市政', '市政': '市政', '市政中心': '市政',
    '园林绿化服务中心': '园林', '园林': '园林', '园林中心': '园林',
    '市容环卫中心': '环卫', '环卫': '环卫', '环卫中心': '环卫',
    '排水': '排水', '排水服务中心': '排水', '泵站': '排水',
    '市容秩序科': '市容秩序科', '秩序科': '市容秩序科',
    '未知': '市政', '部队': '市政',
}
# 字典外的值不置空、不丢弃，原样入库并计入 errors 待人工确认

# 判"已整改"的拒绝口径：result 命中这些词，即使有整改图也不算整改完成
REJECT_RE = re.compile(r'不属于|非我中心|建议转|搬不动')

# 判重：照片感知哈希距离 <= 该值视为同一张图
PHASH_DUP_DISTANCE = 2

STATUS_VALID = ('待整改', '已整改')


# Display-only classification: the first matching rule wins, never written to case data.
INSP_CATEGORY_RULES = (
    ('设施破损', r'地砖|路面|路沿石|井盖|护栏|树篦|树池|坑洼|隔离桩|隔离墩|围挡|线缆|电线|灯杆|路灯'),
    ('环境卫生', r'垃圾|脏|不洁|污|小广告|积水|清运|油渍'),
    ('车辆停放', r'车辆|停车|停放|小蓝|单车|小彬|哈罗'),
    ('占道及堆放', r'摊点|商贩|经营|占道|堆|晾晒|晾乱晒'),
    ('绿化养护', r'缺苗|缺株|绿化|枯|黄土|补植|树木|修剪|裸露'),
)
INSP_AGE_BANDS = (('0—3天', 0, 3), ('4—7天', 4, 7), ('8—14天', 8, 14),
                  ('15—21天', 15, 21), ('22天及以上', 22, None))


def inspection_period(args, today):
    """Calendar periods in server Asia/Shanghai. Endpoints refer to discovery dates only."""
    from datetime import date
    mode = args.get('mode', 'all')
    if mode not in ('all', 'month', 'week', 'day', 'range'):
        raise ValueError('统计模式无效')
    def parse(value):
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value)):
                raise ValueError()
            d = date.fromisoformat(value)
            if d.year < 2000 or d > today:
                raise ValueError()
            return d
        except (ValueError, TypeError):
            raise ValueError('日期须为2000年起且不晚于今天的有效日期')
    anchor = parse(args.get('anchor') or today.isoformat())
    start = end = previous_start = previous_end = None
    if mode == 'day':
        start = end = anchor
        previous_start = previous_end = start - timedelta(days=1)
    elif mode == 'week':
        start = anchor - timedelta(days=anchor.weekday())
        end = min(start + timedelta(days=6), today)
        previous_start = start - timedelta(days=7)
        previous_end = previous_start + (end - start)
    elif mode == 'month':
        start = anchor.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = min(next_month - timedelta(days=1), today)
        previous_end_of_month = start - timedelta(days=1)
        previous_start = previous_end_of_month.replace(day=1)
        previous_end = min(previous_start + (end - start), previous_end_of_month)
    elif mode == 'range':
        start = parse(args.get('date_from'))
        end = parse(args.get('date_to'))
        if end < start:
            raise ValueError('开始日期不能晚于结束日期')
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - (end - start)
    if start and (end - start).days > 3660:
        raise ValueError('统计区间不能超过10年')
    try:
        page, size = int(args.get('page', 1)), int(args.get('size', 20))
    except (TypeError, ValueError):
        raise ValueError('分页参数无效')
    if page < 1 or not 1 <= size <= 50:
        raise ValueError('每页须为1—50条且页码大于0')
    return {'mode': mode, 'start': start, 'end': end, 'previous_start': previous_start,
            'previous_end': previous_end, 'page': page, 'size': size}


def build_inspection_analysis(rows, args, today):
    """Pure aggregation of minimal case columns. No mutations, SQL, photos or history inference."""
    from datetime import date
    p = inspection_period(args, today)
    category_rules = [(name, re.compile(pattern)) for name, pattern in INSP_CATEGORY_RULES]
    dispute_re = re.compile(r'不属于|非我|建议转|转办|权属|非本科室|非我科室|不归|管理范围')
    enriched = []
    for source in rows:
        r = dict(source)
        found = date.fromisoformat(str(r['case_date'])[:10])
        # Future discovery dates are invalid for present-state metrics; expose their count separately.
        r['case_date'] = found.isoformat()
        r['dept'] = r.get('dept') or '未填'
        r['road'] = r.get('road') or '未填'
        r['category'] = next((name for name, pattern in category_rules
                              if pattern.search(str(r.get('problem') or ''))), '未分类')
        r['age_days'] = (today - found).days
        r['disputed'] = bool(dispute_re.search(str(r.get('result') or '')))
        r['_date'] = found
        enriched.append(r)
    valid = [r for r in enriched if r['_date'] <= today]
    selected = [r for r in valid if not p['start'] or p['start'] <= r['_date'] <= p['end']]
    pending = [r for r in selected if r['status'] != '已整改']
    done = len(selected) - len(pending)
    def pct(n, d):
        return round(n / d * 100, 1) if d else None
    def grouped(key):
        result = {}
        for r in selected:
            entry = result.setdefault(r[key], {'name': r[key], 'total': 0, 'rectified': 0, 'pending': 0})
            entry['total'] += 1
            entry['rectified' if r['status'] == '已整改' else 'pending'] += 1
        for entry in result.values():
            entry['rate'] = pct(entry['rectified'], entry['total'])
            entry['pending_share'] = pct(entry['pending'], len(pending))
        return sorted(result.values(), key=lambda x: (-x['pending'], -x['total'], x['name']))
    bands = []
    for label, low, high in INSP_AGE_BANDS:
        count = sum(r['age_days'] >= low and (high is None or r['age_days'] <= high) for r in pending)
        bands.append({'name': label, 'min': low, 'max': high, 'total': count,
                      'share': pct(count, len(pending))})
    by_day = {}
    for r in selected:
        entry = by_day.setdefault(r['case_date'], {'name': r['case_date'], 'total': 0, 'rectified': 0, 'pending': 0})
        entry['total'] += 1
        entry['rectified' if r['status'] == '已整改' else 'pending'] += 1
    # Fill zeros only within a bounded current query range; never claim absence of inspections.
    first = p['start'] or min((r['_date'] for r in selected), default=today)
    last = p['end'] or max((r['_date'] for r in selected), default=today)
    granularity = 'day' if (last - first).days <= 92 else 'week' if (last - first).days <= 730 else 'month'
    buckets = {}
    cursor = first
    while cursor <= last:
        key = cursor.isoformat() if granularity == 'day' else (
            (cursor - timedelta(days=cursor.weekday())).isoformat() if granularity == 'week' else cursor.strftime('%Y-%m'))
        entry = buckets.setdefault(key, {'name': key, 'total': 0, 'rectified': 0, 'pending': 0})
        daily = by_day.get(cursor.isoformat(), {})
        for field in ('total', 'rectified', 'pending'):
            entry[field] += daily.get(field, 0)
        cursor += timedelta(days=1)
    comparison = None
    earliest = min((r['_date'] for r in valid), default=None)
    if p['previous_start']:
        previous = [r for r in valid if p['previous_start'] <= r['_date'] <= p['previous_end']]
        coverage = bool(earliest and earliest <= p['previous_start'])
        # If previous month is shorter, compare only the same number of calendar days on both sides.
        days = (p['previous_end'] - p['previous_start']).days + 1
        comparable_end = p['start'] + timedelta(days=days - 1)
        comparable = [r for r in selected if r['_date'] <= comparable_end]
        previous_total = len(previous)
        comparison = {'start': p['previous_start'].isoformat(), 'end': p['previous_end'].isoformat(),
                      'current_start': p['start'].isoformat(), 'current_end': comparable_end.isoformat(),
                      'days': days, 'total': previous_total, 'current_total': len(comparable),
                      'available': coverage, 'delta': len(comparable) - previous_total if coverage else None,
                      'percent': round((len(comparable) - previous_total) / previous_total * 100, 1)
                      if coverage and previous_total else None,
                      'note': '仅比较相同日数的已登记问题量；不代表巡查工作量或绩效。' if coverage else '对比期早于台账最早发现日期，数据覆盖不足，不作增减判断。'}
    departments, roads, categories = grouped('dept'), grouped('road'), grouped('category')
    old_count = sum(r['age_days'] >= 15 for r in pending)
    dispute_count = sum(r['disputed'] for r in pending)
    period_label = f"{p['start']}至{p['end']}" if p['start'] else '全部已登记问题'
    narrative = [{'text': f"{period_label}共发现{len(selected)}件问题，目前已整改{done}件、待整改{len(pending)}件，"
                         + (f"整改率{pct(done, len(selected))}%。" if selected else '整改率暂无。'),
                  'kind': 'all', 'value': ''}]
    if pending:
        leaders = [d for d in departments if d['pending']][:2]
        count = sum(d['pending'] for d in leaders)
        narrative.append({'text': f"待整改问题主要集中在{'、'.join(d['name'] for d in leaders)}，共{count}件，占本期待整改的{pct(count, len(pending))}%。",
                          'kind': 'pending', 'value': ''})
        narrative.append({'text': f"本期问题中，发现满15天仍待整改{old_count}件，占待整改的{pct(old_count, len(pending))}%；涉及权属或转办表述的待整改问题{dispute_count}件，需逐条核实。",
                          'kind': 'old', 'value': ''})
    if roads:
        busiest = sorted(roads, key=lambda d: (-d['total'], d['name']))[:3]
        count = sum(d['total'] for d in busiest)
        narrative.append({'text': f"问题量居前的道路为{'、'.join(d['name'] for d in busiest)}，合计{count}件，占本期问题的{pct(count, len(selected))}%。",
                          'kind': 'all', 'value': ''})
    if comparison:
        if comparison['available']:
            difference = comparison['delta']
            narrative.append({'text': f"同阶段（各{comparison['days']}天）登记问题，本期{comparison['current_total']}件、对比期{comparison['total']}件，"
                                     + (f"增加{difference}件。" if difference > 0 else f"减少{-difference}件。" if difference < 0 else '数量持平。'),
                              'kind': 'all', 'value': ''})
        else:
            narrative.append({'text': comparison['note'], 'kind': 'all', 'value': ''})
    response = {'period': {'mode': p['mode'], 'start': str(p['start']) if p['start'] else None,
                           'end': str(p['end']) if p['end'] else None, 'label': period_label},
                'as_of': today.isoformat(), 'earliest_date': str(earliest) if earliest else None,
                'latest_date': str(max((r['_date'] for r in valid), default='')) or None,
                'future_date_count': len(enriched) - len(valid),
                'overview': {'total': len(selected), 'rectified': done, 'pending': len(pending),
                             'rate': pct(done, len(selected)), 'old_pending': old_count,
                             'disputed': dispute_count, 'roads': len(roads), 'departments': len(departments)},
                'comparison': comparison, 'trend': list(buckets.values()), 'trend_grain': granularity,
                'departments': departments, 'roads': roads, 'categories': categories, 'ages': bands,
                'narrative': narrative,
                'classification_rules': [{'name': name, 'keywords': pattern} for name, pattern in INSP_CATEGORY_RULES],
                'classification_note': '按问题描述关键词依次匹配，仅供分析，不改原案；无法识别保留未分类。'}
    kind = args.get('detail_kind')
    if kind:
        value = str(args.get('detail_value') or '')
        detail = selected
        if kind in ('dept', 'road', 'category', 'date'):
            field = 'case_date' if kind == 'date' else kind
            detail = [r for r in selected if r[field] == value]
        elif kind == 'age':
            band = next((b for b in bands if b['name'] == value), None)
            if band is None:
                raise ValueError('账龄区间无效')
            detail = [r for r in pending if r['age_days'] >= band['min'] and (band['max'] is None or r['age_days'] <= band['max'])]
        elif kind == 'pending':
            detail = pending
        elif kind == 'done':
            detail = [r for r in selected if r['status'] == '已整改']
        elif kind == 'old':
            detail = [r for r in pending if r['age_days'] >= 15]
        elif kind == 'disputed':
            detail = [r for r in pending if r['disputed']]
        elif kind != 'all':
            raise ValueError('明细类型无效')
        detail = sorted(detail, key=lambda r: (r['status'] == '已整改', -r['age_days'], r['id']))
        offset = (p['page'] - 1) * p['size']
        response['detail'] = {'total': len(detail), 'page': p['page'], 'size': p['size'],
                              'items': [{k: v for k, v in r.items() if k != '_date'}
                                        for r in detail[offset:offset + p['size']]]}
    return response


def _now() -> str:
    """服务器容器 TZ=Asia/Shanghai，这里显式取本地时间，避免 MySQL NOW() 用 UTC 覆写。"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def normalize_text(s) -> str:
    """归一化：去空白与中英文标点后转小写（位置整体参与，不截取）。"""
    if s is None:
        return ''
    s = str(s)
    s = re.sub(r'[\s，。、；：！!（）()【】\[\]"\'‘’“”·\-_—–,.?？:;~/]', '', s)
    return s.lower()


def normalized_key(location, problem) -> str:
    """去重键：md5(归一化位置|归一化问题)。仅用于候选提示，不作为唯一约束。"""
    import hashlib
    raw = normalize_text(location) + '|' + normalize_text(problem)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def normalize_dept(raw):
    """责任单位归一化。返回 (归一化值, 是否命中字典)。

    合写单位（如"市政、环卫"）取第一个作为主责单位，其余单位记在 dept_raw 里留痕
    （需求方 2026-10-22 确认：指定第一个为主办，不拆成多案）。
    """
    if raw is None:
        return None, False
    s = str(raw).strip()
    if not s:
        return None, False
    # 合写：按中文顿号/逗号/斜杠/加号拆，取第一个
    if re.search(r'[、,，/＋+]', s):
        first = re.split(r'[、,，/＋+]', s)[0].strip()
        if first:
            s = first
    if s in DEPT_ALIAS:
        return DEPT_ALIAS[s], True
    # 去掉"中心/服务中心"等后缀再试一次，提高上游脏写法命中率
    stripped = re.sub(r'(服务中心|中心|科室|办公室)$', '', s)
    if stripped in DEPT_ALIAS:
        return DEPT_ALIAS[stripped], True
    return s, False


def judge_status(raw_status, result) -> str:
    """状态两值化。只有'已整改'保留，其余一律待整改。"""
    s = str(raw_status or '').strip()
    if s == '已整改':
        # result 命中拒绝口径时，即使标了已整改也按待整改（这活儿不归我管，不算整改完成）
        if result and str(result).strip() not in ('', '—', '-', '–') and REJECT_RE.search(str(result)):
            return '待整改'
        return '已整改'
    return '待整改'


def parse_case_date(raw, fallback=None) -> str:
    """一行只允许一个日期。支持 '2026-10-21' / '10月21日' / '2026/10/21'；
    区间写法（10月17-18日、10.17-18）取首日；解析失败用 fallback（调用方给文件送达日）。"""
    if raw is None:
        return fallback or _today()
    s = str(raw).strip()
    if not s:
        return fallback or _today()
    m = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})', s)
    if m:
        return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    # 区间写法优先：取首日（月日都可带范围符）
    m = re.match(r'^(\d{1,2})月(\d{1,2})\s*日', s)
    if m:
        year = datetime.now().year
        return f'{year:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}'
    m = re.match(r'^(\d{1,2})[-/.](\d{1,2})', s)  # 10.21 或 10-21 或 10/21
    if m:
        year = datetime.now().year
        return f'{year:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}'
    logger.warning(f'[INSP] 日期无法解析: {s!r}，回退 {fallback or _today()}')
    return fallback or _today()


# ---------------------------------------------------------------- 建表
INSP_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS insp_case (
      id            INT AUTO_INCREMENT PRIMARY KEY,
      case_date     DATE NOT NULL COMMENT '巡查发现日期（单日，禁止区间）',
      road          VARCHAR(50)  NOT NULL COMMENT '道路',
      location      VARCHAR(255) NOT NULL COMMENT '具体位置',
      problem       TEXT         NOT NULL COMMENT '问题描述',
      dept          VARCHAR(50)  DEFAULT NULL COMMENT '责任单位（归一化后）',
      dept_raw      VARCHAR(50)  DEFAULT NULL COMMENT '责任单位原文（未命中字典时留痕）',
      result        VARCHAR(500) DEFAULT NULL COMMENT '处理结果（部门填写原文）',
      status        VARCHAR(10)  NOT NULL DEFAULT '待整改' COMMENT '仅两值：待整改 / 已整改',
      leader_group  VARCHAR(50)  DEFAULT NULL COMMENT '带队领导或巡查组（可选）',
      normalized_key CHAR(32)    NOT NULL COMMENT '去重提示键=md5(归一化位置|归一化问题)，非唯一约束',
      photo_hashes  TEXT         DEFAULT NULL COMMENT '本案件照片感知哈希JSON数组',
      source_file   VARCHAR(255) DEFAULT NULL COMMENT '来源文件名',
      source_row    INT          DEFAULT NULL COMMENT '来源文件中的行号',
      first_seen_at DATETIME     DEFAULT CURRENT_TIMESTAMP,
      rectified_at  DATETIME     DEFAULT NULL COMMENT '判定为已整改的日期',
      remark        VARCHAR(500) DEFAULT NULL,
      UNIQUE KEY uk_source (source_file, source_row),
      KEY idx_date (case_date), KEY idx_dept (dept), KEY idx_status (status), KEY idx_road (road)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS insp_photo (
      id         INT AUTO_INCREMENT PRIMARY KEY,
      case_id    INT NOT NULL COMMENT '关联 insp_case.id',
      kind       VARCHAR(10) NOT NULL COMMENT 'problem=问题图 / rectify=整改图',
      file_path  VARCHAR(500) NOT NULL COMMENT '相对路径 /uploads/inspection/...',
      phash      CHAR(16) DEFAULT NULL COMMENT '感知哈希（16位十六进制）',
      orig_name  VARCHAR(255) DEFAULT NULL COMMENT '原始文件名',
      seq        INT NOT NULL DEFAULT 1 COMMENT '同案件同类型内的序号',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      UNIQUE KEY uk_case_kind_seq (case_id, kind, seq),
      KEY idx_case (case_id), KEY idx_phash (phash),
      CONSTRAINT fk_photo_case FOREIGN KEY (case_id) REFERENCES insp_case(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS insp_dup_candidate (
      id              INT AUTO_INCREMENT PRIMARY KEY,
      batch_no        VARCHAR(40) NOT NULL COMMENT '一次导入一个批次号',
      new_case_json   TEXT NOT NULL COMMENT '待入库记录的完整JSON',
      matched_case_id INT DEFAULT NULL COMMENT '命中的库内案件ID',
      match_score     DECIMAL(4,3) DEFAULT NULL COMMENT '相似度 0-1',
      match_reason    VARCHAR(30) DEFAULT NULL COMMENT 'phash=照片一致 / exact=归一化相同 / fuzzy=近似',
      decision        VARCHAR(10) NOT NULL DEFAULT 'pending' COMMENT 'pending/merged/new',
      decided_by      INT DEFAULT NULL,
      decided_at      DATETIME DEFAULT NULL,
      created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
      KEY idx_batch (batch_no), KEY idx_decision (decision)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def ensure_inspection_tables(engine):
    """建表（仅首次）。只建 insp_ 前缀三张表，不 ALTER/DROP 任何既有表。"""
    if engine is None:
        raise RuntimeError('engine 不可用，拒绝建表')
    with engine.begin() as conn:
        for sql in INSP_TABLES:
            conn.execute(text(sql))
    logger.info('[INSP] insp_ 三表 ensured')


# ---------------------------------------------------------------- 图片工具（模块级，供迁移脚本复用）
def _photo_subdir(case_date: str) -> str:
    """按案件日期分目录：uploads/inspection/20261021/"""
    d = str(case_date or '').replace('-', '')
    return os.path.join(INSP_PHOTO_DIR, d)


def _phash_hex(img_bytes: bytes) -> str:
    """算感知哈希。失败必须抛出，由调用方计入 errors，禁止静默跳过。"""
    import imagehash
    im = Image.open(io.BytesIO(img_bytes))
    im.load()
    return str(imagehash.phash(im))


def _hamming(a: str, b: str) -> int:
    """两个16位十六进制 phash 的汉明距离。"""
    if not a or not b:
        return 99
    try:
        return bin(int(a, 16) ^ int(b, 16)).count('1')
    except ValueError:
        return 99


def _save_photo(case_id: int, kind: str, seq: int, img_bytes: bytes,
                case_date: str, orig_name: str = '', phash: str = ''):
    """压缩落盘。返回 (绝对路径, 相对URL)。
    命名：{MMDD}-{case_id 补零4位}-{p|r}{seq}.jpg；最长边1280、JPEG质量80。"""
    subdir = _photo_subdir(case_date)
    os.makedirs(subdir, exist_ok=True)
    prefix = str(case_date or '')[5:].replace('-', '') or '0000'
    save_name = f'{prefix}-{case_id:04d}-{"p" if kind == "problem" else "r"}{seq}.jpg'
    abs_path = os.path.join(subdir, save_name)

    im = Image.open(io.BytesIO(img_bytes))
    im.load()
    if im.mode not in ('RGB', 'L'):
        im = im.convert('RGB')
    w, h = im.size
    if max(w, h) > MAX_EDGE:
        ratio = MAX_EDGE / max(w, h)
        im = im.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
    im.save(abs_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)

    rel_url = f'/uploads/inspection/{str(case_date or "").replace("-", "")}/{save_name}'
    return abs_path, rel_url


def _find_phash_match(conn, phash: str, exclude_case_id=None):
    """在库内找 phash 距离<=2 的照片，返回 (case_id, 距离)。找不到返回 None。"""
    if not phash:
        return None
    rows = conn.execute(text(
        "SELECT p.case_id, p.phash FROM insp_photo p WHERE p.phash IS NOT NULL AND p.phash != ''"
    )).fetchall()
    best = None
    for cid, existing in rows:
        if exclude_case_id is not None and cid == exclude_case_id:
            continue
        d = _hamming(phash, existing)
        if d <= PHASH_DUP_DISTANCE and (best is None or d < best[1]):
            best = (cid, d)
    return best


# ---------------------------------------------------------------- 注册路由
def register_inspection_routes(app, Session=None, engine=None, protected=None, admin_required=None):
    """注册领导巡查问题台账路由。engine 由 app.py 传入；建表失败只告警，不影响其余路由。"""
    if engine is None:
        logger.warning('[INSP] engine 不可用，跳过建表与路由注册')
        return

    def perm_access(permission_key):
        """细粒度权限鉴权：admin 直通；普通用户需 permissions 表对应列=1
        （permission_key 为单键或键元组，元组是「或」语义）"""
        keys = (permission_key,) if isinstance(permission_key, str) else tuple(permission_key)
        cols = ', '.join(keys)

        def decorator(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                token = request.headers.get("Authorization")
                if not token:
                    return jsonify({"error": "Missing token"}), 401
                if token.startswith("Bearer "):
                    token = token[7:]
                payload = _verify_token(token)
                if not payload:
                    return jsonify({"error": "Invalid or expired token"}), 401
                request.user_id = payload["user_id"]
                request.username = payload["username"]
                request.role = payload["role"]
                if payload.get("role") == "admin":
                    return f(*args, **kwargs)
                try:
                    with engine.connect() as conn:
                        row = conn.execute(
                            text(f"SELECT {cols} FROM permissions WHERE user_id = :uid"),
                            {"uid": payload["user_id"]}
                        ).fetchone()
                    if not row or not any(row):
                        return jsonify({"error": "Permission denied"}), 403
                except Exception as e:
                    logger.error(f"[INSP] 权限校验失败: {e}")
                    return jsonify({"error": "Permission check failed"}), 500
                return f(*args, **kwargs)
            return decorated
        return decorator

    try:
        ensure_inspection_tables(engine)
    except Exception as e:
        logger.warning(f'[INSP] insp_ 表创建失败（路由仍注册，接口会报错提示）: {e}')

    insp_access = perm_access('inspection')

    # ---------------------------------------------------------------- 图片暂存

    def _read_staged_photo(token: str):
        """读暂存区照片文件。token 是纯文件名（禁止带路径，防目录穿越）。找不到返回 None。"""
        safe = os.path.basename(str(token or '').strip())
        if not safe or safe != str(token or '').strip():
            return None
        abs_path = os.path.join(STAGE_DIR, safe)
        if not os.path.isfile(abs_path):
            return None
        with open(abs_path, 'rb') as f:
            return f.read()

    # ---------------------------------------------------------------- 导入接口

    @app.route('/api/inspection/import', methods=['POST'])
    @insp_access
    def insp_import():
        """批量导入案件。同文件内不去重；幂等键 source_file+source_row；
        照片 phash 命中库内已有照片才进疑似重复队列。返回七项对账计数。"""
        payload = request.get_json(silent=True) or {}
        batch_no = (payload.get('batch_no') or '').strip()
        source_file = (payload.get('source_file') or '').strip()
        cases = payload.get('cases') or []
        if not batch_no:
            return jsonify({'error': '缺少 batch_no'}), 400
        if not source_file:
            return jsonify({'error': '缺少 source_file'}), 400
        if not isinstance(cases, list):
            return jsonify({'error': 'cases 必须是数组'}), 400

        counters = {
            'inserted': 0, 'updated': 0, 'duplicates_skipped': 0,
            'pending_review': 0, 'photos_received': 0, 'photos_saved': 0,
        }
        errors = []

        for idx, c in enumerate(cases):
            row_no = c.get('source_row')
            label = f'第{row_no}行' if row_no else f'第{idx + 1}条'
            try:
                # --- 幂等：同一份表同一行，直接跳过（重复导入保护）
                with engine.begin() as conn:
                    exist = conn.execute(text(
                        "SELECT id FROM insp_case WHERE source_file = :sf AND source_row = :sr"
                    ), {'sf': source_file, 'sr': row_no}).fetchone()
                if exist:
                    counters['duplicates_skipped'] += 1
                    continue

                # --- 字段清洗
                case_date = parse_case_date(c.get('case_date'))
                road = (c.get('road') or '').strip()
                location = (c.get('location') or '').strip()
                problem = (c.get('problem') or '').strip()
                if not location and not problem:
                    errors.append({'source_row': row_no, 'reason': '位置与问题均为空'})
                    continue
                dept, hit = normalize_dept(c.get('dept'))
                if c.get('dept') and not hit:
                    errors.append({'source_row': row_no,
                                   'reason': f'责任单位不在字典内：{c.get("dept")}（已原文入库，请确认）'})
                result = (c.get('result') or '').strip()
                status = judge_status(c.get('status'), result)
                rectified_at = _now() if status == '已整改' else None

                # --- 照片：先全部读出并算 phash，再判定是否疑似重复
                photos = c.get('photos') or []
                counters['photos_received'] += len(photos)
                photo_records = []
                for p in photos:
                    token = (p.get('file_token') or '').strip()
                    kind = p.get('kind') or 'problem'
                    seq = int(p.get('seq') or 1)
                    phash = (p.get('phash') or '').strip().lower() or None
                    if not token:
                        errors.append({'source_row': row_no, 'reason': f'照片缺少 file_token（{kind}/{seq}）'})
                        continue
                    raw = _read_staged_photo(token)
                    if raw is None:
                        errors.append({'source_row': row_no, 'reason': f'照片文件不存在或读不到：{token}'})
                        continue
                    if not phash:
                        try:
                            phash = _phash_hex(raw)
                        except Exception as e:
                            errors.append({'source_row': row_no,
                                           'reason': f'phash 计算失败：{token}（{e}）'})
                            continue
                    photo_records.append({'kind': kind, 'seq': seq, 'phash': phash,
                                          'orig_name': token, 'raw': raw})
                    counters['photos_saved'] += 1

                # --- 疑似重复：只看照片（文字相同不问，不同点位常被写成一样）
                dup = None
                problem_hashes = [p['phash'] for p in photo_records if p['kind'] == 'problem']
                if problem_hashes:
                    with engine.connect() as conn:
                        for ph in problem_hashes:
                            m = _find_phash_match(conn, ph)
                            if m:
                                dup = m
                                break
                if dup:
                    with engine.begin() as conn:
                        conn.execute(text(
                            "INSERT INTO insp_dup_candidate "
                            "(batch_no, new_case_json, matched_case_id, match_score, match_reason, decision) "
                            "VALUES (:b, :j, :m, :s, 'phash', 'pending')"
                        ), {'b': batch_no,
                            'j': json.dumps({'source_row': row_no, 'case_date': case_date,
                                             'road': road, 'location': location, 'problem': problem,
                                             'dept': dept, 'dept_raw': c.get('dept'),
                                             'result': result, 'status': status,
                                             'leader_group': c.get('leader_group'),
                                             'photos': [{'kind': p['kind'], 'seq': p['seq'],
                                                         'phash': p['phash'],
                                                         'orig_name': p['orig_name']}
                                                        for p in photo_records]},
                                            ensure_ascii=False),
                            'm': dup[0], 's': round(1.0 - dup[1] / 64.0, 3)})
                    counters['pending_review'] += 1
                    continue

                # --- 正式入库
                with engine.begin() as conn:
                    r = conn.execute(text(
                        "INSERT INTO insp_case "
                        "(case_date, road, location, problem, dept, dept_raw, result, status, "
                        " leader_group, normalized_key, photo_hashes, source_file, source_row, "
                        " first_seen_at, rectified_at) "
                        "VALUES (:cd, :rd, :lo, :pr, :dp, :dr, :rs, :st, :lg, :nk, :ph, :sf, :sr, :ts, :ra)"
                    ), {'cd': case_date, 'rd': road, 'lo': location, 'pr': problem,
                        'dp': dept, 'dr': (c.get('dept') or None), 'rs': result, 'st': status,
                        'lg': (c.get('leader_group') or None),
                        'nk': normalized_key(location, problem),
                        'ph': json.dumps([p['phash'] for p in photo_records if p['phash']],
                                         ensure_ascii=False),
                        'sf': source_file, 'sr': row_no, 'ts': _now(), 'ra': rectified_at})
                    case_id = r.lastrowid
                    for p in photo_records:
                        try:
                            abs_path, rel_url = _save_photo(
                                case_id, p['kind'], p['seq'], p['raw'], case_date, p['orig_name'])
                            conn.execute(text(
                                "INSERT INTO insp_photo (case_id, kind, file_path, phash, orig_name, seq) "
                                "VALUES (:c, :k, :f, :h, :o, :s)"
                            ), {'c': case_id, 'k': p['kind'], 'f': rel_url, 'h': p['phash'],
                                'o': p['orig_name'], 's': p['seq']})
                        except Exception as e:
                            errors.append({'source_row': row_no,
                                           'reason': f'照片落盘失败：{p["orig_name"]}（{e}）'})
                counters['inserted'] += 1
            except Exception as e:
                logger.exception(f'[INSP] 导入单条失败 {label}')
                errors.append({'source_row': row_no, 'reason': f'导入异常：{e}'})

        counters['errors'] = errors
        logger.info(f"[INSP] 导入 {source_file} 批次 {batch_no}: "
                    f"inserted={counters['inserted']} updated={counters['updated']} "
                    f"dup={counters['duplicates_skipped']} pending={counters['pending_review']} "
                    f"photos={counters['photos_saved']}/{counters['photos_received']} "
                    f"errors={len(errors)}")
        return jsonify(counters), 200

    # ---------------------------------------------------------------- 照片上传

    @app.route('/api/inspection/photos', methods=['POST'])
    @insp_access
    def insp_upload_photos():
        """上传本批照片到暂存区，返回 phash。file_token 即上传时的文件名，导入时按它取图。"""
        files = request.files.getlist('files') or request.files.getlist('file')
        if not files:
            return jsonify({'error': '没有收到文件'}), 400
        saved, errors = [], []
        for f in files:
            orig = f.filename or ''
            ext = os.path.splitext(orig)[1].lower()
            if ext not in ALLOWED_IMG_EXT:
                errors.append({'file': orig, 'reason': f'不支持的扩展名 {ext}'})
                continue
            token = f'{uuid.uuid4().hex}{ext}'
            abs_path = os.path.join(STAGE_DIR, token)
            try:
                # 先把整个文件读进内存，再用读到的字节落盘并算 phash。
                # 不能 f.read() 之后直接 f.save()——流已被推到末尾，会存出 0 字节文件
                # （曾因此静默丢图：文件存在但打不开，导入时才在 errors 里暴露）。
                raw = f.read()
                if not raw:
                    errors.append({'file': orig, 'reason': '文件内容为空'})
                    continue
                with open(abs_path, 'wb') as fh:
                    fh.write(raw)
                try:
                    phash = _phash_hex(raw)
                except Exception as e:
                    phash = None
                    errors.append({'file': orig, 'reason': f'phash 计算失败：{e}'})
                saved.append({'file_token': token, 'orig_name': orig, 'phash': phash})
            except Exception as e:
                errors.append({'file': orig, 'reason': f'保存失败：{e}'})
        return jsonify({'saved': saved, 'errors': errors}), 200

    # ---------------------------------------------------------------- 查询

    @app.route('/api/inspection/cases', methods=['GET'])
    @insp_access
    def insp_cases():
        """案件列表与筛选：日期区间、道路、责任单位、状态、关键字；分页。"""
        args = request.args
        date_from = (args.get('date_from') or '').strip()
        date_to = (args.get('date_to') or '').strip()
        road = (args.get('road') or '').strip()
        dept = (args.get('dept') or '').strip()
        status = (args.get('status') or '').strip()
        keyword = (args.get('keyword') or '').strip()
        page = max(1, int(args.get('page') or 1))
        size = min(200, max(1, int(args.get('size') or 20)))

        where, params = ['1=1'], {}
        if date_from:
            where.append('c.case_date >= :df')
            params['df'] = date_from
        if date_to:
            where.append('c.case_date <= :dt')
            params['dt'] = date_to
        if road:
            where.append('c.road LIKE :rd')
            params['rd'] = f'%{road}%'
        if dept:
            where.append('c.dept = :dp')
            params['dp'] = dept
        if status:
            where.append('c.status = :st')
            params['st'] = status
        if keyword:
            where.append('(c.location LIKE :kw OR c.problem LIKE :kw OR c.result LIKE :kw)')
            params['kw'] = f'%{keyword}%'
        wsql = ' AND '.join(where)

        with engine.connect() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) FROM insp_case c WHERE {wsql}"),
                                 params).scalar()
            rows = conn.execute(text(
                f"SELECT c.id, c.case_date, c.road, c.location, c.problem, c.dept, "
                f"       c.result, c.status, c.leader_group, c.source_file, c.source_row, "
                f"       c.first_seen_at, c.rectified_at "
                f"FROM insp_case c WHERE {wsql} "
                f"ORDER BY c.case_date DESC, c.id DESC LIMIT :lim OFFSET :off"
            ), {**params, 'lim': size, 'off': (page - 1) * size}).fetchall()
            ids = [r[0] for r in rows]
            photos_by_case = {}
            if ids:
                prows = conn.execute(text(
                    "SELECT case_id, kind, file_path, phash, seq FROM insp_photo "
                    "WHERE case_id IN :ids ORDER BY case_id, kind, seq"
                ).bindparams(bindparam_in := __import__('sqlalchemy').bindparam('ids', expanding=True)),
                    {'ids': ids}).fetchall()
                for cid, kind, fp, ph, seq in prows:
                    photos_by_case.setdefault(cid, []).append(
                        {'kind': kind, 'file_path': fp, 'phash': ph, 'seq': seq})

        items = []
        for r in rows:
            items.append({
                'id': r[0], 'case_date': str(r[1]), 'road': r[2], 'location': r[3],
                'problem': r[4], 'dept': r[5], 'result': r[6], 'status': r[7],
                'leader_group': r[8], 'source_file': r[9], 'source_row': r[10],
                'first_seen_at': str(r[11]) if r[11] else None,
                'rectified_at': str(r[12]) if r[12] else None,
                'photos': photos_by_case.get(r[0], []),
            })
        return jsonify({'total': total, 'page': page, 'size': size, 'items': items}), 200

    @app.route('/api/inspection/stats', methods=['GET'])
    @insp_access
    def insp_stats():
        """统计：总数/已整改/待整改/整改率，按道路与责任单位分组。全部实时聚合。"""
        args = request.args
        date_from = (args.get('date_from') or '').strip()
        date_to = (args.get('date_to') or '').strip()
        where, params = ['1=1'], {}
        if date_from:
            where.append('case_date >= :df')
            params['df'] = date_from
        if date_to:
            where.append('case_date <= :dt')
            params['dt'] = date_to
        wsql = ' AND '.join(where)

        with engine.connect() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) FROM insp_case WHERE {wsql}"),
                                 params).scalar() or 0
            done = conn.execute(text(
                f"SELECT COUNT(*) FROM insp_case WHERE {wsql} AND status = '已整改'"),
                params).scalar() or 0
            by_dept = conn.execute(text(
                f"SELECT COALESCE(dept, '未填') AS d, COUNT(*) AS n, "
                f"SUM(CASE WHEN status = '已整改' THEN 1 ELSE 0 END) AS done "
                f"FROM insp_case WHERE {wsql} GROUP BY d ORDER BY n DESC"
            ), params).fetchall()
            by_road = conn.execute(text(
                f"SELECT COALESCE(road, '未填') AS r, COUNT(*) AS n, "
                f"SUM(CASE WHEN status = '已整改' THEN 1 ELSE 0 END) AS done "
                f"FROM insp_case WHERE {wsql} GROUP BY r ORDER BY n DESC"
            ), params).fetchall()
            by_date = conn.execute(text(
                f"SELECT case_date, COUNT(*) AS n, "
                f"SUM(CASE WHEN status = '已整改' THEN 1 ELSE 0 END) AS done "
                f"FROM insp_case WHERE {wsql} GROUP BY case_date ORDER BY case_date"
            ), params).fetchall()

        pending = total - done
        return jsonify({
            'total': total, 'rectified': done, 'pending': pending,
            'rectify_rate': round(done / total * 100, 1) if total else 0.0,
            'by_dept': [{'dept': r[0], 'total': r[1], 'rectified': int(r[2] or 0)} for r in by_dept],
            'by_road': [{'road': r[0], 'total': r[1], 'rectified': int(r[2] or 0)} for r in by_road],
            'by_date': [{'date': str(r[0]), 'total': r[1], 'rectified': int(r[2] or 0)} for r in by_date],
        }), 200

    # ---------------------------------------------------------------- 疑似重复队列

    @app.route('/api/inspection/analysis', methods=['GET'])
    @insp_access
    def insp_analysis():
        """只读分析；不调用建表、更新状态或图片处理。旧 stats 接口保持兼容。"""
        import time
        started = time.monotonic()
        try:
            # Validate before accessing the database, including bounded dates and pagination.
            inspection_period(request.args, datetime.now().date())
            with engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT id, case_date, road, location, problem, dept, result, status "
                    "FROM insp_case ORDER BY case_date, id"
                )).mappings().all()
                data = build_inspection_analysis(rows, request.args, datetime.now().date())
                if 'detail' in data and data['detail']['items']:
                    ids = [r['id'] for r in data['detail']['items']]
                    from sqlalchemy import bindparam
                    photos = conn.execute(text(
                        "SELECT case_id, kind, file_path FROM insp_photo WHERE case_id IN :ids "
                        "ORDER BY case_id, kind, seq"
                    ).bindparams(bindparam('ids', expanding=True)), {'ids': ids}).mappings().all()
                    by_id = {}
                    for p in photos:
                        by_id.setdefault(p['case_id'], []).append(dict(p))
                    for r in data['detail']['items']:
                        r['photos'] = by_id.get(r['id'], [])
            data['generated_at'] = _now()
            data['query_ms'] = round((time.monotonic() - started) * 1000, 1)
            return jsonify(data), 200
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

    @app.route('/api/inspection/dup-candidates', methods=['GET'])
    @insp_access
    def insp_dup_list():
        """取疑似重复清单（默认只看 pending）。"""
        args = request.args
        batch_no = (args.get('batch_no') or '').strip()
        decision = (args.get('decision') or 'pending').strip()
        where, params = ['1=1'], {}
        if batch_no:
            where.append('batch_no = :b')
            params['b'] = batch_no
        if decision and decision != 'all':
            where.append('decision = :d')
            params['d'] = decision
        wsql = ' AND '.join(where)
        with engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT id, batch_no, new_case_json, matched_case_id, match_score, "
                f"       match_reason, decision, decided_by, decided_at, created_at "
                f"FROM insp_dup_candidate WHERE {wsql} ORDER BY id DESC LIMIT 500"
            ), params).fetchall()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r[2])
                except (ValueError, TypeError):
                    payload = {}
                matched = None
                if r[3]:
                    m = conn.execute(text(
                        "SELECT id, case_date, road, location, problem, dept, status "
                        "FROM insp_case WHERE id = :i"), {'i': r[3]}).fetchone()
                    if m:
                        matched = {'id': m[0], 'case_date': str(m[1]), 'road': m[2],
                                   'location': m[3], 'problem': m[4], 'dept': m[5],
                                   'status': m[6]}
                out.append({'id': r[0], 'batch_no': r[1], 'new_case': payload,
                            'matched_case': matched,
                            'match_score': float(r[4]) if r[4] is not None else None,
                            'match_reason': r[5], 'decision': r[6],
                            'decided_by': r[7],
                            'decided_at': str(r[8]) if r[8] else None,
                            'created_at': str(r[9])})
        return jsonify({'items': out}), 200

    @app.route('/api/inspection/dup-candidates/<int:cid>', methods=['POST'])
    @insp_access
    def insp_dup_decide(cid):
        """判定：merged=并入 matched_case_id（照片挂过去）；new=正式插入为新案。"""
        body = request.get_json(silent=True) or {}
        decision = (body.get('decision') or '').strip()
        if decision not in ('merged', 'new'):
            return jsonify({'error': "decision 只能是 merged 或 new"}), 400

        with engine.begin() as conn:
            row = conn.execute(text(
                "SELECT id, batch_no, new_case_json, matched_case_id, decision "
                "FROM insp_dup_candidate WHERE id = :i FOR UPDATE"), {'i': cid}).fetchone()
            if not row:
                return jsonify({'error': '记录不存在'}), 404
            if row[4] != 'pending':
                return jsonify({'error': f'该条已判定过：{row[4]}'}), 409
            try:
                payload = json.loads(row[2])
            except (ValueError, TypeError):
                return jsonify({'error': 'new_case_json 损坏，无法处理'}), 500

            if decision == 'merged':
                target = row[3] or body.get('matched_case_id')
                if not target:
                    return jsonify({'error': 'merged 需要 matched_case_id'}), 400
                # 并案：只回填整改结果与整改图，不改原记录文字与日期
                conn.execute(text(
                    "UPDATE insp_case SET result = COALESCE(NULLIF(:rs, ''), result), "
                    "status = :st, rectified_at = COALESCE(rectified_at, :ra) "
                    "WHERE id = :i"
                ), {'rs': payload.get('result') or '',
                    'st': payload.get('status') or '待整改',
                    'ra': _now() if payload.get('status') == '已整改' else None,
                    'i': target})
                seq_base = conn.execute(text(
                    "SELECT COALESCE(MAX(seq), 0) FROM insp_photo WHERE case_id = :i AND kind = 'rectify'"
                ), {'i': target}).scalar()
                photos = payload.get('photos') or []
                moved = 0
                for p in photos:
                    if p.get('kind') != 'rectify':
                        continue
                    raw = _read_staged_photo(p.get('orig_name') or '')
                    if raw is None:
                        continue
                    seq_base += 1
                    try:
                        abs_path, rel_url = _save_photo(target, 'rectify', seq_base, raw,
                                                        str(conn.execute(text(
                                                            "SELECT case_date FROM insp_case WHERE id = :i"),
                                                            {'i': target}).scalar()))
                        conn.execute(text(
                            "INSERT INTO insp_photo (case_id, kind, file_path, phash, orig_name, seq) "
                            "VALUES (:c, 'rectify', :f, :h, :o, :s)"
                        ), {'c': target, 'f': rel_url, 'h': p.get('phash'),
                            'o': p.get('orig_name'), 's': seq_base})
                        moved += 1
                    except Exception as e:
                        logger.warning(f'[INSP] 并案搬迁照片失败: {e}')
                conn.execute(text(
                    "UPDATE insp_dup_candidate SET decision = 'merged', decided_by = :u, "
                    "decided_at = :ts WHERE id = :i"
                ), {'u': request.user_id, 'ts': _now(), 'i': cid})
                logger.info(f'[INSP] 重复候选 {cid} 并入案件 {target}，搬迁整改图 {moved} 张')
                return jsonify({'ok': True, 'action': 'merged', 'case_id': target,
                                'photos_moved': moved}), 200

            # decision == 'new'：正式入库
            case_date = parse_case_date(payload.get('case_date'))
            result = (payload.get('result') or '').strip()
            status = payload.get('status') or '待整改'
            photos = payload.get('photos') or []
            r = conn.execute(text(
                "INSERT INTO insp_case "
                "(case_date, road, location, problem, dept, dept_raw, result, status, "
                " leader_group, normalized_key, photo_hashes, source_file, source_row, "
                " first_seen_at, rectified_at) "
                "VALUES (:cd, :rd, :lo, :pr, :dp, :dr, :rs, :st, :lg, :nk, :ph, :sf, :sr, :ts, :ra)"
            ), {'cd': case_date, 'rd': payload.get('road') or '',
                'lo': payload.get('location') or '', 'pr': payload.get('problem') or '',
                'dp': payload.get('dept'), 'dr': payload.get('dept_raw'),
                'rs': result, 'st': status, 'lg': payload.get('leader_group'),
                'nk': normalized_key(payload.get('location'), payload.get('problem')),
                'ph': json.dumps([p.get('phash') for p in photos if p.get('phash')],
                                 ensure_ascii=False),
                'sf': payload.get('source_file'), 'sr': payload.get('source_row'),
                'ts': _now(), 'ra': _now() if status == '已整改' else None})
            case_id = r.lastrowid
            saved = 0
            seqs = Counter()
            for p in photos:
                raw = _read_staged_photo(p.get('orig_name') or '')
                if raw is None:
                    continue
                kind = p.get('kind') or 'problem'
                seqs[kind] += 1
                try:
                    abs_path, rel_url = _save_photo(case_id, kind, seqs[kind], raw, case_date,
                                                    p.get('orig_name'))
                    conn.execute(text(
                        "INSERT INTO insp_photo (case_id, kind, file_path, phash, orig_name, seq) "
                        "VALUES (:c, :k, :f, :h, :o, :s)"
                    ), {'c': case_id, 'k': kind, 'f': rel_url, 'h': p.get('phash'),
                        'o': p.get('orig_name'), 's': seqs[kind]})
                    saved += 1
                except Exception as e:
                    logger.warning(f'[INSP] new 判定落盘照片失败: {e}')
            conn.execute(text(
                "UPDATE insp_dup_candidate SET decision = 'new', decided_by = :u, "
                "decided_at = :ts WHERE id = :i"
            ), {'u': request.user_id, 'ts': _now(), 'i': cid})
            logger.info(f'[INSP] 重复候选 {cid} 判为新案 id={case_id}，落图 {saved} 张')
            return jsonify({'ok': True, 'action': 'new', 'case_id': case_id,
                            'photos_saved': saved}), 200

    @app.route('/api/inspection/cases/<int:cid>', methods=['PUT'])
    @insp_access
    def insp_case_update(cid):
        """回填/更正整改结果。只改 result/status/rectified_at，不改位置、问题、
        责任单位、日期与来源行（那些是巡查现场的原始记录，改了就对不上上游表）。
        status 仍走 judge_status 两值化——处理结果命中拒绝口径时即使传已整改也按待整改。"""
        body = request.get_json(silent=True) or {}
        if 'result' not in body and 'status' not in body:
            return jsonify({'error': '没有要更新的字段（result / status）'}), 400
        result = (body.get('result') or '').strip()
        with engine.begin() as conn:
            row = conn.execute(text(
                "SELECT id, result FROM insp_case WHERE id = :i"), {'i': cid}).fetchone()
            if not row:
                return jsonify({'error': '案件不存在'}), 404
            if 'result' in body:
                final_result = result
            else:
                final_result = row[1] or ''
            status = judge_status(body.get('status') or '待整改', final_result)
            conn.execute(text(
                "UPDATE insp_case SET result = :rs, status = :st, "
                "rectified_at = :ra WHERE id = :i"
            ), {'rs': final_result, 'st': status,
                'ra': _now() if status == '已整改' else None, 'i': cid})
        logger.info(f'[INSP] 案件 {cid} 回填整改：status={status}')
        return jsonify({'ok': True, 'id': cid, 'status': status, 'result': final_result}), 200

    # ---------------------------------------------------------------- 导出

    EXPORT_HEADERS = ['序号', '日期', '道路', '具体位置', '问题', '责任单位',
                      '处理结果', '整改状态', '问题图片', '整改图片']

    @app.route('/api/inspection/export', methods=['GET'])
    @insp_access
    def insp_export():
        """导出台账 xlsx。版式沿用《问题处置汇总总台账》：
        第1行标题（不带日期范围）、第2行表头；默认写图片文件名，
        ?with_images=1 时嵌入缩略图。日期输出"10月21日"。"""
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.utils import get_column_letter

        args = request.args
        with_images = (args.get('with_images') or '').strip() == '1'
        date_from = (args.get('date_from') or '').strip()
        date_to = (args.get('date_to') or '').strip()
        dept = (args.get('dept') or '').strip()
        status = (args.get('status') or '').strip()

        where, params = ['1=1'], {}
        if date_from:
            where.append('case_date >= :df')
            params['df'] = date_from
        if date_to:
            where.append('case_date <= :dt')
            params['dt'] = date_to
        if dept:
            where.append('dept = :dp')
            params['dp'] = dept
        if status:
            where.append('status = :st')
            params['st'] = status
        wsql = ' AND '.join(where)

        with engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT id, case_date, road, location, problem, dept, result, status "
                f"FROM insp_case WHERE {wsql} ORDER BY case_date, id"
            ), params).fetchall()
            photos_by_case = {}
            if rows:
                ids = [r[0] for r in rows]
                prows = conn.execute(text(
                    "SELECT case_id, kind, file_path, seq FROM insp_photo "
                    "WHERE case_id IN :ids ORDER BY case_id, kind, seq"
                ).bindparams(__import__('sqlalchemy').bindparam('ids', expanding=True)),
                    {'ids': ids}).fetchall()
                for cid, kind, fp, seq in prows:
                    photos_by_case.setdefault(cid, []).append((kind, fp, seq))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '汇总台账'

        title_font = Font(name='宋体', size=16, bold=True)
        head_font = Font(name='宋体', size=11, bold=True, color='FFFFFF')
        body_font = Font(name='宋体', size=10)
        head_fill = PatternFill('solid', fgColor='4472C4')
        thin = Side(style='thin', color='999999')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        left_wrap = Alignment(horizontal='left', vertical='center', wrap_text=True)

        ncol = len(EXPORT_HEADERS)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        tcell = ws.cell(row=1, column=1, value='领导巡查发现问题及各部门处置情况汇总台账')
        tcell.font = title_font
        tcell.alignment = center
        ws.row_dimensions[1].height = 32

        for i, h in enumerate(EXPORT_HEADERS, start=1):
            c = ws.cell(row=2, column=i, value=h)
            c.font = head_font
            c.fill = head_fill
            c.alignment = center
            c.border = border
        ws.row_dimensions[2].height = 24

        widths = [6, 12, 14, 34, 34, 12, 30, 10, 16, 16]
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

        tmp_imgs = []
        r_out = 3
        for idx, row in enumerate(rows, start=1):
            cid, case_date, road, location, problem, dept, result, st = row
            try:
                d = datetime.strptime(str(case_date), '%Y-%m-%d')
                date_cn = f'{d.month}月{d.day}日'
            except ValueError:
                date_cn = str(case_date)
            pphs = photos_by_case.get(cid, [])
            prob = [p for p in pphs if p[0] == 'problem']
            rect = [p for p in pphs if p[0] == 'rectify']

            values = [idx, date_cn, road, location, problem,
                      dept or '', result or '', st,
                      '、'.join(os.path.basename(p[1]) for p in prob),
                      '、'.join(os.path.basename(p[1]) for p in rect)]
            for ci, v in enumerate(values, start=1):
                c = ws.cell(row=r_out, column=ci, value=v)
                c.font = body_font
                c.border = border
                c.alignment = left_wrap if ci in (4, 5, 7, 9, 10) else center
            ws.row_dimensions[r_out].height = 42

            if with_images:
                # 问题图贴第9列、整改图贴第10列，取每类第一张缩略图
                for col, kindlist in ((9, prob), (10, rect)):
                    if not kindlist:
                        continue
                    rel = kindlist[0][1]
                    abs_path = os.path.join(UPLOAD_DIR, rel.lstrip('/uploads/'))
                    if not os.path.isfile(abs_path):
                        continue
                    try:
                        im = Image.open(abs_path)
                        im.load()
                        im.thumbnail((120, 120), Image.LANCZOS)
                        tmp = os.path.join(STAGE_DIR, f'_xl_{uuid.uuid4().hex}.png')
                        im.convert('RGB').save(tmp, 'PNG')
                        tmp_imgs.append(tmp)
                        ximg = XLImage(tmp)
                        ws.add_image(ximg, f'{get_column_letter(col)}{r_out}')
                    except Exception as e:
                        logger.warning(f'[INSP] 导出嵌图失败 {rel}: {e}')
            r_out += 1

        ws.freeze_panes = 'A3'
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        for t in tmp_imgs:
            try:
                os.remove(t)
            except OSError:
                pass
        fname = f"巡查问题台账_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return Response(
            buf.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition':
                     "attachment; filename*=UTF-8''" + quote(fname)},
        )

    logger.info('[INSP] 巡查问题台账路由注册完成')
