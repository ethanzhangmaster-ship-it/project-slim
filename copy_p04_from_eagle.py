import json
import shutil
import os
from pathlib import Path

# Load Eagle assets index
assets_path = Path("output/video_intelligence/p04/eagle_assets_full.json")
with open(assets_path, "r", encoding="utf-8") as f:
    assets = json.load(f)

# Filter P04 videos
p04_assets = [a for a in assets if a["filename"].upper().startswith(("P4-", "P04-"))]
print(f"Total P04 video assets found in index: {len(p04_assets)}")

# Target directory
target_dir = Path("D:/project_slim/output/P04_videos_from_eagle")
target_dir.mkdir(parents=True, exist_ok=True)

# Copy files
copied = 0
skipped = 0
errors = 0

for asset in p04_assets:
    # Map Y:\Eagle\... to D:\...
    src_path = Path(asset["file_path"].replace("Y:\\Eagle\\", "D:\\"))
    
    if not src_path.exists():
        # Try alternate mapping
        src_path = Path(asset["file_path"].replace("Y:\\Eagle\\公司-市场部门库.library", "D:\\公司-市场部门库.library"))
    
    if not src_path.exists():
        print(f"  MISSING: {src_path}")
        errors += 1
        continue
    
    dst_path = target_dir / asset["filename"]
    
    if dst_path.exists():
        print(f"  SKIP (exists): {asset['filename']}")
        skipped += 1
        continue
    
    print(f"  COPY: {asset['filename']} ({asset.get('filesize', 0)/1024/1024:.1f} MB)")
    shutil.copy2(src_path, dst_path)
    copied += 1

print(f"\nDone! Copied: {copied}, Skipped: {skipped}, Missing: {errors}")
print(f"Output directory: {target_dir}")
