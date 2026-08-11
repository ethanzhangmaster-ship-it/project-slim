"""
P04 Video Factory V3.4 Phase 0 — AI Video Generation Pipeline

读取 V3.3 TOP20 recipe → 从 Eagle 素材提取片段 → 组装 15s 9:16 MP4 → 字幕 → 输出报告
"""
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

SOURCE_VIDEOS_DIR = Path("D:/project_slim/output/P04_remix_videos/广告视频")
OUTPUT_DIR = Path("D:/project_slim/output/P04_remix_videos/v34_videos")
V33_REPORT = Path("creative_remix_engine/storage/outputs/remix_report_P04_v33.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DNA_STRUCTURE = [
    {"role": "hook", "duration": 2.5},
    {"role": "problem", "duration": 2.5},
    {"role": "gameplay", "duration": 6.0},
    {"role": "reward", "duration": 2.5},
    {"role": "cta", "duration": 1.5},
]

SUBTITLES = {
    "hook": "WITCH MERGE",
    "problem": "Can You Spot the Fake?",
    "gameplay": "Swipe Merge EVOLVE",
    "reward": "ULTIMATE TRANSFORMATION",
    "cta": "Download Now and Play",
}


def get_video_info(path):
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "json", str(path)
        ], capture_output=True, text=True, timeout=10)
        s = json.loads(result.stdout)["streams"][0]
        return {"width": int(s.get("width", 0)), "height": int(s.get("height", 0)),
                "duration": float(s.get("duration", 0) or 0)}
    except:
        return {"width": 0, "height": 0, "duration": 15.0}


def build_source_pool():
    """从 Eagle 素材库建立片段池（只取竖版 9X16 视频）"""
    all_videos = list(SOURCE_VIDEOS_DIR.glob("*.mp4"))
    pool = {"hook": [], "gameplay": [], "reward": [], "problem": [], "cta": []}
    content_map = {
        "hook": ["kaitou", "开场", "宠物展示", "角色展示"],
        "gameplay": ["wanfazhanshi", "玩法展示"],
        "problem": ["wenzigundong", "文字滚动", "剧情"],
        "reward": ["juesezhanshi", "角色展示"],
        "cta": ["kaitou", "宠物展示"],
    }
    for vp in all_videos:
        info = get_video_info(vp)
        if info["duration"] < 3 or info["width"] == 0:
            continue
        stem = vp.stem.lower()
        for role, kw in content_map.items():
            if any(k in stem for k in kw):
                pool[role].append((vp, info))
                break
        else:
            for role in content_map:
                pool[role].append((vp, info))
    for role in pool:
        vertical = [(p, i) for p, i in pool[role] if 0.4 < i["width"]/max(i["height"],1) < 0.7]
        pool[role] = sorted(vertical or pool[role], key=lambda x: abs(x[1]["duration"] - 12.0))
    return pool


