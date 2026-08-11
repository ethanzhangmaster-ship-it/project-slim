"""正确上传图片获取 image_hash 并创建带 CTA 的广告"""
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

print("=== 方法 1: 用 adaccount/images 上传获取 hash ===")
image_hashes = []

for i, img_info in enumerate(manifest['images'], 1):
    img_path = img_info['file_path']
    if not os.path.exists(img_path):
        continue
    
    with open(img_path, 'rb') as img_file:
        r = requests.post(
            f"{BV}/act_{ad_account_id}/adimages",
            data={
                "access_token": USER_TOKEN,
                "filename": f"P04-v2-{i}.png",
            },
            files={"source": img_file},
            timeout=60,
        )
    d = r.json()
    print(f"  图片 {i}: {json.dumps(d, ensure_ascii=False)[:150]}")
    
    if d.get("images"):
        img_data = list(d["images"].values())[0]
        ih = img_data.get("hash", "")
        if ih:
            image_hashes.append(ih)
            print(f"    ✅ hash: {ih}")
            continue
    
    print(f"    ❌ 失败，尝试方法 2...")
    
    # 方法 2: 上传到 Page 后获取 photo detail
    with open(img_path, 'rb') as img_file:
        r2 = requests.post(
            f"{BV}/{page_id}/photos",
            data={
                "access_token": PAGE_TOKEN,
                "published": "false",
            },
            files={"source": img_file},
            timeout=60,
        )
    d2 = r2.json()
    photo_id = d2.get("id", "")
    
    if photo_id:
        # 获取 photo 详情找 hash
        r3 = requests.get(
            f"{BV}/{photo_id}",
            params={
                "access_token": PAGE_TOKEN,
                "fields": "id,images,image_hash,picture",
            },
            timeout=30,
        )
        d3 = r3.json()
        print(f"    photo 详情: {json.dumps(d3, ensure_ascii=False)[:200]}")
        
        # 从 images 中找
        images_list = d3.get("images", [])
        if images_list:
            image_hashes.append(f"photo:{photo_id}")
            print(f"    ✅ 用 photo_id 方式")

print(f"\n获取到 {len(image_hashes)} 个图片标识")
for i, ih in enumerate(image_hashes, 1):
    print(f"  {i}: {ih[:50]}")
