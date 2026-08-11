"""测试：通过 adimages API 上传时是否能创建 creative"""
import requests, json
from pathlib import Path

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

ROOT = Path(__file__).parent.parent
img_path = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070843/variant_05_00.png"

# 测试上传图片 + 同时创建 creative
print("测试上传图片同时创建 creative...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/adimages",
    data={
        "access_token": TOKEN,
        "filename": "p04_new_img.png",
        "create_creative": "true",
        "creative_name": "P04-Auto-Creative-Test",
    },
    files={"file": ("variant_05_00.png", open(img_path, "rb"), "image/png")},
    timeout=60,
)
print(f"结果: {json.dumps(r.json(), ensure_ascii=False, indent=2)[:500]}")

# 测试直接上传到 page 的照片
page_id = "103008755226035"
print("\n测试上传到 Page 相册...")
r2 = requests.post(
    f"{BV}/{page_id}/photos",
    data={
        "access_token": TOKEN,
        "caption": "P04 Witch AI image test",
        "published": "false",
    },
    files={"source": ("variant_05_00.png", open(img_path, "rb"), "image/png")},
    timeout=60,
)
print(f"结果: {json.dumps(r2.json(), ensure_ascii=False, indent=2)[:500]}")