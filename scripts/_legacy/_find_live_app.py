"""找一个 Live 模式的 App，用它生成 token 来创建广告创意

已找到的 Live App:
  - 629727356750561: Be a Super Model
  - 238075515735854: Hospital Fever
  - 823925869110059: Gossip Hospital
  - 1568360654444512: Drama Hospital
  - 345226445029961: Singing Mermaids
  - 819548239469125: Merge Vampire
  - 3178897598866693: Merge Mermaids
  - 836792580521282: Merge Witches
"""
import json, os, sys, requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent

USER_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

ad_account_id = "1470190336720235"  # 旧 token 用的 ad account (有 P04 广告)

# 候选 Live App
live_apps = [
    ("836792580521282", "Merge Witches"),   # 最可能和 P04 Witch 相关
    ("819548239469125", "Merge Vampire"),
    ("3178897598866693", "Merge Mermaids"),
    ("629727356750561", "Be a Super Model"),
    ("238075515735854", "Hospital Fever"),
    ("823925869110059", "Gossip Hospital"),
    ("1568360654444512", "Drama Hospital"),
    ("345226445029961", "Singling Mermaids"),
]

print("=" * 60)
print("  检查 Live App + 生成 App Token")
print("=" * 60)

# 对每个 App 测试: 看它是否在 Live 模式
working_apps = []
for app_id, app_name in live_apps:
    print(f"\nApp: {app_name} ({app_id})")
    
    # 检查 App 状态
    r = requests.get(f"{BV}/{app_id}", params={
        "access_token": USER_TOKEN,
        "fields": "id,name,app_type"
    })
    app_info = r.json()
    print(f"  信息: {app_info}")
    
    # 尝试生成 App Access Token (如果有 app secret 的话需要)
    # 没有 app secret 的话，用用户 token + app scoped token 试试
    
    # 测试: 用这个 app 的身份创建 creative (通过 Business Manager)
    # 先看 app 和 ad account 的关联
    
    # 用 app 的 access token (如果能拿到)
    # 尝试 business 关联的 app token
    
    # 方案: 通过系统用户获取 app 权限
    # 先看 Business 下 app 的关系
    
    # 直接测试: 用用户 token + 这个 app 能不能创建 creative
    # 需要给这个 app 生成一个 token
    # 用 Graph API 的 access_token endpoint
    
    r2 = requests.get(f"{BV}/oauth/access_token", params={
        "client_id": app_id,
        "client_secret": "",  # 没有 secret，不行
        "grant_type": "client_credentials",
    })
    print(f"  App token (无 secret): {r2.status_code} {r2.text[:100]}")

print("""
结论: 没有 App Secret 无法生成 App Token。

需要的操作 (手动):
  1. 登录 Facebook Business Manager
  2. 选一个 Live 状态的 App (比如 Merge Witches 836792580521282)
  3. 设置 → Basic → 复制 App Secret
  4. 然后用 App ID + App Secret 生成 App Token

或者更简单:
  - 用现有广告里的 creative_id 复用 (已经通了)
  - 等 App Review 通过后，再用新 token 创建全新 creative
""")

# 另一个思路: 找现有广告的 creative 是用哪个 App 创建的
print("\n" + "=" * 60)
print("  检查现有广告的 creative 用的是哪个 App")
print("=" * 60)

r_ads = requests.get(f"{BV}/act_{ad_account_id}/ads", params={
    "access_token": USER_TOKEN,
    "fields": "id,name,creative{id,object_story_spec,image_hash}",
    "limit": 3
})
ads = r_ads.json().get("data", [])
for ad in ads:
    cr = ad.get("creative", {})
    print(f"\nAd {ad.get('id')}: {ad.get('name','?')[:40]}")
    print(f"  Creative ID: {cr.get('id','?')}")
    oss = cr.get("object_story_spec", {})
    if isinstance(oss, dict):
        print(f"  Page ID: {oss.get('page_id','?')}")
        video_data = oss.get("video_data", {})
        link_data = oss.get("link_data", {})
        if video_data:
            print(f"  Video data keys: {list(video_data.keys())}")
        if link_data:
            print(f"  Link data keys: {list(link_data.keys())}")

print("\n" + "=" * 60)

# 最终方案: 用 Merge Witches App (836792580521282) + Business System User
# 如果 System User 能访问这个 App 和 Ad Account
# 先检查 System User
print("\n  检查成都江边舟科技的 System User")
biz_id = "349909759814468"
r_su = requests.get(f"{BV}/{biz_id}/system_users", params={"access_token": USER_TOKEN})
sus = r_su.json().get("data", [])
print(f"  System users: {len(sus)}")
for su in sus:
    print(f"    {su.get('id')}: {su.get('name','?')} role={su.get('role','?')}")

# 看看 System User 有没有 assigned ads + apps 权限
if sus:
    su_id = sus[0].get("id", "")
    print(f"\n  System User {su_id} 的已分配资产:")
    r_assets = requests.get(f"{BV}/{su_id}/assigned_business_asset_groups", params={
        "access_token": USER_TOKEN
    })
    print(f"    资产组: {r_assets.status_code} {r_assets.text[:200]}")

print("\n" + "=" * 60)
print("  结论")
print("=" * 60)
print("""
当前状态:
  ✅ 用户 Token 有 pages_manage_ads + ads_management 权限
  ✅ Business Manager 下有 8 个 Live App
  ❌ 当前 App (hgh0629 / 1470804601756335) 是开发模式
  ❌ 没有 App Secret，无法生成 Live App 的 Token

最快可行路径:
  [1] 复用 creative_id (已通，5 个广告已发布) — 现在就能用
  [2] 手动到 developers.facebook.com 把 hgh0629 切到 Live 模式
      → 设置 → Basic → App Mode → 切换到 Live
  [3] 在 Business Manager 中创建 System User，分配 App + Ad Account 权限，
      生成 System User Token (永久有效)
""")