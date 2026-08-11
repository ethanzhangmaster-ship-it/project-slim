"""Export P04 905 Facebook videos CSV with FB backend links."""
import json, csv, os
from collections import OrderedDict

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "output", "video_intelligence", "p04")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "output")

# Facebook ad account from env (see .env)
ACT_ID = "1455525822955003"
ADS_MANAGER_BASE = f"https://business.facebook.com/adsmanager/manage/creatives?act={ACT_ID}"
AD_LIBRARY_BASE = "https://www.facebook.com/ads/library/?id="

full = json.load(open(os.path.join(BASE, "p4_full_export_all_accounts.json"), "r", encoding="utf-8"))
videos = full.get("videos", [])

export = []
for v in videos:
    video_id = v.get("video_id", "")
    creative_ids = v.get("creative_ids", [])
    creative_names = v.get("creative_names", [])
    ad_names = v.get("ad_names", [])

    if not creative_ids:
        ads_mgr_url = ""
        ad_lib_url = ""
        row = OrderedDict([
            ("video_id", video_id),
            ("video_title", v.get("video_title", "")),
            ("creative_id", ""),
            ("creative_name", v.get("video_title", "")),
            ("ad_name", ""),
            ("platforms", ";".join(v.get("platforms", []))),
            ("spend", v.get("total_spend", 0)),
            ("impressions", v.get("total_impressions", 0)),
            ("installs", v.get("total_installs", 0)),
            ("revenue", v.get("total_revenue", 0)),
            ("roas", v.get("total_revenue", 0) / v.get("total_spend", 1) if v.get("total_spend", 0) > 0 else 0),
            ("duration_sec", v.get("video_length", 0)),
            ("thumbnail_url", v.get("video_picture", "")),
            ("created_time", v.get("video_created_time", "")),
            ("ads_manager_url", ads_mgr_url),
            ("ad_library_url", ad_lib_url),
        ])
        export.append(row)
    else:
        for i, cid in enumerate(creative_ids):
            creative_name = creative_names[i] if i < len(creative_names) else ""
            ad_name = ad_names[i] if i < len(ad_names) else ""

            ads_mgr_url = f"{ADS_MANAGER_BASE}&creative_ids%5B0%5D={cid}" if cid else ""
            ad_lib_url = f"{AD_LIBRARY_BASE}{cid}" if cid else ""

            row = OrderedDict([
                ("video_id", video_id),
                ("video_title", v.get("video_title", "")),
                ("creative_id", cid),
                ("creative_name", creative_name),
                ("ad_name", ad_name),
                ("platforms", ";".join(v.get("platforms", []))),
                ("spend", v.get("total_spend", 0)),
                ("impressions", v.get("total_impressions", 0)),
                ("installs", v.get("total_installs", 0)),
                ("revenue", v.get("total_revenue", 0)),
                ("roas", v.get("total_revenue", 0) / v.get("total_spend", 1) if v.get("total_spend", 0) > 0 else 0),
                ("duration_sec", v.get("video_length", 0)),
                ("thumbnail_url", v.get("video_picture", "")),
                ("created_time", v.get("video_created_time", "")),
                ("ads_manager_url", ads_mgr_url),
                ("ad_library_url", ad_lib_url),
            ])
            export.append(row)

out_path = os.path.join(OUT, "p04_all_905_facebook_videos.csv")
with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=export[0].keys())
    w.writeheader()
    w.writerows(export)

total_spend = sum(float(v.get("total_spend", 0) or 0) for v in videos)
total_rev = sum(float(v.get("total_revenue", 0) or 0) for v in videos)

print(f"Exported {len(export)} records to:")
print(f"  {out_path}")
print()
print(f"Summary:")
print(f"  Total videos:  {len(videos)}")
print(f"  Total spend:   ${total_spend:,.2f}")
print(f"  Total revenue: ${total_rev:,.2f}")
print(f"  Overall ROAS:  {total_rev/total_spend:.4f}" if total_spend > 0 else "")
print(f"\nLink fields:")
print(f"  ads_manager_url - 点开直接跳到 FB Ads Manager 的 creative 页面（需登录）")
print(f"  ad_library_url  - 点开跳到 FB Ad Library 公开预览页（无需登录）")
