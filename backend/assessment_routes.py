# -*- coding: utf-8 -*-
"""考核评分路由模块 - 考核评分、系数管理"""
import os
import json
from flask import request, jsonify
from helpers import protected, convert_nan_to_null

def register_assessment_routes(app, Session, engine, call_llm_api, calculate_law_enforcement_score, calculate_huanwei_score, calculate_garden_score, calculate_park_score, calculate_generic_score):
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
            month = data.get('month', '')  # 新增：月份筛选

            if not table_name or not department:
                return jsonify({'error': 'Missing table_name or department'}), 400

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
                    print(f"[考核计分] 筛选月份 {month}，剩余 {len(df)} 条数据")

            cases = df.to_dict('records')
            
            # 根据部门选择计算逻辑
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
            
            # 添加元数据
            result['department'] = department
            result['table_name'] = table_name
            
            return jsonify(convert_nan_to_null(result)), 200
        except Exception as e:
            print(f"Error in assess: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/assessment-coefficients', methods=['GET'])
    @protected
    def get_assessment_coefficients():
        nonlocal assessment_coefficients
        # 每次都从文件重新加载，确保获取最新配置
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
            
            # 加载当前所有系数
            current_coefficients = load_coefficients()
            
            # 更新指定部门的系数
            if 'coefficients' in data:
                current_coefficients[department] = data['coefficients']
            else:
                # 兼容旧格式
                current_coefficients[department] = {
                    'on_time': data.get('on_time', DEFAULT_COEFFICIENTS['on_time']),
                    'overdue': data.get('overdue', DEFAULT_COEFFICIENTS['overdue']),
                    'closure_weight': data.get('closure_weight', DEFAULT_COEFFICIENTS['closure_weight']),
                    'delay_weight': data.get('delay_weight', DEFAULT_COEFFICIENTS['delay_weight']),
                    'rework_weight': data.get('rework_weight', DEFAULT_COEFFICIENTS['rework_weight'])
                }
            
            # 保存到文件
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
