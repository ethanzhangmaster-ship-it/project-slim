"""检查旧账户广告是否真的能投放"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

old_account_id = "1455525822955003"
new_account_id = "1784471669598847"

print("=== 旧账户广告状态 ===")
r = requests.get(
    f"{BV}/act_{old_account_id}/ads",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,campaign{name,objective}",
        "limit": 10,
    },
    timeout=30,
)
old_ads = r.json().get("data", [])
for ad in old_ads:
    campaign = ad.get("campaign", {})
    print(f"  {ad.get('name')}: status={ad.get('status')}, effective={ad.get('effective_status')}, objective={campaign.get('objective')}")

print(f"\n=== 新账户广告状态 ===")
r2 = requests.get(
    f"{BV}/act_{new_account_id}/ads",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,campaign{name,objective}",
        "limit": 10,
    },
    timeout=30,
)
new_ads = r2.json().get("data", [])
for ad in new_ads:
    campaign = ad.get("campaign", {})
    print(f"  {ad.get('name')}: status={ad.get('status')}, effective={ad.get('effective_status')}, objective={campaign.get('objective')}")

print(f"\n=== 检查 App 配置 ===")
app_id = "836792580521282"
r3 = requests.get(
    f"{BV}/{app_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,platforms,ios_bundle_id,android_package",
    },
    timeout=30,
)
d3 = r3.json()
print(f"App: {d3.get('name')} ({app_id})")
print(f"platforms: {d3.get('platforms')}")
print(f"ios_bundle_id: {d3.get('ios_bundle_id')}")
print(f"android_package: {d3.get('android_package')}")

print(f"\n=== 检查账户权限 ===")
r4 = requests.get(
    f"{BV}/act_{new_account_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,currency,timezone_name,disabled_reason",
    },
    timeout=30,
)
d4 = r4.json()
print(f"账户: {d4.get('name')}")
print(f"currency: {d4.get('currency')}")
print(f"timezone: {d4.get('timezone_name')}")
print(f"disabled_reason: {d4.get('disabled_reason')}")
