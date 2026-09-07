# -*- coding: utf-8 -*-
"""生成 Word 公文稿：先出图表 PNG，再排版 docx
口径：结案=当前阶段[办结]；超时/延期/返工=对应字段；考核时限=《立案、处置和结案标准》法定时限
"""
import json, os, sys, glob
import matplotlib
matplotlib.use('Agg')
# 彻底删除字体缓存
_cache = matplotlib.get_cachedir()
for _f in glob.glob(os.path.join(_cache, 'fontlist*')):
    os.remove(_f)
import matplotlib.font_manager as fm
# 显式注册字体文件 + 直接设 font.family 为字体名（不走 sans-serif 中转）
fm.fontManager.addfont('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc')
matplotlib.rcParams['font.family'] = 'WenQuanYi Micro Hei'
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
import numpy as np
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CFG = json.load(open(sys.argv[1], encoding='utf-8')) if len(sys.argv) > 1 else {}
BASE = CFG.get('workdir', os.getcwd())
os.makedirs(BASE, exist_ok=True)


def _p(*a):
    return os.path.join(BASE, *a)


MC = CFG.get('month_cn', '2026年1月')        # 报告标题用，如 2026年8月
ML = CFG.get('month_label', '1月份')         # 表题/图注用，如 8月份
MS = CFG.get('month_short', ML[:2])          # 图注用，如 8月
ORG = CFG.get('org', '')
MINSUP = CFG.get('min_cases_supervisor', 100)
MT = CFG.get('month_cn_text', MC)      # 正文用月份写法，如 2026 年 8 月
BRIEF = CFG.get('brief', True)          # 精简版（定稿形态）/ 完整版（含方法说明与全部建议）
UNIT_DESC = CFG.get('unit_addr_desc', '金城大厦（铺安街 989 号）')

D = json.load(open(_p(CFG.get('out_json', 'analysis.json')), encoding='utf-8'))
CHARTS = _p('charts')
os.makedirs(CHARTS, exist_ok=True)

NAVY = '#12305c'; BLUE = '#2b6cb8'; RED = '#c53030'; AMB = '#d97706'; GRN = '#2f855a'; GRY = '#97a3b6'
PAL = ['#2b6cb8', '#4a90d9', '#38a169', '#d97706', '#c53030', '#805ad5', '#319795',
       '#d69e2e', '#5a67d8', '#dd6b20', '#2c7a7b', '#b794f4', '#718096', '#9f7aea']
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150

B = D['basis']; E = D['eff']; S = D['structure']; T = D['time']; R = D['recur']
I = D['insight']; STD = D['std']; W = T['work']; K = I['weekend']
TOT = B['total']
PT = {r[0]: r for r in E['ptype']}

_WW = T['work'].get('work_windows') or [[8, 11.5], [14, 20]]


def _h(x):
    return ('%d:%02d' % (int(x), round((x - int(x)) * 60))) if x % 1 else ('%d:00' % int(x))


_WT = '、'.join('%s—%s' % (_h(a), _h(b)) for a, b in _WW)


def _u(key):
    """从 std.unit_dist 取某时限单位的分类小类数"""
    for r in STD['unit_dist']:
        if r[0] == key:
            return r[1]
    return 0



