"""视频内容深度分析 — 找出真正有视觉冲击力的秒段"""
import subprocess
import re
from pathlib import Path

VIDEO_PATH = Path("d:/project_slim/output/P04_remix_videos/广告视频/P4-v2601523-mg-2d-juesezhanshi-en-16s-9X16.mp4")
OUTPUT_DIR = Path("d:/project_slim/output/video_analysis/v2601523")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print(f"分析视频: {VIDEO_PATH.name}")
print("=" * 60)

# 1. 基础信息
print(f"\n[基础信息]")
print(f"  文件: {VIDEO_PATH.name}")
print(f"  大小: {VIDEO_PATH.stat().st_size / 1024 / 1024:.1f} MB")

# 2. 场景变化检测
print(f"\n[场景变化检测] — 检测画面切换点...")
scene_result = subprocess.run([
    "ffmpeg", "-i", str(VIDEO_PATH),
    "-filter:v", "select='gt(scene,0.3)',showinfo",
    "-f", "null", "-"
], capture_output=True, text=True)

scenes = []
for line in scene_result.stderr.split("\n"):
    if "pts_time:" in line:
        try:
            time_str = line.split("pts_time:")[1].split(" ")[0]
            scenes.append(float(time_str))
        except:
            pass

print(f"  检测到 {len(scenes)} 个场景切换点:")
for t in scenes[:15]:
    print(f"    {t:.2f}s")

# 3. 提取每秒关键帧
print(f"\n[提取关键帧] — 每0.5秒一帧 (共约32帧)...")
duration = 16.0
for i in range(0, int(duration * 2) + 1):
    sec = i * 0.5
    frame_path = OUTPUT_DIR / f"frame_{i:02d}_{sec:04.1f}s.jpg"
    if frame_path.exists():
        continue
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(sec),
        "-i", str(VIDEO_PATH),
        "-vframes", "1", "-q:v", "2",
        str(frame_path)
    ], capture_output=True)

print(f"  关键帧已保存到: {OUTPUT_DIR}")

# 4. 音频波形分析（简化版：检测每秒最大音量）
print(f"\n[音频波形分析] — 检测音量变化...")
audio_result = subprocess.run([
    "ffmpeg", "-i", str(VIDEO_PATH),
    "-af", "volumedetect",
    "-f", "null", "-"
], capture_output=True, text=True)

max_vol = None
mean_vol = None
for line in audio_result.stderr.split("\n"):
    if "max_volume" in line:
        max_vol = line.split(":")[-1].strip()
    if "mean_volume" in line:
        mean_vol = line.split(":")[-1].strip()

if max_vol:
    print(f"  最大音量: {max_vol}")
if mean_vol:
    print(f"  平均音量: {mean_vol}")

# 5. 画面运动强度分析（用scene=0.05检测所有细微变化）
print(f"\n[画面运动分析] — 检测所有画面变化...")
motion_result = subprocess.run([
    "ffmpeg", "-i", str(VIDEO_PATH),
    "-filter:v", "select='gt(scene,0.05)',showinfo",
    "-f", "null", "-"
], capture_output=True, text=True)

motion_events = []
for line in motion_result.stderr.split("\n"):
    if "pts_time:" in line:
        try:
            time_str = line.split("pts_time:")[1].split(" ")[0]
            motion_events.append(float(time_str))
        except:
            pass

print(f"  检测到 {len(motion_events)} 个画面变化事件")

# 6. 生成分析报告
print(f"\n{'='*60}")
print("分析完成!")
print(f"{'='*60}")
print(f"\n关键帧路径: {OUTPUT_DIR}")
print(f"  frame_00_0.0s.jpg  ~  frame_32_16.0s.jpg")
print(f"\n你可以打开这些图片，看看每0.5秒的画面内容:")
print(f"  - 哪些秒段画面最精彩？")
print(f"  - 哪些秒段是静态/无聊的？")
print(f"  - 变身高潮发生在第几秒？")
print(f"\n场景切换点 (画面大变化):")
for t in scenes[:10]:
    print(f"  {t:.1f}s")
print(f"\n请查看关键帧后告诉我:")
print(f"  1. 哪几秒是变身高潮？")
print(f"  2. 哪几秒是静态/无聊的？")
print(f"  3. 整段视频里最炸的3秒是哪3秒？")
