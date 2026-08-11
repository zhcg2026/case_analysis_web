# -*- coding: utf-8 -*-
"""数据分析路由模块 - 案件数据上传、AI分析、报表生成"""
import os
import io
import json
import datetime
import re
import logging
import pandas as pd
import requests
from flask import request, jsonify
from sqlalchemy import text

logger = logging.getLogger(__name__)

try:
    from common import protected as _protected
except ImportError:
    from helpers import protected as _protected

# LLM配置（仅从环境变量读取，禁止在代码中硬编码密钥）
DOUBAO_API_KEY = os.getenv('DOUBAO_API_KEY', '')
DOUBAO_API_URL = os.getenv('DOUBAO_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
DOUBAO_MODEL = os.getenv('DOUBAO_MODEL', 'doubao-seed-1-8-251228')

# Excel列名到数据库字段的映射
COLUMN_MAP = {
    '上报时间': 'report_time',
    '任务号': 'task_no',
    '大类名称': 'big_category',
    '小类名称': 'small_category',
    '问题来源': 'source',
    '问题描述': 'description',
    '当前阶段名称': 'stage',
    '处置部门': 'department',
    '捆绑处置截止时间': 'deadline_bundled',
    '结案时间': 'close_time',
    '所属片区': 'district',
    '问题类型': 'issue_type',
    '地址描述': 'address',
    '所属街道': 'street',
    '所属社区': 'community',
    '监督员': 'supervisor',
    '处置截止时间': 'deadline',
    '延期案件': 'is_delayed',
    '返工案件': 'is_rework',
    'X坐标': 'longitude',
    'Y坐标': 'latitude',
}

# 数据库表创建SQL
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS case_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    upload_batch VARCHAR(10) NOT NULL COMMENT '上传批次(年月如202606)',
    report_time DATETIME COMMENT '上报时间',
    task_no BIGINT COMMENT '任务号',
    big_category VARCHAR(50) COMMENT '大类名称',
    small_category VARCHAR(50) COMMENT '小类名称',
    source VARCHAR(50) COMMENT '问题来源',
    description TEXT COMMENT '问题描述',
    stage VARCHAR(50) COMMENT '当前阶段名称',
    department VARCHAR(100) COMMENT '处置部门',
    deadline_bundled DATETIME COMMENT '捆绑处置截止时间',
    close_time DATETIME COMMENT '结案时间',
    district VARCHAR(50) COMMENT '所属片区',
    issue_type VARCHAR(50) COMMENT '问题类型',
    address VARCHAR(500) COMMENT '地址描述',
    street VARCHAR(100) COMMENT '所属街道',
    community VARCHAR(100) COMMENT '所属社区',
    supervisor VARCHAR(50) COMMENT '监督员',
    deadline DATETIME COMMENT '处置截止时间',
    is_delayed TINYINT DEFAULT 0 COMMENT '延期案件',
    is_rework TINYINT DEFAULT 0 COMMENT '返工案件',
    longitude DECIMAL(10,6) DEFAULT NULL COMMENT '经度(X坐标)',
    latitude DECIMAL(10,6) DEFAULT NULL COMMENT '纬度(Y坐标)',
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    uploader VARCHAR(50) COMMENT '上传人',
    INDEX idx_batch (upload_batch),
    INDEX idx_big_category (big_category),
    INDEX idx_district (district),
    INDEX idx_department (department),
    INDEX idx_street (street),
    INDEX idx_report_time (report_time),
    INDEX idx_coordinates (longitude, latitude)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='城市管理案件数据';
"""

# 需要获取样本值的字段
SAMPLE_COLUMNS = ['district', 'department', 'big_category', 'small_category',
                  'street', 'source', 'issue_type', 'stage']

# SQL安全检查白名单与危险关键字
ALLOWED_TABLES = {'case_data'}
_DANGEROUS_KEYWORDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC',
    'RENAME', 'GRANT', 'REVOKE', 'CALL', 'MERGE', 'SHUTDOWN', 'LOCK', 'INTO',
    'LOAD_FILE', 'SLEEP', 'BENCHMARK', 'UNION', 'INFORMATION_SCHEMA',
]


def _normalize_bool(x):
    """将单元格值统一规范化为 0/1 整数（兼容 是/否、true/false、1/0、Y/N 等）"""
    if pd.isna(x):
        return 0
    s = str(x).strip().lower()
    if s in ('是', 'true', '1', 'yes', 'y', 't', '有'):
        return 1
    return 0



def process_excel_upload(file_stream, batch_override, username, engine):
    df = pd.read_excel(io.BytesIO(file_stream))
    required_cols = {k: v for k, v in COLUMN_MAP.items() if k not in ('坐标', 'Y坐标')}
    missing_cols = [col for col in required_cols.keys() if col not in df.columns]
    if missing_cols:
        raise ValueError('缺少列: ' + ', '.join(missing_cols))
    batch = (batch_override or '').strip()
    if not batch:
        # 优先用"捆绑处置截止时间"众数推断月份（考核依据），回退到"上报时间"
        for col_cn in ['捆绑处置截止时间', '上报时间']:
            if col_cn in df.columns and len(df) > 0:
                parsed = pd.to_datetime(df[col_cn], errors='coerce').dropna()
                if not parsed.empty:
                    batch = parsed.dt.strftime('%Y%m').mode().iloc[0]
                    break
        if not batch:
            batch = datetime.datetime.now().strftime('%Y%m')
    df = df.rename(columns=COLUMN_MAP)
    df = df[[col for col in COLUMN_MAP.values() if col in df.columns]]
    df['upload_batch'] = batch
    df['uploader'] = username or 'system'
    for col in ['is_delayed', 'is_rework']:
        if col in df.columns:
            df[col] = df[col].apply(_normalize_bool).astype(int)
    for col in ['report_time', 'close_time', 'deadline', 'deadline_bundled']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    if not engine:
        raise ValueError('数据库未连接')
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM case_data WHERE upload_batch = :batch"), {'batch': batch})
        conn.commit()
    df.to_sql('case_data', engine, if_exists='append', index=False, method='multi', chunksize=500)
    return {'batch': batch, 'count': len(df)}

def register_analysis_routes(app, engine=None, protected=None):
    """注册数据分析相关路由"""
    protected = protected or _protected

    # 确保数据库表存在
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text(CREATE_TABLE_SQL))
                conn.commit()
            logger.info("case_data 表创建/检查成功")
        except Exception as e:
            logger.error(f"case_data 表创建失败: {e}")

        # 为已有表添加经纬度字段（如果不存在）
        try:
            with engine.connect() as conn:
                for col_name, col_def in [
                    ('longitude', "ADD COLUMN longitude DECIMAL(10,6) DEFAULT NULL COMMENT '经度(X坐标)'"),
                    ('latitude', "ADD COLUMN latitude DECIMAL(10,6) DEFAULT NULL COMMENT '纬度(Y坐标)'"),
                ]:
                    result = conn.execute(text(f"SHOW COLUMNS FROM case_data LIKE '{col_name}'"))
                    if not result.fetchone():
                        conn.execute(text(f"ALTER TABLE case_data {col_def}"))
                        conn.commit()
                        logger.info(f"case_data 表添加 {col_name} 字段成功")
                try:
                    conn.execute(text("ALTER TABLE case_data ADD INDEX idx_coordinates (longitude, latitude)"))
                    conn.commit()
                    logger.info("case_data 表添加坐标索引成功")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"case_data 表添加经纬度字段失败: {e}")

    @app.route('/api/analysis/upload', methods=['POST'])
    @protected
    def upload_case_data():
        """上传案件数据Excel文件"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': '请上传文件'}), 400

            file = request.files['file']
            if not file.filename.endswith(('.xlsx', '.xls')):
                return jsonify({'error': '仅支持Excel文件(.xlsx/.xls)'}), 400

            batch_override = (request.form.get('batch', '') or '').strip()
            username = getattr(request, 'username', 'system')
            result = process_excel_upload(file.read(), batch_override, username, engine)

            return jsonify({
                'success': True,
                'batch': result['batch'],
                'rows': result['count'],
                'message': f'成功导入 {result["count"]} 条数据（批次: {result["batch"]}）'
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.exception('上传案件数据失败')
            return jsonify({'error': f'上传失败: {str(e)}'}), 500

    @app.route('/api/analysis/months', methods=['GET'])
    @protected
    def get_months():
        """获取已上传的月份列表"""
        try:
            if not engine:
                return jsonify({'months': []})

            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT upload_batch, COUNT(*) as count, MIN(upload_time) as upload_time "
                    "FROM case_data GROUP BY upload_batch ORDER BY upload_batch DESC"
                ))
                months = [
                    {'batch': row[0], 'count': row[1], 'upload_time': str(row[2])}
                    for row in result
                ]
            return jsonify({'months': months})
        except Exception as e:
            logger.error(f"获取月份列表失败: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analysis/query', methods=['POST'])
    @protected
    def analysis_query():
        """AI分析查询 - 两步流水线：LLM生成SQL → 执行SQL → 返回结构化结果"""
        try:
            data = request.get_json(silent=True) or {}
            question = (data.get('question', '') or '').strip()
            months = data.get('months', []) or []

            if not question:
                return jsonify({'error': '请输入分析需求'}), 400

            if not engine:
                return jsonify({'error': '数据库未连接'}), 500

            # 获取上下文
            schema_info = _get_schema_info(engine)
            available_months = _get_available_months(engine)
            data_samples = _get_data_samples(engine)

            # 未选择月份时，回退为全部已上传月份，确保SQL始终带合法的月份过滤条件
            effective_months = months if months else available_months

            # 构建prompt并调用LLM
            prompt = _build_analysis_prompt(question, schema_info, available_months, data_samples, effective_months)
            llm_response = _call_llm(prompt)
            if not llm_response:
                return jsonify({'error': 'AI分析服务暂时不可用，请检查LLM配置'}), 500

            # 解析JSON响应
            spec = _parse_llm_json(llm_response)
            if not spec or 'sql' not in spec:
                return jsonify({'error': 'AI未能生成有效的分析方案，请换个问法试试'}), 500

            # 安全检查SQL
            sql = spec['sql'].strip()
            if not _validate_sql(sql):
                logger.warning(f"SQL安全检查未通过: {sql}")
                return jsonify({'error': 'SQL安全检查未通过'}), 400

            # 执行SQL获取真实数据
            try:
                with engine.connect() as conn:
                    df = pd.read_sql(text(sql), conn)
            except Exception as e:
                logger.error(f"分析SQL执行失败: {sql} -> {e}")
                return jsonify({'error': f'查询执行失败: {str(e)}'}), 500

            if df.empty:
                return jsonify({
                    'success': True,
                    'question': question,
                    'answer': '未查询到符合条件的数据。',
                    'chart': None,
                    'table_data': [],
                })

            # 构建返回结果
            chart_spec = {
                'chart_type': spec.get('chart_type', 'bar'),
                'title': spec.get('title', question),
                'x_field': spec.get('x_field', ''),
                'y_field': spec.get('y_field', ''),
                'data': json.loads(df.to_json(orient='records', force_ascii=False)),
            }

            table_data = json.loads(df.to_json(orient='records', force_ascii=False))
            answer = _generate_summary(df, spec)

            return jsonify({
                'success': True,
                'question': question,
                'answer': answer,
                'chart': chart_spec,
                'table_data': table_data,
            })

        except Exception as e:
            logger.exception("分析查询失败")
            return jsonify({'error': f'分析失败: {str(e)}'}), 500

    @app.route('/api/analysis/schema', methods=['GET'])
    @protected
    def get_schema():
        """获取数据表结构信息"""
        try:
            if not engine:
                return jsonify({'schema': {}})
            schema = _get_schema_info(engine)
            return jsonify({'schema': schema})
        except Exception as e:
            logger.error(f"获取表结构失败: {e}")
            return jsonify({'error': str(e)}), 500


def _get_schema_info(engine):
    """获取case_data表的schema信息"""
    schema = {}
    try:
        with engine.connect() as conn:
            result = conn.execute(text("DESCRIBE case_data"))
            for row in result:
                schema[row[0]] = row[1]
    except Exception as e:
        logger.warning(f"获取schema失败: {e}")
    return schema


def _get_available_months(engine):
    """获取已上传的月份列表"""
    months = []
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT DISTINCT upload_batch FROM case_data ORDER BY upload_batch"
            ))
            months = [row[0] for row in result]
    except Exception as e:
        logger.warning(f"获取可用月份失败: {e}")
    return months


