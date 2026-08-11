"""用老 creative 模板 + 新图片创建 5 个 P04 广告"""
import json, requests, time
from pathlib import Path
from datetime import datetime

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
campaign_id = "120249183478520444"
adset_id = "120249183479450444"

ROOT = Path(__file__).parent.parent

# 5 张新上传的图片 (完整 hash)
new_image_hashes = [
    "f1af4b1c94c7a302c2a767f51a01ee2e",  # variant_01
    "58775d21d0cb2de8d2df52a808185527",  # variant_02
    "f5341e1a0f410cceca8ba8aaf3b4df30",  # variant_03
    "570fe0748e65006a00f917f3f4ff0ce6",  # variant_04
    "0c0493ba836a1ba624f591bfc087760e",  # variant_05
]

# 老 creative 模板字段 (从 36024357000496699 复制)
base_store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
referrer = "&referrer=utm_source%3Dapps.facebook.com%26utm_campaign%3Dfb4a%26utm_content%3D%257B%2522app%2522%253A0%252C%2522t%2522%253A1782868147%252C%2522source%2522%253Anull%257D"
object_store_url = base_store_url + referrer

templates = [
    {
        "body": "Discover New Gameplay! Merge Witches & explore the most fun experience 🎨✨",
        "title": "Try It Now! 🎯🎯",
        "call_to_action_type": "PLAY_GAME",
    },
    {
        "body": "Join the magical world of witch merging! Collect, combine & conquer ✨🧙‍♀️",
        "title": "Join the Magic World! 🎯💫",
        "call_to_action_type": "PLAY_GAME",
    },
    {
        "body": "Unlock powerful witches and build your ultimate coven! Are you ready? 🔮✨",
        "title": "Magic & Mystery Awaits 🕯️",
        "call_to_action_type": "PLAY_GAME",
    },
    {
        "body": "Merge identical witches to unlock rare and powerful ones! Download now 🎮✨",
        "title": "Play Now & Discover! 🎯🎨",
        "call_to_action_type": "PLAY_GAME",
    },
    {
        "body": "Experience the ultimate merge adventure! Hundreds of witches to collect ✨🌟",
        "title": "Start Your Journey! 🎯✨",
        "call_to_action_type": "PLAY_GAME",
    },
]

print("=" * 60)
print("  创建 5 个新 creative + 广告 (老模板 + 新图片)")
print("=" * 60)

print("\n[Step 1] 创建 creatives...")
creative_ids = []
for i, (img_hash, tmpl) in enumerate(zip(new_image_hashes, templates), 1):
    print(f"  Creative {i}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": TOKEN,
            "name": f"P04-AI-Creative-New-{i:02d}",
            "status": "PAUSED",
            "image_hash": img_hash,
            "body": tmpl["body"],
            "title": tmpl["title"],
            "object_store_url": object_store_url,
            "object_type": "SHARE",
            "call_to_action_type": tmpl["call_to_action_type"],
        },
        timeout=30,
    )
    d = r.json()
    if "id" in d:
        creative_ids.append(d["id"])
        print(f" ✅ {d['id']}")
    else:
        err = d.get("error", {})
        print(f" ❌ [{err.get('code')}] {err.get('error_user_msg', err.get('message', d))[:80]}")
    time.sleep(0.5)

print(f"\n成功创建 {len(creative_ids)}/{len(new_image_hashes)} 个 creatives")

if len(creative_ids) == 0:
    print("❌ 没有成功的 creative，无法创建广告")
    import sys; sys.exit(1)

print("\n[Step 2] 创建 ads...")
ad_ids = []
for i, cid in enumerate(creative_ids, 1):
    print(f"  Ad {i}...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": TOKEN,
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
        err = d.get("error", {})
        print(f" ❌ [{err.get('code')}] {err.get('error_user_msg', d)[:80]}")
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"  完成! 共创建 {len(ad_ids)} 个广告")
print(f"{'='*60}")
for i, (aid, cid) in enumerate(zip(ad_ids, creative_ids), 1):
    print(f"  {i}. Ad: {aid} | Creative: {cid}")

# 保存结果
result = {
    "campaign_id": campaign_id,
    "adset_id": adset_id,
    "ad_ids": ad_ids,
    "creative_ids": creative_ids,
    "image_hashes": new_image_hashes[:len(creative_ids)],
    "created_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
}
out = ROOT / f"output/closed_loop/publish_results/publish_p04_new_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n结果已保存: {out}")