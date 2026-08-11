"""P04 TOP1 爆款混剪 — 无字幕纯视觉节奏版

设计原则：
1. 只选 ROAS TOP 的 9X16 竖版素材
2. 每个片段只取最精华的 2-5 秒
3. 快节奏拼接，总时长控制在 20-25 秒
4. 无字幕，纯靠画面冲击力和原游戏音效
5. 0.2s 快速 fade 转场
"""
import json
import subprocess
from pathlib import Path

RECIPE_PATH = Path("d:/project_slim/output/P04_remix_videos/remix_output/remix_report.json")
OUTPUT_DIR = Path("d:/project_slim/output/P04_remix_videos/final_production")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# TOP1 爆款配方：精华片段 + 快节奏
# 每个片段: (v_num, 原始视频起始秒, 提取时长秒, 作用说明)
TOP1_CLIPS = [
    # Segment 1: HOOK — 最强视觉冲击，直接炸场
    {"v_num": "v2601523", "start": 10, "dur": 2.5, "role": "hook",
     "reason": "角色变身高潮前，张力最强"},
    
    # Segment 2: PROBLEM — 快速制造冲突
    {"v_num": "v2601375", "start": 4, "dur": 2.5, "role": "problem",
     "reason": "文字滚动揭示危机，信息密度高"},
    
    # Segment 3: ACTION — 核心玩法快闪
    {"v_num": "v2601010", "start": 10, "dur": 4, "role": "action",
     "reason": "玩法展示中段，操作最流畅"},
    
    # Segment 4: BUILDUP — 紧张感上升
    {"v_num": "v2601523", "start": 12, "dur": 3, "role": "buildup",
     "reason": "变身过程，悬念 buildup"},
    
    # Segment 5: CLIMAX — 终极爽点
    {"v_num": "v2601523", "start": 2, "dur": 3.5, "role": "climax",
     "reason": "变身完成瞬间，ROAS 44.68 的核心爽点"},
    
    # Segment 6: CTA — 炸场收尾
    {"v_num": "v2601410", "start": 0, "dur": 2.5, "role": "cta",
     "reason": "宠物展示开场，萌+炸"},
]

FADE_DURATION = 0.2  # 快速转场

def extract_clip(src_path, dst_path, start_sec, dur_sec):
    """从原始视频提取片段，保留音效，加快速 fade"""
    
    # fadein + fadeout
    fade_in = f"fade=t=in:st=0:d={FADE_DURATION}"
    fade_out = f"fade=t=out:st={dur_sec-FADE_DURATION}:d={FADE_DURATION}"
    vf = f"{fade_in},{fade_out}"
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-i", str(src_path),
        "-t", str(dur_sec),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        str(dst_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

# Load recipe to get source file paths
with open(RECIPE_PATH, "r", encoding="utf-8") as f:
    report = json.load(f)

# Build v_num -> source_file mapping from all remixes
v_to_file = {}
for r in report["remixes"]:
    for seg in r["segments"]:
        v_num = seg["source_v_num"]
        file_path = seg["source_file"]
        if v_num not in v_to_file:
            v_to_file[v_num] = file_path

# Step 1: Extract all clips
extracted = []
for i, clip in enumerate(TOP1_CLIPS):
    v_num = clip["v_num"]
    src_path = Path(v_to_file[v_num])
    dst_path = OUTPUT_DIR / f"top1_{i:02d}_{clip['role']}.mp4"
    extracted.append(dst_path)
    
    if dst_path.exists():
        dst_path.unlink()
    
    print(f"  [{clip['role']}] {src_path.name}")
    print(f"    取 {clip['start']}s-{clip['start']+clip['dur']}s ({clip['dur']}s) | {clip['reason']}")
    
    success = extract_clip(src_path, dst_path, clip["start"], clip["dur"])
    if not success:
        print(f"    ⚠️ 提取失败")

# Step 2: Concat
concat_list = OUTPUT_DIR / "top1_concat_list.txt"
concat_list.write_text("\n".join(f"file '{c}'" for c in extracted), encoding="utf-8")

final_video = OUTPUT_DIR / "P04_TOP1_Bomb_Viral_v1.mp4"
if final_video.exists():
    final_video.unlink()

print(f"\n合成 TOP1 爆款视频...")
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
    print(f"  ⚠️ 合成失败: {result.stderr[:200]}")
else:
    print(f"  ✅ 合成完成")

# Report
if final_video.exists():
    size_mb = final_video.stat().st_size / 1024 / 1024
    
    # Get info
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,codec_name",
        "-of", "default=noprint_wrappers=1",
        str(final_video)
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    streams = result.stdout.strip().split("\n")
    
    probe_cmd2 = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "csv=s=x:p=0",
        str(final_video)
    ]
    result2 = subprocess.run(probe_cmd2, capture_output=True, text=True)
    
    print(f"\n{'='*60}")
    print("🚀 P04 TOP1 爆款视频已生成")
    print(f"{'='*60}")
    print(f"文件: {final_video}")
    print(f"大小: {size_mb:.1f} MB")
    print(f"视频信息: {result2.stdout.strip()}")
    print(f"流信息: {' | '.join(streams)}")
    print()
    print("片段结构（快节奏纯视觉）：")
    for i, clip in enumerate(TOP1_CLIPS):
        print(f"  {i+1}. [{clip['role']}] {clip['dur']}s | {clip['reason']}")
    print()
    print("投放策略建议:")
    print("  - 竖版 9X16，适合 Facebook/Instagram/TikTok Reels")
    print("  - 20-25秒黄金时长，完播率最优")
    print("  - 前3秒即高潮，3秒留存率最大化")
    print("  - 无字幕 → 全球化投放无需翻译")
    print("  - 原游戏音效 → 玩家认同感强")
    print("  - 建议同时测 15秒/30秒剪辑版")
