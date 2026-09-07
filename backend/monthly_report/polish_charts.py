# -*- coding: utf-8 -*-
"""优化版图表重绘：统一专业视觉，数据与 make_word.py 完全一致，保持原图高宽比
输出到 charts_opt/，并生成 charts_opt/proportions.json 供 docx 调整图片显示尺寸
"""
import json, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
import matplotlib.patches as mp
import numpy as np

CFG = json.load(open(sys.argv[1], encoding='utf-8')) if len(sys.argv) > 1 else {}
BASE = CFG.get('workdir', os.getcwd())
D = json.load(open(os.path.join(BASE, CFG.get('out_json', 'analysis.json')), encoding='utf-8'))
OUT = os.path.join(BASE, 'charts_opt')
os.makedirs(OUT, exist_ok=True)

NAVY = '#17365D'; BLUE = '#2B6CB8'; RED = '#C53030'; AMB = '#D97706'; GRN = '#2F855A'; GRY = '#97A3B6'
PAL = ['#2B6CB8', '#4A90D9', '#38A169', '#D97706', '#C53030', '#805AD5', '#319795',
       '#D69E2E', '#5A67D8', '#DD6B20', '#2C7A7B', '#B794F4', '#718096', '#9F7AEA']
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 180
plt.rcParams['savefig.dpi'] = 200

B = D['basis']; E = D['eff']; S = D['structure']; T = D['time']; R = D['recur']
I = D['insight']; STD = D['std']; W = T['work']; K = I['weekend']
TOT = B['total']
PT = {r[0]: r for r in E['ptype']}

# 目标：与原 media 图相同的显示比例，避免替换后在 docx 中变形
RATIO = {
    'image1.png': 5.9843 / 3.8722,
    'image2.png': 5.9843 / 3.1602,
    'image3.png': 5.9843 / 2.7568,
    'image4.png': 5.9843 / 2.6223,
    'image5.png': 5.9843 / 3.2947,
    'image6.png': 5.9843 / 3.9671,
    'image7.png': 5.9843 / 4.4354,
    'image8.png': 5.9843 / 3.6981,
    'image9.png': 5.3543 / 4.1932,
}
WIDTH_IN = 6.2  # 出图逻辑宽度

proportions = {}


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    from PIL import Image
    im = Image.open(path); w, h = im.size
    proportions[name] = {'w': w, 'h': h, 'ratio': w / h}
    return path


def fresh_axes(w, h, name):
    """按原图比例创建坐标，保证替换后不变形"""
    fig, ax = plt.subplots(figsize=(WIDTH_IN, WIDTH_IN / RATIO[name]))
    return fig, ax


def style(ax, title, sub='', xlabel='', ylabel=''):
    ax.set_title(title, fontsize=14, color=NAVY, pad=(16 if sub else 12),
                 fontweight='bold', loc='center')
    if sub:
        ax.text(0.5, 1.02, sub, transform=ax.transAxes, ha='center', va='bottom',
                fontsize=9.5, color='#7A879E')
    if xlabel: ax.set_xlabel(xlabel, fontsize=10.5, color='#55627A')
    if ylabel: ax.set_ylabel(ylabel, fontsize=10.5, color='#55627A')
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax.spines[sp].set_color('#B7C0CD')
    ax.tick_params(colors='#44506B', labelsize=10)
    ax.grid(axis='y', color='#E7ECF3', linestyle='-', linewidth=.8, zorder=0)
    ax.set_axisbelow(True)


# ---------- 1 案件大类构成 ----------
fig, ax = fresh_axes(8.6, 5.6, 'image1.png')
dl = S['dalei'][::-1]; y = np.arange(len(dl)); v = [r[1] for r in dl]
colors = [PAL[i % len(PAL)] for i in range(len(v))][::-1]
ax.barh(y, v, color=colors, height=.62, zorder=3)
for i, val in enumerate(v):
    ax.text(val + 60, i, f'{val:,}  ({val/TOT*100:.1f}%)', va='center',
            fontsize=9.5, color='#44506B')
ax.set_yticks(y); ax.set_yticklabels([r[0] for r in dl], fontsize=10.5)
ax.set_xlim(0, max(v) * 1.28)
style(ax, '图1  案件大类构成', f'全月案件总量 {TOT:,} 件', '案件数（件）')
save(fig, 'fig1_dalei.png')

# ---------- 2 小类帕累托 Top15 ----------
fig, ax = fresh_axes(9, 4.8, 'image2.png')
xlt = S['xiaolei'][:15]; x = [r[0] for r in xlt]; vv = [r[1] for r in xlt]; cum = S['pareto'][:15]
ax.bar(np.arange(len(x)), vv, color=BLUE, width=.58, label='案件数（件）', zorder=3)
for i, val in enumerate(vv):
    ax.text(i, val + 60, f'{val}', ha='center', fontsize=8.5, color='#44506B')
