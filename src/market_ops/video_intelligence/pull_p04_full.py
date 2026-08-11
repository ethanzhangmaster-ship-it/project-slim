"""Pull ALL P04 Witch Facebook data from all 4 accounts (2025-11-01 ~ 2026-07-09).

Full hierarchy: Account → Campaign → Adset → Ad → Creative
- No effective_status filtering (get ALL ads including paused/deleted)
- Include names and IDs at every level
- Time range: 2025-11-01 to 2026-07-09

Output:
  output/video_intelligence/p04/full_export_all_accounts_complete.json
  output/video_intelligence/p04/p04_full_ad_hierarchy.csv
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
            os.environ[_k.strip()] = _v.strip()


ACCOUNTS = [
    {"id": "1379499207181514", "name": "iOS-2 (260312)", "label": "GAMEGZZ_Tec_Do_04_260312_IOS_2"},
    {"id": "1423660739468966", "name": "iOS-1 (260115)", "label": "GAMEGZZ_Tec_Do_04_260115_IOS_1"},
    {"id": "1455525822955003", "name": "AND-1 (260115)", "label": "GAMEGZZ_Tec_Do_04_260115_AND_1"},
    {"id": "1628583695016910", "name": "iOS-3 (260312)", "label": "GAMEGZZ_Tec_Do_04_260312_IOS_3"},
]

START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 7, 9)
API_VERSION = "v19.0"


def main():
    ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
    if not ACCESS_TOKEN:
        print("ERROR: Missing META_ACCESS_TOKEN")
        return 1

    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
    OUTPUT_DIR = ROOT / "output" / "video_intelligence" / "p04"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("P04 FULL DATA PULL — All 4 Accounts")
    print(f"  Date: {START_DATE} ~ {END_DATE}")
    print(f"  Accounts: {[a['name'] for a in ACCOUNTS]}")
    print("=" * 70)

    # ── Step 1: Pull all ads from all accounts (NO status filter) ──
    print("\n[1/6] Pulling all ads from all 4 accounts (no status filter)...")
    all_ads_by_account: dict[str, list] = {}
    for acc in ACCOUNTS:
        acc_id = acc["id"]
        print(f"\n  [{acc['name']}] Fetching ads...")
        ads = _get_paginated(
            BASE_URL, ACCESS_TOKEN,
            f"/act_{acc_id}/ads",
            {
                "fields": (
                    "id,name,effective_status,"
                    "campaign{id,name,objective},"
                    "adset{id,name},"
                    "creative{id,name}"
                ),
                "limit": 500,
            },
        )
        all_ads_by_account[acc_id] = ads
        print(f"  [{acc['name']}] Total ads: {len(ads)}")

    # ── Step 2: Pull insights from all accounts ──
    print("\n[2/6] Pulling insights from all 4 accounts...")
    all_insights_by_account: dict[str, list] = {}
    time_range = json.dumps({"since": START_DATE.isoformat(), "until": END_DATE.isoformat()})

    for acc in ACCOUNTS:
        acc_id = acc["id"]
        print(f"\n  [{acc['name']}] Fetching insights...")
        insights = _get_paginated(
            BASE_URL, ACCESS_TOKEN,
            f"/act_{acc_id}/insights",
            {
                "level": "ad",
                "time_range": time_range,
                "fields": (
                    "ad_id,ad_name,campaign_id,campaign_name,"
                    "adset_id,adset_name,spend,impressions,clicks,ctr,"
                    "actions,action_values,purchase_roas,"
                    "cost_per_action_type,cpc,cpm"
                ),
                "limit": 500,
            },
        )
        all_insights_by_account[acc_id] = insights
        print(f"  [{acc['name']}] Insight rows: {len(insights)}")

    # ── Step 3: Pull campaign & adset-level insights ──
    print("\n[3/6] Pulling campaign & adset insights...")
    campaign_insights: dict[str, dict] = {}
    adset_insights: dict[str, dict] = {}

    for acc in ACCOUNTS:
        acc_id = acc["id"]
        print(f"\n  [{acc['name']}] Fetching campaign-level insights...")
        ci = _get_paginated(
            BASE_URL, ACCESS_TOKEN,
            f"/act_{acc_id}/insights",
            {
                "level": "campaign",
                "time_range": time_range,
                "fields": "campaign_id,campaign_name,spend,impressions,clicks,actions,action_values",
                "limit": 500,
            },
        )
        for row in ci:
            cid = str(row.get("campaign_id", ""))
            if cid:
                campaign_insights[cid] = row

        print(f"  [{acc['name']}] Fetching adset-level insights...")
        ai = _get_paginated(
            BASE_URL, ACCESS_TOKEN,
            f"/act_{acc_id}/insights",
            {
                "level": "adset",
                "time_range": time_range,
                "fields": "adset_id,adset_name,campaign_id,spend,impressions,actions,action_values",
                "limit": 500,
            },
        )
        for row in ai:
            asid = str(row.get("adset_id", ""))
            if asid:
                adset_insights[asid] = row

    print(f"  Total campaigns with insights: {len(campaign_insights)}")
    print(f"  Total adsets with insights: {len(adset_insights)}")

    # ── Step 4: Collect all creative IDs ──
    print("\n[4/6] Collecting creative IDs from all accounts...")
    creative_ids_by_account: dict[str, set] = {}
    ad_to_hierarchy: dict[str, dict] = {}

    for acc in ACCOUNTS:
        acc_id = acc["id"]
        creative_ids_by_account[acc_id] = set()
        for ad in all_ads_by_account.get(acc_id, []):
            ad_id = str(ad.get("id", ""))
            creative = ad.get("creative") or {}
            cid = str(creative.get("id", ""))
            campaign = ad.get("campaign") or {}
            adset = ad.get("adset") or {}
            if cid:
                creative_ids_by_account[acc_id].add(cid)
            ad_to_hierarchy[ad_id] = {
                "account_id": acc_id,
                "account_name": acc["label"],
                "ad_name": str(ad.get("name", "")),
                "effective_status": str(ad.get("effective_status", "")),
                "campaign_id": str(campaign.get("id", "")),
                "campaign_name": str(campaign.get("name", "")),
                "campaign_objective": str(campaign.get("objective", "")),
                "adset_id": str(adset.get("id", "")),
                "adset_name": str(adset.get("name", "")),
                "creative_id": cid,
                "creative_name": str(creative.get("name", "")),
            }

    for acc_id, cids in creative_ids_by_account.items():
        print(f"  {acc_id}: {len(cids)} unique creatives")

    # ── Step 5: Batch fetch creative details ──
    print("\n[5/6] Fetching creative details (batch, all accounts)...")
    creative_details: dict[str, dict] = {}

    for acc in ACCOUNTS:
        acc_id = acc["id"]
        cid_list = sorted(creative_ids_by_account.get(acc_id, []))
        if not cid_list:
            continue
        print(f"  [{acc['name']}] Fetching {len(cid_list)} creative details...")
        batch_size = 50
        fetched = 0
        for i in range(0, len(cid_list), batch_size):
            batch = cid_list[i:i + batch_size]
            try:
                r = _requests.get(
                    f"{BASE_URL}/",
                    params={
                        "ids": ",".join(batch),
                        "fields": (
                            "id,name,thumbnail_url,image_url,"
                            "object_story_spec,video_id,asset_feed_spec,"
                            "applink_treatment"
                        ),
                        "access_token": ACCESS_TOKEN,
                    },
                    timeout=120,
                )
                if r.status_code == 200:
                    data = r.json()
                    for cid_str, detail in (data or {}).items():
                        if isinstance(detail, dict):
                            creative_details[cid_str] = detail
                            fetched += 1
            except Exception as exc:
                print(f"    Batch error: {exc}")
            if (i // batch_size + 1) % 10 == 0:
                print(f"    [{min(i + batch_size, len(cid_list))}/{len(cid_list)}]...")
            time.sleep(0.3)
        print(f"  [{acc['name']}] Fetched {fetched} creative details")

    print(f"  Total creative details: {len(creative_details)}")

    # ── Step 6: Build full hierarchy records ──
    print("\n[6/6] Building full hierarchy and P04 filter...")

    # Group insights by ad_id first
    insights_by_ad: dict[str, dict] = {}
    for acc in ACCOUNTS:
        acc_id = acc["id"]
        for row in all_insights_by_account.get(acc_id, []):
            ad_id = str(row.get("ad_id", ""))
            if ad_id:
                insights_by_ad[ad_id] = row

    # Build full records
    all_records: list[dict] = []
    p04_records: list[dict] = []
    video_records: list[dict] = []

    for acc in ACCOUNTS:
        acc_id = acc["id"]
        for ad in all_ads_by_account.get(acc_id, []):
            ad_id = str(ad.get("id", ""))
            hierarchy = ad_to_hierarchy.get(ad_id, {})
            creative = ad.get("creative") or {}
            cid = hierarchy.get("creative_id", "")
            creative_name = hierarchy.get("creative_name", "")
            campaign_name = hierarchy.get("campaign_name", "")
            adset_name = hierarchy.get("adset_name", "")
            ad_name = hierarchy.get("ad_name", "")

            # P04 filter
            upper = f"{creative_name} {campaign_name} {adset_name} {ad_name}".upper()
            is_p04 = "P04" in upper or "P4-" in upper or "P4 " in upper or "WITCH" in upper

            # Insights
            insight = insights_by_ad.get(ad_id, {})
            spend = _to_float(insight.get("spend"))
            impressions = _to_float(insight.get("impressions"))
            clicks = _to_float(insight.get("clicks"))
            ctr = _to_float(insight.get("ctr"))
            cpc = _to_float(insight.get("cpc"))
            cpm = _to_float(insight.get("cpm"))

            install = _extract_action_value(insight.get("actions"), "install")
            purchase = _extract_action_value(insight.get("actions"), "purchase")
            revenue = _extract_action_value(insight.get("action_values"), "purchase")
            roas = round(revenue / spend, 4) if spend > 0 else 0.0
            cpa = round(spend / purchase, 4) if purchase > 0 else 0.0

            # Creative details
            detail = creative_details.get(cid, {})
            is_video = _is_video_creative(detail)
            video_id_str = detail.get("video_id", "")
            thumbnail = detail.get("thumbnail_url", "")
            video_source = _get_video_source(BASE_URL, ACCESS_TOKEN, detail)

            record = {
                "account_id": acc_id,
                "account_name": acc["label"],
                "campaign_id": hierarchy.get("campaign_id", ""),
                "campaign_name": campaign_name,
                "adset_id": hierarchy.get("adset_id", ""),
                "adset_name": adset_name,
                "ad_id": ad_id,
                "ad_name": ad_name,
                "effective_status": hierarchy.get("effective_status", ""),
                "creative_id": cid,
                "creative_name": creative_name,
                "creative_type": "video" if is_video else "image",
                "video_id": video_id_str,
                "thumbnail_url": thumbnail,
                "video_source_url": video_source,
                "is_p04": is_p04,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
                "cpc": cpc,
                "cpm": cpm,
                "installs": install,
                "purchases": purchase,
                "revenue": revenue,
                "roas": roas,
                "cpa": cpa,
            }
            all_records.append(record)

            if is_p04:
                p04_records.append(record)
                if is_video:
                    video_records.append(record)

    print(f"  All ads: {len(all_records)}")
    print(f"  P04 ads: {len(p04_records)}")
    print(f"  P04 video ads: {len(video_records)}")

    # Summary by account
    print("\n  P04 spend by account:")
    for acc in ACCOUNTS:
        acc_id = acc["id"]
        acc_spend = sum(r["spend"] for r in p04_records if r["account_id"] == acc_id)
        acc_imp = sum(r["impressions"] for r in p04_records if r["account_id"] == acc_id)
        print(f"    {acc['label']}: spend=${acc_spend:,.2f}, impressions={int(acc_imp):,}")

    # Save full JSON
    full_json_path = OUTPUT_DIR / "p04_full_ad_hierarchy.json"
    full_json_path.write_text(
        json.dumps({
            "pull_date": str(END_DATE),
            "start_date": str(START_DATE),
            "end_date": str(END_DATE),
            "accounts": ACCOUNTS,
            "total_ads": len(all_records),
            "p04_ads": len(p04_records),
            "p04_video_ads": len(video_records),
            "records": p04_records,
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )
    print(f"\n  Saved: {full_json_path}")

    # Save CSV
    csv_path = OUTPUT_DIR / "p04_full_ad_hierarchy.csv"
    _save_csv(p04_records, csv_path)
    print(f"  Saved: {csv_path}")

    # Summary
    total_spend = sum(r["spend"] for r in p04_records)
    total_imp = sum(r["impressions"] for r in p04_records)
    total_rev = sum(r["revenue"] for r in p04_records)
    print(f"\n{'='*70}")
    print(f"P04 FULL PULL COMPLETE")
    print(f"  Total ads (all accounts): {len(all_records)}")
    print(f"  P04 ads: {len(p04_records)}")
    print(f"  P04 video ads: {len(video_records)}")
    print(f"  Total P04 spend: ${total_spend:,.2f}")
    print(f"  Total P04 impressions: {int(total_imp):,}")
    print(f"  Total P04 revenue: ${total_rev:,.2f}")
    print(f"  P04 ROAS: {total_rev/total_spend:.4f}" if total_spend > 0 else "  P04 ROAS: N/A")
    print(f"{'='*70}")
    return 0


def _get_paginated(base_url: str, token: str, path: str, params: dict, max_retries: int = 5) -> list[dict]:
    url = f"{base_url}{path}"
    results: list[dict] = []
    next_params: dict | None = dict(params)
    next_params["access_token"] = token
    page = 0
    while url and page < 500:
        success = False
        for attempt in range(max_retries):
            try:
                resp = _requests.get(url, params=next_params, timeout=180)
                if resp.status_code == 200:
                    success = True
                    break
                if resp.status_code in (400, 500) and attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                print(f"  API error (page {page}): {resp.status_code} {resp.text[:200]}")
                return results
            except Exception as exc:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                print(f"  Error (page {page}): {exc}")
                return results
        if not success:
            return results
        payload = resp.json()
        if "error" in payload:
            err = payload["error"]
            print(f"  API error: {err.get('message', err)}")
            break
        results.extend(payload.get("data", []))
        paging = payload.get("paging") or {}
        url = paging.get("next", "") or ""
        next_params = None
        page += 1
        if page % 10 == 0:
            print(f"    Page {page}: {len(results)} rows...")
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
    for vid in asset_spec.get("videos", []):
        if vid.get("video_id"):
            return True
    return False


def _get_video_source(base_url: str, token: str, creative: dict) -> str:
    if not creative:
        return ""
    video_id = creative.get("video_id", "")
    if not video_id:
        story_spec = creative.get("object_story_spec") or {}
        video_data = story_spec.get("video_data") or {}
        video_id = video_data.get("video_id", "")
    if not video_id:
        asset_spec = creative.get("asset_feed_spec") or {}
        for body in asset_spec.get("bodies", []):
            if body.get("video_id"):
                video_id = body["video_id"]
                break
        if not video_id:
            for vid in asset_spec.get("videos", []):
                if vid.get("video_id"):
                    video_id = vid["video_id"]
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


def _to_float(value: Any) -> float:
    if value in (None, "", "nan"):
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


def _save_csv(records: list[dict], path: Path):
    if not records:
        path.write_text("", encoding="utf-8")
        return
    import csv
    fieldnames = [
        "account_name", "account_id",
        "campaign_name", "campaign_id",
        "adset_name", "adset_id",
        "ad_name", "ad_id",
        "effective_status",
        "creative_name", "creative_id", "creative_type",
        "video_id", "thumbnail_url",
        "spend", "impressions", "clicks", "ctr", "cpc", "cpm",
        "installs", "purchases", "revenue", "roas", "cpa",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    sys.exit(main())
