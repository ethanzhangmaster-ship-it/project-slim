"""用现有 creative 直接创建 P04 广告 (不需要新建 creative)"""
import json, requests, time
from datetime import datetime
from pathlib import Path

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1455525822955003"
campaign_id = "120249183478520444"
adset_id = "120249183479450444"

ROOT = Path(__file__).parent.parent

# 用这5个已有的 creative (来自之前上传的图片 hash)
creative_ids = [
    "36024357000496699",  # 使用已有的 creative 作为模板
    "35464582833188645",
    "28660063510260685",
    "28075417912047561",
    "34323136007300232",
]

print("创建 5 个广告 (复用已有 creative)...")
ad_ids = []
for i, cid in enumerate(creative_ids, 1):
    print(f"  Ad {i} (creative {cid[:8]}...)...", end="")
    r = requests.post(
        f"{BV}/act_{ad_account_id}/ads",
        data={
            "access_token": TOKEN,
            "name": f"P04-AI-Ad-{i:02d}",
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
        print(f" ❌ {d.get('error', {}).get('error_user_msg', d)}")
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"  广告创建完成! 共 {len(ad_ids)} 个")
print(f"{'='*60}")
for aid in ad_ids:
    print(f"    Ad ID: {aid}")

# 保存结果
result = {
    "campaign_id": campaign_id,
    "adset_id": adset_id,
    "ad_ids": ad_ids,
    "creative_ids": creative_ids,
    "created_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
}
out = ROOT / f"output/closed_loop/publish_results/publish_p04_witch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n结果已保存: {out}")