"""测试：用旧账户已验证的图片 hash 创建应用广告"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
app_id = "836792580521282"
page_id = "103008755226035"
instagram_user_id = "17841446738818954"

# 旧账户成功的图片 hash
old_image_hashes = [
    "3b04a2bb889763b7e6893c92288c0288",
    "b0456899a1853865c15e98765c1e8932",
    "a98763b7e6893c92288c02883b04a2bb",
]

print("=== 测试：用旧图片 hash 创建应用广告 ===")

print("\n【步骤 1】创建 Campaign...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-OldImage-AppPromo",
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
print(f"  ✅ Campaign: {campaign_id}")

print("\n【步骤 2】创建 Adset...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-OldImage-Adset",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US", "CA", "GB", "AU", "FR", "DE"]},
            "user_os": ["Android"],
            "user_device": ["Android_Smartphone", "Android_Tablet"],
            "age_min": 25,
            "age_max": 65,
        }),
        "promoted_object": json.dumps({
            "application_id": app_id,
            "object_store_url": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
        }),
        "dsa_beneficiary": json.dumps({"name": "Merge Witches", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "Merge Witches", "category": "APP"}),
    },
    timeout=30,
)
adset_id = r_aset.json().get("id", "")
print(f"  ✅ Adset: {adset_id}")

print("\n【步骤 3】创建 Creative（用旧图片 hash + instagram_user_id）...")
r_cre = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-OldImage-Creative",
        "object_story_spec": json.dumps({
            "page_id": page_id,
            "instagram_user_id": instagram_user_id,
            "link_data": {
                "image_hash": old_image_hashes[0],
                "link": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
                "call_to_action": {
                    "type": "PLAY_GAME",
                    "value": {"link": "http://play.google.com/store/apps/details?id=com.wjoy.witch"}
                },
            },
        }),
    },
    timeout=30,
)
d_cre = r_cre.json()
creative_id = d_cre.get("id", "")
print(f"  {'✅ Creative: ' + creative_id if creative_id else '❌ Creative 失败: ' + json.dumps(d_cre, ensure_ascii=False)}")

if creative_id:
    print("\n【步骤 4】创建 Ad...")
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": "P04-Test-OldImage-Ad",
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    d_ad = r_ad.json()
    ad_id = d_ad.get("id", "")
    print(f"  {'✅ Ad: ' + ad_id if ad_id else '❌ Ad 失败: ' + json.dumps(d_ad, ensure_ascii=False)}")
