"""生成Round1图片预览HTML - 展示6张生成的mutation图片"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
IMG_DIR = ROOT / "output" / "P04_Creative_Factory" / "images_round1"
LOG_FILE = IMG_DIR / [f for f in os.listdir(IMG_DIR) if f.startswith("run_round1")][0]

with open(LOG_FILE, 'r', encoding='utf-8') as f:
    results = json.load(f)

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>P04 Creative Factory - Round 1</title>
<style>
body { font-family: Arial, sans-serif; margin: 0; background: #0f0f0f; color: #eee; }
header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; text-align: center; }
h1 { color: #FFD700; margin: 0; }
.subtitle { color: #aaa; margin-top: 5px; font-size: 14px; }
.dna-bar { display: flex; justify-content: center; gap: 15px; margin-top: 10px; }
.dna-tag { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }
.dna-mystery { background: #4a148c; color: #ce93d8; }
.dna-magic { background: #1a237e; color: #7986cb; }
.dna-progress { background: #00695c; color: #4db6ac; }
.dna-collection { background: #e65100; color: #ffcc80; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; padding: 20px; max-width: 1400px; margin: 0 auto; }
.card { background: #1a1a1a; border-radius: 12px; overflow: hidden; box-shadow: 0 6px 20px rgba(0,0,0,0.6); }
.card img { width: 100%; display: block; }
.card-body { padding: 12px; }
.card-id { color: #FFD700; font-weight: bold; font-size: 14px; }
.card-type { display: inline-block; padding: 2px 8px; border-radius: 8px; font-size: 11px; margin-left: 8px; }
.type-winner { background: #1b5e20; color: #a5d6a7; }
.type-new { background: #e65100; color: #ffcc80; }
.type-explore { background: #4a148c; color: #ce93d8; }
.card-source { color: #888; font-size: 11px; margin-top: 4px; }
.card-hook { color: #0ff; font-size: 11px; margin-top: 2px; }
.card-prompt { color: #aaa; font-size: 10px; margin-top: 6px; max-height: 60px; overflow: hidden; }
.card-time { color: #666; font-size: 10px; margin-top: 4px; }
footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
</style>
</head>
<body>
<header>
    <h1>P04 Creative Factory - Round 1</h1>
    <div class="subtitle">基于真实Facebook Ads Winner DNA生成 | 6张mutation图片 | Lovart GPT-Image-2</div>
    <div class="dna-bar">
        <span class="dna-tag dna-mystery">Mystery 10/10</span>
        <span class="dna-tag dna-magic">Magic 7/10</span>
        <span class="dna-tag dna-progress">Progress 4/10</span>
        <span class="dna-tag dna-collection">Collection 3/10</span>
    </div>
    <div class="subtitle" style="margin-top:8px;">Winner DNA: gray60% + purple17.5% + black13.6% | medium亮度</div>
</header>
<div class="grid">
"""

type_class = {"winner_mutation": "type-winner", "new_hook": "type-new", "explore": "type-explore"}
type_label = {"winner_mutation": "Winner Mut", "new_hook": "New Hook", "explore": "Explore"}

for r in results:
    if r["status"] != "ok":
        continue
    filename = os.path.basename(r["file"])
    html += f"""
    <div class="card">
        <img src="images_round1/{filename}" loading="lazy">
        <div class="card-body">
            <span class="card-id">{r['id']}</span>
            <span class="card-type {type_class.get(r['type'], '')}">{type_label.get(r['type'], r['type'])}</span>
            <div class="card-hook">Hook: {r['hook']}</div>
            <div class="card-source">来源: {r['source']}</div>
            <div class="card-prompt">{r['prompt'][:150]}...</div>
            <div class="card-time">生成耗时: {r['elapsed_sec']}s</div>
        </div>
    </div>
    """

html += """
</div>
<footer>
    P04 Creative Factory Round 1 | DNA-driven Mutation Engine | 2026-06-26
</footer>
</body>
</html>
"""

out_path = ROOT / "output" / "P04_Creative_Factory" / "round1_preview.html"
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"预览已生成: {out_path}")
print(f"成功图片: {sum(1 for r in results if r['status']=='ok')}/{len(results)}")
