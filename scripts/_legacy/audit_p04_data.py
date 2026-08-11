#!/usr/bin/env python3
"""Comprehensive data audit for P04 Adjust + Facebook merge."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output" / "p04_platform_analysis"

ADJUST_RAW = OUTPUT / "adjust_raw.csv"
MERGED = OUTPUT / "p04_merged_fb_adjust.csv"
ADJUST_CREATIVES = OUTPUT / "p04_platform_creatives.csv"

print("=" * 80)
print("  P04 数据质量审计")
print("=" * 80)

# ════════════════════════════════════════════════════════════════════
# AUDIT 1: Adjust 原始数据完整性
# ════════════════════════════════════════════════════════════════════
print("\n" + "─" * 80)
print("  AUDIT 1: Adjust 原始数据完整性")
print("─" * 80)

dates = set()
partner_counts = Counter()
store_counts = Counter()
apps = Counter()
creative_id_status = Counter()

with open(ADJUST_RAW, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    raw_rows = list(reader)

print(f"  总行数: {len(raw_rows):,}")

for r in raw_rows:
    dates.add(r.get("day", ""))
    partner_counts[r.get("partner_name", "unknown")] += 1
    store_counts[r.get("store_type", "unknown")] += 1
    apps[r.get("app", "unknown")] += 1
    cid = r.get("creative_id_network", "unknown")
    if cid == "unknown" or "Search" in cid or "Organic" in cid or cid == "Display" or cid == "Expired Attributions":
        creative_id_status["unknown/filtered"] += 1
    else:
        creative_id_status["known"] += 1

dates_sorted = sorted(dates)
print(f"\n  日期范围: {dates_sorted[0]} ~ {dates_sorted[-1]}")
print(f"  日期数: {len(dates_sorted)} / 应该 ~263 天 (2025-11-01 ~ 2026-07-20)")
print(f"  日期覆盖率: {len(dates_sorted)/263*100:.1f}%")

# Check missing dates
d1 = date(2025, 11, 1)
d2 = date(2026, 7, 20)
all_dates = set()
from datetime import timedelta
d = d1
while d <= d2:
    all_dates.add(d.isoformat())
    d += timedelta(days=1)
missing = sorted(all_dates - dates)
if missing:
    print(f"  ⚠️ 缺失日期 ({len(missing)} 天): {missing[0]} ~ {missing[-1]}")
    print(f"     前10天: {missing[:10]}")
    print(f"     后10天: {missing[-10:]}")
else:
    print(f"  ✅ 日期无缺失")

print(f"\n  Partner 分布:")
for p, c in partner_counts.most_common():
    pct = c / len(raw_rows) * 100
    print(f"    {p:30s}: {c:>8,} ({pct:.1f}%)")

print(f"\n  Store 分布:")
for s, c in store_counts.most_common():
    print(f"    {s:20s}: {c:>8,}")

print(f"\n  App 分布:")
for a, c in apps.most_common():
    print(f"    {a:20s}: {c:>8,}")

print(f"\n  Creative ID 状态:")
for s, c in creative_id_status.most_common():
    print(f"    {s:20s}: {c:>8,}")

# Facebook-only date check
fb_dates = set()
for r in raw_rows:
    if r.get("partner_name") == "Facebook":
        fb_dates.add(r.get("day", ""))
fb_dates_sorted = sorted(fb_dates)
print(f"\n  Facebook 日期范围: {fb_dates_sorted[0]} ~ {fb_dates_sorted[-1]}")
print(f"  Facebook 日期数: {len(fb_dates_sorted)} / {len(dates_sorted)}")

# ════════════════════════════════════════════════════════════════════
# AUDIT 2: Adjust 创意级数据检查
# ════════════════════════════════════════════════════════════════════
print("\n" + "─" * 80)
print("  AUDIT 2: Adjust 创意级数据 (ad_id 维度)")
print("─" * 80)

with open(ADJUST_CREATIVES, "r", encoding="utf-8") as f:
    adj_creatives = list(csv.DictReader(f))

print(f"  总 ad_id 数: {len(adj_creatives)}")
stores = Counter()
for a in adj_creatives:
    stores[a.get("store", "unknown")] += 1
print(f"  按平台: {dict(stores)}")

# Check cost distribution
costs = [float(a.get("cost", 0)) for a in adj_creatives]
print(f"  Cost 范围: ${min(costs):,.0f} ~ ${max(costs):,.0f}")
print(f"  Cost 中位数: ${sorted(costs)[len(costs)//2]:,.0f}")
print(f"  Cost 合计: ${sum(costs):,.0f}")

# Cost mismatch with raw
fb_raw_spend = sum(float(r.get("cost", 0)) for r in raw_rows if r.get("partner_name") == "Facebook")
print(f"  Facebook Raw Total Cost: ${fb_raw_spend:,.0f}")
print(f"  Creatives Total Cost: ${sum(costs):,.0f}")
print(f"  差异: ${abs(fb_raw_spend - sum(costs)):,.0f} "
      f"({abs(fb_raw_spend - sum(costs))/fb_raw_spend*100:.2f}%)" if fb_raw_spend else "")

# ════════════════════════════════════════════════════════════════════
# AUDIT 3: Facebook 数据完整性
# ════════════════════════════════════════════════════════════════════
print("\n" + "─" * 80)
print("  AUDIT 3: Facebook 数据完整性")
print("─" * 80)

with open(MERGED, "r", encoding="utf-8") as f:
    merged = list(csv.DictReader(f))

print(f"  合并后 ad_id 数: {len(merged)}")

# Platform breakdown
plat_counts = Counter()
for m in merged:
    plat_counts[m.get("platform", "unknown")] += 1
print(f"  按平台: {dict(plat_counts)}")

# Match rate
adj_ios = [a for a in adj_creatives if a.get("store") == "iOS"]
adj_and = [a for a in adj_creatives if a.get("store") == "Android"]
merged_ios = [m for m in merged if m.get("platform") == "iOS"]
merged_and = [m for m in merged if m.get("platform") == "Android"]

print(f"\n  匹配率:")
print(f"    iOS:  {len(merged_ios)}/{len(adj_ios)} = {len(merged_ios)/len(adj_ios)*100:.1f}%")
print(f"    Android: {len(merged_and)}/{len(adj_and)} = {len(merged_and)/len(adj_and)*100:.1f}%")
print(f"    总计: {len(merged)}/{len(adj_creatives)} = {len(merged)/len(adj_creatives)*100:.1f}%")

# FB spend vs Adj cost
for label, data in [("iOS", merged_ios), ("Android", merged_and)]:
    fb_total = sum(float(m.get("fb_spend", 0)) for m in data)
    adj_total = sum(float(m.get("adj_cost", 0)) for m in data)
    diff = abs(fb_total - adj_total)
    print(f"\n  {label} FB Spend vs Adj Cost:")
    print(f"    FB Spend: ${fb_total:,.0f}")
    print(f"    Adj Cost: ${adj_total:,.0f}")
    print(f"    差异: ${diff:,.0f} ({diff/fb_total*100:.2f}%)" if fb_total else "    差异: N/A")

# Missing: which Adjust IDs don't have FB data
adj_ids = set(a["creative_id"] for a in adj_creatives)
merged_ids = set(m["ad_id"] for m in merged)
unmatched = adj_ids - merged_ids
if unmatched:
    print(f"\n  ⚠️ 未匹配 Adjust ID: {len(unmatched)} 个")
    # Sample
    sample = list(unmatched)[:10]
    for uid in sample:
        adj_info = next((a for a in adj_creatives if a["creative_id"] == uid), {})
        print(f"    {uid}: cost=${adj_info.get('cost',0)}, revenue=${adj_info.get('revenue',0)}")
else:
    print(f"\n  ✅ 所有 Adjust ID 均已匹配")

# ════════════════════════════════════════════════════════════════════
# AUDIT 4: 数据准确性 — 异常检测
# ════════════════════════════════════════════════════════════════════
print("\n" + "─" * 80)
print("  AUDIT 4: 数据准确性 — 异常检测")
print("─" * 80)

anomalies = []

for m in merged:
    adj_cost = float(m.get("adj_cost", 0))
    adj_rev = float(m.get("adj_revenue", 0))
    fb_spend = float(m.get("fb_spend", 0))
    adj_inst = int(m.get("adj_installs", 0))
    fb_imp = int(m.get("fb_impressions", 0))
    fb_clicks = int(m.get("fb_clicks", 0))
    roas = float(m.get("roas", 0))
    cpi = float(m.get("cpi", 0))
    ctr = float(m.get("ctr", 0))
    cpm = float(m.get("cpm", 0))
    cpc = float(m.get("cpc", 0))
    freq = float(m.get("frequency", 0))

    # Check: adj_cost > 0 but fb_spend = 0
    if adj_cost > 100 and fb_spend < 1:
        anomalies.append(f"⚠️ {m['ad_id']}: adj_cost=${adj_cost:,.0f} but fb_spend=${fb_spend:.2f}")

    # Check: adj_rev > adj_cost * 10 (suspiciously high ROAS)
    if adj_cost > 100 and adj_rev > adj_cost * 10:
        anomalies.append(f"⚠️ {m['ad_id']}: ROAS={roas:.1f} (adj_rev=${adj_rev:,.0f}, adj_cost=${adj_cost:,.0f})")

    # Check: fb_imp > 0 but fb_clicks = 0
    if fb_imp > 1000 and fb_clicks == 0:
        anomalies.append(f"⚠️ {m['ad_id']}: {fb_imp:,} imp but 0 clicks")

    # Check: adj_inst = 0 but adj_cost > 500
    if adj_cost > 500 and adj_inst == 0:
        anomalies.append(f"⚠️ {m['ad_id']}: adj_cost=${adj_cost:,.0f} but 0 installs")

    # Check: CTR > 20% (unrealistic)
    if ctr > 20:
        anomalies.append(f"⚠️ {m['ad_id']}: CTR={ctr:.1f}% (unrealistic)")

    # Check: CPM > $500 (unrealistic)
    if cpm > 500:
        anomalies.append(f"⚠️ {m['ad_id']}: CPM=${cpm:.0f} (unrealistic)")

    # Check: frequency > 10 (saturation)
    if freq > 10:
        anomalies.append(f"⚠️ {m['ad_id']}: frequency={freq:.1f}x (saturated)")

    # Check: fb_spend vs adj_cost mismatch > 10%
    if adj_cost > 100 and fb_spend > 100:
        ratio = fb_spend / adj_cost
        if ratio < 0.5 or ratio > 2.0:
            anomalies.append(f"⚠️ {m['ad_id']}: fb_spend=${fb_spend:,.0f} vs adj_cost=${adj_cost:,.0f} (ratio={ratio:.2f})")

if anomalies:
    print(f"  发现 {len(anomalies)} 个异常:")
    for a in anomalies[:20]:
        print(f"    {a}")
    if len(anomalies) > 20:
        print(f"    ... 还有 {len(anomalies)-20} 个")
else:
    print(f"  ✅ 无异常")

# ════════════════════════════════════════════════════════════════════
# AUDIT 5: 维度正确性检查
# ════════════════════════════════════════════════════════════════════
print("\n" + "─" * 80)
print("  AUDIT 5: 维度正确性")
print("─" * 80)

# Check: platform split is correct
ios_adj_ids = set(a["creative_id"] for a in adj_creatives if a["store"] == "iOS")
and_adj_ids = set(a["creative_id"] for a in adj_creatives if a["store"] == "Android")

ios_merged = set(m["ad_id"] for m in merged if m["platform"] == "iOS")
and_merged = set(m["ad_id"] for m in merged if m["platform"] == "Android")

# Cross-check: any overlapping IDs between platforms?
overlap = ios_merged & and_merged
if overlap:
    print(f"  ⚠️ {len(overlap)} ad_ids appear in both iOS and Android!")
    print(f"     Sample: {list(overlap)[:5]}")
else:
    print(f"  ✅ iOS/Android 无重叠")

# Check: all merged platforms match Adjust platform
mismatched = []
for m in merged:
    mid = m["ad_id"]
    adj = next((a for a in adj_creatives if a["creative_id"] == mid), None)
    if adj:
        adj_store = adj.get("store", "")
        merged_plat = m.get("platform", "")
        if (adj_store == "iOS" and merged_plat != "iOS") or \
           (adj_store == "Android" and merged_plat != "Android"):
            mismatched.append(f"{mid}: Adjust={adj_store}, Merged={merged_plat}")

if mismatched:
    print(f"  ⚠️ {len(mismatched)} 平台不匹配!")
    for m in mismatched[:10]:
        print(f"    {m}")
else:
    print(f"  ✅ 所有平台匹配正确")

# Check: video/image type correctness
videos = [m for m in merged if m.get("is_video") == "True"]
images = [m for m in merged if m.get("is_video") != "True"]
print(f"\n  视频: {len(videos)} ({len(videos)/len(merged)*100:.1f}%)")
print(f"  图片: {len(images)} ({len(images)/len(merged)*100:.1f}%)")

# Check video metrics
videos_with_plays = [m for m in videos if int(m.get("video_plays", 0)) > 0]
print(f"  有播放数据的视频: {len(videos_with_plays)}/{len(videos)}")

# Check: key metrics ranges
print(f"\n  关键指标范围:")
for metric, label in [("roas", "ROAS"), ("cpi", "CPI"), ("ctr", "CTR"), ("cpm", "CPM"), ("frequency", "Freq")]:
    vals = [float(m.get(metric, 0)) for m in merged]
    vals = [v for v in vals if v > 0]
    if vals:
        print(f"    {label}: {min(vals):.3f} ~ {max(vals):.1f} (median={sorted(vals)[len(vals)//2]:.2f})")

# ════════════════════════════════════════════════════════════════════
# AUDIT 6: 花费一致性检查 (Adjust vs FB)
# ════════════════════════════════════════════════════════════════════
print("\n" + "─" * 80)
print("  AUDIT 6: Adjust vs Facebook 花费一致性")
print("─" * 80)

# By platform
for label, data in [("iOS", merged_ios), ("Android", merged_and)]:
    fb_spend = sum(float(m.get("fb_spend", 0)) for m in data)
    adj_cost = sum(float(m.get("adj_cost", 0)) for m in data)
    print(f"  {label}:")
    print(f"    Facebook Spend: ${fb_spend:,.0f}")
    print(f"    Adjust Cost:    ${adj_cost:,.0f}")
    print(f"    Ratio: {fb_spend/adj_cost:.3f}" if adj_cost else "    Ratio: N/A")

# Check top 10 by cost - are they matched?
print(f"\n  Top 10 Adjust Cost 匹配检查:")
top10 = sorted(adj_creatives, key=lambda x: float(x.get("cost", 0)), reverse=True)[:10]
for a in top10:
    mid = a["creative_id"]
    matched = mid in merged_ids
    m = next((m for m in merged if m["ad_id"] == mid), None)
    if m:
        print(f"    {mid}: adj=${a['cost']} | fb=${m['fb_spend']} | ✅")
    else:
        print(f"    {mid}: adj=${a['cost']} | ❌ 未匹配")

# ════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("  审计总结")
print("=" * 80)

issues = []
if len(dates_sorted) < 200:
    issues.append(f"日期覆盖率仅 {len(dates_sorted)}/263 天")
if fb_raw_spend > 0 and abs(fb_raw_spend - sum(costs)) / fb_raw_spend > 0.05:
    issues.append(f"Raw vs Creative Cost 差异 > 5%")
if len(anomalies) > 50:
    issues.append(f"异常值过多: {len(anomalies)}")
if len(unmatched) > len(adj_creatives) * 0.1:
    issues.append(f"未匹配率 > 10%: {len(unmatched)}/{len(adj_creatives)}")
if overlap:
    issues.append(f"平台重叠: {len(overlap)} IDs")
if mismatched:
    issues.append(f"平台不匹配: {len(mismatched)}")

if issues:
    print("  ❌ 发现问题:")
    for i in issues:
        print(f"    - {i}")
else:
    print("  ✅ 所有审计通过")

print(f"\n  数据规模:")
print(f"    Adjust 原始: {len(raw_rows):,} 行")
print(f"    Adjust 创意: {len(adj_creatives):,} ad_ids")
print(f"    Facebook 匹配: {len(merged):,} ad_ids")
print(f"    日期范围: {dates_sorted[0]} ~ {dates_sorted[-1]}")
print(f"    平台: iOS={len(merged_ios)}, Android={len(merged_and)}")