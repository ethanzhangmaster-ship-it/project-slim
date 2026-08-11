"""用 Page Access Token 创建 creative"""
import requests, json

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
page_id = "103008755226035"

# 获取 Page Access Token
r = requests.get(f"{BV}/{page_id}", params={
    "access_token": USER_TOKEN,
    "fields": "access_token"
}, timeout=30)
page_token = r.json().get("access_token", "")
print(f"Page Token 获取: {'✅' if page_token else '❌'}")

new_hash = "f1af4b1c94c7a302c2a767f51a01ee2e"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

# 用 Page Token 创建 creative
print("\n用 Page Token 创建 creative (object_story_spec)...")
r2 = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": USER_TOKEN,  # 用 user token 但加 actor_id
        "name": "P04-PageToken-Test-01",
        "status": "PAUSED",
        "actor_id": page_id,
        "image_hash": new_hash,
        "body": "Discover New Gameplay! Merge Witches & explore the most fun experience 🎨✨",
        "title": "Try It Now! 🎯🎯",
        "object_store_url": store_url,
        "object_type": "SHARE",
        "call_to_action_type": "PLAY_GAME",
    },
    timeout=30,
)
print(f"结果 (user token + actor_id): {r2.json()}")

# 试试用 page token
print("\n用 Page Token 直接创建...")
r3 = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": page_token,
        "name": "P04-PageToken-Test-02",
        "status": "PAUSED",
        "image_hash": new_hash,
        "body": "Discover New Gameplay! Merge Witches & explore the most fun experience 🎨✨",
        "title": "Try It Now! 🎯🎯",
        "object_store_url": store_url,
        "object_type": "SHARE",
        "call_to_action_type": "PLAY_GAME",
    },
    timeout=30,
)
print(f"结果 (page token): {r3.json()}")