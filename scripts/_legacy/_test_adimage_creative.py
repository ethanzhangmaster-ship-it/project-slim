"""测试：上传图片时指定 object_store_url 来创建 app promotion creative"""
import requests, json
from pathlib import Path

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

ROOT = Path(__file__).parent.parent
img_path = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070843/variant_01_00.png"
store_url = "http://play.google.com/store/apps/details?id=com.wjoy.witch"

print("方式：adimages + object_store_url + title + body...")
r = requests.post(
    f"{BV}/act_{ad_account_id}/adimages",
    data={
        "access_token": TOKEN,
        "filename": "p04_test_app_ad.png",
        "object_store_url": store_url,
        "title": "Try It Now! 🎯🎯",
        "body": "Discover New Gameplay! Merge Witches & explore ✨",
    },
    files={"file": ("variant_01_test.png", open(img_path, "rb"), "image/png")},
    timeout=60,
)
print(f"结果: {json.dumps(r.json(), ensure_ascii=False, indent=2)[:800]}")