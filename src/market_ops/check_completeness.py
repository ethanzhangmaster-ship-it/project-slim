"""检查数据抓取完整性 - 找出遗漏"""
import json
import os

SUMMARY = 'output/facebook_ads_data/summary.json'
IMAGE_DIR = 'output/facebook_top_creatives'

def main():
    with open(SUMMARY, 'r', encoding='utf-8') as f:
        s = json.load(f)

    print("="*70)
    print("  数据完整性检查")
    print("="*70)

    # === 1. 账户层 ===
    print(f"\n[账户层] summary.json包含 {len(s['accounts'])} 个账户:")
    total_campaigns = 0
    total_ads = 0
    total_ins30 = 0
    total_ins7 = 0
    for a in s['accounts']:
        nc = len(a.get('campaigns', []))
        na = len(a.get('ads', []))
        ni30 = len(a.get('insights_30d', []))
        ni7 = len(a.get('insights_7d', []))
        total_campaigns += nc
        total_ads += na
        total_ins30 += ni30
        total_ins7 += ni7
        print(f"  {a['account_id']:<20} {a['account_name'][:25]:<25} "
              f"camp={nc:<5} ads={na:<5} ins30={ni30:<5} ins7={ni7}")
    print(f"  {'TOTAL':<20} {'':<25} camp={total_campaigns} ads={total_ads} ins30={total_ins30} ins7={total_ins7}")

    # === 2. 是否所有账户都被抓取 ===
    # 之前facebook_all_accounts.py发现50个账户,这里只有7个
    all_accounts_file = 'output/facebook_ads_data/all_accounts.json'
    if os.path.exists(all_accounts_file):
        with open(all_accounts_file, 'r', encoding='utf-8') as f:
            all_accs = json.load(f)
        print(f"\n[全账户清单] all_accounts.json: {len(all_accs)} 个账户")
        print(f"  summary.json只包含 {len(s['accounts'])} 个 → 缺失 {len(all_accs) - len(s['accounts'])} 个账户")
    else:
        print(f"\n[全账户清单] all_accounts.json 不存在,无法核对全部账户")

    # === 3. 素材图片下载情况 ===
    if os.path.exists(IMAGE_DIR):
        files = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')]
        valid = [f for f in files if os.path.getsize(os.path.join(IMAGE_DIR, f)) > 5000]
        small = [f for f in files if os.path.getsize(os.path.join(IMAGE_DIR, f)) <= 5000]
        print(f"\n[图片下载] 目录: {IMAGE_DIR}")
        print(f"  总文件: {len(files)}")
        print(f"  有效大图(>5KB): {len(valid)}")
        print(f"  小图/缩略图: {len(small)}")
    else:
        print(f"\n[图片下载] 目录不存在: {IMAGE_DIR}")

    # === 4. all_creatives_with_perf.json 是否生成 ===
    perf_file = os.path.join(IMAGE_DIR, 'all_creatives_with_perf.json')
    if os.path.exists(perf_file):
        with open(perf_file, 'r', encoding='utf-8') as f:
            creatives = json.load(f)
        print(f"\n[素材性能记录] all_creatives_with_perf.json: {len(creatives)} 条")
    else:
        print(f"\n[素材性能记录] all_creatives_with_perf.json 不存在")
        print(f"  → download_all_creatives.py 未运行完成")

    # === 5. 计算应有的素材总数 ===
    unique_creatives = set()
    creatives_with_perf = 0
    for acc in s['accounts']:
        insight_map = {ins['ad_name']: ins for ins in acc.get('insights_30d', [])}
        for ad in acc.get('ads', []):
            ad_name = ad.get('name', '')
            creative_data = ad.get('adcreatives', {}).get('data', [])
            if not creative_data:
                continue
            c = creative_data[0]
            img_url = c.get('image_url') or c.get('thumbnail_url')
            if not img_url:
                continue
            key = f"{acc['project']}_{ad_name}"
            unique_creatives.add(key)
            perf = insight_map.get(ad_name, {})
            if perf.get('spend', 0) > 0:
                creatives_with_perf += 1

    print(f"\n[应有素材数]")
    print(f"  唯一素材(去重): {len(unique_creatives)}")
    print(f"  有花费的素材: {creatives_with_perf}")

    # === 6. 缺口分析 ===
    print(f"\n[缺口分析]")
    if os.path.exists(perf_file):
        with open(perf_file, 'r', encoding='utf-8') as f:
            creatives = json.load(f)
        downloaded_with_perf = len(creatives)
        gap = creatives_with_perf - downloaded_with_perf
        print(f"  应下载(有花费): {creatives_with_perf}")
        print(f"  已记录: {downloaded_with_perf}")
        print(f"  缺口: {gap}")
    else:
        print(f"  all_creatives_with_perf.json未生成 → 需重跑download_all_creatives.py")

    # === 7. 7d insights 缺口 ===
    print(f"\n[7天数据缺口]")
    print(f"  ins30: {total_ins30}  vs  ins7: {total_ins7}")
    if total_ins7 < total_ins30 * 0.5:
        print(f"  ⚠ 7天数据明显少于30天,可能有账户7d查询失败")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