def _get_data_samples(engine):
    """获取关键字段的真实数据样本，注入Prompt让LLM了解实际数据"""
    samples = {}
    try:
        with engine.connect() as conn:
            for col in SAMPLE_COLUMNS:
                try:
                    result = conn.execute(text(
                        f"SELECT DISTINCT {col} FROM case_data "
                        f"WHERE {col} IS NOT NULL AND {col} != '' "
                        f"ORDER BY {col} LIMIT 20"
                    ))
                    samples[col] = [row[0] for row in result]
                except Exception as e:
                    logger.warning(f"获取样本失败(col={col}): {e}")
    except Exception as e:
        logger.warning(f"获取样本失败: {e}")
    return samples


def _build_analysis_prompt(question, schema_info, available_months, data_samples, selected_months=None):
    """构造AI分析的prompt - 包含真实数据样本和few-shot示例"""
    schema_text = "\n".join([f"  - {col}: {dtype}" for col, dtype in schema_info.items()])
    months_text = ", ".join(available_months) if available_months else "无"

    samples_text = ""
    for col, values in data_samples.items():
        if values:
            samples_text += f"  - {col}: {', '.join(str(v) for v in values)}\n"

    month_filter = ""
    if selected_months:
        month_list = ", ".join([f"'{m}'" for m in selected_months])
        month_filter = f"upload_batch IN ({month_list})"

    month_filter_rule = ""
    if month_filter:
        month_filter_rule = f"""
【月份过滤 - 必须遵守】
当前分析的月份条件: WHERE {month_filter}
所有SQL的FROM case_data之后必须紧跟此WHERE条件，不可省略。"""

    system_prompt = """你是一个SQL查询专家。用户有一份城市管理案件数据，存储在MySQL的 case_data 表中。你的任务是根据用户的自然语言问题，生成正确的SQL查询，并指定合适的图表类型。

你必须严格输出JSON格式，不要输出任何其他内容。"""

    user_prompt = f"""表结构:
{schema_text}

各字段实际数据样本:
{samples_text}
可用月份: {months_text}
{month_filter_rule}

【重要区分 - 必须严格遵守】
- district（片区）是地理区域，值如: 东片区、西片区、南片区、北片区、中片区、高铁站片区、经济开发区片区
- department（部门/处置部门）是执法单位，值如: 执法东片区、执法西片区、城市综合行政执法队、园林西片区、环卫西片区、环卫北片区、环卫中片区、排水服务中心
- 用户说"执法西片区"→ 用department字段，不是district！
- 用户说"环卫案件"→ 需要 WHERE department LIKE '%环卫%' 过滤，不能查所有部门！
- 用户说"园林案件"→ 需要 WHERE department LIKE '%园林%' 过滤
- 用户说"执法案件"→ 需要 WHERE department LIKE '%执法%' 过滤

【强制规则 - 所有SQL必须包含月份过滤】
每条SQL必须在 FROM case_data 后包含 WHERE upload_batch IN (...) 条件。
如果有其他过滤条件（如 close_time IS NOT NULL），用 AND 连接。
无其他WHERE条件时: FROM case_data WHERE upload_batch IN (...) GROUP BY ...
有其他WHERE条件时: FROM case_data WHERE upload_batch IN (...) AND close_time IS NOT NULL GROUP BY ...

常用SQL模板（优先使用，禁止修改计算逻辑，所有模板均已包含月份过滤）：

【计数类 - 统计所有案件，不过滤close_time】
1. 案件数量按片区:
   SELECT district AS 片区, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN (...) GROUP BY district ORDER BY 案件数量 DESC

2. 案件数量按部门:
   SELECT department AS 部门, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN (...) GROUP BY department ORDER BY 案件数量 DESC

3. 案件数量按大类:
   SELECT big_category AS 大类, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN (...) GROUP BY big_category ORDER BY 案件数量 DESC

4. 案件数量按街道（TOP20）:
   SELECT street AS 街道, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN (...) GROUP BY street ORDER BY 案件数量 DESC LIMIT 20

5. 案件数量按小类（TOP20）:
   SELECT small_category AS 小类, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN (...) GROUP BY small_category ORDER BY 案件数量 DESC LIMIT 20

【均值类 - 只统计已结案，WHERE close_time IS NOT NULL，使用ABS避免负时长】
6. 平均处置时长（小时）按片区:
   SELECT district AS 片区, ROUND(AVG(ABS(TIMESTAMPDIFF(MINUTE, report_time, close_time)))/60.0, 2) AS 平均处置时长 FROM case_data WHERE upload_batch IN (...) AND close_time IS NOT NULL GROUP BY district ORDER BY 平均处置时长 DESC

7. 平均处置时长（小时）按部门:
   SELECT department AS 部门, ROUND(AVG(ABS(TIMESTAMPDIFF(MINUTE, report_time, close_time)))/60.0, 2) AS 平均处置时长 FROM case_data WHERE upload_batch IN (...) AND close_time IS NOT NULL GROUP BY department ORDER BY 平均处置时长 DESC

【比率类】
8. 逾期率按片区:
   SELECT district AS 片区, ROUND(SUM(is_delayed)*100.0/COUNT(*), 2) AS 逾期率 FROM case_data WHERE upload_batch IN (...) GROUP BY district ORDER BY 逾期率 DESC

9. 逾期率按部门:
   SELECT department AS 部门, ROUND(SUM(is_delayed)*100.0/COUNT(*), 2) AS 逾期率 FROM case_data WHERE upload_batch IN (...) GROUP BY department ORDER BY 逾期率 DESC

10. 返工率按片区:
    SELECT district AS 片区, ROUND(SUM(is_rework)*100.0/COUNT(*), 2) AS 返工率 FROM case_data WHERE upload_batch IN (...) GROUP BY district ORDER BY 返工率 DESC

11. 延期和返工案件统计（使用 CASE WHEN 合并统计，禁止使用 UNION）:
    SELECT district AS 片区, SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) AS 延期数量, SUM(CASE WHEN is_rework = 1 THEN 1 ELSE 0 END) AS 返工数量 FROM case_data WHERE upload_batch IN (...) GROUP BY district ORDER BY 延期数量 DESC

12. 延期和返工案件按部门统计:
    SELECT department AS 部门, SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) AS 延期数量, SUM(CASE WHEN is_rework = 1 THEN 1 ELSE 0 END) AS 返工数量 FROM case_data WHERE upload_batch IN (...) GROUP BY department ORDER BY 延期数量 DESC

【关键规则 - y_field 必须与 SQL 中的列别名完全一致】
- 计数类SQL → y_field = "案件数量"
- 均值类SQL → y_field = "平均处置时长"（注意：均值类SQL不要包含COUNT列，只返回平均值）
- 比率类SQL → y_field = "逾期率" 或 "返工率"
- 如果用户问的是某类部门的效率，SQL必须加 WHERE department LIKE '%关键词%' 过滤

图表类型选择规则:
- bar: 分组对比（片区/部门/大类等，项<=10个）
- horizontal_bar: 排名类（TOP N、最多/最少，项>5个时优先）
- pie: 占比分布（大类分布、来源分布等）
- line: 时间趋势（按月/日变化）

示例（假设月份条件为 upload_batch IN ('202606')）：

问题: "各片区案件数量统计"
输出:
{{"sql": "SELECT district AS 片区, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN ('202606') GROUP BY district ORDER BY 案件数量 DESC", "chart_type": "bar", "title": "各片区案件数量统计", "x_field": "片区", "y_field": "案件数量"}}

问题: "大类案件分布"
输出:
{{"sql": "SELECT big_category AS 大类, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN ('202606') GROUP BY big_category ORDER BY 案件数量 DESC", "chart_type": "pie", "title": "案件大类分布", "x_field": "大类", "y_field": "案件数量"}}

问题: "各处置部门案件数量排名"
输出:
{{"sql": "SELECT department AS 部门, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN ('202606') GROUP BY department ORDER BY 案件数量 DESC", "chart_type": "horizontal_bar", "title": "各部门案件数量排名", "x_field": "部门", "y_field": "案件数量"}}

问题: "各片区平均处置时长"
输出:
{{"sql": "SELECT district AS 片区, ROUND(AVG(ABS(TIMESTAMPDIFF(MINUTE, report_time, close_time)))/60.0, 2) AS 平均处置时长 FROM case_data WHERE upload_batch IN ('202606') AND close_time IS NOT NULL GROUP BY district ORDER BY 平均处置时长 DESC", "chart_type": "bar", "title": "各片区平均处置时长（小时）", "x_field": "片区", "y_field": "平均处置时长"}}

问题: "分析一下环卫案件处置效率"
输出:
{{"sql": "SELECT department AS 部门, ROUND(AVG(ABS(TIMESTAMPDIFF(MINUTE, report_time, close_time)))/60.0, 2) AS 平均处置时长 FROM case_data WHERE upload_batch IN ('202606') AND close_time IS NOT NULL AND department LIKE '%环卫%' GROUP BY department ORDER BY 平均处置时长 DESC", "chart_type": "horizontal_bar", "title": "环卫部门案件处置效率（平均处置时长）", "x_field": "部门", "y_field": "平均处置时长"}}

问题: "执法西片区有多少案件"
输出:
{{"sql": "SELECT department AS 部门, COUNT(*) AS 案件数量 FROM case_data WHERE upload_batch IN ('202606') AND department LIKE '%执法西片区%' GROUP BY department", "chart_type": "bar", "title": "执法西片区案件数量", "x_field": "部门", "y_field": "案件数量"}}

问题: "延期和返工案件统计"
输出:
{{"sql": "SELECT district AS 片区, SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) AS 延期数量, SUM(CASE WHEN is_rework = 1 THEN 1 ELSE 0 END) AS 返工数量 FROM case_data WHERE upload_batch IN ('202606') GROUP BY district ORDER BY 延期数量 DESC", "chart_type": "bar", "title": "各片区延期和返工案件统计", "x_field": "片区", "y_field": ["延期数量", "返工数量"]}}

现在请分析用户的问题，只输出JSON（注意：SQL中必须使用实际的月份条件，不可用省略号）:

问题: {question}
输出:"""

    return [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
    ]


