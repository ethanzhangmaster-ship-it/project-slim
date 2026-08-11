"""查 P07 账户成功的 APP_INSTALLS adset 配置"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

# 之前成功的 P07 adset
adset_id = "6838677046281"

r = requests.get(f"{BV}/{adset_id}", params={
    "access_token": TOKEN,
    "fields": "id,name,optimization_goal,billing_event,daily_budget,targeting,promoted_object,platforms,device_platforms,publisher_platforms",
}, timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))