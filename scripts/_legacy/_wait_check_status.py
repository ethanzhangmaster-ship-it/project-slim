"""等待检查广告状态"""
import json, requests, time

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_id = "120250205903180346"

print("等待 60 秒...")
time.sleep(60)

r = requests.get(
    f"{BV}/{ad_id}",
    params={"access_token": USER_TOKEN, "fields": "name,status,effective_status"},
    timeout=30,
)
d = r.json()
print(f"状态: {d.get('status')}, effective: {d.get('effective_status')}")
