"""用 Page Token 上传照片，然后用 post_id 创建 creative"""
import requests, json
from pathlib import Path

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
page_id = "103008755226035"

ROOT = Path(__file__).parent.parent
img_path = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070843/variant_05_00.png"

# 获取 Page Token
r = requests.get(f"{BV}/{page_id}", params={
    "access_token": USER_TOKEN,
    "fields": "access_token"
}, timeout=30)
page_token = r.json().get("access_token", "")
print(f"Page Token: {'✅' if page_token else '❌'}")

# 用 Page Token 上传照片到 Page (已发布)
print("\n用 Page Token 上传照片...")
r2 = requests.post(
    f"{BV}/{page_id}/photos",
    data={
        "access_token": page_token,
        "caption": "P04 Witch AI image",
        "published": "true",
    },
    files={"source": ("variant_05_00.png", open(img_path, "rb"), "image/png")},
    timeout=60,
)
d2 = r2.json()
print(f"结果: {json.dumps(d2, ensure_ascii=False)[:300]}")

if "id" in d2:
    photo_id = d2["id"]
    print(f"Photo ID: {photo_id}")
    
    # 用 photo_id 创建 creative (object_story_id 方式)
    print("\n用 object_story_id 创建 creative...")
    r3 = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": USER_TOKEN,
            "name": "P04-Photo-Creative-Test",
            "status": "PAUSED",
            "object_story_id": photo_id,
            "object_store_url": "http://play.google.com/store/apps/details?id=com.wjoy.witch",
            "object_type": "SHARE",
        },
        timeout=30,
    )
    print(f"结果: {json.dumps(r3.json(), ensure_ascii=False)[:500]}")