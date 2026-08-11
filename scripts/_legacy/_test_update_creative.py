"""测试：更新现有 creative 的 image_hash"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

creative_id = "36024357000496699"
new_hash = "f1af4b1c94c7a302c2a767f51a01ee2e"

# 尝试更新 creative 的 image_hash
print("尝试更新 creative image_hash...")
r = requests.post(
    f"{BV}/{creative_id}",
    data={
        "access_token": TOKEN,
        "image_hash": new_hash,
    },
    timeout=30,
)
print(f"结果: {r.json()}")

# 试试复制 creative
print("\n尝试复制 creative (通过创建时指定 creative_id 作为模板)...")
r2 = requests.post(
    f"{BV}/act_1455525822955003/adcreatives",
    data={
        "access_token": TOKEN,
        "name": "P04-Copy-Test-03",
        "status": "PAUSED",
        "creative_id": creative_id,  # 以这个为模板
        "image_hash": new_hash,  # 只改 image_hash
    },
    timeout=30,
)
print(f"结果: {r2.json()}")