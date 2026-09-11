# -*- coding: utf-8 -*-
"""考核人工数据录入 + 计算读库 + 结果落库。

安全约定：
- 仅 CREATE TABLE IF NOT EXISTS 新表，不改 case_data 等既有业务表
- 不 DROP 任何业务数据表
- 保存接口仅写 assessment_manual_* / assessment_result / dict_unit
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from flask import request, jsonify
from sqlalchemy import text

logger = logging.getLogger(__name__)

try:
    from common import protected as _protected, admin_required as _admin_required
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required

# 环卫片区（考核部门名）与采集员片区对应
SANITATION_REGION_MAP = {
    '东': '环卫东片区',
    '西': '环卫西片区',
    '南': '环卫南片区',
    '北': '环卫北片区',
    '中': '环卫中片区',
}
REGION_KEYS = ['东', '西', '南', '北', '中']

# 考核单位列表（与 assessment 计算逻辑对齐）
DISPATCH_TEAMS = [
    '姚孟执法分队', '大渠执法分队', '西城执法分队', '南城执法分队',
    '北城执法分队', '中城执法分队', '东城执法分队', '安邑执法分队',
]
# 组织架构中的名称 → 计算用名称
ORG_DISPATCH_TO_CALC = {
    '执法东片区': '东城执法分队',
    '执法西片区': '西城执法分队',
    '执法南片区': '南城执法分队',
    '执法北片区': '北城执法分队',
    '执法中片区': '中城执法分队',
    '执法大渠分队': '大渠执法分队',
    '执法姚孟分队': '姚孟执法分队',
    '执法安邑分队': '安邑执法分队',
}

GARDEN_DISTRICTS = [
    '园林东片区', '园林西片区', '园林南片区', '园林北片区', '园林中片区',
]
PARKS = [
    '人民公园', '体育公园', '南风广场', '天逸公园', '圣惠公园', '禹都公园', '航天公园',
]
MUNICIPAL_UNITS = [
    '城市照明部', '市政设施维护部', '排水服务中心', '应急执法分队',
]
# 组织架构市政部名 → 计算用
ORG_MUNICIPAL = {
    '城市照明部': '城市照明部',
    '市政设施维护部': '市政设施维护部',
}

CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS assessment_manual_monthly (
        batch VARCHAR(10) NOT NULL PRIMARY KEY COMMENT '年月如202608',
        assessment_case_cnt INT NULL COMMENT '当月考核案件数(人工口径)',
        work_note MEDIUMTEXT NULL COMMENT '工作动态',
        updated_by VARCHAR(50) NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考核人工-月度总项'
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_manual_score (
        id INT AUTO_INCREMENT PRIMARY KEY,
        batch VARCHAR(10) NOT NULL,
        unit_name VARCHAR(100) NOT NULL,
        unit_type VARCHAR(30) NOT NULL COMMENT 'dispatch/sanitation/garden/garden_park/municipal',
        score_type VARCHAR(20) NOT NULL COMMENT 'team/street/center/extra',
        score_value DECIMAL(10,3) NOT NULL,
        updated_by VARCHAR(50) NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_batch_unit_type (batch, unit_name, score_type),
        KEY idx_batch (batch)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考核人工-分值'
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_manual_garbage (
        batch VARCHAR(10) NOT NULL,
        region VARCHAR(10) NOT NULL COMMENT '东/西/南/北/中',
        district_name VARCHAR(50) NOT NULL COMMENT '环卫片区部门名',
        piece_count INT NOT NULL DEFAULT 0 COMMENT '单体垃圾件数',
        updated_by VARCHAR(50) NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (batch, region)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考核人工-单体垃圾件数'
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_manual_collector (
        batch VARCHAR(10) NOT NULL PRIMARY KEY,
        self_dispose_cnt INT NOT NULL DEFAULT 0 COMMENT '采集员自行处置数',
        updated_by VARCHAR(50) NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考核人工-采集员汇总'
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_manual_special_detail (
        id INT AUTO_INCREMENT PRIMARY KEY,
        batch VARCHAR(10) NOT NULL,
        major_name VARCHAR(100) NOT NULL,
        minor_name VARCHAR(100) NOT NULL,
        piece_cnt INT NOT NULL DEFAULT 0,
        updated_by VARCHAR(50) NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_batch (batch)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考核人工-专项采集明细'
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_manual_ledger (
        id INT AUTO_INCREMENT PRIMARY KEY,
        batch VARCHAR(10) NOT NULL,
        ledger_type VARCHAR(20) NOT NULL COMMENT 'pending/backlog/praise',
        unit_name VARCHAR(100) NULL,
        dept_name VARCHAR(100) NULL,
        source VARCHAR(100) NULL,
        piece_cnt INT NULL,
        content TEXT,
        reason TEXT,
        deadline DATE NULL,
        updated_by VARCHAR(50) NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_batch_type (batch, ledger_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考核人工-台账(挂账/积压/表扬)'
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_result (
        id INT AUTO_INCREMENT PRIMARY KEY,
        batch VARCHAR(10) NOT NULL,
        unit_name VARCHAR(100) NOT NULL,
        unit_type VARCHAR(30) NOT NULL DEFAULT 'other',
        total INT NULL,
        closed INT NULL,
        overtime INT NULL,
        delayed_cnt INT NULL,
        rework INT NULL,
        system_score DECIMAL(10,3) NULL,
        team_score DECIMAL(10,3) NULL,
        street_score DECIMAL(10,3) NULL,
        garbage_score DECIMAL(10,3) NULL,
        center_score DECIMAL(10,3) NULL,
        extra_points DECIMAL(10,3) NULL,
        final_score DECIMAL(10,3) NULL,
        missing_fields VARCHAR(500) NULL,
        is_complete TINYINT(1) DEFAULT 0,
        calc_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        calc_by VARCHAR(50) NULL,
        UNIQUE KEY uk_batch_unit (batch, unit_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考核计算结果(同月覆盖)'
    """,
]


