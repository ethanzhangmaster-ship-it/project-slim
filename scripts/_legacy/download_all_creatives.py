"""Download ALL available FB creative images — Winners + Losers for contrastive DNA.

Strategy:
  - Download as many as possible from Creative Mapping V2 (1484 records)
  - Classify: Winner (ROAS>1.5), Neutral (0.5-1.5), Loser (ROAS<0.5, spend>0)
  - Prioritize: Winners first, then high-spend losers, then rest
  - Save with performance tier tags for contrastive DNA analysis
"""
import csv
import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(r"d:\project_slim\project_slim")
TOKEN = os.environ.get("FB_TOKEN", "") or os.environ.get("META_ACCESS_TOKEN", "")
API_VERSION = os.environ.get("META_API_VERSION", "v19.0")
BASE = f"https://graph.facebook.com/{API_VERSION}"

OUT_DIR = ROOT / "output" / "creative_analysis" / "real_assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Step 1: Load ALL creatives with performance data ──

def load_all_creatives():
    """Load all creatives from Creative Mapping V2 with performance tiers."""
    mapping_path = ROOT / "output" / "video_intelligence" / "p04" / "creative_mapping_v2.csv"
    with open(mapping_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Total rows in CSV: {len(rows)}")
    
    all_creatives = []
    for r in rows:
        try:
            cid = r.get("creative_id", "").strip()
            if not cid:
                continue
            
            spend = float(r.get("spend", 0) or 0)
            revenue = float(r.get("revenue", 0) or 0)
            roas = float(r.get("roas", 0) or 0)
            installs = int(float(r.get("installs", 0) or 0))
            
            ad_name = (r.get("ad_name") or "").strip()
            platform = "unknown"
            if "IOS" in (ad_name or ""):
                platform = "iOS"
            elif "And" in (ad_name or ""):
                platform = "Android"
            
            # Classify performance tier
            if roas > 1.5:
                tier = "winner"
            elif roas >= 0.5:
                tier = "neutral"
            elif spend > 0:
                tier = "loser"
            else:
                tier = "unknown"  # No spend data
            
            # Composite priority score
            # Winners: sort by ROAS * revenue (most profitable first)
            # Losers: sort by spend (most wasted money first, to learn from)
            # Neutral: sort by spend
            if tier == "winner":
                priority = roas * revenue
            elif tier == "loser":
                priority = spend  # High spend + low ROAS = most to learn
            else:
                priority = spend
            
            all_creatives.append({
                "creative_id": cid,
                "platform": platform,
                "spend": spend,
                "revenue": revenue,
                "roas": roas,
                "installs": installs,
                "tier": tier,
                "priority": priority,
                "creative_name": (r.get("creative_name") or "").strip(),
                "ad_name": ad_name,
                "eagle_filename": (r.get("eagle_filename") or "").strip(),
            })
        except (ValueError, TypeError, KeyError):
            continue
    
    # Sort by priority descending
    all_creatives.sort(key=lambda x: x["priority"], reverse=True)
    
    return all_creatives


# ── Step 2: Get high-res image URL from FB API ──

def get_creative_image_url(creative_id):
    """Get high-res image URL from FB Graph API creative endpoint."""
    url = f"{BASE}/{creative_id}"
    params = {
        "access_token": TOKEN,
        "fields": "id,name,image_url,thumbnail_url,object_story_spec{link_data,video_data{image_url,image_hash}}",
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            code = data["error"].get("code", 0)
            return None, f"API_ERROR:{code}:{error_msg}"
        
        oss = data.get("object_story_spec", {})
        video_data = oss.get("video_data", {})
        image_url = video_data.get("image_url", "")
        if image_url:
            return image_url, "video_data.image_url"
        
        image_url = data.get("image_url", "")
        if image_url:
            return image_url, "direct_image_url"
        
        return None, "No image_url found"
    except Exception as e:
        return None, str(e)


# ── Step 3: Download image ──

def download_image(creative_id, image_url, tier):
    """Download image with tier-specific naming."""
    filename = f"fb_{tier}_{creative_id}.jpg"
    filepath = OUT_DIR / filename
    
    if filepath.exists():
        return str(filepath), filepath.stat().st_size // 1024
    
    try:
        resp = requests.get(image_url, timeout=60)
        if resp.status_code != 200:
            return None, 0
        filepath.write_bytes(resp.content)
        return str(filepath), len(resp.content) // 1024
    except Exception:
        return None, 0


# ── Main ──

def main():
    print("=" * 60)
    print("Downloading ALL FB Creative Images — Winners + Losers")
    print("=" * 60)
    print(f"Token: {'YES' if TOKEN else 'NO'} ({len(TOKEN)} chars)")
    print(f"API: {BASE}\n")
    
    # Step 1: Load all creatives
    all_creatives = load_all_creatives()
    print(f"Loaded {len(all_creatives)} creatives with performance data")
    
    # Performance tier distribution
    from collections import Counter
    tiers = Counter(c["tier"] for c in all_creatives)
    print(f"Tier distribution: {dict(tiers)}")
    print(f"  Winners (ROAS>1.5): {tiers['winner']}")
    print(f"  Neutral (0.5-1.5): {tiers['neutral']}")
    print(f"  Losers (ROAS<0.5): {tiers['loser']}")
    print(f"  Unknown (no spend): {tiers['unknown']}")
    
    # Show top winners and top losers
    winners = [c for c in all_creatives if c["tier"] == "winner"]
    losers = [c for c in all_creatives if c["tier"] == "loser"]
    print(f"\nTop 5 Winners:")
    for i, w in enumerate(winners[:5]):
        print(f"  [{i+1}] {w['creative_id']} ({w['platform']}) "
              f"spend=${w['spend']:.0f} rev=${w['revenue']:.0f} roas={w['roas']:.2f}")
    print(f"\nTop 5 Losers (highest spend, low ROAS):")
    top_losers = sorted(losers, key=lambda x: x["spend"], reverse=True)[:5]
    for i, l in enumerate(top_losers):
        print(f"  [{i+1}] {l['creative_id']} ({l['platform']}) "
              f"spend=${l['spend']:.0f} rev=${l['revenue']:.0f} roas={l['roas']:.2f}")
    
    # Step 2 & 3: Download images
    # Strategy: download up to 200 (FB API rate limit ~200/hr)
    # Priority: winners first, then high-spend losers, then neutral
    MAX_DOWNLOADS = 200
    download_queue = all_creatives[:MAX_DOWNLOADS]
    
    print(f"\n{'='*60}")
    print(f"Downloading up to {MAX_DOWNLOADS} creatives...")
    print("=" * 60)
    
    results = []
    stats = {"winner": {"ok": 0, "fail": 0}, "neutral": {"ok": 0, "fail": 0}, 
             "loser": {"ok": 0, "fail": 0}, "unknown": {"ok": 0, "fail": 0}}
    rate_limit_hit = False
    
    for i, c in enumerate(download_queue):
        if rate_limit_hit:
            break
            
        cid = c["creative_id"]
        tier = c["tier"]
        
        # Skip if already downloaded (check by creative_id pattern, ignoring tier prefix)
        existing = list(OUT_DIR.glob(f"fb_*_{cid}.jpg"))
        if existing:
            results.append({**c, "local_path": str(existing[0]), "size_kb": existing[0].stat().st_size // 1024, "source_type": "cached"})
            stats[tier]["ok"] += 1
            continue
        
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(download_queue)}] {stats['winner']['ok']}W/{stats['loser']['ok']}L/{stats['neutral']['ok']}N OK, "
                  f"{stats['winner']['fail']+stats['loser']['fail']+stats['neutral']['fail']} failed")
        
        # Get image URL
        image_url, source_type = get_creative_image_url(cid)
        
        if not image_url:
            if "API_ERROR" in source_type:
                code = source_type.split(":")[1]
                if code == "4" or code == "80004":  # Rate limit
                    print(f"  RATE LIMIT HIT at [{i+1}/{len(download_queue)}]")
                    rate_limit_hit = True
                    break
            stats[tier]["fail"] += 1
            results.append({**c, "local_path": None, "source_type": source_type, "size_kb": 0, "error": source_type})
            continue
        
        # Download
        local_path, size_kb = download_image(cid, image_url, tier)
        
        if local_path:
            stats[tier]["ok"] += 1
            results.append({**c, "local_path": local_path, "source_type": source_type, "size_kb": size_kb})
        else:
            stats[tier]["fail"] += 1
            results.append({**c, "local_path": None, "source_type": source_type, "size_kb": 0, "error": "download_failed"})
        
        # Rate limit protection
        time.sleep(0.3)
    
    # Summary
    total_ok = sum(s["ok"] for s in stats.values())
    total_fail = sum(s["fail"] for s in stats.values())
    print(f"\n{'='*60}")
    print(f"DOWNLOAD SUMMARY: {total_ok} downloaded, {total_fail} failed")
    print(f"  Winners: {stats['winner']['ok']} OK / {stats['winner']['fail']} fail")
    print(f"  Neutral: {stats['neutral']['ok']} OK / {stats['neutral']['fail']} fail")
    print(f"  Losers:  {stats['loser']['ok']} OK / {stats['loser']['fail']} fail")
    print(f"  Unknown: {stats['unknown']['ok']} OK / {stats['unknown']['fail']} fail")
    print("=" * 60)
    
    # Save results
    output_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "all_creatives_dna.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    dna_records = []
    for r in results:
        if r.get("local_path"):
            dna_records.append({
                "creative_id": r["creative_id"],
                "creative_name": r["creative_name"],
                "platform": r["platform"],
                "tier": r["tier"],
                "spend": r["spend"],
                "revenue": r["revenue"],
                "roas": r["roas"],
                "installs": r["installs"],
                "local_image_path": r["local_path"],
                "size_kb": r.get("size_kb", 0),
                "eagle_filename": r["eagle_filename"],
                "visual_dna": {"source": "real_facebook_ad", "status": "pending_ai_analysis"},
                "extracted_at": datetime.now().isoformat(),
            })
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.0.0",
            "source": "facebook_graph_api",
            "total_downloaded": total_ok,
            "total_failed": total_fail,
            "tier_counts": {t: s["ok"] for t, s in stats.items()},
            "creatives": dna_records,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved {len(dna_records)} DNA records to: {output_path}")
    print(f"Images directory: {OUT_DIR}")
    
    # Show tier balance
    tier_balance = Counter(r["tier"] for r in dna_records)
    print(f"\nFinal Tier Balance:")
    for t in ["winner", "neutral", "loser", "unknown"]:
        count = tier_balance.get(t, 0)
        bar = "█" * (count // 2)
        print(f"  {t:10s}: {count:3d} {bar}")


if __name__ == "__main__":
    main()