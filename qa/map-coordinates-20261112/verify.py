"""Exercise actual map endpoints against an isolated SQLite database."""
import argparse
import ast
import json
from pathlib import Path
from flask import Flask
from sqlalchemy import create_engine, text


def client_for(source):
    scope = {'__name__': 'isolated_map_routes'}
    exec(compile(source.read_text(encoding='utf-8-sig'), str(source), 'exec'), scope)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE case_data (id INTEGER, longitude REAL, latitude REAL, big_category TEXT, small_category TEXT, report_time TEXT, description TEXT, address TEXT, department TEXT, stage TEXT, is_delayed INTEGER, is_rework INTEGER, task_no TEXT, district TEXT, street TEXT, community TEXT, source TEXT, upload_batch TEXT)'))
        rows = [(1, 117.1, 36.1, '市容环境', '垃圾', '202610'), (2, None, 36.1, '市容环境', '垃圾', '202610'), (3, 117.1, None, '宣传广告', '广告', '202610'), (4, None, None, '街面秩序', '占道', '202610'), (5, 117.2, 36.2, '市容环境', '其他', '202610'), (6, 117.3, 36.3, '宣传广告', '广告', '202609')]
        for ident, lng, lat, big, small, batch in rows:
            connection.execute(text('INSERT INTO case_data (id, longitude, latitude, big_category, small_category, report_time, stage, is_delayed, is_rework, upload_batch) VALUES (:id,:lng,:lat,:big,:small,:time,:stage,0,0,:batch)'), {'id': ident, 'lng': lng, 'lat': lat, 'big': big, 'small': small, 'time': ('2026-10-' if batch == '202610' else '2026-09-') + f'{ident:02d} 10:00:00', 'stage': '[办结]', 'batch': batch})
    app = Flask('isolated-map')
    scope['register_case_map_routes'](app, engine=engine, protected=lambda fn: fn)
    return app.test_client(), engine


def check(source, baseline):
    client, engine = client_for(source)
    old, old_engine = client_for(baseline)
    passed = []
    def request(path):
        response = client.get('/api/case-map/' + path)
        assert response.status_code == 200, response.get_json()
        return response.get_json()
    for query in ['', '?batch=,,,']:
        assert client.get('/api/case-map/categories' + query).status_code == 400
    passed.append('unfiltered-query-still-rejected')
    categories = request('categories?batch=202610')['categories']
    assert len(categories) == 1 and categories[0]['total'] == 2
    assert {r['name']: r['count'] for r in categories[0]['small_categories']} == {'垃圾': 1, '其他': 1}
    passed.append('missing-longitude-latitude-and-both-excluded')
    points = request('points?batch=202610')
    assert points['total'] == 2 == sum(c['total'] for c in categories)
    assert {p['id'] for p in points['points']} == {1, 5}
    passed.append('category-count-matches-mappable-points')
    categories = request('categories?batch=202609,202610')['categories']
    assert sum(c['total'] for c in categories) == 3 and len(categories) == 2
    passed.append('multi-batch-categories')
    categories = request('categories?start_date=2026-10-05&end_date=2026-10-05')['categories']
    assert sum(c['total'] for c in categories) == 1
    passed.append('date-only-filter-and-inclusive-end-day')
    assert request('categories?batch=209901')['categories'] == []
    passed.append('empty-result')
    first = request('points?batch=202610&per_page=1&page=1')
    second = request('points?batch=202610&per_page=1&page=2')
    assert first['total'] == second['total'] == 2
    assert first['points'][0]['id'] != second['points'][0]['id']
    passed.append('pagination-preserved')
    stats = request('stats?batch=202610')
    assert stats['total_cases'] == 5 and stats['with_coordinates'] == 2
    passed.append('summary-retains-total-and-with-coordinate-counts')
    for path in ['points?batch=202610', 'points?batch=202610&per_page=1&page=2', 'heatmap?batch=202610', 'stats?batch=202610']:
        assert client.get('/api/case-map/' + path).get_json() == old.get('/api/case-map/' + path).get_json()
    passed.append('points-heatmap-stats-identical-to-before')
    before = old.get('/api/case-map/categories?batch=202610').get_json()['categories']
    assert sum(c['total'] for c in before) == 5
    passed.append('baseline-category-mismatch-reproduced')
    old_tree = ast.parse(baseline.read_text(encoding='utf-8-sig'))
    new_tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    old_fn = next(n for n in ast.walk(old_tree) if isinstance(n, ast.FunctionDef) and n.name == 'case_map_categories')
    register = next(n for n in new_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'register_case_map_routes')
    register.body = [old_fn if isinstance(n, ast.FunctionDef) and n.name == 'case_map_categories' else n for n in register.body]
    assert ast.dump(new_tree, include_attributes=False) == ast.dump(old_tree, include_attributes=False)
    passed.append('no-other-route-changed')
    engine.dispose(); old_engine.dispose()
    return {'passed_cases': len(passed), 'passed': passed, 'production_database_calls': 0, 'isolation': 'in-memory SQLite; actual route module; authentication bypass only in isolated test app'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('backend/case_map_routes.py'))
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(args.source, args.baseline)
    output = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(output, encoding='utf-8')
    print(output)
