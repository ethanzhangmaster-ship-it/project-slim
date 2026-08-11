import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

# 测试只用 object_store_url + body
print("测试 creative 创建 (object_store_url + body)...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": TOKEN,
        "name": "P04-Test-Creative-Body",
        "status": "PAUSED",
        "body": "Play P04 Witch now! Amazing magical adventure awaits!",
        "object_store_url": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
    },
    timeout=30,
)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))