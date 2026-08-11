"""仅执行 Facebook 发布步骤 (使用已生成的图片)"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip()

# Use the first successful run's images
image_dir = ROOT / "output" / "creative_growth_loop" / "images" / "closed_loop_20260630_070327"
images = sorted(image_dir.glob("*.png"))
print(f"Images found: {len(images)}")
for img in images:
    print(f"  {img.name} ({img.stat().st_size} bytes)")

# Import FacebookPublisher
_publish_dir = str(ROOT / "src" / "market_ops" / "creative_growth_loop" / "14_publish")
sys.path.insert(0, _publish_dir)
from facebook_publisher import FacebookPublisher

token = os.getenv("META_ACCESS_TOKEN", "")
ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
page_id = os.getenv("CLOSED_LOOP_PAGE_ID", "")
adset_id = os.getenv("CLOSED_LOOP_ADSET_ID", "")
api_version = os.getenv("META_API_VERSION", "v19.0")

print(f"\nAd Account: {ad_account_id}")
print(f"Page ID: {page_id}")
print(f"Adset ID: {adset_id}")
print(f"API Version: {api_version}")

publisher = FacebookPublisher(
    access_token=token,
    ad_account_id=ad_account_id,
    api_version=api_version,
    page_id=page_id,
)

# Load directives for headlines
directives_path = ROOT / "output" / "pipeline_directives.json"
if directives_path.exists():
    directives = json.loads(directives_path.read_text(encoding="utf-8"))
    winners = directives.get("directives", {})
    game_w = winners.get("game", {}).get("target", "P04 Witch")
    tone_w = winners.get("color_tone", {}).get("target", "cool")
    layout_w = winners.get("layout", {}).get("target", "top_bottom")
else:
    game_w, tone_w, layout_w = "P04 Witch", "cool", "top_bottom"

headlines = [f"{game_w} - {tone_w} {layout_w}"] * 5
primary_texts = [
    "Can you solve this? 🔮",
    "Merge & conquer! Try now 👇",
    "The most satisfying puzzle game!",
    "Test your skills - can you beat it?",
    "Addictive puzzle fun awaits!",
]
run_id = datetime.now().strftime("closed_loop_%Y%m%d_%H%M%S")
ad_names = [f"AI_{run_id}_{i:02d}" for i in range(len(images))]

image_paths = [str(p) for p in images]

# Step 1: Upload
print(f"\n📤 Uploading {len(image_paths)} images...")
image_hashes = publisher.upload_images(image_paths)
print(f"✅ Uploaded: {len(image_hashes)}/{len(image_paths)}")

if not image_hashes:
    print("❌ Upload failed")
    sys.exit(1)

# Step 2: Create creatives
print(f"\n🎨 Creating ad creatives (v={api_version})...")
creative_ids = publisher.create_ad_creatives(
    image_hashes=image_hashes,
    headlines=headlines[:len(image_hashes)],
    primary_texts=primary_texts[:len(image_hashes)],
)
print(f"✅ Creatives: {len(creative_ids)}/{len(image_hashes)}")

if not creative_ids:
    # Try to get more details about the error
    print("❌ Creative creation failed. Checking API...")
    import requests
    test_url = f"https://graph.facebook.com/{api_version}/act_{ad_account_id}/adcreatives"
    print(f"  URL: {test_url}")
    # Try a simple GET to check token validity
    me_url = f"https://graph.facebook.com/{api_version}/me"
    resp = requests.get(me_url, params={"access_token": token, "fields": "id,name"})
    print(f"  Token check: {resp.status_code} - {resp.text[:200]}")
    sys.exit(1)

# Step 3: Create ads
status = "PAUSED"
print(f"\n📢 Creating ads (adset={adset_id}, status={status})...")
ad_ids = publisher.create_ads(
    creative_ids=creative_ids,
    adset_id=adset_id,
    names=ad_names[:len(creative_ids)],
    status=status,
)
print(f"✅ Ads: {len(ad_ids)}/{len(creative_ids)}")

# Save result
result = {
    "run_id": run_id,
    "ad_account_id": ad_account_id,
    "adset_id": adset_id,
    "status": status,
    "api_version": api_version,
    "image_hashes": image_hashes,
    "creative_ids": creative_ids,
    "ad_ids": ad_ids,
    "published_at": datetime.now(timezone.utc).isoformat(),
}

result_path = ROOT / "output" / "closed_loop" / "publish_results" / f"publish_{run_id}.json"
result_path.parent.mkdir(parents=True, exist_ok=True)
with open(result_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"\n{'='*60}")
print(f"  发布完成!")
print(f"{'='*60}")
print(f"  上传: {len(image_hashes)} 张")
print(f"  创意: {len(creative_ids)} 个")
print(f"  广告: {len(ad_ids)} 个, 状态={status}")
print(f"  结果: {result_path}")