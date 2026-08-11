"""查广告所属的 Campaign"""
import requests
TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

# 广告所属的 adset
adset_id = "6838677046281"
print(f"Adset {adset_id} 的信息:")
r = requests.get(f"{BV}/{adset_id}", params={
    "access_token": TOKEN,
    "fields": "id,name,campaign_id,status,optimization_goal,daily_budget"
})
d = r.json()
print(f"  Adset: {d.get('name')}")
print(f"  Campaign ID: {d.get('campaign_id')}")
print(f"  Status: {d.get('status')}")
print(f"  Goal: {d.get('optimization_goal')}")
print(f"  Daily Budget: {d.get('daily_budget')}")

camp_id = d.get("campaign_id", "")
if camp_id:
    print(f"\nCampaign {camp_id} 的信息:")
    r2 = requests.get(f"{BV}/{camp_id}", params={
        "access_token": TOKEN,
        "fields": "id,name,objective,status,daily_budget"
    })
    c = r2.json()
    print(f"  Name: {c.get('name')}")
    print(f"  Objective: {c.get('objective')}")
    print(f"  Status: {c.get('status')}")
    print(f"  Daily Budget: {c.get('daily_budget')}")

# 同时列出 ad account 下的所有 campaign
print(f"\nAd Account 736136435514410 下的所有 Campaign:")
r3 = requests.get(f"{BV}/act_736136435514410/campaigns", params={
    "access_token": TOKEN,
    "fields": "id,name,objective,status,daily_budget",
    "limit": 20
})
for c in r3.json().get("data", []):
    print(f"  {c['id']}: {c.get('name','?')[:50]} [{c.get('status','?')}] obj={c.get('objective','?')}")