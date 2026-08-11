"""检查账户的 pixel 和转化事件"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"
ad_account_id = "1784471669598847"

print("=== 检查账户的像素 ===")
r = requests.get(
    f"{BV}/act_{ad_account_id}/ads_pixels",
    params={"access_token": USER_TOKEN},
    timeout=30,
)
pixels = r.json().get("data", [])
print(f"账户像素数量: {len(pixels)}")
for pixel in pixels:
    print(f"  - ID: {pixel.get('id')}, Name: {pixel.get('name')}")

print("\n=== 检查旧账户的像素 ===")
old_account_id = "1455525822955003"
r2 = requests.get(
    f"{BV}/act_{old_account_id}/ads_pixels",
    params={"access_token": USER_TOKEN},
    timeout=30,
)
old_pixels = r2.json().get("data", [])
print(f"旧账户像素数量: {len(old_pixels)}")
for pixel in old_pixels:
    print(f"  - ID: {pixel.get('id')}, Name: {pixel.get('name')}")

print("\n=== 检查应用事件配置 ===")
app_id = "836792580521282"
r3 = requests.get(
    f"{BV}/{app_id}/app_events",
    params={"access_token": USER_TOKEN},
    timeout=30,
)
print(f"应用事件: {json.dumps(r3.json(), ensure_ascii=False)[:300]}")
