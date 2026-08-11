"""找 APP_INSTALLS adset 或新建一个，然后创建广告"""
import json, os, requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

ad_account_id = "736136435514410"
app_id = "819548239469125"  # promoted_object 里的 app_id
store_url = "http://play.google.com/store/apps/details?id=com.lilijoy.monster"

print("=" * 60)
print("  找/创建 APP_INSTALLS Adset")
print("=" * 60)

# 扫描该 ad account 下所有 campaign 的 adsets
r_camps = requests.get(f"{BV}/act_{ad_account_id}/campaigns", params={
    "access_token": TOKEN,
    "fields": "id,name,objective,status",
    "limit": 20
})
camps = r_camps.json().get("data", [])
print(f"Campaigns: {len(camps)}")

app_install_campaigns = [c for c in camps if "APP" in (c.get("objective","") or "").upper()]
print(f"App 相关 Campaigns: {len(app_install_campaigns)}")
for c in app_install_campaigns:
    print(f"  {c['id']}: {c.get('name','?')[:40]} obj={c.get('objective','?')}")

# 找 APP_INSTALLS campaign 的 adset
target_campaign_id = ""
target_adset_id = ""
for camp in camps:
    cid = camp["id"]
    r_as = requests.get(f"{BV}/{cid}/adsets", params={
        "access_token": TOKEN,
        "fields": "id,name,status,optimization_goal,daily_budget,promoted_object{object_store_url,application_id}",
        "limit": 5
    })
    for a in r_as.json().get("data", []):
        po = a.get("promoted_object", {})
        opt_goal = a.get("optimization_goal", "")
        status = a.get("status", "")
        print(f"  Adset {a['id']}: {a.get('name','?')[:30]} [{status}] goal={opt_goal} app={po.get('application_id','')[:20]}")
        if opt_goal in ("APP_INSTALLS", "OFFSITE_CONVERSIONS") and status == "ACTIVE":
            if not target_adset_id:
                target_adset_id = a["id"]
                target_campaign_id = cid

print(f"\n目标 Adset: {target_adset_id} (campaign={target_campaign_id})")

# 如果没有 APP_INSTALLS adset，创建一个
if not target_adset_id:
    print(f"\n没有 APP_INSTALLS Adset，创建一个...")
    # 找一个 active campaign
    active_camps = [c for c in camps if c.get("status") == "ACTIVE"]
    if active_camps:
        camp_id = active_camps[0]["id"]
    else:
        camp_id = camps[0]["id"] if camps else ""
    
    if camp_id:
        # 获取 campaign 详细信息
        r_camp_det = requests.get(f"{BV}/{camp_id}", params={
            "access_token": TOKEN,
            "fields": "id,name,campaign_id,status,daily_budget,start_time"
        })
        camp_det = r_camp_det.json()
        print(f"  用 Campaign: {camp_id}")
        
        # 创建 adset
        r_new_as = requests.post(
            f"{BV}/act_{ad_account_id}/adsets",
            data={
                "access_token": TOKEN,
                "name": f"P04-AI-ClosedLoop-{datetime.now().strftime('%m%d')}",
                "campaign_id": camp_id,
                "status": "PAUSED",
                "optimization_goal": "APP_INSTALLS",
                "billing_event": "IMPRESSIONS",
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                "daily_budget": 1000,
                "start_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0800"),
                "targeting": json.dumps({
                    "device_platforms": ["mobile"],
                    "publisher_platforms": ["facebook", "instagram", "audience_network"],
                }),
                "promoted_object": json.dumps({
                    "application_id": app_id,
                    "object_store_url": store_url,
                }),
            },
            timeout=30,
        )
        as_data = r_new_as.json()
        if "id" in as_data:
            target_adset_id = as_data["id"]
            print(f"  ✅ 新建 Adset: {target_adset_id}")
        else:
            err = as_data.get("error", {})
            print(f"  ❌ 新建失败: {err.get('error_user_title','')}: {err.get('error_user_msg','')[:100]}")

print(f"\n使用 Adset: {target_adset_id}")

# 读 creative IDs
result_file = ROOT / "output/closed_loop/publish_results/publish_closed_loop_20260630_160827.json"
result = json.loads(result_file.read_text(encoding="utf-8"))
creative_ids = result.get("creative_ids", [])
print(f"Creative IDs: {creative_ids}")

if not target_adset_id or not creative_ids:
    print("❌ 缺少 adset 或 creative")
    sys.exit(1)

# 创建广告
print(f"\n{'=' * 60}")
print(f"  创建广告 (adset={target_adset_id})")
print(f"{'=' * 60}")

run_id = result.get("run_id", datetime.now().strftime("closed_loop_%Y%m%d_%H%M%S"))
ad_ids = []
for i, cr_id in enumerate(creative_ids):
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": TOKEN,
            "name": f"AI_{run_id}_{i:02d}",
            "adset_id": target_adset_id,
            "creative": json.dumps({"creative_id": cr_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    ad_data = r_ad.json()
    if "id" in ad_data:
        ad_ids.append(ad_data["id"])
        print(f"  ✅ Ad {i}: {ad_data['id']}")
    else:
        err = ad_data.get("error", {})
        print(f"  ❌ Ad {i}: {err.get('error_user_title','')[:60]}: {err.get('error_user_msg','')[:80]}")

# 保存
result["run_id"] = run_id
result["adset_id"] = target_adset_id
result["ad_ids"] = ad_ids
result["published_at"] = datetime.now(timezone.utc).isoformat()
result["mode"] = "real_creative_new_token"

result_path = ROOT / "output/closed_loop/publish_results" / f"publish_{run_id}.json"
result_path.parent.mkdir(parents=True, exist_ok=True)
result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\n{'=' * 60}")
print(f"  完成!")
print(f"{'=' * 60}")
print(f"  Creative: {len(creative_ids)} 个 (P04 Witch 图片)")
print(f"  广告: {len(ad_ids)} / {len(creative_ids)} 个")
print(f"  Adset: {target_adset_id}")
print(f"  状态: PAUSED")
print(f"  结果: {result_path}")