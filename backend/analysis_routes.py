# -*- coding: utf-8 -*-
"""数据分析路由模块 - 数据分析、图表生成、AI相关"""
import json
import os
from flask import request, jsonify
import pandas as pd
from sqlalchemy import text
from helpers import protected, convert_nan_to_null, call_llm_api

def register_analysis_routes(app, Session, engine):
    """注册数据分析相关路由"""
    
    @app.route('/api/analyze', methods=['POST'])
    @protected
    def analyze():
        try:
            data = request.json
            table_name = data.get('table_name')
            analysis_type = data.get('analysis_type')
            month = data.get('month', '')  # 新增：月份筛选

            if not table_name or not analysis_type:
                return jsonify({'error': 'Missing table_name or analysis_type'}), 400

            # 从数据库读取数据
            df = pd.read_sql_table(table_name, engine)

            # 月份筛选
            if month:
                month_col = None
                for col in ['月份', 'data_month']:
                    if col in df.columns:
                        month_col = col
                        break
                if month_col:
                    df = df[df[month_col] == month]
                    print(f"[数据分析] 筛选月份 {month}，剩余 {len(df)} 条数据")

            # 基础结果
            result = {
                'table_name': table_name,
                'analysis_type': analysis_type,
                'data_summary': f'Table has {len(df)} rows and {len(df.columns)} columns',
                'columns': df.columns.tolist(),
                'sample_data': df.head(5).to_dict('records')
            }
            
            # 案件时间分析
            if analysis_type == 'time_analysis':
                # 生成分析提示
                prompt = f"数据表 {table_name} 包含以下关键字段：\n"
                prompt += f"- 上报时间：案件的上报时间\n"
                prompt += f"- 小类名称：案件的具体类型\n"
                prompt += f"- 提取的道路名称：案件发生的位置\n"
                prompt += f"数据总量：{len(df)} 条记录\n"
                
                # 重点分析字段
                key_fields = {
                    '上报时间': None,
                    '小类名称': None,
                    '提取的道路名称': None
                }
                
                # 查找关键字段
                for col in df.columns:
                    col_lower = col.lower()
                    if '上报' in col:
                        # 优先匹配「上报时间」字段
                        key_fields['上报时间'] = col
                    elif '小类' in col or '类型' in col_lower:
                        key_fields['小类名称'] = col
                    elif '道路' in col or '路名' in col or '街' in col:
                        key_fields['提取的道路名称'] = col
                
                # 如果没有找到上报时间，再尝试其他时间字段
                if not key_fields['上报时间']:
                    for col in df.columns:
                        if '时间' in col:
                            key_fields['上报时间'] = col
                            break
                
                # 保存原始数据副本
                original_df = df.copy()
                
                # 分析上报时间
                time_col = key_fields['上报时间']
                if time_col:
                    try:
                        # 处理各种时间格式，包括非标准格式
                        def parse_time_string(time_str):
                            if not time_str:
                                return pd.NaT
                            
                            if isinstance(time_str, str):
                                # 处理 GMT 格式：Wed, 31 Dec 2025 15:02:18 GMT
                                if 'GMT' in time_str:
                                    try:
                                        # 移除星期和 GMT 时区
                                        time_str = time_str.split(', ')[1].replace(' GMT', '')
                                        # 转换为标准格式
                                        return pd.to_datetime(time_str, format='%d %b %Y %H:%M:%S')
                                    except:
                                        pass
                                
                                # 处理相对时间格式：1小时55分18秒
                                if any(unit in time_str for unit in ['小时', '分', '秒']):
                                    # 对于相对时间，返回 NaT，因为无法转换为绝对时间
                                    return pd.NaT
                                
                                # 尝试多种标准格式
                                formats = ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y']
                                for fmt in formats:
                                    try:
                                        return pd.to_datetime(time_str, format=fmt)
                                    except:
                                        pass
                            
                            # 最后的尝试，让 pandas 自动解析
                            try:
                                return pd.to_datetime(time_str)
                            except:
                                return pd.NaT
                        
                        # 应用时间解析函数
                        df[time_col] = df[time_col].apply(parse_time_string)
                        
                        # 移除无法解析的时间值
                        original_count = len(df)
                        df = df.dropna(subset=[time_col])
                        valid_count = len(df)
                        
                        # 添加数据统计信息
                        prompt += f"\n数据统计信息：\n"
                        prompt += f"总记录数：{original_count}\n"
                        prompt += f"有效时间记录数：{valid_count}\n"
                        prompt += f"时间解析成功率：{valid_count/original_count:.2%}\n"
                        
                        if valid_count > 0:
                            # 统一转换为 YYYY-MM-DD HH:MM:SS 格式
                            df[time_col] = df[time_col].dt.strftime('%Y-%m-%d %H:%M:%S')
                            # 重新转换为 datetime 类型以提取特征
                            df[time_col] = pd.to_datetime(df[time_col])
                            
                            # 提取时间特征
                            df['day'] = df[time_col].dt.day
                            df['hour'] = df[time_col].dt.hour
                            
                            # 日案件量趋势
                            daily_counts = df.groupby('day').size().reset_index(name='count')
                            prompt += f"\n日案件量趋势：\n{daily_counts.to_string(index=False)}"
                            
                            # 高峰时段分析（小时级）
                            hourly_counts = df.groupby('hour').size().reset_index(name='count')
                            prompt += f"\n小时级高峰时段分析：\n{hourly_counts.to_string(index=False)}"
                            
                            # 计算高峰时段
                            peak_hours = hourly_counts.sort_values('count', ascending=False).head(3)
                            prompt += f"\nTop 3 高峰时段：\n{peak_hours.to_string(index=False)}"
                            
                            # 添加图表数据到结果
                            result['chart_data'] = {
                                'daily': daily_counts.to_dict('records'),
                                'hourly': hourly_counts.to_dict('records'),
                                'peak_hours': peak_hours.to_dict('records')
                            }
                        else:
                            prompt += "\n警告：所有时间值均无法解析，无法进行时间维度分析。\n"
                            # 使用原始数据进行其他分析
                            df = original_df
                        
                    except Exception as e:
                        prompt += f"\n时间列转换失败：{str(e)}"
                        # 即使时间处理失败，也要添加基本数据统计
                        prompt += f"\n基本数据统计：\n总记录数：{len(df)}\n"
                
                # 分析小类名称
                category_col = key_fields['小类名称']
                if category_col:
                    try:
                        category_counts = df[category_col].value_counts().head(10).reset_index()
                        category_counts.columns = [category_col, 'count']
                        prompt += f"\n案件类型分布（前10）：\n{category_counts.to_string(index=False)}"
                    except Exception as e:
                        prompt += f"\n类型分析失败：{str(e)}"
                
                # 分析道路名称
                road_col = key_fields['提取的道路名称']
                if road_col:
                    try:
                        road_counts = df[road_col].value_counts().head(10).reset_index()
                        road_counts.columns = [road_col, 'count']
                        prompt += f"\n案件高发区域（前10）：\n{road_counts.to_string(index=False)}"
                    except Exception as e:
                        prompt += f"\n区域分析失败：{str(e)}"
                
                # 调用豆包大模型
                # 调整提示词，只关注日案件量趋势和高峰时段分析
                analysis_result = call_llm_api(
                    api_url='https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    api_key='58a51ac5-3b75-4c5e-85ac-1fb4ef652bd0',
                    model='doubao-seed-1-8-251228',
                    messages=[{"role": "user", "content": prompt}],
                    provider_name="数据分析"
                )
                result['analysis'] = analysis_result[1] if analysis_result[0] else f"分析失败: {analysis_result[1]}"
            
            # 转换NaN值为null值，确保JSON响应有效
            result = convert_nan_to_null(result)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

