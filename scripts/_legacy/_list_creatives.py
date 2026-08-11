import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

# 查这个账户下已有的 creative
r = requests.get(
    f"{BV}/act_{ad_account_id}/adcreatives",
    params={
        "access_token": TOKEN,
        "fields": "id,name,status,image_hash,object_store_url,link_data,image_url",
        "limit": 5,
    },
    timeout=30,
)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))