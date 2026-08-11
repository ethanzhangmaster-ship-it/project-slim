"""检查 promoted_object 的差异"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

old_ad_id = "120249184803470444"
new_ad_id = "120250205452470346"

print("=== 旧账户成功的 Adset ===")
r = requests.get(
    f"{BV}/{old_ad_id}/adset",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,optimization_goal,promoted_object,targeting",
    },
    timeout=30,
)
old_adset = r.json()
print(f"promoted_object: {json.dumps(old_adset.get('promoted_object', {}), indent=2)}")
print(f"targeting: {json.dumps(old_adset.get('targeting', {}), indent=2)}")

print("\n=== 新账户失败的 Adset ===")
r2 = requests.get(
    f"{BV}/{new_ad_id}/adset",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,optimization_goal,promoted_object,targeting",
    },
    timeout=30,
)
new_adset = r2.json()
print(f"promoted_object: {json.dumps(new_adset.get('promoted_object', {}), indent=2)}")
print(f"targeting: {json.dumps(new_adset.get('targeting', {}), indent=2)}")

print("\n" + "=" * 60)
print("=== 测试：不指定 object_store_url ===")
print("=" * 60)

ad_account_id = "1784471669598847"
app_id = "836792580521282"

r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-NoStoreUrl",
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
campaign_id = r_camp.json().get("id", "")
print(f"Campaign: {campaign_id}")

r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-NoStoreUrl-Adset",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US"]},
            "user_os": ["Android"],
            "user_device": ["Android_Smartphone", "Android_Tablet"],
        }),
        "promoted_object": json.dumps({
            "application_id": app_id,
        }),
        "dsa_beneficiary": json.dumps({"name": "Merge Witches", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "Merge Witches", "category": "APP"}),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
print(f"Adset: {'✅ ' + adset_id if adset_id else '❌ ' + json.dumps(d_aset, ensure_ascii=False)}")
