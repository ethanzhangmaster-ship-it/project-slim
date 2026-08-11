import json, csv, os

BASE = r'd:\project_slim\project_slim'

# 1. AEO dataset
print("=" * 60)
print("1. AEO Dataset (real campaign data)")
print("=" * 60)
path = os.path.join(BASE, 'memory', 'test_7day_aeo', 'aeo_dataset.jsonl')
with open(path, 'r', encoding='utf-8') as f:
    lines = [json.loads(line) for line in f if line.strip()]
print(f"Entries: {len(lines)}")
if lines:
    print(f"Keys: {list(lines[0].keys())}")
    # Show first entry
    first = {k: str(v)[:80] for k, v in lines[0].items()}
    for k, v in first.items():
        print(f"  {k}: {v}")

# 2. Check latest_summary for top performers
print("\n" + "=" * 60)
print("2. Latest Summary (top creatives)")
print("=" * 60)
path2 = os.path.join(BASE, 'memory', 'test_7day_aeo', 'latest_summary.json')
with open(path2, 'r', encoding='utf-8') as f:
    summary = json.load(f)
print(f"Keys: {list(summary.keys())}")
if 'top_creatives' in summary:
    tc = summary['top_creatives']
    print(f"Top creatives: {len(tc)}")
    for t in tc[:3]:
        print(f"  {t}")

# 3. Cross-reference: Adjust data top performers (by combined revenue+spend)
print("\n" + "=" * 60)
print("3. Adjust Data - Top Real Performers")
print("=" * 60)
adjust_path = os.path.join(BASE, 'output', 'active', 'adjust_creative_analysis_20260624.csv')
with open(adjust_path, 'r', encoding='utf-8') as f:
    adjust = list(csv.DictReader(f))

# Filter for valid data
valid = []
for r in adjust:
    try:
        spend = float(r.get('spend', 0) or 0)
        revenue = float(r.get('revenue', 0) or 0)
        installs = int(r.get('installs', 0) or 0)
        roi = float(r.get('roi', 0) or 0)
        cid = r.get('creative_id', '').strip()
        if spend >= 10 and cid and cid != 'unknown':  # meaningful spend
            valid.append({
                'creative_id': cid,
                'creative_name': r.get('creative_name', '')[:60],
                'spend': spend,
                'revenue': revenue,
                'installs': installs,
                'roi': roi,
                'project': r.get('project', ''),
            })
    except (ValueError, TypeError):
        pass

# Sort by revenue desc
valid.sort(key=lambda x: x['revenue'], reverse=True)
print(f"Valid entries (spend>=$10): {len(valid)}")
print("\nTop 10 by revenue:")
for i, v in enumerate(valid[:10]):
    print(f"  [{i+1}] ID={v['creative_id']}")
    print(f"       name={v['creative_name']}")
    print(f"       spend={v['spend']:.1f}, revenue={v['revenue']:.1f}, roi={v['roi']:.4f}, installs={v['installs']}")
    print(f"       platform={v['project']}")

# 4. Check: do any of these real winners have local images?
print("\n" + "=" * 60)
print("4. Local Image Asset Check")
print("=" * 60)
assets_dir = os.path.join(BASE, 'memory', 'test_7day_aeo', 'assets')
pngs = [f for f in os.listdir(assets_dir) if f.endswith('.png')]
print(f"Local PNG assets: {len(pngs)}")
for p in pngs:
    fpath = os.path.join(assets_dir, p)
    size = os.path.getsize(fpath)
    print(f"  {p}: {size/1024:.0f}KB")

# 5. Check creative_mapping_v2 for top performers
print("\n" + "=" * 60)
print("5. Creative Mapping V2 - Top Performers")
print("=" * 60)
map_path = os.path.join(BASE, 'output', 'video_intelligence', 'p04', 'creative_mapping_v2.csv')
with open(map_path, 'r', encoding='utf-8') as f:
    mapping = list(csv.DictReader(f))

valid_map = []
for r in mapping:
    try:
        spend = float(r.get('spend', 0) or 0)
        revenue = float(r.get('revenue', 0) or 0)
        roas = float(r.get('roas', 0) or 0)
        cid = r.get('creative_id', '').strip().replace('\ufeff', '')
        if spend >= 10 and cid:
            valid_map.append({
                'creative_id': cid,
                'creative_name': r.get('creative_name', '')[:60],
                'spend': spend,
                'revenue': revenue,
                'roas': roas,
                'eagle_filename': r.get('eagle_filename', '')[:60],
                'eagle_filepath': r.get('eagle_filepath', '')[:80],
                'thumbnail_url': r.get('thumbnail_url', '')[:80],
                'platform': 'iOS' if 'IOS' in (r.get('ad_name', '') or '') else 'Android' if 'And' in (r.get('ad_name', '') or '') else 'unknown',
            })
    except (ValueError, TypeError):
        pass

valid_map.sort(key=lambda x: x['revenue'], reverse=True)
print(f"Valid entries (spend>=$10): {len(valid_map)}")
print("\nTop 10 by revenue:")
for i, v in enumerate(valid_map[:10]):
    print(f"  [{i+1}] ID={v['creative_id']} ({v['platform']})")
    print(f"       name={v['creative_name']}")
    print(f"       spend={v['spend']:.1f}, revenue={v['revenue']:.1f}, roas={v['roas']:.4f}")
    print(f"       eagle={v['eagle_filename']}")
    print(f"       thumbnail={v['thumbnail_url']}")