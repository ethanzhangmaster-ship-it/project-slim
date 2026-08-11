"""Fresh analysis of original P04 MP4s joined to raw Facebook performance rows."""

from __future__ import annotations

import csv
import json
import math
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "output" / "p04_all_905_facebook_videos.csv"
OUT = ROOT / "output" / "video_reanalysis_20260804"
FRAME_ROOT = OUT / "fresh_local_frames"
SOURCE_PARENT = Path("D:/project_slim/output/P04_remix_videos")


def source_dir() -> Path:
    candidates = [item for item in SOURCE_PARENT.iterdir() if item.is_dir()]
    candidates.sort(key=lambda item: len(list(item.glob("*.mp4"))), reverse=True)
    if not candidates or len(list(candidates[0].glob("*.mp4"))) < 100:
        raise RuntimeError("Original P04 source directory not found")
    return candidates[0]


def num(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def raw_performance() -> tuple[dict[str, dict], dict]:
    with RAW.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[str, dict] = {}
    unmapped = []
    duration_rejected = []
    local_durations: dict[str, float] = {}
    for path in source_dir().glob("*.mp4"):
        version = version_from_path(path)
        match = re.search(r"-([0-9]+)s-", path.stem, re.I)
        if version and match:
            local_durations.setdefault(version, float(match.group(1)))
    for row in rows:
        match = re.search(r"(?:^|[-_])A([0-9]{1,4})(?:[-_]|$)", row.get("ad_name", ""), re.I)
        if not match:
            unmapped.append(row["video_id"])
            continue
        version = str(int(match.group(1)))
        raw_duration = num(row.get("duration_sec"))
        local_duration = local_durations.get(version)
        if raw_duration and local_duration and abs(raw_duration-local_duration) > 1.1:
            duration_rejected.append(row["video_id"])
            continue
        item = grouped.setdefault(version, {
            "version": version, "fb_video_objects": set(), "spend": 0.0, "revenue": 0.0,
            "installs": 0.0, "impressions": 0.0, "titles": set(), "platforms": set(),
        })
        item["fb_video_objects"].add(row["video_id"])
        item["titles"].add(row.get("video_title", ""))
        item["platforms"].update(v.strip() for v in row.get("platforms", "").split(",") if v.strip())
        for field in ("spend", "revenue", "installs", "impressions"):
            item[field] += num(row.get(field))
    for item in grouped.values():
        item["fb_video_object_count"] = len(item.pop("fb_video_objects"))
        item["titles"] = sorted(item["titles"])
        item["platforms"] = sorted(item["platforms"])
        item["roas"] = item["revenue"] / item["spend"] if item["spend"] else 0.0
        item["cpi"] = item["spend"] / item["installs"] if item["installs"] else None
    return grouped, {"raw_rows": len(rows), "mapped_rows": len(rows)-len(unmapped)-len(duration_rejected), "unmapped_rows": len(unmapped), "duration_mismatch_rows": len(duration_rejected), "unmapped_video_ids": unmapped, "duration_mismatch_video_ids": duration_rejected}


def version_from_path(path: Path) -> str | None:
    match = re.search(r"v([0-9]{7})", path.stem, re.I)
    return str(int(match.group(1)[-3:])) if match else None


def classify(path: Path) -> str:
    value = path.stem.lower()
    rules = (
        ("character_showcase", ("juesezhanshi", "bianshen")),
        ("story", ("juqing",)),
        ("opening_hook", ("kaitou",)),
        ("gameplay", ("wanfashipin", "wanfazhanshi")),
        ("scrolling_text", ("wenzigundong",)),
        ("scene_showcase", ("changjingzhanshi",)),
        ("egg_hatch", ("fudan",)),
    )
    for label, tokens in rules:
        if any(token in value for token in tokens):
            return label
    return "other"


def ratio_from_path(path: Path) -> str:
    value = path.stem.upper()
    for ratio in ("9X16", "1X1", "16X9"):
        if ratio in value:
            return ratio
    return "unknown"


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=45,
    )
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    return {
        "duration": num((payload.get("format") or {}).get("duration")),
        "width": int(video.get("width") or 0), "height": int(video.get("height") or 0),
        "has_audio": any(item.get("codec_type") == "audio" for item in streams),
    }


def frames(path: Path, duration: float) -> list[Path]:
    target = FRAME_ROOT / path.stem
    target.mkdir(parents=True, exist_ok=True)
    outputs = []
    for index, fraction in enumerate((0.0, .06, .15, .30, .50, .72, .88, .97)):
        output = target / f"f{index}.jpg"
        outputs.append(output)
        if output.exists() and output.stat().st_size > 1024:
            continue
        timestamp = max(0.1, min(duration - .04, duration * fraction))
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}", "-i", str(path),
             "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "3", "-y", str(output)],
            capture_output=True, timeout=75,
        )
    return [item for item in outputs if item.exists() and item.stat().st_size > 1024]


