"""按项目分析Top Winners - 展示每个项目的最佳素材"""
import json

with open('output/facebook_top_creatives/all_image_creatives_with_perf.json', 'r', encoding='utf-8') as f:
    creatives = json.load(f)

# 按项目分组
by_project = {}
for c in creatives:
    p = c['project']
    by_project.setdefault(p, []).append(c)

for proj in sorted(by_project.keys()):
    items = by_project[proj]
    print(f"\n{'='*80}")
    print(f"  {proj} - {len(items)}张图片素材")
    print(f"{'='*80}")

    # 按spend排序
    by_spend = sorted(items, key=lambda x: x['spend'], reverse=True)
    print(f"\n--- Top10 by Spend ---")
    print(f"{'ad_name':<35} {'cid':<18} {'spend':>8} {'ctr':>6} {'ipm':>6} {'cpi':>6} {'inst':>6} {'roas':>6}")
    for c in by_spend[:10]:
        print(f"{c['ad_name'][:34]:<35} {c['creative_id']:<18} {c['spend']:>8.0f} "
              f"{c['ctr']:>5.1f}% {c['ipm']:>5.2f} {c['cpi']:>5.2f} {c['installs']:>6} {c['roas']:>5.2f}")

    # 按CTR排序(最低spend $50门槛)
    high_spend = [c for c in items if c['spend'] >= 50]
    by_ctr = sorted(high_spend, key=lambda x: x['ctr'], reverse=True)
    print(f"\n--- Top10 by CTR (spend>=$50) ---")
    for c in by_ctr[:10]:
        print(f"{c['ad_name'][:34]:<35} {c['creative_id']:<18} {c['spend']:>8.0f} "
              f"{c['ctr']:>5.1f}% {c['ipm']:>5.2f} {c['cpi']:>5.2f} {c['installs']:>6}")

    # 按IPM排序
    by_ipm = sorted([c for c in high_spend if c['installs'] > 0], key=lambda x: x['ipm'], reverse=True)
    print(f"\n--- Top10 by IPM (spend>=$50) ---")
    for c in by_ipm[:10]:
        print(f"{c['ad_name'][:34]:<35} {c['creative_id']:<18} {c['spend']:>8.0f} "
              f"{c['ctr']:>5.1f}% {c['ipm']:>5.2f} {c['cpi']:>5.2f} {c['installs']:>6}")

    # 按CPI排序(越低越好)
    by_cpi = sorted([c for c in high_spend if c['cpi'] > 0], key=lambda x: x['cpi'])
    print(f"\n--- Top10 by CPI (spend>=$50, 越低越好) ---")
    for c in by_cpi[:10]:
        print(f"{c['ad_name'][:34]:<35} {c['creative_id']:<18} {c['spend']:>8.0f} "
              f"{c['ctr']:>5.1f}% {c['ipm']:>5.2f} {c['cpi']:>5.2f} {c['installs']:>6}")

    # 平台分布
    by_plat = {}
    for c in items:
        p = c.get('platform', '?')
        by_plat.setdefault(p, {'count': 0, 'spend': 0})
        by_plat[p]['count'] += 1
        by_plat[p]['spend'] += c['spend']
    print(f"\n--- 平台分布 ---")
    for p, v in sorted(by_plat.items()):
        print(f"  {p}: {v['count']}张, ${v['spend']:,.0f}")

    # title/body样本
    print(f"\n--- Top1 素材文案 ---")
    top1 = by_spend[0]
    print(f"  ad_name: {top1['ad_name']}")
    print(f"  creative_id: {top1['creative_id']}")
    print(f"  title: {top1.get('title','')}")
    print(f"  body: {top1.get('body','')}")
    print(f"  cta: {top1.get('call_to_action','')}")
    print(f"  local_path: {top1.get('local_path','')}")
