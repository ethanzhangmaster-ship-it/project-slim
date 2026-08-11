"""验证新 Token 权限并用它创建广告"""
import json, os, sys, requests
from pathlib import Path
ROOT = Path(__file__).parent.parent

NEW_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

print("=" * 60)
print("  新 Token 权限诊断")
print("=" * 60)

# 1. Token 信息
print("\n[1] Token 信息")
r1 = requests.get(f"{BV}/debug_token", params={
    "input_token": NEW_TOKEN,
    "access_token": NEW_TOKEN,
})
d1 = r1.json().get("data", {})
print(f"  app_id: {d1.get('app_id')}")
print(f"  type: {d1.get('type')}")
print(f"  expires_at: {d1.get('expires_at')}")
print(f"  scopes: {d1.get('scopes')}")
app_id = d1.get("app_id", "")

# 2. 用户信息
print("\n[2] 用户信息")
r2 = requests.get(f"{BV}/me", params={"access_token": NEW_TOKEN})
print(f"  /me: {r2.text[:200]}")

# 3. 管理的 Page
print("\n[3] 管理的 Page")
r3 = requests.get(f"{BV}/me/accounts", params={"access_token": NEW_TOKEN, "fields": "id,name,access_token"})
pages = r3.json().get("data", [])
print(f"  数量: {len(pages)}")
for p in pages[:10]:
    has_token = bool(p.get("access_token"))
    print(f"    {p['id']}: {p.get('name','?')} (page_token={has_token})")

# 4. 广告账户
print("\n[4] 广告账户")
r4 = requests.get(f"{BV}/me/adaccounts", params={"access_token": NEW_TOKEN, "fields": "id,name,account_status"})
accts = r4.json().get("data", [])
print(f"  数量: {len(accts)}")
for a in accts[:10]:
    print(f"    {a['id']}: {a.get('name','?')} status={a.get('account_status','?')}")

# 5. Business Manager
print("\n[5] Business Manager")
r5 = requests.get(f"{BV}/me/businesses", params={"access_token": NEW_TOKEN})
biz = r5.json().get("data", [])
print(f"  数量: {len(biz)}")
for b in biz[:5]:
    print(f"    {b['id']}: {b.get('name','?')}")

# 6. App 状态
print(f"\n[6] App {app_id} 状态")
r6 = requests.get(f"{BV}/{app_id}", params={"access_token": NEW_TOKEN, "fields": "id,name,status,category"})
print(f"  {r6.text[:200]}")

print("\n" + "=" * 60)