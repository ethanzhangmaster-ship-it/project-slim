"""完整重新创建 P04 广告：OUTCOME_TRAFFIC + LEARN_MORE CTA"""
import json, requests, os

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"
page_id = "103008755226035"

manifest_path = "C:\\Users\\ethan\\Downloads\\project_slim\\output\\creative_growth_loop\\images\\closed_loop_20260630_070843\\manifest.json"

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

print("=" * 60)
print("P04 Witch 广告完整创建流程（自检版）")
print("=" * 60)
print(f"账户: {ad_account_id}")
print(f"图片数量: {len(manifest['images'])}")
print(f"目标: OUTCOME_TRAFFIC + LINK_CLICKS")
print(f"CTA: LEARN_MORE (避免应用链接不兼容)")
print()

print("【步骤 1/5】创建 Campaign...")
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Traffic-Final-20260701",
        "objective": "OUTCOME_TRAFFIC",
        "status": "PAUSED",
        "is_adset_budget_sharing_enabled": True,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "special_ad_categories": json.dumps([]),
        "dsa_beneficiary": json.dumps({"name": "Merge Witches", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "Merge Witches", "category": "APP"}),
    },
    timeout=30,
)
d_camp = r_camp.json()
campaign_id = d_camp.get("id", "")
if not campaign_id:
    print(f"  ❌ 失败: {d_camp}")
    exit(1)
print(f"  ✅ Campaign: {campaign_id}")

print("\n【步骤 2/5】创建 Adset...")
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "P04-AI-Traffic-Adset-欧美-移动端",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US", "GB", "DE", "FR", "CA", "AU"]},
            "device_platforms": ["mobile"],
        }),
        "dsa_beneficiary": json.dumps({"name": "Merge Witches", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "Merge Witches", "category": "APP"}),
    },
    timeout=30,
)
d_aset = r_aset.json()
adset_id = d_aset.get("id", "")
if not adset_id:
    print(f"  ❌ 失败: {d_aset}")
    exit(1)
print(f"  ✅ Adset: {adset_id}")

print("\n【步骤 3/5】上传图片到广告账户图片库（获取正确的 image_hash）...")
image_hashes = []
for i, img_info in enumerate(manifest['images'], 1):
    img_path = img_info['file_path']
    if not os.path.exists(img_path):
        print(f"  ⚠️  图片 {i} 不存在: {img_path}")
        continue
    
    with open(img_path, 'rb') as img_file:
        r = requests.post(
            f"{BV}/act_{ad_account_id}/adimages",
            data={"access_token": USER_TOKEN, "filename": f"P04-final-{i}.png"},
            files={"source": img_file},
            timeout=60,
        )
    d = r.json()
    
    if d.get("images"):
        img_data = list(d["images"].values())[0]
        ih = img_data.get("hash", "")
        if ih:
            image_hashes.append(ih)
            print(f"  ✅ 图片 {i}: hash={ih}")
            continue
    
    print(f"  ❌ 图片 {i} 上传失败: {d}")

if len(image_hashes) < 5:
    print(f"\n  ⚠️  只上传成功 {len(image_hashes)} 张，继续用现有的")

print(f"\n【步骤 4/5】创建 Creatives（带 LEARN_MORE CTA）...")
creative_ids = []
for i, image_hash in enumerate(image_hashes, 1):
    cta_types = ["LEARN_MORE", "SHOP_NOW", "USE_APP", "DOWNLOAD"]
    creative_id = None
    used_cta = None
    
    for cta_type in cta_types:
        r_cre = requests.post(
            f"{BV}/act_{ad_account_id}/adcreatives",
            data={
                "access_token": USER_TOKEN,
                "name": f"P04-AI-Final-Creative-{i}",
                "object_story_spec": json.dumps({
                    "page_id": page_id,
                    "link_data": {
                        "image_hash": image_hash,
                        "link": store_url,
                        "message": "Merge Witches - Play the addictive merge puzzle game!",
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
    
    if creative_id:
        creative_ids.append(creative_id)
        print(f"  ✅ Creative {i}: {creative_id} (CTA: {used_cta})")
    else:
        print(f"  ❌ Creative {i} 创建失败")

if len(creative_ids) < len(image_hashes):
    print(f"\n  ⚠️  只创建了 {len(creative_ids)}/{len(image_hashes)} 个 Creative")

print(f"\n【步骤 5/5】创建 Ads...")
ad_ids = []
for i, creative_id in enumerate(creative_ids, 1):
    r_ad = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-Final-Ad-{i}",
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        },
        timeout=30,
    )
    d_ad = r_ad.json()
    ad_id = d_ad.get("id", "")
    if ad_id:
        ad_ids.append(ad_id)
        print(f"  ✅ Ad {i}: {ad_id}")
    else:
        print(f"  ❌ Ad {i} 创建失败: {d_ad}")

print("\n" + "=" * 60)
print("【自检阶段】验证每个广告的配置")
print("=" * 60)

all_ok = True
for i, ad_id in enumerate(ad_ids, 1):
    r = requests.get(
        f"{BV}/{ad_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "id,name,status,effective_status,creative{id,name,object_story_spec}",
        },
        timeout=30,
    )
    d = r.json()
    creative = d.get("creative", {})
    spec = creative.get("object_story_spec", {})
    link_data = spec.get("link_data", {})
    cta = link_data.get("call_to_action", {})
    
    print(f"\nAd {i}: {d.get('name')} ({ad_id})")
    print(f"  状态: {d.get('status')} / effective: {d.get('effective_status')}")
    print(f"  Creative: {creative.get('name')}")
    print(f"  CTA: {cta.get('type', '无')}")
    print(f"  链接: {link_data.get('link', '无')}")
    print(f"  图片hash: {link_data.get('image_hash', '无')[:20]}...")
    
    if not cta.get("type"):
        print(f"  ⚠️  缺少 CTA")
        all_ok = False
    if d.get("effective_status") == "DISAPPROVED":
        print(f"  ❌ 审核未通过")
        all_ok = False

print("\n" + "=" * 60)
print(f"【自检结果】{'全部通过 ✅' if all_ok else '有问题 ❌'}")
print("=" * 60)
print(f"Campaign: {campaign_id}")
print(f"Adset: {adset_id}")
print(f"图片: {len(image_hashes)}/5")
print(f"Creative: {len(creative_ids)}")
print(f"广告: {len(ad_ids)}")
if ad_ids:
    print(f"广告 IDs: {', '.join(ad_ids)}")
