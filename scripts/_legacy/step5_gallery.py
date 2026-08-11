#!/usr/bin/env python3
"""Generate image gallery HTML showing top P04 Witch ad creatives."""
import base64
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output" / "creative_intelligence"

# Top images to showcase
IMAGES = [
    (ROOT / "output/creative_factory/batch_20260713_170800_78ebef/production_candidates/TOP01.png", "Creative Factory TOP #1"),
    (ROOT / "output/creative_factory/batch_20260713_170800_78ebef/production_candidates/TOP02.png", "Creative Factory TOP #2"),
    (ROOT / "output/creative_factory/batch_20260713_170800_78ebef/production_candidates/TOP03.png", "Creative Factory TOP #3"),
    (ROOT / "output/creative_analysis/winner_images/winner_1_26995257276809682.png", "Winner Analysis #1"),
    (ROOT / "output/creative_analysis/winner_images/winner_2_1499507254711059.png", "Winner Analysis #2"),
    (ROOT / "output/creative_analysis/winner_images/winner_3_2681080065641777.png", "Winner Analysis #3"),
    (ROOT / "output/creative_rework/own_top/own_top2.png", "Creative Rework Top #2"),
    (ROOT / "output/creative_rework/own_top/own_top3.png", "Creative Rework Top #3"),
    (ROOT / "output/creative_rework/own_top/own_top4.png", "Creative Rework Top #4"),
    (ROOT / "output/creative_rework/own_top/own_top5.png", "Creative Rework Top #5"),
]

# Encode images
encoded = []
for path, label in IMAGES:
    if path.exists():
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        encoded.append((label, b64, path.stat().st_size))
        print(f"  Loaded: {label} ({path.stat().st_size/1024:.0f} KB)")

# Generate HTML
cards = ""
for i, (label, b64, size) in enumerate(encoded):
    cards += f"""
    <div class="card">
      <img src="data:image/png;base64,{b64}" alt="{label}" />
      <div class="label">{label}</div>
      <div class="size">{size/1024:.0f} KB</div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>P04 Witch - Top Ad Creatives</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0a0a1a; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }}
  h1 {{ text-align: center; color: #c9a0ff; margin-bottom: 8px; font-size: 24px; }}
  .subtitle {{ text-align: center; color: #888; margin-bottom: 24px; font-size: 13px; }}
  .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; max-width: 1400px; margin: 0 auto; }}
  .card {{ background: #1a1a2e; border-radius: 12px; overflow: hidden; border: 1px solid #2a2a4a; transition: transform 0.2s, border-color 0.2s; }}
  .card:hover {{ transform: translateY(-2px); border-color: #c9a0ff; }}
  .card img {{ width: 100%; display: block; aspect-ratio: 1; object-fit: cover; }}
  .label {{ padding: 10px 12px 4px; font-weight: 600; color: #c9a0ff; font-size: 13px; }}
  .size {{ padding: 0 12px 10px; color: #666; font-size: 11px; }}
  .dna-box {{ max-width: 1400px; margin: 24px auto 16px; background: #1a1a2e; border-radius: 12px; border: 1px solid #2a2a4a; padding: 16px 20px; }}
  .dna-box h2 {{ color: #c9a0ff; font-size: 16px; margin-bottom: 8px; }}
  .dna-box .dna-row {{ color: #aaa; font-size: 13px; line-height: 1.8; }}
  .dna-box .dna-row span {{ color: #e0e0e0; font-weight: 600; }}
</style>
</head>
<body>
<h1>P04 Witch - Top Ad Creatives</h1>
<div class="subtitle">Winner DNA: collection_completion + achievement + collection_bundle_purchase</div>

<div class="dna-box">
  <h2>Winner Creative DNA (Phase 4.1 Analysis)</h2>
  <div class="dna-row">
    Hook: <span>collection_completion</span> &nbsp;|&nbsp;
    Scene: <span>collection progress showcase</span> &nbsp;|&nbsp;
    Emotion: <span>achievement</span> &nbsp;|&nbsp;
    Monetization: <span>collection_bundle_purchase</span>
  </div>
  <div class="dna-row" style="margin-top: 6px">
    Visual Rules: <span>use large character as focal point, character should occupy >30% of frame</span>
  </div>
</div>

<div class="gallery">
{cards}
</div>
</body>
</html>"""

gallery_path = OUTPUT / "gallery.html"
gallery_path.write_text(html, encoding="utf-8")
print(f"\nGallery saved: {gallery_path}")
print(f"Images: {len(encoded)}")