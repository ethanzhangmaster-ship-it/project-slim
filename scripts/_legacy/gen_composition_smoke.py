"""Phase 2.1.6.2 — Composition Smoke Test 生成。

用 Composition Planner 规划 3 张创意版式，再调 Lovart 生成：
  - 001 MERGE      : egg + egg -> baby dragon
  - 002 EVOLUTION  : small witch -> powerful witch queen
  - 003 COLLECTION : flowers -> magic tree

产物：
  output/phase2_1_6_2/smoke/creative_00X.png
  output/phase2_1_6_2/composition/creative_00X.json   （版式规划）
  output/phase2_1_6_2/prompts/creative_00X.txt        （最终 Prompt）

用法: python scripts/gen_composition_smoke.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from creative_prompting.gameplay_pattern import GameplayPattern
from creative_composition.planner import CompositionPlanner
from market_ops.clients.lovart import LovartClient, download_image

OUT = ROOT / "output" / "phase2_1_6_2"
SMOKE = OUT / "smoke"
COMP = OUT / "composition"
PROMPTS = OUT / "prompts"
for d in (SMOKE, COMP, PROMPTS):
    d.mkdir(parents=True, exist_ok=True)

WINNER = ROOT / "output" / "phase2_1_5" / "real_validation" / "winner_reference" / "winner_001.png"
attachments = [str(WINNER)] if WINNER.exists() else None

# 3 张 smoke test 规划（PRD §11）
PLAN: list[tuple[str, GameplayPattern, str, str, str]] = [
    ("creative_001", GameplayPattern.MERGE, "dragon egg", "baby dragon", "witch"),
    ("creative_002", GameplayPattern.EVOLUTION, "small level-1 witch", "powerful witch queen", "witch"),
    ("creative_003", GameplayPattern.COLLECTION, "many small glowing flowers", "magic tree", "witch"),
]

planner = CompositionPlanner()
client = LovartClient()

for cid, pattern, before, after, character in PLAN:
    comp = planner.plan(cid, pattern, before, after, character=character)
    (COMP / f"{cid}.json").write_text(
        json.dumps(comp.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PROMPTS / f"{cid}.txt").write_text(comp.prompt, encoding="utf-8")

    print("=" * 70)
    print(f"{cid}  | layout={comp.layout_type}  pattern={comp.pattern}")
    print("=" * 70)
    print(comp.prompt[:500], "...\n")

    print(f"[{cid}] submitting to Lovart ...")
    result = client.generate_image(comp.prompt, attachments=attachments)
    print(f"  status={result.status} images={len(result.image_urls)} elapsed={result.elapsed_sec:.1f}s")
    if not result.image_urls:
        print("  [!] NO IMAGE —", result.assistant_text[:300])
        continue
    dest = SMOKE / f"{cid}.png"
    download_image(result.image_urls[0], dest)
    print(f"  saved -> {dest}")

print("\nALL DONE. Compositions + prompts + images in output/phase2_1_6_2/")
