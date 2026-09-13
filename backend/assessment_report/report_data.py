# -*- coding: utf-8 -*-
"""考核月报数据组装：从 case_data + assessment_manual_* 汇总生成月报所需的全部数据"""
import calendar
import logging
from datetime import date, datetime

from sqlalchemy import text

logger = logging.getLogger(__name__)

try:
    from backend.assessment_routes import _calculate_scores, _group_departments
except ImportError:
    from assessment_routes import _calculate_scores, _group_departments

try:
    from backend.assessment_manual_routes import (
        load_external_data_from_db, load_exempt_for_batch, calc_to_case_names,
    )
except ImportError:
    from assessment_manual_routes import (
        load_external_data_from_db, load_exempt_for_batch, calc_to_case_names,
    )

# 期号基数：2021年5月 = 总第1期（2026年7月 = 总第63期 倒推）
ISSUE_BASE_YEAR = 2021
ISSUE_BASE_MONTH = 5

ORG_NAME = '运城市智慧城市管理平台服务中心'

# 来源渠道分组（图1）：采集员上报→采集上报，视频上报→视频上报，其余归入公众诉求子明细
SRC_COLLECTOR = '采集上报'
SRC_VIDEO = '视频上报'
SRC_PUBLIC = '公众诉求'

# 处置情况表行顺序：(分组键, 显示名)
DISPOSAL_ROWS = [
    ('执法队', '城市管理综合行政执法队'),
    ('市容秩序科', '市容秩序科'),
    ('排水服务中心', '排水服务中心'),
    ('城市节约用水中心', '城市节约用水中心'),
    ('建筑垃圾资源利用服务中心', '建筑垃圾资源利用服务中心'),
    ('市容环卫中心', '市容环卫中心'),
    ('园林绿化服务中心', '园林绿化服务中心'),
    ('市集中供热供气服务中心', '市集中供热供气服务中心'),
    ('市政公用服务中心', '市政公用服务中心'),
]

# 市政考核表行顺序（显示名映射）
MUNICIPAL_ROWS = [
    ('城市照明部', '城市照明部'),
    ('排水服务中心', '排水服务中心'),
    ('市政设施维护部', '市政维护部'),
    ('应急执法分队', '应急执法分队'),
]


def issue_no(batch: str):
    """返回 (年内第N期, 总第M期)"""
    y, m = int(batch[:4]), int(batch[4:6])
    total = (y - ISSUE_BASE_YEAR) * 12 + (m - ISSUE_BASE_MONTH) + 1
    return m, total


def month_bounds(batch: str):
    """返回 (首日, 末日, 下月1日) 的 date"""
    y, m = int(batch[:4]), int(batch[4:6])
    last = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last)
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return start, end, date(ny, nm, 1)


def _fmt_issue_date(d: date) -> str:
    return f'{d.year}年{d.month}月{d.day}日'


