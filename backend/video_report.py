"""
视频报告生成模块 - 增强版（带语音配音）
"""

import os
import io
import base64
import tempfile
import asyncio
import subprocess
import math
import re

import numpy as np
from PIL import Image

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 视频分辨率
WIDTH = 1280
HEIGHT = 720


def convert_date_format(text):
    """将日期格式转换为可朗读格式
    例如: '202603' -> '2026年3月', '202603与202602' -> '2026年3月与2026年2月'
    """
    # 匹配 YYYYMM 格式（6位数字）
    def replace_month(match):
        full = match.group(0)
        year = full[:4]
        month = full[4:6].lstrip('0') or '0'
        return f"{year}年{month}月"

    # 替换所有YYYYMM格式
    text = re.sub(r'\d{6}', replace_month, text)
    return text


async def generate_audio(text, output_path, voice='zh-CN-XiaoxiaoNeural'):
    """使用edge-tts生成语音"""
    import edge_tts
    # 转换日期格式以便正确朗读
    text = convert_date_format(text)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path


def get_audio_duration(audio_path, fallback_text=None):
    """获取音频时长（秒）"""
    try:
        # 使用ffprobe获取时长
        try:
            import imageio_ffmpeg
            ffprobe_exe = imageio_ffmpeg.get_ffmpeg_exe().replace('ffmpeg', 'ffprobe')
        except:
            ffprobe_exe = 'ffprobe'

        result = subprocess.run(
            [ffprobe_exe, '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except:
        pass
    # 估算：中文平均每秒4个字
    if fallback_text:
        return max(2.0, len(fallback_text) / 4)
    return 3.0  # 默认时长


class VideoReportGenerator:
    def __init__(self):
        self.fps = 24
        self.voice = 'zh-CN-XiaoxiaoNeural'

    def generate_video(self, report_title, charts_data, insights=None, output_path=None):
        """生成带语音的视频报告"""
        temp_dir = tempfile.mkdtemp()

        try:
            # 收集所有帧和对应的音频
            frames_data = []  # [(ftype, display_title, audio_text, duration)]
            audio_files = []  # 生成的音频文件列表

            summary = insights.get('summary', '') if insights else ''
            key_findings = insights.get('key_findings', []) if insights else []
            chart_insights = insights.get('chart_insights', {}) if insights else {}  # 图表分析结论

            # 1. 封面帧 - 添加欢迎语和标题朗读
            print(f"[视频] 生成封面: {report_title}")
            welcome_text = f"欢迎观看数据分析报告。{report_title}"
            frames_data.append(('cover', report_title, welcome_text, 5.0))

            # 2. 数据概览（如果有）
            if summary:
                print("[视频] 生成概览...")
                frames_data.append(('summary', '数据概览', summary, max(4.0, len(summary) / 4)))

            # 3. 关键发现（带语音）
            if key_findings:
                print(f"[视频] 生成{len(key_findings)}个关键发现...")
                for i, finding in enumerate(key_findings[:5]):
                    frames_data.append(('finding', f'关键发现 {i+1}', finding, max(3.0, len(finding) / 4)))

            # 4. 图表展示（带分析结论朗读）
            if charts_data:
                print(f"[视频] 生成{len(charts_data)}个图表页...")
                for name, b64 in charts_data:
                    try:
                        img = self._decode_chart(b64)
                        if img is not None:
                            # 获取图表对应的分析结论
                            chart_text = chart_insights.get(name, '')
                            print(f"[视频] 图表'{name}'分析: {chart_text[:50] if chart_text else '无'}...")
                            if not chart_text:
                                # 根据图表名称生成简单描述
                                chart_display = name
                                if len(name) > 3 and name[2] == '_':
                                    chart_display = name[3:].replace('_', ' ')
                                chart_text = f"接下来展示{chart_display}图表。"
                            frames_data.append(('chart', name, chart_text, max(4.0, len(chart_text) / 4)))
                    except Exception as e:
                        print(f"[视频] 图表{name}失败: {e}")

            # 5. 结尾
            print("[视频] 生成结尾...")
            frames_data.append(('end', '报告结束', '感谢观看本次数据分析报告，报告结束。', 3.0))

            # 生成所有音频文件
            print("[视频] 生成语音配音...")
            for idx, (ftype, title, audio_text, duration) in enumerate(frames_data):
                if audio_text:
                    audio_path = os.path.join(temp_dir, f'audio_{idx}.mp3')
                    try:
                        asyncio.run(generate_audio(audio_text, audio_path, self.voice))
                        audio_files.append((idx, audio_path))
                        actual_duration = get_audio_duration(audio_path, audio_text)
                        # 更新实际时长
                        frames_data[idx] = (ftype, title, audio_text, actual_duration)
                        print(f"[视频] 语音{idx}: {audio_text[:30]}... ({actual_duration:.1f}s)")
                    except Exception as e:
                        print(f"[视频] 语音生成失败: {e}")
                        import traceback
                        traceback.print_exc()
                        audio_files.append((idx, None))

            # 生成所有帧图像
            print("[视频] 生成视频帧...")
            all_frames = []
            chart_images = {}  # 缓存解码的图表

            # 先解码所有图表
            for name, b64 in (charts_data or []):
                try:
                    chart_images[name] = self._decode_chart(b64)
                except:
                    pass

            for idx, (ftype, title, audio_text, duration) in enumerate(frames_data):
                n_frames = int(self.fps * duration)
                # 对于图表帧，用标题（图表名称）查找图像
                img = chart_images.get(title) if ftype == 'chart' else None
                frame_img = self._create_frame(ftype, title, audio_text, img)
                for _ in range(n_frames):
                    all_frames.append(frame_img)

            print(f"[视频] 共{len(all_frames)}帧")

            # 合成视频
            if output_path is None:
                output_path = tempfile.mktemp(suffix='.mp4')

            # 先生成无音频视频
            video_only_path = os.path.join(temp_dir, 'video_only.mp4')
            self._write_frames_to_video(all_frames, video_only_path)

            # 合成音频
            if audio_files:
                print("[视频] 合成音频...")
                final_path = self._merge_audio_video(
                    video_only_path, audio_files, frames_data, output_path
                )
            else:
                # 无音频，直接复制
                import shutil
                shutil.copy(video_only_path, output_path)

            print(f"[视频] 完成: {output_path}, 大小: {os.path.getsize(output_path)}")
            return output_path

        except Exception as e:
            print(f"[视频] 错误: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _create_frame(self, frame_type, title='', text='', chart_img=None):
        """创建单帧图像 - 增强视觉效果"""
        fig = Figure(figsize=(WIDTH/100, HEIGHT/100), dpi=100, facecolor='#0a1628')
        ax = fig.add_subplot(111)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_facecolor('#0a1628')

        if frame_type == 'cover':
            # 封面 - 渐变背景效果
            # 添加装饰线条
            ax.plot([0, 1], [0.7, 0.7], color='#3498db', linewidth=2, alpha=0.6)
            ax.plot([0, 1], [0.3, 0.3], color='#3498db', linewidth=2, alpha=0.6)

            # 主标题（副标题）
            ax.text(0.5, 0.55, title[:40], fontsize=28, color='#ffffff',
                    ha='center', va='center', fontweight='bold',
                    family='Microsoft YaHei')

            # 副标题
            ax.text(0.5, 0.38, '数据分析报告', fontsize=16, color='#88ccff',
                    ha='center', va='center', family='Microsoft YaHei')

            # 添加角标装饰
            ax.text(0.05, 0.95, '◆', fontsize=14, color='#3498db', va='top')
            ax.text(0.95, 0.95, '◆', fontsize=14, color='#3498db', va='top', ha='right')

        elif frame_type == 'summary':
            # 数据概览页
            ax.text(0.5, 0.88, '数据概览', fontsize=24, color='#ffffff',
                    ha='center', fontweight='bold', family='Microsoft YaHei')

            # 分隔线
            ax.plot([0.2, 0.8], [0.78, 0.78], color='#3498db', linewidth=1)

            # 内容区域
            lines = text.split('\n')[:5]
            y = 0.6
            for line in lines:
                if line.strip():
                    ax.text(0.5, y, line[:50], fontsize=18, color='#e0e0e0',
                            ha='center', family='Microsoft YaHei')
                    y -= 0.12

        elif frame_type == 'finding':
            # 关键发现页
            ax.text(0.5, 0.88, title, fontsize=24, color='#ffffff',
                    ha='center', fontweight='bold', family='Microsoft YaHei')

            # 发现内容框
            rect_y = 0.35
            ax.add_patch(plt.Rectangle((0.15, rect_y), 0.7, 0.35,
                         facecolor='#1a3a5c', edgecolor='#3498db',
                         linewidth=2, transform=ax.transAxes))

            # 发现文本
            ax.text(0.5, 0.52, text[:60], fontsize=20, color='#90caf9',
                    ha='center', va='center', family='Microsoft YaHei')

        elif frame_type == 'chart':
            # 图表展示页
            # 标题
            display_title = title
            if len(title) > 3 and title[2] == '_':
                display_title = title[3:].replace('_', ' ')

            ax.text(0.5, 0.92, display_title[:30], fontsize=20, color='#ffffff',
                    ha='center', va='top', fontweight='bold', family='Microsoft YaHei')

            # 图表区域
            if chart_img is not None:
                ax.imshow(chart_img, extent=[0.08, 0.92, 0.08, 0.82], aspect='auto')

        elif frame_type == 'end':
            # 结尾页
            ax.text(0.5, 0.55, '报告结束', fontsize=32, color='#ffffff',
                    ha='center', fontweight='bold', family='Microsoft YaHei')
            ax.text(0.5, 0.35, '感谢观看', fontsize=18, color='#88ccff',
                    ha='center', family='Microsoft YaHei')

        ax.axis('off')
        return self._fig_to_array(fig)

    def _fig_to_array(self, fig):
        """转换Figure为numpy数组"""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=80, bbox_inches='tight',
                    pad_inches=0, facecolor=fig.get_facecolor())
        buf.seek(0)
        img = Image.open(buf)
        img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
        arr = np.array(img)
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        plt.close(fig)
        return arr

    def _decode_chart(self, b64):
        """解码base64图表"""
        try:
            data = base64.b64decode(b64)
            img = Image.open(io.BytesIO(data))
            img.thumbnail((WIDTH - 100, HEIGHT - 100))
            return np.array(img)
        except:
            return None

    def _write_frames_to_video(self, frames, output_path):
        """将帧写入视频文件"""
        import imageio
        writer = imageio.get_writer(output_path, fps=self.fps,
                                     codec='libx264', quality=8)
        for frame in frames:
            writer.append_data(frame)
        writer.close()

    def _merge_audio_video(self, video_path, audio_files, frames_data, output_path):
        """合并音频和视频"""
        # 获取ffmpeg路径
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except:
            ffmpeg_exe = 'ffmpeg'  # 回退到系统路径

        temp_dir = os.path.dirname(video_path)

        # 计算每段音频的延迟时间，构建静音+音频的序列
        audio_segments = []
        cumulative_time = 0.0

        for idx, (ftype, title, audio_text, duration) in enumerate(frames_data):
            # 找对应的音频文件
            audio_path = None
            for a_idx, a_path in audio_files:
                if a_idx == idx and a_path and os.path.exists(a_path):
                    audio_path = a_path
                    break

            if audio_path:
                audio_segments.append((audio_path, cumulative_time))
            cumulative_time += duration

        if not audio_segments:
            import shutil
            shutil.copy(video_path, output_path)
            return output_path

        # 使用ffmpeg合成音频
        try:
            # 方法：先创建带静音的完整音轨，然后把各段音频放到正确位置
            # 使用apad填充静音，然后逐段叠加音频

            filter_parts = []
            input_args = ['-i', video_path]

            # 第一段音频作为基础
            first_audio, first_delay = audio_segments[0]
            input_args.extend(['-i', first_audio])

            if first_delay > 0:
                # 前面需要静音
                filter_parts.append(f'[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,adelay={int(first_delay*1000)}|{int(first_delay*1000)}[a0]')
            else:
                filter_parts.append(f'[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[a0]')

            # 后续音频依次叠加（统一响度）
            for i, (audio_path, delay_sec) in enumerate(audio_segments[1:], start=1):
                input_args.extend(['-i', audio_path])
                delay_ms = int(delay_sec * 1000)
                filter_parts.append(f'[{i+1}:a]loudnorm=I=-16:TP=-1.5:LRA=11,adelay={delay_ms}|{delay_ms}[a{i}]')

            # 使用amix但带normalize=0避免音量变化
            mix_inputs = ''.join([f'[a{i}]' for i in range(len(audio_segments))])
            filter_parts.append(f'{mix_inputs}amix=inputs={len(audio_segments)}:duration=longest:normalize=0[aout]')

            filter_complex = ';'.join(filter_parts)

            cmd = [ffmpeg_exe, '-y']
            cmd.extend(input_args)
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '0:v', '-map', '[aout]',
                '-c:v', 'copy', '-c:a', 'aac',
                '-shortest',
                output_path
            ])

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[视频] ffmpeg错误: {result.stderr}")
                import shutil
                shutil.copy(video_path, output_path)
            return output_path

        except Exception as e:
            print(f"[视频] 合成失败: {e}")
            import shutil
            shutil.copy(video_path, output_path)
            return output_path


if __name__ == '__main__':
    gen = VideoReportGenerator()
    out = gen.generate_video(
        '202603与202602对比分析报告',
        [],
        {'summary': '本次分析对比了两个月的数据变化趋势', 'key_findings': ['案件总量环比增长15%', '市容环境类问题占比最高']}
    )
    print(f"输出: {out}, 大小: {os.path.getsize(out)}")