"""用正确的 app promotion 格式创建 creative"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
page_id = "103008755226035"
post_id = "103008755226035_1331719982426625"  # 第一张照片的 post_id
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

# 尝试方式 1: object_story_id + object_store_url + object_type=SHARE
print("方式 1: object_story_id + SHARE + object_store_url...")
r1 = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": TOKEN,
        "name": "P04-Test-Type1",
        "status": "PAUSED",
        "object_story_id": post_id,
        "object_store_url": store_url,
        "object_type": "SHARE",
        "link_url": store_url,
    },
    timeout=30,
)
print(f"  结果: {json.dumps(r1.json(), ensure_ascii=False)[:200]}")

# 尝试方式 2: image_hash + object_store_url + object_type=APPLICATION (直接 app ad 格式)
print("\n方式 2: image_hash + object_type=APPLICATION + call_to_action...")
img_hash = "f1af4b1c94c7a302c2a767f51a01ee2e"
r2 = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": TOKEN,
        "name": "P04-Test-Type2",
        "status": "PAUSED",
        "image_hash": img_hash,
        "object_store_url": store_url,
        "object_type": "APPLICATION",
        "title": "Try It Now! 🎯🎯",
        "body": "Discover New Gameplay! Merge Witches & explore ✨",
        "call_to_action_type": "INSTALL_MOBILE_APP",
        "actor_id": page_id,
    },
    timeout=30,
)
print(f"  结果: {json.dumps(r2.json(), ensure_ascii=False)[:200]}")

# 尝试方式 3: link_data + page_id (类似 P07 账户成功的方式)
print("\n方式 3: page_id + link_data + image_hash...")
r3 = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": TOKEN,
        "name": "P04-Test-Type3",
        "status": "PAUSED",
        "page_id": page_id,
        "link_data": json.dumps({
            "image_hash": img_hash,
            "link": store_url,
            "message": "Discover New Gameplay! Merge Witches ✨",
            "name": "Try It Now! 🎯🎯",
            "call_to_action": {
                "type": "INSTALL_MOBILE_APP",
                "value": {"link": store_url}
            }
        }),
    },
    timeout=30,
)
print(f"  结果: {json.dumps(r3.json(), ensure_ascii=False)[:300]}")