# -*- coding: utf-8 -*-
"""数据上传路由模块 - Excel上传、文件上传、图片上传"""
import os
import uuid
from flask import request, jsonify
import pandas as pd
from sqlalchemy import text, inspect
from helpers import admin_required

def register_upload_routes(app, Session, engine):
    """注册数据上传相关路由"""
    
    @app.route('/api/upload', methods=['POST'])
    @admin_required
    def upload_file():
        session = Session()
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            if file and file.filename.endswith('.xlsx'):
                # 读取Excel文件
                df = pd.read_excel(file)
                
                # 用文件名作为表名（去除.xlsx后缀）
                table_name = os.path.splitext(file.filename)[0]
                
                # 写入数据库
                df.to_sql(table_name, engine, if_exists='replace', index=False)
                
                session.commit()
                return jsonify({'message': 'File uploaded successfully', 'table_name': table_name}), 200
            else:
                return jsonify({'error': 'Only Excel files are allowed'}), 400
        except Exception as e:
            session.rollback()
            print(f"Error in upload_file: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 追加数据到现有表接口
    @app.route('/api/append-data', methods=['POST'])
    @admin_required
    def append_data():
        """追加Excel数据到现有表"""
        session = Session()
        try:
            if 'file' not in request.files:
                return jsonify({'error': '没有文件'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': '未选择文件'}), 400

            if not file.filename.endswith('.xlsx'):
                return jsonify({'error': '只支持Excel文件'}), 400

            # 获取参数
            target_table = request.form.get('target_table')
            data_month = request.form.get('data_month', '')

            if not target_table:
                return jsonify({'error': '未指定目标表'}), 400

            # 读取Excel文件
            df = pd.read_excel(file)

            # 检查目标表是否存在
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()

            if target_table not in existing_tables:
                return jsonify({'error': f'目标表 {target_table} 不存在'}), 400

            # 获取目标表的列结构
            existing_columns = [col['name'] for col in inspector.get_columns(target_table)]

            # 检查是否有月份列，如果有则添加月份值
            has_month_column = '月份' in existing_columns or 'data_month' in existing_columns
            month_column_name = '月份' if '月份' in existing_columns else 'data_month' if 'data_month' in existing_columns else None

            # 新增的列（Excel有但表没有的）
            new_columns = [col for col in df.columns if col not in existing_columns]

            # 添加新列到表
            if new_columns:
                for col in new_columns:
                    col_type = 'TEXT'  # 默认使用TEXT类型
                    session.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `{col}` {col_type}"))
                session.commit()
                print(f"添加了新列: {new_columns}")

            # 准备数据
            df_to_insert = df.copy()

            # 添加月份值
            if month_column_name and data_month:
                df_to_insert[month_column_name] = data_month

            # 获取更新后的列列表
            updated_columns = [col['name'] for col in inspector.get_columns(target_table)]

            # 只保留目标表中存在的列
            common_columns = [col for col in df_to_insert.columns if col in updated_columns]
            df_to_insert = df_to_insert[common_columns]

            # 追加数据到表
            df_to_insert.to_sql(target_table, engine, if_exists='append', index=False)

            inserted_count = len(df_to_insert)

            return jsonify({
                'message': f'成功追加 {inserted_count} 条数据到表 {target_table}',
                'inserted_count': inserted_count,
                'new_columns': new_columns
            }), 200

        except Exception as e:
            session.rollback()
            print(f"Error in append_data: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # CMS文件上传接口
    @app.route('/api/upload/file', methods=['POST'])
    @admin_required
    def upload_cms_file():
        session = Session()
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            # 检查文件类型
            allowed_extensions = {'docx', 'pdf'}
            if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                return jsonify({'error': 'Only DOCX and PDF files are allowed'}), 400
            
            # 生成唯一文件名
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # 确保uploads目录存在
            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            # 保存文件
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            session.commit()
            # 返回文件路径（只返回相对路径）
            return jsonify({
                'file_path': f'uploads/{unique_filename}',
                'filename': file.filename
            }), 200
        except Exception as e:
            session.rollback()
            print(f"Error in upload_cms_file: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 图片上传接口（用于富文本编辑器）
    @app.route('/api/upload/image', methods=['POST'])
    @admin_required
    def upload_image():
        session = Session()
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            # 检查文件类型
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                return jsonify({'error': 'Only image files are allowed'}), 400
            
            # 生成唯一文件名
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # 确保uploads目录存在
            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            # 保存文件
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            session.commit()
            
            # TinyMCE需要的响应格式（返回相对路径）
            return jsonify({
                'location': f"/uploads/{unique_filename}"
            }), 200
        except Exception as e:
            session.rollback()
            print(f"Error in upload_image: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
