"""通过 Business Manager API 给 System User 分配资产并生成 Token"""
import json, os, sys, requests
from pathlib import Path

ROOT = Path(__file__).parent.parent

USER_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

biz_id = "156486836425764"  # 海南星月湾
su_id = "122136752109135012"  # test (ADMIN)
app_id = "836792580521282"  # Merge Witches
page_id = "103008755226035"  # Merge Witches
ad_account_id = "736136435514410"  # GAMEGZZ_CMCM_项目07

print("=" * 60)
print("  Business Manager API: 分配资产 + 生成 SU Token")
print("=" * 60)

# 方法1: POST /{business_id}/system_users 直接创建带权限的
# 方法2: 用 /{system_user_id}/assigned_pages, /assigned_ad_accounts, etc.

# 先看现有 System User 有没有页面权限
print(f"\n[1] System User {su_id} 已有的 Pages")
r1 = requests.get(f"{BV}/{su_id}/assigned_pages", params={
    "access_token": USER_TOKEN,
})
print(f"  {r1.status_code}: {r1.text[:300]}")

print(f"\n[2] System User {su_id} 已有的 Ad Accounts")
r2 = requests.get(f"{BV}/{su_id}/assigned_ad_accounts", params={
    "access_token": USER_TOKEN,
})
print(f"  {r2.status_code}: {r2.text[:300]}")

print(f"\n[3] System User {su_id} 已有的 Apps")
r3 = requests.get(f"{BV}/{su_id}/assigned_apps", params={
    "access_token": USER_TOKEN,
})
print(f"  {r3.status_code}: {r3.text[:300]}")

# 分配 Page
print(f"\n[4] 分配 Page {page_id} 给 System User")
r4 = requests.post(
    f"{BV}/{su_id}/assigned_pages",
    data={
        "access_token": USER_TOKEN,
        "page_id": page_id,
        "business_permission": "MANAGE_PAGE",
    }
)
print(f"  {r4.status_code}: {r4.text[:200]}")

# 分配 Ad Account
print(f"\n[5] 分配 Ad Account {ad_account_id} 给 System User")
r5 = requests.post(
    f"{BV}/{su_id}/assigned_ad_accounts",
    data={
        "access_token": USER_TOKEN,
        "ad_account_id": f"act_{ad_account_id}",
        "business_permission": "ADMIN",
    }
)
print(f"  {r5.status_code}: {r5.text[:200]}")

# 生成 System User Token (需要 business_app 参数)
print(f"\n[6] 生成 System User Token (app={app_id})")
# 方式A: business_app
r6 = requests.post(
    f"{BV}/{su_id}/access_tokens",
    data={
        "access_token": USER_TOKEN,
        "business_app": app_id,
        "scope": "ads_management,pages_manage_ads,pages_show_list,read_insights,public_profile",
        "app_id": app_id,
    }
)
print(f"  方式A (business_app): {r6.status_code} {r6.text[:200]}")

# 方式B: 直接 app_id + app secret (没有 secret 不行)

# 方式C: 用 System User + App ID
if "access_token" not in r6.json():
    # 试另一种方式: 通过 /{app_id}/accounts?business=...
    print(f"\n[6b] 尝试生成 Token 的其他方式")
    
    # 检查这个 app 是不是这个 business 下的
    r_app = requests.get(f"{BV}/{app_id}", params={
        "access_token": USER_TOKEN,
        "fields": "id,name,owner_business"
    })
    print(f"  App owner: {r_app.text[:200]}")
    
    # 用 /{business_id}/system_users 创建新的 SU 并指定 app
    print(f"\n[6c] 创建新的 System User 并直接分配 App")
    new_su_name = f"project_slim_{int(__import__('time').time())}"
    r_new_su = requests.post(
        f"{BV}/{biz_id}/system_users",
        data={
            "access_token": USER_TOKEN,
            "name": new_su_name,
            "role": "ADMIN",
        }
    )
    print(f"  新建 SU: {r_new_su.status_code} {r_new_su.text[:200]}")
    new_su = r_new_su.json()
    new_su_id = new_su.get("id", "")
    
    if new_su_id:
        # 给新 SU 分配 Page
        requests.post(f"{BV}/{new_su_id}/assigned_pages", data={
            "access_token": USER_TOKEN,
            "page_id": page_id,
            "business_permission": "MANAGE_PAGE",
        })
        # 分配 Ad Account
        requests.post(f"{BV}/{new_su_id}/assigned_ad_accounts", data={
            "access_token": USER_TOKEN,
            "ad_account_id": f"act_{ad_account_id}",
            "business_permission": "ADMIN",
        })
        
        # 生成 token
        r_token = requests.post(
            f"{BV}/{new_su_id}/access_tokens",
            data={
                "access_token": USER_TOKEN,
                "app_id": app_id,
                "scope": "ads_management,pages_manage_ads,pages_show_list",
            }
        )
        print(f"  Token: {r_token.status_code} {r_token.text[:200]}")

print("\n" + "=" * 60)