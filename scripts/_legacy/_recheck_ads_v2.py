"""复查广告状态 v2"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_ids = [
    "120250205212690346",
    "120250205213540346",
    "120250205213660346",
    "120250205213880346",
    "120250205214560346",
]

print("=== 复查广告状态 ===")

for ad_id in ad_ids:
    r = requests.get(
        f"{BV}/{ad_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "name,status,effective_status",
        },
        timeout=30,
    )
    d = r.json()
    print(f"\n{ad_id}:")
    print(f"  name: {d.get('name')}")
    print(f"  status: {d.get('status')}")
    print(f"  effective_status: {d.get('effective_status')}")
    if 'error' in d:
        print(f"  error: {d['error']}")

print("\n=== 用 ad 列表接口查询 ===")
r2 = requests.get(
    f"{BV}/act_1784471669598847/ads",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,configured_status",
        "limit": 20,
    },
    timeout=30,
)
d2 = r2.json()
ads = d2.get("data", [])
print(f"总广告数: {len(ads)}")
for ad in ads:
    print(f"  {ad.get('name')}: status={ad.get('status')}, eff={ad.get('effective_status')}, cfg={ad.get('configured_status')}")
