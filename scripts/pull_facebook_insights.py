#!/usr/bin/env python3
"""Pull Facebook Ads Insights for P04, merge with Adjust data by ad_id."""
import csv
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("FB_TOKEN", "") or os.environ.get("META_ACCESS_TOKEN", "")
VERSION = os.environ.get("META_API_VERSION", "v19.0")

# P04 accounts (ALL 10 accounts found via audit)
P04_ACCOUNTS = [
    # Original 5
    {"id": "1959429141294402", "name": "P04 And 1", "platform": "Android"},
    {"id": "1455525822955003", "name": "P04 And 2", "platform": "Android"},
    {"id": "1379499207181514", "name": "P04 iOS 1", "platform": "iOS"},
    {"id": "1423660739468966", "name": "P04 iOS 2", "platform": "iOS"},
    {"id": "1628583695016910", "name": "P04 iOS 3", "platform": "iOS"},
    # Missing accounts found via audit
    {"id": "2068461353924819", "name": "P04 iOS 6", "platform": "iOS"},
    {"id": "1868794510383229", "name": "P04 iOS 7", "platform": "iOS"},
    {"id": "2736817463332226", "name": "P04 Connect", "platform": "iOS"},
    {"id": "1784471669598847", "name": "P04 And 3", "platform": "Android"},
    {"id": "820201270652176", "name": "P04 And Adtiger", "platform": "Android"},
]

OUTPUT_DIR = ROOT / "output" / "p04_platform_analysis"
ADJUST_FILE = OUTPUT_DIR / "p04_platform_creatives.csv"
START_DATE = "2025-11-01"
END_DATE = "2026-07-20"


def fetch_insights(act_id: str, retries: int = 3) -> list[dict]:
    """Fetch all ad-level insights with pagination."""
    all_data = []
    url = f"https://graph.facebook.com/{VERSION}/act_{act_id}/insights"
    params = {
        "access_token": TOKEN,
        "level": "ad",
        "time_range": json.dumps({"since": START_DATE, "until": END_DATE}),
        "fields": "ad_id,ad_name,spend,impressions,clicks,ctr,cpm,cpc,frequency,"
                   "video_play_actions,video_p25_watched_actions,video_p50_watched_actions,"
                   "video_p75_watched_actions,video_p100_watched_actions,video_avg_time_watched_actions,"
                   "actions,action_values,inline_link_clicks,inline_post_engagement",
        "limit": 500,
        "action_attribution_windows": json.dumps(["7d_click", "1d_view"]),
    }

    next_url = url
    page = 0
    while next_url:
        for attempt in range(retries):
            try:
                r = requests.get(next_url, params=params if page == 0 else None, timeout=60)
                data = r.json()
                if "error" in data:
                    print(f"    ⚠ API error: {data['error'].get('message', '')[:200]}")
                    return all_data
                all_data.extend(data.get("data", []))
                paging = data.get("paging", {})
                next_url = paging.get("next")
                params = None
                page += 1
                break
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2)
                else:
                    print(f"    ⚠ Request failed: {e}")
                    return all_data
        if page % 5 == 0:
            print(f"    Page {page}, {len(all_data)} rows...")

    return all_data


def parse_video_actions(row: dict) -> dict:
    """Extract video metrics from actions."""
    result = {"video_plays": 0, "video_p25": 0, "video_p50": 0, "video_p75": 0, "video_p100": 0}
    action_map = {
        "video_play_actions": "video_plays",
        "video_p25_watched_actions": "video_p25",
        "video_p50_watched_actions": "video_p50",
        "video_p75_watched_actions": "video_p75",
        "video_p100_watched_actions": "video_p100",
    }
    for fb_field, local_field in action_map.items():
        actions = row.get(fb_field, [])
        if actions:
            for a in actions:
                if a.get("action_type") == "video_view":
                    result[local_field] = int(a.get("value", 0))
    return result


