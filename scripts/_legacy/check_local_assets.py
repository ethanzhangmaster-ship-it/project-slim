"""Check local cached creative assets for quality."""
from PIL import Image
from pathlib import Path
import collections

def check_image(path):
    """Analyze image content quality."""
    img = Image.open(path)
    pixels = list(img.getdata())
    colors = collections.Counter(pixels)
    total = img.size[0] * img.size[1]
    dominant_pct = colors.most_common(1)[0][1] / total * 100
    return {
        "path": path,
        "size": img.size,
        "unique_colors": len(colors),
        "dominant_pct": dominant_pct,
        "file_size_kb": path.stat().st_size // 1024,
    }

# Check P04 creatives_cache
print("=== P04 creatives_cache (first 10) ===")
cache_dir = Path(r"d:\project_slim\project_slim\output\creatives_cache\P04")
for p in sorted(cache_dir.glob("*.png"))[:10]:
    r = check_image(p)
    print(f"  {p.name[:60]}...")
    print(f"    {r['size']}, {r['unique_colors']} colors, dominant={r['dominant_pct']:.0f}%, {r['file_size_kb']}KB")

# Check closed_loop images
print("\n=== closed_loop images ===")
cl_dir = Path(r"d:\project_slim\project_slim\output\closed_loop\closed_loop_20260629_184755\images")
for p in sorted(cl_dir.glob("*.png")):
    r = check_image(p)
    print(f"  {p.name[:60]}...")
    print(f"    {r['size']}, {r['unique_colors']} colors, dominant={r['dominant_pct']:.0f}%, {r['file_size_kb']}KB")

# Check winner_variations
print("\n=== winner_variations ===")
wv_dir = Path(r"d:\project_slim\project_slim\output\winner_variations\20260629_194352")
for p in sorted(wv_dir.glob("*.png")):
    r = check_image(p)
    print(f"  {p.name}: {r['size']}, {r['unique_colors']} colors, dominant={r['dominant_pct']:.0f}%, {r['file_size_kb']}KB")

# Check selected_gameplay from hybrid renderer
print("\n=== hybrid renderer selected_gameplay ===")
for gp_dir in Path(r"d:\project_slim\project_slim\output\creative_intelligence\runs").glob("*/hybrid_v132/render_*/selected_gameplay.png"):
    r = check_image(gp_dir)
    print(f"  {gp_dir.parent.name}: {r['size']}, {r['unique_colors']} colors, dominant={r['dominant_pct']:.0f}%, {r['file_size_kb']}KB")