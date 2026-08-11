"""完整验证：先测试 APP_INSTALLS 是否能创建成功，再决定方案"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
app_id = "836792580521282"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

print("=== 测试 1: OUTCOME_APP_PROMOTION Campaign ===")
r = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-AppPromo",
        "objective": "OUTCOME_APP_PROMOTION",
        "status": "PAUSED",
        "is_adset_budget_sharing_enabled": True,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "special_ad_categories": json.dumps([]),
        "dsa_beneficiary": json.dumps({"name": "Merge Witches", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "Merge Witches", "category": "APP"}),
    },
    timeout=30,
)
d = r.json()
campaign_id = d.get("id", "")
print(f"结果: {'✅ ' + campaign_id if campaign_id else '❌ ' + json.dumps(d, ensure_ascii=False)}")
if not campaign_id:
    print("\nAPP_INSTALLS Campaign 失败，改用 TRAFFIC + 普通 CTA 方案")
    exit(1)

print(f"\n=== 测试 2: APP_INSTALLS Adset (Android) ===")
r2 = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-AppInstalls-Adset",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US"]},
            "device_platforms": ["mobile"],
        }),
        "promoted_object": json.dumps({
            "application_id": app_id,
            "object_store_url": store_url,
        }),
        "dsa_beneficiary": json.dumps({"name": "Merge Witches", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "Merge Witches", "category": "APP"}),
    },
    timeout=30,
)
d2 = r2.json()
adset_id = d2.get("id", "")
print(f"结果: {'✅ ' + adset_id if adset_id else '❌ ' + json.dumps(d2, ensure_ascii=False)}")

if adset_id:
    print(f"\n🎉 APP_INSTALLS 可以用了！平台问题已解决")
    print(f"Campaign: {campaign_id}")
    print(f"Adset: {adset_id}")
else:
    print(f"\n⚠️  APP_INSTALLS 仍有问题，改用 TRAFFIC + 普通 CTA")