def _now_user():
    return getattr(request, 'username', None) or 'admin'


def ensure_manual_tables(engine):
    with engine.begin() as conn:
        for sql in CREATE_TABLES:
            conn.execute(text(sql))
    logger.info('assessment_manual tables ensured')


def register_assessment_manual_routes(app, engine=None, protected=None, admin_required=None):
    protected = protected or _protected
    admin_required = admin_required or _admin_required

    if engine:
        try:
            ensure_manual_tables(engine)
        except Exception as e:
            logger.warning(f'人工分值表创建失败: {e}')

    # ---------- 单位字典 ----------
    @app.route('/api/assessment/units', methods=['GET'])
    @protected
    def assessment_units():
        """单位列表。可选 type=dispatch|sanitation|garden|park|municipal|bureau_dept|..."""
        unit_type = (request.args.get('type') or '').strip()
        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500
            sql = "SELECT id, unit_name, unit_code, unit_type, parent_id FROM dict_unit WHERE is_active=1"
            params = {}
            if unit_type:
                sql += " AND unit_type = :t"
                params['t'] = unit_type
            sql += " ORDER BY sort_order, id"
            with engine.connect() as conn:
                rows = conn.execute(text(sql), params).fetchall()
            return jsonify({
                'success': True,
                'units': [
                    {'id': r[0], 'unit_name': r[1], 'unit_code': r[2], 'unit_type': r[3], 'parent_id': r[4]}
                    for r in rows
                ],
            })
        except Exception as e:
            logger.error(f'获取单位失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

    # ---------- 考核单位模板（录入页用） ----------
    @app.route('/api/assessment/manual/template', methods=['GET'])
    @protected
    def assessment_manual_template():
        """录入页需要的固定单位行（与计算口径一致）"""
        return jsonify({
            'success': True,
            'dispatch_teams': DISPATCH_TEAMS,
            'sanitation_districts': list(SANITATION_REGION_MAP.values()),
            'garden_districts': GARDEN_DISTRICTS,
            'parks': PARKS,
            'municipal_units': MUNICIPAL_UNITS,
            'garbage_regions': [
                {'region': r, 'district': SANITATION_REGION_MAP[r]} for r in REGION_KEYS
            ],
        })

    # ---------- 读取当月全部人工数据 ----------
    @app.route('/api/assessment/manual', methods=['GET'])
    @protected
    def assessment_manual_get():
        batch = (request.args.get('batch') or '').strip()
        if not batch:
            return jsonify({'success': False, 'error': '请指定月份'}), 400
        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500
            out = {
                'batch': batch,
                'monthly': None,
                'scores': [],
                'garbage': [],
                'collector': None,
                'special_details': [],
                'ledgers': [],
            }
            with engine.connect() as conn:
                r = conn.execute(text(
                    "SELECT batch, assessment_case_cnt, work_note, updated_by, updated_at "
                    "FROM assessment_manual_monthly WHERE batch=:b"
                ), {'b': batch}).fetchone()
                if r:
                    out['monthly'] = {
                        'batch': r[0], 'assessment_case_cnt': r[1],
                        'work_note': r[2], 'updated_by': r[3],
                        'updated_at': str(r[4]) if r[4] else None,
                    }

                rows = conn.execute(text(
                    "SELECT unit_name, unit_type, score_type, score_value FROM assessment_manual_score WHERE batch=:b"
                ), {'b': batch}).fetchall()
                out['scores'] = [
                    {'unit_name': x[0], 'unit_type': x[1], 'score_type': x[2], 'score_value': float(x[3])}
                    for x in rows
                ]

                rows = conn.execute(text(
                    "SELECT region, district_name, piece_count FROM assessment_manual_garbage WHERE batch=:b"
                ), {'b': batch}).fetchall()
                out['garbage'] = [
                    {'region': x[0], 'district_name': x[1], 'piece_count': int(x[2])}
                    for x in rows
                ]

                r = conn.execute(text(
                    "SELECT batch, self_dispose_cnt, updated_by FROM assessment_manual_collector WHERE batch=:b"
                ), {'b': batch}).fetchone()
                if r:
                    out['collector'] = {
                        'batch': r[0], 'self_dispose_cnt': int(r[1] or 0), 'updated_by': r[2]
                    }

                rows = conn.execute(text(
                    "SELECT id, major_name, minor_name, piece_cnt FROM assessment_manual_special_detail WHERE batch=:b ORDER BY id"
                ), {'b': batch}).fetchall()
                out['special_details'] = [
                    {'id': x[0], 'major_name': x[1], 'minor_name': x[2], 'piece_cnt': int(x[3])}
                    for x in rows
                ]

                rows = conn.execute(text(
                    "SELECT id, ledger_type, unit_name, dept_name, source, piece_cnt, content, reason, deadline "
                    "FROM assessment_manual_ledger WHERE batch=:b ORDER BY id"
                ), {'b': batch}).fetchall()
                out['ledgers'] = [
                    {
                        'id': x[0], 'ledger_type': x[1], 'unit_name': x[2], 'dept_name': x[3],
                        'source': x[4], 'piece_cnt': x[5], 'content': x[6], 'reason': x[7],
                        'deadline': str(x[8]) if x[8] else None,
                    }
                    for x in rows
                ]

            # 派生
            special_sum = sum(d['piece_cnt'] for d in out['special_details'])
            garbage_sum = sum(g['piece_count'] for g in out['garbage'])
            self_d = out['collector']['self_dispose_cnt'] if out['collector'] else 0
            out['derived'] = {
                'special_summary': special_sum,
                'garbage_total': garbage_sum,
                'no_assess_total': garbage_sum + self_d + special_sum,
            }
            return jsonify({'success': True, **out})
        except Exception as e:
            logger.error(f'读取人工数据失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

    # ---------- 保存：月度总项 ----------
    @app.route('/api/assessment/manual/monthly', methods=['PUT', 'POST'])
    @admin_required
    def assessment_manual_save_monthly():
        data = request.get_json(silent=True) or {}
        batch = (data.get('batch') or '').strip()
        if not batch:
            return jsonify({'success': False, 'error': '请指定月份'}), 400
        cnt = data.get('assessment_case_cnt')
        work_note = data.get('work_note')
        try:
            cnt_i = int(cnt) if cnt is not None and cnt != '' else None
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': '当月考核案件数须为整数'}), 400
        user = _now_user()
        with engine.begin() as conn:
            conn.execute(text(
                """INSERT INTO assessment_manual_monthly (batch, assessment_case_cnt, work_note, updated_by)
                   VALUES (:b, :c, :w, :u)
                   ON DUPLICATE KEY UPDATE assessment_case_cnt=VALUES(assessment_case_cnt),
                     work_note=VALUES(work_note), updated_by=VALUES(updated_by)"""
            ), {'b': batch, 'c': cnt_i, 'w': work_note, 'u': user})
        return jsonify({'success': True})

    # ---------- 保存：分值（整组替换某 unit_type） ----------
    @app.route('/api/assessment/manual/scores', methods=['PUT', 'POST'])
    @admin_required
    def assessment_manual_save_scores():
        """body: { batch, scores: [{unit_name, unit_type, score_type, score_value}] }
        按 batch + unit_type 整组替换，或 scores 内出现的 unit_type 组替换。
        """
        data = request.get_json(silent=True) or {}
        batch = (data.get('batch') or '').strip()
        scores = data.get('scores') or []
        if not batch:
            return jsonify({'success': False, 'error': '请指定月份'}), 400
        if not isinstance(scores, list):
            return jsonify({'success': False, 'error': 'scores 须为数组'}), 400
        user = _now_user()
        types = sorted({s.get('unit_type') for s in scores if s.get('unit_type')})
        try:
            with engine.begin() as conn:
                for ut in types:
                    conn.execute(text(
                        "DELETE FROM assessment_manual_score WHERE batch=:b AND unit_type=:t"
                    ), {'b': batch, 't': ut})
                for s in scores:
                    ut = (s.get('unit_type') or '').strip()
                    un = (s.get('unit_name') or '').strip()
                    st = (s.get('score_type') or '').strip()
                    if not (ut and un and st):
                        continue
                    try:
                        val = float(s.get('score_value'))
                    except (TypeError, ValueError):
                        return jsonify({'success': False, 'error': f'{un}/{st} 分值无效'}), 400
                    conn.execute(text(
                        """INSERT INTO assessment_manual_score
                           (batch, unit_name, unit_type, score_type, score_value, updated_by)
                           VALUES (:b,:u,:t,:st,:v,:by)"""
                    ), {'b': batch, 'u': un, 't': ut, 'st': st, 'v': val, 'by': user})
            return jsonify({'success': True, 'replaced_types': types})
        except Exception as e:
            logger.error(f'保存分值失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

    # ---------- 保存：采集员块 ----------
    @app.route('/api/assessment/manual/collector', methods=['PUT', 'POST'])
    @admin_required
    def assessment_manual_save_collector():
        """body: { batch, garbage: {东:n,...}, self_dispose_cnt, special_details: [{major,minor,cnt}] }"""
        data = request.get_json(silent=True) or {}
        batch = (data.get('batch') or '').strip()
        if not batch:
            return jsonify({'success': False, 'error': '请指定月份'}), 400
        garbage = data.get('garbage') or {}
        self_d = data.get('self_dispose_cnt')
        details = data.get('special_details') or []
        try:
            self_i = int(self_d) if self_d is not None and self_d != '' else 0
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': '自行处置数须为整数'}), 400
        user = _now_user()
        try:
            with engine.begin() as conn:
                for r in REGION_KEYS:
                    dist = SANITATION_REGION_MAP[r]
                    raw = garbage.get(r, garbage.get(dist, 0))
                    try:
                        n = int(raw) if raw is not None and raw != '' else 0
                    except (TypeError, ValueError):
                        return jsonify({'success': False, 'error': f'{r}片区件数无效'}), 400
                    if n < 0:
                        return jsonify({'success': False, 'error': f'{r}片区件数不能为负'}), 400
                    conn.execute(text(
                        """INSERT INTO assessment_manual_garbage
                           (batch, region, district_name, piece_count, updated_by)
                           VALUES (:b,:r,:d,:c,:u)
                           ON DUPLICATE KEY UPDATE piece_count=VALUES(piece_count),
                             district_name=VALUES(district_name), updated_by=VALUES(updated_by)"""
                    ), {'b': batch, 'r': r, 'd': dist, 'c': n, 'u': user})

                conn.execute(text(
                    """INSERT INTO assessment_manual_collector (batch, self_dispose_cnt, updated_by)
                       VALUES (:b,:c,:u)
                       ON DUPLICATE KEY UPDATE self_dispose_cnt=VALUES(self_dispose_cnt), updated_by=VALUES(updated_by)"""
                ), {'b': batch, 'c': self_i, 'u': user})

                conn.execute(text("DELETE FROM assessment_manual_special_detail WHERE batch=:b"), {'b': batch})
                for d in details:
                    major = (d.get('major_name') or d.get('major') or '').strip()
                    minor = (d.get('minor_name') or d.get('minor') or '').strip()
                    try:
                        cnt = int(d.get('piece_cnt', d.get('cnt', 0)) or 0)
                    except (TypeError, ValueError):
                        return jsonify({'success': False, 'error': '专项明细件数无效'}), 400
                    if not major or not minor:
                        continue
                    conn.execute(text(
                        """INSERT INTO assessment_manual_special_detail
                           (batch, major_name, minor_name, piece_cnt, updated_by)
                           VALUES (:b,:ma,:mi,:c,:u)"""
                    ), {'b': batch, 'ma': major, 'mi': minor, 'c': cnt, 'u': user})
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f'保存采集员数据失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

    # ---------- 保存：台账 ----------
    @app.route('/api/assessment/manual/ledgers', methods=['PUT', 'POST'])
    @admin_required
    def assessment_manual_save_ledgers():
        """body: { batch, ledger_type, items: [...] } 整组替换该 type"""
        data = request.get_json(silent=True) or {}
        batch = (data.get('batch') or '').strip()
        ltype = (data.get('ledger_type') or '').strip()
        items = data.get('items') or []
        if not batch or not ltype:
            return jsonify({'success': False, 'error': '请指定月份和台账类型'}), 400
        if ltype not in ('pending', 'backlog', 'praise'):
            return jsonify({'success': False, 'error': '台账类型无效'}), 400
        user = _now_user()
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM assessment_manual_ledger WHERE batch=:b AND ledger_type=:t"
                ), {'b': batch, 't': ltype})
                for it in items:
                    try:
                        cnt = it.get('piece_cnt')
                        cnt_i = int(cnt) if cnt is not None and cnt != '' else None
                    except (TypeError, ValueError):
                        return jsonify({'success': False, 'error': '数量须为整数'}), 400
                    conn.execute(text(
                        """INSERT INTO assessment_manual_ledger
                           (batch, ledger_type, unit_name, dept_name, source, piece_cnt, content, reason, deadline, updated_by)
                           VALUES (:b,:t,:u,:d,:s,:c,:ct,:r,:dl,:by)"""
                    ), {
                        'b': batch, 't': ltype,
                        'u': (it.get('unit_name') or '') or None,
                        'd': (it.get('dept_name') or '') or None,
                        's': (it.get('source') or '') or None,
                        'c': cnt_i,
                        'ct': it.get('content'),
                        'r': it.get('reason'),
                        'dl': it.get('deadline') or None,
                        'by': user,
                    })
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f'保存台账失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

    # ---------- 一次性保存全部（录入页总保存） ----------
    @app.route('/api/assessment/manual/save-all', methods=['PUT', 'POST'])
    @admin_required
    def assessment_manual_save_all():
        data = request.get_json(silent=True) or {}
        batch = (data.get('batch') or '').strip()
        if not batch:
            return jsonify({'success': False, 'error': '请指定月份'}), 400
        user = _now_user()
        monthly = data.get('monthly') or {}
        scores = data.get('scores') or []
        garbage = data.get('garbage') or {}
        self_d = data.get('self_dispose_cnt')
        details = data.get('special_details') or []
        ledgers = data.get('ledgers') or {}  # {pending:[], backlog:[], praise:[]}

        try:
            self_i = int(self_d) if self_d is not None and self_d != '' else 0
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': '自行处置数须为整数'}), 400

        try:
            with engine.begin() as conn:
                # monthly
                cnt = monthly.get('assessment_case_cnt')
                try:
                    cnt_i = int(cnt) if cnt is not None and cnt != '' else None
                except (TypeError, ValueError):
                    return jsonify({'success': False, 'error': '当月考核案件数须为整数'}), 400
                conn.execute(text(
                    """INSERT INTO assessment_manual_monthly (batch, assessment_case_cnt, work_note, updated_by)
                       VALUES (:b,:c,:w,:u)
                       ON DUPLICATE KEY UPDATE assessment_case_cnt=VALUES(assessment_case_cnt),
                         work_note=VALUES(work_note), updated_by=VALUES(updated_by)"""
                ), {'b': batch, 'c': cnt_i, 'w': monthly.get('work_note'), 'u': user})

                # scores by type replace
                types = sorted({s.get('unit_type') for s in scores if s.get('unit_type')})
                for ut in types:
                    conn.execute(text(
                        "DELETE FROM assessment_manual_score WHERE batch=:b AND unit_type=:t"
                    ), {'b': batch, 't': ut})
                for s in scores:
                    ut = (s.get('unit_type') or '').strip()
                    un = (s.get('unit_name') or '').strip()
                    st = (s.get('score_type') or '').strip()
                    if not (ut and un and st):
                        continue
                    try:
                        val = float(s.get('score_value'))
                    except (TypeError, ValueError):
                        return jsonify({'success': False, 'error': f'{un}/{st} 分值无效'}), 400
                    conn.execute(text(
                        """INSERT INTO assessment_manual_score
                           (batch, unit_name, unit_type, score_type, score_value, updated_by)
                           VALUES (:b,:u,:t,:st,:v,:by)"""
                    ), {'b': batch, 'u': un, 't': ut, 'st': st, 'v': val, 'by': user})

                # garbage
                for r in REGION_KEYS:
                    dist = SANITATION_REGION_MAP[r]
                    raw = garbage.get(r, garbage.get(dist, 0))
                    try:
                        n = int(raw) if raw is not None and raw != '' else 0
                    except (TypeError, ValueError):
                        return jsonify({'success': False, 'error': f'{r}片区件数无效'}), 400
                    if n < 0:
                        return jsonify({'success': False, 'error': f'{r}片区件数不能为负'}), 400
                    conn.execute(text(
                        """INSERT INTO assessment_manual_garbage
                           (batch, region, district_name, piece_count, updated_by)
                           VALUES (:b,:r,:d,:c,:u)
                           ON DUPLICATE KEY UPDATE piece_count=VALUES(piece_count),
                             district_name=VALUES(district_name), updated_by=VALUES(updated_by)"""
                    ), {'b': batch, 'r': r, 'd': dist, 'c': n, 'u': user})

                # collector
                conn.execute(text(
                    """INSERT INTO assessment_manual_collector (batch, self_dispose_cnt, updated_by)
                       VALUES (:b,:c,:u)
                       ON DUPLICATE KEY UPDATE self_dispose_cnt=VALUES(self_dispose_cnt), updated_by=VALUES(updated_by)"""
                ), {'b': batch, 'c': self_i, 'u': user})

                # details
                conn.execute(text("DELETE FROM assessment_manual_special_detail WHERE batch=:b"), {'b': batch})
                for d in details:
                    major = (d.get('major_name') or d.get('major') or '').strip()
                    minor = (d.get('minor_name') or d.get('minor') or '').strip()
                    try:
                        cnt = int(d.get('piece_cnt', d.get('cnt', 0)) or 0)
                    except (TypeError, ValueError):
                        return jsonify({'success': False, 'error': '专项明细件数无效'}), 400
                    if not major or not minor:
                        continue
                    conn.execute(text(
                        """INSERT INTO assessment_manual_special_detail
                           (batch, major_name, minor_name, piece_cnt, updated_by)
                           VALUES (:b,:ma,:mi,:c,:u)"""
                    ), {'b': batch, 'ma': major, 'mi': minor, 'c': cnt, 'u': user})

                # ledgers
                for ltype, items in ledgers.items():
                    if ltype not in ('pending', 'backlog', 'praise'):
                        continue
                    conn.execute(text(
                        "DELETE FROM assessment_manual_ledger WHERE batch=:b AND ledger_type=:t"
                    ), {'b': batch, 't': ltype})
                    for it in (items or []):
                        try:
                            cnt = it.get('piece_cnt')
                            cnt_i = int(cnt) if cnt is not None and cnt != '' else None
                        except (TypeError, ValueError):
                            return jsonify({'success': False, 'error': '台账数量须为整数'}), 400
                        conn.execute(text(
                            """INSERT INTO assessment_manual_ledger
                               (batch, ledger_type, unit_name, dept_name, source, piece_cnt, content, reason, deadline, updated_by)
                               VALUES (:b,:t,:u,:d,:s,:c,:ct,:r,:dl,:by)"""
                        ), {
                            'b': batch, 't': ltype,
                            'u': (it.get('unit_name') or '') or None,
                            'd': (it.get('dept_name') or '') or None,
                            's': (it.get('source') or '') or None,
                            'c': cnt_i,
                            'ct': it.get('content'),
                            'r': it.get('reason'),
                            'dl': it.get('deadline') or None,
                            'by': user,
                        })
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f'保存全部人工数据失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500


def load_external_data_from_db(engine, batch: str):
    """从库中加载人工分值，组装为 assessment 计算用的 external_data。

    返回 (external_data, missing_meta)
    missing_meta: {unit_name: [缺的分项...]}
    垃圾分 = 100 - 件数*0.01
    """
    external = {}
    missing = {}
    if not engine:
        return external, missing

    def mark(unit, label):
        missing.setdefault(unit, []).append(label)

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT unit_name, score_type, score_value FROM assessment_manual_score WHERE batch=:b"
        ), {'b': batch}).fetchall()

        key_map = {
            ('dispatch', 'team'): lambda u: f'dispatch_{u}_team_score',
            ('dispatch', 'street'): lambda u: f'dispatch_{u}_street_score',
            ('dispatch', 'extra'): lambda u: f'dispatch_{u}_extra',
            ('sanitation', 'center'): lambda u: f'san_{u}_center',
            ('sanitation', 'extra'): lambda u: f'san_{u}_extra',
            ('garden', 'center'): lambda u: f'garden_{u}_center',
            ('garden', 'extra'): lambda u: f'garden_{u}_extra',
            ('garden_park', 'center'): lambda u: f'garden_{u}_center',
            ('garden_park', 'extra'): lambda u: f'garden_{u}_extra',
            ('municipal', 'extra'): lambda u: f'muni_{u}_extra',
        }
        for unit, st, val in rows:
            for (ut, stp), fn in key_map.items():
                # unit_type 从键推断：用 score 所属类型需另查——简化：按 score_type+名称规则
                pass
            # 重新按 unit_type 查
        rows2 = conn.execute(text(
            "SELECT unit_name, unit_type, score_type, score_value FROM assessment_manual_score WHERE batch=:b"
        ), {'b': batch}).fetchall()
        for unit, ut, st, val in rows2:
            if ut == 'dispatch' and st == 'team':
                external[f'dispatch_{unit}_team_score'] = float(val)
            elif ut == 'dispatch' and st == 'street':
                external[f'dispatch_{unit}_street_score'] = float(val)
            elif ut == 'dispatch' and st == 'extra':
                external[f'dispatch_{unit}_extra'] = float(val)
            elif ut == 'sanitation' and st == 'center':
                external[f'san_{unit}_center'] = float(val)
            elif ut == 'sanitation' and st == 'extra':
                external[f'san_{unit}_extra'] = float(val)
            elif ut in ('garden', 'garden_park') and st == 'center':
                external[f'garden_{unit}_center'] = float(val)
            elif ut in ('garden', 'garden_park') and st == 'extra':
                external[f'garden_{unit}_extra'] = float(val)
            elif ut == 'municipal' and st == 'extra':
                external[f'muni_{unit}_extra'] = float(val)

        # garbage
        grows = conn.execute(text(
            "SELECT region, district_name, piece_count FROM assessment_manual_garbage WHERE batch=:b"
        ), {'b': batch}).fetchall()
        for region, dist, cnt in grows:
            score = 100.0 - int(cnt or 0) * 0.01
            external[f'san_{dist}_garbage'] = round(score, 3)

    # 完整性检查
    for team in DISPATCH_TEAMS:
        if f'dispatch_{team}_team_score' not in external:
            mark(team, '队考核分')
        if f'dispatch_{team}_street_score' not in external:
            mark(team, '街道办分')
        if f'dispatch_{team}_extra' not in external:
            mark(team, '加减分项')
    for dist in SANITATION_REGION_MAP.values():
        if f'san_{dist}_center' not in external:
            mark(dist, '中心考核分')
        if f'san_{dist}_garbage' not in external:
            mark(dist, '单体垃圾件数')
        if f'san_{dist}_extra' not in external:
            mark(dist, '加减分项')
    for d in GARDEN_DISTRICTS:
        if f'garden_{d}_center' not in external:
            mark(d, '中心考核分')
        if f'garden_{d}_extra' not in external:
            mark(d, '加减分项')
    for p in PARKS:
        if f'garden_{p}_center' not in external:
            mark(p, '中心考核分')
        if f'garden_{p}_extra' not in external:
            mark(p, '加减分项')
    for u in MUNICIPAL_UNITS:
        if f'muni_{u}_extra' not in external:
            mark(u, '加减分项')

    return external, missing


