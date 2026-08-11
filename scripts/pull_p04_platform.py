#!/usr/bin/env python3
"""Pull P04 data from Adjust API + Facebook API, merge, and show top creatives by platform."""
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.clients.adjust import AdjustClient


# ── Config ────────────────────────────────────────────────────────
START_DATE = "2025-11-01"
END_DATE = "2026-07-20"
ADJUST_TOKEN = "jzss-pBPTCF9fPcvYrbqNVsa2aay4aSsVK7KuAxpKPayWFecYg"
OUTPUT_DIR = ROOT / "output" / "p04_platform_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# P04 app tokens (from dashboard config)
P04_APPS = {"P04 Witch"}


def main():
    print("=" * 70)
    print("  P04 Witch - Adjust + Facebook 数据拉取")
    print(f"  {START_DATE} ~ {END_DATE}")
    print("=" * 70)

    # ── 1. Pull Adjust Data ────────────────────────────────────────
    print("\n[1] 拉取 Adjust 数据...")
    client = AdjustClient(user_token=ADJUST_TOKEN)

    # Split into monthly chunks to avoid timeout
    all_rows = []
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    end = datetime.strptime(END_DATE, "%Y-%m-%d")
    current = start

    while current <= end:
        chunk_end = min(current + timedelta(days=30), end)
        chunk_start_str = current.strftime("%Y-%m-%d")
        chunk_end_str = chunk_end.strftime("%Y-%m-%d")

        print(f"  拉取 {chunk_start_str} ~ {chunk_end_str}...")
        try:
            rows = client.fetch_revenue_breakdown(chunk_start_str, chunk_end_str)
            # Filter for P04 Witch
            p04_rows = [r for r in rows if r.get("app") == "P04 Witch"]
            all_rows.extend(p04_rows)
            print(f"    API 返回 {len(rows)} 行, P04 Witch: {len(p04_rows)} 行")
        except Exception as e:
            print(f"    ❌ 错误: {e}")
            # Try direct token
            try:
                client2 = AdjustClient(user_token=f"Bearer {ADJUST_TOKEN}")
                rows = client2.fetch_revenue_breakdown(chunk_start_str, chunk_end_str)
                p04_rows = [r for r in rows if r.get("app") == "P04 Witch"]
                all_rows.extend(p04_rows)
                print(f"    ✅ 重试成功: {len(p04_rows)} 行")
            except Exception as e2:
                print(f"    ❌ 重试失败: {e2}")

        current = chunk_end + timedelta(days=1)
        if current <= end:
            time.sleep(1)  # Rate limit

    print(f"\n  Adjust 总计: {len(all_rows)} 行")

    if not all_rows:
        print("  ❌ 无 Adjust 数据，检查 API token 和权限")
        return

    # Save raw Adjust data
    adjust_path = OUTPUT_DIR / "adjust_raw.csv"
    if all_rows:
        all_keys = sorted(set().union(*(r.keys() for r in all_rows)))
        with open(adjust_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"  Adjust 原始数据已保存: {adjust_path}")

    # ── 2. Analyze by platform (store_type) ────────────────────────
    print("\n[2] 按平台 (iOS/Android) 分析...")

    # Filter: Facebook only, exclude organic/unknown creative IDs
    FACEBOOK_ONLY = True
    EXCLUDE_PATTERNS = {"unknown", "Display", "Expired Attributions", "Organic", "Search", "unknown"}
    
    # Aggregate by store_type + creative_id (Facebook only)
    platform_creatives = defaultdict(lambda: {"cost": 0, "revenue": 0, "installs": 0, "daus": 0, "sessions": 0, "days": set()})
    
    for r in all_rows:
        # Filter: Facebook only
        if FACEBOOK_ONLY and r.get("partner_name", "") != "Facebook":
            continue
        
        store = r.get("store_type", "unknown")
        cid = r.get("creative_id_network", "") or "unknown"
        
        # Skip unknown/aggregated creative IDs
        if cid.lower() in EXCLUDE_PATTERNS or "Search" in cid or "Organic" in cid:
            continue
        
        key = (store, cid)
        d = platform_creatives[key]
        d["cost"] += float(r.get("cost", 0) or 0)
        d["revenue"] += float(r.get("all_revenue", 0) or 0)
        d["installs"] += int(float(r.get("installs", 0) or 0))
        d["daus"] += int(float(r.get("daus", 0) or 0))
        d["sessions"] += int(float(r.get("sessions", 0) or 0))
        d["days"].add(r.get("day", ""))

    # Store type mapping
    store_map = {"app_store": "iOS", "google_play": "Android"}
    
    # Split by platform
    ios_data = []
    android_data = []
    for (store, cid), d in platform_creatives.items():
        if d["cost"] <= 0:
            continue
        roas = d["revenue"] / d["cost"] if d["cost"] > 0 else 0
        cpi = d["cost"] / d["installs"] if d["installs"] > 0 else 0
        entry = {
            "creative_id": cid,
            "store": store_map.get(store, store),
            "cost": d["cost"],
            "revenue": d["revenue"],
            "installs": d["installs"],
            "roas": roas,
            "cpi": cpi,
            "daus": d["daus"],
            "sessions": d["sessions"],
            "active_days": len(d["days"]),
        }
        if store == "app_store":
            ios_data.append(entry)
        elif store == "google_play":
            android_data.append(entry)

    # Sort by cost
    ios_data.sort(key=lambda x: x["cost"], reverse=True)
    android_data.sort(key=lambda x: x["cost"], reverse=True)

    # ── 3. Display ─────────────────────────────────────────────────
    print_platform("iOS", ios_data)
    print_platform("Android", android_data)

    # ── 4. Summary ─────────────────────────────────────────────────
    print_summary("iOS", ios_data)
    print_summary("Android", android_data)

    # Save merged data
    save_path = OUTPUT_DIR / "p04_platform_creatives.csv"
    with open(save_path, "w", newline="", encoding="utf-8") as f:
        fields = ["creative_id", "store", "cost", "revenue", "installs", "roas", "cpi", "daus", "sessions", "active_days"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for entry in ios_data + android_data:
            writer.writerow(entry)
    print(f"\n  合并数据已保存: {save_path}")


def print_platform(label: str, data: list[dict]):
    print(f"\n{'─'*70}")
    print(f"  {label} — Top 15 by Spend (Adjust ROAS)")
    print(f"{'─'*70}")
    print(f"{'Creative ID':<25s} {'Cost':>10s} {'Revenue':>10s} {'Installs':>8s} {'ROAS':>8s} {'CPI':>8s} {'Days':>5s}")
    print(f"{'─'*25} {'─'*10} {'─'*10} {'─'*8} {'─'*8} {'─'*8} {'─'*5}")
    
    total_cost = 0
    total_rev = 0
    total_inst = 0
    
    for i, entry in enumerate(data[:15]):
        total_cost += entry["cost"]
        total_rev += entry["revenue"]
        total_inst += entry["installs"]
        roi_mark = "🔥" if entry["roas"] >= 0.5 else ("⚠️" if entry["roas"] < 0.2 else "  ")
        print(f"  {entry['creative_id']:<25s} ${entry['cost']:>9,.0f} ${entry['revenue']:>9,.0f} {entry['installs']:>8,} {entry['roas']:>7.3f} {roi_mark} ${entry['cpi']:>7.2f} {entry['active_days']:>5d}")

    print(f"  {'─'*25} {'─'*10} {'─'*10} {'─'*8} {'─'*8} {'─'*8} {'─'*5}")
    print(f"  {'TOP 15 TOTAL':<25s} ${total_cost:>9,.0f} ${total_rev:>9,.0f} {total_inst:>8,} {total_rev/total_cost if total_cost>0 else 0:>7.3f}   ${total_cost/total_inst if total_inst>0 else 0:>7.2f}")


def print_summary(label: str, data: list[dict]):
    if not data:
        return
    total_cost = sum(d["cost"] for d in data)
    total_rev = sum(d["revenue"] for d in data)
    total_inst = sum(d["installs"] for d in data)
    unique_creatives = len(data)
    avg_roas = total_rev / total_cost if total_cost > 0 else 0
    avg_cpi = total_cost / total_inst if total_inst > 0 else 0
    
    # Count high ROAS
    high_roas = [d for d in data if d["roas"] >= 0.5 and d["cost"] >= 100]
    med_roas = [d for d in data if 0.2 <= d["roas"] < 0.5 and d["cost"] >= 100]
    low_roas = [d for d in data if d["roas"] < 0.2 and d["cost"] >= 100]
    
    print(f"\n  {label} Summary:")
    print(f"    Total Spend:      ${total_cost:,.0f}")
    print(f"    Total Revenue:    ${total_rev:,.0f}")
    print(f"    Total Installs:   {total_inst:,}")
    print(f"    Unique Creatives: {unique_creatives}")
    print(f"    Avg ROAS:         {avg_roas:.3f}")
    print(f"    Avg CPI:          ${avg_cpi:.2f}")
    print(f"    ROI >= 0.5:       {len(high_roas)} creatives")
    print(f"    ROI 0.2-0.5:      {len(med_roas)} creatives")
    print(f"    ROI < 0.2:        {len(low_roas)} creatives")


if __name__ == "__main__":
    main()