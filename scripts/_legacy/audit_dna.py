import json, csv, os

BASE = r'd:\project_slim\project_slim'

# Load winners_dna.json
path = os.path.join(BASE, 'output', 'creative_analysis', 'dna_cache', 'winners_dna.json')
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total entries: {len(data)}')
print()

# Check all entries
for i, e in enumerate(data):
    cid = e.get('creative_id', 'N/A')
    cdn = str(e.get('_cdn_url', ''))[:60]
    has_assistant = bool(e.get('_assistant_text'))
    iap = e.get('iap_score', 0)
    spend = e.get('spend', 0)
    print(f'[{i}] creative_id={cid}')
    print(f'    cdn_url={cdn}...')
    print(f'    has_AI_analysis={has_assistant}')
    print(f'    iap_score={iap}')
    print(f'    spend={spend}')
    print()

# Check if these IDs exist in Adjust data
print('=== Verifying IDs in Adjust data ===')
adjust_path = os.path.join(BASE, 'output', 'active', 'adjust_creative_analysis_20260624.csv')
with open(adjust_path, 'r', encoding='utf-8') as f:
    adjust = list(csv.DictReader(f))

adjust_ids = set()
for r in adjust:
    cid = r.get('creative_id', '').strip()
    if cid:
        adjust_ids.add(cid)

for e in data:
    cid = e.get('creative_id', '')
    in_adjust = cid in adjust_ids
    print(f'  {cid}: in_adjust={in_adjust}')

# Check in mapping
print('\n=== Verifying IDs in Creative Mapping V2 ===')
map_path = os.path.join(BASE, 'output', 'video_intelligence', 'p04', 'creative_mapping_v2.csv')
with open(map_path, 'r', encoding='utf-8') as f:
    mapping = list(csv.DictReader(f))

map_ids = set()
for r in mapping:
    cid = r.get('creative_id', '').strip().replace('\ufeff', '')
    if cid:
        map_ids.add(cid)

for e in data:
    cid = e.get('creative_id', '')
    in_map = cid in map_ids
    print(f'  {cid}: in_mapping={in_map}')

# Check: how many DNA entries have _cdn_url that points to lovart?
print('\n=== CDN source analysis ===')
lovart_count = sum(1 for e in data if 'lovart' in str(e.get('_cdn_url', '')))
print(f'Lovart CDN URLs: {lovart_count}/{len(data)}')
fb_count = sum(1 for e in data if 'fbcdn' in str(e.get('_cdn_url', '')))
print(f'Facebook CDN URLs: {fb_count}/{len(data)}')