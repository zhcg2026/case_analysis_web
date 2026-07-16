# -*- coding: utf-8 -*-
"""视频报告相关路由和辅助函数"""
import os
import json
import re
import datetime
import base64
import tempfile
from io import BytesIO
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import request, jsonify, send_file
from helpers import protected, call_llm_api


def register_video_routes(app, engine):
    """注册视频报告相关路由"""


    @app.route('/api/smart-report', methods=['POST'])
    @protected
    def smart_report():
        """智能报告生成API"""
        try:
            import re

            data = request.json
            table_name = data.get('table_name')
            template_type = data.get('template_type')  # monthly_comparison, yearly_summary, special_analysis, full_analysis
            months = data.get('months', [])  # 月度对比：选中的月份列表
            year = data.get('year', '')  # 年度总结：选中的年份
            dimension = data.get('dimension', '')  # 专项分析：分析维度字段
            dimension_values = data.get('dimension_values', [])  # 专项分析：选中的值列表

            if not table_name or not template_type:
                return jsonify({'error': 'Missing required parameters'}), 400

            print(f"[智能报告] 开始生成报告, 表: {table_name}, 模板: {template_type}")

            # 从数据库读取数据
            df = pd.read_sql_table(table_name, engine)
            original_count = len(df)

            # 根据模板类型筛选数据
            filter_desc = ""
            if template_type == 'monthly_comparison' and months:
                month_col = None
                for col in ['月份', 'data_month']:
                    if col in df.columns:
                        month_col = col
                        break
                if month_col:
                    df = df[df[month_col].isin(months)]
                    filter_desc = f"筛选月份: {', '.join(months)}"

            elif template_type == 'yearly_summary' and year:
                # 从时间字段提取年份
                time_col = None
                for col in ['上报时间', '捆绑处置截止时间', 'created_time']:
                    if col in df.columns:
                        time_col = col
                        break
                if time_col:
                    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
                    df = df[df[time_col].dt.year == int(year)]
                    filter_desc = f"筛选年份: {year}年"

            elif template_type == 'special_analysis' and dimension and dimension_values:
                if dimension in df.columns:
                    df = df[df[dimension].isin(dimension_values)]
                    filter_desc = f"筛选{dimension}: {', '.join(dimension_values)}"

            filtered_count = len(df)
            print(f"[智能报告] 数据筛选: {original_count} -> {filtered_count} 条")

            if filtered_count == 0:
                return jsonify({'error': '筛选后无数据，请调整筛选条件'}), 400

            # ===== 生成图表 =====
            charts_base64 = generate_smart_report_charts(df, template_type, months, dimension, dimension_values)

            # ===== 调用LLM生成分析洞察 =====
            insights = generate_report_insights(df, template_type, months, year, dimension, dimension_values)

            # ===== 生成HTML报告 =====
            html_report = render_smart_report_html(
                df=df,
                template_type=template_type,
                months=months,
                year=year,
                dimension=dimension,
                dimension_values=dimension_values,
                charts_base64=charts_base64,
                insights=insights,
                filter_desc=filter_desc,
                original_count=original_count,
                filtered_count=filtered_count
            )

            print(f"[智能报告] 报告生成完成")
            return jsonify({'html': html_report}), 200

        except Exception as e:
            print(f"Error in smart_report: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500
    @app.route('/api/video-test', methods=['GET'])
    def video_test():
        """视频生成测试端点 - 不需要认证"""
        try:
            print("[视频测试] 开始测试...")

            from video_report import VideoReportGenerator
            from flask import send_file
            import tempfile

            # 创建测试视频
            generator = VideoReportGenerator()
            output_path = tempfile.mktemp(suffix='.mp4')

            # 模拟图表数据
            charts_data = []
            try:
                # 生成简单的测试图表
                import matplotlib.pyplot as plt
                import io
                import base64

                fig, ax = plt.subplots(figsize=(10, 6))
                ax.bar(['A', 'B', 'C'], [100, 150, 80])
                ax.set_title('测试图表')
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=100)
                buf.seek(0)
                img_b64 = base64.b64encode(buf.read()).decode('utf-8')
                charts_data.append(('测试图表', img_b64))
                plt.close(fig)
            except Exception as e:
                print(f"[视频测试] 图表生成失败: {e}")

            print("[视频测试] 生成视频...")
            video_path = generator.generate_video(
                report_title="测试报告",
                charts_data=charts_data,
                insights={'summary': '这是一个测试视频报告', 'key_findings': ['发现一：测试数据正常', '发现二：视频生成成功']},
                output_path=output_path
            )

            print(f"[视频测试] 视频生成完成: {video_path}")

            if video_path and os.path.exists(video_path):
                # 返回视频文件
                response = send_file(
                    video_path,
                    mimetype='video/mp4',
                    as_attachment=True,
                    download_name='test_report.mp4'
                )

                @response.call_on_close
                def cleanup():
                    try:
                        if os.path.exists(video_path):
                            os.remove(video_path)
                    except:
                        pass

                return response
            else:
                return jsonify({'success': False, 'error': '视频生成失败'})

        except Exception as e:
            print(f"[视频测试] 错误: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500
    @app.route('/api/video-debug', methods=['GET'])
    def video_debug():
        """视频报告调试端点 - 模拟完整流程，不需要认证"""
        try:
            print("[视频调试] 开始调试...")
            from video_report import VideoReportGenerator
            from flask import send_file
            import tempfile

            # 模拟真实请求参数
            table_name = 'cases'
            template_type = 'monthly_comparison'
            months = ['202603', '202602']

            print(f"[视频调试] 参数: table={table_name}, template={template_type}")
            report_title = f"{months[0]}与{months[1]}对比分析报告"

            # 测试数据库读取
            try:
                df = pd.read_sql_table(table_name, engine)
                print(f"[视频调试] 数据库读取成功: {len(df)} 条记录")
                print(f"[视频调试] 列名: {list(df.columns)}")
            except Exception as e:
                print(f"[视频调试] 数据库读取失败: {e}")
                import traceback
                traceback.print_exc()
                # 使用模拟数据继续测试
                df = pd.DataFrame({
                    '大类名称': ['市容环境', '市容环境', '市政设施'],
                    '所属片区': ['片区A', '片区B', '片区A'],
                    '当前阶段名称': ['[办结]', '[办结]', '处置中']
                })
                print(f"[视频调试] 使用模拟数据: {len(df)} 条")

            # 测试图表生成
            try:
                charts_base64 = generate_smart_report_charts(df, template_type, months, '', [])
                print(f"[视频调试] 图表生成成功: {len(charts_base64)} 个")
            except Exception as e:
                print(f"[视频调试] 图表生成失败: {e}")
                import traceback
                traceback.print_exc()
                charts_base64 = []

            # 测试洞察生成
            # 计算结案率
            if '当前阶段名称' in df.columns:
                completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
            else:
                completion_rate = 0

            insights = {
                'summary': f'共分析{len(df)}条数据',
                'key_findings': [],
                'chart_insights': {}
            }
            if '大类名称' in df.columns:
                top = df['大类名称'].value_counts().head(1)
                if len(top) > 0:
                    insights['key_findings'].append(f"主要问题: {top.index[0]}")

            # 为每个图表生成分析结论
            for chart_name, _ in charts_base64:
                if '综合仪表盘' in chart_name:
                    insight = f"综合仪表盘展示了整体数据概况。共{len(df)}条数据，结案率{completion_rate:.1f}%。"
                elif '案件总量对比' in chart_name:
                    insight = f"案件总量对比图表展示了两个月的数据对比情况。"
                elif '问题类型' in chart_name:
                    if '大类名称' in df.columns and len(df['大类名称'].value_counts()) > 0:
                        top = df['大类名称'].value_counts().head(3)
                        insight = f"问题类型分布显示，{top.index[0]}占比最高，共{top.values[0]}件。"
                    else:
                        insight = f"问题类型分布图表展示了各类问题的占比情况。"
                elif 'TOP10小类' in chart_name:
                    if '小类名称' in df.columns and len(df['小类名称'].value_counts()) > 0:
                        top5 = df['小类名称'].value_counts().head(3)
                        insight = f"排名前五的小类问题分别是：{top5.index[0]}、{top5.index[1] if len(top5)>1 else ''}等。"
                    else:
                        insight = f"排名图表展示了高频小类问题的分布情况。"
                elif '片区案件' in chart_name:
                    if '所属片区' in df.columns and len(df['所属片区'].value_counts()) > 0:
                        top = df['所属片区'].value_counts().head(3)
                        insight = f"片区案件分布显示，{top.index[0]}案件最多，共{top.values[0]}件。"
                    else:
                        insight = f"片区案件分布图表展示了各区域的案件分布情况。"
                elif '问题来源' in chart_name:
                    if '问题来源' in df.columns and len(df['问题来源'].value_counts()) > 0:
                        top = df['问题来源'].value_counts().head(3)
                        insight = f"问题来源分布显示，主要来源为{top.index[0]}。"
                    else:
                        insight = f"问题来源分布图表展示了案件的来源渠道。"
                elif '街道案件' in chart_name:
                    if '所属街道' in df.columns and len(df['所属街道'].value_counts()) > 0:
                        top = df['所属街道'].value_counts().head(3)
                        insight = f"街道案件分布显示，{top.index[0]}案件最多。"
                    else:
                        insight = f"街道案件分布图表展示了各街道的案件分布情况。"
                elif '处置部门' in chart_name:
                    if '处置部门' in df.columns and len(df['处置部门'].value_counts()) > 0:
                        top = df['处置部门'].value_counts().head(3)
                        insight = f"处置部门排名显示，{top.index[0]}处理案件最多。"
                    else:
                        insight = f"处置部门排名图表展示了各部门的工作量。"
                elif '案件状态' in chart_name:
                    insight = f"案件状态分布显示，已办结{(df['当前阶段名称'] == '[办结]').sum() if '当前阶段名称' in df.columns else 0}件。"
                else:
                    insight = f"该图表展示了数据分析结果。"
                insights['chart_insights'][chart_name] = insight
                print(f"[视频调试] 图表分析 {chart_name}: {insight[:40]}...")

            print(f"[视频调试] 洞察生成完成")

            # 测试视频生成
            print("[视频调试] 开始生成视频...")
            generator = VideoReportGenerator()
            output_path = tempfile.mktemp(suffix='.mp4')

            video_path = generator.generate_video(
                report_title=report_title,
                charts_data=charts_base64,
                insights=insights,
                output_path=output_path
            )

            print(f"[视频调试] 视频完成: {video_path}, 大小: {os.path.getsize(video_path) if video_path else 0}")

            if video_path and os.path.exists(video_path):
                response = send_file(
                    video_path,
                    mimetype='video/mp4',
                    as_attachment=True,
                    download_name='debug_report.mp4'
                )
                @response.call_on_close
                def cleanup():
                    try:
                        if os.path.exists(video_path):
                            os.remove(video_path)
                    except:
                        pass
                return response
            else:
                return jsonify({'error': '视频生成失败'}), 500

        except Exception as e:
            print(f"[视频调试] 总错误: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500
    @app.route('/api/video-report', methods=['POST'])
    @protected
    def video_report():
        """
        视频报告生成API
        将智能报告转化为视频报告
        """
        try:
            from video_report import VideoReportGenerator
            from flask import send_file
            import tempfile

            data = request.json
            table_name = data.get('table_name')
            template_type = data.get('template_type')
            months = data.get('months', [])
            year = data.get('year', '')
            dimension = data.get('dimension', '')
            dimension_values = data.get('dimension_values', [])

            print(f"[视频报告] 请求参数: table={table_name}, template={template_type}, months={months}")

            if not table_name or not template_type:
                return jsonify({'error': 'Missing required parameters'}), 400

            print(f"[视频报告] 开始生成视频, 表: {table_name}, 模板: {template_type}")

            # 从数据库读取数据
            try:
                df = pd.read_sql_table(table_name, engine)
                original_count = len(df)
                print(f"[视频报告] 读取数据: {original_count} 条")
            except Exception as e:
                print(f"[视频报告] 数据库读取失败: {e}")
                return jsonify({'error': f'数据库读取失败: {str(e)}'}), 500

            # 根据模板类型筛选数据
            filter_desc = ""
            if template_type == 'monthly_comparison' and months:
                month_col = None
                for col in ['月份', 'data_month']:
                    if col in df.columns:
                        month_col = col
                        break
                if month_col:
                    df = df[df[month_col].isin(months)]
                    filter_desc = f"筛选月份: {', '.join(months)}"

            elif template_type == 'yearly_summary' and year:
                time_col = None
                for col in ['上报时间', '捆绑处置截止时间', 'created_time']:
                    if col in df.columns:
                        time_col = col
                        break
                if time_col:
                    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
                    df = df[df[time_col].dt.year == int(year)]
                    filter_desc = f"筛选年份: {year}年"

            elif template_type == 'special_analysis' and dimension and dimension_values:
                if dimension in df.columns:
                    df = df[df[dimension].isin(dimension_values)]
                    filter_desc = f"筛选{dimension}: {', '.join(dimension_values)}"

            filtered_count = len(df)
            print(f"[视频报告] 数据筛选: {original_count} -> {filtered_count} 条")

            if filtered_count == 0:
                return jsonify({'error': '筛选后无数据，请调整筛选条件'}), 400

            # 生成图表（带错误处理）
            try:
                charts_base64 = generate_smart_report_charts(df, template_type, months, dimension, dimension_values)
                print(f"[视频报告] 图表生成完成: {len(charts_base64)} 个")
            except Exception as e:
                print(f"[视频报告] 图表生成失败: {e}")
                charts_base64 = []

            # 生成洞察（带错误处理，简化）
            try:
                # 简化洞察生成，不调用LLM
                insights = {
                    'summary': f'共分析{filtered_count}条数据' + (f'，{filter_desc}' if filter_desc else ''),
                    'key_findings': [],
                    'chart_insights': {}  # 图表分析结论
                }

                # 添加基本统计发现
                if '大类名称' in df.columns:
                    top_type = df['大类名称'].value_counts().head(1)
                    if len(top_type) > 0:
                        insights['key_findings'].append(f"主要问题类型: {top_type.index[0]}, 共{top_type.values[0]}件")

                if '所属片区' in df.columns:
                    top_district = df['所属片区'].value_counts().head(1)
                    if len(top_district) > 0:
                        insights['key_findings'].append(f"案件集中区域: {top_district.index[0]}, 共{top_district.values[0]}件")

                # 计算结案率
                if '当前阶段名称' in df.columns:
                    completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
                else:
                    completion_rate = 0

                # 判断是否月度对比模式
                is_monthly_comparison = template_type == 'monthly_comparison' and months and len(months) >= 2

                # 为每个图表生成分析结论
                for chart_name, _ in charts_base64:
                    chart_display = chart_name
                    if len(chart_name) > 3 and chart_name[2] == '_':
                        chart_display = chart_name[3:]

                    # 根据图表名称精确匹配
                    if '综合仪表盘' in chart_name:
                        insight = f"综合仪表盘展示了整体数据概况。共{filtered_count}条数据，结案率{completion_rate:.1f}%。"
                    elif '案件总量对比' in chart_name:
                        if is_monthly_comparison and months:
                            insight = f"案件总量对比图表展示了两个月的数据对比情况。左侧为{months[0]}，右侧为{months[1]}。"
                        else:
                            insight = f"案件总量图表展示了数据的基本情况。"
                    elif '问题类型对比' in chart_name or '问题类型分布' in chart_name:
                        if '大类名称' in df.columns and len(df['大类名称'].value_counts()) > 0:
                            top = df['大类名称'].value_counts().head(3)
                            insight = f"问题类型分布显示，{top.index[0]}占比最高，共{top.values[0]}件。"
                        else:
                            insight = f"问题类型分布图表展示了各类问题的占比情况。"
                    elif 'TOP10小类' in chart_name:
                        if '小类名称' in df.columns and len(df['小类名称'].value_counts()) > 0:
                            top5 = df['小类名称'].value_counts().head(5)
                            insight = f"排名前五的小类问题分别是：{top5.index[0]}、{top5.index[1] if len(top5)>1 else ''}、{top5.index[2] if len(top5)>2 else ''}。"
                        else:
                            insight = f"排名图表展示了高频小类问题的分布情况。"
                    elif '片区案件' in chart_name:
                        if '所属片区' in df.columns and len(df['所属片区'].value_counts()) > 0:
                            top = df['所属片区'].value_counts().head(3)
                            insight = f"片区案件分布显示，{top.index[0]}案件最多，共{top.values[0]}件，其次是{top.index[1] if len(top)>1 else '其他'}。"
                        else:
                            insight = f"片区案件分布图表展示了各区域的案件分布情况。"
                    elif '问题来源' in chart_name:
                        if '问题来源' in df.columns and len(df['问题来源'].value_counts()) > 0:
                            top = df['问题来源'].value_counts().head(3)
                            insight = f"问题来源分布显示，主要来源为{top.index[0]}，占比{top.values[0]/filtered_count*100:.1f}%。"
                        else:
                            insight = f"问题来源分布图表展示了案件的来源渠道。"
                    elif '街道案件' in chart_name:
                        if '所属街道' in df.columns and len(df['所属街道'].value_counts()) > 0:
                            top = df['所属街道'].value_counts().head(3)
                            insight = f"街道案件分布显示，{top.index[0]}案件最多，共{top.values[0]}件。"
                        else:
                            insight = f"街道案件分布图表展示了各街道的案件分布情况。"
                    elif '处置部门' in chart_name:
                        if '处置部门' in df.columns and len(df['处置部门'].value_counts()) > 0:
                            top = df['处置部门'].value_counts().head(3)
                            insight = f"处置部门排名显示，{top.index[0]}处理案件最多，共{top.values[0]}件。"
                        else:
                            insight = f"处置部门排名图表展示了各部门的工作量。"
                    elif '案件状态' in chart_name:
                        if '当前阶段名称' in df.columns:
                            done_count = (df['当前阶段名称'] == '[办结]').sum()
                            insight = f"案件状态分布显示，已办结{done_count}件，结案率{completion_rate:.1f}%。"
                        else:
                            insight = f"案件状态分布图表展示了案件的处理进度。"
                    else:
                        insight = f"该图表展示了{chart_display}的分析结果。"

                    insights['chart_insights'][chart_name] = insight

                print(f"[视频报告] 洞察生成完成，含{len(insights['chart_insights'])}个图表结论")
            except Exception as e:
                print(f"[视频报告] 洞察生成失败: {e}")
                insights = {'summary': f'数据分析报告，共{filtered_count}条数据', 'key_findings': []}

            # 构建报告标题（简洁的副标题格式）
            if template_type == 'monthly_comparison' and months:
                report_title = f"{months[0]}与{months[1]}对比分析报告"
            elif template_type == 'yearly_summary' and year:
                report_title = f"{year}年度数据分析报告"
            elif template_type == 'special_analysis' and dimension:
                report_title = f"{dimension}专项分析报告"
            elif template_type == 'full_analysis':
                report_title = "全量数据分析报告"
            else:
                report_title = "数据分析报告"

            # 生成视频
            print("[视频报告] 开始生成视频文件...")
            generator = VideoReportGenerator()

            # 设置输出路径
            output_path = tempfile.mktemp(suffix='.mp4')

            try:
                video_path = generator.generate_video(
                    report_title=report_title,
                    charts_data=charts_base64,
                    insights=insights,
                    output_path=output_path
                )
            except Exception as e:
                print(f"[视频报告] 视频生成失败: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'视频生成失败: {str(e)}'}), 500

            if not video_path or not os.path.exists(video_path):
                return jsonify({'error': '视频生成失败'}), 500

            print(f"[视频报告] 视频生成完成: {video_path}, 大小: {os.path.getsize(video_path)} bytes")

            # 返回视频文件
            response = send_file(
                video_path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name=f'{report_title}.mp4'
            )

            # 请求结束后删除临时文件
            @response.call_on_close
            def cleanup():
                try:
                    if os.path.exists(video_path):
                        os.remove(video_path)
                except:
                    pass

            return response

        except Exception as e:
            print(f"Error in video_report: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500
    def generate_smart_report_charts(df, template_type, months, dimension, dimension_values):
        """生成精美图表，返回base64编码列表"""
        charts = []

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'SimSun']
        plt.rcParams['axes.unicode_minus'] = False

        # 列名映射（英文 -> 中文）
        column_mapping = {
            'major_category': '大类名称',
            'minor_category': '小类名称',
            'area': '所属片区',
            'source': '问题来源',
            'street': '所属街道',
            'owner_unit': '处置部门',
            'status': '当前阶段名称',
            'report_time': '上报时间',
            'responsible_area_name': '责任区域',
            'community': '所属社区'
        }
        # 重命名列（如果存在）
        df = df.rename(columns=column_mapping)

        # 配色方案
        colors_palette = ['#4ECDC4', '#FF6B6B', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']
        color_m1 = '#4ECDC4'  # 第一个月颜色
        color_m2 = '#FF6B6B'  # 第二个月颜色

        # 获取月份列
        month_col = None
        for col in ['月份', 'data_month']:
            if col in df.columns:
                month_col = col
                break

        # 是否是月度对比模式
        is_monthly_comparison = template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col

        try:
            # ===== 综合仪表盘（总体情况，无对比） =====
            # 创建一个综合仪表盘图表，展示总体数据情况
            fig = plt.figure(figsize=(16, 12))
            fig.suptitle('案件数据分析综合仪表盘', fontsize=22, fontweight='bold', y=0.98)

            # 创建子图网格
            gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.25)

            # 子图1：案件总量（数字展示）
            ax1 = fig.add_subplot(gs[0, 0])
            total_count = len(df)
            ax1.text(0.5, 0.6, f'{total_count:,}', ha='center', va='center', fontsize=36, fontweight='bold', color='#667eea')
            ax1.text(0.5, 0.3, '案件总量', ha='center', va='center', fontsize=16, color='#666')
            ax1.set_xlim(0, 1)
            ax1.set_ylim(0, 1)
            ax1.axis('off')
            ax1.add_patch(plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor='#667eea', linewidth=2, transform=ax1.transAxes))

            # 子图2：结案率
            ax2 = fig.add_subplot(gs[0, 1])
            if '当前阶段名称' in df.columns:
                completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
            else:
                completion_rate = 0
            ax2.text(0.5, 0.6, f'{completion_rate:.1f}%', ha='center', va='center', fontsize=36, fontweight='bold',
                     color='#27ae60' if completion_rate > 95 else '#f39c12')
            ax2.text(0.5, 0.3, '结案率', ha='center', va='center', fontsize=16, color='#666')
            ax2.set_xlim(0, 1)
            ax2.set_ylim(0, 1)
            ax2.axis('off')
            ax2.add_patch(plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor='#27ae60', linewidth=2, transform=ax2.transAxes))

            # 子图3：问题类型数
            ax3 = fig.add_subplot(gs[0, 2])
            type_count = len(df['大类名称'].unique()) if '大类名称' in df.columns else 0
            ax3.text(0.5, 0.6, f'{type_count}', ha='center', va='center', fontsize=36, fontweight='bold', color='#FF6B6B')
            ax3.text(0.5, 0.3, '问题类型', ha='center', va='center', fontsize=16, color='#666')
            ax3.set_xlim(0, 1)
            ax3.set_ylim(0, 1)
            ax3.axis('off')
            ax3.add_patch(plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor='#FF6B6B', linewidth=2, transform=ax3.transAxes))

            # 子图4：问题类型分布饼图
            ax4 = fig.add_subplot(gs[1, 0:2])
            if '大类名称' in df.columns:
                type_counts = df['大类名称'].value_counts().head(6)
                colors_pie = colors_palette[:len(type_counts)]
                wedges, texts, autotexts = ax4.pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%',
                                                   colors=colors_pie, startangle=90, textprops={'fontsize': 11})
                ax4.set_title('问题类型分布', fontsize=14, fontweight='bold', pad=10)

            # 子图5：片区分布条形图
            ax5 = fig.add_subplot(gs[1, 2])
            if '所属片区' in df.columns:
                district_counts = df['所属片区'].value_counts().head(5)
                bars = ax5.barh(range(len(district_counts)), district_counts.values[::-1],
                               color=colors_palette[:len(district_counts)])
                ax5.set_yticks(range(len(district_counts)))
                ax5.set_yticklabels(district_counts.index[::-1], fontsize=11)
                ax5.set_xlabel('案件数', fontsize=11)
                ax5.set_title('片区分布', fontsize=14, fontweight='bold', pad=10)

            # 子图6：TOP5小类问题
            ax6 = fig.add_subplot(gs[2, 0:2])
            if '小类名称' in df.columns:
                top5 = df['小类名称'].value_counts().head(5)
                colors_bar = plt.cm.Blues(np.linspace(0.4, 0.9, len(top5)))[::-1]
                bars = ax6.barh(range(len(top5)), top5.values[::-1], color=colors_bar)
                ax6.set_yticks(range(len(top5)))
                ax6.set_yticklabels(top5.index[::-1], fontsize=11)
                ax6.set_xlabel('案件数', fontsize=11)
                ax6.set_title('TOP5小类问题', fontsize=14, fontweight='bold', pad=10)
                for i, (bar, val) in enumerate(zip(bars, top5.values[::-1])):
                    ax6.text(bar.get_width() + max(top5.values)*0.02, bar.get_y() + bar.get_height()/2,
                            f'{int(val)}', ha='left', va='center', fontsize=10)

            # 子图7：问题来源分布
            ax7 = fig.add_subplot(gs[2, 2])
            if '问题来源' in df.columns:
                source_counts = df['问题来源'].value_counts().head(4)
                colors_src = ['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'][:len(source_counts)]
                wedges, texts, autotexts = ax7.pie(source_counts.values, labels=source_counts.index, autopct='%1.1f%%',
                                                   colors=colors_src, startangle=90, textprops={'fontsize': 9})
                ax7.set_title('问题来源', fontsize=14, fontweight='bold', pad=10)

            charts.append(('00_综合仪表盘', fig_to_base64(fig)))
            plt.close(fig)

            # ===== 图1: 案件总量对比 =====
            if months and month_col:
                fig, ax = plt.subplots(figsize=(10, 8))

                month_counts = df[month_col].value_counts().reindex(months)
                x = np.arange(len(months))
                bars = ax.bar(x, month_counts.values, color=[color_m1, color_m2][:len(months)], width=0.5, edgecolor='white', linewidth=2)
                ax.set_title('案件总量对比', fontsize=20, fontweight='bold', pad=20)
                ax.set_ylabel('案件数量', fontsize=14)
                ax.set_xticks(x)
                ax.set_xticklabels(months, fontsize=14)
                ax.tick_params(axis='y', labelsize=12)

                for bar, val in zip(bars, month_counts.values):
                    if pd.notna(val):
                        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(month_counts.values)*0.02,
                                f'{int(val):,}', ha='center', va='bottom', fontsize=16, fontweight='bold')

                # 添加环比变化
                if len(months) == 2 and month_counts.values[0] > 0:
                    change = month_counts.values[1] - month_counts.values[0]
                    change_pct = change / month_counts.values[0] * 100
                    color = '#e74c3c' if change > 0 else '#27ae60'
                    ax.text(0.5, 0.95, f'环比变化: {change:+,} ({change_pct:+.1f}%)',
                            transform=ax.transAxes, ha='center', fontsize=14, color=color, fontweight='bold')

                plt.tight_layout()
                charts.append(('01_案件总量对比', fig_to_base64(fig)))
                plt.close(fig)

            # ===== 图2: 问题类型对比 =====
            if '大类名称' in df.columns:
                if is_monthly_comparison:
                    # 月度对比模式：分组柱状图
                    fig, ax = plt.subplots(figsize=(14, 8))

                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]

                    type_counts1 = df1['大类名称'].value_counts()
                    type_counts2 = df2['大类名称'].value_counts()

                    # 合并所有类型
                    all_types = list(set(type_counts1.index) | set(type_counts2.index))
                    all_types.sort(key=lambda x: type_counts2.get(x, 0) + type_counts1.get(x, 0), reverse=True)

                    x = np.arange(len(all_types))
                    width = 0.35

                    vals1 = [type_counts1.get(t, 0) for t in all_types]
                    vals2 = [type_counts2.get(t, 0) for t in all_types]

                    bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                    bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                    ax.set_xticks(x)
                    ax.set_xticklabels(all_types, rotation=45, ha='right', fontsize=10)
                    ax.set_ylabel('案件数量', fontsize=12)
                    ax.set_title('各类型案件数量对比', fontsize=16, fontweight='bold', pad=15)
                    ax.legend(fontsize=12)

                    plt.tight_layout()
                else:
                    # 非对比模式：饼图
                    fig, ax = plt.subplots(figsize=(10, 8))
                    type_counts = df['大类名称'].value_counts()
                    colors = colors_palette[:len(type_counts)]
                    wedges, texts, autotexts = ax.pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%',
                                                       colors=colors, startangle=90, textprops={'fontsize': 10})
                    ax.set_title('问题类型分布', fontsize=16, fontweight='bold', pad=15)
                charts.append(('02_问题类型对比', fig_to_base64(fig)))
                plt.close(fig)

            # ===== 图3: TOP10小类问题对比 =====
            if '小类名称' in df.columns:
                if is_monthly_comparison:
                    fig, ax = plt.subplots(figsize=(14, 8))

                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]

                    # 获取两个月份完整的统计，不只是TOP10
                    all_counts1 = df1['小类名称'].value_counts()
                    all_counts2 = df2['小类名称'].value_counts()

                    # 取两个月份TOP10的并集
                    top10_1_names = set(all_counts1.head(10).index)
                    top10_2_names = set(all_counts2.head(10).index)
                    all_items = list(top10_1_names | top10_2_names)
                    all_items.sort(key=lambda x: all_counts2.get(x, 0) + all_counts1.get(x, 0), reverse=True)
                    all_items = all_items[:10]  # 取TOP10

                    y = np.arange(len(all_items))
                    width = 0.35

                    # 使用完整统计数据获取值
                    vals1 = [all_counts1.get(t, 0) for t in all_items]
                    vals2 = [all_counts2.get(t, 0) for t in all_items]

                    bars1 = ax.barh(y - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                    bars2 = ax.barh(y + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                    ax.set_yticks(y)
                    ax.set_yticklabels(all_items, fontsize=10)
                    ax.set_xlabel('案件数量', fontsize=12)
                    ax.set_title('TOP10小类问题对比', fontsize=16, fontweight='bold', pad=15)
                    ax.legend(fontsize=12)

                    plt.tight_layout()
                else:
                    fig, ax = plt.subplots(figsize=(12, 6))
                    top10 = df['小类名称'].value_counts().head(10)
                    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(top10)))[::-1]
                    bars = ax.barh(range(len(top10)), top10.values[::-1], color=colors)
                    ax.set_yticks(range(len(top10)))
                    ax.set_yticklabels(top10.index[::-1], fontsize=10)
                    ax.set_xlabel('案件数量', fontsize=12)
                    ax.set_title('TOP10小类问题', fontsize=16, fontweight='bold', pad=15)
                charts.append(('03_TOP10小类问题对比', fig_to_base64(fig)))
                plt.close(fig)

            # ===== 图4: 片区案件对比 =====
            if '所属片区' in df.columns:
                if is_monthly_comparison:
                    fig, ax = plt.subplots(figsize=(12, 6))

                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]

                    district_counts1 = df1['所属片区'].value_counts()
                    district_counts2 = df2['所属片区'].value_counts()

                    all_districts = list(set(district_counts1.index) | set(district_counts2.index))
                    all_districts.sort(key=lambda x: district_counts2.get(x, 0) + district_counts1.get(x, 0), reverse=True)

                    x = np.arange(len(all_districts))
                    width = 0.35

                    vals1 = [district_counts1.get(d, 0) for d in all_districts]
                    vals2 = [district_counts2.get(d, 0) for d in all_districts]

                    bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                    bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                    ax.set_xticks(x)
                    ax.set_xticklabels(all_districts, fontsize=10)
                    ax.set_ylabel('案件数量', fontsize=12)
                    ax.set_title('各片区案件对比', fontsize=16, fontweight='bold', pad=15)
                    ax.legend(fontsize=12)

                    plt.tight_layout()
                else:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    district_counts = df['所属片区'].value_counts()
                    colors = colors_palette[:len(district_counts)]
                    bars = ax.bar(district_counts.index, district_counts.values, color=colors, edgecolor='white')
                    ax.set_ylabel('案件数量', fontsize=12)
                    ax.set_title('各片区案件分布', fontsize=16, fontweight='bold', pad=15)
                charts.append(('04_片区案件对比', fig_to_base64(fig)))
                plt.close(fig)

            # ===== 图5: 问题来源对比 =====
            if '问题来源' in df.columns:
                if is_monthly_comparison:
                    fig, ax = plt.subplots(figsize=(12, 6))

                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]

                    source_counts1 = df1['问题来源'].value_counts()
                    source_counts2 = df2['问题来源'].value_counts()

                    all_sources = list(set(source_counts1.index) | set(source_counts2.index))
                    all_sources.sort(key=lambda x: source_counts2.get(x, 0) + source_counts1.get(x, 0), reverse=True)

                    x = np.arange(len(all_sources))
                    width = 0.35

                    vals1 = [source_counts1.get(s, 0) for s in all_sources]
                    vals2 = [source_counts2.get(s, 0) for s in all_sources]

                    bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                    bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                    ax.set_xticks(x)
                    ax.set_xticklabels(all_sources, rotation=45, ha='right', fontsize=10)
                    ax.set_ylabel('案件数量', fontsize=12)
                    ax.set_title('问题来源对比', fontsize=16, fontweight='bold', pad=15)
                    ax.legend(fontsize=12)

                    plt.tight_layout()
                else:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    source_counts = df['问题来源'].value_counts()
                    colors = colors_palette[:len(source_counts)]
                    wedges, texts, autotexts = ax.pie(source_counts.values, labels=source_counts.index, autopct='%1.1f%%',
                                                       colors=colors, startangle=90, textprops={'fontsize': 10})
                    ax.set_title('问题来源分布', fontsize=16, fontweight='bold', pad=15)
                charts.append(('05_问题来源对比', fig_to_base64(fig)))
                plt.close(fig)

            # ===== 图6: 街道案件对比 =====
            if '所属街道' in df.columns:
                if is_monthly_comparison:
                    fig, ax = plt.subplots(figsize=(14, 6))

                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]

                    street_counts1 = df1['所属街道'].value_counts()
                    street_counts2 = df2['所属街道'].value_counts()

                    all_streets = list(set(street_counts1.index) | set(street_counts2.index))
                    all_streets.sort(key=lambda x: street_counts2.get(x, 0) + street_counts1.get(x, 0), reverse=True)

                    x = np.arange(len(all_streets))
                    width = 0.35

                    vals1 = [street_counts1.get(s, 0) for s in all_streets]
                    vals2 = [street_counts2.get(s, 0) for s in all_streets]

                    bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                    bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                    ax.set_xticks(x)
                    ax.set_xticklabels(all_streets, rotation=45, ha='right', fontsize=10)
                    ax.set_ylabel('案件数量', fontsize=12)
                    ax.set_title('各街道案件对比', fontsize=16, fontweight='bold', pad=15)
                    ax.legend(fontsize=12)

                    plt.tight_layout()
                else:
                    fig, ax = plt.subplots(figsize=(12, 6))
                    street_counts = df['所属街道'].value_counts()
                    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(street_counts)))[::-1]
                    bars = ax.bar(range(len(street_counts)), street_counts.values, color=colors)
                    ax.set_xticks(range(len(street_counts)))
                    ax.set_xticklabels(street_counts.index, rotation=45, ha='right', fontsize=10)
                    ax.set_ylabel('案件数量', fontsize=12)
                    ax.set_title('各街道案件分布', fontsize=16, fontweight='bold', pad=15)
                charts.append(('06_街道案件对比', fig_to_base64(fig)))
                plt.close(fig)

            # ===== 图7: 处置部门TOP10对比 =====
            if '处置部门' in df.columns:
                if is_monthly_comparison:
                    # 月度对比模式：分组柱状图
                    fig, ax = plt.subplots(figsize=(14, 8))

                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]

                    # 获取完整统计，不只是TOP10
                    all_dept_counts1 = df1['处置部门'].value_counts()
                    all_dept_counts2 = df2['处置部门'].value_counts()

                    # 取两个月份TOP10的并集
                    top10_1_names = set(all_dept_counts1.head(10).index)
                    top10_2_names = set(all_dept_counts2.head(10).index)
                    all_depts = list(top10_1_names | top10_2_names)
                    all_depts.sort(key=lambda x: all_dept_counts2.get(x, 0) + all_dept_counts1.get(x, 0), reverse=True)
                    all_depts = all_depts[:10]  # 取TOP10

                    y = np.arange(len(all_depts))
                    width = 0.35

                    # 使用完整统计数据获取值
                    vals1 = [all_dept_counts1.get(d, 0) for d in all_depts]
                    vals2 = [all_dept_counts2.get(d, 0) for d in all_depts]

                    bars1 = ax.barh(y - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                    bars2 = ax.barh(y + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                    ax.set_yticks(y)
                    ax.set_yticklabels(all_depts, fontsize=10)
                    ax.set_xlabel('案件数量', fontsize=12)
                    ax.set_title('处置部门TOP10对比', fontsize=16, fontweight='bold', pad=15)
                    ax.legend(fontsize=12)

                    plt.tight_layout()
                else:
                    # 非对比模式：普通条形图
                    fig, ax = plt.subplots(figsize=(12, 6))
                    dept_counts = df['处置部门'].value_counts().head(10)
                    colors = plt.cm.Greens(np.linspace(0.4, 0.9, len(dept_counts)))[::-1]
                    bars = ax.barh(range(len(dept_counts)), dept_counts.values[::-1], color=colors)
                    ax.set_yticks(range(len(dept_counts)))
                    ax.set_yticklabels(dept_counts.index[::-1], fontsize=10)
                    ax.set_xlabel('案件数量', fontsize=12)
                    ax.set_title('处置部门TOP10', fontsize=16, fontweight='bold', pad=15)
                charts.append(('07_处置部门TOP10对比', fig_to_base64(fig)))
                plt.close(fig)

            # ===== 图8: 案件状态对比 =====
            if '当前阶段名称' in df.columns:
                if is_monthly_comparison:
                    fig, ax = plt.subplots(figsize=(10, 6))

                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]

                    status_counts1 = df1['当前阶段名称'].value_counts()
                    status_counts2 = df2['当前阶段名称'].value_counts()

                    all_status = list(set(status_counts1.index) | set(status_counts2.index))

                    x = np.arange(len(all_status))
                    width = 0.35

                    vals1 = [status_counts1.get(s, 0) for s in all_status]
                    vals2 = [status_counts2.get(s, 0) for s in all_status]

                    bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                    bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                    ax.set_xticks(x)
                    ax.set_xticklabels(all_status, fontsize=10)
                    ax.set_ylabel('案件数量', fontsize=12)
                    ax.set_title('案件状态对比', fontsize=16, fontweight='bold', pad=15)
                    ax.legend(fontsize=12)

                    plt.tight_layout()
                else:
                    fig, ax = plt.subplots(figsize=(8, 6))
                    status_counts = df['当前阶段名称'].value_counts()
                    colors = ['#27ae60', '#f39c12', '#e74c3c'][:len(status_counts)]
                    wedges, texts, autotexts = ax.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%',
                                                       colors=colors, startangle=90, textprops={'fontsize': 11})
                    ax.set_title('案件状态分布', fontsize=16, fontweight='bold', pad=15)
                charts.append(('08_案件状态对比', fig_to_base64(fig)))
                plt.close(fig)

        except Exception as e:
            print(f"[智能报告] 图表生成失败: {e}")
            import traceback
            traceback.print_exc()

        return charts
    def fig_to_base64(fig):
        """将matplotlib图表转换为base64字符串"""
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    def generate_report_insights(df, template_type, months, year, dimension, dimension_values):
        """调用LLM生成分析洞察"""
        try:
            # 准备数据摘要
            data_summary = f"""
    数据总量: {len(df)}
    字段数量: {len(df.columns)}
    主要字段:
    """

            # 月度对比时，添加详细的对比数据
            if template_type == 'monthly_comparison' and months and len(months) >= 2:
                month_col = None
                for col in ['月份', 'data_month']:
                    if col in df.columns:
                        month_col = col
                        break

                if month_col:
                    data_summary += f"\n对比月份: {months[0]} vs {months[1]}"
                    data_summary += f"\n各月数据量:"
                    for m in months:
                        count = len(df[df[month_col] == m])
                        data_summary += f"\n  - {m}: {count}件"

                    # 类型变化
                    if '大类名称' in df.columns:
                        data_summary += f"\n各类型月度变化:"
                        for m_idx in range(len(months)-1):
                            m1, m2 = months[m_idx], months[m_idx+1]
                            df1 = df[df[month_col] == m1]
                            df2 = df[df[month_col] == m2]
                            for cat in df['大类名称'].unique()[:5]:
                                c1 = len(df1[df1['大类名称'] == cat])
                                c2 = len(df2[df2['大类名称'] == cat])
                                change = c2 - c1
                                pct = (c2 - c1) / c1 * 100 if c1 > 0 else 0
                                data_summary += f"\n  - {cat}: {c1}→{c2} ({change:+d}, {pct:+.1f}%)"

            # 添加关键统计
            for col in ['大类名称', '小类名称', '所属片区', '问题来源', '处置部门']:
                if col in df.columns:
                    top3 = df[col].value_counts().head(3)
                    data_summary += f"\n{col} TOP3: {dict(top3)}"

            # 构建提示词
            if template_type == 'monthly_comparison':
                prompt = f"""请分析以下案件数据的月度对比情况：

    {data_summary}

    对比月份: {months[0]} 与 {months[1]}

    重要说明：
    - "所属片区"字段（如东、西、南、北、中片区）表示案件发生的地理位置区域
    - "处置部门"字段（如执法东片区、执法南片区等）表示负责处置案件的部门
    - 这两者是不同的概念，不要混淆或关联分析

    请生成以下内容（以JSON格式返回）：
    {{
        "summary": "数据概况，明确说明对比的是哪两个月，各有多少案件，环比变化百分比",
        "key_findings": [
            "发现1：具体说明哪个问题类型增长/下降最多，引用具体数字和百分比",
            "发现2：案件数量变化趋势分析",
            "发现3：片区或来源变化分析"
        ],
        "recommendations": [
            "建议1：针对变化趋势的具体管理建议",
            "建议2：资源配置建议"
        ]
    }}

    注意：
    1. key_findings和recommendations数组只包含有实际价值的分析和建议
    2. 如果某方面数据不足或无法分析，不要强行编造发现，可以减少数组元素数量
    3. 每个发现都必须引用具体数据，不要说"暂无数据"、"无法分析"等空话
    """
            elif template_type == 'yearly_summary':
                prompt = f"""请分析以下案件数据的年度总结：

    {data_summary}

    分析年份: {year}年

    请生成以下内容（以JSON格式返回）：
    {{
        "summary": "数据概况（2-3句话）",
        "key_findings": ["发现1", "发现2", "发现3"],
        "recommendations": ["建议1", "建议2", "建议3"]
    }}
    """
            elif template_type == 'special_analysis':
                prompt = f"""请分析以下专项数据：

    {data_summary}

    分析维度: {dimension}
    分析范围: {', '.join(dimension_values) if dimension_values else '全部'}

    请生成以下内容（以JSON格式返回）：
    {{
        "summary": "数据概况（2-3句话）",
        "key_findings": ["发现1", "发现2", "发现3"],
        "recommendations": ["建议1", "建议2", "建议3"]
    }}
    """
            else:
                prompt = f"""请分析以下案件数据：

    {data_summary}

    请生成以下内容（以JSON格式返回）：
    {{
        "summary": "数据概况（2-3句话）",
        "key_findings": ["发现1", "发现2", "发现3"],
        "recommendations": ["建议1", "建议2", "建议3"]
    }}
    """

            messages = [
                {"role": "system", "content": "你是一个数据分析专家，擅长从数据中发现规律并给出建议。"},
                {"role": "user", "content": prompt}
            ]

            # 调用LLM
            success, result = call_llm_api(
                API_URL, API_KEY, MODEL,
                messages,
                max_tokens=1500,
                provider_name="火山引擎-智能报告"
            )

            if success:
                # 解析JSON
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    return json.loads(json_match.group())

            return {"summary": "分析生成中...", "key_findings": [], "recommendations": []}

        except Exception as e:
            print(f"[智能报告] LLM调用失败: {e}")
            return {"summary": "分析生成中...", "key_findings": [], "recommendations": []}
    def render_smart_report_html(df, template_type, months, year, dimension, dimension_values,
                                  charts_base64, insights, filter_desc, original_count, filtered_count):
        """渲染精美HTML报告 - 按照模板结构组织"""

        # 获取模板名称
        template_names = {
            'monthly_comparison': '月度对比分析报告',
            'yearly_summary': '年度总结报告',
            'special_analysis': '专项分析报告',
            'full_analysis': '全量分析报告'
        }
        report_title = template_names.get(template_type, '数据分析报告')

        # 月度对比时，标题显示对比月份
        if template_type == 'monthly_comparison' and months and len(months) >= 2:
            report_title = f'{months[0]}与{months[1]}对比分析报告'

        # 获取月份列
        month_col = None
        for col in ['月份', 'data_month']:
            if col in df.columns:
                month_col = col
                break

        # 解析图表，按名称分类
        charts_dict = {}
        for title, img_base64 in charts_base64:
            charts_dict[title] = img_base64

        # 生成核心数据概览（汇总）
        summary_box_html = ""
        if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
            m1_count = len(df[df[month_col] == months[0]])
            m2_count = len(df[df[month_col] == months[1]])
            total_count = m1_count + m2_count
            change = m2_count - m1_count
            change_pct = (m2_count - m1_count) / m1_count * 100 if m1_count > 0 else 0
            change_color = 'positive' if change > 0 else 'negative'

            summary_box_html = f'''
            <div class="summary-box">
                <div class="summary-item">
                    <div class="value">{total_count:,}</div>
                    <div class="label">总案件量</div>
                </div>
                <div class="summary-item">
                    <div class="value">{m1_count:,}</div>
                    <div class="label">{months[0]}案件</div>
                </div>
                <div class="summary-item highlight">
                    <div class="value">{m2_count:,}</div>
                    <div class="label">{months[1]}案件</div>
                </div>
                <div class="summary-item">
                    <div class="value {change_color}">{change_pct:+.2f}%</div>
                    <div class="label">环比增长</div>
                </div>
            </div>
            '''
        else:
            # 非月度对比模式
            completion_rate = 0
            if '当前阶段名称' in df.columns:
                completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
            summary_box_html = f'''
            <div class="summary-box">
                <div class="summary-item highlight">
                    <div class="value">{filtered_count:,}</div>
                    <div class="label">案件总数</div>
                </div>
                <div class="summary-item">
                    <div class="value">{len(df["大类名称"].unique()) if "大类名称" in df.columns else 0}</div>
                    <div class="label">问题类型</div>
                </div>
                <div class="summary-item">
                    <div class="value">{completion_rate:.1f}%</div>
                    <div class="label">结案率</div>
                </div>
                <div class="summary-item">
                    <div class="value">{len(df["所属片区"].unique()) if "所属片区" in df.columns else 0}</div>
                    <div class="label">涉及片区</div>
                </div>
            </div>
            '''

        # 生成关键发现HTML
        findings_html = ""
        findings_list = insights.get('key_findings', [])
        for finding in findings_list:
            if finding and finding.strip():
                findings_html += f'''
            <div class="finding-item">
                <h4>关键发现</h4>
                <p>{finding}</p>
            </div>
            '''

        # 只有有发现时才显示关键发现部分
        findings_section = ""
        if findings_html.strip():
            findings_section = f'''
            <div class="section">
                <h2 class="section-title">关键发现</h2>
                <div class="key-findings">
                    {findings_html}
                </div>
            </div>
            '''

        # 生成综合仪表盘HTML
        dashboard_html = ""
        if '00_综合仪表盘' in charts_dict:
            dashboard_html = f'''
            <div class="section">
                <h2 class="section-title">综合仪表盘</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['00_综合仪表盘']}" class="dashboard-img" alt="综合仪表盘">
                    <div class="chart-caption">案件数据分析综合仪表盘 - 展示各维度数据概况</div>
                </div>
            </div>
            '''

        # 生成各部分图表和分析HTML
        sections_html = ""

        # 一、月份案件总量对比
        if '01_案件总量对比' in charts_dict:
            # 生成分析文本和数据表格
            analysis_text = ""
            data_table = ""
            if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                m1_count = len(df[df[month_col] == months[0]])
                m2_count = len(df[df[month_col] == months[1]])
                change = m2_count - m1_count
                change_pct = (m2_count - m1_count) / m1_count * 100 if m1_count > 0 else 0

                # 计算延期次数和返工次数
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                delay1 = pd.to_numeric(df1['延期次数'], errors='coerce').fillna(0).sum() if '延期次数' in df1.columns else 0
                delay2 = pd.to_numeric(df2['延期次数'], errors='coerce').fillna(0).sum() if '延期次数' in df2.columns else 0
                rework1 = pd.to_numeric(df1['返工次数'], errors='coerce').fillna(0).sum() if '返工次数' in df1.columns else 0
                rework2 = pd.to_numeric(df2['返工次数'], errors='coerce').fillna(0).sum() if '返工次数' in df2.columns else 0

                analysis_text = f'{months[1]}案件总量{m2_count}件，较{months[0]}的{m1_count}件增长{change_pct:.2f}%。案件量增长可能与季节性因素和监管力度有关。建议关注案件增长趋势，合理调配处置资源。'

                data_table = f'''
                <table class="data-table">
                    <tr>
                        <th>月份</th>
                        <th>案件数量</th>
                        <th>延期次数</th>
                        <th>返工次数</th>
                        <th>环比变化</th>
                    </tr>
                    <tr>
                        <td>{months[0]}</td>
                        <td>{m1_count:,}</td>
                        <td>{int(delay1)}</td>
                        <td>{int(rework1)}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>{months[1]}</td>
                        <td>{m2_count:,}</td>
                        <td>{int(delay2)}</td>
                        <td>{int(rework2)}</td>
                        <td class="{'positive' if change > 0 else 'negative'}">{change_pct:+.2f}%</td>
                    </tr>
                </table>
                '''

            sections_html += f'''
            <div class="section">
                <h2 class="section-title">一、月份案件总量对比</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['01_案件总量对比']}" alt="月份案件总量对比">
                    <div class="chart-caption">{months[0] if months else ''}与{months[1] if months else ''}案件总量对比及占比分布</div>
                </div>
                <div class="analysis-text">
                    <strong>分析结论：</strong>{analysis_text}
                </div>
                {data_table}
            </div>
            '''

        # 二、问题类型分布对比
        if '02_问题类型对比' in charts_dict:
            # 生成分析文本和数据表格
            analysis_text = ""
            data_table = ""
            if '大类名称' in df.columns:
                if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]
                    type_counts1 = df1['大类名称'].value_counts()
                    type_counts2 = df2['大类名称'].value_counts()

                    # 找出变化最大的类型
                    max_change_type = ""
                    max_change_val = 0
                    for cat in df['大类名称'].unique():
                        c1 = type_counts1.get(cat, 0)
                        c2 = type_counts2.get(cat, 0)
                        change = c2 - c1
                        if abs(change) > abs(max_change_val):
                            max_change_val = change
                            max_change_type = cat

                    analysis_text = f'{max_change_type}类案件变化最显著，从{type_counts1.get(max_change_type, 0)}件变化至{type_counts2.get(max_change_type, 0)}件。建议重点关注变化显著的类型。'

                    data_table = '<table class="data-table"><tr><th>大类名称</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化数量</th><th>变化率</th></tr>'
                    for cat in df['大类名称'].value_counts().head(6).index:
                        c1 = type_counts1.get(cat, 0)
                        c2 = type_counts2.get(cat, 0)
                        change = c2 - c1
                        pct = (c2 - c1) / c1 * 100 if c1 > 0 else (100 if c2 > 0 else 0)
                        color_class = 'positive' if change > 0 else ('negative' if change < 0 else '')
                        data_table += f'<tr><td>{cat}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{change:+,}</td><td class="{color_class}">{pct:+.1f}%</td></tr>'
                    data_table += '</table>'

            sections_html += f'''
            <div class="section">
                <h2 class="section-title">二、问题类型分布对比</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['02_问题类型对比']}" alt="问题类型分布对比">
                    <div class="chart-caption">{months[0] if months else ''}与{months[1] if months else ''}各问题类型占比分布对比</div>
                </div>
                <div class="analysis-text">
                    <strong>分析结论：</strong>{analysis_text}
                </div>
                {data_table}
            </div>
            '''

        # 三、TOP10小类问题对比
        if '03_TOP10小类问题对比' in charts_dict:
            analysis_text = ""
            data_table = ""
            if '小类名称' in df.columns:
                if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]
                    # 获取两个月份各自所有的统计，不只是TOP10
                    all_counts1 = df1['小类名称'].value_counts()
                    all_counts2 = df2['小类名称'].value_counts()

                    # 获取两个月TOP10的并集
                    top10_1_names = set(all_counts1.head(10).index)
                    top10_2_names = set(all_counts2.head(10).index)
                    all_items = list(top10_1_names | top10_2_names)
                    all_items.sort(key=lambda x: all_counts2.get(x, 0) + all_counts1.get(x, 0), reverse=True)

                    # 找出变化最大的小类
                    max_change_name = ""
                    max_change_val = 0
                    for name in all_items:
                        c1 = all_counts1.get(name, 0)
                        c2 = all_counts2.get(name, 0)
                        change = c2 - c1
                        if abs(change) > abs(max_change_val):
                            max_change_val = change
                            max_change_name = name

                    analysis_text = f'{max_change_name}问题变化最显著，从{months[0]}的{all_counts1.get(max_change_name, 0)}件变化至{months[1]}的{all_counts2.get(max_change_name, 0)}件。建议针对高频问题制定专项治理方案，加强源头管控。'

                    data_table = '<table class="data-table"><tr><th>排名</th><th>小类名称</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化</th></tr>'
                    for i, name in enumerate(all_items[:10], 1):
                        c1 = all_counts1.get(name, 0)
                        c2 = all_counts2.get(name, 0)
                        change = c2 - c1
                        color_class = 'positive' if change > 0 else ('negative' if change < 0 else '')
                        data_table += f'<tr><td>{i}</td><td>{name}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{change:+,}</td></tr>'
                    data_table += '</table>'
                else:
                    top10 = df['小类名称'].value_counts().head(10)
                    analysis_text = "小类问题案件量前10名分析。建议针对高频问题制定专项治理方案。"
                    data_table = '<table class="data-table"><tr><th>排名</th><th>小类名称</th><th>案件数量</th><th>占比</th></tr>'
                    for i, (name, count) in enumerate(top10.items(), 1):
                        pct = count / filtered_count * 100
                        data_table += f'<tr><td>{i}</td><td>{name}</td><td>{count:,}</td><td>{pct:.1f}%</td></tr>'
                    data_table += '</table>'

            sections_html += f'''
            <div class="section">
                <h2 class="section-title">三、TOP10小类问题对比</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['03_TOP10小类问题对比']}" alt="TOP10小类问题对比">
                    <div class="chart-caption">小类问题案件量前10名对比分析</div>
                </div>
                <div class="analysis-text">
                    <strong>分析结论：</strong>{analysis_text}
                </div>
                {data_table}
            </div>
            '''

        # 四、片区案件分析
        if '04_片区案件对比' in charts_dict:
            analysis_text = ""
            data_table = ""
            if '所属片区' in df.columns:
                if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]
                    district_counts1 = df1['所属片区'].value_counts()
                    district_counts2 = df2['所属片区'].value_counts()

                    # 找出变化最大的片区
                    max_change_district = ""
                    max_change_pct = 0
                    for district in df['所属片区'].unique():
                        c1 = district_counts1.get(district, 0)
                        c2 = district_counts2.get(district, 0)
                        pct = (c2 - c1) / c1 * 100 if c1 > 0 else 0
                        if abs(pct) > abs(max_change_pct):
                            max_change_pct = pct
                            max_change_district = district

                    analysis_text = f'{max_change_district}案件量变化最显著({max_change_pct:+.1f}%)。建议根据片区案件分布调整资源配置。'

                    data_table = '<table class="data-table"><tr><th>片区</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化率</th></tr>'
                    for district in df['所属片区'].value_counts().index:
                        c1 = district_counts1.get(district, 0)
                        c2 = district_counts2.get(district, 0)
                        pct = (c2 - c1) / c1 * 100 if c1 > 0 else (100 if c2 > 0 else 0)
                        color_class = 'positive' if pct > 0 else ('negative' if pct < 0 else '')
                        data_table += f'<tr><td>{district}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{pct:+.1f}%</td></tr>'
                    data_table += '</table>'

            sections_html += f'''
            <div class="section">
                <h2 class="section-title">四、片区案件分析</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['04_片区案件对比']}" alt="片区案件分析">
                    <div class="chart-caption">各片区案件数量对比及变化率分析</div>
                </div>
                <div class="analysis-text">
                    <strong>分析结论：</strong>{analysis_text}
                </div>
                {data_table}
            </div>
            '''

        # 五、问题来源分析
        if '05_问题来源对比' in charts_dict:
            analysis_text = ""
            data_table = ""
            if '问题来源' in df.columns:
                if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]
                    source_counts1 = df1['问题来源'].value_counts()
                    source_counts2 = df2['问题来源'].value_counts()

                    main_source = df['问题来源'].value_counts().index[0] if len(df['问题来源'].value_counts()) > 0 else ''
                    main_pct = df['问题来源'].value_counts().values[0] / len(df) * 100 if len(df['问题来源'].value_counts()) > 0 else 0

                    analysis_text = f'{main_source}是主要案件来源，占比约{main_pct:.1f}%。建议优化监督员巡查路线，提升案件发现效率。'

                    data_table = '<table class="data-table"><tr><th>问题来源</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化率</th></tr>'
                    for source in df['问题来源'].value_counts().head(5).index:
                        c1 = source_counts1.get(source, 0)
                        c2 = source_counts2.get(source, 0)
                        pct = (c2 - c1) / c1 * 100 if c1 > 0 else (100 if c2 > 0 else 0)
                        color_class = 'positive' if pct > 0 else ('negative' if pct < 0 else '')
                        data_table += f'<tr><td>{source}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{pct:+.1f}%</td></tr>'
                    data_table += '</table>'

            sections_html += f'''
            <div class="section">
                <h2 class="section-title">五、问题来源分析</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['05_问题来源对比']}" alt="问题来源分析">
                    <div class="chart-caption">各问题来源渠道案件量对比</div>
                </div>
                <div class="analysis-text">
                    <strong>分析结论：</strong>{analysis_text}
                </div>
                {data_table}
            </div>
            '''

        # 六、处置部门分析（月度对比）
        if '07_处置部门TOP10对比' in charts_dict:
            analysis_text = ""
            data_table = ""
            if '处置部门' in df.columns:
                if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]
                    dept_counts1 = df1['处置部门'].value_counts()
                    dept_counts2 = df2['处置部门'].value_counts()

                    # 获取两个月TOP10的并集，确保数据完整
                    all_depts = list(set(dept_counts1.head(10).index) | set(dept_counts2.head(10).index))
                    all_depts.sort(key=lambda x: dept_counts2.get(x, 0) + dept_counts1.get(x, 0), reverse=True)

                    main_dept = all_depts[0] if all_depts else ''
                    main_count1 = dept_counts1.get(main_dept, 0)
                    main_count2 = dept_counts2.get(main_dept, 0)

                    analysis_text = f'{main_dept}承担案件量最多，{months[0]}为{main_count1}件，{months[1]}为{main_count2}件。建议根据案件分布调整人力配置，优化案件分流机制。'

                    data_table = '<table class="data-table"><tr><th>处置部门</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化率</th></tr>'
                    for dept in all_depts[:10]:
                        c1 = dept_counts1.get(dept, 0)
                        c2 = dept_counts2.get(dept, 0)
                        pct = (c2 - c1) / c1 * 100 if c1 > 0 else (100 if c2 > 0 else 0)
                        color_class = 'positive' if pct > 0 else ('negative' if pct < 0 else '')
                        data_table += f'<tr><td>{dept}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{pct:+.1f}%</td></tr>'
                    data_table += '</table>'
                else:
                    dept_counts = df['处置部门'].value_counts().head(6)
                    main_dept = dept_counts.index[0] if len(dept_counts) > 0 else ''
                    main_count = dept_counts.values[0] if len(dept_counts) > 0 else 0
                    analysis_text = f'{main_dept}承担案件量最多({main_count}件)。建议根据案件分布调整人力配置。'
                    data_table = '<table class="data-table"><tr><th>处置部门</th><th>案件数</th></tr>'
                    for dept, count in dept_counts.items():
                        data_table += f'<tr><td>{dept}</td><td>{count:,}</td></tr>'
                    data_table += '</table>'

            sections_html += f'''
            <div class="section">
                <h2 class="section-title">六、处置部门分析</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['07_处置部门TOP10对比']}" alt="处置部门TOP10对比">
                    <div class="chart-caption">处置部门案件量TOP10对比</div>
                </div>
                <div class="analysis-text">
                    <strong>分析结论：</strong>{analysis_text}
                </div>
                {data_table}
            </div>
            '''

        # 七、街道案件分布
        if '06_街道案件对比' in charts_dict:
            analysis_text = ""
            data_table = ""
            if '所属街道' in df.columns:
                if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]
                    street_counts1 = df1['所属街道'].value_counts()
                    street_counts2 = df2['所属街道'].value_counts()

                    main_street = df['所属街道'].value_counts().index[0] if len(df['所属街道'].value_counts()) > 0 else ''
                    main_count = df['所属街道'].value_counts().values[0] if len(df['所属街道'].value_counts()) > 0 else 0

                    analysis_text = f'{main_street}案件量最高({main_count}件)。建议重点关注案件量高的街道区域城市管理问题。'

                    data_table = '<table class="data-table"><tr><th>街道</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>合计</th></tr>'
                    for street in df['所属街道'].value_counts().head(5).index:
                        c1 = street_counts1.get(street, 0)
                        c2 = street_counts2.get(street, 0)
                        total = c1 + c2
                        data_table += f'<tr><td>{street}</td><td>{c1:,}</td><td>{c2:,}</td><td>{total:,}</td></tr>'
                    data_table += '</table>'

            sections_html += f'''
            <div class="section">
                <h2 class="section-title">七、街道案件分布</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['06_街道案件对比']}" alt="街道案件分布">
                    <div class="chart-caption">各街道案件量对比分析</div>
                </div>
                <div class="analysis-text">
                    <strong>分析结论：</strong>{analysis_text}
                </div>
                {data_table}
            </div>
            '''

        # 八、效率指标分析（案件状态）
        if '08_案件状态对比' in charts_dict:
            analysis_text = ""
            data_table = ""
            if '当前阶段名称' in df.columns:
                if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                    df1 = df[df[month_col] == months[0]]
                    df2 = df[df[month_col] == months[1]]

                    # 计算结案率
                    rate1 = (df1['当前阶段名称'] == '[办结]').sum() / len(df1) * 100 if len(df1) > 0 else 0
                    rate2 = (df2['当前阶段名称'] == '[办结]').sum() / len(df2) * 100 if len(df2) > 0 else 0

                    delay1 = pd.to_numeric(df1['延期次数'], errors='coerce').fillna(0).sum() if '延期次数' in df1.columns else 0
                    delay2 = pd.to_numeric(df2['延期次数'], errors='coerce').fillna(0).sum() if '延期次数' in df2.columns else 0
                    rework1 = pd.to_numeric(df1['返工次数'], errors='coerce').fillna(0).sum() if '返工次数' in df1.columns else 0
                    rework2 = pd.to_numeric(df2['返工次数'], errors='coerce').fillna(0).sum() if '返工次数' in df2.columns else 0

                    analysis_text = f'结案率从{months[0]}的{rate1:.2f}%变化至{months[1]}的{rate2:.2f}%。延期次数从{int(delay1)}次变化至{int(delay2)}次，返工次数从{int(rework1)}次变化至{int(rework2)}次。'

                    data_table = f'''
                    <table class="data-table">
                        <tr>
                            <th>效率指标</th>
                            <th>{months[0]}</th>
                            <th>{months[1]}</th>
                            <th>变化</th>
                        </tr>
                        <tr>
                            <td>结案率</td>
                            <td>{rate1:.2f}%</td>
                            <td>{rate2:.2f}%</td>
                            <td class="{'positive' if rate2 > rate1 else 'negative'}">{rate2 - rate1:+.2f}%</td>
                        </tr>
                        <tr>
                            <td>延期次数</td>
                            <td>{int(delay1)}</td>
                            <td>{int(delay2)}</td>
                            <td class="{'positive' if delay2 < delay1 else 'negative'}">{int(delay2 - delay1):+}</td>
                        </tr>
                        <tr>
                            <td>返工次数</td>
                            <td>{int(rework1)}</td>
                            <td>{int(rework2)}</td>
                            <td class="{'negative' if rework2 > rework1 else 'positive'}">{int(rework2 - rework1):+}</td>
                        </tr>
                    </table>
                    '''

            sections_html += f'''
            <div class="section">
                <h2 class="section-title">八、效率指标分析</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{charts_dict['08_案件状态对比']}" alt="效率指标分析">
                    <div class="chart-caption">结案率与超时情况对比分析</div>
                </div>
                <div class="analysis-text">
                    <strong>分析结论：</strong>{analysis_text}
                </div>
                {data_table}
            </div>
            '''

        # 九、管理建议
        recommendations_html = ""
        recommendations_list = insights.get('recommendations', [])
        border_colors = ['#e74c3c', '#27ae60', '#9b59b6', '#f39c12']
        for i, rec in enumerate(recommendations_list):
            if rec and rec.strip():
                color = border_colors[i % len(border_colors)]
                recommendations_html += f'''
            <div class="finding-item" style="border-left-color: {color};">
                <h4>管理建议</h4>
                <p>{rec}</p>
            </div>
            '''

        # 只有有建议时才显示管理建议部分
        if recommendations_html.strip():
            sections_html += f'''
        <div class="section">
            <h2 class="section-title">九、管理建议</h2>
            <div class="key-findings">
                {recommendations_html}
            </div>
        </div>
        '''

        # HTML模板
        # CSS样式（独立变量，避免f-string转义问题）
        css_styles = '''
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }

            .header {
                text-align: center;
                padding-bottom: 30px;
                border-bottom: 3px solid #667eea;
                margin-bottom: 40px;
            }

            .header h1 {
                font-size: 36px;
                color: #333;
                margin-bottom: 10px;
            }

            .header .subtitle {
                font-size: 18px;
                color: #666;
            }

            .header .date {
                font-size: 14px;
                color: #999;
                margin-top: 10px;
            }

            .summary-box {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 20px;
                margin-bottom: 40px;
            }

            .summary-item {
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                padding: 25px;
                border-radius: 15px;
                text-align: center;
                transition: transform 0.3s ease;
            }

            .summary-item:hover {
                transform: translateY(-5px);
            }

            .summary-item .value {
                font-size: 32px;
                font-weight: bold;
                color: #667eea;
                margin-bottom: 5px;
            }

            .summary-item .label {
                font-size: 14px;
                color: #666;
            }

            .summary-item.highlight {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }

            .summary-item.highlight .value,
            .summary-item.highlight .label {
                color: white;
            }

            .section {
                margin-bottom: 50px;
            }

            .section-title {
                font-size: 24px;
                color: #333;
                margin-bottom: 20px;
                padding-left: 15px;
                border-left: 4px solid #667eea;
            }

            .chart-container {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 30px;
            }

            .chart-container img {
                width: 100%;
                border-radius: 10px;
            }

            .chart-caption {
                text-align: center;
                color: #666;
                margin-top: 15px;
                font-size: 14px;
            }

            .data-table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 30px;
            }

            .data-table th {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px;
                text-align: center;
                font-size: 14px;
            }

            .data-table td {
                padding: 12px;
                text-align: center;
                border-bottom: 1px solid #eee;
                font-size: 13px;
            }

            .data-table tr:nth-child(even) {
                background: #f8f9fa;
            }

            .data-table tr:hover {
                background: #e9ecef;
            }

            .positive {
                color: #27ae60;
                font-weight: bold;
            }

            .negative {
                color: #e74c3c;
                font-weight: bold;
            }

            .analysis-text {
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 20px;
                border-radius: 0 10px 10px 0;
                margin-bottom: 20px;
                font-size: 14px;
                line-height: 1.8;
            }

            .key-findings {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
                margin-bottom: 40px;
            }

            .finding-item {
                background: linear-gradient(to right, #e3f2fd, #f3e5f5);
                padding: 20px;
                border-radius: 10px;
                border-left: 4px solid #2196f3;
            }

            .finding-item h4 {
                color: #333;
                margin-bottom: 10px;
                font-size: 16px;
            }

            .finding-item p {
                color: #666;
                font-size: 13px;
                line-height: 1.6;
            }

            .dashboard-img {
                width: 100%;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }

            .footer {
                text-align: center;
                padding-top: 30px;
                border-top: 1px solid #eee;
                color: #999;
                font-size: 12px;
            }

            @media (max-width: 768px) {
                .summary-box {
                    grid-template-columns: repeat(2, 1fr);
                }
                .key-findings {
                    grid-template-columns: 1fr;
                }
            }
        '''

        html_template = f'''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>案件数据分析报告 - {report_title}</title>
        <style>
        {css_styles}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>案件数据分析报告</h1>
                <div class="subtitle">{report_title}</div>
                <div class="date">生成日期: {datetime.datetime.now().strftime('%Y年%m月%d日')}</div>
            </div>

            <!-- 核心数据概览 -->
            {summary_box_html}

            <!-- 关键发现 -->
            {findings_section}

            <!-- 综合仪表盘 -->
            {dashboard_html}

            <!-- 各部分分析 -->
            {sections_html}

            <div class="footer">
                <p>数据分析报告 - 自动生成 | 数据来源: 案件管理系统</p>
                <p>如有疑问请联系相关部门核实数据准确性</p>
            </div>
        </div>
    </body>
    </html>
        '''

        return html_template
