# -*- coding: utf-8 -*-
"""月度分析报告流水线 runner

把 case_data 数据库批次导出为 xlsx，再以子进程方式原样执行 skill 固化脚本
（std_parse → analyze → build_html → make_word → polish_charts → polish_docx），
产物（HTML / docx / analysis.json）落盘到 backend/reports/ 与 work/<batch>/。

设计原则：不改动已验证口径的分析脚本本身（仅 template.html 的 echarts 改为本地引用），
通过子进程保证口径与原 skill 输出逐位一致。
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pandas as pd
from sqlalchemy import text

MR_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(MR_DIR)
REPORTS_DIR = os.path.join(BACKEND_DIR, 'reports')
STD_XLSX = os.path.join(MR_DIR, 'std', '立案、处置和结案标准.xlsx')
CONFIG_DIR = os.path.join(MR_DIR, 'config')

BATCH_RE = re.compile(r'^\d{6}$')

# 与 analysis_routes.COLUMN_MAP 保持一致的英文->中文反向映射
# （is_overtime 在原始平台导出 xlsx 中即为英文名，不参与反向映射）
DB_TO_CN = {
    'report_time': '上报时间',
    'task_no': '任务号',
    'big_category': '大类名称',
    'small_category': '小类名称',
    'source': '问题来源',
    'description': '问题描述',
    'stage': '当前阶段名称',
    'department': '处置部门',
    'deadline_bundled': '捆绑处置截止时间',
    'close_time': '结案时间',
    'district': '所属片区',
    'issue_type': '问题类型',
    'address': '地址描述',
    'street': '所属街道',
    'community': '所属社区',
    'supervisor': '监督员',
    'deadline': '处置截止时间',
    'is_delayed': '延期案件',
    'is_rework': '返工案件',
    'longitude': 'X坐标',
    'latitude': 'Y坐标',
    'is_overtime': 'is_overtime',
}

DEFAULT_ORG = '运城市城市管理局智慧城市管理平台服务中心'
DEFAULT_ORG_DOT = '运城市城市管理局 · 智慧城市管理平台服务中心'

# 口径参数（与 skill config.example.json 一致）
DEFAULT_CFG = {
    'lat': 35.03,
    'recur_radius_m': 50,
    'min_cases_supervisor': 100,
    'unit_addr_keywords': ['金城大厦', '铺安街989'],
    'work_windows': [[8, 11.5], [14, 20]],
    'brief': True,
    'anomaly_reason_tpl': {
        '降雨': '{days}为降雨天气，采集作业受限',
        '系统故障': '{days}因平台系统故障影响',
    },
    'img_width_cm': 13.6,
    'img_narrow_cm': 12.2,
    'table_head_fill': '17365D',
    'table_head_font': 'FFFFFF',
    'table_zebra': 'F3F7FC',
}

PIPELINE_STEPS = ['std_parse.py', 'analyze.py', 'build_html.py', 'make_word.py',
                  'polish_charts.py', 'polish_docx.py']


def export_batch_to_xlsx(engine, batch, dst_path):
    """从 case_data 导出指定批次并还原为平台中文列名，供 analyze.py 使用"""
    cols = ', '.join(DB_TO_CN.keys())
    sql = text(f"SELECT {cols} FROM case_data WHERE upload_batch = :b")
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={'b': batch})
    if df.empty:
        raise ValueError(f'批次 {batch} 无数据')
    # DECIMAL 列回读为 decimal.Decimal，转 float 避免后续数值运算报错
    for col in ('longitude', 'latitude'):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
    df = df.rename(columns=DB_TO_CN)
    df.to_excel(dst_path, index=False)
    return len(df)


def build_config(batch, workdir, src_path, anomalies, overrides):
    y, m = int(batch[:4]), int(batch[4:6])
    month = f'{y:04d}-{m:02d}'
    month_cn = f'{y}年{m}月'
    cfg = {
        'workdir': workdir,
        'src': src_path,
        'std_src': STD_XLSX if os.path.exists(STD_XLSX) else '',
        'month': month,
        'month_cn': month_cn,
        'month_cn_text': f'{y} 年 {m} 月',
        'month_label': f'{m}月份',
        'month_short': f'{m}月',
        'org': overrides.get('org') or DEFAULT_ORG,
        'org_dot': overrides.get('org_dot') or DEFAULT_ORG_DOT,
        'anomalies': anomalies or [],
        'out_json': 'analysis.json',
        'out_html': f'{m}月份案件数据分析报告.html',
        'out_docx': f'{month_cn}份城市管理案件数据分析报告.docx',
        'out_docx_final': f'{month_cn}份城市管理案件数据分析报告_优化版.docx',
    }
    cfg.update({k: v for k, v in DEFAULT_CFG.items()})
    for k in ('lat', 'recur_radius_m', 'min_cases_supervisor', 'unit_addr_keywords',
              'work_windows', 'brief', 'anomalies', 'anomaly_reason_tpl'):
        if k in overrides and overrides[k] is not None:
            cfg[k] = overrides[k]
    return cfg


def _run_step(script, config_path, workdir, optional=False):
    env = dict(os.environ)
    env['MPLBACKEND'] = 'Agg'  # 容器/服务无显示器环境下 matplotlib 必须用 Agg
    proc = subprocess.run(
        [sys.executable, os.path.join(MR_DIR, script), config_path],
        cwd=workdir, env=env, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=600,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or '')[-1500:]
        if optional:
            print(f'[monthly_report] {script} 失败（可选步骤，跳过）: {tail}')
            return False
        raise RuntimeError(f'{script} 执行失败: {tail}')
    return True


def _prepare_mpl_env(workdir):
    """在 workdir 写入 matplotlibrc（matplotlib 优先读 cwd 下的配置），
    同时删除 matplotlib 字体缓存，强制每次重建。"""
    rc_path = os.path.join(workdir, 'matplotlibrc')
    with open(rc_path, 'w') as f:
        f.write("font.sans-serif: WenQuanYi Micro Hei, Microsoft YaHei, SimHei, DejaVu Sans\n"
                "axes.unicode_minus: False\n")
    # 删除 matplotlib 字体缓存（~/.cache/matplotlib/）
    import glob
    mpl_cache = os.path.expanduser('~/.cache/matplotlib')
    if os.path.isdir(mpl_cache):
        shutil.rmtree(mpl_cache, ignore_errors=True)


def load_batch_config(batch):
    """读取按 batch 存储的配置（anomalies 等），不存在则返回空 dict"""
    path = os.path.join(CONFIG_DIR, f'{batch}.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_batch_config(batch, data):
    """持久化按 batch 的配置字段（合并写入，不覆盖其他字段）"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    path = os.path.join(CONFIG_DIR, f'{batch}.json')
    existing = load_batch_config(batch)
    existing.update(data)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def resolve_anomalies(batch, anomalies):
    """三级优先：前端传入 > 配置文件 > 空列表"""
    if anomalies:
        return anomalies
    stored = load_batch_config(batch)
    return stored.get('anomalies', [])


