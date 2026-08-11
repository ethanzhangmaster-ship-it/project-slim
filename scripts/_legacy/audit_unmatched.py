#!/usr/bin/env python3
"""Deep dive into unmatched P04 IDs."""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output" / "p04_platform_analysis"

ADJUST_CREATIVES = OUTPUT / "p04_platform_creatives.csv"
MERGED = OUTPUT / "p04_merged_fb_adjust.csv"

# Load
with open(ADJUST_CREATIVES, "r", encoding="utf-8") as f:
    adj = list(csv.DictReader(f))
with open(MERGED, "r", encoding="utf-8") as f:
    merged = list(csv.DictReader(f))

adj_ids = set(a["creative_id"] for a in adj)
merged_ids = set(m["ad_id"] for m in merged)
unmatched = adj_ids - merged_ids

# Unmatched by platform
unmatched_data = [a for a in adj if a["creative_id"] in unmatched]
ios_unmatched = [a for a in unmatched_data if a["store"] == "iOS"]
and_unmatched = [a for a in unmatched_data if a["store"] == "Android"]

print("=" * 70)
print("  未匹配 P04 IDs 深入分析")
print("=" * 70)

# Total cost unmatched
ios_um_cost = sum(float(a["cost"]) for a in ios_unmatched)
and_um_cost = sum(float(a["cost"]) for a in and_unmatched)
print(f"\n  未匹配总花费: iOS=${ios_um_cost:,.0f}, Android=${and_um_cost:,.0f}")

# Top unmatched by cost
print(f"\n  iOS Top 10 未匹配 (按花费):")
for a in sorted(ios_unmatched, key=lambda x: float(x["cost"]), reverse=True)[:10]:
    print(f"    {a['creative_id']}: cost=${a['cost']}, revenue=${a['revenue']}, installs={a['installs']}")

print(f"\n  Android Top 10 未匹配:")
for a in sorted(and_unmatched, key=lambda x: float(x["cost"]), reverse=True)[:10]:
    print(f"    {a['creative_id']}: cost=${a['cost']}, revenue=${a['revenue']}, installs={a['installs']}")

# ID suffix analysis
print(f"\n  ID 后缀分析:")
ios_um_suffixes = Counter(a["creative_id"][-3:] for a in ios_unmatched)
ios_m_suffixes = Counter(a["creative_id"][-3:] for a in adj if a["creative_id"] in merged_ids and a["store"] == "iOS")
and_um_suffixes = Counter(a["creative_id"][-3:] for a in and_unmatched)
and_m_suffixes = Counter(a["creative_id"][-3:] for a in adj if a["creative_id"] in merged_ids and a["store"] == "Android")

print(f"  iOS 未匹配 suffix: {ios_um_suffixes.most_common(5)}")
print(f"  iOS 已匹配 suffix: {ios_m_suffixes.most_common(5)}")
print(f"  Android 未匹配 suffix: {and_um_suffixes.most_common(5)}")
print(f"  Android 已匹配 suffix: {and_m_suffixes.most_common(5)}")

# Cost distribution of unmatched
print(f"\n  未匹配花费分布:")
for label, data in [("iOS", ios_unmatched), ("Android", and_unmatched)]:
    costs = [float(a["cost"]) for a in data]
    print(f"    {label}: min=${min(costs):.2f}, median=${sorted(costs)[len(costs)//2]:.2f}, max=${max(costs):.0f}")
    print(f"      Cost<$10: {sum(1 for c in costs if c < 10)}")
    print(f"      Cost $10-$100: {sum(1 for c in costs if 10 <= c < 100)}")
    print(f"      Cost $100-$1000: {sum(1 for c in costs if 100 <= c < 1000)}")
    print(f"      Cost>$1000: {sum(1 for c in costs if c >= 1000)}")

# Check if unmatched IDs are from a different account
# The 15-digit Facebook IDs: first few digits indicate account
print(f"\n  ID 前缀分析 (前6位):")
ios_um_prefix = Counter(a["creative_id"][:6] for a in ios_unmatched)
ios_m_prefix = Counter(a["creative_id"][:6] for a in adj if a["creative_id"] in merged_ids and a["store"] == "iOS")
print(f"  iOS 未匹配 prefix: {ios_um_prefix.most_common(5)}")
print(f"  iOS 已匹配 prefix: {ios_m_prefix.most_common(5)}")

# Conclusion
print(f"\n{'='*70}")
print(f"  结论:")
print(f"  iOS 未匹配: {len(ios_unmatched)} ({ios_um_cost:,.0f} 花费)")
print(f"  Android 未匹配: {len(and_unmatched)} ({and_um_cost:,.0f} 花费)")
print(f"  总未匹配花费: ${ios_um_cost + and_um_cost:,.0f}")

# Percent of total
total_adj_cost = sum(float(a["cost"]) for a in adj)
print(f"  未匹配花费占比: {(ios_um_cost + and_um_cost) / total_adj_cost * 100:.1f}%")
print(f"  总 Adjust 花费: ${total_adj_cost:,.0f}")