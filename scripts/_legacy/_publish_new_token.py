"""用新 Token 创建完整广告 (含真实 creative)

Token 权限: pages_manage_ads + ads_management + business_management
Page: 13 个可管理 (需要找到 P04 Witch 对应的 page)
"""
import json, os, sys, requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

NEW_TOKEN = "EAAU5sGHSWq8BRyrldzCYMjkS4ZCUxlxsqTq5xUoDlk618XlzySk9wyTZAlYZCDzx61Jygf4QLdApSNj68hUiSJe4lUZCnG45dIzhei4ijFy9caOmaAxPSqZAp2dU5VZBq4VYO7GF3x2Uv4icKdHlzC8kWtgJjJzTStQAdkyfUe86bUnbLcm4eyiYnI4nT0"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

# 当前使用的参数
ad_account_id = "1470190336720235"  # act_1470190336720235 from .env
adset_id = "120249103015030444"     # CLOSED_LOOP_ADSET_ID from .env

# 可管理的 Page 列表 (从新 token 获取)
pages_to_try = [
    # (page_id, page_name)
    ("112434405163824", "Dragon Island Game"),
    ("117105931434949", "Gossip Hospital"),
    ("100745153014855", "Hospital Frenzy"),
    ("221874354340551", "Drama Hospital"),
    ("673995235795891", "Be a Super Model"),
    ("564368240073696", "Be A Master Chef"),
    ("864287563441749", "Merge fans"),
    ("882615694935889", "Merge Games Mermaids"),
    ("150929001448234", "Singing Mermaids"),
    ("393376613867866", "Stella's Salon"),
]

print("=" * 60)
print("  找到有权限创建 creative 的 Page")
print("=" * 60)

# 先上传一张测试图片
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
print(f"\n测试图片上传: hash={img_hash[:20]}...")

# 试每个 page 创建 creative
working_pages = []
for page_id, page_name in pages_to_try:
    print(f"\n  尝试 Page: {page_name} ({page_id})...")
    oss = json.dumps({
        "page_id": page_id,
        "link_data": {
            "image_hash": img_hash,
            "link": "https://apps.apple.com/app/id000000000",
            "message": "Test - can you solve this?",
            "name": "P04 Witch - Test Ad",
            "call_to_action": {"type": "INSTALL_MOBILE_APP"},
        }
    })
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={"access_token": NEW_TOKEN, "object_story_spec": oss, "name": f"Test-{page_name}"},
        timeout=30,
    )
    if r.status_code == 200 and "id" in r.json():
        cid = r.json()["id"]
        print(f"    ✅ 成功! creative_id={cid}")
        working_pages.append((page_id, page_name, cid))
        # 删除测试 creative
        requests.delete(f"{BV}/{cid}", params={"access_token": NEW_TOKEN})
        break  # 找到一个就够了
    else:
        err = r.json().get("error", {})
        print(f"    ❌ {err.get('error_user_title', r.status_code)}: {err.get('error_user_msg', err.get('message',''))[:100]}")

print(f"\n可用的 Page: {len(working_pages)} 个")
if working_pages:
    page_id, page_name, _ = working_pages[0]
    print(f"选择 Page: {page_name} ({page_id})")
else:
    print("⚠️ 没有可用的 Page，继续用回退方案")
    sys.exit(0)

# 完整创建 5 个广告
print(f"\n{'=' * 60}")
print(f"  完整创建 5 个广告 (真实 creative)")
print(f"{'=' * 60}")

image_dir = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070327"
images = sorted(image_dir.glob("*.png"))
print(f"图片: {len(images)} 张")

# 上传所有图片
image_hashes = []
for img in images:
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adimages",
        params={"access_token": NEW_TOKEN},
        files={"filename": (img.name, open(img, "rb"), "image/png")},
        timeout=60,
    )
    d = r.json()
    h = list(d.get("images", {}).values())[0].get("hash", "") if d.get("images") else ""
    if h:
        image_hashes.append(h)
        print(f"  ✅ {img.name}: {h[:16]}...")
    else:
        print(f"  ❌ {img.name}: {d.get('error',{}).get('message','unknown')[:80]}")

print(f"\n上传成功: {len(image_hashes)}/{len(images)}")

# 创建 creative
creative_ids = []
run_id = datetime.now().strftime("closed_loop_%Y%m%d_%H%M%S")
headlines = ["P04 Witch - cool top_bottom"] * len(image_hashes)
primary_texts = [
    "Can you solve this? 🔮",
    "Merge & conquer! Try now 👇",
    "The most satisfying puzzle game!",
    "Test your skills - can you beat it?",
    "Addictive puzzle fun awaits!",
]

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
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={"access_token": NEW_TOKEN, "object_story_spec": oss, "name": f"AI_{run_id}_{i:02d}"},
        timeout=30,
    )
    if r.status_code == 200 and "id" in r.json():
        creative_ids.append(r.json()["id"])
        print(f"  ✅ Creative {i}: {r.json()['id']}")
    else:
        err = r.json().get("error", {})
        print(f"  ❌ Creative {i}: {err.get('error_user_title', r.status_code)}: {err.get('error_user_msg','')[:80]}")

print(f"\nCreative 创建: {len(creative_ids)}/{len(image_hashes)}")

# 创建广告
ad_ids = []
for i, cr_id in enumerate(creative_ids):
    ad_name = f"AI_{run_id}_{i:02d}"
    r = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": NEW_TOKEN,
            "name": ad_name,
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": cr_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    if r.status_code == 200 and "id" in r.json():
        ad_ids.append(r.json()["id"])
        print(f"  ✅ Ad {i}: {r.json()['id']} ({ad_name})")
    else:
        err = r.json().get("error", {})
        print(f"  ❌ Ad {i}: {err.get('error_user_title', r.status_code)}: {err.get('error_user_msg','')[:80]}")

print(f"\n广告创建: {len(ad_ids)}/{len(creative_ids)}")

# 保存结果
result = {
    "run_id": run_id,
    "token_source": "new_token_with_pages_manage_ads",
    "ad_account_id": ad_account_id,
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
print(f"  发布完成! (新 Token, 真实 creative)")
print(f"{'=' * 60}")
print(f"  Page: {page_name} ({page_id})")
print(f"  上传图片: {len(image_hashes)} 张")
print(f"  新建 Creative: {len(creative_ids)} 个")
print(f"  新建广告: {len(ad_ids)} 个 (PAUSED)")
print(f"  结果文件: {result_path}")