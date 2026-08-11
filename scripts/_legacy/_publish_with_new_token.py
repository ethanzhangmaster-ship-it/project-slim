"""验证新 Token 并创建真正的图片广告"""
import json, os, sys, requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

print("=" * 60)
print("  验证新 Token")
print("=" * 60)

r1 = requests.get(f"{BV}/debug_token", params={"input_token": TOKEN, "access_token": TOKEN})
d1 = r1.json().get("data", {})
print(f"app_id: {d1.get('app_id')}")
print(f"type: {d1.get('type')}")
print(f"scopes: {d1.get('scopes')}")

r2 = requests.get(f"{BV}/me", params={"access_token": TOKEN})
print(f"/me: {r2.text[:200]}")

# 可管理的 Page
r3 = requests.get(f"{BV}/me/accounts", params={"access_token": TOKEN, "fields": "id,name"})
pages = r3.json().get("data", [])
print(f"Pages: {len(pages)}")
for p in pages[:5]:
    print(f"  {p['id']}: {p.get('name','?')}")

# Ad Account
r4 = requests.get(f"{BV}/me/adaccounts", params={"access_token": TOKEN, "fields": "id,name,account_status"})
accts = r4.json().get("data", [])
active = [a for a in accts if a.get("account_status") == 1]
print(f"\n活跃 Ad Account: {len(active)} 个")
for a in active[:5]:
    print(f"  {a['id']}: {a.get('name','?')[:40]}")

# 找合适的 Page + Ad Account 组合
# 找一个 P04 Witch 相关的 ad account: GAMEGZZ_CMCM_04
p04_accts = [a for a in active if "CMCM_04" in a.get("name","") or "04" in a.get("name","")]
print(f"\nP04 相关账户: {len(p04_accts)}")
for a in p04_accts:
    print(f"  {a['id']}: {a.get('name','?')}")

# 选第一个活跃账户
if not active:
    print("❌ 没有活跃账户")
    sys.exit(1)

target_acct = active[0]["id"].replace("act_", "")
print(f"\n选择账户: {target_acct} ({active[0].get('name','')})")

# 找对应的 campaign/adset
print(f"\n{'=' * 60}")
print(f"  Step 2: 找 Campaign / Adset")
print(f"{'=' * 60}")

r_camp = requests.get(f"{BV}/act_{target_acct}/campaigns", params={
    "access_token": TOKEN,
    "fields": "id,name,objective,status",
    "limit": 5
})
camps = r_camp.json().get("data", [])
print(f"Campaigns: {len(camps)}")
for c in camps:
    print(f"  {c['id']}: {c.get('name','?')[:40]} [{c.get('status','?')}]")

# 找一个 active adset
adset_id = ""
for c in camps:
    if c.get("status") == "ACTIVE":
        r_as = requests.get(f"{BV}/{c['id']}/adsets", params={
            "access_token": TOKEN,
            "fields": "id,name,status",
            "limit": 3
        })
        for a in r_as.json().get("data", []):
            if a.get("status") == "ACTIVE":
                adset_id = a["id"]
                print(f"  Active Adset: {adset_id} ({a.get('name','?')})")
                break
    if adset_id:
        break

if not adset_id and camps:
    # 用第一个 adset
    r_as = requests.get(f"{BV}/{camps[0]['id']}/adsets", params={
        "access_token": TOKEN,
        "fields": "id,name,status",
        "limit": 1
    })
    adsets = r_as.json().get("data", [])
    if adsets:
        adset_id = adsets[0]["id"]
        print(f"  用第一个 Adset: {adset_id} ({adsets[0].get('name','?')})")

print(f"\n{'=' * 60}")
print(f"  Step 3: 测试创建 Creative (5 张图片)")
print(f"{'=' * 60}")

# 选择 Page
if pages:
    # 找一个和 P04 / Merge Witches 相关的 page
    merge_pages = [p for p in pages if "merge" in p.get("name","").lower() or "witch" in p.get("name","").lower()]
    if merge_pages:
        page_id = merge_pages[0]["id"]
        page_name = merge_pages[0]["name"]
    else:
        page_id = pages[0]["id"]
        page_name = pages[0]["name"]
    print(f"Page: {page_name} ({page_id})")
else:
    print("❌ 没有可管理的 Page")
    sys.exit(1)

# 上传 5 张图片
image_dir = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070327"
images = sorted(image_dir.glob("*.png"))
print(f"图片: {len(images)} 张")

