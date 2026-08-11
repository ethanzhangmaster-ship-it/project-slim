"""找 5 个 PAUSED 状态的 creative，更新 image_hash，然后创建广告"""
import requests, json, time
from pathlib import Path
from datetime import datetime

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
campaign_id = "120249183478520444"
adset_id = "120249183479450444"

ROOT = Path(__file__).parent.parent

# 5 张新图的 hash
new_image_hashes = [
    "f1af4b1c94c7a302c2a767f51a01ee2e",
    "58775d21d0cb2de8d2df52a808185527",
    "f5341e1a0f410cceca8ba8aaf3b4df30",
    "570fe0748e65006a00f917f3f4ff0ce6",
    "0c0493ba836a1ba624f591bfc087760e",
]

# 找 5 个 PAUSED 的 creative
print("查找 PAUSED 状态的 creative...")
r = requests.get(
    f"{BV}/act_{ad_account_id}/adcreatives",
    params={
        "access_token": TOKEN,
        "fields": "id,name,status,image_hash",
        "limit": 50,
    },
    timeout=30,
)
creatives = r.json().get("data", [])
paused_creatives = [c for c in creatives if c.get("status") == "PAUSED" and c.get("image_hash")]
print(f"共 {len(creatives)} 个 creative，其中 PAUSED + 有图: {len(paused_creatives)}")

# 取前 5 个
target_creatives = paused_creatives[:5]
if len(target_creatives) < 5:
    print(f"❌ 只有 {len(target_creatives)} 个 PAUSED creative，不够 5 个")
    # 不够就找 ACTIVE 的补充
    active_creatives = [c for c in creatives if c.get("status") == "ACTIVE" and c.get("image_hash")]
    needed = 5 - len(target_creatives)
    target_creatives += active_creatives[:needed]
    print(f"补充 {needed} 个 ACTIVE creative，共 {len(target_creatives)} 个")

for i, c in enumerate(target_creatives, 1):
    print(f"  {i}. {c['id']} ({c['status']}): {c.get('name','')[:50]}")

print(f"\n更新 5 个 creative 的 image_hash 为新图...")
updated_creative_ids = []
for i, (c, new_hash) in enumerate(zip(target_creatives, new_image_hashes), 1):
    cid = c["id"]
    old_hash = c.get("image_hash", "")
    print(f"  {i}. Creative {cid}: {old_hash[:12]}... → {new_hash[:12]}...", end="")
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
        updated_creative_ids.append(cid)
        print(f" ✅")
    else:
        print(f" ❌ {d.get('error', d)}")
    time.sleep(0.3)

print(f"\n成功更新 {len(updated_creative_ids)} 个 creative")

# 用更新后的 creative 创建广告
print("\n创建 5 个新广告...")
ad_ids = []
for i, cid in enumerate(updated_creative_ids, 1):
    print(f"  Ad {i} (creative {cid})...", end="")
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

# 总结
print(f"\n{'='*60}")
print(f"  完成! {len(ad_ids)} 个新广告 (新图片素材)")
print(f"{'='*60}")
for i, (aid, cid, h) in enumerate(zip(ad_ids, updated_creative_ids, new_image_hashes), 1):
    print(f"  {i}. Ad: {aid} | Creative: {cid} | Hash: {h[:16]}...")

result = {
    "campaign_id": campaign_id,
    "adset_id": adset_id,
    "ad_ids": ad_ids,
    "creative_ids": updated_creative_ids,
    "image_hashes": new_image_hashes,
    "created_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
}
out = ROOT / f"output/closed_loop/publish_results/publish_p04_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n已保存: {out}")