"""用未使用的 creative 替换图片后创建新广告"""
import requests, json, time
from pathlib import Path
from datetime import datetime

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
campaign_id = "120249183478520444"
adset_id = "120249183479450444"

ROOT = Path(__file__).parent.parent

new_image_hashes = [
    "f1af4b1c94c7a302c2a767f51a01ee2e",
    "58775d21d0cb2de8d2df52a808185527",
    "f5341e1a0f410cceca8ba8aaf3b4df30",
    "570fe0748e65006a00f917f3f4ff0ce6",
    "0c0493ba836a1ba624f591bfc087760e",
]

unused_creative_ids = [
    "27807359555528154",
    "27509904531937494",
    "27465795199716598",
    "27376076861984184",
    "27269108226040210",
]

print("=" * 60)
print("  P04 Witch 新广告 (替换未使用 creative 的图片)")
print("=" * 60)

print("\n[Step 1] 更新 5 个 creative 的 image_hash...")
updated = []
for i, (cid, new_hash) in enumerate(zip(unused_creative_ids, new_image_hashes), 1):
    print(f"  {i}. Creative {cid}...", end="")
    r = requests.post(
        f"{BV}/{cid}",
        data={
            "access_token": TOKEN,
            "name": f"P04-AI-New-{i:02d}-{datetime.now().strftime('%m%d')}",
            "image_hash": new_hash,
        },
        timeout=30,
    )
    d = r.json()
    if d.get("success"):
        updated.append(cid)
        print(f" ✅")
    else:
        print(f" ❌ {d.get('error', d)}")
    time.sleep(0.3)

print(f"\n成功更新 {len(updated)}/5 个 creative")

print("\n[Step 2] 创建 5 个广告...")
ad_ids = []
for i, cid in enumerate(updated, 1):
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
        msg = err.get("error_user_msg") or err.get("message") or str(d)
        print(f" ❌ {msg[:80]}")
    time.sleep(0.3)

print(f"\n{'='*60}")
print(f"  完成! {len(ad_ids)} 个新广告 (新图片素材)")
print(f"{'='*60}")
for i, (aid, cid, h) in enumerate(zip(ad_ids, updated, new_image_hashes), 1):
    print(f"  {i}. Ad: {aid} | Creative: {cid} | Hash: {h[:16]}...")

result = {
    "campaign_id": campaign_id,
    "adset_id": adset_id,
    "ad_ids": ad_ids,
    "creative_ids": updated,
    "image_hashes": new_image_hashes,
    "created_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
}
out = ROOT / f"output/closed_loop/publish_results/publish_p04_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n已保存: {out}")