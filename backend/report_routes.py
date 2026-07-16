# -*- coding: utf-8 -*-
"""智能报告与视频报告路由模块"""
import os
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import request, jsonify, send_file

def register_report_routes(app, engine, protected, admin_required, call_llm_api):
    """注册智能报告与视频报告相关路由"""

    @app.route('/api/smart-report', methods=['POST'])
    @protected
    def smart_report():
        """智能报告生成API"""
        try:
            data = request.json
            table_name = data.get('table_name')
            template_type = data.get('template_type')
            months = data.get('months', [])
            year = data.get('year', '')
            dimension = data.get('dimension', '')
            dimension_values = data.get('dimension_values', [])

            if not table_name or not template_type:
                return jsonify({'error': 'Missing required parameters'}), 400

            print(f"[智能报告] 开始生成报告, 表: {table_name}, 模板: {template_type}")

            df = pd.read_sql_table(table_name, engine)
            original_count = len(df)

            # 月份筛选
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

            if filtered_count == 0:
                return jsonify({'error': '筛选后数据为空，请调整筛选条件'}), 400

            # 生成图表
            charts_base64 = generate_smart_report_charts(df, template_type, months, dimension, dimension_values)

            # 生成洞察
            insights = generate_report_insights(df, template_type, months, year, dimension, dimension_values)

            # 渲染HTML报告
            html_report = render_smart_report_html(
                df, template_type, months, year, dimension, dimension_values,
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
            import tempfile

            generator = VideoReportGenerator()
            output_path = tempfile.mktemp(suffix='.mp4')

            charts_data = []
            try:
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
            import tempfile

            table_name = 'cases'
            template_type = 'monthly_comparison'
            months = ['202603', '202602']

            print(f"[视频调试] 参数: table={table_name}, template={template_type}")
            report_title = f"{months[0]}与{months[1]}对比分析报告"

            try:
                df = pd.read_sql_table(table_name, engine)
                print(f"[视频调试] 数据库读取成功: {len(df)} 条记录")
            except Exception as e:
                print(f"[视频调试] 数据库读取失败: {e}")
                df = pd.DataFrame({
                    '大类名称': ['市容环境', '市容环境', '市政设施'],
                    '所属片区': ['片区A', '片区B', '片区A'],
                    '当前阶段名称': ['[办结]', '[办结]', '处置中']
                })

            try:
                charts_base64 = generate_smart_report_charts(df, template_type, months, '', [])
                print(f"[视频调试] 图表生成成功: {len(charts_base64)} 个")
            except Exception as e:
                print(f"[视频调试] 图表生成失败: {e}")
                charts_base64 = []

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

            print(f"[视频调试] 洞察生成完成")

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
        """视频报告生成API"""
        try:
            from video_report import VideoReportGenerator
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

            try:
                df = pd.read_sql_table(table_name, engine)
                original_count = len(df)
                print(f"[视频报告] 读取数据: {original_count} 条")
            except Exception as e:
                print(f"[视频报告] 数据库读取失败: {e}")
                return jsonify({'error': f'数据库读取失败: {str(e)}'}), 500

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

            try:
                charts_base64 = generate_smart_report_charts(df, template_type, months, dimension, dimension_values)
                print(f"[视频报告] 图表生成完成: {len(charts_base64)} 个")
            except Exception as e:
                print(f"[视频报告] 图表生成失败: {e}")
                charts_base64 = []

            try:
                insights = {
                    'summary': f'共分析{filtered_count}条数据' + (f'，{filter_desc}' if filter_desc else ''),
                    'key_findings': [],
                    'chart_insights': {}
                }

                if '大类名称' in df.columns:
                    top_type = df['大类名称'].value_counts().head(1)
                    if len(top_type) > 0:
                        insights['key_findings'].append(f"主要问题类型: {top_type.index[0]}, 共{top_type.values[0]}件")

                if '所属片区' in df.columns:
                    top_district = df['所属片区'].value_counts().head(1)
                    if len(top_district) > 0:
                        insights['key_findings'].append(f"案件集中区域: {top_district.index[0]}, 共{top_district.values[0]}件")

                if '当前阶段名称' in df.columns:
                    completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
                else:
                    completion_rate = 0

                is_monthly_comparison = template_type == 'monthly_comparison' and months and len(months) >= 2

                for chart_name, _ in charts_base64:
                    chart_display = chart_name
                    if len(chart_name) > 3 and chart_name[2] == '_':
                        chart_display = chart_name[3:]

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

            print("[视频报告] 开始生成视频文件...")
            generator = VideoReportGenerator()
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

            response = send_file(
                video_path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name=f'{report_title}.mp4'
            )

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


def fig_to_base64(fig):
    """将matplotlib图表转换为base64字符串"""
    import io
    import base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_str


def generate_smart_report_charts(df, template_type, months, dimension, dimension_values):
    """生成精美图表，返回base64编码列表"""
    charts = []

    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'SimSun']
    plt.rcParams['axes.unicode_minus'] = False

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
    df = df.rename(columns=column_mapping)

    colors_palette = ['#4ECDC4', '#FF6B6B', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']
    color_m1 = '#4ECDC4'
    color_m2 = '#FF6B6B'

    month_col = None
    for col in ['月份', 'data_month']:
        if col in df.columns:
            month_col = col
            break

    is_monthly_comparison = template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col

    try:
        # 综合仪表盘
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle('案件数据分析综合仪表盘', fontsize=22, fontweight='bold', y=0.98)
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.25)

        ax1 = fig.add_subplot(gs[0, 0])
        total_count = len(df)
        ax1.text(0.5, 0.6, f'{total_count:,}', ha='center', va='center', fontsize=36, fontweight='bold', color='#667eea')
        ax1.text(0.5, 0.3, '案件总量', ha='center', va='center', fontsize=16, color='#666')
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1)
        ax1.axis('off')
        ax1.add_patch(plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor='#667eea', linewidth=2, transform=ax1.transAxes))

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

        ax3 = fig.add_subplot(gs[0, 2])
        type_count = len(df['大类名称'].unique()) if '大类名称' in df.columns else 0
        ax3.text(0.5, 0.6, f'{type_count}', ha='center', va='center', fontsize=36, fontweight='bold', color='#FF6B6B')
        ax3.text(0.5, 0.3, '问题类型', ha='center', va='center', fontsize=16, color='#666')
        ax3.set_xlim(0, 1)
        ax3.set_ylim(0, 1)
        ax3.axis('off')
        ax3.add_patch(plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor='#FF6B6B', linewidth=2, transform=ax3.transAxes))

        ax4 = fig.add_subplot(gs[1, 0:2])
        if '大类名称' in df.columns:
            type_counts = df['大类名称'].value_counts().head(6)
            colors_pie = colors_palette[:len(type_counts)]
            wedges, texts, autotexts = ax4.pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%',
                                               colors=colors_pie, startangle=90, textprops={'fontsize': 11})
            ax4.set_title('问题类型分布', fontsize=14, fontweight='bold', pad=10)

        ax5 = fig.add_subplot(gs[1, 2])
        if '所属片区' in df.columns:
            district_counts = df['所属片区'].value_counts().head(5)
            bars = ax5.barh(range(len(district_counts)), district_counts.values[::-1],
                           color=colors_palette[:len(district_counts)])
            ax5.set_yticks(range(len(district_counts)))
            ax5.set_yticklabels(district_counts.index[::-1], fontsize=11)
            ax5.set_xlabel('案件数', fontsize=11)
            ax5.set_title('片区分布', fontsize=14, fontweight='bold', pad=10)

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

        ax7 = fig.add_subplot(gs[2, 2])
        if '问题来源' in df.columns:
            source_counts = df['问题来源'].value_counts().head(4)
            colors_src = ['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'][:len(source_counts)]
            wedges, texts, autotexts = ax7.pie(source_counts.values, labels=source_counts.index, autopct='%1.1f%%',
                                               colors=colors_src, startangle=90, textprops={'fontsize': 9})
            ax7.set_title('问题来源', fontsize=14, fontweight='bold', pad=10)

        charts.append(('00_综合仪表盘', fig_to_base64(fig)))

        # 案件总量对比
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
            if len(months) == 2 and month_counts.values[0] > 0:
                change = month_counts.values[1] - month_counts.values[0]
                change_pct = change / month_counts.values[0] * 100
                color = '#e74c3c' if change > 0 else '#27ae60'
                ax.text(0.5, 0.95, f'环比变化: {change:+,} ({change_pct:+.1f}%)',
                        transform=ax.transAxes, ha='center', fontsize=14, color=color, fontweight='bold')
            plt.tight_layout()
            charts.append(('01_案件总量对比', fig_to_base64(fig)))

        # 问题类型对比
        if '大类名称' in df.columns:
            if is_monthly_comparison:
                fig, ax = plt.subplots(figsize=(14, 8))
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                type_counts1 = df1['大类名称'].value_counts()
                type_counts2 = df2['大类名称'].value_counts()
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
                fig, ax = plt.subplots(figsize=(10, 8))
                type_counts = df['大类名称'].value_counts()
                colors = colors_palette[:len(type_counts)]
                wedges, texts, autotexts = ax.pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%',
                                                   colors=colors, startangle=90, textprops={'fontsize': 10})
                ax.set_title('问题类型分布', fontsize=16, fontweight='bold', pad=15)
            charts.append(('02_问题类型对比', fig_to_base64(fig)))

        # TOP10小类问题对比
        if '小类名称' in df.columns:
            if is_monthly_comparison:
                fig, ax = plt.subplots(figsize=(14, 8))
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                all_counts1 = df1['小类名称'].value_counts()
                all_counts2 = df2['小类名称'].value_counts()
                top10_1_names = set(all_counts1.head(10).index)
                top10_2_names = set(all_counts2.head(10).index)
                all_items = list(top10_1_names | top10_2_names)
                all_items.sort(key=lambda x: all_counts2.get(x, 0) + all_counts1.get(x, 0), reverse=True)
                all_items = all_items[:10]
                y = np.arange(len(all_items))
                width = 0.35
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

        # 片区案件对比
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

        # 问题来源对比
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

        # 街道案件对比
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

        # 处置部门TOP10对比
        if '处置部门' in df.columns:
            if is_monthly_comparison:
                fig, ax = plt.subplots(figsize=(14, 8))
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                all_dept_counts1 = df1['处置部门'].value_counts()
                all_dept_counts2 = df2['处置部门'].value_counts()
                top10_1_names = set(all_dept_counts1.head(10).index)
                top10_2_names = set(all_dept_counts2.head(10).index)
                all_depts = list(top10_1_names | top10_2_names)
                all_depts.sort(key=lambda x: all_dept_counts2.get(x, 0) + all_dept_counts1.get(x, 0), reverse=True)
                all_depts = all_depts[:10]
                y = np.arange(len(all_depts))
                width = 0.35
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
                fig, ax = plt.subplots(figsize=(12, 6))
                dept_counts = df['处置部门'].value_counts().head(10)
                colors = plt.cm.Greens(np.linspace(0.4, 0.9, len(dept_counts)))[::-1]
                bars = ax.barh(range(len(dept_counts)), dept_counts.values[::-1], color=colors)
                ax.set_yticks(range(len(dept_counts)))
                ax.set_yticklabels(dept_counts.index[::-1], fontsize=10)
                ax.set_xlabel('案件数量', fontsize=12)
                ax.set_title('处置部门TOP10', fontsize=16, fontweight='bold', pad=15)
            charts.append(('07_处置部门TOP10对比', fig_to_base64(fig)))

        # 案件状态对比
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
                ax.set_xticklabels(all_status, rotation=45, ha='right', fontsize=10)
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('案件状态对比', fontsize=16, fontweight='bold', pad=15)
                ax.legend(fontsize=12)
                plt.tight_layout()
            else:
                fig, ax = plt.subplots(figsize=(10, 6))
                status_counts = df['当前阶段名称'].value_counts()
                colors = ['#27ae60' if '[办结]' in str(s) else '#f39c12' for s in status_counts.index]
                bars = ax.bar(status_counts.index, status_counts.values, color=colors, edgecolor='white')
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('案件状态分布', fontsize=16, fontweight='bold', pad=15)
            charts.append(('08_案件状态对比', fig_to_base64(fig)))

    except Exception as e:
        print(f"[图表生成] 错误: {e}")
        import traceback
        traceback.print_exc()

    return charts


