"""测试：OUTCOME_TRAFFIC + dsa_beneficiary"""
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
        "name": "P04-AI-Traffic-v2",
        "objective": "OUTCOME_TRAFFIC",
        "status": "PAUSED",
        "is_adset_budget_sharing_enabled": True,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "special_ad_categories": json.dumps([]),
        "dsa_beneficiary": json.dumps({
            "name": "Merge Witches",
            "category": "APP",
        }),
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
        "name": "P04-AI-Traffic-Adset-v2",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US"]},
            "device_platforms": ["mobile"],
        }),
        "dsa_beneficiary": json.dumps({
            "name": "Merge Witches",
            "category": "APP",
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

print("\n检查图片文件...")
image_path = "output/creative_growth_loop/images/2026-06-30_08-59-03/manifest.json"
try:
    import os
    with open(image_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    image_files = manifest.get("images", [])
    print(f"找到 {len(image_files)} 张图片")
    for img in image_files:
        print(f"  - {img.get('file_path')}")
except Exception as e:
    print(f"读取图片失败: {e}")
