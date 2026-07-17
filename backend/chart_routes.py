# -*- coding: utf-8 -*-
"""图表分析路由模块"""
import pandas as pd
from flask import request, jsonify

try:
    from common import engine as _engine, protected as _protected
except ImportError:
    _engine = None
    from helpers import protected as _protected

def register_chart_routes(app, engine=None, protected=None):
    engine = engine or _engine
    protected = protected or _protected
    """注册图表分析相关路由"""

    @app.route('/api/chart-analysis', methods=['POST'])
    @protected
    def chart_analysis():
        """图表分析API - 根据数据表生成仪表盘数据"""
        try:
            data = request.json
            table_name = data.get('table_name')
            month = data.get('month', '')

            if not table_name:
                return jsonify({'error': 'Missing table_name parameter'}), 400

            print(f"[图表分析] 开始分析数据表: {table_name}, 月份: {month}")

            # 从数据库读取数据
            df = pd.read_sql_table(table_name, engine)
            total_count = len(df)

            # 月份筛选
            if month:
                month_col = None
                for col in ['月份', 'data_month', 'month']:
                    if col in df.columns:
                        month_col = col
                        break
                if month_col:
                    print(f"[图表分析] 找到月份列: {month_col}, 筛选值: {month}")
                    print(f"[图表分析] 筛选前月份值分布: {df[month_col].value_counts().head()}")
                    df = df[df[month_col] == month]
                    print(f"[图表分析] 筛选月份 {month}，剩余 {len(df)} 条数据")
                else:
                    print(f"[图表分析] 未找到月份列，列名: {list(df.columns)}")

            filtered_count = len(df)

            if filtered_count == 0:
                return jsonify({'error': '筛选后数据为空'}), 400

            print(f"[图表分析] 数据总量: {total_count}, 筛选后: {filtered_count} 条")

            # 初始化结果
            result = {
                'total_count': total_count,
                'filtered_count': filtered_count,
                'month': month,
                'charts': {}
            }

            # 1. 问题来源分布（饼状图）
            source_col = None
            for col in ['问题来源', 'source', '案件来源']:
                if col in df.columns:
                    source_col = col
                    break
            if source_col:
                source_data = df[source_col].fillna('未知').value_counts()
                result['charts']['source_pie'] = {
                    'title': '问题来源分布',
                    'type': 'pie',
                    'data': [{'name': str(k), 'value': int(v)} for k, v in source_data.items()]
                }

            # 2. 问题类型分布（饼状图）
            problem_type_col = None
            for col in ['问题类型', 'problem_type', '案件类型']:
                if col in df.columns:
                    problem_type_col = col
                    break
            if problem_type_col:
                type_data = df[problem_type_col].fillna('未知').value_counts()
                result['charts']['type_pie'] = {
                    'title': '问题类型分布',
                    'type': 'pie',
                    'data': [{'name': str(k), 'value': int(v)} for k, v in type_data.items()]
                }

            # 3. 大类名称占比图（横向柱状图）
            major_cat_col = None
            for col in ['大类名称', 'major_category', '大类']:
                if col in df.columns:
                    major_cat_col = col
                    break
            if major_cat_col:
                major_data = df[major_cat_col].fillna('未知').value_counts().head(15)
                result['charts']['major_category'] = {
                    'title': '大类案件分布',
                    'type': 'bar',
                    'data': {'categories': [str(k) for k in major_data.index], 'values': [int(v) for v in major_data.values]}
                }

            # 4. 小类名称分布图（横向柱状图）
            minor_cat_col = None
            for col in ['小类名称', 'minor_category', '小类']:
                if col in df.columns:
                    minor_cat_col = col
                    break
            if minor_cat_col:
                minor_data = df[minor_cat_col].fillna('未知').value_counts().head(20)
                result['charts']['minor_category'] = {
                    'title': '小类案件分布',
                    'type': 'bar',
                    'data': {'categories': [str(k) for k in minor_data.index], 'values': [int(v) for v in minor_data.values]}
                }

            # 5. 所属片区分布图（饼状图）
            area_col = None
            for col in ['所属片区', '所属区域', 'area', '片区']:
                if col in df.columns:
                    area_col = col
                    break
            if area_col:
                area_data = df[area_col].fillna('未知').value_counts()
                result['charts']['area_pie'] = {
                    'title': '案件采集片区分布',
                    'type': 'pie',
                    'data': [{'name': str(k), 'value': int(v)} for k, v in area_data.items()]
                }

            # 6. 所属街道分布图（横向柱状图）
            street_col = None
            for col in ['所属街道', 'street', '街道']:
                if col in df.columns:
                    street_col = col
                    break
            if street_col:
                street_data = df[street_col].fillna('未知').value_counts()
                result['charts']['street'] = {
                    'title': '案件街道分布',
                    'type': 'bar',
                    'data': {'categories': [str(k) for k in street_data.index], 'values': [int(v) for v in street_data.values]}
                }

            # 7. 所属社区分布图（横向柱状图）
            community_col = None
            for col in ['所属社区', 'community', '社区']:
                if col in df.columns:
                    community_col = col
                    break
            if community_col:
                community_data = df[community_col].fillna('未知').value_counts().head(25)
                result['charts']['community'] = {
                    'title': '案件社区分布',
                    'type': 'bar',
                    'data': {'categories': [str(k) for k in community_data.index], 'values': [int(v) for v in community_data.values]}
                }

            # 8. 处置部门案件占比图（饼状图）
            dept_col = None
            for col in ['处置部门', 'department', '处理部门', '责任部门']:
                if col in df.columns:
                    dept_col = col
                    break
            if dept_col:
                dept_data = df[dept_col].fillna('未知').value_counts()
                result['charts']['department_pie'] = {
                    'title': '处置部门案件占比',
                    'type': 'pie',
                    'data': [{'name': str(k), 'value': int(v)} for k, v in dept_data.items()]
                }

            # 9. 各处置部门平均处置时间图（横向柱状图）
            close_time_col = None
            for col in ['结案时间', 'close_time', 'handle_time', '完成时间']:
                if col in df.columns:
                    close_time_col = col
                    break

            report_time_col = None
            for col in ['上报时间', 'report_time', '创建时间']:
                if col in df.columns:
                    report_time_col = col
                    break

            if close_time_col and report_time_col and dept_col:
                try:
                    df['_close_time'] = pd.to_datetime(df[close_time_col], errors='coerce')
                    df['_report_time'] = pd.to_datetime(df[report_time_col], errors='coerce')
                    df['_handling_hours'] = (df['_close_time'] - df['_report_time']).dt.total_seconds() / 3600

                    valid_df = df[(df['_handling_hours'] > 0) & (df['_handling_hours'] < 720)]
                    if len(valid_df) > 0:
                        avg_time_by_dept = valid_df.groupby(dept_col)['_handling_hours'].mean().sort_values()
                        result['charts']['avg_handling_time'] = {
                            'title': '各处置部门平均处置时间',
                            'type': 'bar',
                            'data': {
                                'categories': [str(k) for k in avg_time_by_dept.index],
                                'values': [round(v, 1) for v in avg_time_by_dept.values]
                            },
                            'unit': '小时'
                        }
                except Exception as e:
                    print(f"[图表分析] 计算处置时间出错: {str(e)}")

            print(f"[图表分析] 分析完成，生成 {len(result['charts'])} 个图表")
            return jsonify(result), 200

        except Exception as e:
            print(f"Error in chart_analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
