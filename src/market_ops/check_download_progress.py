import os
d = 'output/facebook_top_creatives'
for sub in sorted(os.listdir(d)):
    p = os.path.join(d, sub)
    if os.path.isdir(p):
        files = [f for f in os.listdir(p) if f.endswith('.png')]
        valid = [f for f in files if os.path.getsize(os.path.join(p, f)) > 5000]
        print(f"{sub}: {len(files)} files ({len(valid)} valid >5KB)")
