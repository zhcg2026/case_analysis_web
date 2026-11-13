"""Calendar and cohort boundary tests. Extracts pure functions; no app imports or database access."""
import ast, re, json, copy, unittest, sys, os
from datetime import date, datetime, timedelta
from pathlib import Path
P = Path(__file__).resolve().parent
def load_module(path):
    tree = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    names = {'inspection_period', 'build_inspection_analysis'}
    constants = {'INSP_CATEGORY_RULES', 'INSP_AGE_BANDS'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)]
    scope = {'re': re, 'timedelta': timedelta}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<analysis>', 'exec'), scope)
    return scope, tree

class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope, cls.tree = load_module(os.environ.get('INSPECTION_SOURCE', P.parent / 'backend/inspection_routes.py'))
    def period(self, args, now=date(2026, 11, 13)):
        return self.scope['inspection_period'](args, now)
    def analyze(self, rows, args=None, now=date(2026, 11, 13)):
        return self.scope['build_inspection_analysis'](rows, args or {}, now)
    def row(self, id=1, found='2026-11-12', status='待整改', problem='地砖破损', **kw):
        return dict(id=id, case_date=found, road='解放路', location='测试位置', problem=problem, dept='市政', result='', status=status, **kw)
    def test_calendar_week(self):
        p = self.period({'mode': 'week', 'anchor': '2026-11-13'})
        self.assertEqual((p['start'], p['end'], p['previous_start'], p['previous_end']),
                         (date(2026,11,9),date(2026,11,13),date(2026,11,2),date(2026,11,6)))
        p = self.period({'mode':'week','anchor':'2026-01-01'})
        self.assertEqual(p['start'], date(2025,12,29))
        self.assertEqual(p['end'], date(2026,1,4))
    def test_month_lengths_leap(self):
        p = self.period({'mode':'month','anchor':'2024-03-01'}, date(2024,3,31))
        self.assertEqual(p['previous_end'], date(2024,2,29))
        rows=[self.row(found='2024-02-01'),self.row(2,found='2024-03-31')]
        result=self.analyze(rows,{'mode':'month','anchor':'2024-03-01'},date(2024,3,31))
        self.assertEqual(result['comparison']['current_end'],'2024-03-29')
        self.assertEqual(result['comparison']['current_total'],0)
        self.assertEqual(result['overview']['total'],1)
    def test_validation(self):
        for args in ({'mode':'bad'},{'mode':'range','date_from':'2026-11-12','date_to':'2026-11-01'},
                     {'anchor':'2026-11-14'},{'anchor':'2026-02-30'},{'anchor':'1 OR 1=1'},
                     {'page':'x'},{'size':51},{'page':0}):
            with self.subTest(args=args), self.assertRaises(ValueError):self.period(args)
    def test_no_data_not_zero_rate(self):
        r=self.analyze([],{'mode':'day','anchor':'2026-11-13'})
        self.assertEqual(r['overview']['total'],0);self.assertIsNone(r['overview']['rate'])
        self.assertEqual(len(r['trend']),1);self.assertIsNone(r['ages'][0]['share'])
        self.assertFalse(r['comparison']['available'])
    def test_age_boundaries(self):
        rows=[self.row(i+1,found=(date(2026,11,13)-timedelta(days=n)).isoformat()) for i,n in enumerate([0,3,4,7,8,14,15,21,22])]
        r=self.analyze(rows)
        self.assertEqual([b['total'] for b in r['ages']],[2,2,2,2,1]);self.assertEqual(r['overview']['old_pending'],3)
        detail=self.analyze(rows,{'detail_kind':'age','detail_value':'15—21天'})['detail']
        self.assertEqual(detail['total'],2)
    def test_current_status_not_completion_dates(self):
        rows=[self.row(found='2026-11-10',status='已整改'),self.row(2,found='2026-10-01')]
        r=self.analyze(rows,{'mode':'week'})
        self.assertEqual(r['overview']['rectified'],1);self.assertEqual(r['overview']['total'],1)
        self.assertNotIn('completed_this_week',r)
    def test_preserves_inputs_and_reconciles(self):
        rows=[self.row(),self.row(2,status='已整改',problem='缺苗'),self.row(3,problem='未知写法')]
        original=copy.deepcopy(rows);r=self.analyze(rows)
        self.assertEqual(rows,original)
        for key in ('departments','roads','categories','trend'):
            self.assertEqual(sum(x['total'] for x in r[key]),3)
            self.assertEqual(sum(x['pending'] for x in r[key]),2)
        self.assertEqual(sum(x['total'] for x in r['ages']),2)
        self.assertIn('未分类',[x['name'] for x in r['categories']])
    def test_dispute_and_photos_do_not_change_status(self):
        rows=[self.row(problem='小蓝乱停放')];rows[0]['result']='哈罗出行车辆，非我科室管理'
        r=self.analyze(rows,{'detail_kind':'disputed'})
        self.assertEqual(r['overview']['disputed'],1);self.assertEqual(r['detail']['items'][0]['id'],1)
    def test_comparison_coverage_and_zero(self):
        r=self.analyze([self.row(found='2026-11-12')],{'mode':'month'})
        self.assertFalse(r['comparison']['available']);self.assertIsNone(r['comparison']['delta'])
        rows=[self.row(found='2026-10-01'),self.row(2,found='2026-11-13')]
        r=self.analyze(rows,{'mode':'day'})
        self.assertTrue(r['comparison']['available']);self.assertIsNone(r['comparison']['percent'])
        self.assertEqual(r['comparison']['delta'],1)
    def test_future_dates_and_details(self):
        rows=[self.row(i,found='2026-11-12') for i in range(25)]+[self.row(99,found='2026-11-14')]
        r=self.analyze(rows,{'detail_kind':'all','page':2,'size':20})
        self.assertEqual(r['future_date_count'],1);self.assertEqual(r['detail']['total'],25)
        self.assertEqual(len(r['detail']['items']),5)
        for kind,value in [('dept','市政'),('road','解放路'),('category','设施破损'),('date','2026-11-12')]:
            self.assertEqual(self.analyze(rows,{'detail_kind':kind,'detail_value':value})['detail']['total'],25)
        with self.assertRaises(ValueError):self.analyze(rows,{'detail_kind':'bad'})
    def test_long_range_bounded_trend(self):
        r=self.analyze([self.row(found='2020-01-01'),self.row(2)])
        self.assertEqual(r['trend_grain'],'month');self.assertLess(len(r['trend']),100)

def run():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(AnalysisTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    return {'pure_tests':result.testsRun,'passed':True}
if __name__=='__main__':
    result=run()
    print(json.dumps(result))
