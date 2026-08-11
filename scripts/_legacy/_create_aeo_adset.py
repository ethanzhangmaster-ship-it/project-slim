"""重新创建 AEO Adset（应用内购买目标）"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"

campaign_id = "120250206158790346"

print("=== 创建 AEO Adset（应用内购买）===")

r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-AEO-InAppPurchase",
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
            "app_install_state": "not_installed",
            "genders": [2],
            "targeting_automation": {"advantage_audience": 1},
        }),
        "promoted_object": json.dumps({
            "application_id": "836792580521282",
            "object_store_url": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
            "custom_event_type": "PURCHASE",
        }),
        "dsa_beneficiary": json.dumps({"name": "海南星月湾网络科技有限公司", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "TECDO HONG KONG LIMITED", "category": "APP"}),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")

if adset_id:
    print(f"✅ Adset 创建成功: {adset_id}")
    
    r_check = requests.get(
        f"{BV}/{adset_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "id,name,optimization_goal,promoted_object",
        },
        timeout=30,
    )
    print("\n配置详情:")
    print(json.dumps(r_check.json(), indent=2, ensure_ascii=False))
    
    print("\n=== 重新创建广告 ===")
    creative_ids = [
        "28076977575607561",
        "28076977575817561",
        "28076977576027561",
        "28076977576237561",
        "28076977576447561",
    ]
    
    for i, creative_id in enumerate(creative_ids, 1):
        r_ad = requests.post(
            f"{BV}/act_{ad_account_id}/ads",
            data={
                "access_token": USER_TOKEN,
                "name": f"P04-AI-AEO-Ad-{i}",
                "adset_id": adset_id,
                "creative": json.dumps({"creative_id": creative_id}),
                "status": "PAUSED",
            },
            timeout=30,
        )
        d_ad = r_ad.json()
        ad_id = d_ad.get("id", "")
        print(f"  {'✅ Ad ' + str(i) + ': ' + ad_id if ad_id else '❌ Ad ' + str(i) + ' 失败'}")
else:
    print(f"❌ Adset 创建失败: {json.dumps(d_aset, ensure_ascii=False)}")
