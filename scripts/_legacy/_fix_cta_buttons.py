"""修复 Creative 添加 CTA 按钮"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
page_id = "103008755226035"
adset_id = "120250205065330346"

manifest_path = "C:\\Users\\ethan\\Downloads\\project_slim\\output\\creative_growth_loop\\images\\closed_loop_20260630_070843\\manifest.json"

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

print("=== 获取已上传图片的 image_hash ===")
PAGE_TOKEN = "EAAI8u9NniuEBRyyoskEznZAngZAu986lUOxjIOW9luQ8s3WB54JTPg4NKUtpklGRSNZBNjjlogU05EWtIDFCbdmhGeuyPztdeGDwl59ZAw8dnp8GrrlZB93eV6WZC7qklPwaymQv6WaksGW4N1TIIsc4lovwPZCc45KebF5deeOZCBavZAZBmIvVVbMqAZAl2r5zp2vELcZD"

r_photos = requests.get(
    f"{BV}/{page_id}/photos",
    params={
        "access_token": PAGE_TOKEN,
        "fields": "id,image_hash,name",
        "limit": 10,
    },
    timeout=30,
)
d_photos = r_photos.json()
photo_list = d_photos.get("data", [])
print(f"找到 {len(photo_list)} 张照片")

image_hashes = []
for p in photo_list:
    ih = p.get("image_hash", "")
    if ih and ih not in image_hashes:
        image_hashes.append(ih)
        print(f"  - {p['id']}: {ih}")

if len(image_hashes) < 5:
    print(f"\n⚠️  只找到 {len(image_hashes)} 张图片的 hash，可能需要重新上传")
else:
    image_hashes = image_hashes[:5]
    print(f"\n使用前 5 张图片的 hash")

print(f"\n=== 创建带 CTA 的新 Creative ===")
cta_types = [
    "INSTALL_MOBILE_APP",
    "USE_APP",
    "DOWNLOAD",
    "PLAY_GAME",
    "SHOP_NOW",
    "LEARN_MORE",
]

new_creative_ids = []
for i, image_hash in enumerate(image_hashes[:5], 1):
    print(f"\n   --- Creative {i}/5 ---")
    
    r_cre = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-Creative-CTA-{i}",
            "object_story_spec": json.dumps({
                "page_id": page_id,
                "link_data": {
                    "image_hash": image_hash,
                    "link": store_url,
                    "message": "Merge Witches - Play Now!",
                    "call_to_action": {
                        "type": "INSTALL_MOBILE_APP",
                        "value": {
                            "link": store_url,
                        }
                    },
                },
            }),
        },
        timeout=30,
    )
    d_cre = r_cre.json()
    creative_id = d_cre.get("id", "")
    
    if not creative_id:
        print(f"   ❌ Creative 创建失败: {d_cre}")
        print(f"   尝试其他 CTA 类型...")
        
        for cta_type in cta_types[1:]:
            r_cre2 = requests.post(
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
                                "value": {
                                    "link": store_url,
                                }
                            },
                        },
                    }),
                },
                timeout=30,
            )
            d_cre2 = r_cre2.json()
            creative_id = d_cre2.get("id", "")
            if creative_id:
                print(f"   ✅ 使用 CTA={cta_type} 成功: {creative_id}")
                break
            else:
                print(f"   ❌ CTA={cta_type} 也失败")
        
        if not creative_id:
            continue
    
    print(f"   ✅ Creative: {creative_id}")
    new_creative_ids.append(creative_id)

print(f"\n=== 更新现有 Ad 的 Creative ===")
ad_ids = [
    "120250205081180346",
    "120250205083240346",
    "120250205085480346",
    "120250205089310346",
    "120250205092170346",
]

updated_ads = []
for i, (ad_id, creative_id) in enumerate(zip(ad_ids[:len(new_creative_ids)], new_creative_ids), 1):
    print(f"\n   --- Ad {i}: {ad_id} ---")
    
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
        print(f"   ✅ 更新成功")
        updated_ads.append(ad_id)
    else:
        print(f"   ❌ 更新失败: {d_update}")

print(f"\n=== 完成 ===")
print(f"新 Creative: {len(new_creative_ids)}/{len(image_hashes)}")
print(f"更新的 Ad: {len(updated_ads)}/{len(ad_ids)}")
