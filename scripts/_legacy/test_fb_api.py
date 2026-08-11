import os, json, requests
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.environ.get('FB_TOKEN', '') or os.environ.get('META_ACCESS_TOKEN', '')
VERSION = os.environ.get('META_API_VERSION', 'v19.0')
ACCT = '1455525822955003'

# Test 3: Campaign level insights recent
url = f'https://graph.facebook.com/{VERSION}/act_{ACCT}/insights'
params = {
    'access_token': TOKEN,
    'level': 'campaign',
    'time_range': json.dumps({'since': '2026-06-01', 'until': '2026-07-20'}),
    'fields': 'campaign_id,campaign_name,spend,impressions',
    'limit': 5,
}
r = requests.get(url, params=params)
print('Test 3 - Campaign insights (recent):')
data = r.json()
print(f'  Data count: {len(data.get("data", []))}')
for d in data.get('data', [])[:5]:
    print(f'  {d.get("campaign_name","?")}: spend={d.get("spend",0)}')

# Test 4: Get ads list
url4 = f'https://graph.facebook.com/{VERSION}/act_{ACCT}/ads'
params4 = {'access_token': TOKEN, 'fields': 'id,name,status', 'limit': 5}
r4 = requests.get(url4, params=params4)
print()
print('Test 4 - Ads list:')
data4 = r4.json()
print(f'  Data count: {len(data4.get("data", []))}')
for d in data4.get('data', [])[:5]:
    print(f'  {d.get("id","?")}: {d.get("name","?")} ({d.get("status","?")})')

# Test 5: Ad level insights with creative
url5 = f'https://graph.facebook.com/{VERSION}/act_{ACCT}/insights'
params5 = {
    'access_token': TOKEN,
    'level': 'ad',
    'time_range': json.dumps({'since': '2026-06-01', 'until': '2026-07-20'}),
    'fields': 'ad_id,ad_name,creative{id},spend,impressions,clicks,ctr,cpm',
    'limit': 5,
}
r5 = requests.get(url5, params=params5)
print()
print('Test 5 - Creative insights (recent):')
data5 = r5.json()
print(f'  Data count: {len(data5.get("data", []))}')
for d in data5.get('data', [])[:5]:
    cid = ''
    if 'creative' in d and d['creative']:
        cid = d['creative'].get('id', '')
    print(f'  ad={d.get("ad_id","?")} | creative={cid} | spend={d.get("spend",0)} | imp={d.get("impressions",0)}')