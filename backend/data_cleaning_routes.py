"""
data_cleaning_routes.py —— 数据清洗API路由
==========================================
提供原始数据上传、清洗预览、确认入库等功能
"""
import os
import io
import datetime
import logging
import pandas as pd
from flask import request, jsonify
from sqlalchemy import text

from cleaning_rules import (
    prepare_dataframe, run_cleaning,
    parse_delay_rework_txt, parse_delay_rework_excel
)

logger = logging.getLogger(__name__)

try:
    from common import protected as _protected, admin_required as _admin_required
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required


# 上传文件存储目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads', 'cleaning')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 五大片区GeoJSON路径（用户在QGIS中绘制后放到此位置）
DISTRICT_GEOJSON = os.path.join(
    os.path.dirname(__file__), '..', 'frontend', 'public', 'data', '采集员片区.geojson'
)


def register_data_cleaning_routes(app, engine=None):
    """注册数据清洗相关路由"""
    protected = _protected

    @app.route('/api/cleaning/upload', methods=['POST'])
    @protected
    def cleaning_upload():
        """上传原始Excel，返回预览数据"""
        if 'file' not in request.files:
            return jsonify({'error': '请选择文件'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'error': '文件名为空'}), 400

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ('.xlsx', '.xls'):
            return jsonify({'error': '仅支持 .xlsx / .xls 格式'}), 400

        try:
            file_bytes = file.read()
            df = pd.read_excel(io.BytesIO(file_bytes))

            # 列名检查
            expected_cols = set(RAW_COLUMN_MAP.keys())
            actual_cols = set(df.columns)
            missing = expected_cols - actual_cols
            if missing:
                return jsonify({
                    'error': f'缺少必要列: {", ".join(missing)}',
                    'actual_columns': list(df.columns)
                }), 400

            # 准备预览数据（前10行）
            preview_df = prepare_dataframe(df.head(10))
            preview_data = preview_df.fillna('').to_dict('records')

            return jsonify({
                'success': True,
                'total_rows': len(df),
                'columns': list(df.columns),
                'preview': preview_data,
                'file_id': None  # 暂不保存文件，直接处理
            })
        except Exception as e:
            logger.error(f'上传解析失败: {e}')
            return jsonify({'error': f'文件解析失败: {str(e)}'}), 400

    @app.route('/api/cleaning/preview', methods=['POST'])
    @protected
    def cleaning_preview():
        """执行清洗规则，返回清洗前后对比"""
        if not request.json:
            return jsonify({'error': '请求体为空'}), 400

        data = request.json
        file_data = data.get('file_data')
        rules_config = data.get('rules_config', {})
        geojson_path = data.get('geojson_path')

        if not file_data:
            return jsonify({'error': '缺少文件数据'}), 400

        try:
            # 重建DataFrame
            df = pd.DataFrame(file_data)
            original_df = df.copy()

            # 执行清洗
            df, report = run_cleaning(
                df, rules_config,
                engine=engine,
                geojson_path=geojson_path or DISTRICT_GEOJSON
            )

            # 生成对比数据（前20行）
            compare_rows = []
            check_cols = ['source', 'description', 'district', 'community',
                          'longitude', 'latitude', 'supervisor',
                          'is_delayed', 'is_rework']
            for i in range(min(20, len(df))):
                row_before = {}
                row_after = {}
                changes = []
                for col in check_cols:
                    if col in original_df.columns and col in df.columns:
                        before = str(original_df.iloc[i].get(col, ''))
                        after = str(df.iloc[i].get(col, ''))
                        if before != after and before != 'nan' and after != 'nan':
                            row_before[col] = before
                            row_after[col] = after
                            changes.append(col)
                if changes:
                    compare_rows.append({
                        'index': i + 1,
                        'task_no': str(df.iloc[i].get('task_no', '')),
                        'changes': changes,
                        'before': row_before,
                        'after': row_after
                    })

            # 清洗后的完整数据（用于后续入库）
            cleaned_data = df.fillna('').to_dict('records')

            return jsonify({
                'success': True,
                'report': report,
                'compare': compare_rows,
                'total_rows': len(df),
                'cleaned_data': cleaned_data
            })
        except Exception as e:
            logger.error(f'清洗预览失败: {e}')
            return jsonify({'error': f'清洗处理失败: {str(e)}'}), 500

    @app.route('/api/cleaning/execute', methods=['POST'])
    @protected
    def cleaning_execute():
        """确认入库"""
        if not engine:
            return jsonify({'error': '数据库未连接'}), 500

        if not request.json:
            return jsonify({'error': '请求体为空'}), 400

        data = request.json
        cleaned_data = data.get('cleaned_data')
        batch = data.get('batch', '').strip()

        if not cleaned_data:
            return jsonify({'error': '缺少清洗后数据'}), 400

        if not batch:
            # 自动推断月份
            try:
                df_temp = pd.DataFrame(cleaned_data)
                if 'deadline_bundled' in df_temp.columns:
                    parsed = pd.to_datetime(df_temp['deadline_bundled'], errors='coerce').dropna()
                    if not parsed.empty:
                        batch = parsed.dt.strftime('%Y%m').mode().iloc[0]
                if not batch:
                    batch = datetime.datetime.now().strftime('%Y%m')
            except Exception:
                batch = datetime.datetime.now().strftime('%Y%m')

        try:
            df = pd.DataFrame(cleaned_data)

            # 确保必要列存在
            for col in ['is_delayed', 'is_rework']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: 1 if str(x).strip() in ('1', 'True', 'true', '是') else 0).astype(int)

            for col in ['report_time', 'close_time', 'deadline', 'deadline_bundled']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

            # 添加元数据
            df['upload_batch'] = batch
            df['uploader'] = 'cleaning_module'

            # 选择要入库的列
            db_columns = [
                'upload_batch', 'report_time', 'task_no', 'big_category',
                'small_category', 'source', 'description', 'stage',
                'department', 'deadline_bundled', 'close_time', 'district',
                'issue_type', 'address', 'street', 'community', 'supervisor',
                'deadline', 'is_delayed', 'is_rework', 'longitude', 'latitude',
                'reason_delayed', 'opinion', 'area', 'grid', 'delay_count',
                'uploader'
            ]
            df = df[[c for c in db_columns if c in df.columns]]

            # 先删除同批次旧数据，再插入
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM case_data WHERE upload_batch = :batch"), {'batch': batch})
                conn.commit()

            df.to_sql('case_data', engine, if_exists='append', index=False, method='multi', chunksize=500)

            return jsonify({
                'success': True,
                'batch': batch,
                'count': len(df),
                'message': f'成功入库 {len(df)} 条记录（批次: {batch}）'
            })
        except Exception as e:
            logger.error(f'入库失败: {e}')
            return jsonify({'error': f'入库失败: {str(e)}'}), 500

    @app.route('/api/cleaning/upload-delay-rework', methods=['POST'])
    @protected
    def upload_delay_rework():
        """上传延期/返工案件列表（txt或xlsx）"""
        if 'file' not in request.files:
            return jsonify({'error': '请选择文件'}), 400

        file = request.files['file']
        ext = os.path.splitext(file.filename or '')[1].lower()

        try:
            if ext == '.txt':
                content = file.read().decode('utf-8')
                result = parse_delay_rework_txt(content)
            elif ext in ('.xlsx', '.xls'):
                df = pd.read_excel(io.BytesIO(file.read()))
                result = parse_delay_rework_excel(df)
            else:
                return jsonify({'error': '仅支持 .txt / .xlsx 格式'}), 400

            return jsonify({
                'success': True,
                'delayed_count': len(result['delayed']),
                'rework_count': len(result['rework']),
                'delayed_task_nos': result['delayed'],
                'rework_task_nos': result['rework']
            })
        except Exception as e:
            return jsonify({'error': f'解析失败: {str(e)}'}), 400

    @app.route('/api/cleaning/communities', methods=['GET'])
    @protected
    def get_community_centers():
        """获取社区中心点数据（从现有case_data反推）"""
        if not engine:
            return jsonify({'error': '数据库未连接'}), 500

        try:
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT community,
                           ROUND(AVG(longitude), 6) as center_lng,
                           ROUND(AVG(latitude), 6) as center_lat,
                           COUNT(*) as cnt
                    FROM case_data
                    WHERE community IS NOT NULL AND community != ''
                      AND longitude IS NOT NULL AND latitude IS NOT NULL
                    GROUP BY community
                    HAVING cnt >= 3
                    ORDER BY cnt DESC
                """))
                rows = result.fetchall()

            communities = [
                {'name': row[0], 'lng': row[1], 'lat': row[2], 'count': row[3]}
                for row in rows
            ]
            return jsonify({'success': True, 'communities': communities})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cleaning/rules', methods=['GET'])
    @protected
    def get_cleaning_rules():
        """获取可用清洗规则列表"""
        rules = [
            {'id': 'rule1', 'name': '问题来源替换', 'description': '其他问题上报→采集员上报', 'enabled': True},
            {'id': 'rule2', 'name': '问题描述清洗', 'description': '清除开头无关数字、序号、标点', 'enabled': True},
            {'id': 'rule3', 'name': '所属片区判定', 'description': '根据坐标判定五大片区（需GeoJSON）', 'enabled': True},
            {'id': 'rule4', 'name': '所属社区补全', 'description': '根据坐标就近匹配社区', 'enabled': True},
            {'id': 'rule5', 'name': '坐标转换', 'description': '百度墨卡托→高德坐标系', 'enabled': True},
            {'id': 'rule6', 'name': '监督员规范化', 'description': '去除姓名周围多余修饰字符', 'enabled': True},
            {'id': 'rule7', 'name': '问题描述脱敏', 'description': '手机号、座机号、地址脱敏', 'enabled': False},
        ]
        return jsonify({'success': True, 'rules': rules})


# 导入 RAW_COLUMN_MAP
from cleaning_rules import RAW_COLUMN_MAP
