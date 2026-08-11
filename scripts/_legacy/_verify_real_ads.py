"""验证新创建的 5 个广告"""
import json, requests, os
from pathlib import Path
ROOT = Path(__file__).parent.parent

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

# 找最新的结果文件
result_dir = ROOT / "output/closed_loop/publish_results"
files = sorted(result_dir.glob("publish_closed_loop_20260630_160827.json"))
result_file = files[0]
result = json.loads(result_file.read_text(encoding="utf-8"))

ad_ids = result.get("ad_ids", [])
print(f"验证 {len(ad_ids)} 个广告...")

for i, ad_id in enumerate(ad_ids):
    r = requests.get(f"{BV}/{ad_id}", params={
        "access_token": TOKEN,
        "fields": "id,name,status,effective_status,creative{id,image_hash}"
    })
    if r.status_code == 200:
        d = r.json()
        cr = d.get("creative", {})
        img_hash = cr.get("image_hash", "")
        st = d.get("effective_status") or d.get("status", "?")
        print(f"  {i+1}. {ad_id}: status={st}, name={d.get('name','?')[:40]}")
        print(f"     image_hash={img_hash[:20] if img_hash else 'N/A'}...")
        # 验证 image hash 匹配
        our_hashes = result.get("image_hashes", [])
        if i < len(our_hashes):
            match = img_hash == our_hashes[i]
            print(f"     图片匹配: {'✅' if match else '⚠️'}")
    else:
        print(f"  {i+1}. {ad_id}: {r.status_code} {r.text[:100]}")

print(f"\n广告链接:")
for ad_id in ad_ids:
    print(f"  https://business.facebook.com/adsmanager/ads/?adservice=true&creative={ad_id}")