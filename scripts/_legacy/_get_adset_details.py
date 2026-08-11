"""正确获取 adset 详情"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

# 从旧广告获取 adset ID
old_ad_id = "120249184803470444"
r = requests.get(
    f"{BV}/{old_ad_id}",
    params={"access_token": USER_TOKEN, "fields": "adset{id}"},
    timeout=30,
)
old_adset_id = r.json().get("adset", {}).get("id", "")
print(f"旧 Adset ID: {old_adset_id}")

# 从新广告获取 adset ID
new_ad_id = "120250205452470346"
r2 = requests.get(
    f"{BV}/{new_ad_id}",
    params={"access_token": USER_TOKEN, "fields": "adset{id}"},
    timeout=30,
)
new_adset_id = r2.json().get("adset", {}).get("id", "")
print(f"新 Adset ID: {new_adset_id}")

print("\n=== 旧账户 Adset 详情 ===")
r3 = requests.get(
    f"{BV}/{old_adset_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,optimization_goal,promoted_object,targeting,campaign{id,name,objective}",
    },
    timeout=30,
)
old_adset = r3.json()
print(json.dumps(old_adset, indent=2, ensure_ascii=False))

print("\n=== 新账户 Adset 详情 ===")
r4 = requests.get(
    f"{BV}/{new_adset_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,optimization_goal,promoted_object,targeting,campaign{id,name,objective}",
    },
    timeout=30,
)
new_adset = r4.json()
print(json.dumps(new_adset, indent=2, ensure_ascii=False))

print("\n" + "=" * 60)
print("=== 对比差异 ===")
print("=" * 60)
print(f"旧 promoted_object: {old_adset.get('promoted_object')}")
print(f"新 promoted_object: {new_adset.get('promoted_object')}")
print(f"旧 targeting keys: {list(old_adset.get('targeting', {}).keys())}")
print(f"新 targeting keys: {list(new_adset.get('targeting', {}).keys())}")
