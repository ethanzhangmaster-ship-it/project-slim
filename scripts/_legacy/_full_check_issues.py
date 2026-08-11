"""全面检查广告问题"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"

campaign_id = "120250205205890346"
adset_id = "120250205207120346"
ad_id = "120250205212690346"

print("=== 1. 检查 Campaign ===")
r = requests.get(
    f"{BV}/{campaign_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,issues_info",
    },
    timeout=30,
)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

print(f"\n=== 2. 检查 Adset ===")
r2 = requests.get(
    f"{BV}/{adset_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,issues_info,optimization_goal,promoted_object",
    },
    timeout=30,
)
print(json.dumps(r2.json(), indent=2, ensure_ascii=False))

print(f"\n=== 3. 检查 Ad ===")
r3 = requests.get(
    f"{BV}/{ad_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,issues_info,creative{id,name,status,effective_status,object_story_spec}",
    },
    timeout=30,
)
print(json.dumps(r3.json(), indent=2, ensure_ascii=False))

print(f"\n=== 4. 列出账户下所有带问题的广告 ===")
r4 = requests.get(
    f"{BV}/act_{ad_account_id}/ads",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,campaign_id",
        "filtering": json.dumps([{"field": "effective_status", "operator": "IN", "value": ["WITH_ISSUES"]}]),
        "limit": 20,
    },
    timeout=30,
)
d4 = r4.json()
ads = d4.get("data", [])
print(f"有问题的广告数: {len(ads)}")
for ad in ads:
    print(f"  {ad.get('name')}: eff={ad.get('effective_status')}, campaign={ad.get('campaign_id')}")
