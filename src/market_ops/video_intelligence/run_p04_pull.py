"""Pull P04 Witch videos from Facebook API (2025-11-01 ~ now).

Approach:
  1. Fetch ads with minimal fields (creative{id} only)
  2. Fetch creative details in batches (50 per batch)
  3. Filter P04, identify video creatives
  4. Download video source files
  5. Build video_metrics.json
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import requests as _requests

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def main():
    ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
    AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "").strip().removeprefix("act_")
    API_VERSION = os.environ.get("META_API_VERSION", "v19.0").strip()
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

    if not ACCESS_TOKEN or not AD_ACCOUNT_ID:
        print("ERROR: Missing META_ACCESS_TOKEN or META_AD_ACCOUNT_ID")
        return 1

    START_DATE = date(2025, 11, 1)
    END_DATE = date.today()

    output_override = os.environ.get("P04_VIDEO_OUTPUT_DIR", "").strip()
    OUTPUT_DIR = Path(output_override).resolve() if output_override else ROOT / "output" / "video_intelligence" / "p04"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR = OUTPUT_DIR / "videos"
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("P04 Video Intelligence Pull")
    print(f"  Account: act_{AD_ACCOUNT_ID}")
    print(f"  Date: {START_DATE} ~ {END_DATE}")
    print(f"  API: {API_VERSION}")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

    # ── Step 1: Fetch all ads with minimal creative info ──
    print("\n[1/5] Fetching all ads (minimal fields)...")
    ads = _get_paginated(
        BASE_URL, ACCESS_TOKEN,
        f"/act_{AD_ACCOUNT_ID}/ads",
        {
            "fields": "id,name,effective_status,campaign{id,name},adset{id,name},creative{id,name}",
            "limit": 500,
        },
    )
    print(f"  Total ads: {len(ads)}")

    # ── Step 2: Fetch insights (ad-level performance) ──
    print("\n[2/5] Fetching insights (2025-11-01 ~ now)...")
    insights = _get_paginated(
        BASE_URL, ACCESS_TOKEN,
        f"/act_{AD_ACCOUNT_ID}/insights",
        {
            "level": "ad",
            "time_range": json.dumps({"since": START_DATE.isoformat(), "until": END_DATE.isoformat()}),
            "fields": "ad_id,ad_name,campaign_name,adset_name,spend,impressions,clicks,ctr,actions,action_values,purchase_roas",
            "limit": 500,
        },
    )
    print(f"  Total insight rows: {len(insights)}")

    # Build ad_map: ad_id -> {campaign, adset, creative}
    ad_map: dict[str, dict] = {}
    creative_ids: set[str] = set()
    for ad in ads:
        ad_id = str(ad.get("id", ""))
        creative = ad.get("creative") or {}
        cid = str(creative.get("id", ""))
        ad_map[ad_id] = {
            "ad_name": str(ad.get("name", "")),
            "campaign": ad.get("campaign") or {},
            "adset": ad.get("adset") or {},
            "creative_id": cid,
            "creative_name": str(creative.get("name", "")),
        }
        if cid:
            creative_ids.add(cid)

    print(f"  Unique creative_ids: {len(creative_ids)}")

    # Build reverse map: creative_id -> ad_info
    creative_to_ad: dict[str, dict] = {}
    for ad_id, ad_info in ad_map.items():
        cid = ad_info.get("creative_id", "")
        if cid:
            if cid not in creative_to_ad:
                creative_to_ad[cid] = ad_info
            creative_to_ad[cid]["ad_id"] = creative_to_ad[cid].get("ad_id", "") or ad_id

    # ── Step 3: Batch fetch creative details (check if video) ──
    print(f"\n[3/5] Fetching creative details ({len(creative_ids)} creatives)...")
    creative_details: dict[str, dict] = {}
    cid_list = sorted(creative_ids)
    batch_size = 50
    for i in range(0, len(cid_list), batch_size):
        batch = cid_list[i:i + batch_size]
        try:
            r = _requests.get(
                f"{BASE_URL}/",
                params={
                    "ids": ",".join(batch),
                    "fields": "id,name,thumbnail_url,image_url,object_story_spec,video_id,asset_feed_spec",
                    "access_token": ACCESS_TOKEN,
                },
                timeout=120,
            )
            if r.status_code == 200:
                data = r.json()
                for cid_str, detail in (data or {}).items():
                    if isinstance(detail, dict):
                        creative_details[cid_str] = detail
        except Exception as exc:
            print(f"  Batch {i//batch_size + 1}: error - {exc}")
        if (i // batch_size + 1) % 10 == 0:
            print(f"  [{min(i + batch_size, len(cid_list))}/{len(cid_list)}] creatives fetched...")
        time.sleep(0.3)

    print(f"  Creative details fetched: {len(creative_details)}")

    # Merge insights by creative_id
    creative_metrics: dict[str, dict] = {}
    for row in insights:
        ad_id = str(row.get("ad_id", ""))
        ad_info = ad_map.get(ad_id, {})
        cid = ad_info.get("creative_id", "")
        if not cid:
            continue

        cm = creative_metrics.setdefault(cid, {
            "spend": 0.0, "impression": 0.0, "click": 0.0,
            "install": 0.0, "purchase": 0.0, "revenue": 0.0,
            "campaign_id": str((ad_info.get("campaign") or {}).get("id", "")),
            "adset_id": str((ad_info.get("adset") or {}).get("id", "")),
        })
        cm["spend"] += _to_float(row.get("spend"))
        cm["impression"] += _to_float(row.get("impressions"))
        cm["click"] += _to_float(row.get("clicks"))
        cm["install"] += _extract_action_value(row.get("actions"), "install")
        cm["purchase"] += _extract_action_value(row.get("actions"), "purchase")
        cm["revenue"] += _extract_action_value(row.get("action_values"), "purchase")

    print(f"  Creatives with metrics: {len(creative_metrics)}")

    # ── Step 4: Filter P04 + video creatives ──
    print("\n[4/5] Filtering P04 video creatives...")
    video_records: list[dict] = []
    metrics_list: list[dict] = []

    for cid, cm in creative_metrics.items():
        detail = creative_details.get(cid, {})
        ad_info = creative_to_ad.get(cid, {})

        # Check if video
        is_video = _is_video_creative(detail)
        if not is_video:
            continue

        # Check if P04 (from creative name or campaign name)
        creative_name = detail.get("name", "") or ad_info.get("creative_name", "")
        campaign_name = str((ad_info.get("campaign") or {}).get("name", ""))
        all_names = f"{creative_name} {campaign_name} {ad_info.get('ad_name', '')}"

        upper = all_names.upper()
        if not ("P04" in upper or "P4-" in upper or "P4 " in upper or "WITCH" in upper):
            continue

        source_video_id = _extract_video_id(detail)
        video_id = f"video_{source_video_id or cid}"
        source_url = _extract_video_source(BASE_URL, ACCESS_TOKEN, detail)

        # Compute derived metrics
        spend = cm["spend"]
        impression = cm["impression"]
        click = cm["click"]
        purchase = cm["purchase"]
        revenue = cm["revenue"]
        install = cm["install"]

        video_records.append({
            "video_id": video_id,
            "source_video_id": source_video_id,
            "creative_id": cid,
            "ad_id": ad_info.get("ad_id", ""),
            "adset_id": cm["adset_id"],
            "campaign_id": cm["campaign_id"],
            "creative_name": creative_name,
            "creative_type": "video",
            "video_url": source_url,
            "local_path": "",
            "thumbnail_url": detail.get("thumbnail_url", ""),
        })

        metrics_list.append({
            "video_id": video_id,
            "source_video_id": source_video_id,
            "creative_id": cid,
            "creative_name": creative_name,
            "spend": spend,
            "impression": impression,
            "click": click,
            "ctr": round(click / impression * 100, 4) if impression > 0 else 0,
            "cpc": round(spend / click, 4) if click > 0 else 0,
            "cpm": round(spend / impression * 1000, 4) if impression > 0 else 0,
            "install": install,
            "purchase": purchase,
            "revenue": revenue,
            "roas": round(revenue / spend, 4) if spend > 0 else 0,
            "ipm": round(install / impression * 1000, 4) if impression > 0 else 0,
            "cpa": round(spend / purchase, 4) if purchase > 0 else 0,
            "campaign_id": cm["campaign_id"],
            "adset_id": cm["adset_id"],
            "ad_id": ad_info.get("ad_id", ""),
        })

    print(f"  P04 video creatives: {len(video_records)}")

    # ── Step 5: Download videos ──
    print(f"\n[5/5] Downloading videos...")
    downloaded = 0
    for i, rec in enumerate(video_records):
        vid = rec["video_id"]
        local_path = VIDEOS_DIR / f"{vid}.mp4"

        if local_path.exists() and local_path.stat().st_size > 1024:
            rec["local_path"] = str(local_path)
            downloaded += 1
            continue

        source = rec["video_url"]
        if not source:
            continue

        try:
            resp = _requests.get(source, stream=True, timeout=300)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
            rec["local_path"] = str(local_path)
            downloaded += 1
            size_mb = local_path.stat().st_size / (1024 * 1024)
            if (i + 1) % 10 == 0 or size_mb > 10:
                print(f"  [{i+1}/{len(video_records)}] {vid} ({size_mb:.1f}MB)")
        except Exception as exc:
            print(f"  [{i+1}/{len(video_records)}] {vid} FAILED: {exc}")

    print(f"  Downloaded: {downloaded}/{len(video_records)}")

    # Save results
    records_path = OUTPUT_DIR / "video_records.json"
    records_path.write_text(json.dumps(video_records, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    metrics_path = OUTPUT_DIR / "video_metrics.json"
    metrics_path.write_text(json.dumps(metrics_list, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    total_spend = sum(m["spend"] for m in metrics_list)
    total_impressions = sum(m["impression"] for m in metrics_list)
    avg_ctr = sum(m["ctr"] for m in metrics_list) / len(metrics_list) if metrics_list else 0
    avg_roas = sum(m["roas"] for m in metrics_list) / len(metrics_list) if metrics_list else 0

    print(f"\n{'='*60}")
    print(f"P04 PULL COMPLETE")
    print(f"  P04 video creatives: {len(video_records)}")
    print(f"  Videos downloaded: {downloaded}")
    print(f"  Total spend: ${total_spend:,.0f}")
    print(f"  Total impressions: {total_impressions:,.0f}")
    print(f"  Avg CTR: {avg_ctr:.2f}%")
    print(f"  Avg ROAS: {avg_roas:.2f}")
    print(f"  Records: {records_path}")
    print(f"  Metrics: {metrics_path}")
    print(f"  Videos: {VIDEOS_DIR}")
    print(f"{'='*60}")
    return 0


def _get_paginated(base_url: str, token: str, path: str, params: dict, max_retries: int = 5) -> list[dict]:
    url = f"{base_url}{path}"
    results: list[dict] = []
    next_params: dict | None = dict(params)
    page = 0
    while url and page < 300:
        success = False
        for attempt in range(max_retries):
            try:
                resp = _requests.get(url, params=next_params, timeout=180)
                if resp.status_code == 200:
                    success = True
                    break
                if resp.status_code == 403 and "app ID" in resp.text:
                    print(f"  Transient 403, retry {attempt+1}/{max_retries}...")
                    time.sleep(3 * (attempt + 1))
                    continue
                print(f"  API error (page {page}): {resp.status_code} {resp.text[:300]}")
                return results
            except Exception as exc:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                print(f"  Pagination error (page {page}): {exc}")
                return results

        if not success:
            print(f"  Max retries exceeded for page {page}")
            return results

        payload = resp.json()
        if "error" in payload:
            print(f"  API error: {payload['error']}")
            break
        results.extend(payload.get("data", []))
        paging = payload.get("paging") or {}
        url = paging.get("next", "") or ""
        next_params = None
        page += 1
        if page % 5 == 0:
            print(f"  Page {page}: {len(results)} rows total...")
            time.sleep(1)
    return results


def _is_video_creative(creative: dict) -> bool:
    if not creative:
        return False
    if creative.get("video_id"):
        return True
    story_spec = creative.get("object_story_spec") or {}
    if story_spec.get("video_data"):
        return True
    asset_spec = creative.get("asset_feed_spec") or {}
    for body in asset_spec.get("bodies", []):
        if body.get("video_id"):
            return True
    return False


def _extract_video_source(base_url: str, token: str, creative: dict) -> str:
    if not creative:
        return ""
    video_id = _extract_video_id(creative)
    if not video_id:
        asset_spec = creative.get("asset_feed_spec") or {}
        for body in asset_spec.get("bodies", []):
            if body.get("video_id"):
                video_id = body["video_id"]
                break
    if not video_id:
        return ""
    try:
        resp = _requests.get(
            f"{base_url}/{video_id}",
            params={"access_token": token, "fields": "source,picture"},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("source", "")
    except Exception:
        return ""


def _extract_video_id(creative: dict) -> str:
    """Return the actual story video object before creative-level preview IDs."""
    if not creative:
        return ""
    story_spec = creative.get("object_story_spec") or {}
    video_data = story_spec.get("video_data") or {}
    video_id = str(video_data.get("video_id", "") or "")
    if video_id:
        return video_id
    asset_spec = creative.get("asset_feed_spec") or {}
    for item in asset_spec.get("videos", []):
        video_id = str(item.get("video_id", "") or "")
        if video_id:
            return video_id
    for item in asset_spec.get("bodies", []):
        video_id = str(item.get("video_id", "") or "")
        if video_id:
            return video_id
    return str(creative.get("video_id", "") or "")


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_action_value(actions: Any, key_pattern: str) -> float:
    if not isinstance(actions, list):
        return 0.0
    total = 0.0
    for item in actions:
        if not isinstance(item, dict):
            continue
        action_type = str(item.get("action_type", "")).lower()
        if key_pattern in action_type or action_type == f"omni_{key_pattern}":
            total += _to_float(item.get("value"))
    return total


if __name__ == "__main__":
    sys.exit(main())
