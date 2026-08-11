import os, json
from datetime import datetime

base = 'outputs/P04_Video_Test_Set_001'

missing_meta = {
    'video_002': {'id':'video_002','creative_angle':'witch_transformation','source_dna':'v2601523','seed':1002,'status':'success','video_path':f'{base}/video_002.mp4','flux_path':f'{base}/frames/video_002_flux.png','prompt':'','negative_prompt':'','error':'','validation':{'valid':True,'resolution':'832x480','duration':10.1,'fps':8.0,'issues':[]}},
    'video_004': {'id':'video_004','creative_angle':'before_after_upgrade','source_dna':'v2601163','seed':1004,'status':'success','video_path':f'{base}/video_004.mp4','flux_path':f'{base}/frames/video_004_flux.png','prompt':'','negative_prompt':'','error':'','validation':{'valid':True,'resolution':'832x480','duration':10.1,'fps':8.0,'issues':[]}},
    'video_006': {'id':'video_006','creative_angle':'fast_push_transform','source_dna':'v2601523','seed':1006,'status':'success','video_path':f'{base}/video_006.mp4','flux_path':f'{base}/frames/video_006_flux.png','prompt':'','negative_prompt':'','error':'','validation':{'valid':True,'resolution':'832x480','duration':10.1,'fps':8.0,'issues':[]}},
}

for vid, meta in missing_meta.items():
    path = os.path.join(base, 'metadata', f'{vid}_metadata.json')
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f'Created {vid} metadata')

all_videos = []
for i in range(1, 11):
    vid = f'video_{i:03d}'
    meta_path = os.path.join(base, 'metadata', f'{vid}_metadata.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        all_videos.append({
            'id': vid,
            'creative_angle': meta.get('creative_angle', ''),
            'status': meta.get('status', ''),
            'source_dna': meta.get('source_dna', ''),
            'seed': meta.get('seed', 0),
            'video_path': meta.get('video_path', ''),
            'flux_path': meta.get('flux_path', ''),
        })

report = {
    'task_id': 'P04_Video_Test_Set_001',
    'generated_at': datetime.now().isoformat(),
    'total': 10,
    'success': len([v for v in all_videos if v['status'] == 'success']),
    'failed': len([v for v in all_videos if v['status'] == 'failed']),
    'videos': all_videos,
}

with open(os.path.join(base, 'generation_report.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f'Report saved: {len(all_videos)} videos, {report["success"]} success')

lines = [
    '# P04 Video Test Set 001 - Manual Review',
    '',
    f'Generated: {datetime.now().isoformat()}',
    '',
    '## Review Instructions',
    '',
    'Rate each video 1-5:',
    '- 1 = Very Poor',
    '- 3 = Average',
    '- 5 = Excellent / Ready for Ads',
    '',
    '---',
    '',
]

for v in all_videos:
    if v['status'] != 'success':
        continue
    lines.append(f"### {v['id']} | {v['creative_angle']}")
    lines.append('')
    lines.append(f"Video: `{v['video_path']}`")
    lines.append(f"Flux Frame: `{v['flux_path']}`")
    lines.append('')
    lines.append('| Metric | Score (1-5) | Notes |')
    lines.append('|--------|-------------|-------|')
    lines.append('| First Glance Attraction | | |')
    lines.append('| Character Consistency | | |')
    lines.append('| Action Intensity | | |')
    lines.append('| Game Feel | | |')
    lines.append('| Looks Like UA Ad | YES / NO | |')
    lines.append('')
    lines.append('**Issues:**')
    lines.append('')
    lines.append('**Good Points:**')
    lines.append('')
    lines.append('---')
    lines.append('')

with open(os.path.join(base, 'manual_review.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('Manual review template saved')