def _unit_type_of(name: str) -> str:
    if name in DISPATCH_TEAMS:
        return 'dispatch'
    if name in SANITATION_REGION_MAP.values():
        return 'sanitation'
    if name in GARDEN_DISTRICTS:
        return 'garden'
    if name in PARKS:
        return 'garden_park'
    if name in MUNICIPAL_UNITS:
        return 'municipal'
    return 'other'


def persist_calc_results(engine, batch: str, results: dict, missing: dict, username: str):
    """同月覆盖写入 assessment_result"""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM assessment_result WHERE batch=:b"), {'b': batch})
        for unit, r in results.items():
            ut = _unit_type_of(unit)
            miss = missing.get(unit) or []
            # 独立部门等无 missing 也参与计算的：is_complete=1
            # 有 missing 且 final_score 置空的：is_complete=0
            final = r.get('final_score')
            complete = 0 if (miss or final is None) else 1
            if miss:
                final = None
            conn.execute(text(
                """INSERT INTO assessment_result
                   (batch, unit_name, unit_type, total, closed, overtime, delayed_cnt, rework,
                    system_score, team_score, street_score, garbage_score, center_score, extra_points,
                    final_score, missing_fields, is_complete, calc_by)
                   VALUES (:b,:n,:t,:tot,:cl,:ot,:dl,:rw,:ss,:tm,:st,:gs,:cs,:ex,:fs,:mf,:ic,:by)"""
            ), {
                'b': batch, 'n': unit, 't': ut,
                'tot': r.get('total'), 'cl': r.get('closed'),
                'ot': r.get('overtime'), 'dl': r.get('delayed'), 'rw': r.get('rework'),
                'ss': r.get('system_score'),
                'tm': r.get('team_score'), 'st': r.get('street_score'),
                'gs': r.get('garbage_score'), 'cs': r.get('center_score'),
                'ex': r.get('extra_points'),
                'fs': final,
                'mf': ','.join(miss) if miss else None,
                'ic': complete,
                'by': username,
            })
