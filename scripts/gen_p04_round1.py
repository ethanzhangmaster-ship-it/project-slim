"""
P04 图片闭环生成 - 基于真实Winner DNA的Mutation

DNA分析结果:
- 心理驱动: Mystery(10/10) > Magic(7/10) > Progress(4/10) > Collection(3/10)
- 颜色: gray/neutral(60%) + purple(17.5%) + black(13.6%) - 暗色调
- 亮度: medium(70%) + dark(30%)
- Top文案: "Build Dark Empire! Shack→Castle→Empire" / "Lv.1→MAX! Cosmic Power"

预算分配(按project_memory):
- 70% Winner Mutation (4张) - 保留Mystery+Progress, 变化成长链
- 20% New Hook (1张) - Collection+Mystery组合
- 10% Explore (1张) - Cute+Mystery新方向
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

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

OUTPUT_DIR = ROOT / "output" / "P04_Creative_Factory" / "images_round1"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "generate_image_gpt_image_2"
SIZE_HINT = "mobile portrait 9:16 aspect ratio, 1080x1920 pixels"

# 共享DNA元素 - 基于真实winner分析
DNA_COLOR = "dominant gray and neutral tones (60%), deep purple accents (17%), black shadows (14%), subtle white highlights"
DNA_MOOD = "mysterious and magical atmosphere, medium brightness, gothic dark fantasy allure"
DNA_QUALITY = "3D cartoon style mobile game advertisement, professional Facebook ad creative quality, high detail, cinematic lighting"

# ── Mutation Prompts ───────────────────────────────────────────────────────
TASKS = [
    # === 70% Winner Mutation - 保留Mystery+Progress核心, 变化成长链 ===
    {
        "id": "mut01_empire_gothic",
        "type": "winner_mutation",
        "source": "P4-And-T1-深度挖掘-图片1-1229 ($2929, IPM 5.01)",
        "hook": "progress+mystery",
        "prompt": (
            f"{DNA_QUALITY}. "
            "Dark empire building progression chain showing 4 evolution stages from "
            "wooden hut to stone tower to gothic castle to massive dark fortress empire, "
            "connected by glowing purple magical energy streams, "
            "gargoyle guards and bat army silhouettes around the final fortress, "
            f"full moon background with dramatic purple fog, "
            f"{DNA_COLOR}, {DNA_MOOD}, "
            "glowing magical particles, no text overlay, no watermark, "
            f"{SIZE_HINT}"
        ),
    },
    {
        "id": "mut02_dragon_evolution",
        "type": "winner_mutation",
        "source": "P4-And-T1-深度挖掘-图片1-1229 variant (Lv.1→MAX Cosmic)",
        "hook": "progress+mystery",
        "prompt": (
            f"{DNA_QUALITY}. "
            "Shadow dragon evolution chain showing 5 stages from tiny cute baby dragon (Lv1) "
            "to juvenile dragon to adult dragon to elder dragon to massive divine shadow dragon (Lv MAX) with golden crown, "
            "stages arranged vertically with glowing purple progression arrows between each, "
            "each stage more majestic and darker than the previous, "
            "mystical dark arena background with ancient glowing runes, "
            f"{DNA_COLOR}, {DNA_MOOD}, "
            "dramatic purple magical particles emanating from each dragon, "
            "no text overlay, no watermark, "
            f"{SIZE_HINT}"
        ),
    },
    {
        "id": "mut03_mystery_portal",
        "type": "winner_mutation",
        "source": "P4-IOS-T1-图片6-0608 ($1669, Mystery+Magic)",
        "hook": "mystery+magic",
        "prompt": (
            f"{DNA_QUALITY}. "
            "Giant mysterious magical portal swirling with deep purple cosmic energy, "
            "large glowing ??? symbol floating above the portal in golden light, "
            "legendary creature silhouette barely visible through the swirling portal, "
            "witch character silhouette standing before the portal in awe, "
            "dramatic light bursting from portal cracks, intense mystery and anticipation, "
            "ancient stone platform with glowing runes surrounding the portal, "
            f"{DNA_COLOR}, {DNA_MOOD}, "
            "electrifying magical particles, no text overlay, no watermark, "
            f"{SIZE_HINT}"
        ),
    },
    {
        "id": "mut04_dark_castle_progress",
        "type": "winner_mutation",
        "source": "P4-And-T1-优质素材-图片5-0505 ($1590, IPM 6.79)",
        "hook": "progress+mystery",
        "prompt": (
            f"{DNA_QUALITY}. "
            "Gothic castle merge progression showing 3 upgrade stages from "
            "abandoned cottage to dark manor to magnificent gothic vampire castle, "
            "connected by glowing purple magical merge energy, "
            "mystical fog surrounding each stage, gargoyles perched on final castle, "
            "full moon and starry night sky background, "
            f"{DNA_COLOR}, {DNA_MOOD}, "
            "soft purple magical sparkles rising from each building, "
            "no text overlay, no watermark, "
            f"{SIZE_HINT}"
        ),
    },
    # === 20% New Hook - Collection + Mystery 组合 ===
    {
        "id": "new01_dark_collection",
        "type": "new_hook",
        "source": "New: Collection+Mystery combination",
        "hook": "collection+mystery",
        "prompt": (
            f"{DNA_QUALITY}. "
            "Mysterious dark creature collection display, "
            "10 shadowy magical creatures arranged in a grid floating in dark mystical space, "
            "each creature in a glowing purple summoning circle, "
            "some creatures fully visible (baby dragon, shadow wolf, crystal golem, dark fairy), "
            "others as mysterious silhouettes with ??? marks creating curiosity, "
            "central focal point: legendary creature egg with cracks glowing golden, "
            f"{DNA_COLOR}, {DNA_MOOD}, "
            "ethereal purple particles floating between creatures, "
            "no text overlay, no watermark, "
            f"{SIZE_HINT}"
        ),
    },
    # === 10% Explore - Cute + Mystery 新方向 ===
    {
        "id": "exp01_cute_mystery",
        "type": "explore",
        "source": "Explore: Cute+Mystery new direction",
        "hook": "cute+mystery",
        "prompt": (
            f"{DNA_QUALITY}. "
            "Adorable chibi baby dragon hatching from a mysterious glowing purple egg, "
            "big sparkling curious eyes looking at the viewer, "
            "egg cracks radiating golden magical light, "
            "dark mystical cave background with glowing crystals and ancient runes, "
            "tiny magical particles floating around the egg, "
            "contrast between cute baby dragon and mysterious dark environment, "
            f"{DNA_COLOR} with warm golden glow from egg, {DNA_MOOD}, "
            "no text overlay, no watermark, "
            f"{SIZE_HINT}"
        ),
    },
]


def main():
    print("="*70)
    print("  P04 Creative Factory - Round 1 Image Generation")
    print("  Based on real Winner DNA: Mystery(10/10) > Magic(7) > Progress(4)")
    print("="*70)
    print(f"\n模型: {MODEL}")
    print(f"输出: {OUTPUT_DIR}")
    print(f"任务数: {len(TASKS)} (Winner Mutation: 4, New Hook: 1, Explore: 1)\n")

    client = LovartClient(mode="fast")
    results = []

    for i, task in enumerate(TASKS, 1):
        print(f"[{i}/{len(TASKS)}] {task['id']} ({task['type']}/{task['hook']})")
        print(f"  来源: {task['source']}")
        print(f"  Prompt: {task['prompt'][:100]}...")
        t0 = time.time()

        try:
            result = client.generate_image(
                prompt=task["prompt"],
                model=MODEL,
            )

            if result.status == "done" and result.image_urls:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{task['id']}_{ts}.png"
                dest = OUTPUT_DIR / filename

                url = result.image_urls[0]
                print(f"  下载中: {url[:80]}...")
                download_image(url, dest)

                elapsed = time.time() - t0
                print(f"  [OK] 保存: {filename} ({elapsed:.1f}s)\n")
                results.append({
                    "id": task["id"],
                    "type": task["type"],
                    "hook": task["hook"],
                    "source": task["source"],
                    "status": "ok",
                    "file": str(dest),
                    "url": url,
                    "elapsed_sec": round(elapsed, 1),
                    "prompt": task["prompt"],
                })
            else:
                elapsed = time.time() - t0
                print(f"  [FAIL] status={result.status}, text={result.assistant_text[:200]}\n")
                results.append({
                    "id": task["id"],
                    "type": task["type"],
                    "hook": task["hook"],
                    "source": task["source"],
                    "status": "failed",
                    "error": result.assistant_text[:300],
                    "elapsed_sec": round(elapsed, 1),
                    "prompt": task["prompt"],
                })
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  [ERR] {e}\n")
            results.append({
                "id": task["id"],
                "type": task["type"],
                "hook": task["hook"],
                "source": task["source"],
                "status": "error",
                "error": str(e),
                "elapsed_sec": round(elapsed, 1),
                "prompt": task["prompt"],
            })

        if i < len(TASKS):
            time.sleep(3)

    # 保存运行日志
    log_path = OUTPUT_DIR / f"run_round1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    ok = sum(1 for r in results if r["status"] == "ok")
    print("="*70)
    print(f"  完成: {ok}/{len(TASKS)} 成功")
    print(f"  日志: {log_path}")
    print("="*70)
    return results


if __name__ == "__main__":
    main()
