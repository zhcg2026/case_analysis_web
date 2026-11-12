# -*- coding: utf-8 -*-
"""考核月报（运行月报）路由：一键生成 / 状态 / 下载"""
import logging
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime

from flask import request, jsonify, send_from_directory
from urllib.parse import quote

logger = logging.getLogger(__name__)

try:
    from backend.assessment_report.report_data import collect_report_data
    from backend.assessment_report.make_charts import make_charts
    from backend.assessment_report.make_docx import generate_word
except ImportError:
    from assessment_report.report_data import collect_report_data
    from assessment_report.make_charts import make_charts
    from assessment_report.make_docx import generate_word

try:
    from common import protected as _protected
except ImportError:
    from helpers import protected as _protected

BATCH_RE = re.compile(r'^\d{6}$')
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports')
CHARTS_DIR = os.path.join(REPORTS_DIR, 'assess_charts')


def _docx_path(batch: str) -> str:
    return os.path.join(REPORTS_DIR, f'assessment_{batch}.docx')


def generate_assessment_report(engine, batch: str) -> dict:
    """收集数据 → 出图 → 生成Word。返回文件信息。"""
    # 文件锁跨Gunicorn worker生效；临时产物验证成功后才原子替换正式Word。
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with _report_lock(batch):
        data = collect_report_data(engine, batch)
        with tempfile.TemporaryDirectory(prefix=f'.assessment_{batch}_', dir=REPORTS_DIR) as stage:
            img1, img2 = make_charts(data, stage)
            draft = os.path.join(stage, 'report.docx')
            generate_word(data, img1, img2, draft)
            from zipfile import ZipFile
            with ZipFile(draft) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError('月报文件校验失败，原报告已保留')
            out = _docx_path(batch)
            os.replace(draft, out)
    return {
        'batch': batch,
        'file_url': f'/reports/assessment_{batch}.docx',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'path': out,
    }


_local_locks = {}
_locks_guard = threading.Lock()


@contextmanager
def _report_lock(batch):
    with _locks_guard:
        lock = _local_locks.setdefault(batch, threading.Lock())
    if not lock.acquire(blocking=False):
        raise ValueError('该月月报正在生成，请稍后重试')
    try:
        with open(os.path.join(REPORTS_DIR, f'.assessment_{batch}.lock'), 'a') as handle:
            if os.name != 'nt':
                import fcntl
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError('该月月报正在生成，请稍后重试')
            yield
    finally:
        lock.release()


def register_assessment_report_routes(app, engine=None, protected=None):
    protected = protected or _protected

    @app.route('/api/assessment/report/generate', methods=['POST'])
    @protected
    def assessment_report_generate():
        try:
            data = request.get_json(silent=True) or {}
            batch = str(data.get('batch') or '').strip()
            if not BATCH_RE.match(batch):
                return jsonify({'success': False, 'error': 'batch 格式须为 YYYYMM，如 202607'}), 400
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500
            info = generate_assessment_report(engine, batch)
            return jsonify({'success': True, **info})
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.exception('考核月报生成失败 batch=%s', batch)
            return jsonify({'success': False, 'error': f'生成失败: {e}'}), 500

    @app.route('/api/assessment/report/status', methods=['GET'])
    @protected
    def assessment_report_status():
        batch = request.args.get('batch', '').strip()
        if not BATCH_RE.match(batch):
            return jsonify({'success': False, 'error': 'batch 格式须为 YYYYMM'}), 400
        path = _docx_path(batch)
        exists = os.path.exists(path)
        return jsonify({
            'success': True,
            'batch': batch,
            'exists': exists,
            'file_url': f'/reports/assessment_{batch}.docx' if exists else None,
            'generated_at': datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S') if exists else None,
        })

    @app.route('/api/assessment/report/download', methods=['GET'])
    @protected
    def assessment_report_download():
        batch = request.args.get('batch', '').strip()
        if not BATCH_RE.match(batch):
            return jsonify({'success': False, 'error': 'batch 格式须为 YYYYMM'}), 400
        path = _docx_path(batch)
        if not os.path.exists(path):
            return jsonify({'success': False, 'error': '月报尚未生成'}), 404
        y, m = batch[:4], int(batch[4:6])
        download_name = f'{y}年{m}月运行月报.docx'
        resp = send_from_directory(REPORTS_DIR, f'assessment_{batch}.docx', as_attachment=True)
        resp.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(download_name)}"
        return resp
