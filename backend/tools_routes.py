# -*- coding: utf-8 -*-
"""小工具路由模块 - 环卫分配、地址提取等"""
import os
import pandas as pd
from flask import request, jsonify, send_file

def register_tools_routes(app, protected, extract_location_from_text):
    """注册小工具相关路由"""

    @app.route('/api/tools/huanwei-assignment', methods=['POST'])
    @protected
    def huanwei_assignment():
        import tempfile
        output_file = None
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400

            if not file.filename.endswith('.xlsx'):
                return jsonify({'error': 'Only xlsx files are allowed'}), 400

            print(f"Processing huanwei assignment file: {file.filename}")

            try:
                df = pd.read_excel(file)
                print(f"Successfully read Excel file, rows: {len(df)}, columns: {list(df.columns)}")
            except Exception as read_error:
                print(f"Error reading Excel file: {str(read_error)}")
                return jsonify({'error': f'读取Excel文件失败: {str(read_error)}'}), 400

            required_cols = ['处置部门', '所属片区']
            for col in required_cols:
                if col not in df.columns:
                    return jsonify({'error': f'Missing required column: {col}. 文件中必须包含以下列: {", ".join(required_cols)}'}), 400

            filter_condition = df["处置部门"] == "市容环卫中心"
            matched_count = filter_condition.sum()
            print(f"Found {matched_count} rows with '市容环卫中心' as 处置部门")

            df["所属片区"] = df["所属片区"].astype(str)
            df.loc[filter_condition, "处置部门"] = "环卫" + df.loc[filter_condition, "所属片区"]

            print(f"Updated {matched_count} rows with new department names")

            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
                output_file = temp.name

            df.to_excel(output_file, index=False)
            print(f"Successfully saved processed file to: {output_file}")

            response = send_file(output_file, as_attachment=True, download_name='hwcase_data_updated.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

            @response.call_on_close
            def cleanup():
                try:
                    if output_file and os.path.exists(output_file):
                        os.remove(output_file)
                        print(f"Cleaned up temporary file: {output_file}")
                except Exception as cleanup_error:
                    print(f"Error cleaning up temporary file: {cleanup_error}")

            return response
        except Exception as e:
            print(f"Error in huanwei_assignment: {str(e)}")
            import traceback
            traceback.print_exc()
            if output_file and os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
            return jsonify({'error': f'处理文件时出错: {str(e)}'}), 500

    @app.route('/api/tools/extract-location', methods=['POST'])
    @protected
    def extract_location():
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400

            if not file.filename.endswith('.xlsx'):
                return jsonify({'error': 'Only xlsx files are allowed'}), 400

            df = pd.read_excel(file)

            required_cols = ['问题描述', '地址描述']
            for col in required_cols:
                if col not in df.columns:
                    return jsonify({'error': f'Missing required column: {col}'}), 400

            updated_count = 0
            for idx, row in df.iterrows():
                addr_desc = str(row["地址描述"]).strip()
                if addr_desc in ["无位置信息", "无位置描述", "没有相关位置描述", "nan"]:
                    new_addr = extract_location_from_text(row["问题描述"])
                    df.loc[idx, "地址描述"] = new_addr
                    updated_count += 1

            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
                output_file = temp.name

            df.to_excel(output_file, index=False)

            return send_file(output_file, as_attachment=True, download_name='case_data_with_extracted_location.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception as e:
            print(f"Error in extract_location: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
