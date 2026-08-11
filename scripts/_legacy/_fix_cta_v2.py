"""修复：重新上传图片并创建带 CTA 的广告"""
import json, requests, os

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
PAGE_TOKEN = "EAAI8u9NniuEBRyyoskEznZAngZAu986lUOxjIOW9luQ8s3WB54JTPg4NKUtpklGRSNZBNjjlogU05EWtIDFCbdmhGeuyPztdeGDwl59ZAw8dnp8GrrlZB93eV6WZC7qklPwaymQv6WaksGW4N1TIIsc4lovwPZCc45KebF5deeOZCBavZAZBmIvVVbMqAZAl2r5zp2vELcZD"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
page_id = "103008755226035"
adset_id = "120250205065330346"

manifest_path = "C:\\Users\\ethan\\Downloads\\project_slim\\output\\creative_growth_loop\\images\\closed_loop_20260630_070843\\manifest.json"

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

print("=== 上传图片并获取 image_hash ===")
image_hashes = []

for i, img_info in enumerate(manifest['images'], 1):
    img_path = img_info['file_path']
    if not os.path.exists(img_path):
        print(f"   ⚠️ 图片不存在: {img_path}")
        continue
    
    print(f"\n   --- 图片 {i}/5 ---")
    
    with open(img_path, 'rb') as img_file:
        r_upload = requests.post(
            f"{BV}/{page_id}/photos",
            data={
                "access_token": PAGE_TOKEN,
                "published": "false",
            },
            files={"source": img_file},
            timeout=60,
        )
    d_upload = r_upload.json()
    photo_id = d_upload.get("id", "")
    image_hash = d_upload.get("image_hash", "")
    
    if not photo_id:
        print(f"   ❌ 图片上传失败: {d_upload}")
        continue
    print(f"   ✅ 上传成功: photo_id={photo_id}")
    print(f"      image_hash={image_hash}")
    image_hashes.append(image_hash)

print(f"\n=== 创建带 CTA 的 Creative 并更新 Ad ===")
ad_ids = [
    "120250205081180346",
    "120250205083240346",
    "120250205085480346",
    "120250205089310346",
    "120250205092170346",
]

cta_options = ["INSTALL_MOBILE_APP", "DOWNLOAD", "PLAY_GAME", "USE_APP", "SHOP_NOW", "LEARN_MORE"]

updated_ads = []
for i, (ad_id, image_hash) in enumerate(zip(ad_ids, image_hashes), 1):
    print(f"\n   --- Ad {i}: {ad_id} ---")
    
    creative_id = None
    used_cta = None
    
    for cta_type in cta_options:
        r_cre = requests.post(
            f"{BV}/act_{ad_account_id}/adcreatives",
            data={
                "access_token": USER_TOKEN,
                "name": f"P04-AI-Creative-{cta_type}-{i}",
                "object_story_spec": json.dumps({
                    "page_id": page_id,
                    "link_data": {
                        "image_hash": image_hash,
                        "link": store_url,
                        "message": "Merge Witches - Play Now!",
                        "call_to_action": {
                            "type": cta_type,
                            "value": {"link": store_url}
                        },
                    },
                }),
            },
            timeout=30,
        )
        d_cre = r_cre.json()
        creative_id = d_cre.get("id", "")
        
        if creative_id:
            used_cta = cta_type
            break
        else:
            print(f"   ❌ CTA={cta_type} 失败: {d_cre.get('error', {}).get('message', '')[:80]}")
    
    if not creative_id:
        print(f"   ❌ 所有 CTA 类型都失败")
        continue
    
    print(f"   ✅ Creative: {creative_id} (CTA: {used_cta})")
    
    r_update = requests.post(
        f"{BV}/{ad_id}",
        data={
            "access_token": USER_TOKEN,
            "creative": json.dumps({"creative_id": creative_id}),
        },
        timeout=30,
    )
    d_update = r_update.json()
    
    if d_update.get("success") or "id" in d_update:
        print(f"   ✅ Ad 更新成功")
        updated_ads.append(ad_id)
    else:
        print(f"   ❌ Ad 更新失败: {d_update}")

print(f"\n=== 完成 ===")
print(f"上传图片: {len(image_hashes)}/{len(manifest['images'])}")
print(f"更新的 Ad: {len(updated_ads)}/{len(ad_ids)}")
