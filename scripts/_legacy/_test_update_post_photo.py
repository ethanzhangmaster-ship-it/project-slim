"""测试：更新 Page Post 的照片"""
import requests, json
from pathlib import Path

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
page_id = "103008755226035"
post_id = "103008755226035_1331719982426625"  # 第一张照片的 post_id

ROOT = Path(__file__).parent.parent
new_img = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070843/variant_02_00.png"

# 获取 Page Token
r = requests.get(f"{BV}/{page_id}", params={
    "access_token": USER_TOKEN, "fields": "access_token"
}, timeout=30)
page_token = r.json().get("access_token", "")
print(f"Page Token: {'✅' if page_token else '❌'}")

# 方式：上传新照片到同一个 post
print("\n上传新照片到 post...")
r2 = requests.post(
    f"{BV}/{post_id}/photos",
    data={
        "access_token": page_token,
        "caption": "Updated P04 Witch AI image",
    },
    files={"source": ("variant_02.png", open(new_img, "rb"), "image/png")},
    timeout=60,
)
print(f"结果: {json.dumps(r2.json(), ensure_ascii=False)[:400]}")