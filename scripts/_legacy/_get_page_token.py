"""获取 Page Token"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
page_id = "103008755226035"

print(f"获取 Page {page_id} 的 Token...")
r = requests.get(
    f"{BV}/me/accounts",
    params={"access_token": USER_TOKEN},
    timeout=30,
)
d = r.json()

pages = d.get("data", [])
for page in pages:
    print(f"\nPage: {page.get('name')} ({page.get('id')})")
    print(f"  Token: {page.get('access_token')}")
    print(f"  Permissions: {page.get('perms')}")

print(f"\n=== 检查 Page 照片上传权限 ===")
r2 = requests.get(
    f"{BV}/{page_id}",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,access_token",
    },
    timeout=30,
)
print(json.dumps(r2.json(), indent=2, ensure_ascii=False))
