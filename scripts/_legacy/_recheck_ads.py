"""复查广告状态"""
import json, requests, time

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_ids = [
    "120250205212690346",
    "120250205213540346",
    "120250205213660346",
    "120250205213880346",
    "120250205214560346",
]

print("等待 40 秒后复查...")
time.sleep(40)
print()
print("=== 复查广告状态 ===")

all_ok = True
for ad_id in ad_ids:
    r = requests.get(
        f"{BV}/{ad_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "id,name,status,effective_status,issues_info,rejection_reasons",
        },
        timeout=30,
    )
    d = r.json()
    issues = d.get("issues_info", []) or []
    rejections = d.get("rejection_reasons", []) or []
    eff = d.get("effective_status", "")
    
    has_error = len(issues) > 0 or len(rejections) > 0 or eff in ["DISAPPROVED", "REJECTED"]
    
    status_icon = "✅" if not has_error else "❌"
    print(f"\n{status_icon} {d.get('name')} ({ad_id}):")
    print(f"     status: {d.get('status')}")
    print(f"     effective: {eff}")
    print(f"     issues: {len(issues)}")
    print(f"     rejections: {len(rejections)}")
    
    if issues:
        all_ok = False
        for issue in issues:
            print(f"       - {issue}")
    
    if rejections:
        all_ok = False
        for rej in rejections:
            print(f"       - {rej}")

print("\n" + "=" * 50)
print(f"最终结果: {'全部正常 ✅' if all_ok else '有问题 ❌'}")
print("=" * 50)
