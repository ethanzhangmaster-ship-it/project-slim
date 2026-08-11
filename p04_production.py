"""P04 Production Pipeline — 从原始视频提取带音效片段，加字幕后合成成品

处理步骤：
1. 读取 remix_recipe 获取原始视频路径和提取时间段
2. 从原始视频提取片段（保留音效）+ 加字幕 + fade 转场
3. concat 拼接音视频
4. 输出最终可投放视频
"""
import json
import subprocess
from pathlib import Path

RECIPE_PATH = Path("d:/project_slim/output/P04_remix_videos/remix_output/remix_report.json")
OUTPUT_DIR = Path("d:/project_slim/output/P04_remix_videos/final_production")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = OUTPUT_DIR / "simhei.ttf"

# 英文字幕文案（对应5个DNA片段）
SUBTITLES = [
    ("Can You Spot the Fake?", True),
    ("Fakes Are Infiltrating the Witch Squad!", False),
    ("Swipe to Merge, Unlock Super Witch", False),
    ("ULTIMATE TRANSFORMATION!", True),
    ("Download Now and Start Merging!", True),
]

FADE_DURATION = 0.4  # 秒

def extract_with_subtitle(src_path, dst_path, start_sec, dur_sec, text, is_big=False):
    """从原始视频提取片段，保留音效，加字幕和 fade"""
    
    fontsize = 64 if is_big else 52
    y_pos = "h*0.72" if is_big else "h*0.78"
    
    # ffmpeg filter 中: 空格转义为 \空格, 逗号转义为 \逗号
    safe_text = text.replace(" ", "\\ ").replace(",", "\,")
    drawtext = (
        f"drawtext=fontfile={FONT_PATH.name}:"
        f"text={safe_text}:"
        f"fontsize={fontsize}:"
        f"fontcolor=white:"
        f"borderw=5:bordercolor=black@0.8:"
        f"shadowx=3:shadowy=3:shadowcolor=black@0.5:"
        f"x=(w-text_w)/2:y={y_pos}"
    )
    
    # fadein + fadeout (视频)
    fade_in = f"fade=t=in:st=0:d={FADE_DURATION}"
    fade_out = f"fade=t=out:st={dur_sec-FADE_DURATION}:d={FADE_DURATION}"
    vf = f"{fade_in},{fade_out},{drawtext}"
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-i", str(src_path),
        "-t", str(dur_sec),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",  # 重新编码音频确保格式统一
        str(dst_path)
    ]
    
    print(f"  提取 {start_sec}s-{start_sec+dur_sec}s: {Path(src_path).name}")
    print(f"    字幕: {text}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(OUTPUT_DIR))
    if result.returncode != 0:
        print(f"    ⚠️ 错误: {result.stderr[:400]}")
        return False
    return True

# Load recipe
with open(RECIPE_PATH, "r", encoding="utf-8") as f:
    report = json.load(f)

# Find remix_9X16_01_top
target_name = "remix_9X16_01_top"
recipe = None
for r in report["remixes"]:
    if r["name"] == target_name:
        recipe = r
        break

if not recipe:
    print(f"找不到配方: {target_name}")
    exit(1)

# Step 1: 从原始视频提取带字幕和音效的片段
processed_clips = []
for i, seg in enumerate(recipe["segments"]):
    src = Path(seg["source_file"])
    dst = OUTPUT_DIR / f"proc_{i:02d}.mp4"
    processed_clips.append(dst)
    
    if dst.exists():
        dst.unlink()
    
    text, is_big = SUBTITLES[i]
    success = extract_with_subtitle(
        src, dst,
        seg["extract_start_sec"],
        seg["extract_duration_sec"],
        text, is_big
    )
    if not success:
        print(f"    处理失败，跳过此片段")

# Step 2: concat 所有处理后的片段
concat_list = OUTPUT_DIR / "concat_list.txt"
concat_list.write_text("\n".join(f"file '{c}'" for c in processed_clips), encoding="utf-8")

final_video = OUTPUT_DIR / "P04_Remix_9X16_Final_v1.mp4"
if final_video.exists():
    final_video.unlink()

print(f"\n拼接视频片段（含原音效）...")
cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", str(concat_list),
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "aac", "-b:a", "192k",
    str(final_video)
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"  ⚠️ 拼接失败: {result.stderr[:200]}")
else:
    print(f"  ✅ 拼接完成")

# Report
if final_video.exists():
    size_mb = final_video.stat().st_size / 1024 / 1024
    print(f"\n{'='*60}")
    print("✅ 成品视频已生成")
    print(f"{'='*60}")
    print(f"文件: {final_video}")
    print(f"大小: {size_mb:.1f} MB")
    
    # Get stream info
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,codec_name",
        "-of", "default=noprint_wrappers=1",
        str(final_video)
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    streams = result.stdout.strip().split("\n")
    print(f"流信息: {' | '.join(streams)}")
    
    probe_cmd2 = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "csv=s=x:p=0",
        str(final_video)
    ]
    result2 = subprocess.run(probe_cmd2, capture_output=True, text=True)
    print(f"视频信息: {result2.stdout.strip()}")
    print()
    print("字幕内容:")
    for text, _ in SUBTITLES:
        print(f"  • {text}")
    print()
    print("音效来源: 保留原视频游戏音效")
