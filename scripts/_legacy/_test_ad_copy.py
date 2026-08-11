"""用 ad copies API 复制广告，然后改 creative"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

# 用一个现有的 APP_INSTALLS 广告复制
source_ad_id = "120249184799280444"  # P04-AI-Ad-03 (之前创建的，有图片)
new_adset_id = "120249183479450444"

# 方式 1: /ad_id/copies 复制广告
print("方式 1: 复制广告到新 adset...")
r = requests.post(
    f"{BV}/{source_ad_id}/copies",
    data={
        "access_token": TOKEN,
        "adset_id": new_adset_id,
        "status_option": "PAUSED",
    },
    timeout=30,
)
print(f"结果: {json.dumps(r.json(), ensure_ascii=False)[:500]}")

# 方式 2: /act_id/adcopies
if "copied_ad_id" not in r.json():
    print("\n方式 2: /act_id/adcopies...")
    r2 = requests.post(
        f"{BV}/act_{ad_account_id}/adcopies",
        data={
            "access_token": TOKEN,
            "ad_ids": json.dumps([source_ad_id]),
            "adset_id": new_adset_id,
            "status_type": "PAUSED",
        },
        timeout=30,
    )
    print(f"结果: {json.dumps(r2.json(), ensure_ascii=False)[:500]}")