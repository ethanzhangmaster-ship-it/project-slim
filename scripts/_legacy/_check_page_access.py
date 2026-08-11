import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

page_id = "103008755226035"

# 查这个 page 的信息
r = requests.get(f"{BV}/{page_id}", params={"access_token": TOKEN, "fields": "id,name,access_token"}, timeout=30)
print(f"Page {page_id}: {r.json()}")

# 查 me/accounts 看能管理哪些 page
r2 = requests.get(f"{BV}/me/accounts", params={"access_token": TOKEN, "limit": 20}, timeout=30)
pages = r2.json().get("data", [])
print(f"\n可管理的 Pages: {len(pages)}")
for p in pages:
    print(f"  {p['id']}: {p.get('name', '?')}")