def run_pipeline(batch, engine, anomalies=None, overrides=None):
    """执行完整流水线，返回产物路径信息。失败抛异常。"""
    if not BATCH_RE.match(batch or ''):
        raise ValueError('batch 格式须为 YYYYMM，如 202608')
    if engine is None:
        raise ValueError('数据库未连接')
    overrides = overrides or {}
    workdir = os.path.join(MR_DIR, 'work', batch)
    os.makedirs(workdir, exist_ok=True)

    src_path = os.path.join(workdir, 'src.xlsx')
    n_rows = export_batch_to_xlsx(engine, batch, src_path)

    # anomalies 三级优先：前端传入 > 配置文件 > 空
    anomalies = resolve_anomalies(batch, anomalies)
    # 如果前端传了 anomalies，持久化到配置文件（下次自动读取）
    if anomalies and load_batch_config(batch).get('anomalies') != anomalies:
        save_batch_config(batch, {'anomalies': anomalies})

    cfg = build_config(batch, workdir, src_path, anomalies, overrides)
    config_path = os.path.join(workdir, 'config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    _prepare_mpl_env(workdir)

    # 步骤1: std_parse（可选）
    _run_step('std_parse.py', config_path, workdir, optional=True)
    # 步骤2: analyze
    _run_step('analyze.py', config_path, workdir)
    # 步骤3: AI 章节生成（可选，LLM 不可用时 fallback 到规则引擎 bullets）
    try:
        from backend.monthly_report.llm_writer import generate_ai_chapters
    except ImportError:
        from monthly_report.llm_writer import generate_ai_chapters
    month_cn = cfg.get('month_cn', batch)
    analysis_json = os.path.join(workdir, cfg.get('out_json', 'analysis.json'))
    ai_result = generate_ai_chapters(analysis_json, month=month_cn)
    ai_path = os.path.join(workdir, 'ai_chapters.json')
    with open(ai_path, 'w', encoding='utf-8') as f:
        json.dump(ai_result, f, ensure_ascii=False)
    # 注入 analysis.json 供 template.html 使用
    if os.path.exists(analysis_json):
        with open(analysis_json, encoding='utf-8') as f:
            d = json.load(f)
        d['ai_chapters'] = ai_result
        with open(analysis_json, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, default=str)
    # 步骤4-6: build_html / make_word / polish
    for script in ['build_html.py', 'make_word.py', 'polish_charts.py', 'polish_docx.py']:
        optional = script in ('polish_charts.py', 'polish_docx.py')
        _run_step(script, config_path, workdir, optional=optional)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    html_src = os.path.join(workdir, cfg['out_html'])
    html_dst = os.path.join(REPORTS_DIR, f'{batch}.html')
    if not os.path.exists(html_src):
        raise RuntimeError('build_html 未产出 HTML 文件')
    shutil.copyfile(html_src, html_dst)

    docx_name = cfg['out_docx_final'] if os.path.exists(os.path.join(workdir, cfg['out_docx_final'])) \
        else cfg['out_docx']
    docx_src = os.path.join(workdir, docx_name)
    docx_dst = os.path.join(REPORTS_DIR, f'{batch}.docx')
    if not os.path.exists(docx_src):
        raise RuntimeError('make_word 未产出 docx 文件')
    shutil.copyfile(docx_src, docx_dst)

    metrics = {}
    json_path = os.path.join(workdir, cfg['out_json'])
    if os.path.exists(json_path):
        with open(json_path, encoding='utf-8') as f:
            d = json.load(f)
        basis, eff, recur, insight = d.get('basis', {}), d.get('eff', {}), d.get('recur', {}), d.get('insight', {})
        metrics = {
            'total': basis.get('total'),
            'closed': basis.get('closed'),
            'overtime_n': (eff.get('overtime') or {}).get('n'),
            'overtime_rate': (eff.get('overtime') or {}).get('rate'),
            'delay_n': (eff.get('delay') or {}).get('n'),
            'rework_n': (eff.get('rework') or {}).get('n'),
            'recur_ge3_n': recur.get('ge3_n'),
            'recur_ge3_cases': recur.get('ge3_cases'),
            'std_n_xl': (d.get('std') or {}).get('n_xl'),
            'no_addr': insight.get('no_addr'),
        }

    return {
        'batch': batch,
        'rows': n_rows,
        'html_url': f'/reports/{batch}.html',
        'docx_url': f'/api/monthly-report/{batch}/export',
        'metrics': metrics,
    }


def ensure_report(batch, engine, anomalies=None, overrides=None):
    """报告文件已存在则跳过生成，否则执行流水线（供 export 自动触发）"""
    if os.path.exists(os.path.join(REPORTS_DIR, f'{batch}.docx')):
        return {'batch': batch, 'html_url': f'/reports/{batch}.html',
                'docx_url': f'/api/monthly-report/{batch}/export', 'cached': True}
    return run_pipeline(batch, engine, anomalies, overrides)
