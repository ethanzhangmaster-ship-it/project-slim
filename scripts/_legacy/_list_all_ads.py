"""列出所有广告状态"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"

print("=== 账户下所有广告 ===")
r = requests.get(
    f"{BV}/act_{ad_account_id}/ads",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,campaign{name},adset{name}",
        "limit": 50,
    },
    timeout=30,
)
d = r.json()
ads = d.get("data", [])
print(f"总数: {len(ads)}")
for ad in ads:
    campaign_name = ad.get("campaign", {}).get("name", "N/A") if ad.get("campaign") else "N/A"
    adset_name = ad.get("adset", {}).get("name", "N/A") if ad.get("adset") else "N/A"
    print(f"  {ad.get('name')}: status={ad.get('status')}")
    print(f"    campaign={campaign_name}, adset={adset_name}")

print(f"\n=== 我们最新的 5 个广告 ===")
new_ad_ids = [
    "120250205212690346",
    "120250205213540346",
    "120250205213660346",
    "120250205213880346",
    "120250205214560346",
]
for ad_id in new_ad_ids:
    r2 = requests.get(
        f"{BV}/{ad_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "name,status",
        },
        timeout=30,
    )
    d2 = r2.json()
    print(f"  {ad_id}: {d2.get('name')}, status={d2.get('status')}")

print(f"\n=== 结论 ===")
print("如果 status = PAUSED，广告本身没有错误")
print("Facebook 后台的'投放错误'可能是其他原因，比如：")
print("1. 广告组或广告系列层级的问题")
print("2. 审核中的状态显示")
print("3. 需要手动开启后才会报具体错误")