def save(fig, name):
    p = os.path.join(CHARTS, name)
    fig.tight_layout(); fig.savefig(p, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def style(ax, title, xlabel='', ylabel=''):
    ax.set_title(title, fontsize=13, color=NAVY, pad=12, fontweight='bold')
    ax.set_xlabel(xlabel, fontsize=10.5, color='#4a5568')
    ax.set_ylabel(ylabel, fontsize=10.5, color='#4a5568')
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e0'); ax.spines['bottom'].set_color('#cbd5e0')
    ax.tick_params(colors='#4a5568', labelsize=10)
    ax.grid(axis='x', color='#eef1f6', linestyle='-', linewidth=.8)
    ax.set_axisbelow(True)


# ============ 图表 ============
# 1 大类构成（14 类）
fig, ax = plt.subplots(figsize=(8.6, 5.6))
dl = S['dalei']; y = [r[0] for r in dl][::-1]; v = [r[1] for r in dl][::-1]
b = ax.barh(y, v, color=[PAL[i % len(PAL)] for i in range(len(v))][::-1], height=.6)
for r, val in zip(b, v):
    ax.text(val + 40, r.get_y() + r.get_height() / 2, f'{val:,}  ({val/TOT*100:.1f}%)',
            va='center', fontsize=9, color='#4a5568')
ax.set_xlim(0, max(v) * 1.30); style(ax, '图1  案件大类构成', '案件数（件）')
F1 = save(fig, 'fig1_dalei.png')

# 2 小类帕累托 Top15
fig, ax = plt.subplots(figsize=(9, 4.8))
xlt = S['xiaolei'][:15]; x = [r[0] for r in xlt]; vv = [r[1] for r in xlt]; cum = S['pareto'][:15]
ax.bar(x, vv, color=BLUE, width=.62, label='案件数')
ax.set_xticks(range(len(x))); ax.set_xticklabels(x, rotation=38, ha='right', fontsize=9.5)
ax2 = ax.twinx(); ax2.plot(range(len(x)), cum, color=RED, marker='o', ms=4.5, lw=2, label='累计占比')
ax2.set_ylabel('累计占比（%）', fontsize=10.5, color='#4a5568')
ax2.set_ylim(0, 105); ax2.tick_params(colors='#4a5568', labelsize=10)
ax2.axhline(80, color=RED, ls='--', lw=.9, alpha=.55); ax2.text(.1, 82, '80%', color=RED, fontsize=9.5)
style(ax, '图2  小类案件量 Top15 与累计占比', '', '案件数（件）')
ax.legend(loc='upper left', fontsize=9.5); ax2.legend(loc='upper right', fontsize=9.5)
F2 = save(fig, 'fig2_pareto.png')

# 3 日趋势（8/31 按全天，无半天标注）
fig, ax = plt.subplots(figsize=(9, 4.2))
dd = T['daily']; xs = [r[0][5:] for r in dd]; ys = [r[1] for r in dd]
ax.plot(range(len(xs)), ys, color=BLUE, lw=2, marker='o', ms=4)
ax.fill_between(range(len(xs)), ys, color=BLUE, alpha=.10)
avg_all = round(sum(ys) / len(ys), 1)
ax.axhline(avg_all, color=GRY, ls='--', lw=1)
ax.text(.4, avg_all + 12, f'全月日均 {avg_all} 件', color='#5a6474', fontsize=9.5)
for lab, val, col, mark in [(a[0][5:], a[1], (RED if a[2] == '系统故障' else '#378add'),
                             ('故障' if a[2] == '系统故障' else '雨')) for a in B['anomaly']]:
    i = xs.index(lab)
    ax.plot(i, val, 'o', color=col, ms=9, zorder=5)
    ax.annotate(f'{mark}\n{val}', (i, val), textcoords='offset points', xytext=(0, 13),
                ha='center', color=col, fontsize=9, fontweight='bold')
ax.set_ylim(0, 800); ax.set_xticks(range(len(xs)))
ax.set_xticklabels(xs, rotation=45, ha='right', fontsize=8.5)
style(ax, '图3  8月每日案件量走势', '', '案件数（件）')
F3 = save(fig, 'fig3_daily.png')

# 4 时段分布
fig, ax = plt.subplots(figsize=(9, 4.0))
hh = T['hourly']
cols = [BLUE if 8 <= i <= 11 else ('#38a169' if 15 <= i <= 19 else (AMB if i == 14 else GRY)) for i in range(24)]
ax.bar(range(24), hh, color=cols, width=.68)
for i, val in enumerate(hh):
    if val > 200: ax.text(i, val + 45, str(val), ha='center', fontsize=9, color='#4a5568')
ax.set_xticks(range(24)); ax.set_xticklabels([f'{i}时' for i in range(24)], rotation=45, ha='right', fontsize=9)
ax.set_ylim(0, max(hh) * 1.15)
style(ax, '图4  上报时段分布（对照作业时间 8:00—11:30、14:00—20:00）', '', '案件数（件）')
F4 = save(fig, 'fig4_hour.png')

# 5 重复案件空间分布
fig, ax = plt.subplots(figsize=(8.6, 6.4))
hs = R['top'][:40]
sc = ax.scatter([r['lon'] for r in hs], [r['lat'] for r in hs],
                s=[max(30, r['n'] * 5) for r in hs],
                c=[r['n'] for r in hs], cmap='Reds', alpha=.72, edgecolors='#fff', linewidths=.5)
ax.set_xlabel('经度', fontsize=10.5, color='#4a5568'); ax.set_ylabel('纬度', fontsize=10.5, color='#4a5568')
ax.set_title('图5  高频重复点位空间分布（前40位，圆点大小表示案件数）', fontsize=13, color=NAVY, pad=12, fontweight='bold')
ax.tick_params(colors='#4a5568', labelsize=9.5)
ax.grid(color='#eef1f6', linewidth=.8); ax.set_axisbelow(True)
for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
for sp in ['left', 'bottom']: ax.spines[sp].set_color('#cbd5e0')
cb = plt.colorbar(sc, ax=ax, fraction=.035, pad=.02); cb.set_label('案件数（件）', fontsize=10, color='#4a5568')
cb.ax.tick_params(colors='#4a5568', labelsize=9)
F5 = save(fig, 'fig5_recur_scatter.png')

# 6 高频重复 Top15（用问题描述点位）
fig, ax = plt.subplots(figsize=(9, 5.6))
rt = R['top'][:15][::-1]
lbl = [(r['label'] or r['addr'][:12]) + ' · ' + r['xl'] for r in rt]
pos = np.arange(len(rt))
ax.barh(pos, [r['n'] for r in rt], color=BLUE, height=.5, label='案件数（件）')
ax.barh(pos + .38, [r['days'] for r in rt], color=AMB, height=.28, label='涉及天数（天）')
ax.set_yticks(pos + .19); ax.set_yticklabels(lbl, fontsize=9)
for i, r in enumerate(rt):
    ax.text(r['n'] + 1.2, i, str(r['n']), va='center', fontsize=9, color='#4a5568')
ax.set_xlim(0, max(r['n'] for r in rt) * 1.16)
ax.legend(loc='lower right', fontsize=10)
style(ax, '图6  高频重复点位 Top15（按问题描述点位）', '案件数（件）/ 涉及天数（天）')
F6 = save(fig, 'fig6_recur_top.png')

# 7 大类处置时长中位
fig, ax = plt.subplots(figsize=(9, 5.0))
lb = E['dalei'][::-1]
pos = np.arange(len(lb))
ax.barh(pos, [r[2] for r in lb], height=.6, color=BLUE)
ax.set_yticks(pos); ax.set_yticklabels([r[0] for r in lb], fontsize=10)
for i, r in enumerate(lb):
    ax.text(r[2] + .5, i, f'{r[2]} h', va='center', fontsize=9, color='#4a5568')
ax.set_xlim(0, max(r[2] for r in lb) * 1.12)
style(ax, '图7  各大类处置时长中位（案件量 ≥30）', '处置时长中位（小时）')
F7 = save(fig, 'fig7_dalei_dur.png')

# 8 部门处置时长中位
fig, ax = plt.subplots(figsize=(9, 6.0))
dep = E['dept'][::-1]
pos = np.arange(len(dep))
ax.barh(pos, [r[2] for r in dep], height=.62, color=BLUE)
for i, r in enumerate(dep):
    ax.text(r[2] + .3, i, f'{r[2]} h', va='center', fontsize=8.5, color='#4a5568')
ax.set_yticks(pos); ax.set_yticklabels([r[0] for r in dep], fontsize=9)
ax.set_xlim(0, max(r[2] for r in dep) * 1.12)
style(ax, '图8  处置部门处置时长中位（案件量 ≥50）', '处置时长中位（小时）')
F8 = save(fig, 'fig8_dept_dur.png')

# 9 专职监督员
fig, ax = plt.subplots(figsize=(8.4, 6.6))
sp = I['sup_all']; pos = np.arange(len(sp))
ax.barh(pos, [r[1] for r in sp],
        color=[RED if r[1] >= 600 else (GRY if r[1] < I['sup_mean'] * .7 else BLUE) for r in sp], height=.62)
for i, r in enumerate(sp):
    ax.text(r[1] + 8, i, str(r[1]), va='center', fontsize=9, color='#4a5568')
ax.set_yticks(pos); ax.set_yticklabels([r[0] for r in sp], fontsize=9.5)
ax.axvline(I['sup_mean'], color=AMB, ls='--', lw=1.1)
ax.text(I['sup_mean'] + 10, len(sp) - .6, f"人均 {I['sup_mean']} 件", color=AMB, fontsize=9.5)
ax.set_xlim(0, max(r[1] for r in sp) * 1.16)
style(ax, f"图9  专职监督员采集工作量分布（{I['sup_n']}人，已剔除采集量<{MINSUP}件的非专职人员）", '采集案件数（件）')
F9 = save(fig, 'fig9_sup.png')

# ============ Word ============
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(3.0)
sec.top_margin = Cm(2.8); sec.bottom_margin = Cm(2.5)
st = doc.styles['Normal']; st.font.name = '仿宋_GB2312'; st.font.size = Pt(16)
st.element.rPr.rFonts.set(qn('w:eastAsia'), '仿宋_GB2312')


def para(text, size=16, font='仿宋_GB2312', bold=False, align=None, indent=True,
         space_before=0, space_after=6, color=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5; pf.space_before = Pt(space_before); pf.space_after = Pt(space_after)
    if indent: pf.first_line_indent = Pt(size * 2)
    if align is not None: p.alignment = align
    r = p.add_run(text); r.font.size = Pt(size); r.font.bold = bold; r.font.name = font
    r._element.rPr.rFonts.set(qn('w:eastAsia'), font)
    if color: r.font.color.rgb = RGBColor.from_string(color)
    return p


def h1(t): return para(t, size=16, font='黑体', space_before=14, space_after=8)
def h2(t): return para(t, size=16, font='楷体_GB2312', bold=True, space_before=8, space_after=4)


def caption(t):
    return para(t, size=12, font='楷体_GB2312', align=WD_ALIGN_PARAGRAPH.CENTER,
                indent=False, space_before=4, space_after=12, color='595959')


def shade(cell, h):
    el = OxmlElement('w:shd'); el.set(qn('w:fill'), h); cell._tc.get_or_add_tcPr().append(el)


def table(headers, rows, widths=None, fontsize=11, center=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = ''
        p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15; p.paragraph_format.space_after = Pt(2)
        r = p.add_run(str(h)); r.font.size = Pt(fontsize); r.font.bold = True
        r.font.name = '黑体'; r._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        shade(c, 'E8EFF7')
    for row in rows:
        cs = t.add_row().cells
        for i, val in enumerate(row):
            cs[i].text = ''
            p = cs[i].paragraphs[0]
            p.paragraph_format.line_spacing = 1.15; p.paragraph_format.space_after = Pt(2)
            if center and i in center: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(val)); r.font.size = Pt(fontsize)
            r.font.name = '仿宋_GB2312'; r._element.rPr.rFonts.set(qn('w:eastAsia'), '仿宋_GB2312')
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths): row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


def pic(path, width=15.2):
    doc.add_picture(path, width=Cm(width)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


# 标题
para(f'{MC}份城市管理案件', size=22, font='方正小标宋简体',
     align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, space_after=0)
para('数据分析报告', size=22, font='方正小标宋简体', align=WD_ALIGN_PARAGRAPH.CENTER,
     indent=False, space_after=10)
para(f'（{ORG}）', size=12, font='楷体_GB2312',
     align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, space_after=16, color='595959')

# 一 总体情况
h1('一、总体情况')
if BRIEF:
    para(f"本次数据分析考核口径为处置截止时间在 {MT}的案件，共 {TOT:,} 条，"
         f"全月办结 {B['closed']:,} 件，办结率 {B['close_rate']}%，未办结 {B['unclosed']} 件。"
         f"处置时长中位 {E['dur']['p50']} 小时，{E['dur']['in4h']}% 的案件在 4 小时内办结，"
         f"{E['dur']['in24h']}% 在 24 小时内办结，当日结案率 {E['same_day_rate']}%。"
         f"超时 {E['overtime']['n']} 件（超时率 {E['overtime']['rate']}%）、"
         f"延期 {E['delay']['n']} 件（延期率 {E['delay']['rate']}%）、"
         f"返工 {E['rework']['n']} 件（返工率 {E['rework']['rate']}%），"
         f"其余 {E['ontime']:,} 件为按期办结，按期办结率 {E['ontime_rate']}%。")
else:
    para(f"本表按考核口径统计，即处置截止时间在 {MC} 的案件，共 {TOT:,} 条，"
         f"其中 {B['deadline_aug']:,} 条（{B['deadline_aug_rate']}%）的处置截止时间落在 {MS}内，"
         f"另有 {TOT - B['deadline_aug']} 条顺延至次月初。按上报时间划分，本月新上报 {B['aug_n']:,} 条，"
         f"往月上报、经延期后处置截止时间落在本月的 {B['prev_n']} 条。")
    para(f"全月办结 {B['closed']:,} 件（以当前阶段为“办结”为准），办结率 {B['close_rate']}%，"
         f"未办结 {B['unclosed']} 件。处置时长中位 {E['dur']['p50']} 小时，"
         f"{E['dur']['in4h']}% 的案件在 4 小时内办结，{E['dur']['in24h']}% 在 24 小时内办结，"
         f"当日结案率 {E['same_day_rate']}%。")
    para(f"按平台认定字段统计，超时 {E['overtime']['n']} 件（超时率 {E['overtime']['rate']}%）、"
         f"延期 {E['delay']['n']} 件（延期率 {E['delay']['rate']}%）、"
         f"返工 {E['rework']['n']} 件（返工率 {E['rework']['rate']}%），"
         f"其余 {E['ontime']:,} 件为按期办结，按期办结率 {E['ontime_rate']}%。")
para(f"表1  {ML}核心指标一览", size=12, font='黑体', indent=False, space_before=6,
     space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
table(['指标', '数值', '指标', '数值'],
      [['案件总量', f"{TOT:,} 件", '办结率', f"{B['close_rate']}%"],
       ['本月新上报', f"{B['aug_n']:,} 件", '往月挂账', f"{B['prev_n']} 件"],
       ['处置时长中位', f"{E['dur']['p50']} 小时", '当日结案率', f"{E['same_day_rate']}%"],
       ['超时率', f"{E['overtime']['rate']}%", '延期率', f"{E['delay']['rate']}%"],
       ['返工率', f"{E['rework']['rate']}%", '按期办结率', f"{E['ontime_rate']}%"],
       ['重复案件占比', f"{R['ge3_rate']}%", '涉及小类', f"{S['xiaolei_n']} 类"]],
      widths=[3.6, 3.4, 3.6, 3.4], center=[1, 3])

# 二 结构
h1('二、案件结构分析')
h2('（一）问题类型集中')
para(f"本月案件涉及 {S['xiaolei_n']} 个小类，Top10 小类覆盖 {S['top10_cover']}%，"
     f"Top20 覆盖 {S['top20_cover']}%。无照经营游商、道路不洁、共享单车管理、店外经营、沿街晾挂五类"
     f"合计 {sum(r[1] for r in S['xiaolei'][:5]):,} 件，占 "
     f"{sum(r[1] for r in S['xiaolei'][:5])/TOT*100:.1f}%。大类层面，街面秩序与市容环境合计 "
     f"{(S['dalei'][0][1]+S['dalei'][1][1])/TOT*100:.1f}%。")
pic(F1); caption('图1  案件大类构成')
pic(F2); caption('图2  小类案件量Top15与累计占比')
para("表2  案件量Top10小类", size=12, font='黑体', indent=False, space_before=6,
     space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
xldur = {r[0]: r for r in E['xiaolei'] + E['xiaolei_fast']}
table(['序号', '小类名称', '案件数', '占比', '处置时长中位'],
      [[i + 1, r[0], f"{r[1]:,}", f"{r[1]/TOT*100:.1f}%",
        (f"{xldur[r[0]][2]}h" if r[0] in xldur else '—')]
       for i, r in enumerate(S['xiaolei'][:10])],
      widths=[1.2, 4.8, 2.2, 2.0, 3.0], fontsize=10.5, center=[0, 2, 3, 4])
h2('（二）发现渠道构成')
para(f"采集员上报 {I['src_collector']:,} 件，占 {I['src_collector_rate']}%；"
     f"视频上报 {I['src_video']} 件，占 {I['src_video']/TOT*100:.1f}%；"
     f"12345 热线转办、电话快办、市民热线举报、微信举报、民呼我应邮箱等市民政务渠道合计 "
     f"{I['src_gov']} 件，占 {I['src_gov_rate']}%。")
h2('（三）空间分布')
para(f"从街道看，北城办事处 {S['street'][0][1]:,} 件、东城办事处 {S['street'][1][1]:,} 件、"
     f"安邑办事处 {S['street'][2][1]:,} 件、姚孟办事处 {S['street'][3][1]:,} 件，"
     f"四个街道合计占 {sum(r[1] for r in S['street'][:4])/TOT*100:.1f}%。"
     f"社区层面，留驾庄村 {S['community'][0][1]} 件居首，金色家园社区 {S['community'][1][1]} 件、"
     f"岳坛村 {S['community'][2][1]} 件次之。")
para("表3  街道案件量分布", size=12, font='黑体', indent=False, space_before=6,
     space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
table(['街道', '案件数', '占比'],
      [[r[0], f"{r[1]:,}", f"{r[1]/TOT*100:.1f}%"] for r in S['street'] if r[0] != '未标注'],
      widths=[5.0, 3.4, 3.0], center=[1, 2])

# 三 时空
h1('三、时空分布特征')
h2('（一）日趋势')
anomaly_txt = '、'.join(f"{a[0][5:]}日（{a[1]}件）" for a in B['anomaly'])
good_n = B['aug_n'] - sum(a[1] for a in B['anomaly'])
good_days = W['days'] - len(B['anomaly'])
_RT = CFG.get('anomaly_reason_tpl', {})


def _reason():
    """按异常类型聚合生成原因说明，如：8月4日、12日为降雨天气，采集作业受限"""
    g = {}
    for a in B['anomaly']:
        g.setdefault(a[2], []).append('%d日' % int(a[0][8:10]))
    out = []
    for k, days in g.items():
        days = [(MS + days[0])] + days[1:] if days else days
        tpl = _RT.get(k, '{days}为{k}天气，采集作业受限')
        out.append(tpl.format(days='、'.join(days), k=k, month=MS))
    return '；'.join(out)
para(f"本月上报 {B['aug_n']:,} 件，全月 {W['days']} 天日均 {B['aug_n']/W['days']:.1f} 件。"
     f"其中 {anomaly_txt} 采集量明显偏低（{_reason()}）。剔除上述 {len(B['anomaly'])} 日后，"
     f"{good_days} 个正常采集日共 {good_n:,} 件，日均 {good_n/good_days:.1f} 件。"
     f"全月无明显的持续上升或下降趋势。")
pic(F3); caption(f'图3  {MS}每日案件量走势')
h2('（二）采集时段与作业时间对照')
para(f"采集员作业时间为 {_WT}，节假日不休息。数据显示，"
     f"8:00—11:00 采集 {W['am_cases']:,} 件，合 {W['am_rate']} 件/小时；"
     f"11:00—11:30 采集 {W['amhalf_cases']:,} 件，合 {W['amhalf_rate']} 件/小时；"
     f"15:00—20:00 采集 {W['pm_cases']:,} 件，合 {W['pm_rate']} 件/小时，"
     f"上午单位时间采集量约为下午的 {W['am_rate']/W['pm_rate']:.1f} 倍。"
     + (f"14:00—15:00 时段仅 {W['pm14_cases']} 件（{W['pm14_rate']} 件/小时），"
        f"与 14:00 开始作业的安排存在差异，15:00 起采集量才明显上升。"
        f"作业时间以外共 {W['off_cases']} 件，占 {W['off_rate']}%。" if not BRIEF else ""))
pic(F4); caption('图4  上报时段分布')
h2('（三）周末与工作日')
para(f"周末日均 {K['we_avg']} 件（{K['we_days']} 天），工作日日均 {K['wd_avg']} 件"
     f"（{K['wd_days']} 天），周末高出 {(K['we_avg']/K['wd_avg']-1)*100:.1f}%。"
     f"由于节假日不休息，该差异反映的是问题发生规律而非排班差异。"
     f"处置时长方面，周末中位 {K['we_dur']} 小时、工作日 {K['wd_dur']} 小时，"
     f"周末高于工作日 {(K['we_dur']/K['wd_dur']-1)*100:.0f}%。")

# 四 考核时限与处置效能
h1('四、考核时限与处置效能')
h2('（一）法定考核时限')
if BRIEF:
    para(f"平台依据《立案、处置和结案标准》为各小类设定法定考核时限，共 {STD['n_xl']} 个小类，"
         f"本月全部 {STD['covered']:,} 件案件均可对应到标准时限，覆盖率 {STD['cover_rate']}%。")
else:
    para(f"平台依据《立案、处置和结案标准》为各小类设定法定考核时限，共 {STD['n_xl']} 个小类，"
         f"本月全部 {STD['covered']:,} 件案件均可对应到标准时限，覆盖率 {STD['cover_rate']}%。"
         f"时限单位分为“工作时”（工作小时数）与“工作日”（工作日天数）两类，"
         f"以“工作时”计 {_u('工作时')} 类、以“工作日”计 {_u('工作日')} 类、"
         f"按处置环节分设两类时限 {_u('工作时+工作日')} 类。")
    para("不同小类的考核时限差异较大，街面秩序类多为紧急工作时，部件类多以工作日计，"
         "时限明显更长。因此在处置时长解读时需结合各自小类的考核时限，不宜跨小类直接横向比较。")
para("表4  案件量Top12小类的法定考核时限", size=12, font='黑体', indent=False,
     space_before=6, space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
table(['序号', '小类名称', '案件数', '法定考核时限'],
      [[i + 1, r[0], f"{r[1]:,}", r[2]] for i, r in enumerate(STD['rows'][:12])],
      widths=[1.2, 5.0, 2.4, 6.4], fontsize=10.5, center=[0, 2])
h2('（二）处置时长分布')
para(f"全平台处置时长中位 {E['dur']['p50']} 小时，P90 为 {E['dur']['p90']} 小时。"
     f"分时长段看，1 小时内办结 {E['dur_bins'][0][1]:,} 件，"
     f"1—2 小时 {E['dur_bins'][1][1]:,} 件，两者合计 {E['dur']['in4h']}% 在 4 小时内办结。")
h2('（三）部件类与事件类')
para(f"按问题类型看，事件类 {PT['事件'][1]:,} 件，处置时长中位 {PT['事件'][2]} 小时，"
     f"处置工时占比 {PT['事件'][3]}%；部件类 {PT['部件'][1]:,} 件，处置时长中位 {PT['部件'][2]} 小时，"
     f"处置工时占比 {PT['部件'][3]}%；服务事项 {PT['服务事项'][1]:,} 件，时长中位 "
     f"{PT['服务事项'][2]} 小时，工时占比 {PT['服务事项'][3]}%。"
     f"部件类案件量占比约 {PT['部件'][1]/B['dur_n']*100:.1f}%，但工时占比达 {PT['部件'][3]}%，"
     f"单件处置周期较长。")
pic(F7); caption('图5  各大类处置时长中位')
h2('（四）部门处置时长')
para(f"各部门（案件量 ≥50）处置时长中位差异明显，最短的 {E['dept'][0][0]} 为 "
     f"{E['dept'][0][2]} 小时，最长的 {E['dept'][-1][0]} 为 {E['dept'][-1][2]} 小时。"
     f"时长较长的部门主要集中在市政工程、道路设施、园林养护等专业线条。")
pic(F8); caption('图6  处置部门处置时长中位')
h2('（五）来源渠道处置时长')
para(f"12345 热线转办工单 {I['gov_by_src'][0][1]} 件，处置时长中位 {I['gov_by_src'][0][2]} 小时；"
     f"12345 电话快办 {I['gov_by_src'][1][1]} 件、{I['gov_by_src'][1][2]} 小时。"
     f"采集员上报件中位 {[r[2] for r in E['src'] if r[0] == '采集员上报'][0]} 小时，"
     f"视频上报件 {[r[2] for r in E['src'] if r[0] == '视频上报'][0]} 小时。"
     f"12345 转办件需经市民反映、12345 受理、转至平台、平台转派、处置部门处置的流转环节，"
     f"链条长于采集员直接上报" + ("；因表中无平台签收时间与转派时间字段，各环节耗时暂无法拆分。" if not BRIEF else "。"))

# 五 重复案件
h1('五、重复案件分析')
h2('（一）识别方法')
if BRIEF:
    para(f"重复案件识别以问题描述为主、坐标为确认、地址描述为参考。剔除单位默认地址："
         f"{UNIT_DESC}为本单位地址，12345 转办等无定位案件在系统中默认使用该地址，"
         f"共 {R['default_n']} 件（占 {R['default_rate']}%），避免在单位门口形成虚假的重复热点。")
else:
    para(f"重复案件识别以问题描述为主、坐标为确认、地址描述为参考。具体做法：一是提取问题描述中的"
         f"具体点位（格式为“道路名＋店铺/小区/路口等具体位置”），同一小类内点位一致的问题归为一组，"
         f"确保定位精确到店铺或具体点位而非整条街道；二是坐标相近确认，以组内案件为中心、"
         f"半径 {R['r']} 米划定圆形区域，坐标落在圆内的归并，不做链式传递，"
         f"每组直径上限 {R['r']*2} 米，实测中位直径 {R['diam_med']} 米、最大 {R['diam_max']} 米；"
         f"三是地址描述仅作参考，用于核对点位归属，不作为判定条件。")
    para(f"同时剔除单位默认地址：{UNIT_DESC} 为本单位地址，"
         f"12345 转办等无定位案件在系统中默认使用该地址，共 {R['default_n']} 件（占 {R['default_rate']}%），"
         f"予以剔除，避免在单位门口形成虚假的重复热点。")
    para(f"距离换算依据：纬度 1° 约 110,540 米（本区纬度约 {CFG.get('lat', 35.03)}°），"
         f"经度 1° 约 {R['lon_m']:,.0f} 米。采用真实距离而非网格，可避免相邻网格其实很近的边界问题。")
h2('（二）识别结果')
para(f"按半径 {R['r']} 米、同小类、点位一致且组内 ≥3 件的条件，共识别出 {R['ge3_n']:,} 组，"
     f"涉及 {R['ge3_cases']:,} 件，占全表 {R['ge3_rate']}%；其中案件数 ≥10 件且涉及 ≥5 天的"
     f"高频重复组 {R['hot_n']} 个、{R['hot_cases']:,} 件，占 {R['hot_rate']}%。"
     f"单组最大 {R['top'][0]['n']} 件，为“{R['top'][0]['xl']}”类、"
     f"位于“{R['top'][0]['label']}”，分布在 {R['top'][0]['days']} 天。"
     f"未成组的案件 {R['isolated']:,} 件，占 {R['isolated_rate']}%。")
para("表5  不同半径下的识别结果", size=12, font='黑体', indent=False, space_before=6,
     space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
NOTE = {30: '定位到具体摊位、门店门口等点位', 50: '兼顾点位与门前路段，本报告采用',
        100: '整条街道或街区的重复发生情况', 200: '较大片区的整体发生强度'}
table(['半径', '识别组数', '涉及案件', '占比', '适用解读'],
      [[f"{r[0]} 米", f"{r[3]:,}", f"{r[1]:,}", f"{r[2]}%", NOTE.get(r[0], '')] for r in R['sens']],
      widths=[1.6, 2.0, 2.2, 1.6, 6.2], fontsize=10.5, center=[0, 1, 2, 3])
pic(F5); caption('图7  高频重复点位空间分布（前40位）')
pic(F6); caption('图8  高频重复点位Top15（按问题描述点位）')
h2('（三）小类分布')
para(f"按小类统计，重复组数最多的是 {R['by_xl'][0][0]}（{R['by_xl'][0][1]} 组、"
     f"{R['by_xl'][0][2]:,} 件）、{R['by_xl'][1][0]}（{R['by_xl'][1][1]} 组）、"
     f"{R['by_xl'][2][0]}（{R['by_xl'][2][1]} 组）、{R['by_xl'][3][0]}（{R['by_xl'][3][1]} 组）、"
     f"{R['by_xl'][4][0]}（{R['by_xl'][4][1]} 组）。其中无照经营游商、店外经营属人流聚集处的"
     f"经营活动，共享单车管理、沿街晾挂属高频动态问题。")
para("表6  高频重复点位清单（前15位）", size=12, font='黑体', indent=False,
     space_before=6, space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
table(['序号', '小类', '案件', '天数', '直径(m)', '问题点位', '地址参照物'],
      [[i + 1, r['xl'], r['n'], r['days'], f"{r['diam']}",
        (r['label'] or '—')[:18], (r['poi'] or '—')[:16]]
       for i, r in enumerate(R['hot'][:15])],
      widths=[.9, 2.2, 1.0, .9, 1.4, 3.8, 3.4], fontsize=9.5,
      center=[0, 2, 3, 4])
para("表中“问题点位”为从问题描述中提取的具体位置，“地址参照物”为地址描述中的参照物名称（仅供参考）。",
     size=13)

# 六 三率
h1('六、质量三率')
para(f"超时率 {E['overtime']['rate']}%（{E['overtime']['n']}件）、"
     f"延期率 {E['delay']['rate']}%（{E['delay']['n']}件）、"
     f"返工率 {E['rework']['rate']}%（{E['rework']['n']}件）" + ("，均按平台标记字段统计。" if not BRIEF else "。"))
ova = {r[0]: r[3] for r in E['overtime']['by_dalei']}
dla = {r[0]: r[3] for r in E['delay']['by_dalei']}
rwa = {r[0]: r[3] for r in E['rework']['by_dalei']}
keys = sorted(ova, key=lambda k: -(ova.get(k, 0) + dla.get(k, 0)))
para("表7  三率按问题大类", size=12, font='黑体', indent=False, space_before=6,
     space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
table(['大类', '案件数', '超时率', '延期率', '返工率'],
      [[k, f"{[r[1] for r in E['overtime']['by_dalei'] if r[0]==k][0]:,}",
        f"{ova.get(k,0)}%", f"{dla.get(k,0)}%", f"{rwa.get(k,0)}%"] for k in keys],
      widths=[3.6, 2.6, 2.4, 2.4, 2.4], center=[1, 2, 3, 4])
para(f"超时、延期主要分布在道路交通设施、公用设施、市容环境设施等部件类线条。"
     f"按部门看，延期率较高的为 "
     f"{'、'.join(r[0]+'（'+str(r[3])+'%）' for r in sorted(E['delay']['by_dept'], key=lambda x:-x[3])[:3])}；"
     f"超时率较高的为 "
     f"{'、'.join(r[0]+'（'+str(r[3])+'%）' for r in sorted(E['overtime']['by_dept'], key=lambda x:-x[3])[:3])}。"
     f"街面秩序类超时 {[r[2] for r in E['overtime']['by_dalei'] if r[0]=='街面秩序'][0]} 件、"
     f"延期 {[r[2] for r in E['delay']['by_dalei'] if r[0]=='街面秩序'][0]} 件，"
     f"宣传广告类超时、延期均为 0。")

# 七 特征归纳
h1('七、数据特征归纳')
feats = [
    ('重复出现是本批数据最突出的特征。',
     f"半径 {R['r']} 米内同小类、点位一致的案件成组出现的共 {R['ge3_n']:,} 组、{R['ge3_cases']:,} 件"
     f"（{R['ge3_rate']}%），其中高频重复组 {R['hot_n']} 个、{R['hot_cases']:,} 件"
     f"（{R['hot_rate']}%），单组最大 {R['top'][0]['n']} 件、分布在 {R['top'][0]['days']} 天。"),
    ('问题类型高度集中。',
     f"Top10 小类覆盖 {S['top10_cover']}%，无照经营游商、道路不洁、共享单车管理三类合计 "
     f"{sum(r[1] for r in S['xiaolei'][:3]):,} 件，占 {sum(r[1] for r in S['xiaolei'][:3])/TOT*100:.1f}%。"),
    ('部件类案件量少、单件周期长。',
     f"部件类 {PT['部件'][1]:,} 件，占案件量约 {PT['部件'][1]/B['dur_n']*100:.1f}%，"
     f"处置时长中位 {PT['部件'][2]} 小时，处置工时占比 {PT['部件'][3]}%。"),
    ('市民政务渠道件流转环节较多。',
     f"12345 热线转办件处置时长中位 {I['gov_by_src'][0][2]} 小时，"
     f"需经市民反映、12345 受理、转至平台、平台转派、部门处置五个环节"
     + ("，表中无平台签收与转派时间字段。" if not BRIEF else "。")),
    ('采集时段集中于上午，14:00—15:00 时段案件量偏低。',
     f"上午 {W['am_rate']} 件/小时，下午 {W['pm_rate']} 件/小时，"
     f"相差 {W['am_rate']/W['pm_rate']:.1f} 倍；14:00—15:00 时段仅 {W['pm14_cases']} 件。"),
    ('周末案件量高于工作日。',
     f"周末日均 {K['we_avg']} 件、工作日 {K['wd_avg']} 件，周末高出 "
     f"{(K['we_avg']/K['wd_avg']-1)*100:.1f}%；周末处置时长中位 {K['we_dur']} 小时、"
     f"工作日 {K['wd_dur']} 小时。"),
]
if BRIEF:
    feats = [f for i, f in enumerate(feats) if i != 4]
for i, (t, b) in enumerate(feats, 1):
    para(f"{i}. {t}{b}", space_after=5)
para(f"专职采集员工作量方面，" + (
    f"本月出现 {I['sup_all_raw']} 个采集人员账号，其中 {I['sup_cut']} 人采集量低于 {MINSUP} 件"
    f"（合计 {I['sup_cut_cases']} 件），按非专职人员不纳入统计；" if not BRIEF else "") +
     f"{I['sup_n']} 名专职采集员共采集 {I['sup_cases']:,} 件，"
     f"人均 {I['sup_mean']} 件、中位 {I['sup_med']} 件，区间 {I['sup_min']}—{I['sup_max']} 件，"
     f"变异系数 {I['sup_cv']}%，采集量前 10 名占 {I['sup_top10_share']}%。")
pic(F9, width=13.6); caption(f"图9  专职监督员采集工作量分布（{I['sup_n']}人）")

# 八 建议
h1('八、工作建议')
recs = [
    ('对高频重复点位实行分类管理。',
     f"识别出的 {R['hot_n']} 个高频重复组均已满足同小类、点位一致、坐标相近的条件，可按具体点位建档。"
     f"点位类结合值守、疏导区设置，路段类结合巡查频次调整与集中整治；"
     f"将重复发生情况作为片区考核的一项内容。责任建议：执法各片区、市容秩序科。"),
    ('补充流转环节时间字段，量化 12345 转办件各环节耗时。',
     f"该类案件需经市民反映、12345 受理、转至平台、平台转派、部门处置五个环节，"
     f"目前仅能统计全程用时（中位 {I['gov_by_src'][0][2]} 小时）。"
     f"建议增加平台签收时间、转派时间两个字段，便于定位耗时环节。责任建议：平台服务中心。"),
    ('对部件类案件的处置周期开展专项梳理。',
     f"部件类案件处置时长中位 {PT['部件'][2]} 小时、工时占比 {PT['部件'][3]}%，"
     f"超时、延期主要集中在道路交通设施、公用设施等部件类线条。"
     f"建议对路灯、人行道、道路破损等小类逐类梳理处置流程，区分可压缩与不可压缩环节。"
     f"责任建议：市政工程部、城市照明服务中心、排水服务中心。"),
    ('核实 14:00—15:00 时段采集情况。',
     f"该时段案件量仅 {W['pm14_cases']} 件（{W['pm14_rate']} 件/小时），与 14:00 开始作业的安排存在差异，"
     f"15:00 起才明显上升。建议核实为到岗通勤、设备准备还是系统时间记录差异。"
     f"责任建议：平台服务中心、各片区采集队伍。"),
    ('按时段采集强度调整力量投放。',
     f"上午采集强度为 {W['am_rate']} 件/小时，约为下午的 {W['am_rate']/W['pm_rate']:.1f} 倍，"
     f"可结合重复点位的时段分布，在人流高峰时段加强重点点位的巡查与值守。"
     f"责任建议：各片区采集队伍、执法各片区。"),
    ('将地址描述完整率纳入采集质量记录。',
     f"本月地址描述缺失 {I['no_addr']:,} 件（{I['no_addr_rate']}%），"
     f"其中道路不洁、共享单车管理、无照经营游商三类较多。建议按人统计完整率。"
     f"责任建议：平台服务中心、各片区采集队伍。"),
    ('做好跨月挂账案件的单独统计。',
     f"本表含往月上报、经延期后截止落在本月的案件 {B['prev_n']} 条，"
     f"其中 {B['prev_profile']['delay_n']} 条办过延期、{B['prev_profile']['overtime_n']} 条被标记超时。"
     f"建议按月统计时单列，与本月新发案件分开核算；同时对 {B['unclosed']} 件未办结案件逐件落实"
     f"责任部门与办结时限。责任建议：平台服务中心。"),
]
if BRIEF:
    recs = [recs[i] for i in (0, 2, 4) if i < len(recs)]
for i, (t, b) in enumerate(recs, 1):
    para(f"{i}. {t}{b}", space_after=5)
para('')
para(f'附件：{ML}案件数据分析指标明细（见交互式分析报告）', size=12, font='楷体_GB2312',
     indent=False, space_before=10, color='595959')

for s in doc.sections:
    pf = s.footer.paragraphs[0]; pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = pf.add_run()
    for ins in ['begin', 'instrText', 'end']:
        el = OxmlElement(f'w:fld{"" if ins=="instrText" else ins.capitalize()}')
        if ins == 'instrText':
            el.set(qn('xml:space'), 'preserve'); el.text = ' PAGE '
        r._r.append(el)
    r.font.size = Pt(10.5)

_OUT = _p(CFG.get('out_docx', f'{MC}份城市管理案件数据分析报告.docx'))
try:
    doc.save(_OUT)
    print('Word 生成完成：', _OUT)
except PermissionError:
    _OUT = _OUT.replace('.docx', '_v2.docx')
    doc.save(_OUT)
    print('原文件被占用（可能已在 Word 中打开），已另存为：', _OUT)
