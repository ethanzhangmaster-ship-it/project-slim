"""Rebuild Winner DNA from real Facebook ad data.

Step 1: Select real winners from Creative Mapping V2
Step 2: Download real FB thumbnail images
Step 3: Extract visual DNA from real images
"""
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(r"d:\project_slim\project_slim")
OUTPUT = ROOT / "output" / "creative_analysis" / "dna_cache"

# ── Step 1: Select real winners ──

def select_real_winners():
    """Select real winners from Creative Mapping V2 by combined revenue + spend."""
    mapping_path = ROOT / "output" / "video_intelligence" / "p04" / "creative_mapping_v2.csv"
    
    print("=" * 60)
    print("Step 1: Selecting real winners from Creative Mapping V2")
    print("=" * 60)
    
    with open(mapping_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Total rows: {len(rows)}")
    print(f"Columns: {list(reader.fieldnames)}")
    
    # Parse and filter
    valid = []
    for r in rows:
        try:
            cid = r.get("creative_id", "").strip()
            spend = float(r.get("spend", 0) or 0)
            revenue = float(r.get("revenue", 0) or 0)
            installs = int(float(r.get("installs", 0) or 0))
            roas = float(r.get("roas", 0) or 0)
            ctr_val = float(r.get("ctr", 0) or 0)
            thumbnail = (r.get("thumbnail_url") or "").strip()
            eagle_file = (r.get("eagle_filename") or "").strip()
            creative_name = (r.get("creative_name") or "").strip()
            ad_name = (r.get("ad_name") or "").strip()
            campaign_name = (r.get("campaign_name") or "").strip()
            
            if not cid or not thumbnail:
                continue
            
            # Determine platform
            platform = "unknown"
            if "IOS" in (ad_name or ""):
                platform = "iOS"
            elif "And" in (ad_name or ""):
                platform = "Android"
            
            # Composite score: revenue weighted by spend confidence
            # Prefer higher spend (more reliable) AND higher revenue
            spend_log = min(spend / 100, 1.0) if spend > 0 else 0.01
            composite = revenue * spend_log
            
            valid.append({
                "creative_id": cid,
                "creative_name": creative_name,
                "ad_name": ad_name,
                "campaign_name": campaign_name,
                "platform": platform,
                "spend": spend,
                "revenue": revenue,
                "installs": installs,
                "roas": roas,
                "ctr": ctr_val,
                "thumbnail_url": thumbnail,
                "eagle_filename": eagle_file,
                "composite_score": composite,
            })
        except (ValueError, TypeError, KeyError):
            continue
    
    # Sort by composite score
    valid.sort(key=lambda x: x["composite_score"], reverse=True)
    
    print(f"\nValid entries (has thumbnail + creative_id): {len(valid)}")
    print(f"With spend > $10: {sum(1 for v in valid if v['spend'] > 10)}")
    print(f"With revenue > $0: {sum(1 for v in valid if v['revenue'] > 0)}")
    
    # Platform breakdown
    ios_count = sum(1 for v in valid if v["platform"] == "iOS")
    android_count = sum(1 for v in valid if v["platform"] == "Android")
    print(f"iOS: {ios_count}, Android: {android_count}, Unknown: {len(valid) - ios_count - android_count}")
    
    # Top 20
    print("\n--- Top 20 Winners ---")
    for i, v in enumerate(valid[:20]):
        print(f"  [{i+1:2d}] {v['creative_id']} ({v['platform']})")
        print(f"       spend={v['spend']:.1f} revenue={v['revenue']:.1f} roas={v['roas']:.4f} installs={v['installs']}")
        print(f"       name={v['creative_name'][:60]}")
        print(f"       eagle={v['eagle_filename']}")
    
    return valid

# ── Step 2: Download images ──

def download_images(winners, max_count=20):
    """Download real FB thumbnail images for top winners."""
    import urllib.request
    import ssl
    
    assets_dir = ROOT / "output" / "creative_analysis" / "real_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 60)
    print(f"Step 2: Downloading real FB images (top {max_count})")
    print("=" * 60)
    
    # Create SSL context that ignores cert errors (FB CDN sometimes has issues)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    downloaded = []
    for i, w in enumerate(winners[:max_count]):
        url = w["thumbnail_url"]
        cid = w["creative_id"]
        filename = f"fb_{cid}.jpg"
        filepath = assets_dir / filename
        
        if filepath.exists():
            print(f"  [{i+1:2d}] Already exists: {filename}")
            w["local_image_path"] = str(filepath)
            downloaded.append(w)
            continue
        
        try:
            print(f"  [{i+1:2d}] Downloading {cid}...")
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                data = resp.read()
            filepath.write_bytes(data)
            size_kb = len(data) / 1024
            print(f"       Saved: {filename} ({size_kb:.0f}KB)")
            w["local_image_path"] = str(filepath)
            downloaded.append(w)
        except Exception as e:
            print(f"       FAILED: {e}")
    
    print(f"\nDownloaded: {len(downloaded)}/{max_count}")
    return downloaded

# ── Step 3: Extract visual DNA ──

def extract_visual_dna(winners_with_images):
    """Extract visual DNA from real FB ad images using AI analysis."""
    print("\n" + "=" * 60)
    print("Step 3: Extracting visual DNA from real images")
    print("=" * 60)
    
    # For now, build a structured DNA record from available metadata
    # Full AI visual analysis will be added in a follow-up step
    dna_records = []
    
    for w in winners_with_images:
        record = {
            "creative_id": w["creative_id"],
            "creative_name": w["creative_name"],
            "platform": w["platform"],
            "campaign_name": w["campaign_name"],
            # Real performance data
            "spend": w["spend"],
            "revenue": w["revenue"],
            "installs": w["installs"],
            "roas": w["roas"],
            "ctr": w["ctr"],
            # Local assets
            "local_image_path": w.get("local_image_path", ""),
            "thumbnail_url": w["thumbnail_url"],
            "eagle_filename": w["eagle_filename"],
            # DNA placeholder (will be filled by AI analysis)
            "visual_dna": {
                "source": "real_facebook_ad",
                "status": "pending_ai_analysis",
            },
            "extracted_at": datetime.now().isoformat(),
        }
        dna_records.append(record)
    
    # Save
    output_path = OUTPUT / "real_winners_dna.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dna_records, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(dna_records)} records to {output_path}")
    return dna_records

# ── Main ──

if __name__ == "__main__":
    # Step 1
    winners = select_real_winners()
    
    if not winners:
        print("ERROR: No valid winners found!")
        sys.exit(1)
    
    # Step 2
    winners_with_images = download_images(winners, max_count=20)
    
    if not winners_with_images:
        print("ERROR: No images downloaded!")
        sys.exit(1)
    
    # Step 3
    dna_records = extract_visual_dna(winners_with_images)
    
    print("\n" + "=" * 60)
    print("Rebuild Complete!")
    print("=" * 60)
    print(f"Real winners: {len(dna_records)}")
    print(f"Output: {OUTPUT / 'real_winners_dna.json'}")
    print(f"Images: {ROOT / 'output' / 'creative_analysis' / 'real_assets' / 'fb_*.jpg'}")