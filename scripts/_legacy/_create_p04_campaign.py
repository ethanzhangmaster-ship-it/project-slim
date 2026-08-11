"""为 P04 Witch 创建专属 Campaign + Adset (在 P04 广告账户中)"""
import json, requests
from datetime import datetime, timezone

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"  # GAMEGZZ_Tec_Do_04_260115_AND_1 (用户指定 P04 账户)
app_id = "836792580521282"  # P04 Witch Android App
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"  # P04 Witch

run_id = datetime.now().strftime("%m%d")
start = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0800")

print("=" * 60)
print("  创建 P04 Witch 专属 Campaign")
print("=" * 60)

# Step 1: 创建 Campaign
print("\n[1] Campaign...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": TOKEN,
        "name": f"P04-AI-ClosedLoop-欧美-{run_id}",
        "objective": "OUTCOME_APP_PROMOTION",
        "status": "PAUSED",
        "is_adset_budget_sharing_enabled": True,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "special_ad_categories": json.dumps([]),
    },
    timeout=30,
)
camp_data = r_camp.json()
if "id" not in camp_data:
    print(f"  ❌ {camp_data.get('error',{}).get('error_user_msg','')}")
    print(f"  {camp_data}")
    import sys; sys.exit(1)

camp_id = camp_data["id"]
print(f"  ✅ Campaign: {camp_id} — {camp_data.get('name')}")

# Step 2: 创建 Adset
print("\n[2] Adset...")
r_as = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": TOKEN,
        "name": f"P04-AI-{run_id}-欧美-广泛",
        "campaign_id": camp_id,
        "status": "PAUSED",
        "optimization_goal": "APP_INSTALLS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,  # $20/day in cents
        "start_time": start,
        "targeting": json.dumps({
            "age_min": 25,
            "age_max": 65,
            "genders": [2],  # Female
            "geo_locations": {"countries": ["US", "GB", "DE", "FR", "AU", "CA"], "location_types": ["home", "recent"]},
            "user_os": ["Android"],
            "user_device": ["Android_Smartphone", "Android_Tablet"],
            "app_install_state": "not_installed",
            "targeting_automation": {"advantage_audience": 1},
        }),
        "promoted_object": json.dumps({
            "application_id": app_id,
            "object_store_url": store_url,
        }),
    },
    timeout=30,
)
as_data = r_as.json()
if "id" not in as_data:
    print(f"  ❌ {as_data.get('error',{}).get('error_user_msg','')}")
    import sys; sys.exit(1)

adset_id = as_data["id"]
print(f"  ✅ Adset: {adset_id} — {as_data.get('name')}")
print(f"  Daily Budget: $2,000")
print(f"  Goal: APP_INSTALLS")
print(f"  Targeting: US, GB, DE, FR, AU, CA")

# Step 3: 更新 .env
print("\n[3] 更新 .env...")
from pathlib import Path
ROOT = Path(__file__).parent.parent
lines = Path(ROOT / ".env").read_text(encoding="utf-8").splitlines()
new_lines = []
for line in lines:
    if line.startswith("META_ADSET_ID_APP_INSTALLS="):
        new_lines.append(f"META_ADSET_ID_APP_INSTALLS={adset_id}")
    elif line.startswith("META_CAMPAIGN_ID="):
        new_lines.append(f"META_CAMPAIGN_ID={camp_id}")
    else:
        new_lines.append(line)
if not any(l.startswith("META_CAMPAIGN_ID=") for l in new_lines):
    new_lines.append(f"META_CAMPAIGN_ID={camp_id}")
Path(ROOT / ".env").write_text("\n".join(new_lines) + "\n", encoding="utf-8")
print("  ✅ 已写入 .env")

# Step 4: 把之前创建的 5 个广告迁移到这个新 campaign
print("\n[4] 迁移已有广告到新 Campaign...")
result_file = ROOT / "output/closed_loop/publish_results/publish_closed_loop_20260630_161049.json"
result = json.loads(result_file.read_text(encoding="utf-8"))
old_ad_ids = result.get("ad_ids", [])
print(f"  已有广告: {len(old_ad_ids)} 个")

# Facebook API 无法直接修改 ad 的 adset，需要删除重建
# 但这 5 个广告已经在 PENDING_REVIEW 了，先不动

print(f"\n{'=' * 60}")
print(f"  P04 Witch 专属 Campaign 创建完成!")
print(f"{'=' * 60}")
print(f"  Campaign: {camp_id} (PAUSED)")
print(f"  Adset: {adset_id} (PAUSED)")
print(f"  预算: $20/天")
print(f"  地区: US, GB, DE, FR, AU, CA")
print(f"  目标: APP_INSTALLS")
print(f"  已有广告: {len(old_ad_ids)} 个在旧 campaign")
print(f"\n  下次跑闭环时，广告将创建在新 campaign 中!")