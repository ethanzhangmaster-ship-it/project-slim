"""Export P04 video records + metrics to CSV for Facebook matching."""
import json, csv, os
from collections import OrderedDict

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "output", "video_intelligence", "p04")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "output")

records_path = os.path.join(BASE, "video_records.json")
metrics_path = os.path.join(BASE, "video_metrics.json")

records = json.load(open(records_path, "r", encoding="utf-8"))
metrics = json.load(open(metrics_path, "r", encoding="utf-8"))
metrics_by_cid = {m["creative_id"]: m for m in metrics}

export = []
for r in records:
    cid = r["creative_id"]
    m = metrics_by_cid.get(cid, {})

    # Extract campaign and adset IDs from creative_name if present
    creative_name = r.get("creative_name", "")
    campaign_id = r.get("campaign_id", m.get("campaign_id", ""))
    adset_id = r.get("adset_id", m.get("adset_id", ""))
    ad_id = r.get("ad_id", m.get("ad_id", ""))

    export.append(OrderedDict([
        ("creative_id", cid),
        ("video_id", f"video_{cid}"),
        ("creative_name", creative_name),
        ("campaign_id", campaign_id),
        ("adset_id", adset_id),
        ("ad_id", ad_id),
        ("spend", m.get("spend", 0)),
        ("impression", m.get("impression", 0)),
        ("click", m.get("click", 0)),
        ("ctr_pct", m.get("ctr", 0)),
        ("install", m.get("install", 0)),
        ("purchase", m.get("purchase", 0)),
        ("revenue", m.get("revenue", 0)),
        ("roas", m.get("roas", 0)),
        ("thumbnail_url", r.get("thumbnail_url", "")),
        ("local_path", r.get("local_path", "")),
    ]))

out_path = os.path.join(OUT, "p04_facebook_creatives_export.csv")
with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=export[0].keys())
    w.writeheader()
    w.writerows(export)

print(f"Exported {len(export)} records to:")
print(f"  {out_path}")
print()

# Summary stats
total_spend = sum(e["spend"] for e in export)
total_impressions = sum(e["impression"] for e in export)
total_revenue = sum(e["revenue"] for e in export)
with_spend = sum(1 for e in export if e["spend"] > 0)
with_roas = sum(1 for e in export if e["roas"] > 0)
with_install = sum(1 for e in export if e["install"] > 0)
downloaded = sum(1 for e in export if e["local_path"])

print(f"Summary:")
print(f"  Total creatives:      {len(export)}")
print(f"  With spend > $0:      {with_spend}")
print(f"  With ROAS > 0:        {with_roas}")
print(f"  With installs > 0:    {with_install}")
print(f"  Local video files:    {downloaded}")
print(f"  Total spend:          ${total_spend:,.2f}")
print(f"  Total impressions:    {total_impressions:,.0f}")
print(f"  Total revenue:        ${total_revenue:,.2f}")
print(f"  Overall ROAS:         {total_revenue/total_spend:.4f}" if total_spend > 0 else "")
