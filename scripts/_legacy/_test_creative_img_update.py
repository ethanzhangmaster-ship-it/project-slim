"""测试各种更新 creative 图片的方式"""
import requests, json

TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

cid = "34323136007300232"  # 第5个 creative，先看它当前状态
new_hash = "0c0493ba836a1ba624f591bfc087760e"

# 先看当前状态
r0 = requests.get(f"{BV}/{cid}", params={
    "access_token": TOKEN,
    "fields": "id,name,image_hash,image_url,object_store_url,object_type,video_id,body,title"
}, timeout=30)
print("当前 creative:")
print(json.dumps(r0.json(), indent=2, ensure_ascii=False))

# 方式 1: image_url (用 fbcdn URL)
print("\n方式 1: 更新 image_url...")
img_url = "https://scontent-tpe1-1.xx.fbcdn.net/v/t45.1600-4/736172875_122279749382083055_873695637005602145_n.png"
r1 = requests.post(f"{BV}/{cid}", data={
    "access_token": TOKEN,
    "image_url": img_url,
}, timeout=30)
print(f"  结果: {r1.json()}")

# 验证
r1b = requests.get(f"{BV}/{cid}", params={
    "access_token": TOKEN, "fields": "image_hash,image_url"
}, timeout=30)
print(f"  验证: {r1b.json()}")

# 方式 2: 用 adimages 上传后返回的 url
print("\n方式 2: 用 image_file_url (如果有)...")
print("  (跳过，需要找正确的参数名)")