def main():
    print("=" * 70)
    print("  Facebook Ads Insights - P04 All Accounts")
    print(f"  {START_DATE} ~ {END_DATE}")
    print("=" * 70)

    if not TOKEN:
        print("  ❌ 未配置 FB_TOKEN 或 META_ACCESS_TOKEN")
        return

    # Load Adjust data (ad_id = creative_id_network)
    adjust_ids = set()
    adjust_data = {}
    if ADJUST_FILE.exists():
        with open(ADJUST_FILE, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cid = row["creative_id"]  # This is actually Facebook ad_id
                adjust_ids.add(cid)
                adjust_data[cid] = row
        print(f"\n  Adjust IDs (ad_id): {len(adjust_ids)}")

    # ── Pull Facebook Insights per account ──────────────────────────
    all_insights = []
    for acc in P04_ACCOUNTS:
        print(f"\n[{acc['name']}] act_{acc['id']} ({acc['platform']})...")
        insights = fetch_insights(acc["id"])
        print(f"  Total rows: {len(insights)}")

        matched = 0
        for row in insights:
            ad_id = row.get("ad_id", "")
            if ad_id not in adjust_ids:
                continue

            video = parse_video_actions(row)
            all_insights.append({
                "ad_id": ad_id,
                "ad_name": row.get("ad_name", ""),
                "platform": acc["platform"],
                "spend": float(row.get("spend", 0) or 0),
                "impressions": int(row.get("impressions", 0) or 0),
                "clicks": int(row.get("clicks", 0) or 0),
                "ctr": float(row.get("ctr", 0) or 0),
                "cpm": float(row.get("cpm", 0) or 0),
                "cpc": float(row.get("cpc", 0) or 0),
                "frequency": float(row.get("frequency", 0) or 0),
                "video_plays": video["video_plays"],
                "video_p25": video["video_p25"],
                "video_p50": video["video_p50"],
                "video_p75": video["video_p75"],
                "video_p100": video["video_p100"],
            })
            matched += 1

        print(f"  Matched: {matched}")

    print(f"\n  Total matched: {len(all_insights)}")

    if not all_insights:
        print("  ❌ 无匹配数据")
        return

    # ── Aggregate by ad_id ──────────────────────────────────────────
    fb_agg = defaultdict(lambda: {"spend": 0, "impressions": 0, "clicks": 0, "platform": "",
                                   "video_plays": 0, "video_p25": 0, "frequency_total": 0, "row_count": 0})

    for row in all_insights:
        aid = row["ad_id"]
        fb_agg[aid]["spend"] += row["spend"]
        fb_agg[aid]["impressions"] += row["impressions"]
        fb_agg[aid]["clicks"] += row["clicks"]
        fb_agg[aid]["platform"] = row["platform"]
        fb_agg[aid]["video_plays"] += row["video_plays"]
        fb_agg[aid]["video_p25"] += row["video_p25"]
        fb_agg[aid]["frequency_total"] += float(row.get("frequency", 0) or 0)
        fb_agg[aid]["row_count"] += 1

    # ── Merge with Adjust ───────────────────────────────────────────
    merged = []
    for aid, fb in fb_agg.items():
        adj = adjust_data.get(aid, {})
        adj_cost = float(adj.get("cost", 0) or 0)
        adj_rev = float(adj.get("revenue", 0) or 0)
        adj_inst = int(adj.get("installs", 0) or 0)
        adj_days = int(adj.get("active_days", 0) or 0)

        fb_spend = fb["spend"]
        fb_imp = fb["impressions"]
        fb_clicks = fb["clicks"]
        ctr = (fb_clicks / fb_imp * 100) if fb_imp > 0 else 0
        cpm = (fb_spend / fb_imp * 1000) if fb_imp > 0 else 0
        cpc = (fb_spend / fb_clicks) if fb_clicks > 0 else 0
        roas = adj_rev / adj_cost if adj_cost > 0 else 0
        cpi = adj_cost / adj_inst if adj_inst > 0 else 0
        freq = fb["frequency_total"] / fb["row_count"] if fb["row_count"] > 0 else 0
        is_video = fb["video_plays"] > 0
        vtr = (fb["video_p25"] / fb["impressions"] * 100) if fb["impressions"] > 0 else 0

        merged.append({
            "ad_id": aid,
            "platform": fb["platform"],
            "adj_cost": adj_cost,
            "adj_revenue": adj_rev,
            "fb_spend": fb_spend,
            "adj_installs": adj_inst,
            "fb_impressions": fb_imp,
            "fb_clicks": fb_clicks,
            "roas": roas,
            "cpi": cpi,
            "ctr": ctr,
            "cpm": cpm,
            "cpc": cpc,
            "frequency": freq,
            "is_video": is_video,
            "video_plays": fb["video_plays"],
            "vtr": vtr,
            "active_days": adj_days,
        })

    # Split by platform
    ios_data = [m for m in merged if m["platform"] == "iOS"]
    android_data = [m for m in merged if m["platform"] == "Android"]
    ios_data.sort(key=lambda x: x["adj_cost"], reverse=True)
    android_data.sort(key=lambda x: x["adj_cost"], reverse=True)

    # ── Display ─────────────────────────────────────────────────────
    print_platform("iOS", ios_data)
    print_platform("Android", android_data)
    print_summary("iOS", ios_data)
    print_summary("Android", android_data)

    # ── Save ────────────────────────────────────────────────────────
    save_path = OUTPUT_DIR / "p04_merged_fb_adjust.csv"
    with open(save_path, "w", newline="", encoding="utf-8") as f:
        fields = ["ad_id", "platform", "adj_cost", "adj_revenue", "fb_spend",
                  "adj_installs", "fb_impressions", "fb_clicks", "roas", "cpi",
                  "ctr", "cpm", "cpc", "frequency", "is_video", "video_plays",
                  "vtr", "active_days"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(merged)
    print(f"\n  合并数据已保存: {save_path}")


def print_platform(label: str, data: list[dict]):
    print(f"\n{'─'*120}")
    print(f"  {label} — Top 15 (Adjust ROAS × Facebook CTR/CPM/Freq)")
    print(f"{'─'*120}")
    hdr = f"{'Ad ID':<20s} {'Adj Cost':>9s} {'Adj Rev':>9s} {'Inst':>6s} {'ROAS':>7s} {'CPI':>7s} {'CTR':>6s} {'CPM':>7s} {'Freq':>5s} {'FB Spend':>9s} {'Impr':>10s} {'Type':>5s} {'Days':>5s}"
    print(hdr)
    print(f"{'─'*20} {'─'*9} {'─'*9} {'─'*6} {'─'*7} {'─'*7} {'─'*6} {'─'*7} {'─'*5} {'─'*9} {'─'*10} {'─'*5} {'─'*5}")

    totals = {"adj_cost": 0, "adj_revenue": 0, "adj_installs": 0, "fb_impressions": 0, "fb_clicks": 0, "fb_spend": 0}

    for entry in data[:15]:
        roi_mark = "🔥" if entry["roas"] >= 0.5 else ("⚠️" if entry["roas"] < 0.2 else "  ")
        ctr_mark = "✅" if entry["ctr"] >= 2.0 else ("⚠️" if entry["ctr"] < 0.5 else "  ")
        ad_type = "VID" if entry["is_video"] else "IMG"
        for k in totals:
            totals[k] += entry[k]
        print(f"  {entry['ad_id']:<20s} ${entry['adj_cost']:>8,.0f} ${entry['adj_revenue']:>8,.0f} "
              f"{entry['adj_installs']:>6,} {entry['roas']:>6.3f}{roi_mark} ${entry['cpi']:>6.2f} "
              f"{entry['ctr']:>5.2f}%{ctr_mark} ${entry['cpm']:>6.2f} {entry['frequency']:>4.1f}x "
              f"${entry['fb_spend']:>8,.0f} {entry['fb_impressions']:>10,} {ad_type:>5s} {entry['active_days']:>5d}")

    print(f"  {'─'*20} {'─'*9} {'─'*9} {'─'*6} {'─'*7} {'─'*7} {'─'*6} {'─'*7} {'─'*5} {'─'*9} {'─'*10} {'─'*5} {'─'*5}")
    avg_roas = totals["adj_revenue"] / totals["adj_cost"] if totals["adj_cost"] > 0 else 0
    avg_cpi = totals["adj_cost"] / totals["adj_installs"] if totals["adj_installs"] > 0 else 0
    avg_ctr = (totals["fb_clicks"] / totals["fb_impressions"] * 100) if totals["fb_impressions"] > 0 else 0
    avg_cpm = (totals["adj_cost"] / totals["fb_impressions"] * 1000) if totals["fb_impressions"] > 0 else 0
    print(f"  {'TOP 15 TOTAL':<20s} ${totals['adj_cost']:>8,.0f} ${totals['adj_revenue']:>8,.0f} "
          f"{totals['adj_installs']:>6,} {avg_roas:>6.3f}   ${avg_cpi:>6.2f} "
          f"{avg_ctr:>5.2f}%   ${avg_cpm:>6.2f} "
          f"${totals['fb_spend']:>8,.0f} {totals['fb_impressions']:>10,}")


def print_summary(label: str, data: list[dict]):
    if not data:
        return
    tc = sum(d["adj_cost"] for d in data)
    tr = sum(d["adj_revenue"] for d in data)
    ti = sum(d["adj_installs"] for d in data)
    timp = sum(d["fb_impressions"] for d in data)
    tclicks = sum(d["fb_clicks"] for d in data)
    u = len(data)
    high_roas = [d for d in data if d["roas"] >= 0.5 and d["adj_cost"] >= 100]
    high_ctr = [d for d in data if d["ctr"] >= 2.0 and d["adj_cost"] >= 100]
    videos = [d for d in data if d["is_video"]]
    print(f"\n  {label} Summary:")
    print(f"    Spend: ${tc:,.0f} | Revenue: ${tr:,.0f} | Installs: {ti:,} | Creatives: {u}")
    print(f"    ROAS: {tr/tc:.3f}" if tc else "    ROAS: -")
    print(f"    CPI: ${tc/ti:.2f}" if ti else "    CPI: -")
    print(f"    CTR: {(tclicks/timp*100):.2f}%" if timp else "    CTR: -")
    print(f"    CPM: ${tc/timp*1000:.2f}" if timp else "    CPM: -")
    print(f"    ROI>=0.5: {len(high_roas)} | CTR>=2%: {len(high_ctr)} | Videos: {len(videos)}")


if __name__ == "__main__":
    main()