"""Creative Mapping Engine v2 — Facebook P04 → Eagle local videos.

Uses pre-fetched diagnosis data (contains video_id per creative).
Fetches video metadata (duration, resolution, created_time) from Facebook Graph API.
Runs multi-layer matching against Eagle local video index.
"""
import json, os, re, sys, time, requests
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "output" / "video_intelligence" / "p04"
API = "https://graph.facebook.com/v19.0"


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def fetch_fb_video_meta_simple(token: str, diagnosis: list[dict]) -> dict[str, dict]:
    """Batch fetch video metadata from already-known video_ids.

    Returns {creative_id: {fb_duration, fb_resolution, fb_title, fb_created}}
    """
    cid_to_vid = {}
    for d in diagnosis:
        cid = d["creative_id"]
        vid = d.get("video_id") or d.get("object_story_spec_video_data_video_id")
        if vid:
            cid_to_vid[vid] = cid

    print(f"[FB] Fetching metadata for {len(cid_to_vid)} videos...")
    vid_list = list(cid_to_vid.keys())
    result = {}

    for i in range(0, len(vid_list), 50):
        batch = vid_list[i:i + 50]
        try:
            r = requests.get(f"{API}/", params={
                "ids": ",".join(batch),
                "fields": "id,picture,length,format,created_time,title",
                "access_token": token,
            }, timeout=120)
            if r.status_code == 200:
                for vid, detail in (r.json() or {}).items():
                    if not isinstance(detail, dict):
                        continue
                    cid = cid_to_vid.get(vid)
                    if not cid:
                        continue

                    fmt = detail.get("format", []) or []
                    native_fmt = None
                    for f in fmt:
                        if isinstance(f, dict) and f.get("filter") == "native":
                            native_fmt = f
                            break
                    if not native_fmt and fmt:
                        native_fmt = fmt[-1]

                    result[cid] = {
                        "fb_duration": float(detail.get("length", 0)),
                        "fb_thumbnail": detail.get("picture", ""),
                        "fb_created": detail.get("created_time", ""),
                        "fb_title": detail.get("title", ""),
                        "fb_width": native_fmt.get("width") if native_fmt else None,
                        "fb_height": native_fmt.get("height") if native_fmt else None,
                    }
        except Exception as e:
            pass
        if (i // 50 + 1) % 2 == 0:
            print(f"  [{min(i + 50, len(vid_list))}/{len(vid_list)}] {len(result)} loaded")
        time.sleep(0.3)

    print(f"  Loaded: {len(result)}")
    return result


def load_eagle_index() -> dict[str, list[dict]]:
    data = json.loads((OUT / "eagle_index.json").read_text(encoding="utf-8"))
    index = defaultdict(list)
    for entry in data:
        folder = entry["folder"]
        for fn in entry["files"]:
            stem = Path(fn).stem.lower()
            index[stem].append({"folder": folder, "filename": fn, "filepath": os.path.join(folder, fn)})
    return dict(index)


def extract_local_duration(filepath: str) -> float | None:
    try:
        import subprocess
        r = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", filepath
        ], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            d = json.loads(r.stdout).get("format", {}).get("duration")
            if d:
                return round(float(d), 2)
    except Exception:
        pass
    return None


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_best(
    creative_name: str,
    fb_meta: dict,
    eagle_index: dict[str, list[dict]],
) -> dict | None:
    """Find best Eagle match for a Facebook creative."""
    cn = creative_name
    cn_low = cn.lower()
    fb_dur = fb_meta.get("fb_duration")
    fb_w = fb_meta.get("fb_width")
    fb_h = fb_meta.get("fb_height")

    # Extract core name (remove date-hash suffix)
    core = re.sub(r'\s*\d{4}-\d{2}-\d{2}-[a-f0-9]+.*$', '', cn).strip()

    # Tokenize for keyword matching
    cn_tokens = set(re.findall(r'[a-z0-9]{3,}', core.lower()))

    # Also extract date-hash for exact suffix match
    dh_match = re.search(r'(\d{4}-\d{2}-\d{2}-[a-f0-9]{6,})', cn)
    date_hash = dh_match.group(1).lower() if dh_match else ""

    candidates = []

    for ename, entries in eagle_index.items():
        en_low = ename

        # --- Exact hash suffix match ---
        if date_hash and date_hash in en_low:
            entry = entries[0]
            # Get duration for verification
            local_dur = extract_local_duration(entry["filepath"])
            dur_diff = abs(fb_dur - local_dur) if fb_dur and local_dur else None
            score = 1.0
            method = "hash_exact"
            if dur_diff is not None and dur_diff < 0.5:
                score = 1.0
                method = "hash_exact+duration_verified"
            return {
                "local_path": entry["filepath"],
                "local_filename": entry["filename"],
                "local_folder": entry["folder"],
                "confidence": min(score, 1.0),
                "match_method": method,
                "fb_duration": fb_dur,
                "local_duration": local_dur,
                "duration_diff": dur_diff,
                "fb_width": fb_w,
                "fb_height": fb_h,
            }

        # --- Name similarity ---
        name_sim = name_similarity(core, ename)

        # Token overlap
        en_tokens = set(re.findall(r'[a-z0-9]{3,}', en_low))
        common = cn_tokens & en_tokens
        token_sim = len(common) / max(len(cn_tokens | en_tokens), 1)

        # Combined score: name similarity weighted more
        combined = name_sim * 0.65 + token_sim * 0.35

        if combined < 0.25:
            continue

        candidates.append({
            "entry": entries[0],
            "name_sim": round(name_sim, 4),
            "token_sim": round(token_sim, 4),
            "score": round(combined, 4),
            "common_tokens": sorted(common),
        })

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Verify top candidates with duration
    top = candidates[0]
    entry = top["entry"]
    local_dur = extract_local_duration(entry["filepath"])

    score = top["score"]
    method = "name_similarity"
    dur_diff = None

    if fb_dur and local_dur:
        dur_diff = abs(fb_dur - local_dur)
        if dur_diff < 0.3:
            score += 0.20
            method += "+duration_exact"
        elif dur_diff < 1.0:
            score += 0.12
            method += "+duration_close"
        elif dur_diff < 3.0:
            score += 0.05
            method += "+duration_similar"
        elif dur_diff > 10:
            score -= 0.30
            method += "+duration_mismatch"

    if fb_w and local_dur is not None:
        # Resolution bonus (we can't easily check without ffprobe on both)
        pass

    score = max(0.0, min(1.0, score))

    return {
        "local_path": entry["filepath"],
        "local_filename": entry["filename"],
        "local_folder": entry["folder"],
        "confidence": round(score, 4),
        "match_method": method,
        "fb_duration": fb_dur,
        "local_duration": local_dur,
        "duration_diff": round(dur_diff, 2) if dur_diff is not None else None,
        "fb_width": fb_w,
        "fb_height": fb_h,
        "name_sim": top["name_sim"],
        "token_sim": top["token_sim"],
        "common_tokens": top["common_tokens"][:10],
    }


