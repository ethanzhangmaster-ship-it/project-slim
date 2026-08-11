"""在 P04 Witch 专属 Campaign 下创建广告"""
import json, requests, time
from pathlib import Path
from datetime import datetime

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"  # P04 账户
campaign_id = "120249183478520444"  # P04 Campaign
adset_id = "120249183479450444"    # P04 Adset
app_id = "836792580521282"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
page_id = "103008755226035"

ROOT = Path(__file__).parent.parent
image_dir = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070843"
images = sorted(image_dir.glob("variant_*.png"))
print(f"找到 {len(images)} 张图片")

print("\n[Step 1] 上传图片...")
image_hashes = []
for img in images:
    print(f"  上传 {img.name}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adimages",
        data={
            "access_token": TOKEN,
            "filename": img.name,
        },
        files={"file": (img.name, open(img, "rb"), "image/png")},
        timeout=60,
    )
    d = r.json()
    if "images" in d:
        hash_val = list(d["images"].values())[0]["hash"]
        image_hashes.append(hash_val)
        print(f" ✅ {hash_val[:12]}...")
    else:
        print(f" ❌ {d.get('error', {}).get('error_user_msg', d)}")
    time.sleep(0.5)

print(f"\n共获得 {len(image_hashes)} 个 image_hash")

print("\n[Step 2] 创建 creatives (无 page_id，回退方案)...")
creative_ids = []
for i, img_hash in enumerate(image_hashes, 1):
    print(f"  Creative {i}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": TOKEN,
            "name": f"P04-AI-Creative-{i:02d}",
            "status": "PAUSED",
            "image_hash": img_hash,
            "object_store_url": store_url,
            "object_type": "APPLICATION",
        },
        timeout=30,
    )
    d = r.json()
    if "id" in d:
        creative_ids.append(d["id"])
        print(f" ✅ {d['id']}")
    else:
        print(f" ❌ {d.get('error', {}).get('error_user_msg', d)}")
    time.sleep(0.5)

print(f"\n共创建 {len(creative_ids)} 个 creative")

print("\n[Step 3] 创建 ads...")
ad_ids = []
for i, cid in enumerate(creative_ids, 1):
    print(f"  Ad {i}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": TOKEN,
            "name": f"P04-AI-Ad-{i:02d}",
            "status": "PAUSED",
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": cid}),
        },
        timeout=30,
    )
    d = r.json()
    if "id" in d:
        ad_ids.append(d["id"])
        print(f" ✅ {d['id']}")
    else:
        print(f" ❌ {d.get('error', {}).get('error_user_msg', d)}")
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"  P04 Witch 广告创建完成!")
print(f"{'='*60}")
print(f"  Campaign: {campaign_id}")
print(f"  Adset: {adset_id}")
print(f"  广告数量: {len(ad_ids)}")
for aid in ad_ids:
    print(f"    Ad ID: {aid}")

# 保存结果
result = {
    "campaign_id": campaign_id,
    "adset_id": adset_id,
    "ad_ids": ad_ids,
    "creative_ids": creative_ids,
    "image_hashes": image_hashes,
    "store_url": store_url,
    "created_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
}
out = ROOT / f"output/closed_loop/publish_results/publish_p04_witch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n结果已保存: {out}")