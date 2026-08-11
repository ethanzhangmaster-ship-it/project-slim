"""测试更新已有 creative 的 image_hash"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

creative_id = "36024357000496699"
new_hash = "f1af4b1c94c7a302c2a767f51a01ee2e"

# 方式 1: 只更新 name + image_hash
print("方式 1: POST 更新 creative image_hash + name...")
r = requests.post(
    f"{BV}/{creative_id}",
    data={
        "access_token": TOKEN,
        "name": "P04-Updated-Test",
        "image_hash": new_hash,
    },
    timeout=30,
)
print(f"结果: {json.dumps(r.json(), ensure_ascii=False)[:500]}")

# 方式 2: 只更新 name（看看能不能修改）
print("\n方式 2: 只更新 creative name...")
r2 = requests.post(
    f"{BV}/{creative_id}",
    data={
        "access_token": TOKEN,
        "name": "P04-Name-Test-Only",
    },
    timeout=30,
)
print(f"结果: {json.dumps(r2.json(), ensure_ascii=False)[:500]}")