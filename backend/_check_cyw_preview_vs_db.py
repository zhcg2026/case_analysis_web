# -*- coding: utf-8 -*-
"""把导入预览 JSON 的 48 行点位，与导入前库快照逐列比对。
凡是两表不一致的列，就是这次 UPDATE 会真实改动的字段——必须为空才算零漂移。
"""
import csv, json, io, sys

preview = json.load(open('_cyw_preview.json', encoding='utf-8'))['rows']
rows = {}
with open('_cyw_spot_before.tsv', encoding='utf-8', newline='') as f:
    rd = csv.DictReader(f, delimiter='\t')
    for r in rd:
        rows[r['monitor_no']] = r

print('预览行 %d 条；库快照 %d 条' % (len(preview), len(rows)))
assert len(preview) == len(rows) == 48

# 预览行字段 → 库列
KEYMAP = [
    ('spot_no', 'spot_no'), ('monitor_no', 'monitor_no'), ('name', 'name'),
    ('road', 'road'), ('manage_unit', 'manage_unit'),
    ('camera_source', 'camera_source'), ('spot_type', 'spot_type'),
    ('contact_name', 'contact_name'), ('contact_phone', 'contact_phone'),
    ('contact_extra', 'contact_extra'), ('lng', 'lng'), ('lat', 'lat'),
]


def norm(v):
    # mysqldump/-B 输出把 NULL 打成字面量 'NULL'，导入端对应写 None —— 两者等价
    if v is None or v == 'NULL':
        return ''
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


diffs = []
for p in preview:
    db = rows[p['monitor_no']]
    for pk, dk in KEYMAP:
        a, b = norm(p.get(pk)), norm(db.get(dk))
        # is_key 单独比（布尔/整型口径）
        if pk == 'is_key':
            continue
        if a != b:
            diffs.append((p['monitor_no'], pk, a, b))
    ik, dk2 = norm(p.get('is_key')), norm(db.get('is_key'))
    if (ik in ('1', 'true', 'True')) != (dk2 == '1'):
        diffs.append((p['monitor_no'], 'is_key', ik, dk2))

print('点位字段不一致项: %d' % len(diffs))
for d in diffs:
    print('   !!', d)

# 预览里的联系人 vs 本地校验过的生成文件口径
gen = {}
import openpyxl
wb = openpyxl.load_workbook(r'D:\办公文件\2026年\文明城市创建\48个监控点位-系统导入版.xlsx')
ws = wb['联系人']
hdr = [c.value for c in ws[1]]
i_no, i_d, i_p, i_ph = (hdr.index('监控序号'), hdr.index('部门'),
                        hdr.index('人员'), hdr.index('电话'))
for r in ws.iter_rows(min_row=2, values_only=True):
    if r[i_p]:
        gen.setdefault(str(r[i_no]), []).append((str(r[i_d]), str(r[i_p]), str(r[i_ph])))
prev = {p['monitor_no']: [(c['dept_label'], c['person'], c['phone']) for c in (p.get('contacts') or [])]
        for p in preview}

print('\n生成文件联系人点位 %d 个 / %d 条；预览联系人点位 %d 个 / %d 条'
      % (len(gen), sum(len(v) for v in gen.values()),
         sum(1 for v in prev.values() if v), sum(len(v) for v in prev.values())))
bad = 0
for mno in sorted(set(gen) | set(prev)):
    if gen.get(mno, []) != prev.get(mno, []):
        bad += 1
        print('   !! 联系人不一致', mno, '生成', len(gen.get(mno, [])), '预览', len(prev.get(mno, [])))
print('联系人逐条不一致的点位: %d' % bad)
print('\n结论: %s' % ('点位零漂移 + 联系人完全一致 → 可执行确认导入'
                    if not diffs and bad == 0 else '存在差异，禁止执行'))