#     # CMS栏目相关API
#     @app.route('/api/categories', methods=['GET'])
#     @protected
#     def get_categories():
#         # 创建新的session实例
#         session = Session()
#         try:
#             # 获取所有栏目，按排序字段排序
#             from models import Category
#             categories = session.query(Category).order_by(Category.order).all()
#             
#             # 转换为字典列表
#             categories_list = []
#             for category in categories:
#                 categories_list.append({
#                     'id': category.id,
#                     'name': category.name,
#                     'slug': category.slug,
#                     'description': category.description,
#                     'order': category.order,
#                     'created_at': category.created_at.strftime('%Y-%m-%d %H:%M:%S') if category.created_at else None,
#                     'updated_at': category.updated_at.strftime('%Y-%m-%d %H:%M:%S') if category.updated_at else None
#                 })
#             
#             session.commit()
#             return jsonify({'categories': categories_list}), 200
#         except Exception as e:
#             session.rollback()
#             return jsonify({'error': str(e)}), 500
#         finally:
#             session.close()

    # 小工具模块API - 自然语言查询转换为SQL
    @app.route('/api/tools/natural-language-query', methods=['POST'])
    @protected
    def natural_language_query():
        try:
            data = request.json
            query = data.get('query')
            table_name = data.get('table_name')

            if not query or not table_name:
                return jsonify({'error': 'Missing query or table_name'}), 400

            # 使用大模型将自然语言转换为SQL
            prompt = f"你是一个SQL专家。请将以下自然语言查询转换为MySQL SQL语句。\n\n"
            prompt += f"表名: {table_name}\n"
            prompt += f"查询: {query}\n\n"
            prompt += f"要求:\n"
            prompt += f"1. 只返回SQL语句，不要其他内容\n"
            prompt += f"2. 使用MySQL语法\n"
            prompt += f"3. 如果查询不明确，返回最可能的SQL\n"

            result = call_llm_api(
                api_url='https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                api_key='58a51ac5-3b75-4c5e-85ac-1fb4ef652bd0',
                model='doubao-seed-1-8-251228',
                messages=[{"role": "user", "content": prompt}],
                provider_name="自然语言查询"
            )
            
            if result[0]:
                sql = result[1].strip()
                # 移除可能的markdown代码块标记
                if sql.startswith('```'):
                    sql = sql.split('\n', 1)[1] if '\n' in sql else sql[3:]
                if sql.endswith('```'):
                    sql = sql[:-3]
                sql = sql.strip()
                
                # 执行SQL查询
                session = Session()
                try:
                    query_result = session.execute(text(sql))
                    columns = query_result.keys()
                    rows = query_result.fetchall()
                    
                    # 转换为字典列表
                    data_list = []
                    for row in rows:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            row_dict[col] = row[i]
                        data_list.append(row_dict)
                    
                    return jsonify({
                        'sql': sql,
                        'data': data_list,
                        'columns': list(columns),
                        'row_count': len(data_list)
                    }), 200
                except Exception as e:
                    return jsonify({
                        'sql': sql,
                        'error': f'SQL执行失败: {str(e)}'
                    }), 200
                finally:
                    session.close()
            else:
                return jsonify({'error': f'大模型调用失败: {result[1]}'}), 500
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # 数据脱敏字段配置接口
    @app.route('/api/tools/data-desensitization/fields', methods=['POST'])
    @protected
    def get_desensitization_fields():
        try:
            data = request.json
            table_name = data.get('table_name')

            if not table_name:
                return jsonify({'error': 'Missing table_name'}), 400

            # 获取表结构
            inspector = pd.io.sql.SQLAlchemyEngine(engine).inspect()
            columns = inspector.get_columns(table_name)
            
            # 分析每个字段，推荐脱敏方式
            fields_config = {}
            for col in columns:
                col_name = col['name']
                col_type = str(col['type'])
                
                # 根据字段名和类型推荐脱敏方式
                if '电话' in col_name or '手机' in col_name or 'phone' in col_name.lower():
                    fields_config[col_name] = 'phone'
                elif '姓名' in col_name or '名字' in col_name or 'name' in col_name.lower():
                    fields_config[col_name] = 'name'
                elif '地址' in col_name or '位置' in col_name or 'address' in col_name.lower():
                    fields_config[col_name] = 'address'
                elif '问题' in col_name and '描述' in col_name:
                    fields_config[col_name] = 'problem_description'
            
            return jsonify({'fields': fields_config}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # 数据脱敏处理接口
    @app.route('/api/tools/data-desensitization', methods=['POST'])
    @protected
    def process_desensitization():
        try:
            data = request.json
            table_name = data.get('table_name')
            fields_config = data.get('fields_config', {})

            if not table_name:
                return jsonify({'error': 'Missing table_name'}), 400

            # 从数据库读取数据
            df = pd.read_sql_table(table_name, engine)

            # 应用脱敏处理
            from helpers import clean_and_desensitize_data
            result_df = clean_and_desensitize_data(df, fields_config)

            # 返回处理后的数据（不写入数据库）
            result_data = result_df.head(100).to_dict('records')
            
            return jsonify({
                'data': result_data,
                'total_rows': len(result_df),
                'columns': result_df.columns.tolist()
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
