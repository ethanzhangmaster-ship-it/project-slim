import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"

# 5个新上传的图片完整hash
hashes = [
    "f1af4b1c94c7a302c2a767f51a01ee2e",
    "58775d21d0cb2de8d2df52a808185527",
    "f5341e1a0f410cceca8ba8aaf3b4df30",
    "570fe0748e65006a00f917f3f4ff0ce6",
    "0c0493ba836a1ba624f591bfc087760e",
]

print("创建 creatives (只带 image_hash，不带 object_store_url)...")
for i, h in enumerate(hashes, 1):
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adcreatives",
        data={
            "access_token": TOKEN,
            "name": f"P04-AI-Creative-New-{i:02d}",
            "status": "PAUSED",
            "image_hash": h,
        },
        timeout=30,
    )
    d = r.json()
    if "id" in d:
        print(f"  {i}. ✅ {d['id']}")
    else:
        print(f"  {i}. ❌ {d.get('error',{}).get('error_user_msg', d)[:80]}")
    import time; time.sleep(0.3)