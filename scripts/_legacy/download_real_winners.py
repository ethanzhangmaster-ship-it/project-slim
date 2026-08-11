"""Download real winner creative images via FB Graph API.

Approach: Use FB Graph API to get object_story_spec.video_data.image_url
(ads/image URL) which returns high-res (720x1280) creative images.
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

# ── Step 1: Select top winners ──

def select_top_winners(max_count=50):
    mapping_path = ROOT / "output" / "video_intelligence" / "p04" / "creative_mapping_v2.csv"
    with open(mapping_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    valid = []
    for r in rows:
        try:
            cid = r.get("creative_id", "").strip()
            spend = float(r.get("spend", 0) or 0)
            revenue = float(r.get("revenue", 0) or 0)
            thumbnail = (r.get("thumbnail_url") or "").strip()
            eagle_file = (r.get("eagle_filename") or "").strip()
            ad_name = (r.get("ad_name") or "").strip()
            
            if not cid:
                continue
            
            platform = "unknown"
            if "IOS" in (ad_name or ""):
                platform = "iOS"
            elif "And" in (ad_name or ""):
                platform = "Android"
            
            spend_log = min(spend / 100, 1.0) if spend > 0 else 0.01
            composite = revenue * spend_log
            
            valid.append({
                "creative_id": cid,
                "platform": platform,
                "spend": spend,
                "revenue": revenue,
                "roas": float(r.get("roas", 0) or 0),
                "installs": int(float(r.get("installs", 0) or 0)),
                "creative_name": (r.get("creative_name") or "").strip(),
                "eagle_filename": eagle_file,
                "thumbnail_url": thumbnail,
            })
        except (ValueError, TypeError, KeyError):
            continue
    
    valid.sort(key=lambda x: x["revenue"] * min(x["spend"] / 100, 1.0), reverse=True)
    return valid[:max_count]


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
            return None, data["error"].get("message", "Unknown error")
        
        # Priority 1: object_story_spec.video_data.image_url (ads/image - high res)
        oss = data.get("object_story_spec", {})
        video_data = oss.get("video_data", {})
        image_url = video_data.get("image_url", "")
        if image_url:
            return image_url, "video_data.image_url"
        
        # Priority 2: direct image_url
        image_url = data.get("image_url", "")
        if image_url:
            return image_url, "direct_image_url"
        
        # Priority 3: link_data image
        link_data = oss.get("link_data", {})
        image_url = link_data.get("image_url", "")
        if image_url:
            return image_url, "link_data.image_url"
        
        return None, "No image_url found"
    except Exception as e:
        return None, str(e)


# ── Step 3: Download image ──

def download_image(creative_id, image_url, source_type):
    """Download image from URL."""
    filename = f"fb_{creative_id}.jpg"
    filepath = OUT_DIR / filename
    
    if filepath.exists():
        size_kb = filepath.stat().st_size // 1024
        return str(filepath), size_kb
    
    try:
        resp = requests.get(image_url, timeout=60)
        if resp.status_code != 200:
            return None, 0
        
        filepath.write_bytes(resp.content)
        size_kb = len(resp.content) // 1024
        return str(filepath), size_kb
    except Exception as e:
        return None, 0


# ── Main ──

def main():
    print("=" * 60)
    print("Downloading Real Winner Images via FB Graph API")
    print("=" * 60)
    print(f"Token: {'YES' if TOKEN else 'NO'} ({len(TOKEN)} chars)")
    print(f"API: {BASE}\n")
    
    # Step 1: Select winners
    winners = select_top_winners(50)
    print(f"Selected {len(winners)} winners from Creative Mapping V2")
    print(f"Top 5:")
    for i, w in enumerate(winners[:5]):
        print(f"  [{i+1}] {w['creative_id']} ({w['platform']}) "
              f"spend=${w['spend']:.0f} revenue=${w['revenue']:.0f} roas={w['roas']:.2f}")
    
    # Step 2 & 3: Get image URLs and download
    print(f"\n{'='*60}")
    print("Fetching image URLs via FB Graph API...")
    print("=" * 60)
    
    results = []
    success_count = 0
    fail_count = 0
    api_errors = 0
    
    for i, w in enumerate(winners):
        cid = w["creative_id"]
        print(f"\n[{i+1}/{len(winners)}] {cid} ({w['platform']}) "
              f"spend=${w['spend']:.0f} rev=${w['revenue']:.0f}")
        
        # Get image URL from FB API
        image_url, source_type = get_creative_image_url(cid)
        
        if not image_url:
            print(f"  SKIP: {source_type}")
            api_errors += 1
            results.append({**w, "local_path": None, "source_type": source_type, "error": source_type})
            continue
        
        print(f"  Source: {source_type}")
        print(f"  URL: {image_url[:100]}...")
        
        # Download
        local_path, size_kb = download_image(cid, image_url, source_type)
        
        if local_path:
            print(f"  SAVED: {size_kb}KB")
            success_count += 1
            results.append({**w, "local_path": local_path, "source_type": source_type, "size_kb": size_kb})
        else:
            print(f"  FAIL: download error")
            fail_count += 1
            results.append({**w, "local_path": None, "source_type": source_type, "error": "download_failed"})
        
        # Rate limit protection
        time.sleep(0.5)
    
    # Save results
    print(f"\n{'='*60}")
    print(f"SUMMARY: {success_count} downloaded, {fail_count} failed, {api_errors} API errors")
    print("=" * 60)
    
    output_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "real_winners_dna.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    dna_records = []
    for r in results:
        dna_records.append({
            "creative_id": r["creative_id"],
            "creative_name": r["creative_name"],
            "platform": r["platform"],
            "spend": r["spend"],
            "revenue": r["revenue"],
            "roas": r["roas"],
            "installs": r["installs"],
            "local_image_path": r.get("local_path", ""),
            "source_type": r.get("source_type", "unknown"),
            "size_kb": r.get("size_kb", 0),
            "eagle_filename": r["eagle_filename"],
            "visual_dna": {"source": "real_facebook_ad", "status": "pending_ai_analysis"},
            "extracted_at": datetime.now().isoformat(),
        })
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dna_records, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved DNA records to: {output_path}")
    print(f"Images saved to: {OUT_DIR}")
    print(f"Total: {len(dna_records)} records")


if __name__ == "__main__":
    main()