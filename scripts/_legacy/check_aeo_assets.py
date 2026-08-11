"""Check AEO asset image content quality."""
from PIL import Image
from pathlib import Path
import collections

assets_dir = Path(r"d:\project_slim\project_slim\memory\test_7day_aeo\assets")
for p in sorted(assets_dir.glob("*.png")):
    img = Image.open(p)
    pixels = list(img.getdata())
    colors = collections.Counter(pixels)
    total = img.size[0] * img.size[1]
    dominant_pct = colors.most_common(1)[0][1] / total * 100
    top3 = [(f"RGB{c[0]}", f"{c[1]/total*100:.1f}%") for c in colors.most_common(3)]
    print(f"{p.name}: {img.size}, unique={len(colors):5d}, dominant={dominant_pct:.1f}%")
    print(f"  top3: {top3}")