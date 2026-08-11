"""
Lovart batch image generation for P04 Progress & Mystery winners.
Uses the existing LovartClient with AK/SK from .env
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Add src to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from market_ops.clients.lovart import LovartClient, download_image

# ── Config ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = ROOT / "output" / "P04_Progress_Mystery" / "images_lovart"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Which model to use
MODEL = "generate_image_gpt_image_2"  # or generate_image_nano_banana

# Size hint in prompt (Lovart doesn't have direct size param, we embed it)
SIZE_HINT = "square 1080x1080 pixels"

# ── Prompts: one representative per winner ──────────────────────────────────
TASKS = [
    {
        "id": "progress_dragon_m1",
        "winner": "progress_dragon_chain",
        "prompt": (
            "3D cartoon style mobile game advertisement, "
            "dragon evolution chain showing 5 stages from tiny cute Baby Dragon (Lv1) "
            "to massive majestic God Dragon (Lv100) with golden crown, "
            "stages arranged left to right with glowing progression arrows between each, "
            "awe-inspiring atmosphere, glowing mystical arena background, "
            "deep purple and royal gold color palette, "
            "magical particles and sparkles, high detail, "
            "professional Facebook ad creative, no text overlay, no watermark, "
            f"{SIZE_HINT}, 1:1 ratio"
        ),
    },
    {
        "id": "progress_flower_m1",
        "winner": "progress_flower_chain",
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
        "winner": "mystery_secret_dragon",
        "prompt": (
            "3D cartoon style mobile game advertisement, "
            "giant glowing mysterious dragon egg with large ??? symbol on surface, "
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
        "winner": "mystery_secret_witch",
        "prompt": (
            "3D cartoon style mobile game advertisement, "
            "mysterious powerful witch silhouette emerging from swirling purple magical smoke, "
            "glowing ??? symbol above her head in golden light, "
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
    print(f"[Lovart Batch] Starting generation of {len(TASKS)} images")
    print(f"[Lovart Batch] Model: {MODEL}")
    print(f"[Lovart Batch] Output: {OUTPUT_DIR}")
    print()

    client = LovartClient(mode="fast")
    results = []

    for i, task in enumerate(TASKS, 1):
        print(f"[{i}/{len(TASKS)}] Generating: {task['id']} ...")
        t0 = time.time()

        try:
            result = client.generate_image(
                prompt=task["prompt"],
                model=MODEL,
            )

            if result.status == "done" and result.image_urls:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"lovart_{task['id']}_{ts}.png"
                dest = OUTPUT_DIR / filename

                # Download
                url = result.image_urls[0]
                print(f"  Downloading from: {url[:80]}...")
                download_image(url, dest)

                elapsed = time.time() - t0
                print(f"  [OK] Saved: {filename} ({elapsed:.1f}s)")
                results.append({
                    "id": task["id"],
                    "winner": task["winner"],
                    "status": "ok",
                    "file": str(dest),
                    "url": url,
                    "elapsed_sec": round(elapsed, 1),
                })
            else:
                elapsed = time.time() - t0
                print(f"  [FAIL] status={result.status}, text={result.assistant_text[:200]}")
                results.append({
                    "id": task["id"],
                    "winner": task["winner"],
                    "status": "failed",
                    "error": result.assistant_text[:300],
                    "elapsed_sec": round(elapsed, 1),
                })
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  [ERR] Exception: {e}")
            results.append({
                "id": task["id"],
                "winner": task["winner"],
                "status": "error",
                "error": str(e),
                "elapsed_sec": round(elapsed, 1),
            })

        # Small pause between requests
        if i < len(TASKS):
            time.sleep(2)

    # Save run log
    log_path = OUTPUT_DIR / f"run_lovart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n[Lovart Batch] Done: {ok}/{len(TASKS)} succeeded")
    print(f"[Lovart Batch] Log: {log_path}")
    return results

if __name__ == "__main__":
    main()
