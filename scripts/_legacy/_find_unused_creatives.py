"""找没有被广告使用的 creative"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

# 取所有 active 广告的 creative id
print("获取所有广告及其 creative...")
used_creative_ids = set()
r = requests.get(
    f"{BV}/act_{ad_account_id}/ads",
    params={
        "access_token": TOKEN,
        "fields": "id,creative{id}",
        "limit": 200,
    },
    timeout=30,
)
ads = r.json().get("data", [])
for ad in ads:
    c = ad.get("creative", {})
    if c.get("id"):
        used_creative_ids.add(c["id"])
print(f"广告数量: {len(ads)}, 使用的 creative 数量: {len(used_creative_ids)}")

# 获取所有 creative
print("\n获取所有 creative...")
all_creatives = []
after = ""
while True:
    params = {
        "access_token": TOKEN,
        "fields": "id,name,status,image_hash",
        "limit": 100,
    }
    if after:
        params["after"] = after
    r2 = requests.get(f"{BV}/act_{ad_account_id}/adcreatives", params=params, timeout=30)
    data = r2.json().get("data", [])
    all_creatives.extend(data)
    paging = r2.json().get("paging", {})
    cursors = paging.get("cursors", {})
    after = cursors.get("after", "")
    if not after or len(data) < 100:
        break
    print(f"  已获取 {len(all_creatives)} 个...")

print(f"总 creative 数量: {len(all_creatives)}")

# 找未使用的 + 有图片的
unused = []
for c in all_creatives:
    if c["id"] not in used_creative_ids and c.get("image_hash"):
        unused.append(c)

print(f"未使用 + 有图: {len(unused)} 个")
for i, c in enumerate(unused[:10], 1):
    print(f"  {i}. {c['id']} ({c['status']}): {c.get('name','')[:50]}")

if len(unused) >= 5:
    print("\n✅ 有足够的未使用 creative，可以挑选 5 个来替换图片！")
else:
    print(f"\n❌ 只有 {len(unused)} 个，不够 5 个")