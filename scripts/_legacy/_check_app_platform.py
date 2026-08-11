"""检查 App 平台配置"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

app_ids = ["836792580521282", "629727356750561"]

for app_id in app_ids:
    print(f"\n=== 检查 App {app_id} ===")
    
    r = requests.get(
        f"{BV}/{app_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "name,platforms,category",
        },
        timeout=30,
    )
    d = r.json()
    print(json.dumps(d, indent=2, ensure_ascii=False))
    
    r2 = requests.get(
        f"{BV}/{app_id}/platforms",
        params={"access_token": USER_TOKEN},
        timeout=30,
    )
    d2 = r2.json()
    print(f"\n平台列表: {json.dumps(d2.get('data', []), indent=2, ensure_ascii=False)}")

print("\n=== 尝试获取 App Store 信息 ===")
r3 = requests.get(
    f"{BV}/{app_ids[0]}",
    params={
        "access_token": USER_TOKEN,
        "fields": "application_type,ios_bundle_id,android_package,stores",
    },
    timeout=30,
)
print(json.dumps(r3.json(), indent=2, ensure_ascii=False))
