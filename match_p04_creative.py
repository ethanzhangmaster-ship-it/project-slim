"""P04 Creative Mapping v2 — dual pattern: A### + 视频N."""
import json, re, csv
from pathlib import Path
from collections import defaultdict

ROOT = Path("d:/project_slim/project_slim")
OUT = ROOT / "output" / "video_intelligence" / "p04"


def extract_a_number(text):
    if not text:
        return None
    m = re.search(r'-A(\d{2,4})-', str(text))
    return m.group(1) if m else None


def extract_video_number(text):
    if not text:
        return None
    m = re.search(r'视频(\d+)', str(text))
    return m.group(1) if m else None


def build_v_index(assets):
    v_index = {}
    for asset in assets:
        fname = (asset.get("filename_without_ext", "") or asset.get("filename", ""))
        m = re.search(r'v(\d+)', fname)
        if m:
            v_index[int(m.group(1))] = asset
    return v_index


def main():
    print("=" * 70)
    print("P04 CREATIVE MAPPING v2 — A### + 视频N dual pattern")
    print("=" * 70)

    with open(OUT / "eagle_assets_full.json", "r", encoding="utf-8") as f:
        eagle_assets = json.load(f)
    v_index = build_v_index(eagle_assets)
    print(f"Eagle assets: {len(eagle_assets)}, v-numbers: {len(v_index)}")

    with open(OUT / "p04_full_ad_hierarchy.json", "r", encoding="utf-8") as f:
        fb_data = json.load(f)
    records = fb_data.get("records", [])
    fb_videos = [r for r in records if r.get("creative_type") == "video"]
    print(f"FB video ads: {len(fb_videos)}")

    # Old-format mapping from creative_mapping.json
    OLD_FORMAT = {
        "2": 2601002, "3": 2601003, "4": 2601004, "5": 2601005,
        "6": 2601006, "7": 2601007, "8": 2601008,
    }

    matched = []
    unmatched = []

    for r in fb_videos:
        ad_name = r.get("ad_name", "")
        adset_name = r.get("adset_name", "")
        creative_name = r.get("creative_name", "")

        a_num = extract_a_number(ad_name) or extract_a_number(adset_name) or extract_a_number(creative_name)
        vid_num = extract_video_number(ad_name) or extract_video_number(adset_name)

        v_key = None
        method = None

        if a_num:
            v_key = int(f"2601{a_num.zfill(3)}")
            method = f"A-number (A{a_num})"
        elif vid_num and vid_num in OLD_FORMAT:
            v_key = OLD_FORMAT[vid_num]
            method = f"video_number (视频{vid_num})"

        asset = v_index.get(v_key) if v_key else None

        if asset:
            fname = (asset.get("filename_without_ext", "") or asset.get("filename", ""))
            m = re.search(r'v(\d+)', fname)
            vnum = f"v{m.group(1)}" if m else ""
            matched.append({
                "creative_id": r.get("creative_id", ""),
                "creative_name": creative_name,
                "ad_id": r.get("ad_id", ""),
                "ad_name": ad_name,
                "adset_name": adset_name,
                "campaign_name": r.get("campaign_name", ""),
                "account_name": r.get("account_name", ""),
                "effective_status": r.get("effective_status", ""),
                "creative_type": r.get("creative_type", ""),
                "video_id": r.get("video_id", ""),
                "a_number": a_num or "",
                "video_number": vid_num or "",
                "eagle_v_number": vnum,
                "eagle_filename": fname,
                "eagle_filepath": asset.get("file_path", ""),
                "eagle_folder": asset.get("folder_path", ""),
                "match_method": method,
                "confidence": 1.0,
                "spend": r.get("spend", 0),
                "impressions": r.get("impressions", 0),
                "clicks": r.get("clicks", 0),
                "ctr": r.get("ctr", 0),
                "installs": r.get("installs", 0),
                "purchases": r.get("purchases", 0),
                "revenue": r.get("revenue", 0),
                "roas": r.get("roas", 0),
                "cpa": r.get("cpa", 0),
                "thumbnail_url": r.get("thumbnail_url", ""),
                "campaign_id": r.get("campaign_id", ""),
                "adset_id": r.get("adset_id", ""),
            })
        else:
            unmatched.append({
                "creative_id": r.get("creative_id", ""),
                "creative_name": creative_name,
                "ad_id": r.get("ad_id", ""),
                "ad_name": ad_name,
                "adset_name": adset_name,
                "campaign_name": r.get("campaign_name", ""),
                "creative_type": r.get("creative_type", ""),
                "video_id": r.get("video_id", ""),
                "spend": r.get("spend", 0),
                "roas": r.get("roas", 0),
            })

    matched_spend = sum(r["spend"] for r in matched)
    unmatched_spend = sum(r["spend"] for r in unmatched)
    total_spend = matched_spend + unmatched_spend

    print(f"\n{'='*70}")
    print(f"MATCHING RESULT")
    print(f"{'='*70}")
    print(f"Matched:    {len(matched):>6} ads | ${matched_spend:>12,.2f} | {matched_spend/total_spend*100:>5.1f}%")
    print(f"Unmatched:  {len(unmatched):>6} ads | ${unmatched_spend:>12,.2f} | {unmatched_spend/total_spend*100:>5.1f}%")
    print(f"Total:      {len(fb_videos):>6} ads | ${total_spend:>12,.2f}")

    eagle_vnums = set(r["eagle_v_number"] for r in matched)
    print(f"\nUnique Eagle files matched: {len(eagle_vnums)}")
    print(f"Match rate by spend: {matched_spend/total_spend*100:.1f}%")

    # Match method breakdown
    method_dist = defaultdict(lambda: {"count": 0, "spend": 0.0, "ads": []})
    for r in matched:
        m = r["match_method"]
        method_dist[m]["count"] += 1
        method_dist[m]["spend"] += r["spend"]

    print(f"\nMatch method breakdown:")
    for m, d in sorted(method_dist.items(), key=lambda x: -x[1]["spend"]):
        print(f"  {m}: {d['count']} ads, ${d['spend']:,.2f}")

    # Top Eagle by spend
    eagle_spend = defaultdict(lambda: {"spend": 0.0, "revenue": 0.0, "count": 0, "fname": ""})
    for r in matched:
        v = r["eagle_v_number"]
        eagle_spend[v]["spend"] += r["spend"]
        eagle_spend[v]["revenue"] += r["revenue"]
        eagle_spend[v]["count"] += 1
        if not eagle_spend[v]["fname"]:
            eagle_spend[v]["fname"] = r["eagle_filename"]

    print(f"\nTop 20 Eagle files by spend:")
    print(f"{'V-Number':<14} | {'Ads':>5} | {'Spend':>12} | {'Revenue':>12} | {'ROAS':>6}")
    print("-" * 65)
    for v, d in sorted(eagle_spend.items(), key=lambda x: -x[1]["spend"])[:20]:
        roas = d["revenue"] / d["spend"] if d["spend"] > 0 else 0
        print(f"  {v:<12} | {d['count']:>5} | ${d['spend']:>11,.2f} | ${d['revenue']:>11,.2f} | {roas:>5.3f}  {d['fname'][:30]}")

    # Save
    out_json = OUT / "creative_mapping_v2.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "total_fb_videos": len(fb_videos),
            "matched": len(matched),
            "unmatched": len(unmatched),
            "matched_spend": matched_spend,
            "unmatched_spend": unmatched_spend,
            "unique_eagle_matched": len(eagle_vnums),
            "match_records": matched,
            "unmatched_records": unmatched,
        }, f, ensure_ascii=False, indent=2, default=str)

    out_csv = OUT / "creative_mapping_v2_b.csv"
    fieldnames = [
        "creative_id", "creative_name", "ad_id", "ad_name",
        "adset_name", "adset_id", "campaign_name", "campaign_id",
        "account_name", "effective_status", "creative_type",
        "video_id", "a_number", "video_number", "eagle_v_number",
        "eagle_filename", "eagle_filepath",
        "match_method", "confidence",
        "spend", "impressions", "clicks", "ctr",
        "installs", "purchases", "revenue", "roas", "cpa",
        "thumbnail_url",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(matched)

    print(f"\nSaved: {out_json}")
    print(f"Saved: {out_csv}")
    print(f"\nTotal P04 video spend: ${total_spend:,.2f}")
    print(f"Matched: ${matched_spend:,.2f} ({matched_spend/total_spend*100:.1f}%)")


if __name__ == "__main__":
    main()
