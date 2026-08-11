"""完整创建 P04 广告：复制旧账户成功配置"""
import json, requests, os

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
app_id = "836792580521282"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
page_id = "103008755226035"

manifest_path = "C:\\Users\\ethan\\Downloads\\project_slim\\output\\creative_growth_loop\\images\\closed_loop_20260630_070843\\manifest.json"

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

print("=" * 60)
print("P04 Witch 广告创建 - 复制旧账户成功配置")
print("=" * 60)
print(f"账户: {ad_account_id}")
print(f"图片数量: {len(manifest['images'])}")
print(f"目标: OUTCOME_APP_PROMOTION + APP_INSTALLS")
print(f"Targeting: user_os=Android (解决平台匹配)")
print()

print("【步骤 1/5】创建 Campaign (OUTCOME_APP_PROMOTION)...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-AppPromo-20260701",
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
    print(f"  ❌ 失败: {d_camp}")
    exit(1)
print(f"  ✅ Campaign: {campaign_id}")

print("\n【步骤 2/5】创建 Adset (APP_INSTALLS + Android targeting)...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-AppInstalls-欧美-Android",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {
                "countries": ["US", "CA", "GB", "AU", "FR", "DE"],
                "location_types": ["home", "recent"],
            },
            "user_os": ["Android"],
            "user_device": ["Android_Smartphone", "Android_Tablet"],
            "age_min": 25,
            "age_max": 65,
            "app_install_state": "not_installed",
            "genders": [2],  # 女性
            "targeting_automation": {"advantage_audience": 1},
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
if not adset_id:
    print(f"  ❌ 失败: {d_aset}")
    exit(1)
print(f"  ✅ Adset: {adset_id}")

print("\n【步骤 3/5】上传图片到广告账户图片库...")
image_hashes = []
for i, img_info in enumerate(manifest['images'], 1):
    img_path = img_info['file_path']
    if not os.path.exists(img_path):
        print(f"  ⚠️  图片 {i} 不存在")
        continue
    
    with open(img_path, 'rb') as img_file:
        r = requests.post(
            f"{BV}/act_{ad_account_id}/adimages",
            data={"access_token": USER_TOKEN, "filename": f"P04-app-{i}.png"},
            files={"source": img_file},
            timeout=60,
        )
    d = r.json()
    if d.get("images"):
        ih = list(d["images"].values())[0].get("hash", "")
        if ih:
            image_hashes.append(ih)
            print(f"  ✅ 图片 {i}: hash={ih}")
            continue
    print(f"  ❌ 图片 {i} 失败")

print(f"\n【步骤 4/5】创建 Creatives（PLAY_GAME CTA）...")
creative_ids = []
for i, image_hash in enumerate(image_hashes, 1):
    r_cre = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-App-Creative-{i}",
            "object_story_spec": json.dumps({
                "page_id": page_id,
                "link_data": {
                    "image_hash": image_hash,
                    "link": store_url,
                    "message": "Merge Witches - Play Now!",
                    "call_to_action": {
                        "type": "PLAY_GAME",
                        "value": {"link": store_url}
                    },
                },
            }),
        },
        timeout=30,
    )
    d_cre = r_cre.json()
    creative_id = d_cre.get("id", "")
    if creative_id:
        creative_ids.append(creative_id)
        print(f"  ✅ Creative {i}: {creative_id}")
    else:
        print(f"  ❌ Creative {i} 失败: {d_cre}")

print(f"\n【步骤 5/5】创建 Ads...")
ad_ids = []
for i, creative_id in enumerate(creative_ids, 1):
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-App-Ad-{i}",
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    d_ad = r_ad.json()
    ad_id = d_ad.get("id", "")
    if ad_id:
        ad_ids.append(ad_id)
        print(f"  ✅ Ad {i}: {ad_id}")
    else:
        print(f"  ❌ Ad {i} 失败: {d_ad}")

print("\n" + "=" * 60)
print("【自检】验证广告配置")
print("=" * 60)

all_ok = True
for i, ad_id in enumerate(ad_ids, 1):
    r = requests.get(
        f"{BV}/{ad_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "name,status,campaign{name,objective},adset{name,optimization_goal},creative{id,name,object_story_spec}",
        },
        timeout=30,
    )
    d = r.json()
    campaign = d.get("campaign", {})
    adset = d.get("adset", {})
    creative = d.get("creative", {})
    spec = creative.get("object_story_spec", {})
    link_data = spec.get("link_data", {})
    cta = link_data.get("call_to_action", {})
    
    print(f"\nAd {i}: {d.get('name')}")
    print(f"  Campaign: {campaign.get('objective')}")
    print(f"  Adset: {adset.get('optimization_goal')}")
    print(f"  CTA: {cta.get('type')}")
    print(f"  link: {link_data.get('link')}")
    
    # 验证配置是否正确
    if campaign.get("objective") != "OUTCOME_APP_PROMOTION":
        print(f"  ⚠️ Campaign 目标不对")
        all_ok = False
    if adset.get("optimization_goal") != "APP_INSTALLS":
        print(f"  ⚠️ Adset 优化目标不对")
        all_ok = False

print("\n" + "=" * 60)
print(f"【结果】{'配置正确 ✅' if all_ok else '有问题 ❌'}")
print("=" * 60)
print(f"Campaign: {campaign_id}")
print(f"Adset: {adset_id}")
print(f"广告: {len(ad_ids)}/5")
if ad_ids:
    print(f"广告 IDs: {', '.join(ad_ids)}")
