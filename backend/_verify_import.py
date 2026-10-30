# -*- coding: utf-8 -*-
"""独立校验生成的导入版 xlsx：模拟应用读取路径 + 与库现值/源表交叉核对。"""
import csv

import pandas as pd

XLSX = r'D:\办公文件\2026年\文明城市创建\48个监控点位-系统导入版.xlsx'
SPOTS_TSV = r'C:\Users\Administrator\AppData\Local\Temp\spots.tsv'

sheets = pd.read_excel(XLSX, sheet_name=None)
print('sheets:', list(sheets))
df, cdf = sheets['点位'], sheets['联系人']
print('点位 sheet:', df.shape, '| 联系人 sheet:', cdf.shape)
print('点位列:', list(df.columns), '| 联系人列:', list(cdf.columns))


def app_norm(v):
    """照抄 cyw_routes._norm_contact_df 里 g() 的取值口径"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


for col in cdf.columns:
    cdf[col] = cdf[col].map(app_norm)
for col in df.columns:
    df[col] = df[col].map(app_norm)

db = {r['monitor_no']: r for r in csv.DictReader(open(SPOTS_TSV, encoding='utf-8'), delimiter='\t')}

# 1) 点位 sheet 必须与库现值逐一相同（导入是 UPDATE，写回同值才叫零漂移）
bad = []
for _, r in df.iterrows():
    d = db[r['监控序号']]
    for col, key in (('点位名称', 'name'), ('所在路段', 'road'), ('管理单位', 'manage_unit'),
                     ('点位类型', 'spot_type'), ('摄像头归属', 'camera_source')):
        if r[col] != (d[key] or ''):
            bad.append((r['监控序号'], col, r[col], d[key]))
print('\n[1] 点位 sheet 与库现值不一致:', bad or '无（48/48 一致）')

# 2) 无空姓名/空电话；电话形如 11 位
empty = cdf[(cdf['人员'] == '') | (cdf['电话'] == '')]
print('[2] 姓名为空或电话为空的行:', len(empty))
odd = cdf[~cdf['电话'].str.fullmatch(r'\d{11}')]
print('    非 11 位电话:', len(odd), odd['电话'].tolist()[:10])

# 3) 联系人表的序号必须都能在主表找到（否则应用给 warning 且不导入）
unknown = sorted(set(cdf['监控序号']) - set(df['监控序号']))
print('[3] 联系人表中主表没有的序号:', unknown or '无')
dup = cdf.duplicated(subset=['监控序号', '部门', '人员']).sum()
print('    (序号,部门,人员) 重复行:', dup)

# 4) 分组统计
print('[4] 按部门统计:')
print(cdf.groupby('部门').size().to_string())
per = cdf.groupby('监控序号').size()
print(f'    每点位联系人数: 最多 {per.max()} / 最少 {per.min()} / 平均 {per.mean():.1f}')
noct = sorted(set(df['监控序号']) - set(cdf['监控序号']))
print(f'    无联系人行的点位: {noct}（库里本来也是 0 条）')

# 5) 抽验已知个案
def get(mno, person):
    r = cdf[(cdf['监控序号'] == mno) & (cdf['人员'] == person)]
    return r[['部门', '电话']].values.tolist()


print('[5] 抽验:')
print('    XY01 王文杰:', get('XY01', '王文杰'))
print('    BQL007 刘爱芳:', get('BQL007', '刘爱芳'))
print('    SHL038 张永康:', get('SHL038', '张永康'), '| 曹会学:', get('SHL038', '曹会学'))
for mno in ('YDJ041', 'HDJ017', 'GJ01', 'YM01'):
    print(f'    {mno} 全部:')
    for row in cdf[cdf['监控序号'] == mno][['部门', '人员', '电话']].values.tolist():
        print('       ', row)
print('\n总条数:', len(cdf))
