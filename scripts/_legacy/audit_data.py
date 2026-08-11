"""Data audit script for P04 creative pipeline."""
import csv
import os
import json

BASE = r'd:\project_slim\project_slim'

def audit_adjust():
    """Audit Adjust attribution data."""
    path = os.path.join(BASE, 'output', 'active', 'adjust_creative_analysis_20260624.csv')
    print('=' * 60)
    print('1. adjust_creative_analysis_20260624.csv')
    print('=' * 60)
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames
    print(f'总行数: {len(rows)}')
    print(f'列数: {len(cols)}')
    print(f'列: {cols}')
    
    # Missing/unknown
    miss_count = {c: 0 for c in cols}
    for r in rows:
        for c in cols:
            if not r.get(c) or r[c] == 'unknown' or r[c] == '':
                miss_count[c] += 1
    print('\n缺失/unknown 率:')
    for c, m in miss_count.items():
        if m > 0:
            print(f'  {c}: {m}/{len(rows)} ({100*m/len(rows):.0f}%)')
    
    # Platform split
    android = sum(1 for r in rows if 'And' in r.get('creative_name','') or 'AND' in r.get('creative_name',''))
    ios = sum(1 for r in rows if 'IOS' in r.get('creative_name','') or 'ios' in r.get('creative_name',''))
    print(f'\nAndroid: {android}, iOS: {ios}')
    
    # Spend/Revenue/ROI
    spends = [float(r['spend']) for r in rows if r.get('spend') and r['spend'] != 'unknown']
    revenues = [float(r['revenue']) for r in rows if r.get('revenue') and r['revenue'] != 'unknown']
    rois = [float(r['roi']) for r in rows if r.get('roi') and r['roi'] != 'unknown']
    installs = [float(r['installs']) for r in rows if r.get('installs') and r['installs'] != 'unknown']
    print(f'\n有 spend 数据: {len(spends)}/{len(rows)}')
    print(f'有 installs 数据: {len(installs)}/{len(rows)}')
    print(f'有 revenue 数据: {len(revenues)}/{len(rows)}')
    print(f'有 roi 数据: {len(rois)}/{len(rows)}')
    if spends:
        print(f'spend: min={min(spends):.1f}, max={max(spends):.1f}, avg={sum(spends)/len(spends):.1f}')
    if revenues:
        print(f'revenue: min={min(revenues):.1f}, max={max(revenues):.1f}, avg={sum(revenues)/len(revenues):.1f}')
    if rois:
        print(f'roi: min={min(rois):.4f}, max={max(rois):.4f}, avg={sum(rois)/len(rois):.4f}')
    
    # Top 5 by ROI
    valid_rows = [r for r in rows if r.get('roi') and r['roi'] != 'unknown']
    sorted_rows = sorted(valid_rows, key=lambda r: float(r['roi']), reverse=True)
    print('\nTop 5 ROI:')
    for r in sorted_rows[:5]:
        print(f'  {r["creative_name"]}: roi={r["roi"]}, spend={r["spend"]}, revenue={r["revenue"]}, installs={r["installs"]}, platform={r.get("project","")}')
    
    # Check: how many have creative_id that matches
    creative_ids = set(r.get('creative_id', '') for r in rows if r.get('creative_id'))
    print(f'\n唯一 creative_id 数: {len(creative_ids)}')
    
    # Check decision_status
    statuses = {}
    for r in rows:
        s = r.get('decision_status', 'unknown')
        statuses[s] = statuses.get(s, 0) + 1
    print(f'decision_status 分布: {statuses}')

def audit_facebook_export():
    """Audit Facebook creatives export."""
    path = os.path.join(BASE, 'output', 'video_intelligence', 'p04', 'p04_facebook_creatives_export.csv')
    print('\n' + '=' * 60)
    print('2. p04_facebook_creatives_export.csv')
    print('=' * 60)
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames
    print(f'总行数: {len(rows)}')
    print(f'列: {cols}')
    print(f'前2行:')
    for r in rows[:2]:
        print(f'  {dict(r)}')

