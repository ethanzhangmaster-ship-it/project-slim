"""查 P04 Witch 的 iOS App Store 链接"""
import requests, json

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

app_id = "836792580521282"

r = requests.get(f"{BV}/{app_id}", params={
    "access_token": USER_TOKEN,
    "fields": "id,name,app_store_url,google_play_url",
}, timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))