"""对比旧 P04 账户和新账户的广告配置"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

old_account_id = "1455525822955003"  # 之前的 P04 账户
new_account_id = "1784471669598847"  # 新账户

print("=" * 60)
print("=== 1. 旧 P04 账户广告配置 ===")
print("=" * 60)

# 获取旧账户最近的广告
r = requests.get(
    f"{BV}/act_{old_account_id}/ads",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,status,campaign{name,objective},adset{name,optimization_goal,targeting,promoted_object},creative{id,name,object_story_spec}",
        "limit": 5,
    },
    timeout=30,
)
old_ads = r.json().get("data", [])

for ad in old_ads:
    print(f"\n广告: {ad.get('name')} ({ad.get('id')})")
    campaign = ad.get("campaign", {})
    adset = ad.get("adset", {})
    creative = ad.get("creative", {})
    spec = creative.get("object_story_spec", {})
    link_data = spec.get("link_data", {})
    cta = link_data.get("call_to_action", {})
    
    print(f"  Campaign: {campaign.get('name')} - objective={campaign.get('objective')}")
    print(f"  Adset: {adset.get('name')} - optimization_goal={adset.get('optimization_goal')}")
    print(f"  promoted_object: {adset.get('promoted_object')}")
    print(f"  targeting: {adset.get('targeting')}")
    print(f"  Creative: {creative.get('name')}")
    print(f"  link: {link_data.get('link')}")
    print(f"  CTA: {cta.get('type')}")
    print(f"  image_hash: {link_data.get('image_hash', 'N/A')[:20]}")

print("\n" + "=" * 60)
print("=== 2. 新账户广告配置 ===")
print("=" * 60)

new_ad_ids = [
    "120250205212690346",
    "120250205213540346",
    "120250205213660346",
    "120250205213880346",
    "120250205214560346",
]

for ad_id in new_ad_ids[:2]:  # 只看前2个
    r = requests.get(
        f"{BV}/{ad_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "id,name,status,campaign{name,objective},adset{name,optimization_goal,targeting,promoted_object},creative{id,name,object_story_spec}",
        },
        timeout=30,
    )
    ad = r.json()
    print(f"\n广告: {ad.get('name')} ({ad.get('id')})")
    campaign = ad.get("campaign", {})
    adset = ad.get("adset", {})
    creative = ad.get("creative", {})
    spec = creative.get("object_story_spec", {})
    link_data = spec.get("link_data", {})
    cta = link_data.get("call_to_action", {})
    
    print(f"  Campaign: {campaign.get('name')} - objective={campaign.get('objective')}")
    print(f"  Adset: {adset.get('name')} - optimization_goal={adset.get('optimization_goal')}")
    print(f"  promoted_object: {adset.get('promoted_object')}")
    print(f"  targeting: {adset.get('targeting')}")
    print(f"  Creative: {creative.get('name')}")
    print(f"  link: {link_data.get('link')}")
    print(f"  CTA: {cta.get('type')}")
    print(f"  image_hash: {link_data.get('image_hash', 'N/A')[:20]}")

print("\n" + "=" * 60)
print("=== 3. 对比差异 ===")
print("=" * 60)