ax.set_xticks(range(len(x))); ax.set_xticklabels(x, rotation=36, ha='right', fontsize=9)
ax2 = ax.twinx()
ax2.plot(np.arange(len(x)), cum, color=RED, marker='o', ms=5, lw=2.2, label='累计占比（%）', zorder=4)
ax2.set_ylabel('累计占比（%）', fontsize=10.5, color='#55627A')
ax2.set_ylim(0, 105); ax2.tick_params(colors='#44506B', labelsize=9.5)
ax2.axhline(80, color=RED, ls='--', lw=1, alpha=.5)
ax2.text(.6, 83, '80% 参考线', color=RED, fontsize=9)
style(ax, '图2  小类案件量 Top15 与累计占比', '', '', '案件数（件）')
ax.legend(loc='upper left', fontsize=9, frameon=False)
ax2.legend(loc='upper right', fontsize=9, frameon=False)
save(fig, 'fig2_pareto.png')

# ---------- 3 8月每日案件量走势 ----------
fig, ax = fresh_axes(9, 4.2, 'image3.png')
dd = T['daily']; xs = [r[0][5:] for r in dd]; ys = [r[1] for r in dd]
ax.plot(range(len(xs)), ys, color=BLUE, lw=2.2, marker='o', ms=4.5, zorder=3)
ax.fill_between(range(len(xs)), ys, color=BLUE, alpha=.08, zorder=1)
avg_all = round(sum(ys) / len(ys), 1)
ax.axhline(avg_all, color=GRY, ls='--', lw=1.1, zorder=2)
ax.text(.4, avg_all + 14, f'全月日均 {avg_all} 件', color='#5A6474', fontsize=9.5)
for lab, val, col, mark in [(a[0][5:], a[1], (RED if a[2] == '系统故障' else '#2A83C0'),
                             ('故障' if a[2] == '系统故障' else '雨')) for a in B['anomaly']]:
    i = xs.index(lab)
    ax.plot(i, val, 'o', color=col, ms=10, zorder=5)
    ax.annotate(f'{mark}\n{val}', (i, val), textcoords='offset points', xytext=(0, 14),
                ha='center', color=col, fontsize=9, fontweight='bold')
ax.set_ylim(0, 820); ax.set_xticks(range(len(xs)))
ax.set_xticklabels(xs, rotation=45, ha='right', fontsize=8.5)
Y = 8 if S["xiaolei"] else None
style(ax, '图3  8月每日案件量走势', '全月无明显持续升降趋势', '', '案件数（件）')
save(fig, 'fig3_daily.png')

# ---------- 4 上报时段分布 ----------
fig, ax = fresh_axes(9, 4.0, 'image4.png')
hh = T['hourly']
cols = [BLUE if 8 <= i <= 11 else ('#38A169' if 15 <= i <= 19 else (AMB if i == 14 else GRY))
        for i in range(24)]
ax.bar(range(24), hh, color=cols, width=.66, zorder=3)
for i, val in enumerate(hh):
    if val > 200:
        ax.text(i, val + 60, f'{val}', ha='center', fontsize=8.5, color='#44506B')
ax.set_xticks(range(24)); ax.set_xticklabels([f'{i}时' for i in range(24)], rotation=0, fontsize=9)
ax.set_ylim(0, max(hh) * 1.16)
# 覆盖两作业时段底色
ax.axvspan(8, 12, color=BLUE, alpha=.06, zorder=0)
ax.axvspan(14, 20, color='#38A169', alpha=.06, zorder=0)
style(ax, '图4  上报时段分布', '作业时间 8:00—11:30、14:00—20:00（蓝=上午 绿=下午 灰=其他）', '', '案件数（件）')
save(fig, 'fig4_hour.png')

# ---------- 5 各大类处置时长中位 ----------
fig, ax = fresh_axes(9, 5.0, 'image5.png')
lb = E['dalei'][::-1]
pos = np.arange(len(lb)); vals = [r[2] for r in lb]
bar_colors = [RED if v >= 24 else (AMB if v >= 8 else BLUE) for v in vals]
ax.barh(pos, vals, color=bar_colors, height=.6, zorder=3)
ax.set_yticks(pos); ax.set_yticklabels([r[0] for r in lb], fontsize=10)
for i, r in enumerate(lb):
    ax.text(r[2] + max(vals) * .01, i, f'{r[2]} h', va='center', fontsize=9, color='#44506B')
ax.set_xlim(0, max(vals) * 1.15)
ax.axvline(24, color=RED, ls='--', lw=1, alpha=.5)
ax.text(24.5, len(lb) - .5, '24h 界', color=RED, fontsize=9)
style(ax, '图5  各大类处置时长中位', '红=≥24h 琥珀=8–24h 蓝=<8h', '处置时长中位（小时）')
save(fig, 'fig7_dalei_dur.png')

# ---------- 6 部门处置时长中位 ----------
fig, ax = fresh_axes(9, 6.0, 'image6.png')
dep = E['dept'][::-1]
pos = np.arange(len(dep)); vals = [r[2] for r in dep]
bar_colors = [RED if v >= 24 else (AMB if v >= 8 else BLUE) for v in vals]
ax.barh(pos, vals, color=bar_colors, height=.62, zorder=3)
ax.set_yticks(pos); ax.set_yticklabels([r[0] for r in dep], fontsize=9)
for i, r in enumerate(dep):
    ax.text(r[2] + max(vals) * .008, i, f'{r[2]} h', va='center', fontsize=8.5, color='#44506B')
