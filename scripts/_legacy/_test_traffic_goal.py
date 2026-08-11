"""测试：OUTCOME_TRAFFIC 目标，直接链接到 Google Play"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
page_id = "103008755226035"

print("创建 OUTCOME_TRAFFIC Campaign...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Traffic-Test",
        "objective": "OUTCOME_TRAFFIC",
        "status": "PAUSED",
        "is_adset_budget_sharing_enabled": True,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "special_ad_categories": json.dumps([]),
    },
    timeout=30,
)
d_camp = r_camp.json()
campaign_id = d_camp.get("id", "")
if not campaign_id:
    print(f"Campaign 创建失败: {d_camp}")
    exit(1)
print(f" ✅ Campaign: {campaign_id}")

print("\n创建 Adset (LINK_CLICKS)...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Traffic-Adset",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US", "GB", "DE", "FR", "CA", "AU"]},
            "device_platforms": ["mobile"],
        }),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if not adset_id:
    print(f"Adset 创建失败: {d_aset}")
    exit(1)
print(f" ✅ Adset: {adset_id}")

print("\n上传图片到 Page...")
image_path = "output/creative_growth_loop/images/2026-06-30_08-59-03/manifest.json"
try:
    import os
    with open(image_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    image_files = manifest.get("images", [])
    if image_files:
        first_image = image_files[0].get("file_path", "")
        if os.path.exists(first_image):
            with open(first_image, 'rb') as img_file:
                r_upload = requests.post(
                    f"{BV}/{page_id}/photos",
                    data={
                        "access_token": USER_TOKEN,
                        "published": "false",
                    },
                    files={"source": img_file},
                    timeout=60,
                )
            d_upload = r_upload.json()
            photo_id = d_upload.get("id", "")
            print(f" ✅ 图片上传成功: {photo_id}")
            
            print("\n创建 Creative...")
            r_cre = requests.post(
                f"{BV}/act_{ad_account_id}/adcreatives",
                data={
                    "access_token": USER_TOKEN,
                    "name": "P04-AI-Traffic-Creative",
                    "object_story_spec": json.dumps({
                        "page_id": page_id,
                        "link_data": {
                            "image_hash": d_upload.get("image_hash", ""),
                            "link": store_url,
                            "message": "Merge Witches - Play Now!",
                        },
                    }),
                },
                timeout=30,
            )
            d_cre = r_cre.json()
            creative_id = d_cre.get("id", "")
            print(f" 结果: {'✅ ' + creative_id if creative_id else '❌ ' + json.dumps(d_cre, ensure_ascii=False)}")
            
            if creative_id:
                print("\n创建 Ad...")
                r_ad = requests.post(
                    f"{BV}/act_{ad_account_id}/ads",
                    data={
                        "access_token": USER_TOKEN,
                        "name": "P04-AI-Traffic-Ad",
                        "adset_id": adset_id,
                        "creative": json.dumps({"creative_id": creative_id}),
                        "status": "PAUSED",
                    },
                    timeout=30,
                )
                d_ad = r_ad.json()
                ad_id = d_ad.get("id", "")
                print(f" 结果: {'✅ ' + ad_id if ad_id else '❌ ' + json.dumps(d_ad, ensure_ascii=False)}")
        else:
            print(f"图片文件不存在: {first_image}")
except Exception as e:
    print(f"读取图片失败: {e}")
