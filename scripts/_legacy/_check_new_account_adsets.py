"""检查新账户的 adsets 和 app 配置"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"

# 查现有 adsets
r = requests.get(f"{BV}/act_{ad_account_id}/adsets", params={
    "access_token": TOKEN,
    "fields": "id,name,optimization_goal,promoted_object",
    "limit": 10,
}, timeout=30)
adsets = r.json().get("data", [])
print(f"现有 adsets: {len(adsets)}")
for a in adsets:
    print(f"  {a['id']}: {a.get('name','')[:50]}")
    print(f"    goal: {a.get('optimization_goal')}")
    print(f"    promoted_object: {json.dumps(a.get('promoted_object',{}), ensure_ascii=False)[:150]}")

# 查 campaign
print("\n查 campaign...")
r2 = requests.get(f"{BV}/120250204601790346", params={
    "access_token": TOKEN,
    "fields": "id,name,status",
}, timeout=30)
print(json.dumps(r2.json(), indent=2, ensure_ascii=False))