"""测试：用 LINK_CLICKS 目标，在 creative 里加商店链接"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
campaign_id = "120250204601790346"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

print("测试：LINK_CLICKS + 商店链接...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Test-LinkClicks",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US"]},
        }),
        "promoted_object": json.dumps({
            "pixel_id": "259824536585005",
        }),
    },
    timeout=30,
)
d = r.json()
adset_id = d.get("id", "")
print(f"结果: {'✅ ' + adset_id if adset_id else '❌ ' + json.dumps(d)[:300]}")