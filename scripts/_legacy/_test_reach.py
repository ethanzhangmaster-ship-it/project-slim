"""测试：REACH 目标，不需要 promoted_object"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
campaign_id = "120250204601790346"

print("测试：REACH 目标...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Test-Reach",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "REACH",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US"]},
        }),
    },
    timeout=30,
)
d = r.json()
adset_id = d.get("id", "")
print(f"结果: {'✅ ' + adset_id if adset_id else '❌ ' + json.dumps(d)[:300]}")