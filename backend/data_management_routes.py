# -*- coding: utf-8 -*-
"""数据管理路由模块 - 案件数据上传、浏览、编辑、导出"""
import io
import json
import datetime
import logging
from flask import request, jsonify, send_file
from sqlalchemy import text
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from common import protected as _protected, admin_required as _admin_required
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required

try:
    from common import process_excel_upload, COLUMN_MAP, _normalize_bool
except ImportError:
    from analysis_routes import process_excel_upload, COLUMN_MAP, _normalize_bool

DB_COLUMN_LABELS = {v: k for k, v in COLUMN_MAP.items()}
DB_COLUMN_LABELS.update({
    'id': 'ID',
    'upload_batch': '月份',
    'upload_time': '上传时间',
    'uploader': '上传人',
})

SYSTEM_COLUMNS = {'id', 'upload_batch', 'upload_time', 'uploader'}
HIDDEN_COLUMNS = {'id', 'upload_time', 'uploader', 'reason_delayed', 'opinion', 'area', 'grid', 'delay_count'}
SEARCHABLE_TYPES = {'varchar', 'text', 'bigint', 'int'}


def _get_columns_info(engine):
    with engine.connect() as conn:
        result = conn.execute(text("DESCRIBE case_data"))
        columns = []
        for row in result:
            col_name = row[0]
            if col_name in HIDDEN_COLUMNS:
                continue
            col_type = str(row[1]).split('(')[0].lower()
            columns.append({
                'name': col_name,
                'type': col_type,
                'editable': col_name not in SYSTEM_COLUMNS,
                'label': DB_COLUMN_LABELS.get(col_name, col_name),
            })
    return columns


def _snapshot_records(engine, record_ids):
    """查询指定ID记录的完整快照，返回 {id: {字段: 值}} 字典"""
    if not record_ids:
        return {}
    placeholders = ','.join([f':rid{i}' for i in range(len(record_ids))])
    params = {f'rid{i}': v for i, v in enumerate(record_ids)}
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM case_data WHERE id IN ({placeholders})"), params)
        columns = [col for col in result.keys()]
        snapshot = {}
        for row in result:
            row_dict = {}
            for i, col in enumerate(columns):
                val = row[i]
                if isinstance(val, (datetime.datetime,)):
                    val = val.strftime('%Y-%m-%d %H:%M:%S')
                elif hasattr(val, 'isoformat'):
                    val = str(val)
                row_dict[col] = val
            snapshot[str(row_dict['id'])] = row_dict
    return snapshot


def _write_operation_log(conn, user_id, table_name, op_type, record_ids, snapshot_data=None, old_value=None, new_value=None):
    """写入 operation_logs 表"""
    record_id_str = ','.join(str(rid) for rid in record_ids) if record_ids else ''
    snapshot_json = json.dumps(snapshot_data, ensure_ascii=False, default=str) if snapshot_data else None
    conn.execute(text(
        "INSERT INTO operation_logs (user_id, table_name, operation_type, record_id, old_value, new_value, snapshot_data, created_at) "
        "VALUES (:user_id, :table_name, :op_type, :record_id, :old_value, :new_value, :snapshot_data, :created_at)"
    ), {
        'user_id': user_id,
        'table_name': table_name,
        'op_type': op_type,
        'record_id': record_id_str,
        'old_value': old_value,
        'new_value': new_value,
        'snapshot_data': snapshot_json,
        'created_at': datetime.datetime.now()
    })


