"""换个思路：找 Business 下已有的 System User Token，或用 Conversions API SU

System User 列表:
- 122136752109135012: test (ADMIN) — 有 Page + Ad Account 权限
- 122276914418159555: Conversions API System User (EMPLOYEE)
- 122257397984156382: Conversions API System User (EMPLOYEE)

如果无法通过 API 生成 token，就直接在 Business Manager UI 生成。
但在此之前，看看 System User 已经有 access_token 没。
"""
import json, os, sys, requests
from pathlib import Path

ROOT = Path(__file__).parent.parent

USER_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

biz_id = "156486836425764"
su_id = "122136752109135012"  # test ADMIN

print("=" * 60)
print("  方案: 用 Graph API Explorer 思路获取 SU Token")
print("=" * 60)

# 方案1: 查看 System User 的 access_tokens
print(f"\n[1] System User {su_id} 的 access tokens")
r1 = requests.get(f"{BV}/{su_id}/access_tokens", params={
    "access_token": USER_TOKEN,
})
print(f"  {r1.status_code}: {r1.text[:300]}")

# 方案2: 用 Business Manager 的 internal endpoint
# 不行，那是内部 API

# 方案3: 检查 Conversions API SU 有没有 token
print(f"\n[2] Conversions API SU tokens")
for csu_id in ["122276914418159555", "122257397984156382"]:
    r = requests.get(f"{BV}/{csu_id}/access_tokens", params={
        "access_token": USER_TOKEN,
    })
    tokens = r.json().get("data", [])
    print(f"  SU {csu_id}: {len(tokens)} tokens")
    for t in tokens:
        print(f"    id={t.get('id')} scopes={t.get('scopes',[])}")

# 方案4: 检查 test SU 的 assigned ad accounts 详情
print(f"\n[3] test SU 已分配的 Ad Accounts (详细)")
r3 = requests.get(f"{BV}/{su_id}/assigned_ad_accounts", params={
    "access_token": USER_TOKEN,
    "fields": "id,name,account_id,account_status,tasks",
})
accts = r3.json().get("data", [])
print(f"  总数: {len(accts)}")
for a in accts[:10]:
    print(f"    {a.get('account_id')}: {a.get('name','?')[:40]} tasks={a.get('tasks',[])}")

# 方案5: 看看 test SU 的 assigned pages
print(f"\n[4] test SU 已分配的 Pages (详细)")
r4 = requests.get(f"{BV}/{su_id}/assigned_pages", params={
    "access_token": USER_TOKEN,
    "fields": "id,name,tasks,category",
})
pages = r4.json().get("data", [])
print(f"  总数: {len(pages)}")
for p in pages[:10]:
    has_adv = "ADVERTISE" in p.get("tasks", [])
    print(f"    {p['id']}: {p.get('name','?')} ADVERTISE={has_adv}")

# 方案6: 直接用 SU 的 id + Business 生成 token
# 用 appsecret_proof (需要 app secret)
# 没有 app secret 的话试空的
print(f"\n[5] 尝试用 appsecret_proof='' 生成 SU Token")
import hashlib
import hmac

app_secret = ""  # 没有
# 实际上 appsecret_proof = hmac(app_secret, access_token, sha256).hexdigest()
# 没有 secret 就跳过

# 方案7: 检查当前 App 能不能加 appsecret_proof
# 当前 App ID 是 1470804601756335 (hgh0629)
# 这个 App 是开发模式，但 token 是它的
# 如果把 hgh0629 切到 Live 模式，用户 token 就能创建 creative 了

# 方案8: 检查能不能通过 /me/accounts 获取 page token
# Page Access Token 也能创建广告 (如果 page 有 ads 权限)
print(f"\n[6] 用用户 token 获取 Page Access Token")
r_pages = requests.get(f"{BV}/me/accounts", params={
    "access_token": USER_TOKEN,
    "fields": "id,name,access_token,category",
})
page_list = r_pages.json().get("data", [])
print(f"  可管理的 Page: {len(page_list)}")

# 用 Page Access Token 测试创建 creative
for p in page_list[:3]:
    page_token = p.get("access_token", "")
    page_id = p["id"]
    page_name = p.get("name", "?")
    if not page_token:
        continue
    
    print(f"\n  测试 Page Token: {page_name} ({page_id})")
    # 找一个 page 能访问的 ad account
    # 先看 page 的 adaccounts
    r_pa = requests.get(f"{BV}/{page_id}/adaccounts", params={
        "access_token": page_token,
        "fields": "id,name",
        "limit": 3
    })
    p_accts = r_pa.json().get("data", [])
    print(f"    Page 关联的 Ad Accounts: {len(p_accts)}")
    for a in p_accts:
        print(f"      {a['id']}: {a.get('name','?')[:30]}")

print(f"\n{'=' * 60}")
print(f"  最终方案")
print(f"{'=' * 60}")
print("""
最快的方案是：
  1. 把当前 App (hgh0629 / 1470804601756335) 切到 Live 模式
     位置: developers.facebook.com → App → Settings → Basic → App Mode
  2. 切完之后，用你给的新 Token (有 pages_manage_ads) 就能直接创建图片广告了

如果不想动 App:
  1. 到 Business Manager → System Users → test → Generate New Token
  2. 选择 Merge Witches App
  3. 选 ads_management + pages_manage_ads 权限
  4. 复制那个 System User Token 给我
""")