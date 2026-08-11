"""Debug Facebook API: check permissions, app status, and find the right approach."""
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
page_id = os.getenv("CLOSED_LOOP_PAGE_ID", "")
api_version = os.getenv("META_API_VERSION", "v19.0")

BV = f"https://graph.facebook.com/{api_version}"

print("=" * 60)
print("  Facebook API 诊断")
print("=" * 60)

# 1. Token 有效性
print("\n[1] Token 有效性")
r = requests.get(f"{BV}/me", params={"access_token": token})
print(f"    /me: {r.status_code} {r.text[:200]}")

# 2. Token 的授权 scope
print("\n[2] Token 信息")
r2 = requests.get(f"{BV}/debug_token", params={
    "input_token": token,
    "access_token": token,
})
d2 = r2.json().get("data", {})
print(f"    expires_at: {d2.get('expires_at')}")
print(f"    scopes: {d2.get('scopes')}")
print(f"    app_id: {d2.get('app_id')}")
app_id = d2.get("app_id", "")

# 3. App 信息
print(f"\n[3] App {app_id} 信息")
r3 = requests.get(f"{BV}/{app_id}", params={
    "access_token": token,
    "fields": "id,name,app_domains,category,status"
})
print(f"    {r3.status_code} {r3.text[:300]}")

# 4. Ad Account 下的广告系列
print(f"\n[4] Ad Account {ad_account_id} 下的 Campaign")
r4 = requests.get(f"{BV}/act_{ad_account_id}/campaigns", params={
    "access_token": token,
    "fields": "id,name,objective,status",
    "limit": 5
})
print(f"    {r4.status_code} {r4.text[:400]}")
campaigns = r4.json().get("data", [])
if campaigns:
    campaign_id = campaigns[0]["id"]
    print(f"    第一个 campaign: {campaign_id} - {campaigns[0].get('name','')}")

# 5. Ad Account 下的 Adset
print(f"\n[5] Ad Account 下的 Adset")
r5 = requests.get(f"{BV}/act_{ad_account_id}/adsets", params={
    "access_token": token,
    "fields": "id,name,campaign_id,status,daily_budget",
    "limit": 5
})
print(f"    {r5.status_code} {r5.text[:400]}")
adsets = r5.json().get("data", [])
if adsets:
    adset_id = adsets[0]["id"]
    print(f"    第一个 adset: {adset_id} - {adsets[0].get('name','')}")
    print(f"    daily_budget: {adsets[0].get('daily_budget')}")

# 6. 现有广告
print(f"\n[6] Ad Account 下的 Ad (最新 3 条)")
r6 = requests.get(f"{BV}/act_{ad_account_id}/ads", params={
    "access_token": token,
    "fields": "id,name,creative{id,image_url},status",
    "limit": 3
})
print(f"    {r6.status_code} {r6.text[:500]}")
ads = r6.json().get("data", [])

# 7. Page 信息
print(f"\n[7] Page {page_id} 信息")
r7 = requests.get(f"{BV}/{page_id}", params={
    "access_token": token,
    "fields": "id,name,access_token,picture"
})
print(f"    {r7.status_code} {r7.text[:300]}")

# 8. 尝试直接用 URL 创建 creative (不用 page)
print("\n[8] 尝试不用 page_id 的 creative 创建方式")
# 先上传一张测试图片获取 hash
test_img = ROOT / "output" / "creative_growth_loop" / "images" / "closed_loop_20260630_070327" / "variant_01_00.png"
if test_img.exists():
    r8 = requests.post(f"{BV}/act_{ad_account_id}/adimages", params={"access_token": token},
                       files={"filename": (test_img.name, open(test_img, "rb"), "image/png")})
    img_data = r8.json()
    print(f"    upload: {r8.status_code} {img_data}")
    hashes = img_data.get("images", {})
    img_hash = list(hashes.values())[0].get("hash", "") if hashes else ""
    print(f"    image_hash: {img_hash}")

    if img_hash:
        # 方式A: 不用 page_id，image_url 方式
        print("\n    --- 方式A: image_url 方式 ---")
        creative_a = {
            "name": "Test Creative URL",
            "object_story_spec": json.dumps({
                "page_id": page_id,
                "link_data": {
                    "image_hash": img_hash,
                    "link": "https://apps.apple.com/app/id000000000",
                    "message": "Test message",
                    "name": "Test Ad",
                    "call_to_action": {"type": "OPEN_LINK"},
                }
            })
        }
        r_creative = requests.post(
            f"{BV}/act_{ad_account_id}/adcreatives",
            data={**creative_a, "access_token": token},
            timeout=30
        )
        print(f"    creative A: {r_creative.status_code} {r_creative.text[:300]}")

        # 方式B: 用其他 page_id
        print("\n    --- 方式B: 检查可用的 page ---")
        r_pages = requests.get(f"{BV}/me/accounts", params={"access_token": token})
        print(f"    /me/accounts: {r_pages.status_code} {r_pages.text[:300]}")

        # 方式C: 直接创建 ad (不需要 creative) — 现代 API
        print("\n    --- 方式C: 直接创建 ad (含 creative 字段) ---")
        if campaigns and adset_id:
            ad_data = {
                "name": f"Test Ad Direct {Path(__file__).stem}",
                "adset_id": adset_id,
                "creative": json.dumps({
                    "image_url": f"https://scontent-tpe1-1.xx.fbcdn.net/v/t45.1600-4/736207062_122279750090083055_4373220624505592869_n.png",
                    "link_url": "https://apps.apple.com/app/id000000000",
                    "message": "Test creative",
                    "name": "Test Ad",
                    "call_to_action": {"type": "INSTALL_MOBILE_APP"},
                }),
                "status": "PAUSED",
            }
            r_direct = requests.post(
                f"{BV}/act_{ad_account_id}/ads",
                data={**ad_data, "access_token": token},
                timeout=30
            )
            print(f"    direct ad: {r_direct.status_code} {r_direct.text[:300]}")

# 9. 检查 app 的 required features
print("\n[9] App permissions 需要哪些审核")
r9 = requests.get(f"{BV}/{app_id}/permissions", params={"access_token": token})
print(f"    {r9.status_code} {r9.text[:300]}")

print("\n" + "=" * 60)
print("  诊断完成")
print("=" * 60)