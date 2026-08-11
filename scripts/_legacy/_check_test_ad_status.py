"""检查复制旧 Creative 创建的测试 Ad"""
import json, requests, time

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

test_ad_id = "120250205666610346"

print("等待 30 秒后检查测试 Ad 状态...")
time.sleep(30)

r = requests.get(
    f"{BV}/{test_ad_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,campaign{name,objective},adset{name,optimization_goal,promoted_object},creative{id,name,object_story_spec}",
    },
    timeout=30,
)
d = r.json()

campaign = d.get("campaign", {})
adset = d.get("adset", {})
creative = d.get("creative", {})

print(f"\n=== 测试 Ad 状态 ===")
print(f"名称: {d.get('name')}")
print(f"status: {d.get('status')}")
print(f"effective_status: {d.get('effective_status')}")
print(f"Campaign: {campaign.get('name')} - objective={campaign.get('objective')}")
print(f"Adset: {adset.get('name')} - optimization_goal={adset.get('optimization_goal')}")
print(f"promoted_object: {adset.get('promoted_object')}")
print(f"Creative: {creative.get('name')}")

print(f"\n=== 对比：之前失败的 Ad ===")
failed_ad_id = "120250205452470346"
r2 = requests.get(
    f"{BV}/{failed_ad_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,creative{id,name}",
    },
    timeout=30,
)
d2 = r2.json()
print(f"名称: {d2.get('name')}")
print(f"status: {d2.get('status')}")
print(f"effective_status: {d2.get('effective_status')}")
print(f"Creative: {d2.get('creative', {}).get('name')}")

print(f"\n=== 结论 ===")
if d.get("effective_status") == "PAUSED":
    print("✅ 复制旧 Creative 的 Ad 没有报错！")
    print("问题可能是：")
    print("1. 我们新上传的图片的 image_hash 有问题")
    print("2. 新 Creative 的 message 字段导致问题")
    print("3. 新账户需要特定的 Creative 格式")
else:
    print("❌ 复制的 Ad 也有问题")
