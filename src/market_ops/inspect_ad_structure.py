"""检查ad数据结构,确认如何区分图片/视频,以及creative_id字段"""
import json

with open('output/facebook_ads_data/summary.json', 'r', encoding='utf-8') as f:
    s = json.load(f)

# 看第一个账户的前3个ad样本
acc = s['accounts'][0]
print(f"账户: {acc['account_name']}")
print(f"ad字段示例:")
for ad in acc.get('ads', [])[:3]:
    print(json.dumps(ad, indent=2, ensure_ascii=False)[:800])
    print("---")