def _parse_llm_json(llm_response):
    """从LLM响应中提取JSON"""
    content = llm_response.strip()

    # 尝试直接解析
    try:
        result = json.loads(content)
        return _extract_single_spec(result)
    except json.JSONDecodeError:
        pass

    # 从markdown代码块提取
    if '```json' in content:
        content = content.split('```json')[1].split('```')[0].strip()
    elif '```' in content:
        content = content.split('```')[1].split('```')[0].strip()

    try:
        result = json.loads(content)
        return _extract_single_spec(result)
    except json.JSONDecodeError:
        pass

    # 尝试提取第一个 { 到最后一个 } 之间的内容
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            return _extract_single_spec(result)
        except json.JSONDecodeError:
            pass

    # 尝试提取数组中的第一个对象
    match = re.search(r'\[\s*\{.*?\}\s*\]', content, re.DOTALL)
    if match:
        try:
            arr = json.loads(match.group())
            if isinstance(arr, list) and len(arr) > 0:
                return _extract_single_spec(arr[0])
        except json.JSONDecodeError:
            pass

    logger.warning(f"无法解析LLM响应为JSON: {llm_response[:300]}")
    return None


def _extract_single_spec(result):
    """从LLM返回的结果中提取单个分析规格"""
    # 如果是数组，取第一个元素
    if isinstance(result, list) and len(result) > 0:
        result = result[0]

    # 如果有 queries 字段，取第一个
    if isinstance(result, dict) and 'queries' in result:
        queries = result['queries']
        if isinstance(queries, list) and len(queries) > 0:
            return queries[0]

    return result


