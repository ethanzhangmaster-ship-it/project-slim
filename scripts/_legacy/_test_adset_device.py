"""测试：加上 device_platforms 强制 mobile"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
campaign_id = "120250204601790346"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

print("测试 adset 创建 with device_platforms...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Test-欧美",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US"]},
            "device_platforms": ["mobile"],
            "publisher_platforms": ["facebook", "instagram", "audience_network"],
        }),
        "promoted_object": json.dumps({
            "application_id": "836792580521282",
            "object_store_url": store_url,
        }),
    },
    timeout=30,
)
d = r.json()
print(json.dumps(d, indent=2, ensure_ascii=False))