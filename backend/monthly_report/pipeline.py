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
import tempfile

import pandas as pd
from sqlalchemy import text

MR_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(MR_DIR)
REPORTS_DIR = os.path.join(BACKEND_DIR, 'reports')
STD_XLSX = os.path.join(MR_DIR, 'std', '立案、处置和结案标准.xlsx')

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
    # 为每个子进程创建独立的 matplotlib 配置目录，内含 matplotlibrc 指定中文字体，
    # 强制 matplotlib 从零扫描字体、不依赖可能过期的缓存
    mpl_dir = tempfile.mkdtemp(prefix='mpl_')
    with open(os.path.join(mpl_dir, 'matplotlibrc'), 'w') as f:
        f.write("font.sans-serif: WenQuanYi Micro Hei, Microsoft YaHei, SimHei, DejaVu Sans\n"
                "axes.unicode_minus: False\n")
    env['MPLCONFIGDIR'] = mpl_dir
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(MR_DIR, script), config_path],
            cwd=workdir, env=env, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=600,
        )
    finally:
        shutil.rmtree(mpl_dir, ignore_errors=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or '')[-1500:]
        if optional:
            print(f'[monthly_report] {script} 失败（可选步骤，跳过）: {tail}')
            return False
        raise RuntimeError(f'{script} 执行失败: {tail}')
    return True


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

    cfg = build_config(batch, workdir, src_path, anomalies, overrides)
    config_path = os.path.join(workdir, 'config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    for script in PIPELINE_STEPS:
        # std_parse / polish_* 为可选步骤（std 缺失或图表精修失败不阻断主流程）
        optional = script in ('std_parse.py', 'polish_charts.py', 'polish_docx.py')
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
