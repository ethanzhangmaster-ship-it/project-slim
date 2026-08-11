"""检查 App 详细信息"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

app_id = "836792580521282"

print(f"=== 检查 App {app_id} ===")

r = requests.get(
    f"{BV}/{app_id}",
    params={"access_token": USER_TOKEN},
    timeout=30,
)
d = r.json()
print("基本信息:")
print(json.dumps(d, indent=2, ensure_ascii=False))

print("\n=== 检查 adsets 配置 ===")
r2 = requests.get(
    f"{BV}/act_1784471669598847/adsets",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,targeting,promoted_object",
        "limit": 5,
    },
    timeout=30,
)
d2 = r2.json()
for adset in d2.get("data", []):
    print(f"\nAdset {adset.get('id')}: {adset.get('name')}")
    print(f"  targeting: {adset.get('targeting')}")
    print(f"  promoted_object: {adset.get('promoted_object')}")

print("\n=== 检查已存在的 APP_INSTALLS 广告 ===")
r3 = requests.get(
    f"{BV}/act_1784471669598847/ads",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,adset{optimization_goal}",
        "limit": 10,
    },
    timeout=30,
)
d3 = r3.json()
for ad in d3.get("data", []):
    print(f"Ad {ad.get('id')}: {ad.get('name')}")
    if ad.get("adset"):
        print(f"  optimization_goal: {ad['adset'].get('optimization_goal')}")
