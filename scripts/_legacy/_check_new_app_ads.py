"""检查新创建的 APP_INSTALLS 广告状态"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

new_ad_ids = [
    "120250205452470346",
    "120250205453640346",
    "120250205454900346",
    "120250205456760346",
    "120250205458520346",
]

old_ad_id = "120249184803470444"  # 旧账户成功的广告

print("=== 1. 检查新广告状态 ===")
for ad_id in new_ad_ids:
    r = requests.get(
        f"{BV}/{ad_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "name,status,campaign{name,objective},adset{name,optimization_goal,promoted_object}",
        },
        timeout=30,
    )
    d = r.json()
    campaign = d.get("campaign", {})
    adset = d.get("adset", {})
    print(f"\n{ad_id}: {d.get('name')}")
    print(f"  status: {d.get('status')}")
    print(f"  campaign: {campaign.get('objective')}")
    print(f"  adset: {adset.get('optimization_goal')}")
    print(f"  promoted_object: {adset.get('promoted_object')}")

print("\n" + "=" * 60)
print("=== 2. 对比旧账户成功的 Creative ===")
print("=" * 60)

r = requests.get(
    f"{BV}/{old_ad_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "creative{id,name,object_story_spec,object_story_id}",
    },
    timeout=30,
)
d = r.json()
creative = d.get("creative", {})
print(f"Creative: {creative.get('name')} ({creative.get('id')})")
print(f"object_story_id: {creative.get('object_story_id')}")
print(f"object_story_spec: {json.dumps(creative.get('object_story_spec', {}), indent=2, ensure_ascii=False)}")

print("\n" + "=" * 60)
print("=== 3. 检查新账户的 Creative ===")
print("=" * 60)

r2 = requests.get(
    f"{BV}/{new_ad_ids[0]}",
    params={
        "access_token": USER_TOKEN,
        "fields": "creative{id,name,object_story_spec,object_story_id}",
    },
    timeout=30,
)
d2 = r2.json()
creative2 = d2.get("creative", {})
print(f"Creative: {creative2.get('name')} ({creative2.get('id')})")
print(f"object_story_id: {creative2.get('object_story_id')}")
print(f"object_story_spec: {json.dumps(creative2.get('object_story_spec', {}), indent=2, ensure_ascii=False)}")

print("\n" + "=" * 60)
print("=== 4. 对比差异 ===")
print("=" * 60)
old_spec = creative.get("object_story_spec", {})
new_spec = creative2.get("object_story_spec", {})

print(f"旧 link_data: {json.dumps(old_spec.get('link_data', {}), indent=2, ensure_ascii=False)}")
print(f"新 link_data: {json.dumps(new_spec.get('link_data', {}), indent=2, ensure_ascii=False)}")
