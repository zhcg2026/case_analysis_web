# -*- coding: utf-8 -*-
"""冒烟：福龙马公司归属市容环卫中心（分组 + 计分 + 豁免展开）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

from assessment_routes import _group_departments, _calculate_scores, _is_sanitation_center_dept, _get_sanitation_districts

fails = []

# 1. 谓词
assert _is_sanitation_center_dept('环卫东片区')
assert _is_sanitation_center_dept('福龙马公司')
assert _is_sanitation_center_dept('公共卫生间管理部')
assert not _is_sanitation_center_dept('执法东片区')
assert not _is_sanitation_center_dept('督察队')
assert not _is_sanitation_center_dept('市政技术部')
print('[ok] 谓词')

# 2. 分组：福龙马进市容环卫中心，不再产生"其他"
depts = {
    '环卫东片区': {'total': 100, 'closed': 90, 'overtime': 5, 'delayed': 2, 'rework': 1},
    '环卫西片区': {'total': 50, 'closed': 45, 'overtime': 2, 'delayed': 1, 'rework': 0},
    '福龙马公司': {'total': 4, 'closed': 4, 'overtime': 0, 'delayed': 0, 'rework': 0},
    '执法东片区': {'total': 200, 'closed': 180, 'overtime': 10, 'delayed': 3, 'rework': 2},
}
groups = _group_departments(depts)
assert '其他' not in groups, f'不应再有其他组: {groups.keys()}'
assert groups['市容环卫中心']['total'] == 154, groups['市容环卫中心']
assert groups['市容环卫中心']['closed'] == 139, groups['市容环卫中心']
assert groups['执法队']['total'] == 200
print('[ok] _group_departments:', {k: v['total'] for k, v in groups.items()})

# 3. 片区明细不含福龙马（无人工分值录入口径）
districts = _get_sanitation_districts(depts)
assert set(districts.keys()) == {'环卫东片区', '环卫西片区'}, districts.keys()
print('[ok] 片区明细仅环卫片区')

# 4. 计分：市容环卫中心汇总含福龙马；福龙马不单独成行
results = _calculate_scores(depts, {'san_center_score': 100, 'san_garbage_score': 100})
san = results['市容环卫中心']
assert san['total'] == 154 and san['closed'] == 139, san
assert '福龙马公司' not in results, '福龙马不应作为独立明细行'
# 系统分：按期结案率=(139-7)/154, 超期率=7/154, 延期率=3/154, 返工率=1/154
import math
ontime = (139 - 7) / 154
ot = 7 / 154
expect = round((ontime * 100 + ot * 40) * 0.8 + (1 - 3 / 154) * 10 + (1 - 1 / 154) * 10, 3)
assert abs(san['system_score'] - expect) < 1e-9, (san['system_score'], expect)
print('[ok] _calculate_scores 市容环卫中心:', san)

# 5. 豁免组展开覆盖福龙马
from assessment_manual_routes import GROUP_MEMBER_MAP, calc_to_case_names
members = GROUP_MEMBER_MAP['市容环卫中心']
assert '福龙马公司' in members and '公共卫生间管理部' in members, members
popped = set()
for m in members:
    popped |= calc_to_case_names(m)
assert '福龙马公司' in popped, popped
print('[ok] 豁免展开成员:', members)

print('\n全部通过')
