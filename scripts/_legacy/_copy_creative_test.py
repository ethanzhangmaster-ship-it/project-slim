"""测试：复制一个老 creative，只改 image_hash"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

old_creative_id = "36024357000496699"
new_hash = "f1af4b1c94c7a302c2a767f51a01ee2e"

# 先获取老 creative 的完整字段
r = requests.get(
    f"{BV}/{old_creative_id}",
    params={"access_token": TOKEN, "fields": "id,name,status,image_hash,image_url,body,title,object_store_url,object_type,call_to_action_type,actor_id,link_url"},
    timeout=30,
)
old = r.json()
print("老 creative 字段:")
for k, v in old.items():
    if k != "id":
        print(f"  {k}: {str(v)[:80]}")

# 尝试 1: 用完全相同的字段，只改 image_hash + name
print("\n--- 尝试 1: 完全相同字段 + 新 image_hash ---")
data = {k: v for k, v in old.items() if k not in ["id", "image_url", "status"] and v is not None}
data["access_token"] = TOKEN
data["name"] = "P04-Copy-Test-01"
data["image_hash"] = new_hash
data["status"] = "PAUSED"
r1 = requests.post(f"{BV}/act_{ad_account_id}/adcreatives", data=data, timeout=30)
print(f"结果: {r1.json()}")