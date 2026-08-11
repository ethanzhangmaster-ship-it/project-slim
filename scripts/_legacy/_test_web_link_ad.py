"""测试：用普通网页链接创建广告，排除账户问题"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
page_id = "103008755226035"

print("=== 测试：普通网页链接广告 ===")
print("目标：排除账户本身的问题")
print()

print("【步骤 1】创建 Campaign (OUTCOME_TRAFFIC)...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-Web-Traffic",
        "objective": "OUTCOME_TRAFFIC",
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
    print(f"  ❌ Campaign 失败: {d_camp}")
    exit(1)
print(f"  ✅ Campaign: {campaign_id}")

print("\n【步骤 2】创建 Adset (LINK_CLICKS)...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-Web-Adset",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 1000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US"]},
        }),
        "dsa_beneficiary": json.dumps({"name": "Merge Witches", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "Merge Witches", "category": "APP"}),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if not adset_id:
    print(f"  ❌ Adset 失败: {d_aset}")
    exit(1)
print(f"  ✅ Adset: {adset_id}")

print("\n【步骤 3】上传图片...")
r_upload = requests.post(
    f"{BV}/act_{ad_account_id}/adimages",
    data={"access_token": USER_TOKEN, "filename": "test-web.png"},
    files={"source": open("C:\\Users\\ethan\\Downloads\\project_slim\\output\\creative_growth_loop\\images\\closed_loop_20260630_070843\\variant_01_00.png", 'rb')},
    timeout=60,
)
d_upload = r_upload.json()
image_hash = ""
if d_upload.get("images"):
    image_hash = list(d_upload["images"].values())[0].get("hash", "")
print(f"  ✅ image_hash: {image_hash}")

print("\n【步骤 4】创建 Creative（普通网页链接）...")
r_cre = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-Web-Creative",
        "object_story_spec": json.dumps({
            "page_id": page_id,
            "link_data": {
                "image_hash": image_hash,
                "link": "https://www.google.com",
                "message": "Test ad",
                "call_to_action": {
                    "type": "LEARN_MORE",
                    "value": {"link": "https://www.google.com"}
                },
            },
        }),
    },
    timeout=30,
)
d_cre = r_cre.json()
creative_id = d_cre.get("id", "")
if not creative_id:
    print(f"  ❌ Creative 失败: {d_cre}")
    exit(1)
print(f"  ✅ Creative: {creative_id}")

print("\n【步骤 5】创建 Ad...")
r_ad = requests.post(
    f"{BV}/act_{ad_account_id}/ads",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-Web-Ad",
        "adset_id": adset_id,
        "creative": json.dumps({"creative_id": creative_id}),
        "status": "PAUSED",
    },
    timeout=30,
)
d_ad = r_ad.json()
ad_id = d_ad.get("id", "")
print(f"  {'✅ Ad: ' + ad_id if ad_id else '❌ Ad 失败: ' + json.dumps(d_ad, ensure_ascii=False)}")

print("\n" + "=" * 60)
print("=== 结论 ===")
print("=" * 60)
if ad_id:
    print("✅ 普通网页链接广告创建成功！")
    print("问题不在账户本身，而是应用广告的配置问题")
else:
    print("❌ 普通网页链接广告也失败了")
    print("问题在账户级别，需要检查账户设置")
