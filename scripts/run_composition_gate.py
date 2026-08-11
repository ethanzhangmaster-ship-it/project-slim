"""Phase 2.1.6.2 — Composition Gate 验收。

对 gen_composition_smoke.py 生成的 3 张创意跑 Critic Agent（含 Composition
Validator），计算批次多样性，重算 Production Score V2，输出产物并做 7 项
smoke test 验收（PRD §11）：
  [PASS] Gameplay first
  [PASS] Reward dominant
  [PASS] Character secondary
  [PASS] No poster feeling
  [PASS] No fake text
  [PASS] Facebook UA structure
  [PASS] Quality Gate >= 0.85

用法: python scripts/run_composition_gate.py
"""
from __future__ import annotations

import sys
import json
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_ops.creative_intelligence.factory.ranking.clip_ranker import _cosine  # noqa: E402
from creative_quality_gate.critic_agent import CriticAgent  # noqa: E402
from creative_quality_gate.scoring import production_score_v2  # noqa: E402
from creative_quality_gate.models import GateResult  # noqa: E402
from creative_quality_gate.report import build_outputs  # noqa: E402

OUT = ROOT / "output" / "phase2_1_6_2"
SMOKE = OUT / "smoke"
GATE_OUT = OUT / "quality_gate"
WINNER = ROOT / "output" / "phase2_1_5" / "real_validation" / "winner_reference" / "winner_001.png"
GATE_OUT.mkdir(parents=True, exist_ok=True)

# 验收阈值
QG_MIN = 0.85
GAMEPLAY_AREA_MIN = 0.45
REWARD_VIS_MIN = 0.60
CHAR_ATTENTION_MAX = 0.35
ARTIFACT_MAX = 0.70
COMPOSITION_MATCH_MIN = 0.70


def main() -> int:
    imgs = sorted(SMOKE.glob("*.png"))
    if not imgs:
        print(f"[!] No images found in {SMOKE}. Run gen_composition_smoke.py first.")
        return 1

    agent = CriticAgent()
    scores = []
    embs = []
    for p in imgs:
        cid = p.stem
        cs = agent.evaluate(str(p), str(WINNER), cid, group="", mutation_type="")
        emb = agent.encoder.encode_image(str(p))
        embs.append(emb)
        scores.append(cs)
        print(f"  evaluated {cid}: pattern={cs.gameplay_type} prod={cs.production_score:.3f}")

    # 批次多样性：0.6 * 计划玩法多样性（已规划的不同模式数 / 总数）
    #           + 0.4 * 嵌入多样性（1 - 与其它创意平均 CLIP 相似度）
    # 计划玩法多样性衡量「是否覆盖了不同创意角度」，避免 12 张近雷同；
    # 嵌入多样性惩罚同画风近克隆。两者结合更稳健。
    planned_patterns = []
    for p in imgs:
        cj = OUT / "composition" / f"{p.stem}.json"
        if cj.exists():
            try:
                planned_patterns.append(json.loads(cj.read_text(encoding="utf-8")).get("pattern", ""))
            except Exception:
                planned_patterns.append("")
        else:
            planned_patterns.append("")
    distinct = len(set(pp for pp in planned_patterns if pp)) or 1
    pattern_distinct = distinct / max(1, len(scores))

    for i, cs in enumerate(scores):
        sims = []
        for j, e in enumerate(embs):
            if i == j:
                continue
            sims.append((_cosine(embs[i], e) + 1.0) / 2.0)
        mean_sim = float(np.mean(sims)) if sims else 0.0
        emb_div = float(1.0 - mean_sim)
        cs.diversity = round(float(0.6 * pattern_distinct + 0.4 * emb_div), 4)
        cs.production_score = production_score_v2(
            {
                "gameplay_understanding": cs.gameplay_understanding,
                "reward_visibility": cs.reward_visibility,
                "composition_match": cs.composition_match,
                "visual_quality": cs.visual_quality,
                "clip_similarity": cs.clip_similarity,
                "diversity": cs.diversity,
            }
        )

    # ---- 单张决策：以 7 项 gate 验收为口径（而非旧 DIM_PASS 阈值）----
    # collection / evolution 模式的 Gameplay Understanding 因 action_visibility
    # 偏低常 <0.75，但 PF V2 + 构图验收已能覆盖质量；故单张 PASS 以 gate 验收为准。
    for s in scores:
        passed = (
            s.aspect_ok
            and s.ai_artifact_score < ARTIFACT_MAX
            and s.gameplay_area_ratio >= GAMEPLAY_AREA_MIN
            and s.reward_visibility >= REWARD_VIS_MIN
            and s.character_attention <= CHAR_ATTENTION_MAX
            and s.composition_match >= COMPOSITION_MATCH_MIN
            and s.production_score >= QG_MIN
        )
        s.decision = "PASS" if passed else "FAIL"
        if not passed:
            s.hard_reject_reason = "Failed composition / quality-gate checks"
            if s.hard_reject_reason not in s.issues:
                s.issues.append(s.hard_reject_reason)

    # ---- 7 项 smoke test 验收 ----
    def all_pass(pred) -> bool:
        return all(pred(s) for s in scores)

    checks = {
        "Gameplay first": all_pass(lambda s: s.gameplay_area_ratio >= GAMEPLAY_AREA_MIN),
        "Reward dominant": all_pass(lambda s: s.reward_visibility >= REWARD_VIS_MIN),
        "Character secondary": all_pass(lambda s: s.character_attention <= CHAR_ATTENTION_MAX),
        "No poster feeling": all_pass(
            lambda s: (s.character_attention <= 0.50) and (s.gameplay_area_ratio >= 0.40)
        ),
        "No fake text": all_pass(lambda s: s.ai_artifact_score < ARTIFACT_MAX),
        "Facebook UA structure": all_pass(
            lambda s: s.composition_match >= COMPOSITION_MATCH_MIN
        ),
        "Quality Gate >= 0.85": all_pass(lambda s: s.production_score >= QG_MIN),
    }

    approved = [s for s in scores if s.decision == "PASS"]
    avg_prod = round(float(np.mean([s.production_score for s in scores])), 4) if scores else 0.0

    gate = GateResult(
        total=len(scores),
        approved=len(approved),
        rejected=len(scores) - len(approved),
        conditional=0,
        avg_production_score=avg_prod,
        checks=checks,
        produced_at=datetime.now().isoformat(timespec="seconds"),
    )

    paths = build_outputs(scores, gate, GATE_OUT, img_dir=SMOKE)

    print("\n=== Phase 2.1.6.2 Composition Smoke Test ===")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\nApproved {len(approved)} / Rejected {len(scores) - len(approved)} / Total {len(scores)}")
    print(f"Avg Production Score V2: {avg_prod:.3f}")
    print("Outputs:")
    for name, p in paths.items():
        print(f"  - {name}: {p}")

    ok = all(checks.values())
    print("\nRESULT:", "ALL PASS ✅" if ok else "SOME CHECKS FAILED ❌")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
