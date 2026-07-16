# -*- coding: utf-8 -*-
"""考核评分路由模块 - 考核评分、系数管理"""
import os
import json
from flask import request, jsonify
from helpers import convert_nan_to_null, read_file_content

def register_assessment_routes(app, Session, engine, protected, call_llm_api, API_URL, API_KEY, MODEL, calculate_law_enforcement_score, calculate_huanwei_score, calculate_garden_score, calculate_park_score, calculate_generic_score,
                               calculate_law_enforcement_score_v2=None, calculate_huanwei_score_v2=None, calculate_garden_score_v2=None, calculate_park_score_v2=None):
    """注册考核评分相关路由"""

    # 系数配置文件路径
    COEFFICIENTS_FILE = os.path.join(os.path.dirname(__file__), 'assessment_coefficients.json')

    # 部门列表
    DEPARTMENTS = [
        '城市综合行政执法队',
        '市容环卫中心',
        '园林绿化服务中心（片区）',
        '园林绿化服务中心（公园广场）'
    ]

    # 默认系数
    DEFAULT_COEFFICIENTS = {
        'on_time': 1.0,
        'overdue': 0.4,
        'closure_weight': 0.8,
        'delay_weight': 0.1,
        'rework_weight': 0.1
    }

    def load_coefficients():
        """从文件加载系数配置"""
        try:
            if os.path.exists(COEFFICIENTS_FILE):
                with open(COEFFICIENTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 检查是否是旧格式（单个系数对象）
                if 'on_time' in data and not any(dept in data for dept in DEPARTMENTS):
                    # 转换为新格式：将旧系数应用到所有部门
                    new_coefficients = {dept: data.copy() for dept in DEPARTMENTS}
                    # 保存转换后的格式
                    save_coefficients_to_file(new_coefficients)
                    return new_coefficients
                # 检查是否是新格式但缺少某些部门
                if isinstance(data, dict):
                    for dept in DEPARTMENTS:
                        if dept not in data:
                            data[dept] = DEFAULT_COEFFICIENTS.copy()
                    return data
        except Exception as e:
            print(f"Error loading coefficients: {e}")
        # 返回每个部门的默认系数
        return {dept: DEFAULT_COEFFICIENTS.copy() for dept in DEPARTMENTS}

    def save_coefficients_to_file(coefficients):
        """保存系数配置到文件"""
        try:
            with open(COEFFICIENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(coefficients, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving coefficients: {e}")
            return False

    # 加载初始系数
    assessment_coefficients = load_coefficients()

    @app.route('/api/assess', methods=['POST'])
    @protected
    def assess():
        try:
            import pandas as pd
            data = request.json
            table_name = data.get('table_name')
            department = data.get('department')
            month = data.get('month', '')

            if not table_name or not department:
                return jsonify({'error': 'Missing table_name or department'}), 400

            df = pd.read_sql_table(table_name, engine)

            if month:
                month_col = None
                for col in ['月份', 'data_month']:
                    if col in df.columns:
                        month_col = col
                        break
                if month_col:
                    df = df[df[month_col] == month]
                    print(f"[考核计分] 筛选月份 {month}，剩余 {len(df)} 条数据")

            cases = df.to_dict('records')

            if department == '城市综合行政执法队':
                result = calculate_law_enforcement_score(cases)
            elif department == '市容环卫中心':
                result = calculate_huanwei_score(cases)
            elif department == '园林绿化服务中心（片区）':
                result = calculate_garden_score(cases)
            elif department == '园林绿化服务中心（公园广场）':
                result = calculate_park_score(cases)
            else:
                result = calculate_generic_score(cases)

            result['department'] = department
            result['table_name'] = table_name

            return jsonify(convert_nan_to_null(result)), 200
        except Exception as e:
            print(f"Error in assess: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/assess/v2', methods=['POST'])
    @protected
    def assess_v2():
        try:
            import pandas as pd
            data = request.json
            table_name = data.get('table_name')
            department = data.get('department')
            month = data.get('month', '')

            if not table_name or not department:
                return jsonify({'error': 'Missing table_name or department'}), 400

            # 每次都从文件重新加载最新的系数
            current_coefficients = load_coefficients()

            # 获取该部门的系数
            if department in current_coefficients:
                coefficients = current_coefficients[department]
            else:
                coefficients = DEFAULT_COEFFICIENTS.copy()

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
                    print(f"[考核计分V2] 筛选月份 {month}，剩余 {len(df)} 条数据")

            cases = df.to_dict('records')

            # 调试：打印当前阶段名称的唯一值
            if len(cases) > 0:
                stage_vals = set()
                for c in cases:
                    val = c.get('当前阶段名称')
                    if val is not None and pd.notna(val):
                        stage_vals.add(str(val))
                debug_msg = f"[调试] 当前阶段名称的唯一值: {sorted(stage_vals)}"
                print(debug_msg)
                with open('debug.log', 'a', encoding='utf-8') as f:
                    f.write(debug_msg + '\n')

            if department == '城市综合行政执法队':
                result = calculate_law_enforcement_score_v2(cases, coefficients) if calculate_law_enforcement_score_v2 else calculate_law_enforcement_score(cases)
            elif department == '市容环卫中心':
                result = calculate_huanwei_score_v2(cases, coefficients) if calculate_huanwei_score_v2 else calculate_huanwei_score(cases)
            elif department == '园林绿化服务中心（片区）':
                result = calculate_garden_score_v2(cases, coefficients) if calculate_garden_score_v2 else calculate_garden_score(cases)
            elif department == '园林绿化服务中心（公园广场）':
                result = calculate_park_score_v2(cases, coefficients) if calculate_park_score_v2 else calculate_park_score(cases)
            else:
                result = calculate_generic_score(cases)

            result['department'] = department
            result['table_name'] = table_name

            return jsonify(convert_nan_to_null(result)), 200
        except Exception as e:
            print(f"Error in assess_v2: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/spotcheck', methods=['POST'])
    @protected
    def spotcheck():
        session = Session()
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400

            allowed_extensions = {'.docx', '.xlsx'}
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in allowed_extensions:
                return jsonify({'error': 'Only docx and xlsx files are allowed'}), 400

            # 读取文件内容
            file_content = read_file_content(file)

            # 构建大模型提示
            prompt = f"请分析以下城市管理案件详情：\n{file_content}\n\n重要提示：处置时间是按照8小时工作时计算的，不是自然时间，且节假日和周末也不计时。\n\n分析要求：\n1、采集信息是否准确；\n2、受理、派遣、处置流程的时效（注意：处置时间按8小时工作时计算，节假日和周末不计时）；\n3、结案是否规范；\n4、是否有推诿扯皮现象；\n并分别给采集、受理、派遣、处置打分（0-100分），分析内容尽量简短。"

            # 调用大模型API（使用统一调用函数）
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的城市管理案件分析助手，擅长分析案件处理流程和质量。请根据提供的案件详情，生成详细的分析报告。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            success, result = call_llm_api(API_URL, API_KEY, MODEL, messages, max_tokens=2000, provider_name="抽查分析")
            if not success:
                raise Exception(f"大模型API调用失败: {result}")

            analysis_content = result

            scores = {
                'collection': 85,
                'acceptance': 80,
                'dispatch': 75,
                'disposal': 82
            }

            session.commit()
            return jsonify({
                'analysis': analysis_content,
                'scores': scores,
                'file_name': file.filename,
                'file_content': file_content
            }), 200
        except Exception as e:
            session.rollback()
            print(f"Error in spotcheck: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/assessment-coefficients', methods=['GET'])
    @protected
    def get_assessment_coefficients():
        nonlocal assessment_coefficients
        assessment_coefficients = load_coefficients()
        return jsonify(assessment_coefficients), 200

    @app.route('/api/assessment-coefficients', methods=['PUT'])
    @protected
    def save_assessment_coefficients():
        nonlocal assessment_coefficients
        try:
            data = request.json
            department = data.get('department')

            if not department or department not in DEPARTMENTS:
                return jsonify({'error': 'Invalid department'}), 400

            current_coefficients = load_coefficients()

            if 'coefficients' in data:
                current_coefficients[department] = data['coefficients']
            else:
                current_coefficients[department] = {
                    'on_time': data.get('on_time', DEFAULT_COEFFICIENTS['on_time']),
                    'overdue': data.get('overdue', DEFAULT_COEFFICIENTS['overdue']),
                    'closure_weight': data.get('closure_weight', DEFAULT_COEFFICIENTS['closure_weight']),
                    'delay_weight': data.get('delay_weight', DEFAULT_COEFFICIENTS['delay_weight']),
                    'rework_weight': data.get('rework_weight', DEFAULT_COEFFICIENTS['rework_weight'])
                }

            if save_coefficients_to_file(current_coefficients):
                assessment_coefficients = current_coefficients
                return jsonify({'message': 'Coefficients saved successfully', 'coefficients': current_coefficients}), 200
            else:
                return jsonify({'error': 'Failed to save coefficients'}), 500

        except Exception as e:
            print(f"Error in save_assessment_coefficients: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
