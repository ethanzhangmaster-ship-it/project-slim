"""找新 Token 有权限的 ad account，然后完整创建广告"""
import json, os, sys, requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent

NEW_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

print("=" * 60)
print("  新 Token 可用的 Ad Account 列表")
print("=" * 60)

r = requests.get(f"{BV}/me/adaccounts", params={
    "access_token": NEW_TOKEN,
    "fields": "id,name,account_status,currency,timezone_name",
    "limit": 50
})
accts = r.json().get("data", [])
print(f"总数: {len(accts)}\n")

active_accts = [a for a in accts if a.get("account_status") == 1]
print(f"活跃账户: {len(active_accts)} 个")
for a in active_accts:
    aid = a["id"].replace("act_", "")
    print(f"  {aid}: {a.get('name','?')[:50]} ({a.get('currency','?')})")

# 选第一个活跃账户
if not active_accts:
    print("⚠️ 没有活跃账户")
    sys.exit(1)

target_acct = active_accts[0]
ad_account_id = target_acct["id"].replace("act_", "")
print(f"\n选择账户: {target_acct.get('name')} ({ad_account_id})")

# 找这个账户下的 campaign
print(f"\n{'=' * 60}")
print(f"  账户下的 Campaign")
print(f"{'=' * 60}")

r_c = requests.get(f"{BV}/act_{ad_account_id}/campaigns", params={
    "access_token": NEW_TOKEN,
    "fields": "id,name,objective,status,daily_budget",
    "limit": 5
})
camps = r_c.json().get("data", [])
for c in camps:
    print(f"  {c['id']}: {c.get('name','?')[:40]} [{c.get('status','?')}] obj={c.get('objective','?')}")

# 找一个 APP_INSTALLS 类型的 campaign 或 adset
app_install_camps = [c for c in camps if c.get("objective") == "APP_INSTALLS" and c.get("status") == "ACTIVE"]
if app_install_camps:
    print(f"\n找到 APP_INSTALLS campaign: {len(app_install_camps)} 个")
    target_camp = app_install_camps[0]
    # 找它的 adset
    r_as = requests.get(f"{BV}/{target_camp['id']}/adsets", params={
        "access_token": NEW_TOKEN,
        "fields": "id,name,status,daily_budget,optimization_goal",
        "limit": 3
    })
    adsets = r_as.json().get("data", [])
    for a in adsets:
        print(f"    Adset {a['id']}: {a.get('name','?')[:30]} [{a.get('status','?')}] budget={a.get('daily_budget','?')}")
else:
    print(f"\n⚠️ 没有 APP_INSTALLS campaign")
    if camps:
        target_camp = camps[0]
        r_as = requests.get(f"{BV}/{target_camp['id']}/adsets", params={
            "access_token": NEW_TOKEN,
            "fields": "id,name,status",
            "limit": 3
        })
        adsets = r_as.json().get("data", [])
        for a in adsets:
            print(f"    Adset {a['id']}: {a.get('name','?')[:30]} [{a.get('status','?')}]")

# 找 Page
print(f"\n{'=' * 60}")
print(f"  可用的 Page")
print(f"{'=' * 60}")

r_p = requests.get(f"{BV}/me/accounts", params={"access_token": NEW_TOKEN, "fields": "id,name,access_token"})
pages = r_p.json().get("data", [])
for p in pages[:10]:
    print(f"  {p['id']}: {p.get('name','?')}")

# 选 page 并创建测试 creative
target_page = pages[0]
page_id = target_page["id"]
page_name = target_page["name"]
print(f"\n选择 Page: {page_name} ({page_id})")

# 上传测试图片并创建 creative
print(f"\n{'=' * 60}")
print(f"  测试创建 Creative")
print(f"{'=' * 60}")

test_img = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070327/variant_01_00.png"
r_up = requests.post(
    f"{BV}/act_{ad_account_id}/adimages",
    params={"access_token": NEW_TOKEN},
    files={"filename": (test_img.name, open(test_img, "rb"), "image/png")},
    timeout=60,
)
img_data = r_up.json()
hashes = img_data.get("images", {})
img_hash = list(hashes.values())[0].get("hash", "") if hashes else ""
print(f"图片上传: {img_hash[:20] if img_hash else 'FAILED'}")

if not img_hash:
    print(f"上传失败: {img_data}")
    sys.exit(1)

# 测试创建 creative
oss = json.dumps({
    "page_id": page_id,
    "link_data": {
        "image_hash": img_hash,
        "link": "https://apps.apple.com/app/id000000000",
        "message": "Can you solve this? 🔮",
        "name": "P04 Witch - AI Generated",
        "call_to_action": {"type": "INSTALL_MOBILE_APP"},
    }
})
r_cr = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={"access_token": NEW_TOKEN, "object_story_spec": oss, "name": "Test Creative P04"},
    timeout=30,
)
cr_result = r_cr.json()
print(f"Creative: {r_cr.status_code} {cr_result.get('id', cr_result.get('error',{}).get('message','?')[:100])}")

if "id" not in cr_result:
    # 试所有 page 直到找到可用的
    print("\n逐个测试 Page...")
    for p in pages:
        pid = p["id"]
        pname = p.get("name", "?")
        oss2 = json.dumps({
            "page_id": pid,
            "link_data": {
                "image_hash": img_hash,
                "link": "https://apps.apple.com/app/id000000000",
                "message": "Test",
                "name": "Test",
                "call_to_action": {"type": "INSTALL_MOBILE_APP"},
            }
        })
        r2 = requests.post(
            f"{BV}/act_{ad_account_id}/adcreatives",
            data={"access_token": NEW_TOKEN, "object_story_spec": oss2, "name": f"Test-{pname[:10]}"},
            timeout=15,
        )
        if r2.status_code == 200 and "id" in r2.json():
            print(f"  ✅ {pname} ({pid}): creative_id={r2.json()['id']}")
            page_id = pid
            page_name = pname
            # 删除测试
            requests.delete(f"{BV}/{r2.json()['id']}", params={"access_token": NEW_TOKEN})
            break
        else:
            err = r2.json().get("error", {})
            print(f"  ❌ {pname} ({pid}): {err.get('error_user_title', r2.status_code)}")

print(f"\n最终选择: page={page_name} ({page_id}), ad_account={ad_account_id}")
print("=" * 60)