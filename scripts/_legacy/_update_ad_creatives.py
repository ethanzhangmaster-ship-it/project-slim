"""直接修改 5 个广告在用的 creative 的 image_hash 为新图"""
import requests, json, time
from pathlib import Path
from datetime import datetime

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ROOT = Path(__file__).parent.parent

# 5 个广告
ad_ids = [
    "120249184776120444",  # P04-AI-Ad-01
    "120249184794000444",  # P04-AI-Ad-02
    "120249184799280444",  # P04-AI-Ad-03
    "120249184803470444",  # P04-AI-Ad-04
    "120249184810030444",  # P04-AI-Ad-05
]

# 5 张新图
new_image_hashes = [
    "f1af4b1c94c7a302c2a767f51a01ee2e",
    "58775d21d0cb2de8d2df52a808185527",
    "f5341e1a0f410cceca8ba8aaf3b4df30",
    "570fe0748e65006a00f917f3f4ff0ce6",
    "0c0493ba836a1ba624f591bfc087760e",
]

# 获取每个广告的 creative_id
print("获取 5 个广告的 creative...")
creative_ids = []
for ad_id in ad_ids:
    r = requests.get(f"{BV}/{ad_id}", params={
        "access_token": TOKEN, "fields": "id,name,creative{id,name,image_hash}"
    }, timeout=30)
    d = r.json()
    c = d.get("creative", {})
    creative_ids.append(c.get("id", ""))
    print(f"  {d.get('name')}: creative={c.get('id')}, hash={c.get('image_hash','?')[:16]}...")

# 检查是否有重复的 creative
unique_creatives = list(set(creative_ids))
print(f"\n共 {len(creative_ids)} 个 creative，其中唯一的有 {len(unique_creatives)} 个")

# 如果有重复，我们需要先找一些未使用的 creative
if len(unique_creatives) < 5:
    print("⚠️ creative 有重复！需要找 5 个独立的 creative")
    
    # 找 5 个未使用的 creative
    print("查找未使用的 creative...")
    r = requests.get(
        f"{BV}/act_1455525822955003/adcreatives",
        params={"access_token": TOKEN, "fields": "id,name,image_hash", "limit": 200},
        timeout=30,
    )
    all_creatives = r.json().get("data", [])
    
    # 排除在用的
    used_set = set(unique_creatives)
    unused = [c for c in all_creatives if c["id"] not in used_set and c.get("image_hash")]
    print(f"找到 {len(unused)} 个未使用的 creative")
    
    # 选 5 个
    target_creatives = unused[:5]
    creative_ids = [c["id"] for c in target_creatives]
    print(f"选用: {[c['id'] for c in target_creatives]}")

# 更新 creative 的 image_hash
print("\n更新 creative 的 image_hash 为新图...")
results = []
for i, (cid, new_hash) in enumerate(zip(creative_ids, new_image_hashes), 1):
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
    success = d.get("success", False)
    results.append({"creative_id": cid, "new_hash": new_hash, "success": success})
    print(f" {'✅' if success else '❌'}")
    time.sleep(0.3)

successful = [r for r in results if r["success"]]
print(f"\n成功更新 {len(successful)}/5 个 creative")

# 如果 creative 是独立的，需要更新广告指向新 creative
if len(unique_creatives) < 5:
    print("\n⚠️ 需要把广告关联到新 creative，但修改广告可能触发账户验证")
    print("建议：直接在广告管理工具中手动关联")

# 总结
print(f"\n{'='*60}")
print(f"  完成! {len(successful)} 个 creative 已更新为新图片")
print(f"{'='*60}")
for i, r in enumerate(successful, 1):
    print(f"  {i}. Creative: {r['creative_id']} | Hash: {r['new_hash'][:16]}...")

result = {
    "updated_creatives": results,
    "done_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
}
out = ROOT / f"output/closed_loop/publish_results/update_creatives_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n已保存: {out}")