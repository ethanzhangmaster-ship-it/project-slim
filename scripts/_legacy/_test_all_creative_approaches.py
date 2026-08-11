"""Try ALL creative creation approaches to find one that works without page permissions."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if (ROOT / ".env").exists():
    with open(ROOT / ".env") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip()

import requests

token = os.getenv("META_ACCESS_TOKEN", "")
ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
api_version = os.getenv("META_API_VERSION", "v19.0")
BV = f"https://graph.facebook.com/{api_version}"

# 复用已有上传的 image hash
test_img = ROOT / "output" / "creative_growth_loop" / "images" / "closed_loop_20260630_070327" / "variant_01_00.png"

# 先上传获取 hash
r_upload = requests.post(f"{BV}/act_{ad_account_id}/adimages", params={"access_token": token},
                           files={"filename": (test_img.name, open(test_img, "rb"), "image/png")})
img_data = r_upload.json()
hashes = img_data.get("images", {})
img_hash = list(hashes.values())[0].get("hash", "") if hashes else ""
print(f"Image hash: {img_hash}")

# Page ID from existing ad
page_id = "103008755226035"

results = {}

# === Approach 1: 标准 object_story_spec (baseline, 已知失败) ===
print("\n--- Approach 1: 标准 object_story_spec (page_id=required) ---")
r1 = requests.post(f"{BV}/act_{ad_account_id}/adcreatives", data={
    "access_token": token,
    "name": "Test Creative 1",
    "object_story_spec": json.dumps({
        "page_id": page_id,
        "link_data": {
            "image_hash": img_hash,
            "link": "https://apps.apple.com/app/id000000000",
            "message": "Test",
            "name": "Test",
            "call_to_action": {"type": "OPEN_LINK"},
        }
    }),
}, timeout=30)
results["标准page_id"] = r1.status_code
print(f"  {r1.status_code}: {r1.text[:200]}")

# === Approach 2: asset_feed_spec (不需要 page_id) ===
print("\n--- Approach 2: asset_feed_spec (免 page_id) ---")
r2 = requests.post(f"{BV}/act_{ad_account_id}/adcreatives", data={
    "access_token": token,
    "name": "Test Creative 2",
    "asset_feed_spec": json.dumps({
        "images": [{"hash": img_hash, "caption": "Test caption"}],
    }),
}, timeout=30)
results["asset_feed_spec"] = r2.status_code
print(f"  {r2.status_code}: {r2.text[:200]}")

# === Approach 3: 不要 page_id, 不要 object_story_spec ===
print("\n--- Approach 3: 仅 name + body (无 page_id) ---")
r3 = requests.post(f"{BV}/act_{ad_account_id}/adcreatives", data={
    "access_token": token,
    "name": "Test Creative 3",
    "body": "Test body text",
}, timeout=30)
results["仅body"] = r3.status_code
print(f"  {r3.status_code}: {r3.text[:200]}")

# === Approach 4: product_set_id (如果 product catalog 有的话) ===
print("\n--- Approach 4: product + page_id 但不传 message ---")
r4 = requests.post(f"{BV}/act_{ad_account_id}/adcreatives", data={
    "access_token": token,
    "name": "Test Creative 4",
    "object_story_spec": json.dumps({
        "page_id": page_id,
        "link_data": {
            "image_hash": img_hash,
            "link": "https://apps.apple.com/app/id000000000",
            "name": "Test",
            "call_to_action": {"type": "OPEN_LINK"},
        }
    }),
}, timeout=30)
results["无message"] = r4.status_code
print(f"  {r4.status_code}: {r4.text[:200]}")

# === Approach 5: 直接用 image_url (不用 hash) ===
img_url = "https://scontent-tpe1-1.xx.fbcdn.net/v/t45.1600-4/736207062_122279750090083055_4373220624505592869_n.png"
print("\n--- Approach 5: image_url 方式 ---")
r5 = requests.post(f"{BV}/act_{ad_account_id}/adcreatives", data={
    "access_token": token,
    "name": "Test Creative 5",
    "object_story_spec": json.dumps({
        "page_id": page_id,
        "link_data": {
            "image_url": img_url,
            "link": "https://apps.apple.com/app/id000000000",
            "message": "Test message",
            "name": "Test Ad",
            "call_to_action": {"type": "OPEN_LINK"},
        }
    }),
}, timeout=30)
results["image_url"] = r5.status_code
print(f"  {r5.status_code}: {r5.text[:200]}")

# === Approach 6: 直接 ad creation (无 creative_id, 直接传 creative) ===
print("\n--- Approach 6: 直接创建 ad (creative 嵌入) ---")
r6 = requests.post(f"{BV}/act_{ad_account_id}/ads", data={
    "access_token": token,
    "name": "Test Ad 6",
    "adset_id": "120249161378170444",
    "creative": json.dumps({
        "image_hash": img_hash,
        "object_story_spec": {
            "page_id": page_id,
            "link_data": {
                "image_hash": img_hash,
                "link": "https://apps.apple.com/app/id000000000",
                "message": "Test",
                "name": "Test",
                "call_to_action": {"type": "OPEN_LINK"},
            }
        }
    }),
    "status": "PAUSED",
}, timeout=30)
results["直接ad"] = r6.status_code
print(f"  {r6.status_code}: {r6.text[:200]}")

# === Approach 7: 复用已有 video creative ===
# 找有 video 的 creative
print("\n--- Approach 7: 复用 video creative ---")
r_ads = requests.get(f"{BV}/act_{ad_account_id}/ads", params={
    "access_token": token,
    "fields": "id,name,creative{id,object_story_spec}",
    "limit": 5
})
for ad in r_ads.json().get("data", []):
    cr = ad.get("creative", {})
    oss = cr.get("object_story_spec", {})
    if isinstance(oss, dict) and oss.get("video_data"):
        video_url = oss.get("video_data", {}).get("image_url", "")
        video_hash = oss.get("video_data", {}).get("image_hash", "")
        print(f"  Found video creative: {cr.get('id')}, image_url={video_url[:50]}, image_hash={video_hash[:20]}")
        break

# === Approach 8: 找有效的 Page access token ===
print("\n--- Approach 8: 检查 Instagram creative (可能不需要 page) ---")
# Instagram creative might work differently
r8 = requests.post(f"{BV}/act_{ad_account_id}/adcreatives", data={
    "access_token": token,
    "name": "Test Creative 8 - Instagram",
    "object_story_spec": json.dumps({
        "page_id": page_id,
        "instagram_user_id": "17841446738818954",
        "link_data": {
            "image_hash": img_hash,
            "link": "https://apps.apple.com/app/id000000000",
            "message": "Test",
            "name": "Test",
            "call_to_action": {"type": "OPEN_LINK"},
        }
    }),
}, timeout=30)
results["instagram"] = r8.status_code
print(f"  {r8.status_code}: {r8.text[:200]}")

print("\n" + "=" * 60)
print("  总结")
print("=" * 60)
for k, v in results.items():
    status = "✅" if v == 200 else "❌"
    print(f"  {status} {k}: {v}")

print("""
结论:
  所有需要 page_id 的 creative 创建都需要 pages_manage_ads 权限 (App Review)
  当前 App 处于开发模式，无法创建真实 creative

解决路径:
  1. [最快] 复用已有 video creative_id 直接创建 ad → 已通
  2. [正确] 申请 Facebook App Review 获取 pages_manage_ads 权限
  3. [备选] 用已有 image creative 的 image_url 创建 creative (绕过 image_hash 限制)
""")