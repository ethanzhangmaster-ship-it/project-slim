"""给 System User 分配 App + Ad Account + Page，然后生成 SU Token"""
import json, os, sys, requests
from pathlib import Path

ROOT = Path(__file__).parent.parent

USER_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

biz_id = "156486836425764"  # 海南星月湾
su_id = "122136752109135012"  # test (ADMIN)
merge_witches_app_id = "836792580521282"  # Merge Witches

print("=" * 60)
print("  给 System User 分配资产")
print("=" * 60)

# Step 1: 分配 App
print(f"\n[1] 分配 App {merge_witches_app_id} (Merge Witches)")
r1 = requests.post(
    f"{BV}/{biz_id}/assigned_user_roles",
    data={
        "access_token": USER_TOKEN,
        "user": su_id,
        "role": "ADMIN",
        "app": merge_witches_app_id,
    }
)
print(f"  {r1.status_code}: {r1.text[:200]}")

# Step 2: 分配 Page (Merge Witches)
page_id = "103008755226035"  # Merge Witches
print(f"\n[2] 分配 Page {page_id} (Merge Witches)")
r2 = requests.post(
    f"{BV}/{biz_id}/assigned_user_roles",
    data={
        "access_token": USER_TOKEN,
        "user": su_id,
        "role": "MANAGE_PAGE",
        "page": page_id,
    }
)
print(f"  {r2.status_code}: {r2.text[:200]}")

# Step 3: 找一个这个 Business 下的 ad account 并分配
print(f"\n[3] 找 Business {biz_id} 下的 Ad Account")
r3 = requests.get(f"{BV}/{biz_id}/client_ad_accounts", params={
    "access_token": USER_TOKEN,
    "fields": "id,name,account_status",
    "limit": 10
})
accts = r3.json().get("data", [])
print(f"  数量: {len(accts)}")
for a in accts[:5]:
    print(f"    {a['id']}: {a.get('name','?')[:40]} status={a.get('account_status','?')}")

target_acct = ""
if accts:
    # 选第一个活跃的
    for a in accts:
        if a.get("account_status") == 1:
            target_acct = a["id"].replace("act_", "")
            target_acct_name = a.get("name", "")
            break
    if not target_acct:
        target_acct = accts[0]["id"].replace("act_", "")
        target_acct_name = accts[0].get("name", "")
    print(f"  选择: {target_acct} ({target_acct_name})")

    # 分配 Ad Account
    print(f"\n[4] 分配 Ad Account {target_acct}")
    r4 = requests.post(
        f"{BV}/{biz_id}/assigned_user_roles",
        data={
            "access_token": USER_TOKEN,
            "user": su_id,
            "role": "ADMIN",
            "ad_account": f"act_{target_acct}",
        }
    )
    print(f"  {r4.status_code}: {r4.text[:200]}")

# Step 5: 生成 System User Token
print(f"\n[5] 生成 System User Token (App={merge_witches_app_id})")
r5 = requests.post(
    f"{BV}/{su_id}/access_tokens",
    data={
        "access_token": USER_TOKEN,
        "app_id": merge_witches_app_id,
        "scope": "ads_management,pages_manage_ads,pages_show_list,read_insights,public_profile",
    }
)
token_data = r5.json()
print(f"  {r5.status_code}")
if "access_token" in token_data:
    su_token = token_data["access_token"]
    print(f"  ✅ Token: {su_token[:60]}...")
    
    # Step 6: 验证
    print(f"\n[6] 验证 Token")
    r6 = requests.get(f"{BV}/debug_token", params={
        "input_token": su_token,
        "access_token": USER_TOKEN,
    })
    dbg = r6.json().get("data", {})
    print(f"  app_id: {dbg.get('app_id')}")
    print(f"  type: {dbg.get('type')}")
    print(f"  scopes: {dbg.get('scopes')}")
    print(f"  expires_at: {dbg.get('expires_at')} (0=永久)")
    
    # Step 7: 测试创建 creative
    if target_acct:
        print(f"\n[7] 测试创建 Creative (acct={target_acct}, page={page_id})")
        test_img = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070327/variant_01_00.png"
        
        # 上传图片
        r_up = requests.post(
            f"{BV}/act_{target_acct}/adimages",
            params={"access_token": su_token},
            files={"filename": (test_img.name, open(test_img, "rb"), "image/png")},
            timeout=60,
        )
        up_data = r_up.json()
        hashes = up_data.get("images", {})
        img_hash = list(hashes.values())[0].get("hash", "") if hashes else ""
        print(f"  上传: {img_hash[:20] if img_hash else 'FAILED'}")
        
        if img_hash:
            oss = json.dumps({
                "page_id": page_id,
                "link_data": {
                    "image_hash": img_hash,
                    "link": "https://play.google.com/store/apps/details?id=merge.witch.puzzle.game",
                    "message": "Can you solve this? 🔮",
                    "name": "Merge Witches - Puzzle Adventure",
                    "call_to_action": {"type": "INSTALL_MOBILE_APP"},
                }
            })
            r_cr = requests.post(
                f"{BV}/act_{target_acct}/adcreatives",
                data={"access_token": su_token, "object_story_spec": oss, "name": "Test-SU-Token"},
                timeout=30,
            )
            cr = r_cr.json()
            if "id" in cr:
                print(f"  ✅ Creative 成功! id={cr['id']}")
                requests.delete(f"{BV}/{cr['id']}", params={"access_token": su_token})
                
                # 保存 SU token 到 .env
                print(f"\n[8] 保存到 .env")
                env_path = ROOT / ".env"
                lines = env_path.read_text(encoding="utf-8").splitlines()
                new_lines = []
                keys_seen = set()
                for line in lines:
                    if "=" in line and not line.startswith("#"):
                        k = line.split("=", 1)[0].strip()
                        keys_seen.add(k)
                
                add_lines = [
                    f"META_SYSTEM_USER_TOKEN={su_token}",
                    f"META_SYSTEM_USER_APP_ID={merge_witches_app_id}",
                    f"META_SYSTEM_USER_AD_ACCOUNT={target_acct}",
                    f"META_SYSTEM_USER_PAGE_ID={page_id}",
                    f"META_SYSTEM_USER_APP_NAME=Merge Witches",
                ]
                for al in add_lines:
                    k = al.split("=", 1)[0]
                    if k in keys_seen:
                        # replace
                        for i, line in enumerate(new_lines if new_lines else lines):
                            if line.startswith(k + "="):
                                if new_lines:
                                    new_lines[i] = al
                                else:
                                    lines[i] = al
                                break
                    else:
                        lines.append(al)
                
                env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                print("  ✅ 已保存!")
                print(f"\n{'=' * 60}")
                print(f"  完美! SU Token 可创建真实图片广告")
                print(f"  App: Merge Witches (Live 模式)")
                print(f"  Page: Merge Witches")
                print(f"  Ad Account: {target_acct}")
                print(f"{'=' * 60}")
            else:
                err = cr.get("error", {})
                print(f"  ❌ {err.get('error_user_title', r_cr.status_code)}: {err.get('error_user_msg', err.get('message',''))[:120]}")
else:
    print(f"  失败: {token_data}")

print("\n" + "=" * 60)