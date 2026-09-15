# -*- coding: utf-8 -*-
"""数据统计查询 - 按条件汇总 + 点数反查明细（只读）

口径与考核一致：
- 应处置数 = COUNT(*)
- 结案数   = stage = '[办结]'
- 待处置数 = 非办结
- 超时/延期/返工 = is_overtime / is_delayed / is_rework = 1
"""
import datetime
import logging
from flask import request, jsonify
from sqlalchemy import text

logger = logging.getLogger(__name__)

try:
    from helpers import protected as _protected
except ImportError:
    from common import protected as _protected

# 允许筛选的字段 → 列类型
FILTER_FIELDS = {
    'task_no': 'int',
    'report_time': 'datetime',
    'deadline': 'datetime',
    'department': 'string',
    'source': 'string',
    'stage': 'string',
    'address': 'string',
    'description': 'string',
    'is_delayed': 'bool',
    'is_rework': 'bool',
    'is_overtime': 'bool',
    'upload_batch': 'string',
}

DETAIL_SELECT = """
    id, task_no, report_time, deadline, department, source, stage,
    address, description, is_delayed, is_rework, is_overtime,
    big_category, small_category, close_time, upload_batch, district, street
"""


def _parse_dt(s):
    if s is None or s == '':
        return None
    s = str(s).strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _fmt_cell(val):
    if isinstance(val, datetime.datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, datetime.date):
        return val.strftime('%Y-%m-%d')
    return val


def _bool_val(v):
    if isinstance(v, bool):
        return 1 if v else 0
    s = str(v).strip().lower()
    if s in ('1', 'true', 'yes', 'y', '是', '延期', '返工', '超时'):
        return 1
    if s in ('0', 'false', 'no', 'n', '否'):
        return 0
    return 1 if v else 0


def build_where(filters):
    """由前端 filters 列表生成 WHERE 子句与参数。返回 (where_sql, params) 或 raise ValueError。"""
    clauses = []
    params = {}
    if not filters:
        return '1=1', params

    for i, f in enumerate(filters):
        field = (f.get('field') or '').strip()
        op = (f.get('op') or 'eq').strip().lower()
        value = f.get('value')
        if field not in FILTER_FIELDS:
            raise ValueError(f'不支持的筛选字段: {field}')
        if value is None or (isinstance(value, str) and not value.strip()):
            continue

        ftype = FILTER_FIELDS[field]
        key = f'p{i}'
        col = field

        if ftype == 'bool':
            bv = _bool_val(value)
            if op in ('eq', '='):
                clauses.append(f'{col} = :{key}')
                params[key] = bv
            elif op in ('neq', 'ne', '!='):
                clauses.append(f'{col} != :{key}')
                params[key] = bv
            else:
                raise ValueError(f'{field} 仅支持 等于/不等于')
        elif ftype == 'int':
            if op in ('in', 'list'):
                parts = [p.strip() for p in str(value).replace('，', ',').split(',') if p.strip()]
                ids = []
                for p in parts:
                    if not p.isdigit():
                        raise ValueError(f'任务号须为数字: {p}')
                    ids.append(int(p))
                if not ids:
                    continue
                ph = ','.join(f':t{j}' for j in range(len(ids)))
                clauses.append(f'{col} IN ({ph})')
                for j, tid in enumerate(ids):
                    params[f't{j}'] = tid
            elif op in ('eq', '='):
                if not str(value).strip().isdigit():
                    raise ValueError('任务号须为数字')
                clauses.append(f'{col} = :{key}')
                params[key] = int(str(value).strip())
            else:
                raise ValueError(f'{field} 仅支持 等于/多值(逗号)')
        elif ftype == 'datetime':
            if op in ('between', 'range'):
                arr = value if isinstance(value, (list, tuple)) else [value]
                if len(arr) < 2:
                    raise ValueError(f'{field} 介于 需要两个时间')
                d0, d1 = _parse_dt(arr[0]), _parse_dt(arr[1])
                if not d0 or not d1:
                    raise ValueError(f'{field} 时间格式不正确')
                clauses.append(f'{col} >= :{key}a AND {col} <= :{key}b')
                params[f'{key}a'] = d0
                params[f'{key}b'] = d1 if (d1.hour or d1.minute or d1.second) else d1 + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
            elif op in ('eq', '='):
                d0 = _parse_dt(value)
                if not d0:
                    raise ValueError(f'{field} 时间格式不正确')
                if d0.hour == 0 and d0.minute == 0 and d0.second == 0 and 'T' not in str(value) and len(str(value).strip()) <= 10:
                    clauses.append(f'{col} >= :{key}a AND {col} <= :{key}b')
                    params[f'{key}a'] = d0
                    params[f'{key}b'] = d0 + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
                else:
                    clauses.append(f'{col} = :{key}')
                    params[key] = d0
            elif op in ('gt', '>', 'gte', '>='):
                d0 = _parse_dt(value)
                if not d0:
                    raise ValueError(f'{field} 时间格式不正确')
                clauses.append(f'{col} {">=" if op in ("gte", ">=") else ">"} :{key}')
                params[key] = d0
            elif op in ('lt', '<', 'lte', '<='):
                d0 = _parse_dt(value)
                if not d0:
                    raise ValueError(f'{field} 时间格式不正确')
                clauses.append(f'{col} {"<=" if op in ("lte", "<=") else "<"} :{key}')
                params[key] = d0
            else:
                raise ValueError(f'{field} 不支持的操作符: {op}')
        else:  # string
            if op in ('eq', '='):
                clauses.append(f'{col} = :{key}')
                params[key] = str(value).strip()
            elif op in ('neq', 'ne', '!='):
                clauses.append(f'{col} != :{key}')
                params[key] = str(value).strip()
            elif op in ('contains', 'like'):
                clauses.append(f'{col} LIKE :{key}')
                params[key] = f'%{str(value).strip()}%'
            elif op in ('ncontains', 'not_like', 'nlike'):
                clauses.append(f'({col} IS NULL OR {col} NOT LIKE :{key})')
                params[key] = f'%{str(value).strip()}%'
            else:
                raise ValueError(f'{field} 不支持的操作符: {op}')

    if not clauses:
        return '1=1', params
    return ' AND '.join(clauses), params


