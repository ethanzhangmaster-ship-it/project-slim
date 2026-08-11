"""验证广告 Creative 和图片是否正确"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_ids = [
    "120250205081180346",
    "120250205083240346",
    "120250205085480346",
    "120250205089310346",
    "120250205092170346",
]

print("=== 验证广告 Creative ===")
for ad_id in ad_ids:
    r = requests.get(
        f"{BV}/{ad_id}",
        params={
            "access_token": USER_TOKEN,
            "fields": "id,name,creative{id,name,object_story_spec}",
        },
        timeout=30,
    )
    d = r.json()
    creative = d.get("creative", {})
    spec = creative.get("object_story_spec", {})
    link_data = spec.get("link_data", {})
    cta = link_data.get("call_to_action", {})
    
    print(f"\nAd {d.get('name')} ({ad_id}):")
    print(f"  Creative: {creative.get('name')} ({creative.get('id')})")
    print(f"  CTA: {cta.get('type')}")
    print(f"  image_hash: {link_data.get('image_hash', 'N/A')[:30]}...")
    print(f"  link: {link_data.get('link')}")
