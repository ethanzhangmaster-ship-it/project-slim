"""简化版：在新账户创建 adset 和广告"""
import json, requests, time
from pathlib import Path
from datetime import datetime

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
campaign_id = "120250204601790346"
page_id = "103008755226035"

ROOT = Path(__file__).parent.parent
run_id = datetime.now().strftime("%m%d%H%M")

store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

print("=" * 60)
print("  新账户 P04 Witch 广告创建 (简化版)")
print("=" * 60)

# Step 1: 创建 Adset (去掉 targeting，只用必需字段)
print("\n[Step 1] 创建 Adset...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": f"P04-AI-{run_id}-欧美-广泛",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "promoted_object": json.dumps({
            "application_id": "836792580521282",
            "object_store_url": store_url,
        }),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if adset_id:
    print(f"  ✅ Adset: {adset_id}")
else:
    print(f"  ❌ {d_aset}")
    exit(1)

print(f"\n✅ 完成! Campaign: {campaign_id}, Adset: {adset_id}")
print("广告创建待续...")