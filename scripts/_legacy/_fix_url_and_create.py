"""用 APP_INSTALLS adset + 正确的 promoted_object 创建广告"""
import json, os, requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

ad_account_id = "736136435514410"
# APP_INSTALLS adset
app_install_adset_id = "6838677046281"  # P7-And-Ins-欧美-广泛-测试素材-1128
offsite_adset_id = "6838686954881"      # P7-And-Purchase-欧美-广泛-测试素材-112
app_id = "819548239469125"
# 改成 https
store_url = "https://play.google.com/store/apps/details?id=com.lilijoy.monster"

print("=" * 60)
print("  诊断 adset promoted_object")
print("=" * 60)

for asid, asname in [(app_install_adset_id, "APP_INSTALLS"), (offsite_adset_id, "OFFSITE")]:
    r = requests.get(f"{BV}/{asid}", params={
        "access_token": TOKEN,
        "fields": "id,name,optimization_goal,status,promoted_object{object_store_url,application_id,custom_event_type}"
    })
    d = r.json()
    po = d.get("promoted_object", {})
    print(f"\n{asname} Adset {asid}:")
    print(f"  goal: {d.get('optimization_goal')}")
    print(f"  store_url: {po.get('object_store_url')}")
    print(f"  app_id: {po.get('application_id')}")
    print(f"  custom_event: {po.get('custom_event_type')}")

# 关键: creative 的 link URL 必须和 promoted_object.object_store_url 完全一致
# promoted_object.object_store_url = "http://play.google.com/..." (HTTP!)
# 试 HTTP URL
print(f"\n尝试 HTTP URL: http://play.google.com/...")

# Page
r_pages = requests.get(f"{BV}/me/accounts", params={"access_token": TOKEN, "fields": "id,name"})
page_id = r_pages.json().get("data", [{}])[0].get("id", "864287563441749")

# 读 image hashes
result_file = ROOT / "output/closed_loop/publish_results/publish_closed_loop_20260630_160706.json"
result = json.loads(result_file.read_text(encoding="utf-8"))
image_hashes = result.get("image_hashes", [])
print(f"Image hashes: {image_hashes}")

run_id = datetime.now().strftime("closed_loop_%Y%m%d_%H%M%S")
primary_texts = [
    "Can you solve this? 🔮",
    "Merge & conquer! Try now 👇",
    "The most satisfying puzzle game!",
    "Test your skills - can you beat it?",
    "Addictive puzzle fun awaits!",
]

# 试 HTTP URL vs HTTPS URL
for url_protocol in ["http://", "https://"]:
    store_url_test = store_url.replace("https://", url_protocol)
    print(f"\n{'=' * 60}")
    print(f"  测试: {url_protocol} (creative + ad in APP_INSTALLS adset)")
    print(f"{'=' * 60}")

    creative_ids = []
    for i, img_hash in enumerate(image_hashes):
        oss = json.dumps({
            "page_id": page_id,
            "link_data": {
                "image_hash": img_hash,
                "link": store_url_test,
                "message": primary_texts[i],
                "name": f"P04 Witch {i+1}",
                "call_to_action": {"type": "INSTALL_MOBILE_APP"},
            }
        })
        r_cr = requests.post(
            f"{BV}/act_{ad_account_id}/adcreatives",
            data={"access_token": TOKEN, "object_story_spec": oss, "name": f"AI_{run_id}_{i:02d}"},
            timeout=30,
        )
        cr_data = r_cr.json()
        if "id" in cr_data:
            creative_ids.append(cr_data["id"])
            print(f"  ✅ Creative {i}: {cr_data['id']}")
        else:
            err = cr_data.get("error", {})
            print(f"  ❌ Creative {i}: {err.get('error_user_title','')[:60]}: {err.get('error_user_msg','')[:80]}")
            break

    if len(creative_ids) < len(image_hashes):
        # 清理已创建的
        for cid in creative_ids:
            requests.delete(f"{BV}/{cid}", params={"access_token": TOKEN})
        continue

    # 创建广告 (用 APP_INSTALLS adset)
    ad_ids = []
    for i, cr_id in enumerate(creative_ids):
        r_ad = requests.post(
            f"{BV}/act_{ad_account_id}/ads",
            data={
                "access_token": TOKEN,
                "name": f"AI_{run_id}_{i:02d}",
                "adset_id": app_install_adset_id,
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

    if ad_ids:
        # 成功!
        result["run_id"] = run_id
        result["creative_ids"] = creative_ids
        result["ad_ids"] = ad_ids
        result["adset_id"] = app_install_adset_id
        result["store_url"] = store_url_test
        result["published_at"] = datetime.now(timezone.utc).isoformat()
        result["mode"] = "real_creative_new_token_app_installs"
        result_path = ROOT / "output/closed_loop/publish_results" / f"publish_{run_id}.json"
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"\n{'=' * 60}")
        print(f"  🎉 成功! 真正的 P04 Witch 图片广告")
        print(f"{'=' * 60}")
        print(f"  URL: {store_url_test}")
        print(f"  Creative: {len(creative_ids)} 个")
        print(f"  广告: {len(ad_ids)} 个")
        break