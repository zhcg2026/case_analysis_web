# -*- coding: utf-8 -*-
"""月度分析报告路由：生成（HTML+docx）与导出"""
import logging
import os
import re

from flask import request, jsonify, send_from_directory

logger = logging.getLogger(__name__)

try:
    from backend.monthly_report.pipeline import run_pipeline, ensure_report, REPORTS_DIR, load_batch_config, save_batch_config
except ImportError:
    from monthly_report.pipeline import run_pipeline, ensure_report, REPORTS_DIR, load_batch_config, save_batch_config

try:
    from common import protected as _protected
except ImportError:
    from helpers import protected as _protected

BATCH_RE = re.compile(r'^\d{6}$')


def register_monthly_report_routes(app, engine=None, protected=None):
    protected = protected or _protected

    @app.route('/api/monthly-report/generate', methods=['POST'])
    @protected
    def monthly_report_generate():
        try:
            data = request.get_json(silent=True) or {}
            batch = str(data.get('batch') or '').strip()
            if not BATCH_RE.match(batch):
                return jsonify({'error': 'batch 格式须为 YYYYMM，如 202608'}), 400
            anomalies = data.get('anomalies') or []
            if not isinstance(anomalies, list):
                return jsonify({'error': 'anomalies 须为数组'}), 400
            overrides = {k: data.get(k) for k in ('org', 'org_dot', 'lat', 'recur_radius_m',
                                                  'min_cases_supervisor', 'unit_addr_keywords',
                                                  'work_windows', 'brief') if k in data}
            result = run_pipeline(batch, engine, anomalies=anomalies, overrides=overrides)
            return jsonify(result)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.exception('月度报告生成失败 batch=%s', data.get('batch'))
            return jsonify({'error': f'生成失败: {e}'}), 500

    @app.route('/api/monthly-report/<batch>/export', methods=['GET'])
    @protected
    def monthly_report_export(batch):
        try:
            if not BATCH_RE.match(batch):
                return jsonify({'error': 'batch 格式须为 YYYYMM'}), 400
            docx_path = os.path.join(REPORTS_DIR, f'{batch}.docx')
            if not os.path.exists(docx_path):
                # 未生成过则自动先跑流水线（导出无感）
                data = request.get_json(silent=True) or {}
                ensure_report(batch, engine, anomalies=data.get('anomalies'))
            if not os.path.exists(docx_path):
                return jsonify({'error': '报告尚未生成'}), 404
            m = re.match(r'^(\d{4})(\d{2})$', batch)
            download_name = f'{m.group(1)}年{m.group(2)}月份城市管理案件数据分析报告_优化版.docx'
            resp = send_from_directory(REPORTS_DIR, f'{batch}.docx', as_attachment=True)
            from urllib.parse import quote
            resp.headers['Content-Disposition'] = (
                f"attachment; filename*=UTF-8''{quote(download_name)}")
            return resp
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.exception('月度报告导出失败 batch=%s', batch)
            return jsonify({'error': f'导出失败: {e}'}), 500

    @app.route('/api/monthly-report/<batch>/status', methods=['GET'])
    @protected
    def monthly_report_status(batch):
        html_ok = os.path.exists(os.path.join(REPORTS_DIR, f'{batch}.html'))
        docx_ok = os.path.exists(os.path.join(REPORTS_DIR, f'{batch}.docx'))
        return jsonify({'batch': batch, 'html_ready': html_ok, 'docx_ready': docx_ok})

    @app.route('/api/monthly-report/<batch>/config', methods=['GET'])
    @protected
    def monthly_report_config_get(batch):
        if not BATCH_RE.match(batch):
            return jsonify({'error': 'batch 格式须为 YYYYMM'}), 400
        cfg = load_batch_config(batch)
        return jsonify({'batch': batch, 'anomalies': cfg.get('anomalies', [])})

    @app.route('/api/monthly-report/<batch>/config', methods=['PUT'])
    @protected
    def monthly_report_config_put(batch):
        if not BATCH_RE.match(batch):
            return jsonify({'error': 'batch 格式须为 YYYYMM'}), 400
        data = request.get_json(silent=True) or {}
        anomalies = data.get('anomalies', [])
        if not isinstance(anomalies, list):
            return jsonify({'error': 'anomalies 须为数组'}), 400
        # 校验每条记录格式
        for a in anomalies:
            if not isinstance(a, dict) or 'date' not in a:
                return jsonify({'error': '每条异常记录须含 date 字段'}), 400
        save_batch_config(batch, {'anomalies': anomalies})
        return jsonify({'batch': batch, 'anomalies': anomalies, 'message': '保存成功'})
