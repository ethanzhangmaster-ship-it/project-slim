"""Creative Mapping Engine — Step 1: Extract metadata from Eagle local videos.

For each video file in eagle_index.json, extract: duration, width, height, pHash.
Uses ffprobe for video metadata, imagehash for perceptual hashing.
"""
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EAGLE_INDEX = ROOT / "output" / "video_intelligence" / "p04" / "eagle_index.json"
OUTPUT = ROOT / "output" / "video_intelligence" / "p04" / "eagle_metadata.json"
NAS = Path(r"Y:\Eagle\公司-市场部门库.library\images")

try:
    import imagehash
    from PIL import Image
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False
    print("Warning: imagehash/Pillow not available, skipping perceptual hash")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def check_ffprobe():
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def extract_metadata(entry):
    folder = entry["folder"]
    results = []
    for fn in entry["files"]:
        filepath = os.path.join(folder, fn)
        info = {
            "folder": folder,
            "filename": fn,
            "filepath": filepath,
            "duration": None,
            "width": None,
            "height": None,
            "phash": None,
            "filesize": None,
        }

        # File size
        try:
            info["filesize"] = os.path.getsize(filepath)
        except Exception:
            pass

        # ffprobe
        if HAS_FFPROBE:
            try:
                cmd = [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format", "-show_streams",
                    filepath
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    for stream in data.get("streams", []):
                        if stream.get("codec_type") == "video":
                            info["width"] = stream.get("width")
                            info["height"] = stream.get("height")
                            dur = stream.get("duration") or data.get("format", {}).get("duration")
                            if dur:
                                info["duration"] = round(float(dur), 2)
                            break
                    if info["duration"] is None:
                        dur2 = data.get("format", {}).get("duration")
                        if dur2:
                            info["duration"] = round(float(dur2), 2)
            except Exception:
                pass

        # Perceptual hash via first frame
        if HAS_IMAGEHASH and HAS_CV2:
            try:
                cap = cv2.VideoCapture(filepath)
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                cap.release()
                if ret:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb)
                    info["phash"] = str(imagehash.phash(pil_img))
            except Exception:
                pass

        results.append(info)
    return results


# ── Main ──
HAS_FFPROBE = check_ffprobe()
print(f"ffprobe: {HAS_FFPROBE}")
print(f"imagehash: {HAS_IMAGEHASH}")
print(f"cv2: {HAS_CV2}")

eagle = json.loads(EAGLE_INDEX.read_text(encoding="utf-8"))
print(f"Eagle entries: {len(eagle)}")

all_meta = []
with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(extract_metadata, entry): entry for entry in eagle}
    for i, f in enumerate(as_completed(futures)):
        result = f.result()
        if result:
            all_meta.extend(result)
        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(eagle)}] {len(all_meta)} videos analyzed")

# Flatten for matching
flat = {}
for meta in all_meta:
    name = Path(meta["filename"]).stem
    flat[name] = meta

print(f"Total indexed videos: {len(flat)}")
with_dur = sum(1 for v in flat.values() if v["duration"])
with_phash = sum(1 for v in flat.values() if v["phash"])
print(f"  With duration: {with_dur}")
print(f"  With phash: {with_phash}")

OUTPUT.write_text(json.dumps(flat, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved: {OUTPUT}")
