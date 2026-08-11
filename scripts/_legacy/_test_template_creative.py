"""测试：用 adcreative 的 copy 接口或 update 接口"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

old_creative_id = "36024357000496699"
new_hash = "f1af4b1c94c7a302c2a767f51a01ee2e"

# 先获取老 creative 的完整字段
fields = "name,image_hash,object_store_url,object_type,body,title,call_to_action_type,actor_id,status"
r = requests.get(f"{BV}/{old_creative_id}", params={"access_token": TOKEN, "fields": fields}, timeout=30)
old = r.json()
print("老 creative 字段:")
for k, v in old.items():
    if k != "id":
        print(f"  {k}: {v}")

# 方式：POST /act_id/adcreatives 但 creative_id 作为模板
print("\n--- 方式: creative_id 作为模板 + 新 image_hash + 所有字段 ---")
data = {
    "access_token": TOKEN,
    "name": "P04-Template-Test-01",
    "status": "PAUSED",
    "creative_id": old_creative_id,
    "image_hash": new_hash,
    "object_store_url": old["object_store_url"],
    "object_type": old["object_type"],
    "body": old["body"],
    "title": old["title"],
    "call_to_action_type": old["call_to_action_type"],
    "actor_id": old["actor_id"],
}
r2 = requests.post(f"{BV}/act_{ad_account_id}/adcreatives", data=data, timeout=30)
print(f"结果: {json.dumps(r2.json(), ensure_ascii=False)[:400]}")