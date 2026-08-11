import os, json, requests
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.environ.get('FB_TOKEN', '') or os.environ.get('META_ACCESS_TOKEN', '')
VERSION = os.environ.get('META_API_VERSION', 'v19.0')
ACCT = '1455525822955003'

# Test 6: ad-level insights WITHOUT creative field
url = f'https://graph.facebook.com/{VERSION}/act_{ACCT}/insights'
params = {
    'access_token': TOKEN,
    'level': 'ad',
    'time_range': json.dumps({'since': '2026-06-01', 'until': '2026-07-20'}),
    'fields': 'ad_id,ad_name,spend,impressions,clicks,ctr,cpm,cpc,frequency',
    'limit': 5,
}
r = requests.get(url, params=params)
print('Test 6 - Ad insights (no creative field):')
data = r.json()
print(f'  Data count: {len(data.get("data", []))}')
for d in data.get('data', [])[:5]:
    print(f'  ad={d.get("ad_id","?")} | name={d.get("ad_name","?")[:40]} | spend={d.get("spend",0)} | imp={d.get("impressions",0)} | ctr={d.get("ctr",0)} | freq={d.get("frequency",0)}')

# Test 7: Check one ad's creative
url7 = f'https://graph.facebook.com/{VERSION}/120249867566940444'
params7 = {'access_token': TOKEN, 'fields': 'id,name,creative{id,thumbnail_url,image_url}'}
r7 = requests.get(url7, params=params7)
print()
print('Test 7 - Single ad creative:')
data7 = r7.json()
print(json.dumps(data7, indent=2)[:500])

# Test 8: Full date range on ad level
url8 = f'https://graph.facebook.com/{VERSION}/act_{ACCT}/insights'
params8 = {
    'access_token': TOKEN,
    'level': 'ad',
    'time_range': json.dumps({'since': '2025-11-01', 'until': '2026-07-20'}),
    'fields': 'ad_id,ad_name,spend,impressions,clicks,ctr,cpm,date_start,date_stop',
    'limit': 5,
}
r8 = requests.get(url8, params=params8)
print()
print('Test 8 - Full range ad insights:')
data8 = r8.json()
print(f'  Data count: {len(data8.get("data", []))}')
for d in data8.get('data', [])[:5]:
    print(f'  ad={d.get("ad_id","?")} | name={d.get("ad_name","?")[:40]} | spend={d.get("spend",0)} | {d.get("date_start","?")}~{d.get("date_stop","?")}')