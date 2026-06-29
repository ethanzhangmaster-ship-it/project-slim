"""下载Facebook Top表现素材图片"""
import json
import os
import requests
import time
from datetime import datetime

OUTPUT_DIR = "output/facebook_ads_data"
IMAGE_DIR = "output/facebook_top_creatives"
os.makedirs(IMAGE_DIR, exist_ok=True)

def main():
    # 读取汇总数据
    with open(f"{OUTPUT_DIR}/summary.json", 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    # 收集所有广告素材（含图片URL）
    all_creatives = []
    for acc in summary['accounts']:
        acc_name = acc['account_name']
        project = acc['project']
        
        # 构建 ad_name -> insight 的映射
        insight_map = {}
        for ins in acc.get('insights_30d', []):
            insight_map[ins['ad_name']] = ins
        
        # 遍历广告，匹配性能数据
        for ad in acc.get('ads', []):
            ad_name = ad.get('name', '')
            creative_data = ad.get('adcreatives', {}).get('data', [])
            if not creative_data:
                continue
            
            c = creative_data[0]
            img_url = c.get('image_url') or c.get('thumbnail_url')
            if not img_url:
                continue
            
            # 匹配性能数据
            perf = insight_map.get(ad_name, {})
            spend = perf.get('spend', 0)
            
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
                'spend': spend,
                'ctr': perf.get('ctr', 0),
                'ipm': perf.get('ipm', 0),
                'cpi': perf.get('cpi', 0),
                'installs': perf.get('installs', 0),
                'roas': perf.get('roas', 0),
                'impressions': perf.get('impressions', 0),
                'clicks': perf.get('clicks', 0),
            })
    
    print(f"总共找到 {len(all_creatives)} 个带图片的素材")
    
    # 筛选有性能数据的素材（spend > 0）
    with_perf = [c for c in all_creatives if c['spend'] > 0]
    print(f"其中有性能数据的: {len(with_perf)}")
    
    # 按spend排序，取Top 30
    top_creatives = sorted(with_perf, key=lambda x: x['spend'], reverse=True)[:30]
    
    print(f"\n=== 下载Top {len(top_creatives)} 素材图片 ===\n")
    
    downloaded = []
    for i, c in enumerate(top_creatives, 1):
        # 生成文件名
        safe_name = c['ad_name'].replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')
        project = c['project']
        filename = f"{project}_{safe_name}.png"
        filepath = f"{IMAGE_DIR}/{filename}"
        
        print(f"[{i}/{len(top_creatives)}] {c['ad_name'][:40]} | spend=${c['spend']} | ctr={c['ctr']}% | ipm={c['ipm']}")
        
        if os.path.exists(filepath):
            print(f"  已存在，跳过")
            c['local_path'] = filepath
            downloaded.append(c)
            continue
        
        try:
            r = requests.get(c['image_url'], timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(filepath, 'wb') as f:
                    f.write(r.content)
                print(f"  已保存: {filepath} ({len(r.content)//1024}KB)")
                c['local_path'] = filepath
                downloaded.append(c)
            else:
                print(f"  下载失败: status={r.status_code} size={len(r.content)}")
        except Exception as e:
            print(f"  错误: {e}")
        
        time.sleep(0.5)
    
    # 保存下载记录
    with open(f"{IMAGE_DIR}/top_creatives.json", 'w', encoding='utf-8') as f:
        json.dump(downloaded, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== 下载完成: {len(downloaded)}/{len(top_creatives)} ===")
    print(f"保存位置: {IMAGE_DIR}/")
    print(f"记录文件: {IMAGE_DIR}/top_creatives.json")
    
    # 打印Top10排行
    print(f"\n=== Top10 花费素材 ===")
    for c in downloaded[:10]:
        print(f"  {c['project']} | {c['ad_name'][:40]} | spend=${c['spend']} | ctr={c['ctr']}% | ipm={c['ipm']} | cpi=${c['cpi']} | roas={c['roas']}")
    
    # 按CTR排序（spend > $100）
    high_spend = [c for c in downloaded if c['spend'] > 100]
    by_ctr = sorted(high_spend, key=lambda x: x['ctr'], reverse=True)
    print(f"\n=== Top10 CTR (spend>$100) ===")
    for c in by_ctr[:10]:
        print(f"  {c['project']} | {c['ad_name'][:40]} | ctr={c['ctr']}% | spend=${c['spend']} | ipm={c['ipm']} | cpi=${c['cpi']}")
    
    # 按IPM排序（spend > $100）
    by_ipm = sorted(high_spend, key=lambda x: x['ipm'], reverse=True)
    print(f"\n=== Top10 IPM (spend>$100) ===")
    for c in by_ipm[:10]:
        print(f"  {c['project']} | {c['ad_name'][:40]} | ipm={c['ipm']} | spend=${c['spend']} | ctr={c['ctr']}% | cpi=${c['cpi']}")

if __name__ == "__main__":
    main()