"""Find missing P04 Facebook accounts for unmatched ad IDs."""
import os, json, requests, time
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ.get('FB_TOKEN', '') or os.environ.get('META_ACCESS_TOKEN', '')
VERSION = os.environ.get('META_API_VERSION', 'v19.0')

# Check known accounts

# Unmatched ad IDs to check (samples)
unmatched_samples = [
    "120239244822560613",  # iOS high cost
    "120240544735690613",  # iOS high cost
    "120242003537200613",  # iOS
    "120235400021620648",  # Android
    "120245231261040613",  # iOS
]

print("\n=== 查询未匹配 ad_id 所属账户 ===")
for ad_id in unmatched_samples:
    url = f"https://graph.facebook.com/{VERSION}/{ad_id}"
    params = {
        "access_token": TOKEN,
        "fields": "id,name,account_id,status,creative{id,thumbnail_url}",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "error" in data:
            print(f"  {ad_id}: ❌ {data['error'].get('message', '')[:120]}")
        else:
            acc_id = data.get("account_id", "?")
            name = data.get("name", "?")
            creative = data.get("creative", {})
            cid = creative.get("id", "") if creative else ""
            print(f"  {ad_id}: account={acc_id} | name={name[:50]} | creative={cid}")
    except Exception as e:
        print(f"  {ad_id}: ❌ {e}")
    time.sleep(0.5)

# Also check matched samples for comparison
matched_samples = ["120246092997380652", "120235836252110187", "120244794613980444"]
print("\n=== 查询已匹配 ad_id 所属账户 ===")
for ad_id in matched_samples:
    url = f"https://graph.facebook.com/{VERSION}/{ad_id}"
    params = {
        "access_token": TOKEN,
        "fields": "id,name,account_id,status",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "error" in data:
            print(f"  {ad_id}: ❌ {data['error'].get('message', '')[:120]}")
        else:
            acc_id = data.get("account_id", "?")
            name = data.get("name", "?")
            print(f"  {ad_id}: account={acc_id} | name={name[:50]}")
    except Exception as e:
        print(f"  {ad_id}: ❌ {e}")
    time.sleep(0.5)

# Check all accounts accessible with this token
print("\n=== 检查 token 可访问的所有账户 ===")
url = f"https://graph.facebook.com/{VERSION}/me/adaccounts"
params = {"access_token": TOKEN, "fields": "id,name,account_status,amount_spent", "limit": 100}
try:
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if "data" in data:
        print(f"  可访问 {len(data['data'])} 个账户:")
        for acc in data["data"]:
            print(f"    act_{acc['id']}: {acc['name']} (status={acc.get('account_status')})")
    else:
        print(f"  ❌ {json.dumps(data, indent=2)[:500]}")
except Exception as e:
    print(f"  ❌ {e}")