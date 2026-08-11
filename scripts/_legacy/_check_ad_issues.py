"""查询广告具体问题"""
import json, requests

USER_TOKEN = "EAAI8u9NniuEBRwKmUjbrQ1T6THmmf0ZA3uGczZCLcjI4HdrglE93qluZCCEeDHYTxujC2JsXRYs0xwwzenupJz1qT92i5TVSCI90ceYS4aAI8pguIRhIizfO4rZBZAiP1Qz4HqfDA4pZBdHyXcLEYdD4jmYBlg0fj8sSCZAkqDeE6d6dHjX9DGRtFXJtFyKPnQk"
BV = "https://graph.facebook.com/v19.0"

ad_id = "120250205212690346"

# 尝试各种字段找问题
fields_to_try = [
    "name,status,effective_status,issues_info,rejection_reasons,review_feedback",
    "name,status,effective_status,ad_review_feedback",
    "name,status,effective_status,issues",
    "name,status,effective_status,configured_status",
]

for fields in fields_to_try:
    print(f"\n--- fields: {fields[:50]}...")
    r = requests.get(
        f"{BV}/{ad_id}",
        params={"access_token": USER_TOKEN, "fields": fields},
        timeout=30,
    )
    d = r.json()
    print(json.dumps(d, indent=2, ensure_ascii=False))

print("\n--- 检查 adcreative问题 ---")
r2 = requests.get(
    f"{BV}/{ad_id}/creatives",
    params={
        "access_token": USER_TOKEN,
        "fields": "name,status,effective_status,object_story_spec",
        "limit": 5,
    },
    timeout=30,
)
print(json.dumps(r2.json(), indent=2, ensure_ascii=False))
