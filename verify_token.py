"""Token 验证脚本"""
from market_ops.config import load_settings
import requests

s = load_settings()
token = s.meta_access_token
account = s.meta_ad_account_id
version = s.meta_api_version

print(f"Token: {repr(token[:20] + '...' if token else None)}")
print(f"Account: {repr(account)}")
print(f"API Version: {repr(version)}")

if not token:
    print("❌ Token 未配置！请在 .env 文件中设置 META_ACCESS_TOKEN")
    exit(1)

# 测试 API /me
r = requests.get(
    f"https://graph.facebook.com/{version}/me",
    params={"access_token": token, "fields": "name,id,accounts{access_token,name}"},
    timeout=15,
)
print(f"\n/me: {r.status_code}")
data = r.json()
if "error" in data:
    print(f"❌ API Error: {data['error']}")
else:
    print(f"✅ Token 有效")
    print(f"   User: {data.get('name')} ({data.get('id')})")

# 测试广告账户
if account:
    r2 = requests.get(
        f"https://graph.facebook.com/{version}/act_{account}",
        params={"access_token": token, "fields": "name,account_status,currency,timezone"},
        timeout=15,
    )
    print(f"\nact_{account}: {r2.status_code}")
    data2 = r2.json()
    if "error" in data2:
        print(f"❌ Account Error: {data2['error']}")
    else:
        print(f"✅ Account 有效")
        print(f"   Name: {data2.get('name')}")
        print(f"   Status: {data2.get('account_status')}")
        print(f"   Currency: {data2.get('currency')}")
else:
    print("❌ META_AD_ACCOUNT_ID 未配置")
