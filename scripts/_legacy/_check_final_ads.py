"""检查最终广告状态"""
import json, requests, time

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_ids = [
    "120250205959400346",
    "120250205959560346",
    "120250205959920346",
    "120250205960900346",
    "120250205961430346",
]

print("等待 40 秒后检查状态...")
time.sleep(40)

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
    status_icon = "✅" if not has_error else "❌"
    
    print(f"\n{status_icon} {d.get('name')}:")
    print(f"     status: {d.get('status')}")
    print(f"     effective_status: {eff}")
    
    if has_error:
        all_ok = False

print("\n" + "=" * 50)
print(f"最终结果: {'全部正常 ✅' if all_ok else '有问题 ❌'}")
print("=" * 50)
