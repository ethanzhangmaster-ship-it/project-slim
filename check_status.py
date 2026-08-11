import requests, os, json, shutil
os.environ['NO_PROXY'] = '192.168.124.13'
base = 'outputs/P04_Video_Test_Set_001'

r = requests.get('http://192.168.124.13:8188/queue', timeout=10)
q = r.json()
print('Running:', len(q.get('queue_running', [])))
for item in q.get('queue_running', []):
    if len(item) >= 2:
        print('  RUN:', item[1])

r2 = requests.get('http://192.168.124.13:8188/system_stats', timeout=10)
d = r2.json().get('devices', [{}])
vr = d[0].get('vram_free', 0) // (1024 * 1024) if d else 0
print('VRAM free:', vr, 'MB')

# Check video_006 Wan I2V
pid = '905282d2-5d09-443a-878e-f68ec8fe7330'
r3 = requests.get('http://192.168.124.13:8188/history/' + pid, timeout=10)
data = r3.json()
if data and pid in data:
    print('video_006 Wan: COMPLETED')
    outputs = data[pid].get('outputs', {})
    for node_id, node_out in outputs.items():
        if 'gifs' in node_out:
            for g in node_out['gifs']:
                fn = g['filename']
                print('  Found:', fn)
                url = 'http://192.168.124.13:8188/view?filename=' + fn + '&type=output'
                r4 = requests.get(url, timeout=60)
                out = os.path.join(base, 'video_006.mp4')
                with open(out, 'wb') as f:
                    f.write(r4.content)
                print('  Downloaded:', out, len(r4.content))
else:
    print('video_006 Wan: still running or not found')

# List all mp4
print('\nAll MP4 files:')
for f in sorted(os.listdir(base)):
    if f.endswith('.mp4'):
        sz = os.path.getsize(os.path.join(base, f))
        print(' ', f, sz // 1024, 'KB')
