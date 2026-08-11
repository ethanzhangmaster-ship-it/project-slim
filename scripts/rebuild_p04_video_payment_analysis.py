"""Fresh P04 video/payment analysis built from raw exports and original Meta videos.

This intentionally does not read any prior winner report, visual feature report,
cluster label, or causal-policy artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
import requests


ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "output" / "p04_all_905_facebook_videos.csv"
OUT = ROOT / "output" / "video_reanalysis_20260804"
VIDEOS = OUT / "videos"
FRAMES = OUT / "frames"
THUMBNAILS = OUT / "thumbnails"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def load_raw_rows() -> list[dict]:
    with RAW_CSV.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def resolve_and_download(row: dict, token: str, version: str) -> dict:
    video_id = str(row["video_id"])
    destination = VIDEOS / f"{video_id}.mp4"
    result = {
        "video_id": video_id,
        "status": "pending",
        "local_path": str(destination),
        "bytes": destination.stat().st_size if destination.exists() else 0,
        "error": "",
    }
    if destination.exists() and destination.stat().st_size > 32_768:
        result.update(status="downloaded", bytes=destination.stat().st_size)
        return result
    for attempt in range(4):
        try:
            meta = requests.get(
                f"https://graph.facebook.com/{version}/{video_id}",
                params={"access_token": token, "fields": "source,length,title,picture"},
                timeout=45,
            )
            payload = meta.json()
            source = payload.get("source")
            if not source:
                error = payload.get("error") or {}
                raise RuntimeError(f"no_source:{error.get('code')}:{error.get('message', '')[:100]}")
            temporary = destination.with_suffix(".mp4.part")
            with requests.get(source, stream=True, timeout=180) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(512 * 1024):
                        if chunk:
                            output.write(chunk)
            if temporary.stat().st_size < 32_768:
                raise RuntimeError("download_too_small")
            temporary.replace(destination)
            result.update(
                status="downloaded",
                bytes=destination.stat().st_size,
                graph_length=number(payload.get("length")),
                graph_title=str(payload.get("title") or ""),
            )
            return result
        except Exception as exc:  # network/API failures are recorded per asset
            result["error"] = f"{type(exc).__name__}:{str(exc)[:180]}"
            destination.with_suffix(".mp4.part").unlink(missing_ok=True)
            time.sleep(1.5 * (attempt + 1))
    result["status"] = "failed"
    return result


def stage_download(workers: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    VIDEOS.mkdir(parents=True, exist_ok=True)
    rows = load_raw_rows()
    env = load_env()
    token = env.get("META_ACCESS_TOKEN", "")
    version = env.get("META_API_VERSION", "v19.0")
    if not token:
        raise RuntimeError("META_ACCESS_TOKEN is missing")
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(resolve_and_download, row, token, version) for row in rows]
        for index, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if index % 25 == 0:
                ok = sum(r["status"] == "downloaded" for r in results)
                print(f"download {index}/{len(rows)} ok={ok}", flush=True)
    results.sort(key=lambda item: item["video_id"])
    (OUT / "fresh_download_manifest.json").write_text(
        json.dumps({"raw_rows": len(rows), "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "total": len(results),
        "downloaded": sum(r["status"] == "downloaded" for r in results),
        "failed": sum(r["status"] != "downloaded" for r in results),
        "gb": round(sum(r.get("bytes", 0) for r in results) / 1024**3, 2),
    }))


def download_thumbnail(row: dict) -> dict:
    video_id = str(row["video_id"])
    destination = THUMBNAILS / f"{video_id}.jpg"
    if destination.exists() and destination.stat().st_size > 1024:
        return {"video_id": video_id, "status": "downloaded", "bytes": destination.stat().st_size}
    url = str(row.get("thumbnail_url") or "")
    if not url:
        return {"video_id": video_id, "status": "missing_url", "bytes": 0}
    try:
        response = requests.get(url, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        destination.write_bytes(response.content)
        if destination.stat().st_size <= 1024:
            destination.unlink(missing_ok=True)
            raise RuntimeError("thumbnail_too_small")
        return {"video_id": video_id, "status": "downloaded", "bytes": destination.stat().st_size}
    except Exception as exc:
        destination.unlink(missing_ok=True)
        return {"video_id": video_id, "status": "failed", "bytes": 0, "error": f"{type(exc).__name__}:{str(exc)[:120]}"}


def stage_thumbnails(workers: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    THUMBNAILS.mkdir(parents=True, exist_ok=True)
    rows = load_raw_rows()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(download_thumbnail, row) for row in rows]
        for index, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if index % 50 == 0:
                print(f"thumbnail {index}/{len(rows)} ok={sum(r['status']=='downloaded' for r in results)}", flush=True)
    results.sort(key=lambda item: item["video_id"])
    (OUT / "fresh_thumbnail_manifest.json").write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"total": len(results), "downloaded": sum(r["status"] == "downloaded" for r in results)}))


def probe(path: Path) -> dict:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=45,
    )
    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    return {
        "duration": number((payload.get("format") or {}).get("duration")),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "has_audio": any(item.get("codec_type") == "audio" for item in streams),
        "fps": str(video.get("r_frame_rate") or ""),
    }


def extract_frames(video_id: str, path: Path, duration: float) -> list[Path]:
    frame_dir = FRAMES / video_id
    frame_dir.mkdir(parents=True, exist_ok=True)
    positions = (0.0, 0.08, 0.20, 0.40, 0.65, 0.85, 0.97)
    outputs: list[Path] = []
    for index, fraction in enumerate(positions):
        destination = frame_dir / f"f{index}.jpg"
        outputs.append(destination)
        if destination.exists() and destination.stat().st_size > 1024:
            continue
        timestamp = max(0.0, min(duration - 0.05, duration * fraction)) if duration else 0.0
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
             "-i", str(path), "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "3", "-y", str(destination)],
            capture_output=True, timeout=90,
        )
    return [item for item in outputs if item.exists() and item.stat().st_size > 1024]


def frame_features(path: Path) -> dict:
    image = cv2.imread(str(path))
    if image is None:
        return {}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    height, width = gray.shape
    edges = cv2.Canny(gray, 80, 160)
    center = gray[int(height * .2):int(height * .8), int(width * .2):int(width * .8)]
    center_edges = edges[int(height * .2):int(height * .8), int(width * .2):int(width * .8)]
    return {
        "brightness": float(gray.mean() / 255),
        "contrast": float(gray.std() / 255),
        "saturation": float(hsv[:, :, 1].mean() / 255),
        "edge_density": float((edges > 0).mean()),
        "center_contrast": float(center.std() / 255),
        "center_edge_density": float((center_edges > 0).mean()),
        "text_density_proxy": float(((cv2.Sobel(gray, cv2.CV_32F, 1, 0) > 90).mean())),
    }


def analyze_one(row: dict) -> dict:
    video_id = str(row["video_id"])
    path = VIDEOS / f"{video_id}.mp4"
    base = {
        "video_id": video_id,
        "video_title": row.get("video_title", ""),
        "creative_name": row.get("creative_name", ""),
        "platforms": row.get("platforms", ""),
        "spend": number(row.get("spend")),
        "impressions": number(row.get("impressions")),
        "installs": number(row.get("installs")),
        "revenue": number(row.get("revenue")),
    }
    base["roas"] = base["revenue"] / base["spend"] if base["spend"] else 0.0
    base["cpi"] = base["spend"] / base["installs"] if base["installs"] else None
    base["payment_observed"] = base["revenue"] > 0
    if not path.exists():
        thumbnail = THUMBNAILS / f"{video_id}.jpg"
        features = frame_features(thumbnail) if thumbnail.exists() else {}
        if not features:
            return {**base, "analyzed": False, "analysis_scope": "none", "error": "video_and_thumbnail_missing"}
        return {
            **base,
            "analyzed": True,
            "analysis_scope": "thumbnail_only",
            "first_brightness": features["brightness"],
            "first_contrast": features["contrast"],
            "first_saturation": features["saturation"],
            "first_edge_density": features["edge_density"],
            "first_center_contrast": features["center_contrast"],
            "first_center_edge_density": features["center_edge_density"],
            "first_text_density": features["text_density_proxy"],
        }
    try:
        metadata = probe(path)
        frames = extract_frames(video_id, path, metadata["duration"])
        features = [frame_features(item) for item in frames]
        features = [item for item in features if item]
        if len(features) < 4:
            return {**base, **metadata, "analyzed": False, "error": "insufficient_frames"}
        first, early, middle, late = features[0], features[1], features[len(features)//2], features[-1]
        base.update(metadata)
        base.update({
            "analyzed": True,
            "analysis_scope": "full_video",
            "first_brightness": first["brightness"],
            "first_contrast": first["contrast"],
            "first_saturation": first["saturation"],
            "first_edge_density": first["edge_density"],
            "first_center_contrast": first["center_contrast"],
            "first_center_edge_density": first["center_edge_density"],
            "first_text_density": first["text_density_proxy"],
            "early_visual_change": abs(early["brightness"]-first["brightness"]) + abs(early["contrast"]-first["contrast"]) + abs(early["saturation"]-first["saturation"]),
            "reward_surge": max(0.0, late["brightness"]-middle["brightness"]) + max(0.0, late["saturation"]-middle["saturation"]),
            "late_brightness": late["brightness"],
            "late_saturation": late["saturation"],
            "mean_contrast": float(np.mean([item["contrast"] for item in features])),
            "mean_saturation": float(np.mean([item["saturation"] for item in features])),
        })
        return base
    except Exception as exc:
        return {**base, "analyzed": False, "error": f"{type(exc).__name__}:{str(exc)[:120]}"}


def archetype(text: str) -> str:
    value = text.lower()
    rules = [
        ("rescue_survival", ("help", "save", "survive", "freezing", "victim", "rescue")),
        ("progression_evolution", ("level", "evolution", "power", "queen", "empire", "kingdom")),
        ("collection_unlock", ("collect", "collection", "unlock", "summon", "rare")),
        ("social_romance", ("friend", "love", "romantic", "couple", "invited")),
        ("core_merge_gameplay", ("merge", "puzzle", "addictive", "challenge", "satisfying")),
        ("world_building", ("world", "adventure", "garden", "city", "home")),
    ]
    for label, words in rules:
        if any(word in value for word in words):
            return label
    return "other"


def stage_analyze(workers: int) -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    rows = load_raw_rows()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(analyze_one, row) for row in rows]
        for index, future in enumerate(as_completed(futures), 1):
            item = future.result()
            item["archetype"] = archetype(f"{item.get('video_title','')} {item.get('creative_name','')}")
            results.append(item)
            if index % 25 == 0:
                print(f"analyze {index}/{len(rows)} ok={sum(r.get('analyzed',False) for r in results)}", flush=True)
    results.sort(key=lambda item: item["video_id"])
    fields = sorted({key for item in results for key in item})
    with (OUT / "fresh_video_features.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(results)
    build_report(results)


def weighted_roas(items: list[dict]) -> float:
    spend = sum(item["spend"] for item in items)
    return sum(item["revenue"] for item in items) / spend if spend else 0.0


def build_report(results: list[dict]) -> None:
    analyzed = [item for item in results if item.get("analyzed")]
    full_video = [item for item in analyzed if item.get("analysis_scope") == "full_video"]
    thumbnail_only = [item for item in analyzed if item.get("analysis_scope") == "thumbnail_only"]
    paid = [item for item in analyzed if item["payment_observed"]]
    unpaid = [item for item in analyzed if not item["payment_observed"]]
    eligible_paid = [item for item in paid if item["spend"] >= 100]
    eligible_unpaid = [item for item in unpaid if item["spend"] >= 100]
    feature_names = [
        "first_brightness", "first_contrast", "first_saturation", "first_edge_density",
        "first_center_contrast", "first_center_edge_density", "first_text_density",
        "early_visual_change", "reward_surge", "mean_contrast", "mean_saturation",
    ]
    differences = []
    for name in feature_names:
        a = [number(item.get(name)) for item in eligible_paid if item.get(name) not in (None, "")]
        b = [number(item.get(name)) for item in eligible_unpaid if item.get(name) not in (None, "")]
        if a and b:
            differences.append({"feature": name, "paid_mean": float(np.mean(a)), "unpaid_mean": float(np.mean(b)), "difference": float(np.mean(a)-np.mean(b))})
    groups = []
    for label in sorted({item["archetype"] for item in analyzed}):
        items = [item for item in analyzed if item["archetype"] == label]
        groups.append({
            "archetype": label, "videos": len(items), "spend": sum(i["spend"] for i in items),
            "revenue": sum(i["revenue"] for i in items), "roas": weighted_roas(items),
            "payment_observed_rate": sum(i["payment_observed"] for i in items)/len(items),
        })
    report = {
        "provenance": {
            "raw_performance_source": str(RAW_CSV),
            "visual_source": "freshly downloaded original Meta video objects",
            "prior_reports_used": False,
            "analysis_date": "2026-08-04",
        },
        "coverage": {
            "raw_videos": len(results), "analyzed_assets": len(analyzed),
            "full_video_analyzed": len(full_video), "thumbnail_only_analyzed": len(thumbnail_only),
            "payment_observed": len(paid), "no_revenue_observed": len(unpaid),
            "eligible_paid_spend_ge_100": len(eligible_paid),
            "eligible_unpaid_spend_ge_100": len(eligible_unpaid),
        },
        "portfolio": {
            "spend": sum(i["spend"] for i in analyzed), "revenue": sum(i["revenue"] for i in analyzed),
            "roas": weighted_roas(analyzed),
        },
        "paid_vs_unpaid_visual_differences": sorted(differences, key=lambda x: abs(x["difference"]), reverse=True),
        "archetypes": sorted(groups, key=lambda x: x["spend"], reverse=True),
        "top_by_spend_with_payment": sorted(paid, key=lambda x: x["spend"], reverse=True)[:30],
        "top_by_spend_without_payment": sorted(unpaid, key=lambda x: x["spend"], reverse=True)[:30],
        "limitations": [
            "The raw 905-video export contains attributed revenue but not unique payer count.",
            "Payment observed means attributed revenue > 0; it is not a unique-payer label.",
            "Visual comparisons are observational and must be validated with controlled creative tests.",
        ],
    }
    (OUT / "fresh_payment_visual_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["coverage"], ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("download", "thumbnails", "analyze", "all"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.stage in ("download", "all"):
        stage_download(args.workers)
    if args.stage in ("thumbnails", "all"):
        stage_thumbnails(args.workers)
    if args.stage in ("analyze", "all"):
        stage_analyze(max(1, min(args.workers, 6)))


if __name__ == "__main__":
    main()
