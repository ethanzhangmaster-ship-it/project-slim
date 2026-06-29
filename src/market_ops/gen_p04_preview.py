"""生成P04 Top Winners的HTML预览 - 直观查看素材"""
import json
import os
import base64

with open('output/facebook_top_creatives/all_image_creatives_with_perf.json', 'r', encoding='utf-8') as f:
    creatives = json.load(f)

# P04 Top 15 by spend
p04 = sorted([c for c in creatives if c['project'] == 'P04'], key=lambda x: x['spend'], reverse=True)[:15]

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>P04 Top Winners Preview</title>
<style>
body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #eee; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; }
.card { background: #2a2a2a; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
.card img { width: 100%; display: block; }
.info { padding: 10px; font-size: 12px; }
.name { color: #FFD700; font-weight: bold; margin-bottom: 5px; word-break: break-all; }
.stats { display: flex; gap: 10px; flex-wrap: wrap; }
.stat { background: #333; padding: 3px 8px; border-radius: 4px; }
.cid { color: #888; font-size: 10px; margin-top: 5px; }
.title { color: #0ff; margin-top: 5px; font-size: 11px; }
.body { color: #ccc; font-size: 11px; margin-top: 3px; }
h1 { color: #FFD700; }
</style>
</head>
<body>
<h1>P04 Witch - Top 15 Winners by Spend</h1>
<div class="grid">
"""

for c in p04:
    img_path = c.get('local_path', '')
    if not img_path or not os.path.exists(img_path):
        continue

    # 用相对路径
    rel_path = img_path.replace('\\', '/').replace('output/', '../')
    html += f"""
    <div class="card">
        <img src="{rel_path}" loading="lazy" onerror="this.style.display='none'">
        <div class="info">
            <div class="name">{c['ad_name']}</div>
            <div class="stats">
                <span class="stat">💰 ${c['spend']:.0f}</span>
                <span class="stat">CTR {c['ctr']:.1f}%</span>
                <span class="stat">IPM {c['ipm']:.2f}</span>
                <span class="stat">CPI ${c['cpi']:.2f}</span>
                <span class="stat">Install {c['installs']}</span>
            </div>
            <div class="cid">CID: {c['creative_id']}</div>
            <div class="title">{c.get('title','')[:50]}</div>
            <div class="body">{c.get('body','')[:80]}</div>
        </div>
    </div>
    """

html += """
</div>
</body>
</html>
"""

out_path = 'output/facebook_top_creatives/P04_top15_preview.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"预览已生成: {out_path}")
print(f"P04 Top15 图片数: {len(p04)}")
