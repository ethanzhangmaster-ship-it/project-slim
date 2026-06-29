"""下载所有有性能数据的素材图片"""
import json
import os
import requests
import time

IMAGE_DIR = "output/facebook_top_creatives"
os.makedirs(IMAGE_DIR, exist_ok=True)

def main():
    with open('output/facebook_ads_data/summary.json', 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    # 收集所有有性能数据的素材
    all_creatives = []
    for acc in summary['accounts']:
        acc_name = acc['account_name']
        project = acc['project']
        
        insight_map = {}
        for ins in acc.get('insights_30d', []):
            insight_map[ins['ad_name']] = ins
        
        for ad in acc.get('ads', []):
            ad_name = ad.get('name', '')
            creative_data = ad.get('adcreatives', {}).get('data', [])
            if not creative_data:
                continue
            
            c = creative_data[0]
            img_url = c.get('image_url') or c.get('thumbnail_url')
            if not img_url:
                continue
            
            perf = insight_map.get(ad_name, {})
            if perf.get('spend', 0) <= 0:
                continue
            
            all_creatives.append({
                'ad_id': ad.get('id', ''),
                'ad_name': ad_name,
                'account': acc_name,
                'project': project,
                'status': ad.get('status', ''),
                'image_url': img_url,
                'title': c.get('title', ''),
                'body': c.get('body', ''),
                'call_to_action': c.get('call_to_action_type', ''),
                'spend': perf.get('spend', 0),
                'ctr': perf.get('ctr', 0),
                'ipm': perf.get('ipm', 0),
                'cpi': perf.get('cpi', 0),
                'installs': perf.get('installs', 0),
                'roas': perf.get('roas', 0),
                'impressions': perf.get('impressions', 0),
                'clicks': perf.get('clicks', 0),
            })
    
    # 去重（按ad_name + project）
    seen = set()
    unique_creatives = []
    for c in all_creatives:
        key = f"{c['project']}_{c['ad_name']}"
        if key not in seen:
            seen.add(key)
            unique_creatives.append(c)
    
    print(f"有性能数据的唯一素材: {len(unique_creatives)}")
    
    # 检查已下载的
    already = 0
    to_download = []
    for c in unique_creatives:
        safe_name = c['ad_name'].replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')
        filename = f"{c['project']}_{safe_name}.png"
        filepath = f"{IMAGE_DIR}/{filename}"
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 5000:
            c['local_path'] = filepath
            already += 1
        else:
            c['local_path'] = filepath
            to_download.append(c)
    
    print(f"已下载: {already}")
    print(f"待下载: {len(to_download)}")
    
    # 按spend排序，优先下载高花费的
    to_download.sort(key=lambda x: x['spend'], reverse=True)
    
    print(f"\n开始下载...")
    downloaded = already
    failed = 0
    
    for i, c in enumerate(to_download, 1):
        if i % 50 == 0:
            print(f"  进度: {i}/{len(to_download)} | 成功: {downloaded} | 失败: {failed}")
        
        try:
            r = requests.get(c['image_url'], timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(c['local_path'], 'wb') as f:
                    f.write(r.content)
                downloaded += 1
            else:
                failed += 1
        except:
            failed += 1
        
        time.sleep(0.2)  # 避免限流
    
    # 统计有效大图
    valid = 0
    small = 0
    for f in os.listdir(IMAGE_DIR):
        if f.endswith('.png'):
            s = os.path.getsize(f"{IMAGE_DIR}/{f}")
            if s > 5000:
                valid += 1
            else:
                small += 1
    
    print(f"\n=== 下载完成 ===")
    print(f"有效大图(>5KB): {valid}")
    print(f"小图/缩略图: {small}")
    print(f"总文件: {valid + small}")
    
    # 保存完整记录
    all_records = unique_creatives
    with open(f"{IMAGE_DIR}/all_creatives_with_perf.json", 'w', encoding='utf-8') as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    print(f"\n记录已保存: {IMAGE_DIR}/all_creatives_with_perf.json")

if __name__ == "__main__":
    main()