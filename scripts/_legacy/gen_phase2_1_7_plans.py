"""Phase 2.1.7 — Step 1: 12 Creative Composition Plans.

依据 PRD §3 Creative Matrix，把 12 张创意映射到 GameplayPattern + 物体，
调用 CompositionPlanner 生成版式规划（CreativeComposition），并导出两套产物：

  output/creative_phase2_1_7/compositions/composition_plan.json
      PRD §4 格式的 12 条版式规划（template / gameplay_area / reward_position /
      character_position / before_state / after_state / transition_element /
      attention_priority / prompt / planner 全量 dict）

  output/creative_phase2_1_7/prompts/creative_prompts.json
      12 条最终 Prompt（供 Step 3 生成脚本直接读取；人工 review 后可直接改这里）

Pattern 分配（满足 PRD §8 Batch Gate：Merge>=4 / Evolution>=3 / Collection>=3）：
  Group A Merge Reward (001-004) -> 4x MERGE
  Group B Evolution Hook (005-008) -> 4x EVOLUTION
  Group C Collection Hook (009-012) -> 4x COLLECTION
  => MERGE=4, EVOLUTION=4, COLLECTION=4  (两组口径都满足)

注：002 原文 "Dragon Evolution" 为贴合 Group A「Merge Reward」目标与 Merge>=4
硬性门槛，落地为 MERGE（两只幼龙合并 -> 成年金龙），主题仍保留龙成长。

用法: python scripts/gen_phase2_1_7_plans.py
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
from creative_composition.layout_templates import get_layout

OUT = ROOT / "output" / "creative_phase2_1_7"
COMP = OUT / "compositions"
PROMPTS = OUT / "prompts"
for d in (COMP, PROMPTS):
    d.mkdir(parents=True, exist_ok=True)

# 每张创意的基础 DNA（before / after / 主题 / 分组）
# extra: 追加到 Prompt 的强化约束（PRD §5「High-end 3D fantasy」）
EXTRA = "High-end 3D fantasy mobile game style. Polished mobile game advertisement rendering."

# transition_element 按玩法模式固定映射（PRD §4）
TRANSITION = {
    "merge": "golden_merge_arrow",
    "evolution": "evolution_glow_arrow",
    "collection": "collection_swirl",
    "reward_reveal": "reveal_flash",
}

# gameply_area 按 layout 的语义位置（人类可读）
GAMEPLAY_AREA = {
    "merge_before_after": "center",
    "evolution_upgrade": "center",
    "collection_reward": "center_right",
    "surprise_reveal": "center",
}

# 12 张创意矩阵
MATRIX = [
    # ---- Group A — Merge Reward (4) ----
    dict(cid="creative_001", group="A", theme="Dragon Egg Merge",
         pattern=GameplayPattern.MERGE, before="dragon egg", after="baby dragon",
         character="witch"),
    dict(cid="creative_002", group="A", theme="Dragon Evolution (rendered as merge)",
         pattern=GameplayPattern.MERGE, before="baby dragon", after="adult golden dragon",
         character="witch"),
    dict(cid="creative_003", group="A", theme="Magic Flower Merge",
         pattern=GameplayPattern.MERGE, before="magic flower", after="magic tree",
         character="witch"),
    dict(cid="creative_004", group="A", theme="Castle Merge",
         pattern=GameplayPattern.MERGE, before="small stone castle", after="royal castle",
         character="witch"),
    # ---- Group B — Evolution Hook (4) ----
    dict(cid="creative_005", group="B", theme="Witch Evolution",
         pattern=GameplayPattern.EVOLUTION, before="level-1 witch", after="witch queen",
         character="witch"),
    dict(cid="creative_006", group="B", theme="Creature Evolution",
         pattern=GameplayPattern.EVOLUTION, before="tiny creature", after="legendary beast",
         character="witch"),
    dict(cid="creative_007", group="B", theme="Magic Garden Evolution",
         pattern=GameplayPattern.EVOLUTION, before="empty garden", after="fantasy garden",
         character="witch"),
    dict(cid="creative_008", group="B", theme="Dark -> Light Transformation",
         pattern=GameplayPattern.EVOLUTION, before="dark forest", after="magic kingdom",
         character="witch"),
    # ---- Group C — Collection Hook (4) ----
    dict(cid="creative_009", group="C", theme="Rare Creature Collection",
         pattern=GameplayPattern.COLLECTION, before="three small creatures", after="rare dragon",
         character="witch"),
    dict(cid="creative_010", group="C", theme="Magic Item Collection",
         pattern=GameplayPattern.COLLECTION, before="multiple magical items", after="legendary artifact",
         character="witch"),
    dict(cid="creative_011", group="C", theme="Witch House Collection",
         pattern=GameplayPattern.COLLECTION, before="small house", after="wizard castle",
         character="witch"),
    dict(cid="creative_012", group="C", theme="Fantasy World Collection",
         pattern=GameplayPattern.COLLECTION, before="small island", after="magic world",
         character="witch"),
]


def _safe_name(label: str) -> str:
    import re
    return re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")


def prd4_plan(comp, meta) -> dict:
    """把 CreativeComposition 翻译成 PRD §4 版式规划字段。"""
    lay = get_layout(comp.layout_type)
    elems = comp.elements  # 值为 CompositionElement 实例
    pt = comp.pattern
    after_pos = getattr(elems.get("after_state"), "position", "") or "right"
    char_pos = getattr(elems.get("character"), "position", "") or "background_side"
    return {
        "template": f"{lay['template_letter']}_{_safe_name(lay['label'])}",
        "gameplay_area": GAMEPLAY_AREA.get(comp.layout_type, "center"),
        "reward_position": after_pos,
        "character_position": char_pos,
        "before_state": meta["before"],
        "after_state": meta["after"],
        "transition_element": TRANSITION.get(pt, "merge_arrow"),
        "attention_priority": list(comp.focus_order),
    }


def main() -> int:
    planner = CompositionPlanner()
    plans = []
    prompts_out = {}

    for m in MATRIX:
        comp = planner.plan(
            m["cid"], m["pattern"], m["before"], m["after"],
            character=m["character"], extra=EXTRA,
        )
        p4 = prd4_plan(comp, m)
        entry = {
            "creative_id": m["cid"],
            "group": m["group"],
            "theme": m["theme"],
            "pattern": comp.pattern,
            "layout_type": comp.layout_type,
            **p4,
            "prompt": comp.prompt,
            "planner": comp.to_dict(),
        }
        plans.append(entry)
        prompts_out[m["cid"]] = {
            "prompt": comp.prompt,
            "pattern": comp.pattern,
            "group": m["group"],
            "theme": m["theme"],
        }
        print(f"  [planned] {m['cid']} | group={m['group']} | {m['theme']:<28} "
              f"| {comp.pattern:<10} | template={p4['template']}")

    COMP.joinpath("composition_plan.json").write_text(
        json.dumps({"creatives": plans}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    PROMPTS.joinpath("creative_prompts.json").write_text(
        json.dumps(prompts_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 一致性自检（PRD §8 Batch Gate 的 pattern 计数）
    from collections import Counter
    cnt = Counter(p["pattern"] for p in plans)
    print("\n=== Step 1 自检 ===")
    print(f"  total plans: {len(plans)}")
    print(f"  pattern counts: {dict(cnt)}")
    ok = cnt.get("merge", 0) >= 4 and cnt.get("evolution", 0) >= 3 and cnt.get("collection", 0) >= 3
    print(f"  Batch Gate pattern floor (M>=4/E>=3/C>=3): {'PASS' if ok else 'FAIL'}")

    print("\nOutputs:")
    print(f"  - {COMP / 'composition_plan.json'}")
    print(f"  - {PROMPTS / 'creative_prompts.json'}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
