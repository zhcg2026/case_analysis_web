# -*- coding: utf-8 -*-
"""把新版《48个监控点位统计表》按上次入库的口径解析成 {monitor_no: [contact...]}，与库里 132 条对比。"""
import re
import xlrd

SRC = r'D:\办公文件\2026年\文明城市创建\48个监控点位统计表(分项）20261016－改定版.xls'

b = xlrd.open_workbook(SRC)
sh = b.sheet_by_name('主次干道')


def cell(r, c):
    v = sh.cell_value(r, c)
    if v is None:
        return ''
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def split_lines(s):
    return [x.strip() for x in re.split(r'[\n\r]+', s or '') if x.strip()]


def clean_name(s):
    # 姓名里混进的全角空格/普通空格规整掉
    return re.sub(r'[\s\u3000]+', '', s or '')


# 学苑路/解放路 两个点位的摄像头名称里没有 YHQ 编码，上次入库时按路段首字母合成
SYNTH = {('学苑路', '毕家索东'): 'XY01', ('学苑路', '通宝天际南'): 'XY02',
         ('解放路', '解放路萃林佳苑小区西口'): 'JF01', ('解放路', '解放路天逸公园门口'): 'JF02',
         ('盬街', '运城盬街中心口2'): 'GJ01', ('盬街', '运城盬街方言桥东南'): 'GJ02',
         ('黄河夜市', '夜市东出入口南侧向东'): 'YM01', ('黄河夜市', '夜市东出入口南侧向西'): 'YM02'}

out = {}
rows_info = []
cur_road = ''
for r in range(4, 48):
    if cell(r, 1):
        cur_road = cell(r, 1)
    cam_name = cell(r, 4)
    # 编码可能被写成全角括号/小写/双下划线，一律归一到半角大写
    m = re.search(r'[（(]\s*([A-Za-z]+\d+)\s*[）)]', cam_name)
    if m:
        mno = m.group(1).upper()
    else:
        mno = SYNTH.get((cur_road, cam_name))
    rows_info.append((r, cur_road, cam_name, mno))
    if not mno:
        print('!! 无法确定监控序号', r, cur_road, cam_name)
        continue
    # 环卫中心·片区负责人 / 点位主管：源表一格多人，入库只取第一个
    p1, ph1 = split_lines(cell(r, 9)), split_lines(cell(r, 10))
    p2, ph2 = split_lines(cell(r, 11)), split_lines(cell(r, 12))
    # 执法队：分队+中队+点位责任人（一格多人，只取第一个）
    team = f"{cell(r, 16)}{cell(r, 17)}"
    p3, ph3 = split_lines(cell(r, 18)), split_lines(cell(r, 19))
    cts = []
    if p1:
        cts.append(('环卫中心·片区负责人', clean_name(p1[0]), ph1[0] if ph1 else ''))
    if p2:
        cts.append(('环卫中心·点位主管', clean_name(p2[0]), ph2[0] if ph2 else ''))
    if team and p3:
        cts.append((f'执法队·{team}', clean_name(p3[0]), ph3[0] if ph3 else ''))
    out[mno] = cts

# 盬街（55 行合并区，锚定行 55）、夜市（59 行起）
GUJIE = [('建投', '李大战', '15535947666'), ('建投', '李转看', '13223698538'),
         ('环卫中心', '马红岗', '13603598028'), ('环卫中心', '张雪梅', '13835935701'),
         ('盬街北口·中城分队十三中队', '邵钧', '13327480603'),
         ('盬街南口·南城分队四中队（白班）', '董永刚', '13453934924'),
         ('盬街南口·南城分队四中队（夜班）', '冯晓栋', '15388593755')]
YESHI = [('点位总负责人', '尚继军', '13333590067'), ('点位责任人', '杨小明', '19935936999')]
out['GJ01'] = GUJIE
out['GJ02'] = GUJIE
out['YM01'] = YESHI
out['YM02'] = YESHI

print('解析到点位/摄像头数:', len(rows_info), ' 联系人总数:', sum(len(v) for v in out.values()))

import json
json.dump(out, open(r'D:\case_analysis_web\_parse_new_contacts.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已写出 _parse_new_contacts.json')
