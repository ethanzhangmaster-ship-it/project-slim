"""用 Page Post 方式创建 5 个 P04 Witch 新广告 (新图片素材)"""
import json, requests, time
from pathlib import Path
from datetime import datetime

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
campaign_id = "120249183478520444"
adset_id = "120249183479450444"
page_id = "103008755226035"

ROOT = Path(__file__).parent.parent
image_dir = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070843"
images = sorted(image_dir.glob("variant_*.png"))

store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

captions = [
    "Discover New Gameplay! Merge Witches & explore the most fun experience 🎨✨",
    "Join the magical world of witch merging! Collect, combine & conquer ✨🧙‍♀️",
    "Unlock powerful witches and build your ultimate coven! Are you ready? 🔮✨",
    "Merge identical witches to unlock rare and powerful ones! Download now 🎮✨",
    "Experience the ultimate merge adventure! Hundreds of witches to collect ✨🌟",
]

print("=" * 60)
print("  P04 Witch 新广告创建 (Page Post 方式)")
print("=" * 60)
print(f"  图片数量: {len(images)}")
print(f"  图片目录: {image_dir}")

# 获取 Page Token
print("\n[Step 0] 获取 Page Token...", end="")
r = requests.get(f"{BV}/{page_id}", params={
    "access_token": USER_TOKEN, "fields": "access_token"
}, timeout=30)
page_token = r.json().get("access_token", "")
print(f" {'✅' if page_token else '❌'}")

# Step 1: 上传 5 张照片到 Page
print("\n[Step 1] 上传照片到 Page...")
post_ids = []
for i, (img, caption) in enumerate(zip(images, captions), 1):
    print(f"  照片 {i} ({img.name})...", end="")
    r = requests.post(
        f"{BV}/{page_id}/photos",
        data={
            "access_token": page_token,
            "caption": caption,
            "published": "true",
        },
        files={"source": (img.name, open(img, "rb"), "image/png")},
        timeout=60,
    )
    d = r.json()
    if "post_id" in d:
        post_ids.append(d["post_id"])
        print(f" ✅ post_id={d['post_id']}")
    else:
        print(f" ❌ {d.get('error', d)}")
    time.sleep(0.5)

print(f"\n成功上传 {len(post_ids)}/{len(images)} 张照片")

# Step 2: 用 post_id 创建 creatives
print("\n[Step 2] 创建 creatives (object_story_id)...")
creative_ids = []
for i, pid in enumerate(post_ids, 1):
    print(f"  Creative {i}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-Creative-New-{i:02d}",
            "status": "PAUSED",
            "object_story_id": pid,
            "object_store_url": store_url,
            "object_type": "SHARE",
        },
        timeout=30,
    )
    d = r.json()
    if "id" in d:
        creative_ids.append(d["id"])
        print(f" ✅ {d['id']}")
    else:
        print(f" ❌ {d.get('error', {}).get('error_user_msg', d)[:80]}")
    time.sleep(0.5)

print(f"\n成功创建 {len(creative_ids)} 个 creatives")

# Step 3: 创建广告
print("\n[Step 3] 创建广告...")
ad_ids = []
for i, cid in enumerate(creative_ids, 1):
    print(f"  Ad {i}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-New-{i:02d}",
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
        print(f" ❌ {d.get('error', {}).get('error_user_msg', d)[:80]}")
    time.sleep(0.5)

# 总结
print(f"\n{'='*60}")
print(f"  完成! 共创建 {len(ad_ids)} 个新广告")
print(f"{'='*60}")
print(f"  Campaign: {campaign_id}")
print(f"  Adset: {adset_id}")
for i, (aid, cid, pid) in enumerate(zip(ad_ids, creative_ids, post_ids), 1):
    print(f"  {i}. Ad: {aid} | Creative: {cid} | Post: {pid}")

# 保存
result = {
    "campaign_id": campaign_id,
    "adset_id": adset_id,
    "ad_ids": ad_ids,
    "creative_ids": creative_ids,
    "post_ids": post_ids,
    "created_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
}
out = ROOT / f"output/closed_loop/publish_results/publish_p04_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n结果已保存: {out}")