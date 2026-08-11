"""用正确的 App ID 836792580521282 创建广告"""
import json, requests, time
from pathlib import Path
from datetime import datetime

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
campaign_id = "120250204601790346"
page_id = "103008755226035"
app_id = "836792580521282"

ROOT = Path(__file__).parent.parent
run_id = datetime.now().strftime("%m%d%H%M")

image_dir = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070843"
images = sorted(image_dir.glob("variant_*.png"))[:5]

captions = [
    "Discover New Gameplay! Merge Witches & explore ✨",
    "Join the magical world of witch merging! ✨🧙‍♀️",
    "Unlock powerful witches and build your coven! 🔮",
    "Merge identical witches to unlock rare ones! 🎮",
    "Experience the ultimate merge adventure! ✨🌟",
]

store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

print("=" * 60)
print(f"  P04 Witch 广告创建 (App ID: {app_id})")
print(f"  账户: {ad_account_id}")
print("=" * 60)

print("\n[Step 0] 获取 Page Token...", end="")
r = requests.get(f"{BV}/{page_id}", params={
    "access_token": USER_TOKEN, "fields": "access_token"
}, timeout=30)
page_token = r.json().get("access_token", "")
print(f" {'✅' if page_token else '❌'}")

print("\n[Step 1] 创建 Adset...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": f"P04-AI-{run_id}-欧美-广泛",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US", "GB", "DE", "FR", "CA", "AU"]}
        }),
        "promoted_object": json.dumps({
            "application_id": app_id,
            "object_store_url": store_url,
        }),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if adset_id:
    print(f"  ✅ Adset: {adset_id}")
else:
    print(f"  ❌ {d_aset}")
    exit(1)

print("\n[Step 2] 上传照片到 Page...")
post_ids = []
for i, (img, caption) in enumerate(zip(images, captions), 1):
    print(f"  照片 {i} ({img.name})...", end="")
    r = requests.post(
        f"{BV}/{page_id}/photos",
        data={"access_token": page_token, "caption": caption, "published": "true"},
        files={"source": (img.name, open(img, "rb"), "image/png")},
        timeout=60,
    )
    d = r.json()
    if "post_id" in d:
        post_ids.append(d["post_id"])
        print(f" ✅")
    else:
        print(f" ❌ {d.get('error', d)[:60]}")
    time.sleep(0.5)

print("\n[Step 3] 创建 creatives...")
creative_ids = []
for i, pid in enumerate(post_ids, 1):
    print(f"  Creative {i}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-Creative-{i:02d}",
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

print("\n[Step 4] 创建广告...")
ad_ids = []
for i, cid in enumerate(creative_ids, 1):
    print(f"  Ad {i}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
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
        print(f" ❌ {d.get('error', {}).get('error_user_msg', d)[:80]}")
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"  完成! Campaign: {campaign_id}")
print(f"  Adset: {adset_id}")
print(f"  共 {len(ad_ids)} 个广告")
print(f"{'='*60}")
for i, aid in enumerate(ad_ids, 1):
    print(f"  {i}. Ad: {aid}")