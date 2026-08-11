"""测试：新账户用 APP_INSTALLS + user_os Android"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
app_id = "836792580521282"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

print("=== 测试：OUTCOME_APP_PROMOTION Campaign ===")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-AppPromo-Android",
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
d_camp = r_camp.json()
campaign_id = d_camp.get("id", "")
if not campaign_id:
    print(f"❌ Campaign 失败: {d_camp}")
    exit(1)
print(f"✅ Campaign: {campaign_id}")

print(f"\n=== 测试：APP_INSTALLS Adset (带 user_os Android) ===")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-Android-Adset",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US", "GB", "DE", "FR", "CA", "AU"]},
            "user_os": ["Android"],
            "user_device": ["Android_Smartphone", "Android_Tablet"],
            "age_min": 25,
            "age_max": 65,
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
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if adset_id:
    print(f"✅ Adset 成功: {adset_id}")
    print("\n🎉 找到了！关键是 targeting 里加 user_os: ['Android']")
else:
    print(f"❌ Adset 仍失败: {d_aset}")
    print("\n和旧账户的配置差异还有其他因素...")