ax.set_xlim(0, max(vals) * 1.14)
ax.axvline(24, color=RED, ls='--', lw=1, alpha=.5)
ax.text(24.6, len(dep) - .5, '24h 界', color=RED, fontsize=9)
style(ax, '图6  处置部门处置时长中位', '红=≥24h 琥珀=8–24h 蓝=<8h', '处置时长中位（小时）')
save(fig, 'fig8_dept_dur.png')

# ---------- 7 高频重复点位空间分布 ----------
fig, ax = fresh_axes(8.6, 6.4, 'image7.png')
hs = R['top'][:40]
sc = ax.scatter([r['lon'] for r in hs], [r['lat'] for r in hs],
                s=[max(40, r['n'] * 6) for r in hs],
                c=[r['n'] for r in hs], cmap='Reds', alpha=.75, edgecolors='#fff', linewidths=.7, zorder=3)
ax.set_xlabel('经度', fontsize=10.5, color='#55627A')
ax.set_ylabel('纬度', fontsize=10.5, color='#55627A')
ax.tick_params(colors='#44506B', labelsize=9.5)
for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
for sp in ['left', 'bottom']: ax.spines[sp].set_color('#B7C0CD')
ax.grid(color='#E7ECF3', linewidth=.8, zorder=0)
ax.set_axisbelow(True)
cb = plt.colorbar(sc, ax=ax, fraction=.035, pad=.02)
cb.set_label('案件数（件）', fontsize=10, color='#55627A')
cb.ax.tick_params(colors='#44506B', labelsize=9)
ax.set_title('图7  高频重复点位空间分布（前40位）', fontsize=14, color=NAVY, pad=16, fontweight='bold')
ax.set_title('', pad=0)
ax.text(0.5, 1.02, '圆点大小与颜色深浅表示案件数', transform=ax.transAxes, ha='center',
        va='bottom', fontsize=9.5, color='#7A879E')
save(fig, 'fig5_recur_scatter.png')

# ---------- 8 高频重复 Top15 ----------
fig, ax = fresh_axes(9, 5.6, 'image8.png')
rt = R['top'][:15][::-1]
lbl = [(r['label'] or r['addr'][:12]) + ' · ' + r['xl'] for r in rt]
pos = np.arange(len(rt))
ax.barh(pos, [r['n'] for r in rt], color=BLUE, height=.42, label='案件数（件）', zorder=3)
ax.barh(pos + .34, [r['days'] for r in rt], color=AMB, height=.24, label='涉及天数（天）', zorder=3)
ax.set_yticks(pos + .17); ax.set_yticklabels(lbl, fontsize=8.8)
for i, r in enumerate(rt):
    ax.text(r['n'] + .8, i, str(r['n']), va='center', fontsize=8.8, color='#44506B')
    ax.text(r['days'] + .8, i + .34, str(r['days']), va='center', fontsize=8.8, color='#A85406')
ax.set_xlim(0, max(r['n'] for r in rt) * 1.2)
ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=2,
          frameon=False, fontsize=9.5, handletextpad=.4)
style(ax, '图8  高频重复点位 Top15（案件数与涉及天数）', '', '')
save(fig, 'fig6_recur_top.png')

# ---------- 9 专职监督员采集工作量分布 ----------
fig, ax = fresh_axes(8.4, 6.6, 'image9.png')
sp = I['sup_all']; pos = np.arange(len(sp))
colors_sp = [RED if r[1] >= 600 else (GRY if r[1] < I['sup_mean'] * .7 else BLUE) for r in sp]
ax.barh(pos, [r[1] for r in sp], color=colors_sp, height=.62, zorder=3)
for i, r in enumerate(sp):
    ax.text(r[1] + 10, i, str(r[1]), va='center', fontsize=9, color='#44506B')
ax.set_yticks(pos); ax.set_yticklabels([r[0] for r in sp], fontsize=9.5)
ax.axvline(I['sup_mean'], color=AMB, ls='--', lw=1.2, zorder=4)
ax.text(I['sup_mean'] + 14, len(sp) - .5, f"人均 {I['sup_mean']} 件", color=AMB, fontsize=9.5)
ax.set_xlim(0, max(r[1] for r in sp) * 1.18)
ax.axvspan(0, I['sup_mean'], color=AMB, alpha=.04, zorder=0)
style(ax, f"图9  专职监督员采集工作量分布", 
      f"{I['sup_n']}人，已剔除采集量<100件的非专职人员（红≥600 灰<均值70%）", '采集案件数（件）')
save(fig, 'fig9_sup.png')

json.dump(proportions, open(os.path.join(OUT, 'proportions.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('charts_opt 完成：', len(proportions), '张')
print(json.dumps(proportions, ensure_ascii=False))