import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_ids = ["120249184776120444", "120249184794000444", "120249184799280444", "120249184803470444", "120249184810030444"]

for ad_id in ad_ids:
    r = requests.get(f"{BV}/{ad_id}", params={
        "access_token": TOKEN,
        "fields": "id,name,status,campaign_id,adset_id,creative{id,name,image_hash}"
    }, timeout=30)
    d = r.json()
    print(f"Ad {ad_id}:")
    print(f"  name: {d.get('name')}")
    print(f"  status: {d.get('status')}")
    print(f"  campaign: {d.get('campaign_id')}")
    print(f"  adset: {d.get('adset_id')}")
    c = d.get('creative', {})
    print(f"  creative: {c.get('id')} - {c.get('name','')[:40]}")
    print(f"  image_hash: {c.get('image_hash','')}")
    print()