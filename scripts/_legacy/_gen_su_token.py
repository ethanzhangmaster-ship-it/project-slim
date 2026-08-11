"""用新 Token + 找到对应 ad account 的 Live App，创建真正的图片广告

关键:
- 新 Token 有 pages_manage_ads 权限 ✅
- 新 Token 能访问 44 个 ad account ✅
- Business Manager 下有 8 个 Live App ✅
- 需要: App Secret 或 System User Token 才能用 Live App 创建 creative

方案: 通过 Business System User 生成 System User Token (有 App 权限)
"""
import json, os, sys, requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent

USER_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

print("=" * 60)
print("  方案: System User + Live App = 真正的图片广告")
print("=" * 60)

# Step 1: 找一个有 App 权限的 System User
biz_id = "156486836425764"  # 海南星月湾 (有 Merge Witches App)
merge_witches_app_id = "836792580521282"

print(f"\n[1] Business {biz_id} 的 System User")
r_su = requests.get(f"{BV}/{biz_id}/system_users", params={"access_token": USER_TOKEN})
sus = r_su.json().get("data", [])
print(f"  System users: {len(sus)}")
for su in sus:
    print(f"    {su.get('id')}: {su.get('name','?')} role={su.get('role','?')}")

# Step 2: 找 System User 分配的 App
if sus:
    su_id = sus[0]["id"]
    print(f"\n[2] System User {su_id} 已分配的 App")
    r_assigned = requests.get(f"{BV}/{su_id}/assigned_apps", params={
        "access_token": USER_TOKEN,
        "fields": "id,name,permissions"
    })
    apps = r_assigned.json().get("data", [])
    print(f"  已分配 App: {len(apps)}")
    for a in apps:
        print(f"    {a.get('id')}: {a.get('name','?')} perms={a.get('permissions',[])}")
    
    # Step 3: 生成 System User Token
    if apps:
        app_id = apps[0]["id"]
        print(f"\n[3] 为 System User {su_id} 生成 App {app_id} 的 Token")
        r_token = requests.post(
            f"{BV}/{su_id}/access_tokens",
            data={
                "access_token": USER_TOKEN,
                "app_id": app_id,
                "scope": "ads_management,pages_manage_ads,pages_show_list,read_insights",
            }
        )
        token_data = r_token.json()
        print(f"  生成结果: {r_token.status_code}")
        if "access_token" in token_data:
            su_token = token_data["access_token"]
            print(f"  ✅ System User Token: {su_token[:50]}...")
            
            # Step 4: 验证这个 Token
            print(f"\n[4] 验证 System User Token")
            r_me = requests.get(f"{BV}/me", params={"access_token": su_token})
            print(f"  /me: {r_me.text[:200]}")
            
            r_dbg = requests.get(f"{BV}/debug_token", params={
                "input_token": su_token,
                "access_token": USER_TOKEN,
            })
            dbg = r_dbg.json().get("data", {})
            print(f"  scopes: {dbg.get('scopes')}")
            print(f"  app_id: {dbg.get('app_id')}")
            print(f"  type: {dbg.get('type')}")
            
            # Step 5: 用这个 Token 测试创建 creative
            # 先找这个 System User 能访问的 ad account
            print(f"\n[5] System User 能访问的 Ad Account")
            r_accts = requests.get(f"{BV}/me/adaccounts", params={
                "access_token": su_token,
                "fields": "id,name,account_status",
                "limit": 10
            })
            accts = r_accts.json().get("data", [])
            print(f"  数量: {len(accts)}")
            for a in accts[:5]:
                print(f"    {a['id']}: {a.get('name','?')[:40]}")
            
            if accts:
                target_acct = accts[0]["id"].replace("act_", "")
                
                # 找 page
                print(f"\n[6] System User 能访问的 Page")
                r_pages = requests.get(f"{BV}/me/accounts", params={
                    "access_token": su_token,
                    "fields": "id,name"
                })
                pages = r_pages.json().get("data", [])
                print(f"  数量: {len(pages)}")
                for p in pages[:5]:
                    print(f"    {p['id']}: {p.get('name','?')}")
                
                if pages:
                    page_id = pages[0]["id"]
                    page_name = pages[0]["name"]
                    
                    # 上传图片
                    print(f"\n[7] 上传测试图片到 ad account {target_acct}")
                    test_img = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070327/variant_01_00.png"
                    r_up = requests.post(
                        f"{BV}/act_{target_acct}/adimages",
                        params={"access_token": su_token},
                        files={"filename": (test_img.name, open(test_img, "rb"), "image/png")},
                        timeout=60,
                    )
                    up_data = r_up.json()
                    hashes = up_data.get("images", {})
                    img_hash = list(hashes.values())[0].get("hash", "") if hashes else ""
                    print(f"  image_hash: {img_hash[:20]}...")
                    
                    if img_hash:
                        # 测试创建 creative
                        print(f"\n[8] 测试创建 Creative (page={page_name})")
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
                            f"{BV}/act_{target_acct}/adcreatives",
                            data={"access_token": su_token, "object_story_spec": oss, "name": "Test-P04-Witch"},
                            timeout=30,
                        )
                        cr_result = r_cr.json()
                        if "id" in cr_result:
                            print(f"  ✅ Creative 创建成功! id={cr_result['id']}")
                            # 清理测试
                            requests.delete(f"{BV}/{cr_result['id']}", params={"access_token": su_token})
                            
                            # 保存 SU token 到 .env
                            print(f"\n[9] 保存 System User Token 到 .env")
                            env_path = ROOT / ".env"
                            lines = env_path.read_text(encoding="utf-8").splitlines()
                            new_lines = []
                            found = False
                            for line in lines:
                                if line.startswith("META_SYSTEM_USER_TOKEN="):
                                    new_lines.append(f"META_SYSTEM_USER_TOKEN={su_token}")
                                    found = True
                                elif line.startswith("META_AD_ACCOUNT_ID=") and "SYSTEM_USER" not in line:
                                    # 记录 system user 对应的 ad account
                                    new_lines.append(line)
                                else:
                                    new_lines.append(line)
                            if not found:
                                new_lines.append(f"META_SYSTEM_USER_TOKEN={su_token}")
                                new_lines.append(f"META_SYSTEM_USER_APP_ID={app_id}")
                                new_lines.append(f"META_SYSTEM_USER_AD_ACCOUNT={target_acct}")
                                new_lines.append(f"META_SYSTEM_USER_PAGE_ID={page_id}")
                            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                            print("  ✅ 已保存!")
                            
                            print(f"\n{'=' * 60}")
                            print(f"  成功! System User Token 可创建真实图片广告")
                            print(f"{'=' * 60}")
                        else:
                            err = cr_result.get("error", {})
                            print(f"  ❌ {err.get('error_user_title', r_cr.status_code)}: {err.get('error_user_msg', err.get('message',''))[:100]}")
        else:
            print(f"  生成失败: {token_data}")

print("\n" + "=" * 60)