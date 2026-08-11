"""用 page post_id 创建 creative"""
import requests, json

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

post_id = "103008755226035_1331719175760039"  # 刚才上传的 page post

print("用 object_story_id (post_id) 创建 creative...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Post-Creative-Test",
        "status": "PAUSED",
        "object_story_id": post_id,
        "object_store_url": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
        "object_type": "SHARE",
    },
    timeout=30,
)
print(f"结果: {json.dumps(r.json(), ensure_ascii=False, indent=2)[:600]}")