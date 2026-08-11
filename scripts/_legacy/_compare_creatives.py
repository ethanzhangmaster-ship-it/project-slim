import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

new_creative = "1036119765619964"
old_creative = "36024357000496699"

fields = "id,name,status,image_hash,image_url,object_store_url,object_type,link_url,body,title,call_to_action_type,actor_id,video_id"

print("=== 新 creative ===")
r = requests.get(f"{BV}/{new_creative}", params={"access_token": TOKEN, "fields": fields}, timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

print("\n=== 老 creative ===")
r2 = requests.get(f"{BV}/{old_creative}", params={"access_token": TOKEN, "fields": fields}, timeout=30)
print(json.dumps(r2.json(), indent=2, ensure_ascii=False))

# 尝试用新 creative 创建 ad
print("\n=== 测试用新 creative 创建 ad ===")
adset_id = "120249183479450444"
r3 = requests.post(
    f"{BV}/act_1455525822955003/ads",
    data={
        "access_token": TOKEN,
        "name": "P04-Test-Ad-01",
        "status": "PAUSED",
        "adset_id": adset_id,
        "creative": json.dumps({"creative_id": new_creative}),
    },
    timeout=30,
)
print(json.dumps(r3.json(), indent=2, ensure_ascii=False))