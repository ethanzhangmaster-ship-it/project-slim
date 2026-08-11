"""检查修复后广告状态"""
import json, requests, time

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_ids = [
    "120250206163350346",
    "120250206163570346",
    "120250206163810346",
    "120250206164090346",
    "120250206164310346",
]

print("等待 30 秒...")
time.sleep(30)

all_ok = True
for ad_id in ad_ids:
    r = requests.get(
        f"{BV}/{ad_id}",
        params={"access_token": USER_TOKEN, "fields": "name,status,effective_status"},
        timeout=30,
    )
    d = r.json()
    eff = d.get("effective_status", "")
    has_error = eff == "WITH_ISSUES"
    print(f"\n{'✅' if not has_error else '❌'} {d.get('name')}:")
    print(f"     status: {d.get('status')}")
    print(f"     effective_status: {eff}")
    if has_error:
        all_ok = False

print("\n" + "=" * 50)
print(f"最终结果: {'全部正常 ✅' if all_ok else '有问题 ❌'}")
print("=" * 50)
