"""P04 Creative Remix Engine — 基于投放数据自动重组高 ROI 视频

修复：按画面比例（ratio）分组混剪，避免竖版/横版混用导致画面压扁
"""
import json
import csv
import subprocess
import re
import sys
from pathlib import Path
from collections import defaultdict

# V3.9.1: reuse the single ClipResolver so source timestamps are never guessed.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_remix_engine.production.clip_resolver import resolve_clip

BASE = Path("d:/project_slim/project_slim/output/video_intelligence/p04")
ADJUST_REPORT = BASE / "final_adjust_material_report.csv"
SOURCE_DIR = Path("d:/project_slim/output/P04_remix_videos/广告视频")
OUTPUT_DIR = Path("d:/project_slim/output/P04_remix_videos/remix_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_video_info(filepath):
    """获取视频分辨率和时长"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "json",
            str(filepath)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        return {
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "duration": float(stream.get("duration", 0) or 0),
        }
    except Exception:
        return None

def classify_ratio(w, h):
    """根据分辨率分类比例"""
    if w == 0 or h == 0:
        return "unknown"
    ratio = w / h
    if ratio < 0.7:
        return "9X16"   # 竖版 1080x1920
    elif ratio > 1.3:
        return "16X9"   # 横版 1920x1080
    else:
        return "1X1"    # 方版 1080x1080

# Build local video index with resolution info
local_by_v = {}
for video_file in SOURCE_DIR.iterdir():
    if video_file.is_file() and video_file.suffix.lower() == ".mp4":
        fname = video_file.stem
        m = re.search(r'v(\d+)', fname)
        if m:
            v_num = f"v{m.group(1)}"
            info = get_video_info(video_file)
            if info:
                ratio = classify_ratio(info["width"], info["height"])
            else:
                # Fallback: infer from filename
                if "9X16" in fname:
                    ratio = "9X16"
                elif "16X9" in fname:
                    ratio = "16X9"
                else:
                    ratio = "1X1"
            local_by_v[v_num] = {
                "path": str(video_file),
                "ratio": ratio,
                "width": info["width"] if info else 0,
                "height": info["height"] if info else 0,
                "duration": info["duration"] if info else 0,
            }

print(f"本地 P04 视频已索引: {len(local_by_v)} 个")

# Count by ratio
ratio_counts = defaultdict(int)
for v in local_by_v.values():
    ratio_counts[v["ratio"]] += 1
print("比例分布:", dict(ratio_counts))

# Load Adjust performance data
video_data = []
with open(ADJUST_REPORT, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        row["roas"] = float(row.get("roas", 0) or 0)
        row["cost"] = float(row.get("cost", 0) or 0)
        row["revenue"] = float(row.get("revenue", 0) or 0)
        row["installs"] = int(float(row.get("installs", 0) or 0))
        video_data.append(row)

# Content type mapping for DNA segment assignment
CONTENT_SEGMENT = {
    "角色展示": ["transformation", "reward"],
    "剧情": ["problem", "transformation"],
    "文字滚动": ["problem"],
    "开场": ["hook"],
    "玩法展示": ["merge_action"],
    "其他": ["hook"],
}

def build_segments_for_ratio(target_ratio):
    """为指定比例构建 DNA segment 候选池"""
    segments = {
        "hook": [],
        "problem": [],
        "merge_action": [],
        "transformation": [],
        "reward": [],
    }
    
    for v in video_data:
        content = v.get("content", "其他")
        roas = v["roas"]
        cost = v["cost"]
        v_num = v["v_num"]
        
        info = local_by_v.get(v_num)
        if not info:
            continue
        if info["ratio"] != target_ratio:
            continue
        
        roles = CONTENT_SEGMENT.get(content, ["hook"])
        
        entry = {
            "v_num": v_num,
            "roas": roas,
            "cost": cost,
            "revenue": v["revenue"],
            "content": content,
            "duration": v.get("duration", ""),
            "ratio": info["ratio"],
            "width": info["width"],
            "height": info["height"],
            "filepath": info["path"],
        }
        
        for role in roles:
            segments[role].append(entry)
    
    return segments

def pick_best(candidates, top=3):
    scored = sorted(candidates, key=lambda x: (-x["roas"], x["cost"] > 100))
    return scored[:top]

def _role_hint(content):
    """Map a content type to a DNA role hint for temporal positioning."""
    return CONTENT_SEGMENT.get(content, ["hook"])[0]


def build_recipe(name, sources, target_ratio):
    """Build a remix recipe (P0-3 fixed: source windows resolved by ClipResolver)."""
    recipe = {
        "name": name,
        "target_ratio": target_ratio,
        "segments": [],
    }
    
    segment_timeline = [
        ("seg_01_hook", 0, 3, sources[0]),
        ("seg_02_problem", 3, 10, sources[1]),
        ("seg_03_merge", 10, 30, sources[2]),
        ("seg_04_transform", 30, 38, sources[3]),
        ("seg_05_reward", 38, 40, sources[4]),
    ]
    
    for i, (seg_id, seg_start, seg_end, source) in enumerate(segment_timeline):
        seg_duration = seg_end - seg_start
        vnum = source["v_num"]
        src_info = local_by_v.get(vnum)
        src_dur = src_info["duration"] if src_info else (float(source.get("duration") or 0))
        role_hint = _role_hint(source.get("content", ""))
        # P0-3 fix: resolve a valid window strictly inside the source's REAL duration.
        # Never uses the new video's timeline position as a source offset.
        s_start, s_end, actual = resolve_clip(src_dur, seg_duration, role_hint)
        
        recipe["segments"].append({
            "segment_id": seg_id,
            "timeline": f"{seg_start}s-{seg_end}s",
            "source_v_num": vnum,
            "source_roas": source["roas"],
            "source_content": source["content"],
            "source_file": source["filepath"],
            "source_ratio": source["ratio"],
            "extract_start_sec": s_start,
            "extract_duration_sec": actual,
        })
    
    return recipe

def execute_recipe(recipe, output_dir):
    """执行一个混剪配方"""
    name = recipe["name"]
    ratio = recipe["target_ratio"]
    print(f"\n处理: {name} (比例: {ratio})")
    
    proj_dir = output_dir / name
    proj_dir.mkdir(parents=True, exist_ok=True)
    
    clip_files = []
    
    for i, seg in enumerate(recipe["segments"]):
        src = seg["source_file"]
        start = seg["extract_start_sec"]
        dur = seg["extract_duration_sec"]
        out_clip = proj_dir / f"clip_{i:02d}_{seg['segment_id']}.mp4"
        clip_files.append(str(out_clip))
        
        if out_clip.exists():
            print(f"  [{seg['segment_id']}] skip (exists)")
            continue
        
        # Extract clip with re-encode to ensure same codec params (audio kept)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(src),
            "-t", str(dur),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            str(out_clip)
        ]
        print(f"  提取 {seg['segment_id']}: {start}s→{start+dur}s ({seg['source_v_num']})")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            last_line = result.stderr.strip().split('\n')[-1]
            print(f"    ⚠️ {last_line[:120]}")
        else:
            size_mb = out_clip.stat().st_size / 1024 / 1024
            print(f"    ✅ {size_mb:.1f}MB")
    
    # Concat all clips
    concat_list = proj_dir / "concat_list.txt"
    concat_list.write_text("\n".join(f"file '{f}'" for f in clip_files), encoding="utf-8")
    
    final = proj_dir / f"final_{name}.mp4"
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(final)
    ]
    print(f"  合成最终视频...")
    result = subprocess.run(cmd_concat, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ⚠️ 合成失败: {result.stderr[:200]}")
    else:
        size_mb = final.stat().st_size / 1024 / 1024
        print(f"    ✅ {final} ({size_mb:.1f}MB)")
        return final
    return None

# Generate remixes per ratio
all_remixes = []

for ratio in ["9X16", "1X1", "16X9"]:
    segments = build_segments_for_ratio(ratio)
    
    # Check if we have enough candidates
    total_candidates = sum(len(v) for v in segments.values())
    if total_candidates < 10:
        print(f"\n跳过 {ratio}: 候选素材不足 ({total_candidates} 个)")
        continue
    
    print(f"\n{'='*80}")
    print(f"=== 生成 {ratio} 比例混剪 ===")
    print(f"{'='*80}")
    
    selections = {}
    for seg_name in ["hook", "problem", "merge_action", "transformation", "reward"]:
        best = pick_best(segments[seg_name], top=3)
        selections[seg_name] = best
        for b in best:
            print(f"  {b['v_num']:<10} | {b['content']:<10} | {b['roas']:>5.2f} | {b['ratio']}")
    
    # Need at least hook + one more segment
    if not selections["hook"]:
        continue
    
    # Remix 1: Top performers
    hook_src = selections["hook"][0]
    problem_src = selections["problem"][0] if selections["problem"] else hook_src
    merge_src = selections["merge_action"][0] if selections["merge_action"] else problem_src
    trans_src = selections["transformation"][0] if selections["transformation"] else hook_src
    reward_src = selections["reward"][0] if selections["reward"] else hook_src
    
    remix1 = build_recipe(f"remix_{ratio}_01_top", [hook_src, problem_src, merge_src, trans_src, reward_src], ratio)
    
    # Remix 2: Diversified
    hook_src2 = selections["hook"][min(1, len(selections["hook"])-1)]
    problem_src2 = selections["problem"][min(1, len(selections["problem"])-1)] if selections["problem"] else hook_src2
    merge_src2 = selections["merge_action"][min(1, len(selections["merge_action"])-1)] if selections["merge_action"] else problem_src2
    trans_src2 = selections["transformation"][min(1, len(selections["transformation"])-1)] if selections["transformation"] else hook_src2
    reward_src2 = selections["reward"][min(1, len(selections["reward"])-1)] if selections["reward"] else hook_src2
    
    remix2 = build_recipe(f"remix_{ratio}_02_diverse", [hook_src2, problem_src2, merge_src2, trans_src2, reward_src2], ratio)
    
    # Remix 3: Role-display combo
    role_best = sorted(
        [v for v in video_data if v.get("content") == "角色展示" and v["v_num"] in local_by_v and local_by_v[v["v_num"]]["ratio"] == ratio],
        key=lambda x: -x["roas"]
    )[:5]
    for rb in role_best:
        rb["filepath"] = local_by_v[rb["v_num"]]["path"]
        rb["ratio"] = ratio
    
    remixes_for_ratio = [remix1, remix2]
    if len(role_best) >= 5:
        remix3 = build_recipe(f"remix_{ratio}_03_role", role_best[:5], ratio)
        remixes_for_ratio.append(remix3)
    
    # Execute
    for r in remixes_for_ratio:
        final_path = execute_recipe(r, OUTPUT_DIR)
        if final_path:
            all_remixes.append({
                "name": r["name"],
                "ratio": ratio,
                "path": str(final_path),
                "segments": r["segments"],
            })

# Save report
report_path = OUTPUT_DIR / "remix_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump({
        "total_remixes": len(all_remixes),
        "source_data": "Adjust full lifecycle",
        "remixes": all_remixes,
    }, f, ensure_ascii=False, indent=2)

print(f"\n{'='*80}")
print("P04 Creative Remix Report")
print(f"{'='*80}")
print(f"数据来源: Adjust 全生命周期")
print(f"本地视频源: {len(local_by_v)} 个")
print(f"生成混剪: {len(all_remixes)} 条")
print(f"输出目录: {OUTPUT_DIR}")
print()
for r in all_remixes:
    print(f"  [{r['ratio']}] {r['name']}")
    print(f"    → {r['path']}")
print(f"\n报告文件: {report_path}")
