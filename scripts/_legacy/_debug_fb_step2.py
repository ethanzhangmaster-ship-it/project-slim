"""Deep dive: find usable page, existing AI creatives, and fix creative creation."""
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
print("  Step 1: 找可用的 Page")
print("=" * 60)

# 找 Business 下的所有资产
r_biz = requests.get(f"{BV}/me/businesses", params={"access_token": token})
biz_data = r_biz.json()
print(f"me/businesses: {r_biz.status_code} {json.dumps(biz_data, ensure_ascii=False)[:300]}")

biz_id = ""
for b in biz_data.get("data", []):
    biz_id = b.get("id", "")
    print(f"\n  Business: {biz_id} - {b.get('name','')}")

    # 找这个 business 下的 page
    r_pages = requests.get(f"{BV}/{biz_id}/owned_pages", params={"access_token": token})
    pages = r_pages.json().get("data", [])
    print(f"    owned_pages: {len(pages)}")
    for p in pages:
        print(f"      {p.get('id')} - {p.get('name')} - access_token={bool(p.get('access_token'))}")

    # 也检查 managed pages
    r_managed = requests.get(f"{BV}/{biz_id}/client_pages", params={"access_token": token})
    managed = r_managed.json().get("data", [])
    print(f"    client_pages: {len(managed)}")
    for p in managed:
        print(f"      {p.get('id')} - {p.get('name')} - access_token={bool(p.get('access_token'))}")

    if pages or managed:
        break

# 检查 AI campaign 的现有 creative
print("\n" + "=" * 60)
print("  Step 2: 检查现有 AI Campaign 的 creative")
print("=" * 60)

# AI campaign: 120249161152770444
ai_campaign_id = "120249161152770444"
r_ai_ads = requests.get(f"{BV}/{ai_campaign_id}/ads", params={
    "access_token": token,
    "fields": "id,name,creative{id,image_url,object_story_spec,thumbnail_url},status",
    "limit": 5
})
print(f"AI campaign ads: {r_ai_ads.status_code} {r_ai_ads.text[:600]}")
ai_ads = r_ai_ads.json().get("data", [])

# 找一个有效的 creative 来复用
if ai_ads:
    # 获取该 creative 的详细 image_hash
    for ad in ai_ads[:2]:
        cid = ad.get("creative", {}).get("id", "")
        if cid:
            r_c = requests.get(f"{BV}/{cid}", params={
                "access_token": token,
                "fields": "id,image_url,image_hash,thumbnail_url,object_story_spec"
            })
            print(f"\n  Creative {cid}: {r_c.text[:400]}")

# 获取 AI adset 的信息
print("\n" + "=" * 60)
print("  Step 3: 获取 AI campaign 完整结构")
print("=" * 60)
ai_adset_id = "120249161378170444"
r_ai_as = requests.get(f"{BV}/{ai_adset_id}", params={
    "access_token": token,
    "fields": "id,name,campaign_id,status,daily_budget,optimization_goal"
})
print(f"AI Adset: {r_ai_as.status_code} {r_ai_as.text}")

# 直接用 image_hash + adset_id + existing page creative 方式
# 先找 campaign 的 page
print("\n" + "=" * 60)
print("  Step 4: 尝试用现有 creative 的 image_hash 创建新广告")
print("=" * 60)

if ai_ads:
    # 复用 AI campaign 的 image_hash
    ad_ids = [a["id"] for a in ai_ads]
    r_insights = requests.get(f"{BV}/{ad_ids[0]}/insights", params={
        "access_token": token,
        "fields": "creative_id,spend,impressions"
    })
    print(f"Ad insights: {r_insights.text[:300]}")

    # 尝试直接 clone 现有 ad 的 creative
    if ad_ids:
        first_ad_creative_id = ai_ads[0].get("creative", {}).get("id", "")
        if first_ad_creative_id:
            # 直接用现有的 creative_id 创建新 ad (不需要新建 creative)
            print(f"\n直接复用 creative_id={first_ad_creative_id} 创建新 ad...")

            ad_create = {
                "name": f"AI-Closed-Loop-Test-{Path(__file__).stem}",
                "adset_id": ai_adset_id,  # 用 AI adset
                "creative": json.dumps({"creative_id": first_ad_creative_id}),
                "status": "PAUSED",
            }
            r_new_ad = requests.post(
                f"{BV}/act_{ad_account_id}/ads",
                data={**ad_create, "access_token": token},
                timeout=30
            )
            print(f"New ad (clone creative): {r_new_ad.status_code} {r_new_ad.text[:300]}")

# 检查 campaign 下的所有 adsets
print("\n" + "=" * 60)
print("  Step 5: Campaign 下所有 Adset")
print("=" * 60)
r_adsets = requests.get(f"{BV}/{ai_campaign_id}/adsets", params={
    "access_token": token,
    "fields": "id,name,status,daily_budget,optimization_goal",
    "limit": 10
})
print(f"All adsets: {r_adsets.status_code} {r_adsets.text[:600]}")

# 方案：用 image_upload_hash + adset_id + 直接用现有 page
# 关键问题是 page 权限
print("\n" + "=" * 60)
print("  Step 6: 解决方案")
print("=" * 60)
print("""
诊断结果:
1. Token 有效 (Oliver Lin) 但缺少 pages_read_engagement / pages_manage_ads 权限
2. App 1470804601756335 处于开发模式，无法创建带 page_id 的 creative
3. AI Campaign (P4-AND-Purchase-AI-0630) 已存在，有 adset daily_budget=5000

解决方案 (按优先级):
[A] 用 System User Token 替代个人 Token (在 Business Manager 中创建)
[B] 在 Business Manager 中创建一个系统用户并赋予 Page + Ad account 权限
[C] 提交 App 审核获取 pages_manage_ads 权限
[D] 用现有的 creative_id 直接创建 ad (不需要新建 creative)

方案 D 已尝试 (上面)。如果失败，需要方案 A/B。
""")

# 验证: 如果 page token 可用，可以用 image_hash 直接创建
print("\n检查是否有 Page Token...")
r_ig = requests.get(f"{BV}/me/accounts", params={"access_token": token})
print(f"me/accounts: {r_ig.status_code} {r_ig.text[:300]}")