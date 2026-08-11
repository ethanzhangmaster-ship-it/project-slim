"""在 AEO Adset 下创建广告"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"

adset_id = "120250206734390346"
creative_ids = [
    "976040602097480",
    "27780328138227323",
    "1532786678299248",
    "1724147125287070",
    "1586489853071219",
]

print("=== 在 AEO Adset 下创建广告 ===")

ad_ids = []
for i, creative_id in enumerate(creative_ids, 1):
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-AEO-Ad-{i}",
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    d_ad = r_ad.json()
    ad_id = d_ad.get("id", "")
    if ad_id:
        ad_ids.append(ad_id)
        print(f"  ✅ Ad {i}: {ad_id}")
    else:
        print(f"  ❌ Ad {i} 失败: {json.dumps(d_ad, ensure_ascii=False)}")

if ad_ids:
    print(f"\n等待 30 秒检查状态...")
    import time
    time.sleep(30)
    
    for ad_id in ad_ids:
        r_check = requests.get(
            f"{BV}/{ad_id}",
            params={"access_token": USER_TOKEN, "fields": "name,status,effective_status"},
            timeout=30,
        )
        d_check = r_check.json()
        print(f"\n{ad_id}: {d_check.get('name')}")
        print(f"  status: {d_check.get('status')}")
        print(f"  effective_status: {d_check.get('effective_status')}")
