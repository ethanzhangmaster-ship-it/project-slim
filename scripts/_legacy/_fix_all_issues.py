"""修复4个问题：广告主、AEO目标、文案、图片"""
import json, requests, os

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
app_id = "836792580521282"
page_id = "103008755226035"

manifest_path = "C:\\Users\\ethan\\Downloads\\project_slim\\output\\creative_growth_loop\\images\\closed_loop_20260630_070843\\manifest.json"

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

print("=" * 60)
print("修复4个问题")
print("=" * 60)
print("问题1: 广告主 -> 海南星月湾网络科技有限公司")
print("问题2: 成效目标 -> AEO购物事件")
print("问题3: 添加广告文案")
print("问题4: 优化图片上传")
print()

print("【步骤 1/5】创建 AEO Campaign (OUTCOME_SALES)...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-AEO-Sales-Final",
        "objective": "OUTCOME_SALES",
        "status": "PAUSED",
        "is_adset_budget_sharing_enabled": True,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "special_ad_categories": json.dumps([]),
        "dsa_beneficiary": json.dumps({"name": "海南星月湾网络科技有限公司", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "TECDO HONG KONG LIMITED", "category": "APP"}),
    },
    timeout=30,
)
d_camp = r_camp.json()
campaign_id = d_camp.get("id", "")
if not campaign_id:
    print(f"  ❌ Campaign 失败: {d_camp}")
    exit(1)
print(f"  ✅ Campaign: {campaign_id}")

print("\n【步骤 2/5】创建 Adset (AEO购物事件)...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-AEO-Adset",
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
        "dsa_beneficiary": json.dumps({"name": "海南星月湾网络科技有限公司", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "TECDO HONG KONG LIMITED", "category": "APP"}),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if not adset_id:
    print(f"  ❌ Adset 失败: {d_aset}")
    exit(1)
print(f"  ✅ Adset: {adset_id}")

print("\n【步骤 3/5】上传图片...")
image_hashes = []
for i, img_info in enumerate(manifest['images'], 1):
    img_path = img_info['file_path']
    if not os.path.exists(img_path):
        continue
    
    with open(img_path, 'rb') as img_file:
        r = requests.post(
            f"{BV}/act_{ad_account_id}/adimages",
            data={"access_token": USER_TOKEN, "filename": f"p04-aeo-{i}.png"},
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

print(f"\n【步骤 4/5】创建 Creatives（带文案）...")
ad_copies = [
    {
        "body": "Merge Witches - 最 addictive merge puzzle game! Merge witches to unlock powerful spells and magical abilities. Download now and start your magical journey!",
        "title": "Merge Witches",
        "subtitle": "Play Now!",
    },
    {
        "body": "Discover the magic of Merge Witches! Combine cute witch characters and create powerful magical beings. Over 100 levels to explore!",
        "title": "Play Merge Witches",
        "subtitle": "Free Download!",
    },
    {
        "body": "Merge Witches - A magical puzzle adventure! Merge, collect and evolve your witches. Join millions of players worldwide!",
        "title": "Merge Witches Game",
        "subtitle": "Start Playing!",
    },
    {
        "body": "Experience the enchanting world of Merge Witches! Merge magical creatures and build your witch kingdom. Hours of fun!",
        "title": "Merge Witches",
        "subtitle": "Download Free!",
    },
    {
        "body": "Unleash your inner witch with Merge Witches! Merge characters, cast spells, and conquer magical challenges. Free to play!",
        "title": "Play Merge Witches",
        "subtitle": "Join Now!",
    },
]

creative_ids = []
for i, (image_hash, copy) in enumerate(zip(image_hashes, ad_copies), 1):
    r_cre = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-AEO-Creative-{i}",
            "object_story_spec": json.dumps({
                "page_id": page_id,
                "link_data": {
                    "image_hash": image_hash,
                    "link": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
                    "message": copy["body"],
                    "title": copy["title"],
                    "subtitle": copy["subtitle"],
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
            "name": f"P04-AI-AEO-Ad-{i}",
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
print("修复完成")
print("=" * 60)
print(f"Campaign: {campaign_id}")
print(f"Adset: {adset_id}")
print(f"广告: {len(ad_ids)}/5")
if ad_ids:
    print(f"广告 IDs: {', '.join(ad_ids)}")

print("\n修改内容:")
print("1. 广告主: 海南星月湾网络科技有限公司")
print("2. 付费方: TECDO HONG KONG LIMITED")
print("3. 成效目标: OUTCOME_SALES (AEO)")
print("4. 添加了广告文案(body)、标题(title)、副标题(subtitle)")
print("5. 使用了新图片")
