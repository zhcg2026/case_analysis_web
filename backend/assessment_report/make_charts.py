# -*- coding: utf-8 -*-
"""考核月报两张图：统一的紧凑环形概览及横向条形明细。"""
import logging
import os
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

logger = logging.getLogger(__name__)
FONT_CANDIDATES = ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
COLORS = ('#386BA5', '#CF8840', '#438C81')


def _setup_font():
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONT_CANDIDATES:
        if name in available:
            plt.rcParams['font.family'] = name
            plt.rcParams['axes.unicode_minus'] = False
            return name
    plt.rcParams['axes.unicode_minus'] = False
    return None


def _compact_chart(groups, rows, total, center_label, name_label, empty_label, out_path):
    """图例位于环形下，明细靠中；图名由Word输出，避免图片内重复占高。"""
    _setup_font()
    palette = dict(zip(groups, COLORS))
    visible = [dict(r) for r in rows if r['count'] > 0]
    columns = 1 if len(visible) <= 10 else 2
    per_col = max(1, (len(visible) + columns - 1) // columns)
    panels = [visible[i * per_col:(i + 1) * per_col] for i in range(columns)]
    wrap_width = 9 if columns == 1 else 7
    panel_rows = []
    for items in panels:
        prepared = []
        for row in items:
            label = textwrap.fill(str(row['name']), width=wrap_width)
            units = max(1, (label.count('\n') + 1) * .70)
            prepared.append((row, label, units))
        panel_rows.append(prepared)
    extent = max(7, *(sum(r[2] for r in panel) for panel in panel_rows))
    height = max(3.15, extent * .36 + .63)
    fig = plt.figure(figsize=(12, height), dpi=220, facecolor='white')
    try:
        if not total:
            fig.text(.5, .5, empty_label, ha='center', va='center', fontsize=18, color='#596B79')
        else:
            ring = fig.add_axes([.06, .23, .23, .70])
            ring.pie(list(groups.values()), colors=COLORS, startangle=90, counterclock=False,
                     wedgeprops={'width': .23, 'edgecolor': 'white', 'linewidth': 2})
            ring.text(0, .14, f'{total:,}', ha='center', va='center', fontsize=28,
                      fontweight='bold', color='#24374B')
            ring.text(0, -.23, center_label, ha='center', fontsize=13, color='#647582')
            ring.axis('equal')
            for i, (name, count) in enumerate(groups.items()):
                fig.text(.04 + i * .105, .15, '● ' + name, color=COLORS[i], fontsize=13)
                fig.text(.04 + i * .105, .085, f'{count/total:.1%}', color='#596B79', fontsize=13)
            maximum = max((r['count'] for r in visible), default=1)
            for column, items in enumerate(panel_rows):
                left, width = (.34, .62) if columns == 1 else (.34 + column * .34, .28)
                ax = fig.add_axes([left, .20, width, .68])
                ax.set(xlim=(0, 1), ylim=(-.55, extent-.45))
                ax.axis('off')
                size = 16 if columns == 1 else 11
                cursor = extent - 1
                for row, label, units in items:
                    y = cursor - (units - 1) / 2
                    ax.text(.24, y, label, ha='right', va='center', fontsize=size,
                            linespacing=1.05, color='#344656')
                    ax.barh(y, .44, left=.26, height=.35, color='#EFF3F6')
                    ax.barh(y, row['count']/maximum*.44, left=.26, height=.35,
                            color=palette[row['group']])
                    ax.text(.82, y, f"{row['count']:,}", ha='right', va='center',
                            fontsize=size, color='#24374B')
                    ax.text(.99, y, f"{row['count']/total:.2%}", ha='right', va='center',
                            fontsize=size, color='#596B79')
                    cursor -= units
                for x, title in [(.24, name_label), (.82, '件数'), (.99, '占总量')]:
                    ax.text(x, extent-.45, title, ha='right', fontsize=14 if columns == 1 else 11,
                            color='#73818E')
        fig.savefig(out_path, facecolor='white')
    finally:
        plt.close(fig)
    return out_path


def chart_source_pie(sources: dict, out_path: str):
    """图1：考核受理来源，三类概览和各渠道明细同用受理总数作分母。"""
    order = ('采集上报', '视频上报', '公众诉求')
    groups = {g: sources['groups'].get(g, 0) for g in order}
    rows = sorted(sources['channels'], key=lambda r: (order.index(r['group']), -r['count']))
    return _compact_chart(groups, rows, sources['total'], '考核受理 / 件', '渠道',
                          '本月无考核受理案件', out_path)


def chart_non_assess_bar(overview: dict, out_path: str):
    """图2：沿用原不考核数据，专项合计只在环形中出现，条形只列专项明细。"""
    special = overview['special_breakdown']
    groups = {'自行处置': overview['self_dispose'], '单体垃圾': overview['garbage_cnt'],
              '专项采集': sum(count for _, count in special)}
    rows = [{'name': name, 'group': name, 'count': groups[name]}
            for name in ('自行处置', '单体垃圾')]
    rows += [{'name': '专项：' + str(name), 'group': '专项采集', 'count': count}
             for name, count in special]
    return _compact_chart(groups, rows, sum(groups.values()), '不考核案件 / 件', '类型',
                          '本月无不考核案件', out_path)


def make_charts(data: dict, charts_dir: str):
    """生成两张图，返回 (图1路径, 图2路径)。"""
    os.makedirs(charts_dir, exist_ok=True)
    batch = data['batch']
    p1 = chart_source_pie(data['sources'], os.path.join(charts_dir, f'assess_src_{batch}.png'))
    p2 = chart_non_assess_bar(data['overview'], os.path.join(charts_dir, f'assess_nonassess_{batch}.png'))
    return p1, p2
