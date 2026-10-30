# -*- coding: utf-8 -*-
"""生成《48个监控点位-系统导入版.xlsx》（双 sheet，全量联系人 293 条）。

设计原则（数据安全优先）：
- 「点位」sheet 直接取服务器库里 48 个点位的现值，保证导入的 UPDATE 写回去的是同一批值，
  点位档案零漂移（源表里两处单元格笔误也不带进来）。
- 「联系人」sheet 按源表四个人员列逐行展开：片区负责人/点位主管/一线值守(A岗B岗)/执法队责任人，
  姓名与电话按行配对；换行被写成空格的格子（SHL038）按两个以上空格补拆。
- 所有单元格按纯文本写（number_format='@'），避免电话被 Excel 推成数字。
"""
import csv
import re

import openpyxl
import xlrd

SRC_XLS = r'D:\办公文件\2026年\文明城市创建\48个监控点位统计表(分项）20261016－改定版.xls'
SPOTS_TSV = r'C:\Users\Administrator\AppData\Local\Temp\spots.tsv'   # 服务器库现值
OUT = r'D:\办公文件\2026年\文明城市创建\48个监控点位-系统导入版.xlsx'

# ---------------------------------------------------------------- 读库现值
db = {}
for row in csv.DictReader(open(SPOTS_TSV, encoding='utf-8'), delimiter='\t'):
    db[row['monitor_no']] = row
assert len(db) == 48, f'库现值应为 48 个点位，实际 {len(db)}'

# ---------------------------------------------------------------- 读源表
sh = xlrd.open_workbook(SRC_XLS).sheet_by_name('主次干道')


def cell(r, c):
    v = sh.cell_value(r, c)
    if v is None:
        return ''
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def split_phones(s):
    out = []
    for ln in re.split(r'[\n\r]+', s or ''):
        out += [y for y in re.split(r'[ \u3000]+', ln) if y]
    return [re.sub(r'\.0$', '', y) for y in out]


def split_names(s, nph):
    """先按换行拆；个数和电话对不上时，再按两个以上空格拆（源表把换行写成空格的格子）"""
    def flat(x):
        return re.sub(r'[\s\u3000]+', '', x)
    out = [flat(x) for x in re.split(r'[\n\r]+', s or '') if flat(x)]
    if len(out) != nph:
        out2 = []
        for ln in re.split(r'[\n\r]+', s or ''):
            out2 += [flat(x) for x in re.split(r' {2,}', ln) if flat(x)]
        if len(out2) == nph:
            out = out2
    return out


SYNTH = {('学苑路', '毕家索东'): 'XY01', ('学苑路', '通宝天际南'): 'XY02',
         ('解放路', '解放路萃林佳苑小区西口'): 'JF01', ('解放路', '解放路天逸公园门口'): 'JF02'}

# 盬街（55 行合并区，锚定行 55）/ 夜市（59 行起）：源表写成一个文本块，按上次口径拆条
GUJIE = [('建投', '李大战', '15535947666'), ('建投', '李转看', '13223698538'),
         ('环卫中心', '马红岗', '13603598028'), ('环卫中心', '张雪梅', '13835935701'),
         ('盬街北口·中城分队十三中队', '邵钧', '13327480603'),
         ('盬街南口·南城分队四中队（白班）', '董永刚', '13453934924'),
         ('盬街南口·南城分队四中队（夜班）', '冯晓栋', '15388593755')]
YESHI = [('点位总负责人', '尚继军', '13333590067'), ('点位责任人', '杨小明', '19935936999')]

contacts = {}     # monitor_no -> [(dept_label, person, phone), ...]
unaligned = []
cur_road = ''
for r in range(4, 48):
    if cell(r, 1):
        cur_road = cell(r, 1)
    cam = cell(r, 4)
    m = re.search(r'[（(]\s*([A-Za-z]+\d+)\s*[）)]', cam)
    mno = m.group(1).upper() if m else SYNTH.get((cur_road, cam))
    if not mno:
        raise SystemExit(f'行{r} 无法确定监控序号: {cur_road} / {cam}')
    if mno not in db:
        raise SystemExit(f'行{r} 序号 {mno} 不在库里')
    lst = []
    # 1) 环卫中心·片区负责人（一格多人，全部展开）
    ph = split_phones(cell(r, 10))
    nm = split_names(cell(r, 9), len(ph))
    for i in range(len(nm)):
        lst.append(('环卫中心·片区负责人', nm[i], ph[i] if i < len(ph) else ''))
    # 2) 环卫中心·点位主管
    ph = split_phones(cell(r, 12))
    nm = split_names(cell(r, 11), len(ph))
    for i in range(len(nm)):
        lst.append(('环卫中心·点位主管', nm[i], ph[i] if i < len(ph) else ''))
    # 3) 环卫中心·一线值守（A岗/B岗，源表单独一列角色，与姓名逐行对齐）
    ph = split_phones(cell(r, 15))
    nm = split_names(cell(r, 14), len(ph))
    roles = [x.strip() for x in re.split(r'[\n\r]+', cell(r, 13) or '') if x.strip()]
    for i in range(len(nm)):
        role = roles[i] if i < len(roles) else ''
        suffix = f'（{role}）' if role else ''
        lst.append((f'环卫中心·一线值守{suffix}', nm[i], ph[i] if i < len(ph) else ''))
    # 4) 执法队·{分队}{中队} 点位责任人（一格多人，全部展开）
    team = f'{cell(r, 16)}{cell(r, 17)}'
    ph = split_phones(cell(r, 19))
    nm = split_names(cell(r, 18), len(ph))
    for i in range(len(nm)):
        lst.append((f'执法队·{team}', nm[i], ph[i] if i < len(ph) else ''))
    for lbl, p, q in lst:
        if not p or not q:
            unaligned.append((mno, lbl, p, q))
    contacts[mno] = lst

for mno, lst in (('GJ01', GUJIE), ('GJ02', GUJIE), ('YM01', YESHI), ('YM02', YESHI)):
    contacts[mno] = lst

assert not unaligned, f'存在姓名为空或电话为空的行: {unaligned}'
assert set(contacts) <= set(db), '联系人表出现了库里没有的序号'

# ---------------------------------------------------------------- 写 xlsx
wb = openpyxl.Workbook()
ws = wb.active
ws.title = '点位'
ws.append(['监控序号', '点位名称', '所在路段', '管理单位', '点位类型', '摄像头归属'])
for mno in sorted(db):
    s = db[mno]
    ws.append([s['monitor_no'], s['name'], s['road'], s['manage_unit'],
               s['spot_type'], s['camera_source']])

ws2 = wb.create_sheet('联系人')
ws2.append(['监控序号', '部门', '人员', '电话'])
n = 0
for mno in sorted(contacts):
    for lbl, person, phone in contacts[mno]:
        ws2.append([mno, lbl, person, phone])
        n += 1

for sheet in (ws, ws2):
    for row in sheet.iter_rows():
        for c in row:
            c.number_format = '@'
    for col in sheet.columns:
        w = max(len(str(c.value or '')) for c in col)
        sheet.column_dimensions[col[0].column_letter].width = min(max(w * 1.9, 10), 46)

wb.save(OUT)
print(f'已生成 {OUT}')
print(f'  点位 sheet: {ws.max_row - 1} 行')
print(f'   联系人 sheet: {n} 行，覆盖 {len(contacts)} 个点位')
missing = sorted(set(db) - set(contacts))
print(f'  无联系人的点位（源表四列全空，库里本来也没有）: {missing}')
