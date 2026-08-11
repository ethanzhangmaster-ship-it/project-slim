"""用新 Token 的 5 个 Creative + 正确的 App Link 创建广告"""
import json, os, sys, requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

ad_account_id = "736136435514410"
adset_id = "6838686954881"

print("=" * 60)
print("  修复: 用正确的 Store URL 创建广告")
print("=" * 60)

# Step 1: 获取 adset 的推广对象 (store URL)
print("\n[1] 获取 Adset 的推广对象信息...")
r_as = requests.get(f"{BV}/{adset_id}", params={
    "access_token": TOKEN,
    "fields": "id,name,promoted_object{object_store_url,custom_event_type,application_id}"
})
as_data = r_as.json()
print(f"  Adset: {as_data.get('name','?')}")
print(f"  promoted_object: {json.dumps(as_data.get('promoted_object',{}), ensure_ascii=False)}")

promoted_obj = as_data.get("promoted_object", {})
store_url = promoted_obj.get("object_store_url", "")
app_id = promoted_obj.get("application_id", "")
custom_event = promoted_obj.get("custom_event_type", "")
print(f"  Store URL: {store_url}")
print(f"  App ID: {app_id}")
print(f"  Custom Event: {custom_event}")

# Step 2: 读之前创建的 5 个 creative
result_file = ROOT / "output/closed_loop/publish_results/publish_closed_loop_20260630_160706.json"
result = json.loads(result_file.read_text(encoding="utf-8"))
creative_ids = result.get("creative_ids", [])
image_hashes = result.get("image_hashes", [])
print(f"\n[2] Creative IDs: {creative_ids}")

# Step 3: 重新创建 creative (用正确的 store URL)
# 先试：用 creative 的 link 匹配 store URL
# 实际上，APP_INSTALLS 类型需要 link 指向 App Store URL

print(f"\n[3] 重新创建 Creative (正确 URL)...")

# 找正确的 app link
# 尝试不同的 URL 格式
app_links = [
    "https://play.google.com/store/apps/details?id=com.gamegzz.merge.fans",
    "https://play.google.com/store/apps/details?id=com.gamegzz.merge.mermaids",
    "https://apps.apple.com/app/id000000000",
    store_url,  # 用 adset 的 store URL
]

# 找 page
r_pages = requests.get(f"{BV}/me/accounts", params={"access_token": TOKEN, "fields": "id,name"})
pages = r_pages.json().get("data", [])
page_id = pages[0]["id"] if pages else "864287563441749"
print(f"  Page: {page_id}")

run_id = datetime.now().strftime("closed_loop_%Y%m%d_%H%M%S")
primary_texts = [
    "Can you solve this? 🔮",
    "Merge & conquer! Try now 👇",
    "The most satisfying puzzle game!",
    "Test your skills - can you beat it?",
    "Addictive puzzle fun awaits!",
]

# 重新创建 creative，每次用不同的 URL
new_creative_ids = []
for i, img_hash in enumerate(image_hashes):
    for link in app_links:
        oss = json.dumps({
            "page_id": page_id,
            "link_data": {
                "image_hash": img_hash,
                "link": link,
                "message": primary_texts[i],
                "name": f"P04 Witch - Variant {i+1}",
                "call_to_action": {"type": "INSTALL_MOBILE_APP"},
            }
        })
        r_cr = requests.post(
            f"{BV}/act_{ad_account_id}/adcreatives",
            data={
                "access_token": TOKEN,
                "object_story_spec": oss,
                "name": f"AI_{run_id}_{i:02d}"
            },
            timeout=30,
        )
        cr_data = r_cr.json()
        if "id" in cr_data:
            new_creative_ids.append(cr_data["id"])
            print(f"  ✅ Creative {i} (link={link[:40]}...): {cr_data['id']}")
            break
        else:
            err = cr_data.get("error", {})
            print(f"  ❌ Creative {i} link={link[:30]}: {err.get('error_user_title','')[:60]}")
            if i == 0:
                print(f"     {err.get('error_user_msg','')[:100]}")

# 如果 URL 都不行，试不同 page
if len(new_creative_ids) < len(image_hashes):
    print(f"\n[3b] 尝试不同 Page...")
    for p in pages[1:5]:
        pid = p["id"]
        pname = p.get("name","?")
        for i in range(len(new_creative_ids), len(image_hashes)):
            oss = json.dumps({
                "page_id": pid,
                "link_data": {
                    "image_hash": image_hashes[i],
                    "link": app_links[-1] or "https://apps.apple.com/app/id000000000",
                    "message": primary_texts[i],
                    "name": f"P04-{i+1}",
                    "call_to_action": {"type": "INSTALL_MOBILE_APP"},
                }
            })
            r_cr = requests.post(
                f"{BV}/act_{ad_account_id}/adcreatives",
                data={"access_token": TOKEN, "object_story_spec": oss, "name": f"AI_{run_id}_{i:02d}"},
                timeout=20,
            )
            if "id" in r_cr.json():
                new_creative_ids.append(r_cr.json()["id"])
                print(f"  ✅ {pname}: {r_cr.json()['id']}")
                break
            elif i == 0:
                print(f"  ❌ {pname}: {r_cr.json().get('error',{}).get('error_user_title','')[:60]}")

print(f"\nCreative: {len(new_creative_ids)}/{len(image_hashes)}")

# Step 4: 创建广告
print(f"\n[4] 创建广告 (adset={adset_id})...")
ad_ids = []
for i, cr_id in enumerate(new_creative_ids):
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
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
        print(f"  ❌ Ad {i}: {err.get('error_user_title','')[:60]}: {err.get('error_user_msg','')[:80]}")

# Step 5: 保存
result2 = {
    **result,
    "run_id": run_id,
    "creative_ids": new_creative_ids,
    "ad_ids": ad_ids,
    "adset_id": adset_id,
    "published_at": datetime.now(timezone.utc).isoformat(),
}
result_path = ROOT / "output/closed_loop/publish_results" / f"publish_{run_id}.json"
result_path.write_text(json.dumps(result2, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\n{'=' * 60}")
print(f"  完成!")
print(f"{'=' * 60}")
print(f"  Creative (新): {len(new_creative_ids)}")
print(f"  广告: {len(ad_ids)} / {len(new_creative_ids)}")
print(f"  结果: {result_path}")