def collect_report_data(engine, batch: str) -> dict:
    """汇总月报全部数据。"""
    start, end, next_month_1 = month_bounds(batch)
    issue_m, issue_total = issue_no(batch)

    with engine.connect() as conn:
        # 1. 按部门统计（应结案/结案/超期/延期/返工）
        dept_rows = conn.execute(text("""
            SELECT
                department,
                COUNT(*) as total,
                SUM(CASE WHEN stage = '[办结]' THEN 1 ELSE 0 END) as closed,
                SUM(CASE WHEN is_overtime = 1 THEN 1 ELSE 0 END) as overtime,
                SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) as delayed_cnt,
                SUM(CASE WHEN is_rework = 1 THEN 1 ELSE 0 END) as rework
            FROM case_data
            WHERE upload_batch = :batch
            GROUP BY department
        """), {'batch': batch}).fetchall()
        departments = {}
        for r in dept_rows:
            departments[r[0] or '未知'] = {
                'total': int(r[1]), 'closed': int(r[2]),
                'overtime': int(r[3]), 'delayed': int(r[4]), 'rework': int(r[5]),
            }

        # 2. 来源渠道分布（图1）
        src_rows = conn.execute(text("""
            SELECT source, COUNT(*) FROM case_data
            WHERE upload_batch = :batch
            GROUP BY source ORDER BY 2 DESC
        """), {'batch': batch}).fetchall()
        src_groups = {SRC_COLLECTOR: 0, SRC_VIDEO: 0, SRC_PUBLIC: 0}
        src_subs = []
        for r in src_rows:
            name, cnt = r[0] or '其他', int(r[1])
            if name == '采集员上报':
                src_groups[SRC_COLLECTOR] += cnt
            elif name == '视频上报':
                src_groups[SRC_VIDEO] += cnt
            else:
                src_groups[SRC_PUBLIC] += cnt
                src_subs.append([name, cnt])

        # 3. 人工录入数据（extra_note 为后补列，旧库无该列时回退）
        monthly = None
        try:
            monthly = conn.execute(text(
                "SELECT assessment_case_cnt, work_note, extra_note "
                "FROM assessment_manual_monthly WHERE batch = :b"
            ), {'b': batch}).fetchone()
        except Exception:
            monthly = conn.execute(text(
                "SELECT assessment_case_cnt, work_note, NULL "
                "FROM assessment_manual_monthly WHERE batch = :b"
            ), {'b': batch}).fetchone()
        received = int(monthly[0]) if monthly and monthly[0] is not None else None
        work_note = (monthly[1] or '') if monthly else ''
        extra_note = (monthly[2] or '') if monthly else ''

        collector_cnt = 0
        try:
            r = conn.execute(text(
                "SELECT self_dispose_cnt FROM assessment_manual_collector WHERE batch = :b"
            ), {'b': batch}).fetchone()
            collector_cnt = int(r[0]) if r and r[0] is not None else 0
        except Exception as e:
            logger.warning(f'读取采集员汇总失败: {e}')

        garbage_cnt = 0
        garbage_by_district = {}
        try:
            for r in conn.execute(text(
                "SELECT district_name, piece_count FROM assessment_manual_garbage WHERE batch = :b"
            ), {'b': batch}).fetchall():
                garbage_cnt += int(r[1] or 0)
                garbage_by_district[r[0]] = int(r[1] or 0)
        except Exception as e:
            logger.warning(f'读取单体垃圾失败: {e}')

        special_total = 0
        special_breakdown = []
        try:
            for r in conn.execute(text("""
                SELECT minor_name, SUM(piece_cnt) FROM assessment_manual_special_detail
                WHERE batch = :b GROUP BY minor_name ORDER BY 2 DESC
            """), {'b': batch}).fetchall():
                special_total += int(r[1] or 0)
                special_breakdown.append([r[0], int(r[1] or 0)])
        except Exception as e:
            logger.warning(f'读取专项采集明细失败: {e}')

        ledger = {'pending': [], 'backlog': [], 'praise': []}
        pending_by_unit, backlog_by_unit = {}, {}
        try:
            for r in conn.execute(text("""
                SELECT ledger_type, unit_name, dept_name, source, piece_cnt, content, reason, deadline
                FROM assessment_manual_ledger WHERE batch = :b
                ORDER BY id
            """), {'b': batch}).fetchall():
                item = {
                    'unit_name': r[1] or '', 'dept_name': r[2] or '',
                    'source': r[3] or '', 'piece_cnt': int(r[4]) if r[4] is not None else None,
                    'content': r[5] or '', 'reason': r[6] or '',
                    'deadline': r[7].strftime('%Y-%m-%d') if r[7] else '',
                }
                ltype = r[0]
                if ltype in ledger:
                    ledger[ltype].append(item)
                if ltype == 'pending' and item['unit_name']:
                    pending_by_unit[item['unit_name']] = pending_by_unit.get(item['unit_name'], 0) + (item['piece_cnt'] or 0)
                if ltype == 'backlog' and item['unit_name']:
                    backlog_by_unit[item['unit_name']] = backlog_by_unit.get(item['unit_name'], 0) + (item['piece_cnt'] or 0)
        except Exception as e:
            logger.warning(f'读取台账失败: {e}')

    # 4. 考核计分（与 /api/assessment/calculate 同一套逻辑）
    scoring_depts = dict(departments)
    missing = {}
    try:
        external, missing = load_external_data_from_db(engine, batch)
    except Exception as e:
        logger.warning(f'读取人工分值失败: {e}')
        external, missing = {}, {}
    exemptions = []
    try:
        exemptions = load_exempt_for_batch(engine, batch)
    except Exception as e:
        logger.warning(f'读取豁免期失败: {e}')
    for it in exemptions:
        for calc_name in it.get('unit_names') or [it.get('unit_name')]:
            for case_name in calc_to_case_names(calc_name):
                scoring_depts.pop(case_name, None)
    results = _calculate_scores(scoring_depts, external, missing=missing)
    for it in exemptions:
        for calc_name in it.get('unit_names') or [it.get('unit_name')]:
            results[calc_name] = {
                'total': 0, 'closed': 0, 'overtime': 0, 'delayed': 0, 'rework': 0,
                'system_score': None, 'final_score': None,
                'exempt': True, 'exempt_note': it['note'],
                'missing_fields': [], 'is_complete': False,
            }

    # 5. 处置情况表（按中心汇总，全量部门，不受豁免影响）
    groups = _group_departments(departments)
    disposal = []
    grand_total = sum(d['total'] for d in departments.values())
    for key, display in DISPOSAL_ROWS:
        st = groups.get(key)
        if not st or st['total'] == 0:
            continue
        disposal.append({
            'name': display, 'total': st['total'], 'closed': st['closed'],
            'rate': st['closed'] / st['total'] * 100 if st['total'] else 0,
            'share': st['total'] / grand_total * 100 if grand_total else 0,
        })
    other = groups.get('其他')
    if other and other['total'] > 0:
        disposal.append({
            'name': '其他', 'total': other['total'], 'closed': other['closed'],
            'rate': other['closed'] / other['total'] * 100, 'share': other['total'] / grand_total * 100,
        })
    disposal_total = {
        'total': grand_total,
        'closed': sum(d['closed'] for d in departments.values()),
    }
    disposal_total['rate'] = disposal_total['closed'] / disposal_total['total'] * 100 if disposal_total['total'] else 0

    batch_total = sum(d['total'] for d in departments.values())
    batch_closed = sum(d['closed'] for d in departments.values())

    no_assess_total = collector_cnt + garbage_cnt + special_total

    return {
        'batch': batch,
        'org_name': ORG_NAME,
        'period': f'{start.year}年{start.month}月1日至{start.month}月{end.day}日',
        'issue': {'year': start.year, 'no': issue_m, 'total': issue_total,
                  'date_str': _fmt_issue_date(next_month_1)},
        'overview': {
            'received': received,               # 受理数 = 录入的当月考核案件数
            'batch_total': batch_total,          # 应结案
            'batch_closed': batch_closed,        # 结案（stage=[办结]）
            'close_rate': batch_closed / batch_total * 100 if batch_total else 0,
            'self_dispose': collector_cnt,
            'garbage_cnt': garbage_cnt,
            'special_total': special_total,
            'special_breakdown': special_breakdown,
            'no_assess_total': no_assess_total,
        },
        'sources': {'groups': src_groups, 'subs': src_subs,
                    'total': sum(src_groups.values())},
        'disposal': {'rows': disposal, 'total': disposal_total},
        'scores': results,
        'missing': missing,
        'exemptions': exemptions,
        'ledger': ledger,
        'pending_by_unit': pending_by_unit,
        'backlog_by_unit': backlog_by_unit,
        'garbage_by_district': garbage_by_district,
        'work_note': work_note,
        'extra_note': extra_note,
    }


def work_note_lines(work_note: str):
    """工作动态按行拆分，保留录入内容中的序号和标点。"""
    lines = [ln.strip() for ln in (work_note or '').splitlines() if ln.strip()]
    return lines
