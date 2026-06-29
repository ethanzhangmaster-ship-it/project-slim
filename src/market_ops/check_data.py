"""检查数据完整性"""
import json
import os

with open('output/facebook_ads_data/summary.json', 'r', encoding='utf-8') as f:
    summary = json.load(f)

print("=== 各账户数据统计 ===")
print(f"{'账户名':<45} {'项目':<6} {'广告数':<8} {'有性能':<8} {'有图片URL':<10}")
print("-" * 80)

total_ads = 0
total_with_perf = 0
total_with_img = 0

for acc in summary['accounts']:
    acc_name = acc['account_name']
    project = acc['project']
    ads_count = len(acc.get('ads', []))
    insights_count = len(acc.get('insights_30d', []))
    
    with_img = 0
    for ad in acc.get('ads', []):
        creative = ad.get('adcreatives', {}).get('data', [])
        if creative and (creative[0].get('image_url') or creative[0].get('thumbnail_url')):
            with_img += 1
    
    print(f"  {acc_name:<43} {project:<6} {ads_count:<8} {insights_count:<8} {with_img:<10}")
    total_ads += ads_count
    total_with_perf += insights_count
    total_with_img += with_img

print("-" * 80)
print(f"  总计: 广告={total_ads}, 有性能={total_with_perf}, 有图片URL={total_with_img}")

img_count = len([f for f in os.listdir('output/facebook_top_creatives') if f.endswith('.png')])
print(f"\n实际下载图片: {img_count} (有效大图+缩略图)")

# 检查下载的图片大小分布
print("\n=== 下载图片大小分布 ===")
sizes = []
for f in sorted(os.listdir('output/facebook_top_creatives')):
    if f.endswith('.png'):
        s = os.path.getsize(f'output/facebook_top_creatives/{f}')
        sizes.append((f, s))

large = [s for s in sizes if s[1] > 50000]
small = [s for s in sizes if s[1] <= 50000]
print(f"  大图(>50KB): {len(large)}")
print(f"  小图/缩略图(<=50KB): {len(small)}")

# 检查只下载了Top30，但有多少有性能数据的素材
print(f"\n=== 数据缺口 ===")
print(f"  有图片URL的广告: {total_with_img}")
print(f"  只下载了Top30（按spend排序）")
print(f"  未下载: {total_with_img - 30} 个")

# 检查有性能但没图片的
perf_no_img = 0
for acc in summary['accounts']:
    ad_names_with_img = set()
    for ad in acc.get('ads', []):
        creative = ad.get('adcreatives', {}).get('data', [])
        if creative and (creative[0].get('image_url') or creative[0].get('thumbnail_url')):
            ad_names_with_img.add(ad.get('name', ''))
    
    for ins in acc.get('insights_30d', []):
        if ins['ad_name'] not in ad_names_with_img:
            perf_no_img += 1

print(f"  有性能数据但无图片URL: {perf_no_img} 个")