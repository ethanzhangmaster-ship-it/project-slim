"""生成 System User Token for Facebook Ads API.

在 Business Manager 中创建系统用户，赋予 Page + Ad Account 权限。
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
if (ROOT / ".env").exists():
    with open(ROOT / ".env") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip()

import requests

user_token = os.getenv("META_ACCESS_TOKEN", "")
ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
api_version = os.getenv("META_API_VERSION", "v19.0")
BV = f"https://graph.facebook.com/{api_version}"

biz_id = "349909759814468"  # 成都江边舟科技

print("=" * 60)
print("  创建 System User Token")
print("=" * 60)

# Step 1: 在 Business Manager 下创建 System User
print("\n[1] 创建 System User...")
r_create = requests.post(
    f"{BV}/{biz_id}/system_users",
    data={
        "access_token": user_token,
        "name": f"project_slim_api_{int(time.time())}",
        "role": "ADMIN",
        "requested_permissions": json.dumps(["ads_management", "pages_manage_ads", "pages_read_engagement"]),
    }
)
print(f"Create system user: {r_create.status_code} {r_create.text[:400]}")
su_data = r_create.json()
system_user_id = su_data.get("id", "")

if not system_user_id:
    # 尝试 GET existing system users
    r_list = requests.get(f"{BV}/{biz_id}/system_users", params={"access_token": user_token})
    existing = r_list.json().get("data", [])
    print(f"Existing system users: {existing}")
    for su in existing:
        if su.get("role") == "ADMIN":
            system_user_id = su.get("id", "")
            print(f"  Using existing admin: {system_user_id}")
            break

# Step 2: 赋予 Ad Account 权限
if system_user_id:
    print(f"\n[2] 赋予 Ad Account 权限 (user={system_user_id})...")
    # 先看当前的 ad accounts
    r_accts = requests.get(f"{BV}/{biz_id}/client_ad_accounts", params={"access_token": user_token})
    accts = r_accts.json().get("data", [])
    print(f"  Available ad accounts: {[a['id'] for a in accts]}")

    # 添加 ad account 权限
    for acct in accts:
        acct_id = acct.get("id", "").replace("act_", "")
        r_assign = requests.post(
            f"{BV}/{biz_id}/client_ad_accounts",
            data={
                "access_token": user_token,
                "user": system_user_id,
                "role": "ADMIN",
                "account_id": acct_id,
            }
        )
        print(f"  Assign {acct_id}: {r_assign.status_code}")

    # 赋予 Page 权限
    print("\n[3] 赋予 Page 权限...")
    pages = [
        "673995235795891",  # Be a Super Model
        "564368240073696",  # Be A Master Chef
        "393376613867866",  # Stella's Salon
        "221874354340551",  # Drama Hospital
        "117105931434949",  # Gossip Hospital
        "100745153014855",  # Hospital Frenzy
        "112434405163824",  # Dragon Island Game
        "150929001448234",  # Singing Mermaids
        "103008755226035",  # 现有广告用的 page
    ]
    for page_id in pages:
        r_assign_page = requests.post(
            f"{BV}/{biz_id}/client_pages",
            data={
                "access_token": user_token,
                "user": system_user_id,
                "role": "MANAGER",
                "page": page_id,
            }
        )
        print(f"  Assign page {page_id}: {r_assign_page.status_code}")

    # Step 3: 生成 System User Token
    print("\n[4] 生成 System User Token...")
    r_gen = requests.post(
        f"{BV}/{system_user_id}/tokens",
        data={
            "access_token": user_token,
            "app_id": "1470804601756335",
        }
    )
    print(f"Generate token: {r_gen.status_code} {r_gen.text[:400]}")
    su_token_data = r_gen.json()
    system_user_token = su_token_data.get("token", "")

    if system_user_token:
        print(f"\n✅ System User Token 生成成功!")
        print(f"Token: {system_user_token[:50]}...")

        # 验证
        r_verify = requests.get(f"{BV}/me", params={"access_token": system_user_token})
        print(f"Verify: {r_verify.status_code} {r_verify.text[:200]}")

        # 验证 pages
        r_pages = requests.get(f"{BV}/me/accounts", params={"access_token": system_user_token})
        print(f"Pages: {r_pages.status_code} {r_pages.text[:400]}")

        # 保存到 .env
        print("\n[5] 更新 .env...")
        env_path = ROOT / ".env"
        env_lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        found = False
        for line in env_lines:
            if line.startswith("META_SYSTEM_USER_TOKEN="):
                new_lines.append(f"META_SYSTEM_USER_TOKEN={system_user_token}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"META_SYSTEM_USER_TOKEN={system_user_token}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print("  已保存 META_SYSTEM_USER_TOKEN 到 .env")

        # 同时设置环境变量
        os.environ["META_SYSTEM_USER_TOKEN"] = system_user_token
    else:
        print(f"\n⚠️ Token 生成失败: {su_token_data}")
        print("需要手动到 Business Manager 创建 System User 并生成 token")

else:
    print("❌ System User 创建失败")

print("\n" + "=" * 60)