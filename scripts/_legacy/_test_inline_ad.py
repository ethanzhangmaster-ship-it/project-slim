"""测试：创建 ad 时直接内联指定 image_hash 和 object_store_url"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
adset_id = "120249183479450444"

store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
img_hash = "f1af4b1c94c7a302c2a767f51a01ee2e"

print("方式 1: ad creative 内联 image_hash + object_store_url...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/ads",
    data={
        "access_token": TOKEN,
        "name": "P04-Inline-Test-01",
        "status": "PAUSED",
        "adset_id": adset_id,
        "creative": json.dumps({
            "name": "P04-Inline-Creative-01",
            "image_hash": img_hash,
            "object_store_url": store_url,
            "object_type": "SHARE",
            "title": "Try It Now! 🎯🎯",
            "body": "Discover New Gameplay! Merge Witches ✨",
            "call_to_action_type": "PLAY_GAME",
        }),
    },
    timeout=30,
)
print(f"结果: {json.dumps(r.json(), ensure_ascii=False, indent=2)[:500]}")

# 方式 2: 用 object_story_spec
print("\n方式 2: ad creative 内联 object_story_spec + page_id...")
from pathlib import Path
r2 = requests.post(
    f"{BV}/act_{ad_account_id}/ads",
    data={
        "access_token": TOKEN,
        "name": "P04-Inline-Test-02",
        "status": "PAUSED",
        "adset_id": adset_id,
        "creative": json.dumps({
            "name": "P04-Inline-Creative-02",
            "object_story_spec": {
                "page_id": "103008755226035",
                "link_data": {
                    "image_hash": img_hash,
                    "link": store_url,
                    "message": "Discover New Gameplay! Merge Witches ✨",
                    "name": "Try It Now! 🎯🎯",
                    "call_to_action": {
                        "type": "PLAY_GAME",
                        "value": {"link": store_url}
                    }
                }
            }
        }),
    },
    timeout=30,
)
print(f"结果: {json.dumps(r2.json(), ensure_ascii=False, indent=2)[:500]}")