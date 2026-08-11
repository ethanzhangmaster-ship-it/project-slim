"""创建 5 个广告 (creative 已就绪)"""
import json, requests, time
from pathlib import Path
from datetime import datetime

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
campaign_id = "120249183478520444"
adset_id = "120249183479450444"

ROOT = Path(__file__).parent.parent

creative_ids = [
    "1314097907113137",  # variant 01
    "1587067892768302",  # variant 02
    "947793088272281",   # variant 03
    "1681224033160389",  # variant 04
    "1754147638934683",  # variant 05
]

print("创建广告...")
ad_ids = []
for i, cid in enumerate(creative_ids, 1):
    print(f"  Ad {i} (creative {cid})...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": USER_TOKEN,
            "name": f"P04-AI-New-{i:02d}",
            "status": "PAUSED",
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": cid}),
        },
        timeout=30,
    )
    d = r.json()
    if "id" in d:
        ad_ids.append(d["id"])
        print(f" ✅ {d['id']}")
    else:
        err = d.get("error", {})
        msg = err.get("error_user_msg") or err.get("message") or str(d)
        print(f" ❌ {msg[:80]}")
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"  完成! 共 {len(ad_ids)} 个广告")
print(f"{'='*60}")
for i, aid in enumerate(ad_ids, 1):
    print(f"  {i}. Ad: {aid}")

result = {
    "campaign_id": campaign_id,
    "adset_id": adset_id,
    "ad_ids": ad_ids,
    "creative_ids": creative_ids,
    "created_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
}
out = ROOT / f"output/closed_loop/publish_results/publish_p04_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n已保存: {out}")