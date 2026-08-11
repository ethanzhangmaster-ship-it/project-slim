"""测试：OFFSITE_CONVERSIONS + 商店链接"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
campaign_id = "120250204601790346"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

print("测试 OFFSITE_CONVERSIONS + 商店链接...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Test-欧美-直链",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "OFFSITE_CONVERSIONS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US", "GB"]},
            "device_platforms": ["mobile"],
            "publisher_platforms": ["facebook", "instagram", "audience_network"],
        }),
        "promoted_object": json.dumps({
            "object_store_url": store_url,
        }),
    },
    timeout=30,
)
d = r.json()
adset_id = d.get("id", "")
if adset_id:
    print(f"  ✅ Adset: {adset_id}")
else:
    print(f"  ❌ {d}")