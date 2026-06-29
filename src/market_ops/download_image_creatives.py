"""下载所有图片素材(过滤视频) - 带creative_id, 按项目分组

升级点:
1. 只下载 media_type == 'image' 的素材 (跳过视频)
2. 保留 creative_id 用于Facebook后台查找
3. 按项目(P02/P04/P07)分目录存放
4. 生成 all_image_creatives_with_perf.json 完整记录
"""
import json
import os
import requests
import time
import re

SUMMARY = 'output/facebook_ads_data/summary.json'
IMAGE_DIR = 'output/facebook_top_creatives'

os.makedirs(IMAGE_DIR, exist_ok=True)


def safe_filename(name):
    """生成安全文件名"""
    return re.sub(r'[^\w\-\.]', '_', name)[:80]


def main():
    with open(SUMMARY, 'r', encoding='utf-8') as f:
        s = json.load(f)

    print("="*70)
    print("  下载图片素材 (过滤视频)")
    print("="*70)

    # 收集所有图片素材 + 性能数据
    all_image_creatives = []
    video_count = 0
    skipped_no_url = 0

    for acc in s['accounts']:
        acc_name = acc['account_name']
        project = acc['project']
        acc_platform = acc['platform']

        # 建ad_id -> ad 的映射 (用于查找creative_id, media_type, platform)
        ad_map = {ad['id']: ad for ad in acc.get('ads', [])}
        # 也用ad_name映射作为fallback
        ad_name_map = {ad.get('name', ''): ad for ad in acc.get('ads', [])}

        # 建insights映射 (按ad_name)
        insight_map = {ins['ad_name']: ins for ins in acc.get('insights_30d', [])}

        for ad in acc.get('ads', []):
            ad_id = ad.get('id', '')
            ad_name = ad.get('name', '')
            media_type = ad.get('media_type', 'unknown')
            creative_id = ad.get('creative_id', '')
            platform = ad.get('platform', acc_platform)

            creative_data = ad.get('adcreatives', {}).get('data', [])
            if not creative_data:
                skipped_no_url += 1
                continue

            c = creative_data[0]
            img_url = c.get('image_url') or c.get('thumbnail_url')

            # 跳过视频
            if media_type == 'video':
                video_count += 1
                continue

            if not img_url:
                skipped_no_url += 1
                continue

            # 图片素材 - 跳过明显的视频缩略图URL
            if 'p64x64' in img_url or '/v/t15.' in img_url:
                video_count += 1
                continue

            perf = insight_map.get(ad_name, {})
            all_image_creatives.append({
                'ad_id': ad_id,
                'ad_name': ad_name,
                'creative_id': creative_id,
                'account': acc_name,
                'account_id': acc['account_id'],
                'project': project,
                'platform': platform,
                'status': ad.get('status', ''),
                'image_url': img_url,
                'title': c.get('title', ''),
                'body': c.get('body', ''),
                'call_to_action': c.get('call_to_action_type', ''),
                'object_url': c.get('object_url', ''),
                'spend': perf.get('spend', 0),
                'ctr': perf.get('ctr', 0),
                'ipm': perf.get('ipm', 0),
                'cpi': perf.get('cpi', 0),
                'installs': perf.get('installs', 0),
                'roas': perf.get('roas', 0),
                'impressions': perf.get('impressions', 0),
                'clicks': perf.get('clicks', 0),
            })

    print(f"\n图片素材总数: {len(all_image_creatives)}")
    print(f"已跳过视频: {video_count}")
    print(f"已跳过无URL: {skipped_no_url}")

    # 按项目统计
    by_project = {}
    for c in all_image_creatives:
        p = c['project']
        by_project.setdefault(p, {'total': 0, 'with_perf': 0, 'spend': 0})
        by_project[p]['total'] += 1
        if c['spend'] > 0:
            by_project[p]['with_perf'] += 1
            by_project[p]['spend'] += c['spend']

    print(f"\n按项目分布:")
    for p, v in sorted(by_project.items()):
        print(f"  {p}: {v['total']}张 (有花费{v['with_perf']}张, 总花费${v['spend']:,.2f})")

    # 去重 (按creative_id, 保留spend最高的)
    seen = {}
    unique = []
    for c in all_image_creatives:
        key = c['creative_id'] or f"{c['project']}_{c['ad_name']}"
        if key not in seen or c['spend'] > seen[key]['spend']:
            seen[key] = c
    unique = list(seen.values())
    print(f"\n去重后: {len(unique)} 张唯一图片素材")

    # 只下载有花费的
    to_download = [c for c in unique if c['spend'] > 0]
    to_download.sort(key=lambda x: x['spend'], reverse=True)
    print(f"有花费待下载: {len(to_download)} 张")

    # 按项目创建子目录
    for p in by_project:
        os.makedirs(f"{IMAGE_DIR}/{p}", exist_ok=True)

    # 下载
    downloaded = 0
    failed = 0
    already = 0

    for i, c in enumerate(to_download, 1):
        proj = c['project']
        safe_name = safe_filename(c['ad_name'])
        cid = c['creative_id'] or 'nocid'
        filename = f"{IMAGE_DIR}/{proj}/{safe_name}_{cid}.png"

        if os.path.exists(filename) and os.path.getsize(filename) > 5000:
            c['local_path'] = filename
            already += 1
            continue

        c['local_path'] = filename

        if i % 50 == 0:
            print(f"  进度: {i}/{len(to_download)} | 新下载:{downloaded} | 已有:{already} | 失败:{failed}")

        try:
            r = requests.get(c['image_url'], timeout=20)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(filename, 'wb') as f:
                    f.write(r.content)
                downloaded += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        time.sleep(0.15)  # 避免限流

    print(f"\n=== 下载完成 ===")
    print(f"新下载: {downloaded}")
    print(f"已存在: {already}")
    print(f"失败: {failed}")

    # 统计有效大图
    valid = 0
    for p in by_project:
        pdir = f"{IMAGE_DIR}/{p}"
        if os.path.exists(pdir):
            for f in os.listdir(pdir):
                if f.endswith('.png') and os.path.getsize(os.path.join(pdir, f)) > 5000:
                    valid += 1
    print(f"有效大图(>5KB): {valid}")

    # 保存完整记录
    out_file = f"{IMAGE_DIR}/all_image_creatives_with_perf.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(to_download, f, indent=2, ensure_ascii=False)
    print(f"\n记录已保存: {out_file} ({len(to_download)}条)")

    # 按项目保存Top20
    for p in by_project:
        p_items = [c for c in to_download if c['project'] == p]
        p_items.sort(key=lambda x: x['spend'], reverse=True)
        top_file = f"{IMAGE_DIR}/{p}/top20_by_spend.json"
        with open(top_file, 'w', encoding='utf-8') as f:
            json.dump(p_items[:20], f, indent=2, ensure_ascii=False)
        print(f"  {p} Top20: {top_file}")


if __name__ == "__main__":
    main()
