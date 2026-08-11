"""更新广告成效目标为应用内购买（AEO）"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

adset_id = "120250206159850346"

print("=== 当前 Adset 配置 ===")
r = requests.get(
    f"{BV}/{adset_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "id,name,optimization_goal,promoted_object,bid_strategy,targeting",
    },
    timeout=30,
)
d = r.json()
print(json.dumps(d, indent=2, ensure_ascii=False))

print("\n" + "=" * 60)
print("更新为应用内购买 AEO 目标")
print("=" * 60)

r_update = requests.post(
    f"{BV}/{adset_id}",
    data={
        "access_token": USER_TOKEN,
        "optimization_goal": "APP_INSTALLS",
        "promoted_object": json.dumps({
            "application_id": "836792580521282",
            "object_store_url": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
            "custom_event_type": "PURCHASE",
            "action_type": "app_custom_event.fb_mobile_purchase",
        }),
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
    },
    timeout=30,
)
d_update = r_update.json()

if "id" in d_update or d_update.get("success"):
    print("✅ Adset 更新成功")
    
    r_check = requests.get(
        f"{BV}/{adset_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "id,name,optimization_goal,promoted_object",
        },
        timeout=30,
    )
    print("\n更新后配置:")
    print(json.dumps(r_check.json(), indent=2, ensure_ascii=False))
else:
    print(f"❌ 更新失败: {json.dumps(d_update, ensure_ascii=False)}")
