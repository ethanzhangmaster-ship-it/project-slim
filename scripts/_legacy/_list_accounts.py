import requests
TOKEN = 'EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk'
BV = 'https://graph.facebook.com/v19.0'
r = requests.get(f'{BV}/me/adaccounts', params={'access_token': TOKEN, 'fields': 'id,name,account_status', 'limit': 50}, timeout=30)
accts = r.json().get('data', [])
print(f'共 {len(accts)} 个账户:')
for a in accts:
    status = '✅' if a.get('account_status') == 1 else '❌'
    print(f"  {status} {a['id']}: {a.get('name','?')}")