def visual(path: Path) -> dict:
    try:
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError:
        image = None
    if image is None:
        return {}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    edge = cv2.Canny(gray, 80, 160)
    h, w = gray.shape
    center = gray[int(h*.2):int(h*.8), int(w*.2):int(w*.8)]
    center_edge = edge[int(h*.2):int(h*.8), int(w*.2):int(w*.8)]
    return {
        "brightness": float(gray.mean()/255), "contrast": float(gray.std()/255),
        "saturation": float(hsv[:,:,1].mean()/255), "edge_density": float((edge>0).mean()),
        "center_contrast": float(center.std()/255), "center_edge_density": float((center_edge>0).mean()),
        "text_density": float((np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0))>90).mean()),
    }


def analyze(path: Path, performance: dict[str, dict]) -> dict:
    version = version_from_path(path)
    result = {
        "source_file": path.name, "source_path": str(path), "version": version,
        "content_type": classify(path), "ratio": ratio_from_path(path),
    }
    try:
        metadata = probe(path)
        images = frames(path, metadata["duration"])
        feats = [visual(item) for item in images]
        feats = [item for item in feats if item]
        if len(feats) < 5:
            raise RuntimeError("insufficient_frames")
        first, second, middle, late = feats[0], feats[1], feats[len(feats)//2], feats[-1]
        result.update(metadata)
        result.update({
            "analyzed": True,
            "first_brightness": first["brightness"], "first_contrast": first["contrast"],
            "first_saturation": first["saturation"], "first_edge_density": first["edge_density"],
            "first_center_contrast": first["center_contrast"],
            "first_center_edge_density": first["center_edge_density"], "first_text_density": first["text_density"],
            "early_visual_change": sum(abs(second[key]-first[key]) for key in ("brightness","contrast","saturation","edge_density")),
            "reward_surge": max(0.,late["brightness"]-middle["brightness"])+max(0.,late["saturation"]-middle["saturation"]),
            "mean_brightness": float(np.mean([x["brightness"] for x in feats])),
            "mean_contrast": float(np.mean([x["contrast"] for x in feats])),
            "mean_saturation": float(np.mean([x["saturation"] for x in feats])),
            "visual_variation": float(np.mean([np.std([x[key] for x in feats]) for key in ("brightness","contrast","saturation","edge_density")])),
        })
    except Exception as exc:
        result.update(analyzed=False, error=f"{type(exc).__name__}:{str(exc)[:120]}")
    perf = performance.get(version or "")
    result["performance_mapped"] = bool(perf)
    if perf:
        result.update({key: value for key, value in perf.items() if key != "version"})
        result["payment_observed"] = perf["revenue"] > 0
        result["evidence_tier"] = "decision_eligible" if perf["spend"] >= 100 else "low_spend"
    else:
        result.update(spend=0., revenue=0., installs=0., impressions=0., roas=0., payment_observed=None, evidence_tier="no_performance_mapping")
    return result


def mean(items: list[dict], field: str) -> float | None:
    values = [num(item.get(field)) for item in items if item.get(field) not in (None, "")]
    return float(np.mean(values)) if values else None


def weighted_roas(items: list[dict]) -> float:
    spend = sum(num(item.get("spend")) for item in items)
    return sum(num(item.get("revenue")) for item in items)/spend if spend else 0.


def contact_sheet(items: list[dict], destination: Path, title: str) -> None:
    chosen = items[:12]
    canvas = Image.new("RGB", (1440, 1280), (24, 20, 35))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 30)
    draw.text((30, 20), title, font=bold, fill=(255, 230, 110))
    for index, item in enumerate(chosen):
        row, col = divmod(index, 4)
        frame = FRAME_ROOT / Path(item["source_file"]).stem / "f0.jpg"
        if not frame.exists(): continue
        image = Image.open(frame).convert("RGB")
        image.thumbnail((330, 275))
        x, y = 25+col*355, 75+row*395
        canvas.paste(image, (x, y))
        text = f"{item['version']} {item['content_type']}\nSpend ${item['spend']:.0f}  ROAS {item['roas']:.2f}\nRev ${item['revenue']:.0f}  {item['ratio']}"
        draw.multiline_text((x, y+285), text, font=font, fill="white", spacing=4)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=92)


