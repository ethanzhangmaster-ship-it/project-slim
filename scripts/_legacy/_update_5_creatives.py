"""逐个更新 5 个 creative 的 image_hash"""
import requests, json, time
from pathlib import Path
from datetime import datetime

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ROOT = Path(__file__).parent.parent

creative_ids = [
    "36024357000496699",
    "35464582833188645",
    "28660063510260685",
    "28075417912047561",
    "34323136007300232",
]

new_image_hashes = [
    "f1af4b1c94c7a302c2a767f51a01ee2e",
    "58775d21d0cb2de8d2df52a808185527",
    "f5341e1a0f410cceca8ba8aaf3b4df30",
    "570fe0748e65006a00f917f3f4ff0ce6",
    "0c0493ba836a1ba624f591bfc087760e",
]

print("逐个更新 5 个 creative 的 image_hash...")
for i, (cid, h) in enumerate(zip(creative_ids, new_image_hashes), 1):
    print(f"  {i}. {cid} → {h[:16]}...", end=" ", flush=True)
    try:
        r = requests.post(
            f"{BV}/{cid}",
            data={
                "access_token": TOKEN,
                "name": f"P04-AI-Witch-{i:02d}",
                "image_hash": h,
            },
            timeout=30,
        )
        d = r.json()
        if d.get("success"):
            print("✅")
        else:
            err = d.get("error", {})
            msg = err.get("error_user_msg") or err.get("message") or str(d)
            print(f"❌ {msg[:60]}")
    except Exception as e:
        print(f"❌ {e}")
    time.sleep(1)

print("\n验证结果...")
for i, cid in enumerate(creative_ids, 1):
    r = requests.get(f"{BV}/{cid}", params={
        "access_token": TOKEN, "fields": "id,name,image_hash"
    }, timeout=30)
    d = r.json()
    print(f"  {i}. {d.get('name','?')[:40]} | hash={d.get('image_hash','?')[:16]}...")