def generate_report_insights(df, template_type, months, year, dimension, dimension_values):
    """生成报告洞察"""
    insights = {
        'summary': f'共分析{len(df)}条数据',
        'key_findings': [],
        'chart_insights': {}
    }

    if '大类名称' in df.columns:
        top_type = df['大类名称'].value_counts().head(1)
        if len(top_type) > 0:
            insights['key_findings'].append(f"主要问题类型: {top_type.index[0]}, 共{top_type.values[0]}件")

    if '所属片区' in df.columns:
        top_district = df['所属片区'].value_counts().head(1)
        if len(top_district) > 0:
            insights['key_findings'].append(f"案件集中区域: {top_district.index[0]}, 共{top_district.values[0]}件")

    return insights


def render_smart_report_html(df, template_type, months, year, dimension, dimension_values,
                             charts_base64=None, insights=None, filter_desc="",
                             original_count=0, filtered_count=0):
    """渲染智能报告HTML"""
    if charts_base64 is None:
        charts_base64 = []
    if insights is None:
        insights = {'summary': '', 'key_findings': [], 'chart_insights': {}}

    # 构建报告标题
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

    # 构建关键发现HTML
    findings_html = ""
    if insights and insights.get('key_findings'):
        findings_html = '<div class="findings"><h3>关键发现</h3><ul>'
        for finding in insights['key_findings']:
            findings_html += f'<li>{finding}</li>'
        findings_html += '</ul></div>'

    # 构建图表HTML
    charts_html = ""
    if charts_base64:
        for chart_name, chart_base64 in charts_base64:
            display_name = chart_name
            if len(chart_name) > 3 and chart_name[2] == '_':
                display_name = chart_name[3:]
            insight = insights.get('chart_insights', {}).get(chart_name, '')
            charts_html += f'''
            <div class="chart-section">
                <h3>{display_name}</h3>
                <img src="data:image/png;base64,{chart_base64}" alt="{display_name}">
                <p class="chart-insight">{insight}</p>
            </div>
            '''

    html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; text-align: center; border-bottom: 3px solid #4ECDC4; padding-bottom: 15px; }}
        h2 {{ color: #444; margin-top: 30px; }}
        h3 {{ color: #555; }}
        .summary {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .findings {{ background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .findings ul {{ margin: 10px 0; }}
        .findings li {{ margin: 8px 0; }}
        .chart-section {{ margin: 30px 0; text-align: center; }}
        .chart-section img {{ max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .chart-insight {{ color: #666; font-style: italic; margin-top: 10px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #999; text-align: center; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{report_title}</h1>

        <div class="summary">
            <h2>数据概况</h2>
            <p>原始数据量: {original_count} 条</p>
            <p>筛选后数据量: {filtered_count} 条</p>
            {f"<p>筛选条件: {filter_desc}</p>" if filter_desc else ""}
        </div>

        {findings_html}

        {charts_html}

        <div class="footer">
            <p>数据分析报告 - 自动生成 | 数据来源: 案件管理系统</p>
            <p>如有疑问请联系相关部门核实数据准确性</p>
        </div>
    </div>
</body>
</html>
    '''

    return html_template