def report(results: list[dict], raw_stats: dict) -> None:
    analyzed = [item for item in results if item.get("analyzed")]
    mapped_candidates = [item for item in analyzed if item.get("performance_mapped")]
    mapped_by_version: dict[str, dict] = {}
    for item in mapped_candidates:
        mapped_by_version.setdefault(str(item.get("version") or item["source_file"]), item)
    mapped = list(mapped_by_version.values())
    eligible = [item for item in mapped if item.get("evidence_tier") == "decision_eligible"]
    paid = [item for item in eligible if item.get("payment_observed")]
    unpaid = [item for item in eligible if not item.get("payment_observed")]
    features = ("first_brightness","first_contrast","first_saturation","first_edge_density","first_center_contrast","first_center_edge_density","first_text_density","early_visual_change","reward_surge","mean_brightness","mean_contrast","mean_saturation","visual_variation")
    comparisons=[]
    for feature in features:
        p, n = mean(paid, feature), mean(unpaid, feature)
        if p is not None and n is not None:
            paid_values=np.array([num(x.get(feature)) for x in paid if x.get(feature) not in (None,"")],dtype=float)
            unpaid_values=np.array([num(x.get(feature)) for x in unpaid if x.get(feature) not in (None,"")],dtype=float)
            pooled=math.sqrt(((len(paid_values)-1)*paid_values.var(ddof=1)+(len(unpaid_values)-1)*unpaid_values.var(ddof=1))/max(1,len(paid_values)+len(unpaid_values)-2))
            rng=np.random.default_rng(20260804)
            boots=np.array([rng.choice(paid_values,len(paid_values),replace=True).mean()-rng.choice(unpaid_values,len(unpaid_values),replace=True).mean() for _ in range(3000)])
            observed=p-n
            combined=np.concatenate([paid_values,unpaid_values])
            exceed=0
            for _ in range(3000):
                shuffled=rng.permutation(combined)
                delta=shuffled[:len(paid_values)].mean()-shuffled[len(paid_values):].mean()
                exceed += abs(delta)>=abs(observed)
            comparisons.append({"feature":feature,"paid_mean":p,"unpaid_mean":n,"difference":observed,"relative_difference":(p-n)/n if n else None,"cohens_d":observed/pooled if pooled else None,"bootstrap_ci95":[float(np.quantile(boots,.025)),float(np.quantile(boots,.975))],"permutation_p":(exceed+1)/3001})
    types=[]
    for label in sorted({item["content_type"] for item in mapped}):
        group=[item for item in mapped if item["content_type"]==label]
        types.append({"content_type":label,"videos":len(group),"spend":sum(x["spend"] for x in group),"revenue":sum(x["revenue"] for x in group),"roas":weighted_roas(group),"payment_observed_rate":sum(bool(x["payment_observed"]) for x in group)/len(group)})
    eligible_groups={}
    for field in ("content_type","ratio"):
        rows=[]
        for label in sorted({str(item.get(field) or "unknown") for item in eligible}):
            group=[item for item in eligible if str(item.get(field) or "unknown")==label]
            rows.append({field:label,"videos":len(group),"paid_videos":sum(bool(x["payment_observed"]) for x in group),"spend":sum(x["spend"] for x in group),"revenue":sum(x["revenue"] for x in group),"roas":weighted_roas(group)})
        eligible_groups[field]=sorted(rows,key=lambda x:x["spend"],reverse=True)
    paid_rank=sorted([x for x in mapped if x.get("payment_observed")],key=lambda x:x["spend"],reverse=True)
    unpaid_rank=sorted([x for x in mapped if not x.get("payment_observed")],key=lambda x:x["spend"],reverse=True)
    payload={
        "provenance":{"prior_reports_used":False,"performance_source":str(RAW),"visual_source":str(source_dir()),"frames":"freshly extracted in this run"},
        "coverage":{**raw_stats,"original_source_videos":len(results),"visual_analyzed":len(analyzed),"performance_mapped_source_videos":len(mapped),"decision_eligible_spend_ge_100":len(eligible),"eligible_paid":len(paid),"eligible_no_revenue":len(unpaid)},
        "portfolio":{"spend":sum(x["spend"] for x in mapped),"revenue":sum(x["revenue"] for x in mapped),"roas":weighted_roas(mapped)},
        "paid_vs_no_revenue_visual":sorted(comparisons,key=lambda x:abs(x["difference"]),reverse=True),
        "content_type_performance":sorted(types,key=lambda x:x["spend"],reverse=True),
        "decision_eligible_group_performance":eligible_groups,
        "top_paid_by_spend":paid_rank[:40],"top_no_revenue_by_spend":unpaid_rank[:40],
        "interpretation_rules":["Revenue > 0 means attributed payment revenue was observed.","Revenue = 0 is only treated as negative evidence when spend >= 100.","Associations are not causal; final scripts require controlled testing."],
    }
    (OUT/"fresh_original_video_payment_analysis.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    fields=sorted({key for item in results for key in item})
    with (OUT/"fresh_original_video_features.csv").open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader(); writer.writerows(results)
    contact_sheet(paid_rank,OUT/"contact_sheet_paid_top12.jpg","TOP PAID-REVENUE ORIGINAL VIDEOS")
    contact_sheet(unpaid_rank,OUT/"contact_sheet_no_revenue_top12.jpg","TOP SPEND WITH NO OBSERVED REVENUE")
    print(json.dumps(payload["coverage"],ensure_ascii=False))


def main() -> None:
    OUT.mkdir(parents=True,exist_ok=True); FRAME_ROOT.mkdir(parents=True,exist_ok=True)
    performance,raw_stats=raw_performance()
    paths=sorted(source_dir().glob("*.mp4"))
    results=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(analyze,path,performance) for path in paths]
        for index,future in enumerate(as_completed(futures),1):
            results.append(future.result())
            if index%20==0: print(f"fresh analyze {index}/{len(paths)} ok={sum(x.get('analyzed',False) for x in results)}",flush=True)
    results.sort(key=lambda item:item["source_file"])
    report(results,raw_stats)


if __name__=="__main__":
    main()
