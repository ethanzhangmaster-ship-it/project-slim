"""Deep debug: find workable creative, page token approach, and System User plan."""
import json
import os
import sys
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

token = os.getenv("META_ACCESS_TOKEN", "")
ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
api_version = os.getenv("META_API_VERSION", "v19.0")
BV = f"https://graph.facebook.com/{api_version}"

print("=" * 60)
print("  方案1: 找现有广告的 creative (复用 image_hash)")
print("=" * 60)

# 获取所有广告和它们的 creative
r_ads = requests.get(f"{BV}/act_{ad_account_id}/ads", params={
    "access_token": token,
    "fields": "id,name,creative{id,image_hash,image_url},status",
    "limit": 10
})
print(f"All ads: {r_ads.text[:1000]}")
ads = r_ads.json().get("data", [])

# 找 active 广告的 creative
active_creatives = {}
for ad in ads:
    if ad.get("status") == "ACTIVE" and ad.get("creative"):
        cr = ad["creative"]
        cr_id = cr.get("id", "")
        img_hash = cr.get("image_hash", "")
        if cr_id and img_hash:
            active_creatives[cr_id] = img_hash
            print(f"  Active creative: {cr_id}, hash={img_hash[:20]}")

# 找 Dragon Island Game 这个 page 的信息 (可能有 Page access token)
print("\n" + "=" * 60)
print("  方案2: 检查 Business 下 Page 的 Token")
print("=" * 60)

biz_id = "349909759814468"  # 成都江边舟科技
r_sys_users = requests.get(f"{BV}/{biz_id}/system_users", params={"access_token": token})
print(f"System users: {r_sys_users.status_code} {r_sys_users.text[:400]}")

# 找有 ads_management 权限的系统用户
for su in r_sys_users.json().get("data", []):
    su_id = su.get("id", "")
    su_name = su.get("name", "")
    print(f"\n  System user: {su_id} - {su_name}")

    # 找这个系统用户的 assigned business assets
    r_assigned = requests.get(f"{BV}/{biz_id}/business_users", params={"access_token": token})
    print(f"    business_users: {r_assigned.text[:200]}")

# 尝试获取 Gamegzz Tec_Do 相关广告账户的系统用户
# 找 business 关联的 ad accounts
r_accts = requests.get(f"{BV}/{biz_id}/client_ad_accounts", params={"access_token": token})
print(f"\nClient ad accounts: {r_accts.status_code} {r_accts.text[:400]}")

# 尝试通过 adaccount 找 page
# 检查 Tec_Do ad account 下的 pixel
print("\n" + "=" * 60)
print("  方案3: 尝试直接创建 ad (不需要 page_id)")
print("=" * 60)

if active_creatives:
    first_cr_id = list(active_creatives.keys())[0]
    first_hash = list(active_creatives.values())[0]
    print(f"Using creative_id={first_cr_id}, hash={first_hash[:20]}")

    # 用现有 creative_id 创建 ad
    r_new = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": token,
            "name": f"AI-ClosedLoop-复用创意-{Path(__file__).stem}",
            "adset_id": "120249161378170444",  # AI campaign adset
            "creative": json.dumps({"creative_id": first_cr_id}),
            "status": "PAUSED",
        },
        timeout=30
    )
    print(f"Create ad with existing creative: {r_new.status_code} {r_new.text[:400]}")

# 方案4: 通过 adsets 获取 page_id
print("\n" + "=" * 60)
print("  方案4: 通过广告查看 page 信息")
print("=" * 60)

if ads:
    first_ad_id = ads[0].get("id", "")
    if first_ad_id:
        r_detailed = requests.get(f"{BV}/{first_ad_id}", params={
            "access_token": token,
            "fields": "id,name,creative{id,object_story_spec,image_hash},adset{campaign_id,name}"
        })
        print(f"Ad detail: {r_detailed.text[:600]}")

# 方案5: 尝试其他 active campaign 的 adset
print("\n" + "=" * 60)
print("  方案5: 找到有真实 page_id 的 creative")
print("=" * 60)

for ad in ads[:5]:
    ad_id = ad.get("id", "")
    if ad_id:
        r_a = requests.get(f"{BV}/{ad_id}", params={
            "access_token": token,
            "fields": "id,name,creative{id,image_hash,object_story_spec}"
        })
        a_data = r_a.json()
        cr = a_data.get("creative", {})
        oss = cr.get("object_story_spec", {})
        page_id = ""
        if isinstance(oss, dict):
            page_id = oss.get("page_id", "")
        print(f"  Ad {ad_id}: page_id={page_id}, creative_id={cr.get('id','')}")

print("\n" + "=" * 60)
print("  结论 & 行动方案")
print("=" * 60)
print("""
核心问题:
  1. 用户 Token 没有 pages_manage_ads 权限 → 无法创建任何带 page_id 的 creative
  2. App 在开发模式 → 即使有 page 权限也无法用于 creative 创建
  3. /me/accounts 返回空 → 用户不直接管理任何 Page

立即可用的方案:
  ✅ 复用现有 creative_id 创建 ad (方案3) — 如果有 active creative
  ✅ 在 Business Manager 中创建 System User，赋予 ads + pages 权限，拿到 system token
  ✅ 通过 Business ID 找到有权限的系统用户 Token

推荐行动 (按顺序):
  1. [手动] 登录 Business Manager (成都江边舟科技) → System Users → 创建/找一个有
     "Ads Management" + "Pages" 权限的系统用户 → 复制其 token
  2. [手动] 将此 token 设为环境变量 META_SYSTEM_USER_TOKEN
  3. [代码] 使用 System User Token 创建 creative + ad
""")