def register_data_management_routes(app, engine=None, protected=None, admin_required=None):
    protected = protected or _protected
    admin_required = admin_required or _admin_required

    @app.route('/api/data-management/months', methods=['GET'])
    @admin_required
    def dm_months():
        try:
            if not engine:
                return jsonify({'success': True, 'months': []})
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT upload_batch, COUNT(*) as count, MIN(upload_time) as upload_time "
                    "FROM case_data GROUP BY upload_batch ORDER BY upload_batch DESC"
                ))
                months = [
                    {'batch': row[0], 'count': row[1], 'upload_time': str(row[2]) if row[2] else ''}
                    for row in result
                ]
            return jsonify({'success': True, 'months': months})
        except Exception as e:
            logger.error(f"获取月份列表失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/records', methods=['GET'])
    @admin_required
    def dm_records():
        try:
            if not engine:
                return jsonify({'success': True, 'records': [], 'total': 0, 'columns': []})

            month = request.args.get('month', '')
            page = max(request.args.get('page', 1, type=int), 1)
            page_size = min(max(request.args.get('page_size', 20, type=int), 1), 100)
            search_field = request.args.get('search_field', '')
            search_value = request.args.get('search_value', '')
            sort_field = request.args.get('sort_field', 'id')
            sort_order = request.args.get('sort_order', 'desc')

            columns_info = _get_columns_info(engine)
            valid_col_names = {c['name'] for c in columns_info}
            if sort_field not in valid_col_names:
                sort_field = 'id'
            if sort_order not in ('asc', 'desc'):
                sort_order = 'desc'

            conditions = []
            params = {}

            if month:
                conditions.append("upload_batch = :month")
                params['month'] = month

            if search_field and search_value and search_field in valid_col_names:
                col_type = next((c['type'] for c in columns_info if c['name'] == search_field), '')
                if col_type in SEARCHABLE_TYPES or col_type == 'text':
                    if col_type in ('bigint', 'int'):
                        conditions.append(f"`{search_field}` = :search_value")
                        params['search_value'] = search_value
                    else:
                        conditions.append(f"`{search_field}` LIKE :search_value")
                        params['search_value'] = f'%{search_value}%'

            where_clause = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''
            offset = (page - 1) * page_size

            with engine.connect() as conn:
                count_sql = text(f"SELECT COUNT(*) FROM case_data{where_clause}")
                total = conn.execute(count_sql, params).scalar()

                data_sql = text(f"SELECT * FROM case_data{where_clause} ORDER BY `{sort_field}` {sort_order} LIMIT :limit OFFSET :offset")
                params['limit'] = page_size
                params['offset'] = offset
                result = conn.execute(data_sql, params)
                rows = result.fetchall()
                col_names = result.keys()

            records = []
            for row in rows:
                record = {}
                for i, col in enumerate(col_names):
                    val = row[i]
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    elif val is not None:
                        val = str(val) if not isinstance(val, (int, float, bool)) else val
                    record[col] = val
                records.append(record)

            return jsonify({
                'success': True,
                'records': records,
                'total': total,
                'page': page,
                'page_size': page_size,
                'columns': columns_info
            })
        except Exception as e:
            logger.error(f"获取记录失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/record', methods=['POST'])
    @admin_required
    def dm_create_record():
        try:
            data = request.get_json(silent=True) or {}
            record_data = data.get('record_data', {})
            if not record_data:
                return jsonify({'success': False, 'error': '缺少记录数据'}), 400

            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            if 'upload_batch' not in record_data or not record_data['upload_batch']:
                if record_data.get('report_time'):
                    try:
                        dt = pd.to_datetime(record_data['report_time'])
                        record_data['upload_batch'] = dt.strftime('%Y%m')
                    except Exception:
                        record_data['upload_batch'] = datetime.datetime.now().strftime('%Y%m')
                else:
                    record_data['upload_batch'] = datetime.datetime.now().strftime('%Y%m')

            record_data['uploader'] = getattr(request, 'username', 'system')

            for col in ['is_delayed', 'is_rework']:
                if col in record_data:
                    record_data[col] = _normalize_bool(record_data[col])

            valid_cols = set()
            columns_info = _get_columns_info(engine)
            for c in columns_info:
                if c['name'] not in SYSTEM_COLUMNS or c['name'] == 'upload_batch':
                    valid_cols.add(c['name'])

            filtered = {k: v for k, v in record_data.items() if k in valid_cols}
            if not filtered:
                return jsonify({'success': False, 'error': '无有效字段'}), 400

            cols = list(filtered.keys())
            placeholders = ', '.join([f':{c}' for c in cols])
            col_names = ', '.join([f'`{c}`' for c in cols])
            params = {c: filtered[c] for c in cols}

            with engine.connect() as conn:
                sql = text(f"INSERT INTO case_data ({col_names}) VALUES ({placeholders})")
                conn.execute(sql, params)
                conn.commit()
                record_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

            return jsonify({'success': True, 'message': '新增成功', 'record_id': record_id})
        except Exception as e:
            logger.error(f"新增记录失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/record/<int:record_id>', methods=['PUT'])
    @admin_required
    def dm_update_record(record_id):
        try:
            data = request.get_json(silent=True) or {}
            record_data = data.get('record_data', {})
            if not record_data:
                return jsonify({'success': False, 'error': '缺少更新数据'}), 400

            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            for col in ['is_delayed', 'is_rework', 'is_overtime']:
                if col in record_data:
                    record_data[col] = _normalize_bool(record_data[col])

            columns_info = _get_columns_info(engine)
            editable = {c['name'] for c in columns_info if c['editable']}
            filtered = {k: v for k, v in record_data.items() if k in editable}

            if not filtered:
                return jsonify({'success': False, 'error': '无有效更新字段'}), 400

            # 变更前快照
            snapshot = _snapshot_records(engine, [record_id])

            set_clause = ', '.join([f'`{k}` = :{k}' for k in filtered.keys()])
            params = dict(filtered)
            params['id'] = record_id

            with engine.connect() as conn:
                sql = text(f"UPDATE case_data SET {set_clause} WHERE id = :id")
                result = conn.execute(sql, params)

                if result.rowcount == 0:
                    conn.commit()
                    return jsonify({'success': False, 'error': '记录不存在'}), 404

                _write_operation_log(conn, request.user_id, 'case_data', 'update', [record_id],
                                     snapshot_data=snapshot, old_value=f'修改字段: {",".join(filtered.keys())}')
                conn.commit()

            return jsonify({'success': True, 'message': '修改成功'})
        except Exception as e:
            logger.error(f"更新记录失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/record/<int:record_id>', methods=['DELETE'])
    @admin_required
    def dm_delete_record(record_id):
        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            # 变更前快照
            snapshot = _snapshot_records(engine, [record_id])

            with engine.connect() as conn:
                result = conn.execute(text("DELETE FROM case_data WHERE id = :id"), {'id': record_id})

                if result.rowcount == 0:
                    conn.commit()
                    return jsonify({'success': False, 'error': '记录不存在'}), 404

                _write_operation_log(conn, request.user_id, 'case_data', 'delete', [record_id],
                                     snapshot_data=snapshot, old_value='删除记录')
                conn.commit()

            return jsonify({'success': True, 'message': '删除成功'})
        except Exception as e:
            logger.error(f"删除记录失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/batch-delete', methods=['POST'])
    @admin_required
    def dm_batch_delete():
        try:
            data = request.get_json(silent=True) or {}
            ids = data.get('ids', [])

            if not ids or not isinstance(ids, list):
                return jsonify({'success': False, 'error': '请选择要删除的记录'}), 400

            try:
                ids = [int(i) for i in ids]
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': '无效的记录ID'}), 400

            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            # 变更前快照
            snapshot = _snapshot_records(engine, ids)

            placeholders = ','.join([f':id{i}' for i in range(len(ids))])
            params = {f'id{i}': v for i, v in enumerate(ids)}

            with engine.connect() as conn:
                sql = text(f"DELETE FROM case_data WHERE id IN ({placeholders})")
                result = conn.execute(sql, params)
                deleted_count = result.rowcount

                _write_operation_log(conn, request.user_id, 'case_data', 'batch_delete', ids,
                                     snapshot_data=snapshot, old_value=f'批量删除{deleted_count}条记录')
                conn.commit()

            return jsonify({'success': True, 'message': '批量删除成功', 'deleted_count': deleted_count})
        except Exception as e:
            logger.error(f"批量删除失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/batch-update', methods=['POST'])
    @admin_required
    def dm_batch_update():
        try:
            data = request.get_json(silent=True) or {}
            ids = data.get('ids', [])
            field = data.get('field', '')
            value = data.get('value')

            if not ids or not isinstance(ids, list):
                return jsonify({'success': False, 'error': '请选择要修改的记录'}), 400
            if not field:
                return jsonify({'success': False, 'error': '请选择要修改的字段'}), 400

            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            columns_info = _get_columns_info(engine)
            editable = {c['name'] for c in columns_info if c['editable']}
            if field not in editable:
                return jsonify({'success': False, 'error': '不可修改该字段'}), 400

            if field in ('is_delayed', 'is_rework', 'is_overtime'):
                value = _normalize_bool(value)

            try:
                ids = [int(i) for i in ids]
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': '无效的记录ID'}), 400

            # 变更前快照
            snapshot = _snapshot_records(engine, ids)

            field_label = DB_COLUMN_LABELS.get(field, field)
            placeholders = ','.join([f':id{i}' for i in range(len(ids))])
            params = {f'id{i}': v for i, v in enumerate(ids)}
            params['value'] = value

            with engine.connect() as conn:
                sql = text(f"UPDATE case_data SET `{field}` = :value WHERE id IN ({placeholders})")
                result = conn.execute(sql, params)
                updated_count = result.rowcount

                _write_operation_log(conn, request.user_id, 'case_data', 'batch_update', ids,
                                     snapshot_data=snapshot,
                                     old_value=f'批量修改{field_label}',
                                     new_value=f'设为: {value}')
                conn.commit()

            return jsonify({'success': True, 'message': '批量修改成功', 'updated_count': updated_count})
        except Exception as e:
            logger.error(f"批量修改失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/upload', methods=['POST'])
    @admin_required
    def dm_upload():
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': '请上传文件'}), 400

            file = request.files['file']
            if not file.filename.endswith(('.xlsx', '.xls')):
                return jsonify({'success': False, 'error': '仅支持Excel文件(.xlsx/.xls)'}), 400

            batch_override = (request.form.get('batch', '') or '').strip()
            username = getattr(request, 'username', 'system')

            result = process_excel_upload(file.read(), batch_override, username, engine)

            return jsonify({
                'success': True,
                'message': f"上传成功，共导入 {result['count']} 条数据（月份: {result['batch']}）",
                'batch': result['batch'],
                'count': result['count']
            })
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.exception("上传案件数据失败")
            return jsonify({'success': False, 'error': f'上传失败: {str(e)}'}), 500

    @app.route('/api/data-management/detect-delay-rework', methods=['POST'])
    @admin_required
    def dm_detect_delay_rework():
        """检测延期/返工/超时任务号属于哪个批次，返回匹配结果"""
        try:
            data = request.get_json(silent=True) or {}
            delay_task_nos = [str(n).strip() for n in data.get('delay_task_nos', []) if str(n).strip().isdigit()]
            rework_task_nos = [str(n).strip() for n in data.get('rework_task_nos', []) if str(n).strip().isdigit()]
            overtime_task_nos = [str(n).strip() for n in data.get('overtime_task_nos', []) if str(n).strip().isdigit()]

            if not delay_task_nos and not rework_task_nos and not overtime_task_nos:
                return jsonify({'success': False, 'error': '请上传延期/返工/超时列表'}), 400

            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            all_task_nos = list(set(delay_task_nos + rework_task_nos + overtime_task_nos))
            placeholders = ','.join([f':t{i}' for i in range(len(all_task_nos))])
            params = {f't{i}': v for i, v in enumerate(all_task_nos)}

            with engine.connect() as conn:
                result = conn.execute(text(
                    f"SELECT upload_batch, task_no, is_delayed, is_rework, is_overtime "
                    f"FROM case_data WHERE task_no IN ({placeholders})"
                ), params)
                rows = result.fetchall()

            # 同一任务号分布在多个批次时，优先选择有非零标记的批次，否则选最大的批次
            task_batches = {}
            for batch, task_no, d, r, o in rows:
                tn = str(task_no)
                if tn not in task_batches:
                    task_batches[tn] = []
                task_batches[tn].append((batch, d or 0, r or 0, o or 0))

            # 按批次统计
            batch_stats = {}
            found_task_nos = set()
            for tn, entries in task_batches.items():
                if len(entries) > 1:
                    # 多批次：优先选有非零标记的，否则选最大批次
                    non_zero = [e for e in entries if any(e[1:])]
                    best_batch = non_zero[0][0] if non_zero else max(e[0] for e in entries)
                else:
                    best_batch = entries[0][0]
                found_task_nos.add(tn)
                if best_batch not in batch_stats:
                    batch_stats[best_batch] = {'delayed': 0, 'rework': 0, 'overtime': 0, 'total': 0}
                batch_stats[best_batch]['total'] += 1
                if tn in delay_task_nos:
                    batch_stats[best_batch]['delayed'] += 1
                if tn in rework_task_nos:
                    batch_stats[best_batch]['rework'] += 1
                if tn in overtime_task_nos:
                    batch_stats[best_batch]['overtime'] += 1

            # 未找到的任务号
            not_found = [t for t in all_task_nos if t not in found_task_nos]

            return jsonify({
                'success': True,
                'batch_stats': batch_stats,
                'not_found': not_found,
                'total_delayed': len(delay_task_nos),
                'total_rework': len(rework_task_nos),
                'total_overtime': len(overtime_task_nos)
            })
        except Exception as e:
            logger.error(f"检测延期/返工/超时失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/apply-delay-rework', methods=['POST'])
    @admin_required
    def dm_apply_delay_rework():
        """确认更新延期/返工/超时标记"""
        try:
            data = request.get_json(silent=True) or {}
            batch = data.get('batch', '').strip()
            delay_task_nos = [str(n).strip() for n in data.get('delay_task_nos', []) if str(n).strip().isdigit()]
            rework_task_nos = [str(n).strip() for n in data.get('rework_task_nos', []) if str(n).strip().isdigit()]
            overtime_task_nos = [str(n).strip() for n in data.get('overtime_task_nos', []) if str(n).strip().isdigit()]

            if not batch:
                return jsonify({'success': False, 'error': '请选择批次'}), 400

            if not delay_task_nos and not rework_task_nos and not overtime_task_nos:
                return jsonify({'success': False, 'error': '无任务号可更新'}), 400

            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            # 收集所有任务号，查询受影响记录ID用于快照
            all_task_nos = list(set(delay_task_nos + rework_task_nos + overtime_task_nos))
            affected_ids = []
            with engine.connect() as conn:
                placeholders = ','.join([f':tn{i}' for i in range(len(all_task_nos))])
                params = {f'tn{i}': v for i, v in enumerate(all_task_nos)}
                params['batch'] = batch
                result = conn.execute(text(
                    f"SELECT id FROM case_data WHERE upload_batch = :batch AND task_no IN ({placeholders})"
                ), params)
                affected_ids = [row[0] for row in result]

            snapshot = _snapshot_records(engine, affected_ids) if affected_ids else {}
            updated = {'delayed': 0, 'rework': 0, 'overtime': 0}

            with engine.connect() as conn:
                # 更新延期
                if delay_task_nos:
                    placeholders = ','.join([f':t{i}' for i in range(len(delay_task_nos))])
                    params = {f't{i}': v for i, v in enumerate(delay_task_nos)}
                    params['batch'] = batch
                    result = conn.execute(text(
                        f"UPDATE case_data SET is_delayed = 1 WHERE upload_batch = :batch AND task_no IN ({placeholders})"
                    ), params)
                    updated['delayed'] = result.rowcount

                # 更新返工
                if rework_task_nos:
                    placeholders = ','.join([f':t{i}' for i in range(len(rework_task_nos))])
                    params = {f't{i}': v for i, v in enumerate(rework_task_nos)}
                    params['batch'] = batch
                    result = conn.execute(text(
                        f"UPDATE case_data SET is_rework = 1 WHERE upload_batch = :batch AND task_no IN ({placeholders})"
                    ), params)
                    updated['rework'] = result.rowcount

                # 更新超时
                if overtime_task_nos:
                    placeholders = ','.join([f':t{i}' for i in range(len(overtime_task_nos))])
                    params = {f't{i}': v for i, v in enumerate(overtime_task_nos)}
                    params['batch'] = batch
                    result = conn.execute(text(
                        f"UPDATE case_data SET is_overtime = 1 WHERE upload_batch = :batch AND task_no IN ({placeholders})"
                    ), params)
                    updated['overtime'] = result.rowcount

                parts = []
                if updated['delayed']: parts.append(f"延期{updated['delayed']}条")
                if updated['rework']: parts.append(f"返工{updated['rework']}条")
                if updated['overtime']: parts.append(f"超时{updated['overtime']}条")
                _write_operation_log(conn, request.user_id, 'case_data', 'batch_update', affected_ids,
                                     snapshot_data=snapshot,
                                     old_value='更新延期/返工/超时标记',
                                     new_value='，'.join(parts))
                conn.commit()

            return jsonify({
                'success': True,
                'message': f"更新完成：延期{updated['delayed']}条，返工{updated['rework']}条，超时{updated['overtime']}条",
                'updated': updated
            })
        except Exception as e:
            logger.error(f"更新延期/返工/超时失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/export', methods=['GET'])
    @admin_required
    def dm_export():
        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            month = request.args.get('month', '')
            search_field = request.args.get('search_field', '')
            search_value = request.args.get('search_value', '')

            conditions = []
            params = {}

            if month:
                conditions.append("upload_batch = :month")
                params['month'] = month

            columns_info = _get_columns_info(engine)
            valid_col_names = {c['name'] for c in columns_info}

            if search_field and search_value and search_field in valid_col_names:
                col_type = next((c['type'] for c in columns_info if c['name'] == search_field), '')
                if col_type in SEARCHABLE_TYPES or col_type == 'text':
                    if col_type in ('bigint', 'int'):
                        conditions.append(f"`{search_field}` = :search_value")
                        params['search_value'] = search_value
                    else:
                        conditions.append(f"`{search_field}` LIKE :search_value")
                        params['search_value'] = f'%{search_value}%'

            where_clause = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''

            with engine.connect() as conn:
                total = conn.execute(text(f"SELECT COUNT(*) FROM case_data{where_clause}"), params).scalar()

            if total > 100000:
                return jsonify({'success': False, 'error': '数据量过大，请按月份筛选后导出'}), 400

            df = pd.read_sql(text(f"SELECT * FROM case_data{where_clause} ORDER BY id DESC"), engine, params=params)

            if df.empty:
                return jsonify({'success': False, 'error': '无数据可导出'}), 400

            rename_map = {}
            for col in df.columns:
                label = DB_COLUMN_LABELS.get(col, col)
                if label != col:
                    rename_map[col] = label

            export_cols = [c for c in df.columns if c not in HIDDEN_COLUMNS]
            df = df[export_cols]
            df = df.rename(columns=rename_map)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='案件数据')
            buffer.seek(0)

            filename = f"case_data_{month or 'all'}.xlsx"
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ===== 操作日志 =====

    @app.route('/api/data-management/logs', methods=['GET'])
    @admin_required
    def dm_logs():
        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))
            op_type = request.args.get('operation_type', '')
            offset = (page - 1) * page_size

            conditions = ["table_name = 'case_data'"]
            params = {}
            if op_type:
                conditions.append("operation_type = :op_type")
                params['op_type'] = op_type

            where = ' AND '.join(conditions)

            with engine.connect() as conn:
                count_result = conn.execute(text(f"SELECT COUNT(*) FROM operation_logs WHERE {where}"), params)
                total = count_result.scalar()

                params['limit'] = page_size
                params['offset'] = offset
                result = conn.execute(text(
                    f"SELECT ol.id, ol.operation_type, ol.record_id, ol.old_value, ol.new_value, ol.snapshot_data, ol.created_at, u.username "
                    f"FROM operation_logs ol LEFT JOIN users u ON ol.user_id = u.id "
                    f"WHERE {where} ORDER BY ol.created_at DESC LIMIT :limit OFFSET :offset"
                ), params)

                logs = []
                for row in result:
                    logs.append({
                        'id': row[0],
                        'operation_type': row[1],
                        'record_id': row[2],
                        'old_value': row[3],
                        'new_value': row[4],
                        'snapshot_data': row[5],
                        'created_at': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else '',
                        'username': row[7] or '未知'
                    })

            return jsonify({'success': True, 'logs': logs, 'total': total})
        except Exception as e:
            logger.error(f"查询操作日志失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/data-management/rollback', methods=['POST'])
    @admin_required
    def dm_rollback():
        try:
            data = request.get_json(silent=True) or {}
            log_id = data.get('log_id')
            target_record_id = data.get('record_id')  # 可选，指定单条回滚

            if not log_id:
                return jsonify({'success': False, 'error': '缺少日志ID'}), 400

            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            with engine.connect() as conn:
                # 查询日志记录
                result = conn.execute(text(
                    "SELECT operation_type, record_id, snapshot_data FROM operation_logs WHERE id = :log_id"
                ), {'log_id': log_id})
                log_row = result.fetchone()

                if not log_row:
                    return jsonify({'success': False, 'error': '日志记录不存在'}), 404

                op_type, record_id_str, snapshot_json = log_row

                if not snapshot_json:
                    return jsonify({'success': False, 'error': '该操作无可回滚的快照数据'}), 400

                snapshot = json.loads(snapshot_json)

                # 确定要回滚的记录
                if target_record_id:
                    target_id_str = str(target_record_id)
                    if target_id_str not in snapshot:
                        return jsonify({'success': False, 'error': '该记录不在快照中'}), 400
                    rollback_items = {target_id_str: snapshot[target_id_str]}
                else:
                    rollback_items = snapshot

                restored = 0
                for rid_str, record_data in rollback_items.items():
                    rid = int(rid_str)
                    # 检查记录是否存在
                    check = conn.execute(text("SELECT id FROM case_data WHERE id = :id"), {'id': rid})
                    if check.fetchone():
                        # 记录存在 → UPDATE 恢复
                        set_parts = []
                        update_params = {}
                        for k, v in record_data.items():
                            if k == 'id':
                                continue
                            set_parts.append(f'`{k}` = :{k}')
                            update_params[k] = v
                        update_params['id'] = rid
                        conn.execute(text(f"UPDATE case_data SET {', '.join(set_parts)} WHERE id = :id"), update_params)
                    else:
                        # 记录已删除 → INSERT 恢复
                        cols = [k for k in record_data.keys() if k != 'id']
                        vals = [f':{c}' for c in cols]
                        insert_params = {c: record_data[c] for c in cols}
                        insert_params['id'] = rid
                        conn.execute(text(
                            f"INSERT INTO case_data (id, {', '.join(cols)}) VALUES ({rid}, {', '.join(vals)})"
                        ), insert_params)
                    restored += 1

                # 记录回滚操作本身
                _write_operation_log(conn, request.user_id, 'case_data', 'rollback',
                                     [int(rid) for rid in rollback_items.keys()],
                                     snapshot_data=rollback_items,
                                     old_value=f'回滚日志#{log_id}',
                                     new_value=f'恢复{restored}条记录')
                conn.commit()

            return jsonify({'success': True, 'message': f'回滚成功，恢复了 {restored} 条记录', 'restored': restored})
        except Exception as e:
            logger.error(f"回滚失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
