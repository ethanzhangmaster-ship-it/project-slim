"""获取正确的 Creative IDs"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"

print("=== 获取账户的 Creatives ===")
r = requests.get(
    f"{BV}/act_{ad_account_id}/adcreatives",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name",
        "limit": 20,
    },
    timeout=30,
)
creatives = r.json().get("data", [])
print(f"找到 {len(creatives)} 个 Creatives:")
for cre in creatives:
    print(f"  {cre.get('id')}: {cre.get('name')}")

print("\n=== 获取之前广告的 Creative IDs ===")
old_ad_ids = [
    "120250206163350346",
    "120250206163570346",
    "120250206163810346",
    "120250206164090346",
    "120250206164310346",
]

creative_ids = []
for ad_id in old_ad_ids:
    r2 = requests.get(
        f"{BV}/{ad_id}",
        params={"access_token": USER_TOKEN, "fields": "creative{id,name}"},
        timeout=30,
    )
    d2 = r2.json()
    creative = d2.get("creative", {})
    print(f"  {ad_id}: creative={creative.get('id')} ({creative.get('name')})")
    creative_ids.append(creative.get("id"))

print(f"\n可用的 creative_ids: {creative_ids}")