def main():
    load_env()
    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERROR: META_ACCESS_TOKEN not set")
        return 1

    print("=" * 60)
    print("CREATIVE MAPPING ENGINE v2")
    print("=" * 60)

    diagnosis = json.loads((OUT / "video_download_diagnosis.json").read_text(encoding="utf-8"))
    print(f"P04 diagnosis records: {len(diagnosis)}")

    eagle = load_eagle_index()
    print(f"Eagle video files: {len(eagle)}")

    fb_meta = fetch_fb_video_meta_simple(token, diagnosis)

    print(f"\nRunning mapping...")
    results = []
    auto_ok = 0
    review = 0
    unmatched = 0

    for i, d in enumerate(diagnosis):
        cn = d.get("creative_name", "")
        cid = d["creative_id"]
        fm = fb_meta.get(cid, {})

        match = match_best(cn, fm, eagle)

        if match:
            conf = match["confidence"]
            record = {
                "creative_id": cid,
                "creative_name": cn,
                "ad_id": d.get("ad_id", ""),
                "campaign_id": d.get("campaign_id", ""),
                "adset_id": d.get("adset_id", ""),
                "spend": d.get("spend", 0),
                "ctr": d.get("ctr", 0),
                "roas": d.get("roas", 0),
                "local_path": match["local_path"],
                "local_filename": match["local_filename"],
                "confidence": conf,
                "match_method": match["match_method"],
                "fb_duration": match.get("fb_duration"),
                "local_duration": match.get("local_duration"),
                "duration_diff": match.get("duration_diff"),
                "needs_review": conf < 0.90,
            }
            if conf >= 0.95:
                auto_ok += 1
            elif conf >= 0.50:
                review += 1
            else:
                unmatched += 1
        else:
            record = {
                "creative_id": cid,
                "creative_name": cn,
                "ad_id": d.get("ad_id", ""),
                "campaign_id": d.get("campaign_id", ""),
                "adset_id": d.get("adset_id", ""),
                "spend": d.get("spend", 0),
                "ctr": d.get("ctr", 0),
                "roas": d.get("roas", 0),
                "local_path": None,
                "confidence": 0,
                "match_method": "none",
                "needs_review": True,
            }
            unmatched += 1

        results.append(record)
        if (i + 1) % 30 == 0:
            print(f"  [{i+1}/{len(diagnosis)}] auto={auto_ok} review={review} unmatched={unmatched}")

    mapping_file = OUT / "creative_mapping.json"
    mapping_file.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    review_list = [r for r in results if r.get("needs_review")]
    (OUT / "creative_mapping_review.json").write_text(
        json.dumps(review_list, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    print(f"\n{'='*60}")
    print(f"MAPPING RESULTS")
    print(f"  Auto-bind (≥0.95):   {auto_ok}")
    print(f"  Needs review (0.50-0.94): {review}")
    print(f"  Unmatched (<0.50):   {unmatched}")
    print(f"\n  creative_mapping.json        — all {len(results)} creatives")
    print(f"  creative_mapping_review.json — {len(review_list)} need human review")
    print(f"{'='*60}")

    if unmatched > 130:
        print("\n⚠️  Most creatives unmatched.")
        print("   This likely means the Eagle library does NOT contain P04 Witch videos.")
        print("   Let me verify...")
        _diagnose_eagle_vs_p04(eagle, diagnosis)

    return 0


def _diagnose_eagle_vs_p04(eagle_index, diagnosis):
    """Check what kind of content is in Eagle vs P04."""
    all_p04_names = [d.get("creative_name", "") for d in diagnosis]
    # Sample P04 creative name patterns
    key_phrases = Counter()
    for name in all_p04_names:
        core = re.sub(r'\s*\d{4}-\d{2}-\d{2}-[a-f0-9]+.*$', '', name).strip()
        words = core.lower().split()
        for w in words:
            if len(w) > 3:
                key_phrases[w] += 1

    print(f"\n  P04 common keywords: {key_phrases.most_common(10)}")

    # Check if any Eagle file contains these keywords
    p04_keywords = set(w for w, c in key_phrases.most_common(5))
    eagle_matches = []
    for ename in eagle_index:
        matching = [k for k in p04_keywords if k in ename]
        if matching:
            eagle_matches.append((ename, matching))

    if eagle_matches:
        print(f"\n  Eagle files matching P04 keywords ({len(eagle_matches)}):")
        for ename, kw in eagle_matches[:15]:
            print(f"    {ename[:70]} ← {kw}")
    else:
        print(f"\n  ❌ No Eagle files match any P04 keywords.")
        print(f"  This Eagle library likely does NOT contain P04 Witch content.")
        print(f"  P04 Witch videos may be in a different Eagle library or folder.")


from collections import Counter

if __name__ == "__main__":
    sys.exit(main())