def _validate_sql(sql):
    """SQL安全检查：仅允许查询白名单表，禁止写操作/危险关键字/多语句"""
    if not sql or not sql.strip():
        return False
    s = sql.strip()
    su = s.upper()

    if not su.startswith('SELECT'):
        return False

    # 禁止多语句
    if ';' in s:
        return False

    # 禁止危险关键字（\b 边界匹配，避免误伤普通列名）
    for kw in _DANGEROUS_KEYWORDS:
        # 允许 UNION ALL（合法的合并查询），但禁止单独的 UNION（注入风险）
        if kw == 'UNION':
            # 检查是否存在 UNION 但不是 UNION ALL
            # 先移除所有 UNION ALL，再检查是否还有 UNION
            su_no_union_all = re.sub(r'\bUNION\s+ALL\b', '', su)
            if re.search(r'\bUNION\b', su_no_union_all):
                logger.warning(f"SQL安全检查: 检测到非 UNION ALL 的 UNION 语句")
                return False
            continue
        if re.search(rf'\b{kw}\b', su):
            logger.warning(f"SQL安全检查: 检测到危险关键字 '{kw}'")
            return False

    # 只允许查询白名单中的表（FROM/JOIN 后的表名）
    tables = re.findall(r'\b(?:FROM|JOIN)\s+([a-zA-Z0-9_`"]+)', su)
    for t in tables:
        if t.strip('`"').lower() not in ALLOWED_TABLES:
            logger.warning(f"SQL安全检查: 非白名单表 '{t}'")
            return False

    return True


