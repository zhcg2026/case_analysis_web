"""
文字动画视频演示 - 使用imageio直接写入
"""

import os
import io
import tempfile

import imageio
import imageio_ffmpeg

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from PIL import Image
import numpy as np

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False


def create_demo_video(output_path=None):
    """创建演示视频"""
    frames = []
    fps = 24

    # 场景1: 标题渐入 (0-2秒)
    print("场景1: 标题渐入...")
    for i in range(fps * 2):
        alpha = min(1.0, i / (fps * 1.5))
        frames.append(create_title_frame("2026年3月案件数据分析报告", alpha))

    # 场景2: 数字滚动 (2-5秒)
    print("场景2: 数字滚动...")
    total_frames = fps * 3
    for i in range(total_frames):
        t = i / total_frames
        if t < 0.7:
            num = int(1234 * (t / 0.7) ** 0.5)
        else:
            num = 1234
        frames.append(create_number_frame("案件总量", num, 1234))

    # 场景3: 数据卡片 (5-9秒)
    print("场景3: 数据卡片...")
    cards = [
        ("结案率", "96.5%", "#27ae60"),
        ("处理部门", "28个", "#3498db"),
        ("问题类型", "15类", "#e74c3c"),
    ]
    for card_idx, (title, value, color) in enumerate(cards):
        for i in range(fps):
            t = min(1.0, i / (fps * 0.5))
            frames.append(create_cards_frame(cards[:card_idx], (title, value, color), t))

    # 场景4: 关键发现 (9-14秒)
    print("场景4: 关键发现...")
    findings = [
        "案件总量环比增长12.3%",
        "结案率提升至96.5%",
        "东片区案件占比最高",
    ]
    for finding_idx, finding in enumerate(findings):
        for i in range(int(fps * 1.5)):
            t = min(1.0, i / (fps * 0.7))
            frames.append(create_findings_frame(findings[:finding_idx], finding, t))

    # 场景5: 结尾 (14-16秒)
    print("场景5: 结尾...")
    for i in range(fps * 2):
        frames.append(create_conclusion_frame())

    # 用imageio写入视频
    print("写入视频...")
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.mp4')

    writer = imageio.get_writer(
        output_path,
        fps=fps,
        codec='libx264',
        quality=8,
        output_params=['-pix_fmt', 'yuv420p']
    )

    for frame in frames:
        writer.append_data(frame)

    writer.close()

    size = os.path.getsize(output_path)
    print(f"完成: {output_path}")
    print(f"大小: {size:,} bytes ({size/1024/1024:.1f} MB)")
    return output_path


def create_title_frame(title, alpha):
    fig = Figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_facecolor('#1a365d')

    ax.text(0.5, 0.5, title, fontsize=38, color=(1, 1, 1, alpha),
            ha='center', va='center', fontweight='bold')
    ax.text(0.5, 0.32, '数据分析报告', fontsize=24, color=(0.9, 0.9, 0.9, alpha*0.8),
            ha='center')

    ax.axis('off')
    return fig_to_array(fig)


def create_number_frame(label, current, target):
    fig = Figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_facecolor('#1a365d')

    ax.text(0.5, 0.6, label, fontsize=26, color='#90cdf4', ha='center')
    ax.text(0.5, 0.4, f'{current:,}', fontsize=64, color='white',
            ha='center', va='center', fontweight='bold')

    progress = current / target if target > 0 else 0
    ax.add_patch(plt.Rectangle((0.25, 0.25), 0.5 * progress, 0.02,
                               facecolor='#4299e1', transform=ax.transAxes))
    ax.add_patch(plt.Rectangle((0.25, 0.25), 0.5, 0.02,
                               fill=False, edgecolor='#4299e1', linewidth=2, transform=ax.transAxes))

    ax.axis('off')
    return fig_to_array(fig)


def create_cards_frame(existing_cards, new_card, progress):
    fig = Figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_facecolor('#1a365d')

    ax.text(0.5, 0.85, '核心数据指标', fontsize=30, color='white',
            ha='center', fontweight='bold')

    positions = [(0.25, 0.5), (0.5, 0.5), (0.75, 0.5)]

    for i, (title, value, color) in enumerate(existing_cards):
        draw_card(ax, positions[i][0], positions[i][1], title, value, color, 1.0)

    if new_card:
        title, value, color = new_card
        idx = len(existing_cards)
        draw_card(ax, positions[idx][0], positions[idx][1], title, value, color, progress)

    ax.axis('off')
    return fig_to_array(fig)


def draw_card(ax, x, y, title, value, color, alpha):
    r, g, b = hex_to_rgb(color)
    rect = plt.Rectangle((x-0.1, y-0.12), 0.2, 0.24,
                          facecolor=(r, g, b, alpha*0.25),
                          edgecolor=(r, g, b, alpha),
                          linewidth=3, transform=ax.transAxes)
    ax.add_patch(rect)

    ax.text(x, y+0.04, title, fontsize=16, color=(1, 1, 1, alpha), ha='center')
    ax.text(x, y-0.04, value, fontsize=28, color=(r, g, b, alpha),
            ha='center', fontweight='bold')


def create_findings_frame(existing_findings, new_finding, progress):
    fig = Figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_facecolor('#1a365d')

    ax.text(0.5, 0.85, '关键发现', fontsize=30, color='white', ha='center', fontweight='bold')

    colors = ['#e74c3c', '#27ae60', '#3498db']
    y = 0.65

    for i, finding in enumerate(existing_findings):
        ax.text(0.15, y, f'{i+1}.', fontsize=20, color=colors[i], fontweight='bold')
        ax.text(0.2, y, finding, fontsize=18, color='white')
        y -= 0.13

    if new_finding:
        idx = len(existing_findings)
        x_offset = 0.2 * (1 - progress)
        ax.text(0.15 + x_offset, y, f'{idx+1}.', fontsize=20, color=colors[idx],
                fontweight='bold', alpha=progress)
        ax.text(0.2 + x_offset, y, new_finding, fontsize=18, color='white', alpha=progress)

    ax.axis('off')
    return fig_to_array(fig)


def create_conclusion_frame():
    fig = Figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_facecolor('#1a365d')

    ax.text(0.5, 0.55, '报告结束', fontsize=44, color='white', ha='center', fontweight='bold')
    ax.text(0.5, 0.35, '感谢观看', fontsize=26, color='#90cdf4', ha='center')

    ax.axis('off')
    return fig_to_array(fig)


def fig_to_array(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    arr = np.array(Image.open(buf))[:, :, :3]
    plt.close(fig)
    return arr


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16)/255 for i in (0, 2, 4))


if __name__ == '__main__':
    output = create_demo_video()
    if output:
        print(f"\n视频路径: {output}")