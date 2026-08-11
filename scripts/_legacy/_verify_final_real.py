"""验证最终广告"""
import json, requests
from pathlib import Path
ROOT = Path(__file__).parent.parent

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
api_version = "v19.0"
BV = f"https://graph.facebook.com/{api_version}"

result_file = ROOT / "output/closed_loop/publish_results/publish_closed_loop_20260630_161049.json"
result = json.loads(result_file.read_text(encoding="utf-8"))

ad_ids = result.get("ad_ids", [])
image_hashes = result.get("image_hashes", [])
creative_ids = result.get("creative_ids", [])

print("=" * 60)
print("  🎉 验证真正的 P04 Witch 图片广告")
print("=" * 60)

for i, ad_id in enumerate(ad_ids):
    r = requests.get(f"{BV}/{ad_id}", params={
        "access_token": TOKEN,
        "fields": "id,name,status,effective_status,creative{id,image_hash}"
    })
    d = r.json()
    cr = d.get("creative", {})
    img_hash = cr.get("image_hash", "")
    st = d.get("effective_status") or d.get("status", "?")
    our_hash = image_hashes[i] if i < len(image_hashes) else ""
    match = "✅" if img_hash == our_hash else "❌"
    print(f"\n  [{i+1}] {ad_id}")
    print(f"      名称: {d.get('name','')[:50]}")
    print(f"      状态: {st}")
    print(f"      Creative ID: {cr.get('id','')}")
    print(f"      Image Hash: {img_hash[:20]}...")
    print(f"      我们上传的: {our_hash[:20]}...")
    print(f"      图片匹配: {match}")

print(f"\n{'=' * 60}")
print(f"  总结")
print(f"{'=' * 60}")
print(f"  App Token: 629727356750561 (Be a Super Model)")
print(f"  Ad Account: GAMEGZZ_CMCM_项目07_20251126_AND_1")
print(f"  Adset: APP_INSTALLS (P7-And-Ins-欧美-广泛-测试素材-1128)")
print(f"  Page: Merge fans")
print(f"  图片: {len(image_hashes)} 张 (P04 Witch)")
print(f"  Creative: {len(creative_ids)} 个 (全新)")
print(f"  广告: {len(ad_ids)} 个 (PAUSED)")
print(f"  Store URL: {result.get('store_url','')}")
print(f"\n  Facebook 链接:")
for ad_id in ad_ids:
    print(f"    https://business.facebook.com/adsmanager/ads/?adservice=true&creative={ad_id}")