def _generate_summary(df, spec):
    """基于真实查询结果生成文字摘要"""
    if df.empty:
        return '未查询到相关数据。'

    title = spec.get('title', '')
    y_field = spec.get('y_field', '')

    # 确保 y_field 是字符串
    if isinstance(y_field, list):
        y_field = y_field[0] if y_field else ''
    y_field = str(y_field) if y_field else ''

    total_rows = len(df)

    # 找数值列
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    if not numeric_cols:
        cols = list(df.columns)
        return f"共查询到 {total_rows} 条数据。"

    # 用 y_field 对应的列，或第一个数值列
    value_col = y_field if y_field and y_field in df.columns else numeric_cols[0]

    # 找最大/最小
    max_idx = df[value_col].idxmax()
    min_idx = df[value_col].idxmin()
    max_row = df.loc[max_idx]
    min_row = df.loc[min_idx]

    # 找第一个非数值列作为名称列
    name_col = None
    for col in df.columns:
        if col != value_col and col not in numeric_cols:
            name_col = col
            break

    parts = []
    parts.append(f"共{total_rows}条数据")

    if name_col:
        max_name = max_row[name_col]
        max_val = max_row[value_col]
        field_name = y_field if y_field else value_col
        parts.append(f"其中**{max_name}**的{field_name}最高，为**{max_val:,.2f}**" if isinstance(max_val, float) else f"其中**{max_name}**的{field_name}最高，为**{max_val:,}**")

        if total_rows > 1:
            min_name = min_row[name_col]
            min_val = min_row[value_col]
            parts.append(f"**{min_name}**最低，为**{min_val:,.2f}**" if isinstance(min_val, float) else f"**{min_name}**最低，为**{min_val:,}**")

    return '，'.join(parts) + '。'