def extract_clip_raw(src_path, dst_path, start, dur):
    """Pure extract: no text, just fade + audio"""
    fade_in = "fade=in:st=0:d=0.25"
    fade_out = f"fade=out:st={max(0.1,dur-0.25)}:d=0.25"
    vf = f"{fade_in},{fade_out}"
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", str(src_path),
           "-t", str(dur), "-vf", vf,
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
           "-c:a", "aac", "-b:a", "192k", "-loglevel", "error", str(dst_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.returncode == 0 and dst_path.exists()
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def add_text_overlay(input_path, output_path, text, is_big=False):
    """Add burned-in subtitle using drawtext with textfile approach"""
    font_size = 48 if is_big else 40
    y_pos = "h*0.75" if is_big else "h*0.82"

    # Write text to temp file to avoid escaping issues
    textfile = output_path.parent / "_text.txt"
    textfile.write_text(text, encoding="utf-8")

    drawtext = (
        f"drawtext=fontfile=C\\:/Windows/Fonts/simhei.ttf:"
        f"textfile={textfile.as_posix()}:"
        f"fontsize={font_size}:fontcolor=white:"
        f"borderw=4:bordercolor=black@0.7:"
        f"x=(w-text_w)/2:y={y_pos}"
    )
    cmd = ["ffmpeg", "-y", "-i", str(input_path),
           "-vf", drawtext,
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
           "-c:a", "copy", "-loglevel", "error", str(output_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except:
        return False
    ok = r.returncode == 0 and output_path.exists()
    if not ok:
        print(f"         overlay error: {r.stderr[-150:]}")
    textfile.unlink(missing_ok=True)
    return ok


def generate_video(video_idx, pool, project_dir):
    proj_dir = project_dir / f"v{video_idx+1:02d}"
    proj_dir.mkdir(parents=True, exist_ok=True)

    clip_files = []
    for i, slot in enumerate(DNA_STRUCTURE):
        role = slot["role"]
        target_dur = slot["duration"]
        if role not in pool or not pool[role]:
            continue
        src_path, info = pool[role][(video_idx + i) % len(pool[role])]

        if role == "hook":
            start = min(1.0, max(0, info["duration"] - target_dur))
        elif role == "reward":
            start = max(0, info["duration"] - target_dur - 1.0)
        elif role == "gameplay":
            start = info["duration"] * 0.25
        else:
            start = info["duration"] * 0.15
        start = max(0, min(start, info["duration"] - 2.0))
        dur = min(target_dur, info["duration"] - start)

        raw_clip = proj_dir / f"raw_{i:02d}_{role}.mp4"
        if not extract_clip_raw(src_path, raw_clip, start, dur):
            print(f"      Skipping {role} (extract failed)")
            continue

        # Text overlay (tolerate failure)
        text = SUBTITLES.get(role, "")
        if text:
            final_clip = proj_dir / f"clip_{i:02d}_{role}.mp4"
            if add_text_overlay(raw_clip, final_clip, text, is_big=(role in ("hook", "reward", "cta"))):
                clip_files.append(final_clip)
                raw_clip.unlink(missing_ok=True)
            else:
                clip_files.append(raw_clip)  # use raw
        else:
            clip_files.append(raw_clip)

    if not clip_files:
        return None, 0

    # concat
    concat_list = proj_dir / "concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for c in clip_files:
            f.write(f"file '{c.as_posix()}'\n")

    final_path = proj_dir / "final.mp4"
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
           "-c:a", "aac", "-b:a", "192k", "-loglevel", "error", str(final_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        print(f"      concat timeout")
        return None, 0
    if r.returncode != 0:
        print(f"      concat error: {r.stderr[-150:]}")
    return final_path, sum(min(slot["duration"], 5) for slot in DNA_STRUCTURE if clip_files)


def assess_quality(video_path):
    if not video_path or not video_path.exists():
        return {"exists": False, "passed": False, "score": 0, "duration": 0,
                "resolution": "N/A", "size_mb": 0, "has_audio": False,
                "issues": ["FILE_MISSING"], "warnings": []}
    size_mb = video_path.stat().st_size / 1024 / 1024
    info = get_video_info(video_path)
    issues, warnings = [], []
    if size_mb < 0.5: issues.append("FILE_TOO_SMALL")
    if info["duration"] < 5: issues.append("TOO_SHORT")
    if info["duration"] > 25: warnings.append("TOO_LONG")
    r = info["width"] / max(info["height"], 1)
    if not (0.4 < r < 0.7): issues.append("WRONG_RATIO")
    try:
        a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video_path)],
                           capture_output=True, text=True)
        has_audio = "audio" in a.stdout
    except:
        has_audio = False
    if not has_audio: warnings.append("NO_AUDIO")
    return {"exists": True, "passed": len(issues) == 0,
            "score": max(0, 100 - len(issues)*25 - len(warnings)*10),
            "duration": round(info["duration"], 1),
            "resolution": f"{info['width']}x{info['height']}",
            "size_mb": round(size_mb, 1), "has_audio": has_audio,
            "issues": issues, "warnings": warnings}


# ===== MAIN =====
print("=" * 70)
print("V3.4 Phase 0 — AI Video Generation Pipeline")
print("=" * 70)

print("\n[1/5] Load V3.3 TOP20...")
with open(V33_REPORT, "r", encoding="utf-8") as f:
    v33 = json.load(f)
top20 = v33.get("top20", [])[:20]
print(f"  Loaded {len(top20)} predictions")

print("\n[2/5] Build Eagle Source Pool (9X16 only)...")
pool = build_source_pool()
for role, items in pool.items():
    print(f"  {role}: {len(items)} candidates")

print(f"\n[3/5] Generate {len(top20)} videos...")
results = []
project_dir = OUTPUT_DIR / "projects"
project_dir.mkdir(parents=True, exist_ok=True)

for idx, pred in enumerate(top20):
    cid = pred["creative_id"]
    print(f"  [{idx+1:2d}/20] {cid}")

    final_path, _ = generate_video(idx, pool, project_dir)

    final_name = f"P04_v34_{idx+1:03d}.mp4"
    final_dest = OUTPUT_DIR / final_name
    if final_path and final_path.exists():
        shutil.copy(final_path, final_dest)

    qa = assess_quality(final_dest)
    qa["creative_id"] = cid
    qa["expected_roas"] = pred.get("expected_roas", 0)
    qa["pred_decision"] = pred.get("recommendation", "N/A")
    results.append(qa)

print("\n[4/5] Generate Quality Report...")
report = {
    "pipeline": "V3.4 Phase 0",
    "generated_at": datetime.now().isoformat(),
    "source": "Eagle P04素材库",
    "dna_template": "15s_bomb",
    "target_ratio": "9X16",
    "total_videos": len(results),
    "passed": sum(1 for r in results if r.get("passed")),
    "failed": sum(1 for r in results if not r.get("passed")),
    "results": results,
}
report_path = OUTPUT_DIR / "video_generation_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2, default=str)

print(f"\n[5/5] Summary")
print("=" * 70)
print(f"  Total: {len(results)} | Passed: {report['passed']} | Failed: {report['failed']}")
print(f"  Output: {OUTPUT_DIR}")
print(f"  Report: {report_path}")
for i, r in enumerate(results):
    icon = "✅" if r.get("passed") else "❌"
    tag = " ".join(r.get("issues", []) + r.get("warnings", []))
    tag_str = f" [{tag}]" if tag else ""
    print(f"    {icon} {r.get('creative_id',''):<20} "
          f"{r.get('resolution','?'):<12} {r.get('duration',0):5.1f}s "
          f"{r.get('size_mb',0):5.1f}MB Score={r.get('score',0)}{tag_str}")
print("=" * 70)
