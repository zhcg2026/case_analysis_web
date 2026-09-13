# -*- coding: utf-8 -*-
"""考核月报图表：图1 问题来源立案占比（复合饼图）、图2 不考核案件类型及数量（柱状图）"""
import logging
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

logger = logging.getLogger(__name__)

# 中文字体：本地 Windows 与服务器容器均可用的候选，取第一个存在的
FONT_CANDIDATES = ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']


def _setup_font():
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONT_CANDIDATES:
        if name in available:
            # 直接指定字体名（rcParams 间接方式在新版 matplotlib 不可靠）
            plt.rcParams['font.family'] = name
            plt.rcParams['axes.unicode_minus'] = False
            return name
    plt.rcParams['axes.unicode_minus'] = False
    return None


def chart_source_pie(sources: dict, out_path: str):
    """图1.问题来源立案占比：主饼图（采集/视频/公众诉求）+ 公众诉求子明细"""
    import math
    font = _setup_font()
    groups = sources['groups']
    subs = sources['subs']
    total = sources['total'] or 1

    main_labels = ['采集上报', '视频上报', '公众诉求']
    main_vals = [groups.get('采集上报', 0), groups.get('视频上报', 0), groups.get('公众诉求', 0)]
    sub_colors = ['#FFC000', '#70AD47', '#FF7C80', '#4472C4', '#2F5597', '#8FAADC', '#A5A5A5']

    fig = plt.figure(figsize=(10.5, 4.4), dpi=200)
    ax1 = fig.add_axes([0.01, 0.02, 0.52, 0.96])
    ax2 = fig.add_axes([0.66, 0.08, 0.13, 0.84])

    # 主饼图：大扇区标内部，小扇区标签引到右上区并上下错开
    colors = ['#4472C4', '#ED7D31', '#7F4F24']
    wedges, _ = ax1.pie(
        main_vals, startangle=90, counterclock=False, colors=colors,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1},
    )
    small = []  # (angle, label) 小扇区
    for i, w in enumerate(wedges):
        ang = (w.theta1 + w.theta2) / 2
        pct = main_vals[i] / total * 100
        label = f'{main_labels[i]}{main_vals[i]}件\n{pct:.2f}%'
        if pct > 50:
            x, y = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            ax1.text(0.52 * x, 0.52 * y, label, ha='center', va='center',
                     fontsize=13, color='black', fontweight='bold')
        else:
            small.append((ang, label))
    # 小扇区按角度从高到低排，标签 y 依次下移，避免重叠
    small.sort(key=lambda t: -t[0])
    ly = 1.25
    for ang, label in small:
        x, y = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        ax1.annotate(label, xy=(0.99 * x, 0.99 * y), xytext=(1.35, ly),
                     ha='left', va='center', fontsize=11,
                     arrowprops={'arrowstyle': '-', 'color': '#999999', 'lw': 0.8})
        ly -= 0.5
    ax1.set(aspect='equal')
    ax1.set_xlim(-1.05, 2.6)

    # 右侧子明细：单柱堆叠 + 引线标注，标签纵向均匀分布防溢出
    if subs:
        bottoms = 0
        bar_total = sum(v for _, v in subs) or 1
        seg_info = []
        for i, (name, cnt) in enumerate(subs):
            h = cnt / bar_total
            ax2.bar(0, h, bottom=bottoms, width=0.9,
                    color=sub_colors[i % len(sub_colors)], edgecolor='white', linewidth=0.5)
            seg_info.append((name, cnt, bottoms + h / 2))
            bottoms += h
        ax2.set_xlim(-0.6, 2.2)
        ax2.set_ylim(-0.04, 1.04)
        ax2.axis('off')
        n = len(seg_info)
        for j, (name, cnt, mid) in enumerate(seg_info):
            if n > 1:
                ty = 0.05 + j * (0.9 / (n - 1))
            else:
                ty = mid
            pct = cnt / total * 100
            ax2.plot([0.48, 0.62, 0.68], [mid, ty, ty], color='#aaaaaa', lw=0.8)
            ax2.text(0.72, ty, f'{name}\n{cnt}件 {pct:.2f}%', ha='left', va='center', fontsize=10)

    fig.savefig(out_path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    logger.info(f'图1生成: {out_path} (font={font})')
    return out_path


def chart_non_assess_bar(overview: dict, out_path: str):
    """图2.不考核案件类型及数量"""
    font = _setup_font()
    o = overview
    items = [('自行处置', o['self_dispose']), ('单体垃圾', o['garbage_cnt'])]
    for name, cnt in o['special_breakdown']:
        items.append((name, cnt))
    items = [(n, c) for n, c in items if c > 0] or items

    labels = [n for n, _ in items]
    vals = [c for _, c in items]

    fig, ax = plt.subplots(figsize=(9.6, 4.6), dpi=200)
    bars = ax.bar(labels, vals, width=0.55, color='#4472C4')
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.015, str(v),
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    max_val = max(vals)
    ax.set_ylim(0, max_val * 1.1 if max_val else 1)
    ax.tick_params(axis='x', labelsize=11)
    ax.tick_params(axis='y', labelsize=10)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    logger.info(f'图2生成: {out_path} (font={font})')
    return out_path


def make_charts(data: dict, charts_dir: str):
    """生成两张图，返回 (图1路径, 图2路径)"""
    os.makedirs(charts_dir, exist_ok=True)
    batch = data['batch']
    p1 = chart_source_pie(data['sources'], os.path.join(charts_dir, f'assess_src_{batch}.png'))
    p2 = chart_non_assess_bar(data['overview'], os.path.join(charts_dir, f'assess_nonassess_{batch}.png'))
    return p1, p2
