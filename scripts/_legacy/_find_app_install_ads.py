import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

# 找 APP_INSTALLS 类型的 adset
r = requests.get(
    f"{BV}/act_{ad_account_id}/adsets",
    params={
        "access_token": TOKEN,
        "fields": "id,name,optimization_goal,promoted_object",
        "limit": 50,
    },
    timeout=30,
)
adsets = r.json().get("data", [])
app_install_adsets = [a for a in adsets if a.get("optimization_goal") == "APP_INSTALLS"]
print(f"APP_INSTALLS adsets: {len(app_install_adsets)}")
for a in app_install_adsets[:5]:
    print(f"  {a['id']}: {a.get('name','')[:50]}")
    print(f"    promoted_object: {json.dumps(a.get('promoted_object',{}), ensure_ascii=False)[:100]}")

# 如果没有，看看所有 adset 的目标类型
if not app_install_adsets:
    print("\n所有 adset 的目标类型:")
    types = set()
    for a in adsets:
        types.add(a.get("optimization_goal"))
    print(f"  {types}")

# 找一个有广告的 adset，看其 creative
for aset in adsets[:3]:
    r2 = requests.get(
        f"{BV}/{aset['id']}/ads",
        params={
            "access_token": TOKEN,
            "fields": "id,name,creative{id,name,image_hash,object_store_url,object_type,body,title}",
            "limit": 2,
        },
        timeout=30,
    )
    ads = r2.json().get("data", [])
    if ads:
        print(f"\nAdset {aset['id']} ({aset.get('optimization_goal')}):")
        for ad in ads:
            c = ad.get("creative", {})
            print(f"  Ad: {ad['id']}")
            print(f"  Creative: {json.dumps(c, ensure_ascii=False, indent=4)[:300]}")
        break