image_hashes = []
for img in images:
    r_up = requests.post(
        f"{BV}/act_{target_acct}/adimages",
        params={"access_token": TOKEN},
        files={"filename": (img.name, open(img, "rb"), "image/png")},
        timeout=60,
    )
    d = r_up.json()
    h = list(d.get("images", {}).values())[0].get("hash", "") if d.get("images") else ""
    if h:
        image_hashes.append(h)
        print(f"  ✅ {img.name}: {h[:16]}...")
    else:
        print(f"  ❌ {img.name}: {d.get('error',{}).get('message','?')[:80]}")

if not image_hashes:
    print("❌ 图片上传全部失败")
    sys.exit(1)

print(f"\n上传成功: {len(image_hashes)}/{len(images)}")

# 创建 Creative
run_id = datetime.now().strftime("closed_loop_%Y%m%d_%H%M%S")
headlines = ["P04 Witch - Puzzle Adventure 🔮"] * len(image_hashes)
primary_texts = [
    "Can you solve this? 🔮",
    "Merge & conquer! Try now 👇",
    "The most satisfying puzzle game!",
    "Test your skills - can you beat it?",
    "Addictive puzzle fun awaits!",
]
creative_ids = []
for i, img_hash in enumerate(image_hashes):
    oss = json.dumps({
        "page_id": page_id,
        "link_data": {
            "image_hash": img_hash,
            "link": "https://apps.apple.com/app/id000000000",
            "message": primary_texts[i],
            "name": headlines[i],
            "call_to_action": {"type": "INSTALL_MOBILE_APP"},
        }
    })
    r_cr = requests.post(
        f"{BV}/act_{target_acct}/adcreatives",
        data={
            "access_token": TOKEN,
            "object_story_spec": oss,
            "name": f"AI_{run_id}_{i:02d}"
        },
        timeout=30,
    )
    cr_data = r_cr.json()
    if "id" in cr_data:
        creative_ids.append(cr_data["id"])
        print(f"  ✅ Creative {i}: {cr_data['id']}")
    else:
        err = cr_data.get("error", {})
        print(f"  ❌ Creative {i}: {err.get('error_user_title', r_cr.status_code)}: {err.get('error_user_msg', err.get('message',''))[:100]}")

print(f"\nCreative: {len(creative_ids)}/{len(image_hashes)}")

# 创建广告
print(f"\n{'=' * 60}")
print(f"  Step 4: 创建广告 (adset={adset_id})")
print(f"{'=' * 60}")

ad_ids = []
for i, cr_id in enumerate(creative_ids):
    r_ad = requests.post(
        f"{BV}/act_{target_acct}/ads",
        data={
            "access_token": TOKEN,
            "name": f"AI_{run_id}_{i:02d}",
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": cr_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    ad_data = r_ad.json()
    if "id" in ad_data:
        ad_ids.append(ad_data["id"])
        print(f"  ✅ Ad {i}: {ad_data['id']}")
    else:
        err = ad_data.get("error", {})
        print(f"  ❌ Ad {i}: {err.get('error_user_title', r_ad.status_code)}: {err.get('error_user_msg', err.get('message',''))[:100]}")

print(f"\n广告: {len(ad_ids)}/{len(creative_ids)}")

# 保存结果
result = {
    "run_id": run_id,
    "token_type": "user_token_new",
    "app_id": d1.get("app_id", ""),
    "ad_account_id": target_acct,
    "ad_account_name": active[0].get("name", ""),
    "adset_id": adset_id,
    "page_id": page_id,
    "page_name": page_name,
    "status": "PAUSED",
    "image_hashes": image_hashes,
    "creative_ids": creative_ids,
    "ad_ids": ad_ids,
    "published_at": datetime.now(timezone.utc).isoformat(),
}

result_path = ROOT / "output" / "closed_loop" / "publish_results" / f"publish_{run_id}.json"
result_path.parent.mkdir(parents=True, exist_ok=True)
result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\n{'=' * 60}")
print(f"  完成!")
print(f"{'=' * 60}")
print(f"  Token App: {d1.get('app_id')}")
print(f"  Page: {page_name}")
print(f"  Ad Account: {active[0].get('name')} ({target_acct})")
print(f"  Adset: {adset_id}")
print(f"  图片上传: {len(image_hashes)} 张")
print(f"  Creative: {len(creative_ids)} 个 (全新!)")
print(f"  广告: {len(ad_ids)} 个")
print(f"  状态: PAUSED")
print(f"  结果: {result_path}")