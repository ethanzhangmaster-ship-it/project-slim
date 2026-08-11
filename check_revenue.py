import json
from pathlib import Path
from collections import Counter

OUT = Path("d:/project_slim/project_slim/output/video_intelligence/p04")

# Load matched records
with open(OUT / "creative_mapping_v2.json", "r", encoding="utf-8") as f:
    data = json.load(f)

records = data.get("match_records", [])

# Revenue distribution
revenue_dist = Counter()
for r in records:
    rev = r.get("revenue", 0)
    if rev == 0:
        revenue_dist["zero"] += 1
    elif rev < 1:
        revenue_dist["<1"] += 1
    elif rev < 10:
        revenue_dist["1-10"] += 1
    elif rev < 100:
        revenue_dist["10-100"] += 1
    elif rev < 1000:
        revenue_dist["100-1000"] += 1
    else:
        revenue_dist[">1000"] += 1

print("Revenue distribution among matched records:")
for k, v in sorted(revenue_dist.items()):
    print(f"  {k}: {v} records")

zero_revenue = [r for r in records if r.get("revenue", 0) == 0]
print(f"\nZero revenue records: {len(zero_revenue)}/{len(records)} ({len(zero_revenue)/len(records)*100:.1f}%)")

# Top revenue records
print("\nTop 20 records by revenue:")
by_rev = sorted(records, key=lambda x: -x.get("revenue", 0))[:20]
for r in by_rev:
    print(f"  {r['ad_name'][:35]:<35} | spend=${r['spend']:>8,.2f} | rev=${r['revenue']:>10,.2f} | roas={r['roas']:>5.3f}")

# Check if any records have purchase_roas from API
print("\n" + "="*70)
print("Checking original FB data for purchase_roas field...")
print("="*70)

with open(OUT / "p04_full_ad_hierarchy.json", "r", encoding="utf-8") as f:
    fb_data = json.load(f)

fb_records = fb_data.get("records", [])

# Sample records with highest revenue
sample = sorted(fb_records, key=lambda x: -x.get("revenue", 0))[:5]
print("\nTop 5 FB records (revenue):")
for r in sample:
    print(f"  ad_name: {r['ad_name']}")
    print(f"    spend: ${r['spend']:.2f}, revenue: ${r['revenue']:.2f}, roas: {r['roas']:.3f}")
    print(f"    creative_name: {r['creative_name'][:60]}")
    print()

# Check retry insights raw data
for retry_file in ["insights_retry_1379499207181514.json", "insights_retry_1628583695016910.json"]:
    path = OUT / retry_file
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            retry_data = json.load(f)
        insights = retry_data.get("insights", [])
        if insights:
            print(f"\n--- {retry_file} sample ---")
            top = sorted(insights, key=lambda x: -float(x.get("spend", 0) or 0))[:3]
            for ins in top:
                print(f"  ad_id: {ins.get('ad_id', '')}")
                print(f"    spend: ${ins.get('spend', 0)}")
                print(f"    purchase_roas: {ins.get('purchase_roas', 'N/A')}")
                print(f"    action_values: {ins.get('action_values', [])[:2]}")
                print(f"    actions: {ins.get('actions', [])[:2]}")
                print()
        break

# Total stats
total_spend = sum(r.get("spend", 0) for r in fb_records)
total_rev = sum(r.get("revenue", 0) for r in fb_records)
print(f"\nTotal FB records: {len(fb_records)}")
print(f"Total spend: ${total_spend:,.2f}")
print(f"Total revenue: ${total_rev:,.2f}")
print(f"Overall ROAS: {total_rev/total_spend:.4f}" if total_spend > 0 else "")

# How many have zero revenue?
zero_rev = sum(1 for r in fb_records if r.get("revenue", 0) == 0)
print(f"Records with zero revenue: {zero_rev}/{len(fb_records)} ({zero_rev/len(fb_records)*100:.1f}%)")
