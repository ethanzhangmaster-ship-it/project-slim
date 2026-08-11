"""完整创建 P04 广告：OUTCOME_TRAFFIC + 新图片素材"""
import json, requests, os

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
page_id = "103008755226035"

manifest_path = "C:\\Users\\ethan\\Downloads\\project_slim\\output\\creative_growth_loop\\images\\closed_loop_20260630_070843\\manifest.json"

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

print(f"=== 创建 P04 Witch 广告 ===")
print(f"账户: {ad_account_id}")
print(f"图片数量: {len(manifest['images'])}")
print()

print("1. 创建 OUTCOME_TRAFFIC Campaign...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Traffic-20260701",
        "objective": "OUTCOME_TRAFFIC",
        "status": "PAUSED",
        "is_adset_budget_sharing_enabled": True,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "special_ad_categories": json.dumps([]),
        "dsa_beneficiary": json.dumps({
            "name": "Merge Witches",
            "category": "APP",
        }),
        "dsa_payor": json.dumps({
            "name": "Merge Witches",
            "category": "APP",
        }),
    },
    timeout=30,
)
d_camp = r_camp.json()
campaign_id = d_camp.get("id", "")
if not campaign_id:
    print(f" ❌ Campaign 创建失败: {d_camp}")
    exit(1)
print(f" ✅ Campaign: {campaign_id}")

print("\n2. 创建 Adset (LINK_CLICKS)...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Traffic-Adset-欧美",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US", "GB", "DE", "FR", "CA", "AU"]},
            "device_platforms": ["mobile"],
        }),
        "dsa_beneficiary": json.dumps({
            "name": "Merge Witches",
            "category": "APP",
        }),
        "dsa_payor": json.dumps({
            "name": "Merge Witches",
            "category": "APP",
        }),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if not adset_id:
    print(f" ❌ Adset 创建失败: {d_aset}")
    exit(1)
print(f" ✅ Adset: {adset_id}")

print("\n3. 上传图片到广告账户图片库...")
image_hashes = []

for i, img_info in enumerate(manifest['images'], 1):
    img_path = img_info['file_path']
    if not os.path.exists(img_path):
        print(f"   ⚠️ 图片不存在: {img_path}")
        continue
    
    print(f"\n   --- 图片 {i}/5 ---")
    
    with open(img_path, 'rb') as img_file:
        r_upload = requests.post(
            f"{BV}/act_{ad_account_id}/images",
            data={
                "access_token": USER_TOKEN,
                "filename": f"P04-AI-{i}.png",
            },
            files={"source": img_file},
            timeout=60,
        )
    d_upload = r_upload.json()
    
    if d_upload.get("images"):
        image_hash = d_upload["images"][0].get("hash", "")
        if image_hash:
            print(f"   ✅ 图片上传成功: {image_hash}")
            image_hashes.append(image_hash)
        else:
            print(f"   ❌ 图片上传失败: {d_upload}")
    else:
        print(f"   ❌ 图片上传失败: {d_upload}")

print(f"\n4. 创建 Creatives 和 Ads...")
created_ads = []

for i, image_hash in enumerate(image_hashes, 1):
    print(f"\n   --- Creative {i}/{len(image_hashes)} ---")
    
    r_cre = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-Creative-{i}",
            "object_story_spec": json.dumps({
                "page_id": page_id,
                "link_data": {
                    "image_hash": image_hash,
                    "link": store_url,
                    "message": "Merge Witches - Play Now!",
                },
            }),
        },
        timeout=30,
    )
    d_cre = r_cre.json()
    creative_id = d_cre.get("id", "")
    
    if not creative_id:
        print(f"   ❌ Creative 创建失败: {d_cre}")
        continue
    print(f"   ✅ Creative: {creative_id}")
    
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-Ad-{i}",
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    d_ad = r_ad.json()
    ad_id = d_ad.get("id", "")
    
    if ad_id:
        print(f"   ✅ Ad: {ad_id}")
        created_ads.append(ad_id)
    else:
        print(f"   ❌ Ad 创建失败: {d_ad}")

print(f"\n=== 完成 ===")
print(f"上传图片: {len(image_hashes)}/{len(manifest['images'])}")
print(f"创建的广告: {len(created_ads)}/{len(image_hashes)}")
if created_ads:
    print(f"广告 ID: {', '.join(created_ads)}")
