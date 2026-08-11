"""测试：去掉 message 字段的 Creative"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
app_id = "836792580521282"
page_id = "103008755226035"

print("=== 测试：不带 message 的 Creative ===")

print("\n【步骤 1】上传图片...")
r_upload = requests.post(
    f"{BV}/act_{ad_account_id}/adimages",
    data={"access_token": USER_TOKEN, "filename": "p04-no-message.png"},
    files={"source": open("C:\\Users\\ethan\\Downloads\\project_slim\\output\\creative_growth_loop\\images\\closed_loop_20260630_070843\\variant_01_00.png", 'rb')},
    timeout=60,
)
d_upload = r_upload.json()
image_hash = ""
if d_upload.get("images"):
    image_hash = list(d_upload["images"].values())[0].get("hash", "")
print(f"  ✅ image_hash: {image_hash}")

print("\n【步骤 2】创建 Campaign...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-NoMessage",
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

print("\n【步骤 3】创建 Adset...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-NoMessage-Adset",
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
            "application_id": app_id,
            "object_store_url": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
        }),
        "dsa_beneficiary": json.dumps({"name": "Merge Witches", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "Merge Witches", "category": "APP"}),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if adset_id:
    print(f"  ✅ Adset: {adset_id}")
else:
    print(f"  ❌ Adset 失败: {json.dumps(d_aset, ensure_ascii=False)}")
    exit(1)

print("\n【步骤 4】创建 Creative（完全复制旧账户格式，不带 message）...")
r_cre = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-NoMessage-Creative",
        "object_story_spec": json.dumps({
            "page_id": page_id,
            "link_data": {
                "image_hash": image_hash,
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
    print("\n【步骤 5】创建 Ad...")
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": "P04-Test-NoMessage-Ad",
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    d_ad = r_ad.json()
    ad_id = d_ad.get("id", "")
    print(f"  {'✅ Ad: ' + ad_id if ad_id else '❌ Ad 失败: ' + json.dumps(d_ad, ensure_ascii=False)}")
    
    print("\n等待 30 秒检查状态...")
    import time
    time.sleep(30)
    
    r_check = requests.get(
        f"{BV}/{ad_id}",
        params={"access_token": USER_TOKEN, "fields": "name,status,effective_status"},
        timeout=30,
    )
    d_check = r_check.json()
    print(f"\n广告状态:")
    print(f"  status: {d_check.get('status')}")
    print(f"  effective_status: {d_check.get('effective_status')}")
    
    if d_check.get("effective_status") == "PAUSED":
        print("\n🎉 成功！问题出在 message 字段")
    else:
        print("\n⚠️  还是有问题")