def _row_to_dict(row, columns):
    d = {}
    for i, c in enumerate(columns):
        d[c] = _fmt_cell(row[i])
    return d


def register_data_stats_routes(app, engine=None, protected=None):
    protected = protected or _protected

    def _require_engine():
        if not engine:
            return jsonify({'success': False, 'error': '数据库未连接'}), 500
        return None

    @app.route('/api/data-stats/aggregate', methods=['POST'])
    @protected
    def data_stats_aggregate():
        """按处置部门汇总（与考核同口径）。"""
        err = _require_engine()
        if err:
            return err
        try:
            body = request.get_json(silent=True) or {}
            filters = body.get('filters') or []
            where_sql, params = build_where(filters)
            with engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT
                        COALESCE(department, '未知') AS department,
                        COUNT(*) AS total,
                        SUM(CASE WHEN stage = '[办结]' THEN 1 ELSE 0 END) AS closed,
                        SUM(CASE WHEN is_overtime = 1 THEN 1 ELSE 0 END) AS overtime_cnt,
                        SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) AS delayed_cnt,
                        SUM(CASE WHEN is_rework = 1 THEN 1 ELSE 0 END) AS rework_cnt
                    FROM case_data
                    WHERE {where_sql}
                    GROUP BY COALESCE(department, '未知')
                    ORDER BY total DESC, department
                """), params).fetchall()

                rows = []
                sum_total = sum_closed = sum_ot = sum_dl = sum_rw = 0
                for r in result:
                    total = int(r[1] or 0)
                    closed = int(r[2] or 0)
                    overtime = int(r[3] or 0)
                    delayed = int(r[4] or 0)
                    rework = int(r[5] or 0)
                    pending = total - closed
                    rows.append({
                        'department': r[0],
                        'total': total,
                        'closed': closed,
                        'pending': pending,
                        'overtime': overtime,
                        'delayed': delayed,
                        'rework': rework,
                        'close_rate': round(closed / total * 100, 2) if total else 0,
                    })
                    sum_total += total
                    sum_closed += closed
                    sum_ot += overtime
                    sum_dl += delayed
                    sum_rw += rework

            return jsonify({
                'success': True,
                'rows': rows,
                'summary': {
                    'total': sum_total,
                    'closed': sum_closed,
                    'pending': sum_total - sum_closed,
                    'overtime': sum_ot,
                    'delayed': sum_dl,
                    'rework': sum_rw,
                    'close_rate': round(sum_closed / sum_total * 100, 2) if sum_total else 0,
                },
                'filters': filters,
            })
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f'统计查询失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-stats/detail', methods=['POST'])
    @protected
    def data_stats_detail():
        """反查明细（只读）。可叠加 department 等条件。"""
        err = _require_engine()
        if err:
            return err
        try:
            body = request.get_json(silent=True) or {}
            filters = list(body.get('filters') or [])
            department = body.get('department')
            if department:
                filters.append({'field': 'department', 'op': 'eq', 'value': department})
            page = max(1, int(body.get('page') or 1))
            page_size = min(200, max(1, int(body.get('page_size') or 50)))
            where_sql, params = build_where(filters)

            with engine.connect() as conn:
                total_row = conn.execute(
                    text(f'SELECT COUNT(*) FROM case_data WHERE {where_sql}'), params
                ).fetchone()
                total = int(total_row[0] if total_row else 0)
                offset = (page - 1) * page_size
                result = conn.execute(text(
                    f'SELECT {DETAIL_SELECT} FROM case_data WHERE {where_sql} '
                    f'ORDER BY report_time DESC, id DESC LIMIT :lim OFFSET :off'
                ), {**params, 'lim': page_size, 'off': offset})
                columns = list(result.keys())
                rows = [_row_to_dict(r, columns) for r in result]

            return jsonify({
                'success': True,
                'rows': rows,
                'total': total,
                'page': page,
                'page_size': page_size,
                'read_only': True,
                'filters': filters,
            })
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f'反查失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-stats/meta', methods=['GET'])
    @protected
    def data_stats_meta():
        """筛选元数据：部门/来源/阶段下拉。"""
        err = _require_engine()
        if err:
            return err
        try:
            with engine.connect() as conn:
                depts = [r[0] for r in conn.execute(text(
                    "SELECT DISTINCT department FROM case_data WHERE department IS NOT NULL AND department != '' ORDER BY department"
                )).fetchall()]
                sources = [r[0] for r in conn.execute(text(
                    "SELECT DISTINCT source FROM case_data WHERE source IS NOT NULL AND source != '' ORDER BY source"
                )).fetchall()]
                stages = [r[0] for r in conn.execute(text(
                    "SELECT DISTINCT stage FROM case_data WHERE stage IS NOT NULL AND stage != '' ORDER BY stage"
                )).fetchall()]
                batches = [r[0] for r in conn.execute(text(
                    "SELECT DISTINCT upload_batch FROM case_data WHERE upload_batch IS NOT NULL ORDER BY upload_batch DESC"
                )).fetchall()]
            return jsonify({
                'success': True,
                'departments': depts,
                'sources': sources,
                'stages': stages,
                'batches': batches,
            })
        except Exception as e:
            logger.error(f'获取统计元数据失败: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500
