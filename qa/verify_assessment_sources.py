"""Integration checks against a NEW local-only MySQL schema. Never imports app.py."""
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from flask import Flask

d = dotenv_values(ROOT / '.env.local')
assert d['DB_HOST'] in ('localhost', '127.0.0.1'), 'LOCAL DATABASE ONLY'
os.environ['JWT_SECRET_KEY'] = 'local-source-test-key-not-for-production-20261104'
from assessment_manual_routes import register_assessment_manual_routes, ensure_manual_tables
from assessment_report.sources import normalize_sources, read_sources, chart_sources
from assessment_report.report_data import collect_report_data
import assessment_report.assessment_report_routes as reports
from helpers import generate_token

schema = 'qa_sources_' + uuid.uuid4().hex[:12]
url = URL.create('mysql+pymysql', username=d['DB_USER'], password=d['DB_PASSWORD'],
                 host='127.0.0.1', port=int(d.get('DB_PORT', 3306)))
admin = create_engine(url)
with admin.begin() as c:
    c.execute(text(f'CREATE DATABASE `{schema}` CHARACTER SET utf8mb4'))
engine = create_engine(url.set(database=schema))
OUT = ROOT / 'qa' / 'source_validation'
OUT.mkdir(exist_ok=True)
try:
    ensure_manual_tables(engine)
    ensure_manual_tables(engine)
    with engine.begin() as c:
        c.execute(text('CREATE TABLE case_data (department VARCHAR(100),stage VARCHAR(20), '
                       'is_overtime INT,is_delayed INT,is_rework INT,upload_batch VARCHAR(10))'))
        c.execute(text("INSERT INTO case_data VALUES ('环卫东片区','[办结]',0,0,0,'202610')"))
        c.execute(text('CREATE TABLE permissions (user_id INT, assessment_input_platform INT, assessment_input_collector INT)'))
        c.execute(text('INSERT INTO permissions VALUES (2,1,0),(3,0,1)'))
    app = Flask(__name__)
    register_assessment_manual_routes(app, engine=engine)
    reports.register_assessment_report_routes(app, engine=engine)
    client = app.test_client()
    headers = {'Authorization': 'Bearer ' + generate_token(2, 'qa_platform', 'user')}
    collector = {'Authorization': 'Bearer ' + generate_token(3, 'qa_collector', 'user')}
    sources = normalize_sources([
        {'name': n, 'group': g, 'count': v}
        for n, g, v in [('采集上报', '采集上报', 14000), ('视频上报', '视频上报', 3000),
                        ('12345政务转办', '公众诉求', 1600), ('12345热线', '公众诉求', 700),
                        ('值班电话', '公众诉求', 350), ('民呼我应', '公众诉求', 250), ('微信举报', '公众诉求', 100)]])
    def save(payload, h=headers):
        return client.post('/api/assessment/manual/save-platform', json={'batch': '202610', **payload}, headers=h)
    assert save({'monthly': {'assessment_case_cnt': 20000}, 'sources': sources}).status_code == 200
    read = client.get('/api/assessment/manual?batch=202610', headers=headers).json
    assert read['sources'] == sources and read['monthly']['assessment_case_cnt'] == 20000
    print('PASS save/read, independent received total 20000 vs due total 1')
    for bad in [-1, 1.5, True, '1e3', 2147483648]:
        rows = [dict(sources[0], count=bad)]
        assert save({'sources': rows}).status_code == 400
    assert save({'sources': [sources[0], sources[0]]}).status_code == 400
    assert save({'sources': [dict(sources[0], group='无效')]}).status_code == 400
    # A later score error MUST roll back the already-replaced source rows.
    response = save({'sources': [dict(sources[0], count=99)],
                     'scores': [{'unit_type': 'dispatch', 'unit_name': '东城执法分队', 'score_type': 'extra', 'score_value': 'bad'}]})
    assert response.status_code == 400
    with engine.connect() as c:
        assert read_sources(c, '202610') == sources
    print('PASS invalid inputs and transaction rollback')
    assert save({'sources': sources}, collector).status_code == 403
    assert client.post('/api/assessment/manual/save-collector', json={'batch': '202610', 'sources': []}, headers=collector).status_code == 403
    assert client.post('/api/assessment/manual/save-collector', json={'batch': '202610', 'self_dispose_cnt': 5}, headers=collector).status_code == 200
    assert client.post('/api/assessment/manual/save-platform', json={'batch': '202609', 'sources': [sources[0]]}, headers=headers).status_code == 200
    with engine.connect() as c:
        assert read_sources(c, '202610') == sources
    print('PASS permission separation, collector save and month isolation')
    # Omitted source field retains rows; incomplete draft is allowed.
    assert save({'monthly': {'assessment_case_cnt': 20001}}).json['warnings']
    with engine.connect() as c:
        assert read_sources(c, '202610') == sources
    reports.REPORTS_DIR = str(OUT)
    old = OUT / 'assessment_202610.docx'
    old.write_bytes(b'original-report')
    response = client.post('/api/assessment/report/generate', json={'batch': '202610'}, headers=headers)
    assert response.status_code == 400 and old.read_bytes() == b'original-report'
    assert save({'monthly': {'assessment_case_cnt': 20000}}).status_code == 200
    data = collect_report_data(engine, '202610')
    assert data['sources']['total'] == 20000 and data['overview']['batch_total'] == 1
    assert data['sources']['groups']['公众诉求'] == 3000
    with patch.object(reports, 'generate_word', side_effect=RuntimeError('simulated failure')):
        response = client.post('/api/assessment/report/generate', json={'batch': '202610'}, headers=headers)
        assert response.status_code == 500 and old.read_bytes() == b'original-report'
    print('PASS mismatch rejection and original report retained on validation/render failure')
    response = client.post('/api/assessment/report/generate', json={'batch': '202610'}, headers=headers)
    assert response.status_code == 200, response.json
    from zipfile import ZipFile
    with ZipFile(old) as z:
        assert z.testzip() is None and len([n for n in z.namelist() if n.startswith('word/media/')]) == 2
    assert not list(OUT.glob('.assessment_202610_*/'))
    for rows in [[], [dict(sources[0], count=None)]]:
        assert save({'sources': rows}).status_code == 200
        assert client.post('/api/assessment/report/generate', json={'batch': '202610'}, headers=headers).status_code == 400
    from assessment_report.make_charts import chart_source_pie
    chart_source_pie(chart_sources(0, [dict(sources[0], count=0)]), str(OUT / 'zero.png'))
    chart_source_pie(chart_sources(20000, sources), str(OUT / 'normal.png'))
    many = [{'name': f'动态渠道{i}', 'group': '公众诉求', 'count': i} for i in range(1, 16)]
    chart_source_pie(chart_sources(sum(range(1,16)), many), str(OUT / 'many.png'))
    print('PASS valid Word with two charts, empty/missing rejection, zero and dynamic channels')
    print('ALL CHECKS PASSED. Output:', OUT)
finally:
    engine.dispose()
    with admin.begin() as c:
        c.execute(text(f'DROP DATABASE `{schema}`'))
    admin.dispose()
