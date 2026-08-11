"""
Lovart batch - generate remaining 3 images (flower, mystery dragon, mystery witch)
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from market_ops.clients.lovart import LovartClient, download_image

OUTPUT_DIR = ROOT / "output" / "P04_Progress_Mystery" / "images_lovart"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "generate_image_gpt_image_2"
SIZE_HINT = "square 1080x1080 pixels"

TASKS = [
    {
        "id": "progress_flower_m1",
        "prompt": (
            "3D cartoon style mobile game advertisement, "
            "plant growth evolution showing 5 stages from tiny glowing Seed "
            "to towering magnificent God Tree with golden radiant leaves and divine aura, "
            "stages shown left to right with soft magical progression glow, "
            "healing and wonder atmosphere, magical garden background with ethereal light, "
            "soft green pastel pink and radiant gold color palette, "
            "floating sparkles and flower petals, high detail, "
            "professional Facebook ad creative, no text overlay, no watermark, "
            f"{SIZE_HINT}, 1:1 ratio"
        ),
    },
    {
        "id": "mystery_dragon_m1",
        "prompt": (
            "3D cartoon style mobile game advertisement, "
            "giant glowing mysterious dragon egg with large question mark symbol on surface, "
            "dramatic cracks appearing with intense golden light bursting from inside, "
            "legendary dragon silhouette barely visible through cracks, "
            "intense mystery and anticipation atmosphere, "
            "dark mystical cave background with ancient glowing runes on walls, "
            "deep purple mysterious blue and gold light color palette, "
            "dramatic cinematic lighting, high detail, "
            "professional Facebook ad creative, no text overlay, no watermark, "
            f"{SIZE_HINT}, 1:1 ratio"
        ),
    },
    {
        "id": "mystery_witch_m1",
        "prompt": (
            "3D cartoon style mobile game advertisement, "
            "mysterious powerful witch silhouette emerging from swirling purple magical smoke, "
            "glowing question mark symbol above her head in golden light, "
            "legendary form barely visible through dramatic magical smoke, "
            "electrifying reveal mystery atmosphere, "
            "dramatic swirling magical smoke stage with ethereal spotlight from above, "
            "deep purple electric magenta and mysterious silver color palette, "
            "glowing magical particles, high detail, "
            "professional Facebook ad creative, no text overlay, no watermark, "
            f"{SIZE_HINT}, 1:1 ratio"
        ),
    },
]

def main():
    print(f"[Lovart] Generating {len(TASKS)} images with model: {MODEL}")
    client = LovartClient(mode="fast")
    results = []

    for i, task in enumerate(TASKS, 1):
        print(f"[{i}/{len(TASKS)}] {task['id']} ...")
        t0 = time.time()
        try:
            result = client.generate_image(prompt=task["prompt"], model=MODEL)
            if result.status == "done" and result.image_urls:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"lovart_{task['id']}_{ts}.png"
                dest = OUTPUT_DIR / filename
                url = result.image_urls[0]
                print(f"  Downloading: {url[:80]}...")
                download_image(url, dest)
                elapsed = time.time() - t0
                print(f"  [OK] {filename} ({elapsed:.1f}s)")
                results.append({"id": task["id"], "status": "ok", "file": str(dest), "url": url, "elapsed_sec": round(elapsed,1)})
            else:
                elapsed = time.time() - t0
                print(f"  [FAIL] status={result.status} | {result.assistant_text[:150]}")
                results.append({"id": task["id"], "status": "failed", "error": result.assistant_text[:300], "elapsed_sec": round(elapsed,1)})
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  [ERR] {e}")
            results.append({"id": task["id"], "status": "error", "error": str(e), "elapsed_sec": round(elapsed,1)})
        if i < len(TASKS):
            time.sleep(2)

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n[Lovart] Done: {ok}/{len(TASKS)} OK")
    log = OUTPUT_DIR / f"run_lovart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results

if __name__ == "__main__":
    main()
