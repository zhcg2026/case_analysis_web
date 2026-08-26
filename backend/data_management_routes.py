# -*- coding: utf-8 -*-
"""数据管理路由模块 - 案件数据上传、浏览、编辑、导出"""
import io
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
SEARCHABLE_TYPES = {'varchar', 'text'}


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

            for col in ['is_delayed', 'is_rework']:
                if col in record_data:
                    record_data[col] = _normalize_bool(record_data[col])

            columns_info = _get_columns_info(engine)
            editable = {c['name'] for c in columns_info if c['editable']}
            filtered = {k: v for k, v in record_data.items() if k in editable}

            if not filtered:
                return jsonify({'success': False, 'error': '无有效更新字段'}), 400

            set_clause = ', '.join([f'`{k}` = :{k}' for k in filtered.keys()])
            params = dict(filtered)
            params['id'] = record_id

            with engine.connect() as conn:
                sql = text(f"UPDATE case_data SET {set_clause} WHERE id = :id")
                result = conn.execute(sql, params)
                conn.commit()

                if result.rowcount == 0:
                    return jsonify({'success': False, 'error': '记录不存在'}), 404

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

            with engine.connect() as conn:
                result = conn.execute(text("DELETE FROM case_data WHERE id = :id"), {'id': record_id})
                conn.commit()

                if result.rowcount == 0:
                    return jsonify({'success': False, 'error': '记录不存在'}), 404

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

            placeholders = ','.join([f':id{i}' for i in range(len(ids))])
            params = {f'id{i}': v for i, v in enumerate(ids)}

            with engine.connect() as conn:
                sql = text(f"DELETE FROM case_data WHERE id IN ({placeholders})")
                result = conn.execute(sql, params)
                conn.commit()
                deleted_count = result.rowcount

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

            if field in ('is_delayed', 'is_rework'):
                value = _normalize_bool(value)

            try:
                ids = [int(i) for i in ids]
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': '无效的记录ID'}), 400

            placeholders = ','.join([f':id{i}' for i in range(len(ids))])
            params = {f'id{i}': v for i, v in enumerate(ids)}
            params['value'] = value

            with engine.connect() as conn:
                sql = text(f"UPDATE case_data SET `{field}` = :value WHERE id IN ({placeholders})")
                result = conn.execute(sql, params)
                conn.commit()
                updated_count = result.rowcount

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
                    f"SELECT upload_batch, task_no FROM case_data WHERE task_no IN ({placeholders})"
                ), params)
                rows = result.fetchall()

            # 按批次统计
            batch_stats = {}
            found_task_nos = set()
            for batch, task_no in rows:
                found_task_nos.add(str(task_no))
                if batch not in batch_stats:
                    batch_stats[batch] = {'delayed': 0, 'rework': 0, 'overtime': 0, 'total': 0}
                batch_stats[batch]['total'] += 1
                if str(task_no) in delay_task_nos:
                    batch_stats[batch]['delayed'] += 1
                if str(task_no) in rework_task_nos:
                    batch_stats[batch]['rework'] += 1
                if str(task_no) in overtime_task_nos:
                    batch_stats[batch]['overtime'] += 1

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
                    conditions.append(f"`{search_field}` LIKE :search_value")
                    params['search_value'] = f'%{search_value}%'

            where_clause = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''

            with engine.connect() as conn:
                total = conn.execute(text(f"SELECT COUNT(*) FROM case_data{where_clause}"), params).scalar()

            if total > 100000:
                return jsonify({'success': False, 'error': '数据量过大，请按月份筛选后导出'}), 400

            df = pd.read_sql(f"SELECT * FROM case_data{where_clause} ORDER BY id DESC", engine, params=params)

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
