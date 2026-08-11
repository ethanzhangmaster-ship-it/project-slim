"""测试：用最简单的方式创建应用广告"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
app_id = "836792580521282"
page_id = "103008755226035"

print("=== 测试 1: 复制旧账户的成功 Creative ===")
old_creative_id = "28075417912047561"

r = requests.get(
    f"{BV}/{old_creative_id}",
    params={"access_token": USER_TOKEN, "fields": "id,name,object_story_spec"},
    timeout=30,
)
old_spec = r.json().get("object_story_spec", {})
print(f"旧 Creative spec: {json.dumps(old_spec, ensure_ascii=False)[:300]}")

r_new = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-Test-Copy-Creative",
        "object_story_spec": json.dumps(old_spec),
    },
    timeout=30,
)
d_new = r_new.json()
creative_id = d_new.get("id", "")
print(f"新 Creative: {'✅ ' + creative_id if creative_id else '❌ ' + json.dumps(d_new, ensure_ascii=False)}")

if creative_id:
    print(f"\n=== 创建测试 Ad ===")
    # 使用之前创建的 adset
    adset_id = "120250205444460346"
    
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": "P04-Test-Copy-Ad",
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    d_ad = r_ad.json()
    ad_id = d_ad.get("id", "")
    print(f"测试 Ad: {'✅ ' + ad_id if ad_id else '❌ ' + json.dumps(d_ad, ensure_ascii=False)}")

print("\n" + "=" * 60)
print("=== 测试 2: 检查新账户能否访问 App ===")
print("=" * 60)

# 尝试获取应用详情
r_app = requests.get(
    f"{BV}/{app_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,platforms",
    },
    timeout=30,
)
d_app = r_app.json()
print(f"App 查询结果: {json.dumps(d_app, ensure_ascii=False)}")

# 检查账户关联的应用
r_account_apps = requests.get(
    f"{BV}/act_{ad_account_id}/applications",
    params={"access_token": USER_TOKEN},
    timeout=30,
)
d_account_apps = r_account_apps.json()
apps = d_account_apps.get("data", [])
print(f"\n账户关联的应用: {len(apps)} 个")
for app in apps:
    print(f"  - {app.get('id')}: {app.get('name')}")

# 检查是否有权限
r_permissions = requests.get(
    f"{BV}/me/permissions",
    params={"access_token": USER_TOKEN},
    timeout=30,
)
d_permissions = r_permissions.json()
print(f"\n用户权限: {len(d_permissions.get('data', []))} 项")
