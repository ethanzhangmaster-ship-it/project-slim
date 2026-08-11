import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

# 测试一个
cid = "36024357000496699"
new_hash = "f1af4b1c94c7a302c2a767f51a01ee2e"

r = requests.post(
    f"{BV}/{cid}",
    data={
        "access_token": TOKEN,
        "name": "P04-Test-Update",
        "image_hash": new_hash,
    },
    timeout=30,
)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))