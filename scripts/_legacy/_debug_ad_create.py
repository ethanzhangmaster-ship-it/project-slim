import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

creative_id = "1314097907113137"
adset_id = "120249183479450444"

print("=== Creative 详情 ===")
r = requests.get(f"{BV}/{creative_id}", params={
    "access_token": TOKEN,
    "fields": "id,name,status,image_hash,image_url,object_store_url,object_type,link_url,body,title,call_to_action_type,actor_id"
}, timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

print("\n=== Adset promoted_object ===")
r2 = requests.get(f"{BV}/{adset_id}", params={
    "access_token": TOKEN,
    "fields": "id,name,optimization_goal,promoted_object"
}, timeout=30)
print(json.dumps(r2.json(), indent=2, ensure_ascii=False))