"""检查 App 状态并找已发布的 App，或尝试把当前 App 切到 Live 模式"""
import json, os, sys, requests
from pathlib import Path

ROOT = Path(__file__).parent.parent

NEW_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"
CURRENT_APP_ID = "1470804601756335"

print("=" * 60)
print("  方案1: 找用户拥有的所有 App")
print("=" * 60)

# 检查用户拥有的所有应用
r = requests.get(f"{BV}/me/applications/developer", params={
    "access_token": NEW_TOKEN,
    "fields": "id,name,app_type,category,status",
    "limit": 50
})
apps = r.json().get("data", [])
print(f"用户作为开发者的 App: {len(apps)} 个")
for a in apps:
    print(f"  {a['id']}: {a.get('name','?')} type={a.get('app_type','?')} status={a.get('status','?')}")

print(f"\n当前 App {CURRENT_APP_ID} 详细信息:")
r2 = requests.get(f"{BV}/{CURRENT_APP_ID}", params={
    "access_token": NEW_TOKEN,
    "fields": "id,name,app_type,category,app_domains,contact_email"
})
print(f"  {r2.text[:300]}")

print("\n" + "=" * 60)
print("  方案2: 尝试切换到 Live 模式")
print("=" * 60)

# 尝试检查 App 的 mode
r3 = requests.get(f"{BV}/{CURRENT_APP_ID}", params={
    "access_token": NEW_TOKEN,
    "fields": "id,name,mode"
})
app_data = r3.json()
print(f"App mode: {app_data.get('mode', 'unknown')}")

# 尝试通过 API 把 App 设为 live (可能需要 app secret)
# 这个通常不行，需要在 developers.facebook.com 手动操作

print("""
诊断结论:
  当前 App (1470804601756335) 处于 DEVELOPMENT 模式
  即使 Token 有 pages_manage_ads 权限，也无法创建广告创意

解决方案 (按优先级):
  1. [最快] 登录 developers.facebook.com → App → App Review → 申请上线 (Live Mode)
     或者 Settings → Basic → App Mode 切换
  2. [备选] 用另一个已经在 Live 模式的 App 的 App ID + App Secret
  3. [已实现] 复用现有 creative_id 方案 (已通，5 个广告已创建)
""")

# 检查 Business Manager 下的 App
print("=" * 60)
print("  方案3: Business Manager 下的 App")
print("=" * 60)

biz_ids = ["349909759814468", "1505979070545357", "240087050306321", "156486836425764"]
for biz_id in biz_ids:
    r4 = requests.get(f"{BV}/{biz_id}/owned_apps", params={"access_token": NEW_TOKEN})
    owned = r4.json().get("data", [])
    if owned:
        print(f"\n  Business {biz_id} 拥有的 App:")
        for a in owned:
            print(f"    {a.get('id')}: {a.get('name','?')}")

    r5 = requests.get(f"{BV}/{biz_id}/client_apps", params={"access_token": NEW_TOKEN})
    client = r5.json().get("data", [])
    if client:
        print(f"\n  Business {biz_id} 管理的 App:")
        for a in client:
            print(f"    {a.get('id')}: {a.get('name','?')}")

print("\n" + "=" * 60)