def _call_llm(messages, timeout=120, max_retries=3):
    """调用豆包API，带重试机制"""
    import time

    if not DOUBAO_API_KEY:
        logger.error("DOUBAO_API_KEY 未配置，无法调用LLM")
        return None

    formatted_messages = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            formatted_messages.append({
                "role": msg["role"],
                "content": [{"type": "text", "text": content}]
            })
        else:
            formatted_messages.append(msg)

    logger.info(f"[Analysis] _call_llm: {len(formatted_messages)} messages")

    for attempt in range(max_retries):
        try:
            response = requests.post(
                DOUBAO_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DOUBAO_API_KEY}"
                },
                json={
                    "model": DOUBAO_MODEL,
                    "messages": formatted_messages,
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
                timeout=timeout
            )
            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices and choices[0].get("message", {}).get("content"):
                    return choices[0]["message"]["content"]
                else:
                    logger.warning(f"[Analysis] API 返回内容为空: {data}")
                    return None
            else:
                logger.warning(f"[Analysis] 豆包 API 调用失败 (尝试 {attempt+1}/{max_retries}): HTTP {response.status_code}, 响应: {response.text[:300]}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"[Analysis] API 请求超时 (尝试 {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"[Analysis] API 连接失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception as e:
            logger.error(f"[Analysis] LLM 调用异常: {e}")
            return None
    return None
