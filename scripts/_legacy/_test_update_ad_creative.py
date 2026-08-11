"""测试：修改已有广告的 creative_id"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_id = "120249184776120444"  # P04-AI-Ad-01 (之前创建的)
new_creative_id = "27807359555528154"  # 已更新为新图片的 creative

# 查看当前 creative
print("当前广告 creative:")
r0 = requests.get(f"{BV}/{ad_id}", params={"access_token": TOKEN, "fields": "id,name,creative{id,name,image_hash}"}, timeout=30)
print(json.dumps(r0.json(), indent=2, ensure_ascii=False))

# 修改广告的 creative
print("\n修改广告的 creative_id...")
r = requests.post(
    f"{BV}/{ad_id}",
    data={
        "access_token": TOKEN,
        "creative": json.dumps({"creative_id": new_creative_id}),
    },
    timeout=30,
)
print(f"结果: {json.dumps(r.json(), ensure_ascii=False)[:400]}")

# 验证
print("\n修改后:")
r2 = requests.get(f"{BV}/{ad_id}", params={"access_token": TOKEN, "fields": "id,name,creative{id,name,image_hash}"}, timeout=30)
print(json.dumps(r2.json(), indent=2, ensure_ascii=False))