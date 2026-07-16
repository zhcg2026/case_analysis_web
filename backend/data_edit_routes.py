# -*- coding: utf-8 -*-
"""数据编辑路由模块 - 记录CRUD、批量操作"""
import json
from flask import request, jsonify
import pandas as pd
from sqlalchemy import text, inspect
from helpers import admin_required

def register_data_edit_routes(app, Session, engine, OperationLog):
    """注册数据编辑相关路由"""
    
    # 数据编辑列表显示的字段（精简版）
    DATA_EDIT_DISPLAY_FIELDS = [
        '任务号', '问题描述', '处置部门', '结案时间', '是否超时', '延期次数', '返工次数'
    ]

    # 数据编辑弹窗可编辑的字段（完整版）
    DATA_EDIT_FORM_FIELDS = [
        '任务号', '上报时间', '问题描述', '所属街道', '所属社区',
        '处置部门', '结案时间', '是否超时', '延期次数', '返工次数'
    ]

    @app.route('/api/data-edit/records', methods=['GET'])
    @admin_required
    def get_data_edit_records():
        """获取数据列表（支持分页、筛选、查找）"""
        try:
            table_name = request.args.get('table_name', '')
            month = request.args.get('month', '')
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))
            search_field = request.args.get('search_field', '')
            search_value = request.args.get('search_value', '')

            if not table_name:
                return jsonify({'error': '请选择数据表'}), 400

            # 检查表是否存在
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return jsonify({'error': '数据表不存在'}), 400

            # 获取表的列名
            columns = [col['name'] for col in inspector.get_columns(table_name)]

            # 构建SQL查询
            where_clauses = []
            params = {}

            # 月份筛选
            if month and '月份' in columns:
                where_clauses.append("`月份` = :month")
                params['month'] = month

            # 字段查找
            if search_field and search_value:
                if search_field in columns:
                    if search_field == '任务号':
                        # 任务号精确匹配
                        where_clauses.append(f"`{search_field}` = :search_value")
                    else:
                        # 其他字段模糊匹配
                        where_clauses.append(f"`{search_field}` LIKE :search_value")
                        search_value = f"%{search_value}%"
                    params['search_value'] = search_value

            where_sql = " AND ".join(where_clauses)
            if where_sql:
                where_sql = "WHERE " + where_sql

            # 查询总数
            count_sql = f"SELECT COUNT(*) as cnt FROM `{table_name}` {where_sql}"
            with engine.connect() as conn:
                result = conn.execute(text(count_sql), params)
                total = result.fetchone()[0]

            # 查询数据
            offset = (page - 1) * page_size
            data_sql = f"SELECT * FROM `{table_name}` {where_sql} LIMIT {page_size} OFFSET {offset}"
            df = pd.read_sql(text(data_sql), engine, params=params)

            # 转换数据
            records = df.to_dict('records')
            # 处理 NaN 值
            for record in records:
                for key in record:
                    if pd.isna(record[key]):
                        record[key] = None

            return jsonify({
                'records': records,
                'total': total,
                'page': page,
                'page_size': page_size,
                'columns': columns,
                'display_fields': [f for f in DATA_EDIT_DISPLAY_FIELDS if f in columns],
                'edit_fields': [f for f in DATA_EDIT_FORM_FIELDS if f in columns]
            }), 200

        except Exception as e:
            print(f"Error in get_data_edit_records: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/data-edit/record', methods=['POST'])
    @admin_required
    def create_data_edit_record():
        """新增记录"""
        session = Session()
        try:
            data = request.get_json()
            table_name = data.get('table_name')
            record_data = data.get('record_data', {})

            if not table_name:
                return jsonify({'error': '请选择数据表'}), 400

            # 检查表是否存在
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return jsonify({'error': '数据表不存在'}), 400

            # 获取表的列名
            columns = [col['name'] for col in inspector.get_columns(table_name)]

            # 检查任务号是否重复
            if '任务号' in record_data and '任务号' in columns:
                with engine.connect() as conn:
                    result = conn.execute(
                        text(f"SELECT COUNT(*) FROM `{table_name}` WHERE `任务号` = :task_number"),
                        {'task_number': record_data['任务号']}
                    )
                    if result.fetchone()[0] > 0:
                        return jsonify({'error': '任务号已存在，不能重复添加'}), 400

            # 构建插入SQL
            fields = []
            values = []
            params = {}
            for key, value in record_data.items():
                if key in columns and value is not None and value != '':
                    fields.append(f"`{key}`")
                    values.append(f":{key}")
                    params[key] = value

            if not fields:
                return jsonify({'error': '没有有效数据'}), 400

            insert_sql = f"INSERT INTO `{table_name}` ({', '.join(fields)}) VALUES ({', '.join(values)})"
            with engine.connect() as conn:
                conn.execute(text(insert_sql), params)
                conn.commit()

            # 记录操作日志
            log = OperationLog(
                user_id=request.user_id,
                table_name=table_name,
                operation_type='create',
                record_id=record_data.get('任务号', ''),
                old_value=None,
                new_value=json.dumps(record_data, ensure_ascii=False)
            )
            session.add(log)
            session.commit()

            return jsonify({'message': '新增成功', 'task_number': record_data.get('任务号')}), 201

        except Exception as e:
            session.rollback()
            print(f"Error in create_data_edit_record: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/data-edit/record/<task_number>', methods=['PUT'])
    @admin_required
    def update_data_edit_record(task_number):
        """修改记录"""
        session = Session()
        try:
            data = request.get_json()
            table_name = data.get('table_name')
            new_data = data.get('record_data', {})

            if not table_name:
                return jsonify({'error': '请选择数据表'}), 400

            # 检查表是否存在
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return jsonify({'error': '数据表不存在'}), 400

            columns = [col['name'] for col in inspector.get_columns(table_name)]

            # 查询原数据
            with engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT * FROM `{table_name}` WHERE `任务号` = :task_number"),
                    {'task_number': task_number}
                )
                row = result.fetchone()
                if not row:
                    return jsonify({'error': '记录不存在'}), 404

                # 转换为字典
                old_data = dict(zip(columns, row))

            # 构建更新SQL
            set_clauses = []
            params = {'task_number': task_number}
            for key, value in new_data.items():
                if key in columns and key != '任务号':  # 任务号不允许修改
                    set_clauses.append(f"`{key}` = :{key}")
                    params[key] = value

            if not set_clauses:
                return jsonify({'error': '没有需要更新的字段'}), 400

            update_sql = f"UPDATE `{table_name}` SET {', '.join(set_clauses)} WHERE `任务号` = :task_number"
            with engine.connect() as conn:
                conn.execute(text(update_sql), params)
                conn.commit()

            # 记录操作日志
            log = OperationLog(
                user_id=request.user_id,
                table_name=table_name,
                operation_type='update',
                record_id=task_number,
                old_value=json.dumps(old_data, ensure_ascii=False, default=str),
                new_value=json.dumps(new_data, ensure_ascii=False)
            )
            session.add(log)
            session.commit()

            return jsonify({'message': '修改成功'}), 200

        except Exception as e:
            session.rollback()
            print(f"Error in update_data_edit_record: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/data-edit/record/<task_number>', methods=['DELETE'])
    @admin_required
    def delete_data_edit_record(task_number):
        """删除单条记录"""
        session = Session()
        try:
            table_name = request.args.get('table_name')
            if not table_name:
                return jsonify({'error': '请选择数据表'}), 400

            # 检查表是否存在
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return jsonify({'error': '数据表不存在'}), 400

            columns = [col['name'] for col in inspector.get_columns(table_name)]

            # 查询原数据
            with engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT * FROM `{table_name}` WHERE `任务号` = :task_number"),
                    {'task_number': task_number}
                )
                row = result.fetchone()
                if not row:
                    return jsonify({'error': '记录不存在'}), 404

                old_data = dict(zip(columns, row))

            # 删除记录
            with engine.connect() as conn:
                conn.execute(
                    text(f"DELETE FROM `{table_name}` WHERE `任务号` = :task_number"),
                    {'task_number': task_number}
                )
                conn.commit()

            # 记录操作日志
            log = OperationLog(
                user_id=request.user_id,
                table_name=table_name,
                operation_type='delete',
                record_id=task_number,
                old_value=json.dumps(old_data, ensure_ascii=False, default=str),
                new_value=None
            )
            session.add(log)
            session.commit()

            return jsonify({'message': '删除成功'}), 200

        except Exception as e:
            session.rollback()
            print(f"Error in delete_data_edit_record: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/data-edit/batch-delete', methods=['POST'])
    @admin_required
    def batch_delete_data_edit_records():
        """批量删除记录"""
        session = Session()
        try:
            data = request.get_json()
            table_name = data.get('table_name')
            task_numbers = data.get('task_numbers', [])

            if not table_name:
                return jsonify({'error': '请选择数据表'}), 400

            if not task_numbers:
                return jsonify({'error': '请选择要删除的记录'}), 400

            # 检查表是否存在
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return jsonify({'error': '数据表不存在'}), 400

            # 批量删除
            placeholders = ', '.join([f':tn{i}' for i in range(len(task_numbers))])
            params = {f'tn{i}': tn for i, tn in enumerate(task_numbers)}
            
            delete_sql = f"DELETE FROM `{table_name}` WHERE `任务号` IN ({placeholders})"
            with engine.connect() as conn:
                conn.execute(text(delete_sql), params)
                conn.commit()

            # 记录操作日志
            for task_number in task_numbers:
                log = OperationLog(
                    user_id=request.user_id,
                    table_name=table_name,
                    operation_type='delete',
                    record_id=task_number,
                    old_value=None,
                    new_value=None
                )
                session.add(log)
            session.commit()

            return jsonify({'message': f'成功删除 {len(task_numbers)} 条记录'}), 200

        except Exception as e:
            session.rollback()
            print(f"Error in batch_delete_data_edit_records: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/data-edit/batch-update', methods=['POST'])
    @admin_required
    def batch_update_data_edit_records():
        """批量更新记录"""
        session = Session()
        try:
            data = request.get_json()
            table_name = data.get('table_name')
            updates = data.get('updates', [])

            if not table_name:
                return jsonify({'error': '请选择数据表'}), 400

            if not updates:
                return jsonify({'error': '请选择要更新的记录'}), 400

            # 检查表是否存在
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return jsonify({'error': '数据表不存在'}), 400

            columns = [col['name'] for col in inspector.get_columns(table_name)]

            # 批量更新
            updated_count = 0
            for update in updates:
                task_number = update.get('task_number')
                new_data = update.get('data', {})

                if not task_number or not new_data:
                    continue

                set_clauses = []
                params = {'task_number': task_number}
                for key, value in new_data.items():
                    if key in columns and key != '任务号':
                        set_clauses.append(f"`{key}` = :{key}")
                        params[key] = value

                if set_clauses:
                    update_sql = f"UPDATE `{table_name}` SET {', '.join(set_clauses)} WHERE `任务号` = :task_number"
                    with engine.connect() as conn:
                        conn.execute(text(update_sql), params)
                        conn.commit()
                    updated_count += 1

            return jsonify({'message': f'成功更新 {updated_count} 条记录'}), 200

        except Exception as e:
            session.rollback()
            print(f"Error in batch_update_data_edit_records: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 操作日志接口
    @app.route('/api/operation-logs', methods=['GET'])
    @admin_required
    def get_operation_logs():
        """获取操作日志"""
        session = Session()
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            table_name = request.args.get('table_name')

            query = session.query(OperationLog)
            if table_name:
                query = query.filter_by(table_name=table_name)

            total = query.count()
            logs = query.order_by(OperationLog.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()

            logs_list = []
            for log in logs:
                logs_list.append({
                    'id': log.id,
                    'user_id': log.user_id,
                    'table_name': log.table_name,
                    'operation_type': log.operation_type,
                    'record_id': log.record_id,
                    'old_value': log.old_value,
                    'new_value': log.new_value,
                    'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else None
                })

            session.commit()
            return jsonify({
                'logs': logs_list,
                'total': total,
                'page': page,
                'per_page': per_page
            }), 200
        except Exception as e:
            session.rollback()
            print(f"Error in get_operation_logs: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