def audit_creative_mapping():
    """Audit creative mapping."""
    path = os.path.join(BASE, 'output', 'video_intelligence', 'p04', 'creative_mapping.csv')
    print('\n' + '=' * 60)
    print('3. creative_mapping.csv')
    print('=' * 60)
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames
    print(f'总行数: {len(rows)}')
    print(f'列: {cols}')
    print(f'前3行:')
    for r in rows[:3]:
        print(f'  {dict(r)}')
    missing = sum(1 for r in rows if not r.get(list(cols)[-1]))
    print(f'\n缺失率:')
    for c in cols:
        m = sum(1 for r in rows if not r.get(c))
        if m > 0:
            print(f'  {c}: {m}/{len(rows)} ({100*m/len(rows):.0f}%)')

def audit_creative_ranking():
    """Audit creative ranking."""
    path = os.path.join(BASE, 'output', 'creative_ranking', 'ranking.csv')
    print('\n' + '=' * 60)
    print('4. creative_ranking/ranking.csv')
    print('=' * 60)
    if not os.path.exists(path):
        print('  FILE NOT FOUND!')
        return
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames
    print(f'总行数: {len(rows)}')
    print(f'列: {cols}')
    print(f'前3行:')
    for r in rows[:3]:
        print(f'  {dict(r)}')

def audit_image_assets():
    """Audit downloaded image assets."""
    assets_dir = os.path.join(BASE, 'memory', 'test_7day_aeo', 'assets')
    print('\n' + '=' * 60)
    print('5. memory/test_7day_aeo/assets/ (图片素材)')
    print('=' * 60)
    if not os.path.exists(assets_dir):
        print('  DIR NOT FOUND!')
        return
    pngs = [f for f in os.listdir(assets_dir) if f.endswith('.png')]
    print(f'PNG 文件数: {len(pngs)}')
    for p in pngs[:5]:
        fpath = os.path.join(assets_dir, p)
        size = os.path.getsize(fpath)
        print(f'  {p}: {size/1024:.0f}KB')

def audit_video_assets():
    """Check video asset directory."""
    video_dir = os.path.join(BASE, 'output', 'video_intelligence', 'p04')
    print('\n' + '=' * 60)
    print('6. Video assets (output/video_intelligence/p04/)')
    print('=' * 60)
    csvs = [f for f in os.listdir(video_dir) if f.endswith('.csv')]
    print(f'CSV 文件: {csvs}')
    # Check for video files
    video_files = [f for f in os.listdir(video_dir) if f.endswith(('.mp4', '.mov', '.avi'))]
    print(f'视频文件: {len(video_files)}')

def audit_winner_dna():
    """Audit Winner DNA extraction."""
    print('\n' + '=' * 60)
    print('7. Winner DNA 提取逻辑')
    print('=' * 60)
    # Check the golden sample report
    runs_dir = os.path.join(BASE, 'output', 'creative_intelligence', 'runs')
    if not os.path.exists(runs_dir):
        print('  runs/ DIR NOT FOUND!')
        return
    run_dirs = sorted([d for d in os.listdir(runs_dir) if d.startswith('p04_golden_verify')])
    if run_dirs:
        latest = run_dirs[-1]
        report_path = os.path.join(runs_dir, latest, 'golden_sample_report.json')
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            print(f'Latest run: {latest}')
            print(f'Winner Creative ID: {report.get("winner_creative_id", "N/A")}')
            print(f'Winner Score: {report.get("winner_score", "N/A")}')
            print(f'IAP Score: {report.get("iap_score", "N/A")}')
            print(f'Spend: {report.get("spend", "N/A")}')
            print(f'Installs: {report.get("installs", "N/A")}')
            print(f'CTR: {report.get("ctr", "N/A")}')
            print(f'ROAS D7: {report.get("roas_d7", "N/A")}')
            dna = report.get("visual_dna", {})
            print(f'\nVisual DNA:')
            for k, v in dna.items():
                if isinstance(v, str) and len(v) > 80:
                    v = v[:80] + '...'
                print(f'  {k}: {v}')
        else:
            print(f'  Report not found at {report_path}')

if __name__ == '__main__':
    audit_adjust()
    audit_facebook_export()
    audit_creative_mapping()
    audit_creative_ranking()
    audit_image_assets()
    audit_video_assets()
    audit_winner_dna()