"""检查现有summary.json里图片vs视频的真实分布"""
import json

with open('output/facebook_ads_data/summary.json', 'r', encoding='utf-8') as f:
    s = json.load(f)

total_ads = 0
has_image_url = 0      # 真正的图片广告
has_thumbnail_only = 0 # 只有缩略图(可能是视频)
p64x64_count = 0       # 64x64视频缩略图
v15_count = 0          # /v/t15./ 视频路径
no_creative = 0
sample_image_urls = []
sample_thumb_urls = []

for acc in s['accounts']:
    for ad in acc.get('ads', []):
        total_ads += 1
        cd = ad.get('adcreatives', {}).get('data', [])
        if not cd:
            no_creative += 1
            continue
        c = cd[0]
        img = c.get('image_url')
        thumb = c.get('thumbnail_url')

        if img and not ('p64x64' in img or '/v/t15.' in img):
            has_image_url += 1
            if len(sample_image_urls) < 3:
                sample_image_urls.append(img[:120])
        elif thumb:
            has_thumbnail_only += 1
            if 'p64x64' in thumb:
                p64x64_count += 1
            if '/v/t15.' in thumb:
                v15_count += 1
            if len(sample_thumb_urls) < 3:
                sample_thumb_urls.append(thumb[:120])

print(f"总广告数: {total_ads}")
print(f"无creative数据: {no_creative}")
print(f"有真正image_url(非视频): {has_image_url}")
print(f"只有thumbnail_url: {has_thumbnail_only}")
print(f"  其中 p64x64(视频缩略图): {p64x64_count}")
print(f"  其中 /v/t15.(视频路径): {v15_count}")

print(f"\n图片URL样本:")
for u in sample_image_urls:
    print(f"  {u}")

print(f"\n缩略图URL样本:")
for u in sample_thumb_urls:
    print(f"  {u}")

# 按账户统计
print(f"\n按账户:")
for acc in s['accounts']:
    img_c = 0
    vid_c = 0
    for ad in acc.get('ads', []):
        cd = ad.get('adcreatives', {}).get('data', [])
        if not cd:
            continue
        c = cd[0]
        url = c.get('image_url') or c.get('thumbnail_url') or ''
        if 'p64x64' in url or '/v/t15.' in url:
            vid_c += 1
        else:
            img_c += 1
    print(f"  {acc['account_name'][:30]:<30} 图片={img_c:<5} 视频={vid_c}")
