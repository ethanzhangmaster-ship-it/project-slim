import requests, json
TOKEN = 'EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk'
BV = 'https://graph.facebook.com/v19.0'
ad_account_id = '1455525822955003'  # GAMEGZZ_Tec_Do_04_260115_AND_1

# 获取 active adsets
r = requests.get(f'{BV}/act_{ad_account_id}/adsets', params={
    'access_token': TOKEN,
    'fields': 'id,name,optimization_goal,status,promoted_object{object_store_url,application_id}',
    'limit': 50,
}, timeout=30)

adsets = r.json().get('data', [])
print(f'P04账户 {ad_account_id} 活跃 Adsets ({len(adsets)} 个):')
for aset in adsets[:5]:
    po = aset.get('promoted_object', {})
    print(f"  {aset['id']}: {aset.get('name','')[:40]}")
    print(f"    optimization_goal: {aset.get('optimization_goal')}")
    print(f"    app_id: {po.get('application_id')}")
    print(f"    store_url: {po.get('object_store_url')}")