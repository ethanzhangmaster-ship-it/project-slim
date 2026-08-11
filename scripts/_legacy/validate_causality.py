"""Phase 1.4: Creative Causality Validation.

Validates that Phase 1.3 patterns have genuine production value,
not just survivorship bias or sample-size artifacts.

Answers:
  1. Is high ROAS really from DNA, or just small sample size?
  2. Which factors should enter AI Creative Generator?
  3. Which factors are only surface correlations?
"""

import json
import sys
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_entity_v2_adapters import CreativeEntityBuilder
from market_ops.creative_validation_layer import (
    CreativeEntityIndex, WinnerPatternMiner, DNAPerformanceCorrelation,
)
from market_ops.creative_causality_validator import (
    PatternConfidenceAnalyzer, PatternConfidence,
    WinnerVsLoserContrast, DNAContrast,
    DNAImpactScorer, DNAImpactScore,
    CreativeBlueprintV2, GameplayRequirement, VisualRequirement,
    ProductionRules,
)

ROOT = Path(r"d:\project_slim\project_slim")

# ═══════════════════════════════════════════════════════════
# Load Data
# ═══════════════════════════════════════════════════════════

dna_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "all_creatives_dna.json"
entities = CreativeEntityBuilder.from_winner_dna_file(str(dna_path))

contrastive_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "contrastive_dna.json"
if contrastive_path.exists():
    entities = CreativeEntityBuilder.enrich_with_contrastive_dna(entities, str(contrastive_path))

index = CreativeEntityIndex(entities)

# ── Global stats ──
all_roas = [e.performance.roas_d1 for e in entities
            if e.performance.roas_d1 is not None and e.performance.roas_d1 > 0]
global_avg_roas = statistics.mean(all_roas) if all_roas else 0
global_roas_std = statistics.stdev(all_roas) if len(all_roas) > 1 else 0

# ═══════════════════════════════════════════════════════════
# Phase 1.3 Recap: Patterns & Correlations
# ═══════════════════════════════════════════════════════════

miner = WinnerPatternMiner(index)
patterns = miner.mine()
corr_analyzer = DNAPerformanceCorrelation(index)
correlations = corr_analyzer.analyze()

# ═══════════════════════════════════════════════════════════
# Phase 1.4 Module 1: Pattern Confidence Analyzer
# ═══════════════════════════════════════════════════════════

confidence_analyzer = PatternConfidenceAnalyzer(
    global_avg_roas=global_avg_roas,
    global_roas_std=global_roas_std,
)
confidences = confidence_analyzer.analyze(patterns)

# ═══════════════════════════════════════════════════════════
# Phase 1.4 Module 2: Winner vs Loser Contrast
# ═══════════════════════════════════════════════════════════

contrast_analyzer = WinnerVsLoserContrast(index)
contrasts = contrast_analyzer.analyze()

# ═══════════════════════════════════════════════════════════
# Phase 1.4 Module 3: DNA Impact Score
# ═══════════════════════════════════════════════════════════

impact_scorer = DNAImpactScorer(global_avg_roas=global_avg_roas)
impact_scores = impact_scorer.score(confidences, contrasts)

# ═══════════════════════════════════════════════════════════
# Phase 1.4 Module 4: CreativeBlueprintV2
# ═══════════════════════════════════════════════════════════

def build_blueprint_v2(score: DNAImpactScore) -> CreativeBlueprintV2:
    """Build a CreativeBlueprintV2 from a DNAImpactScore."""
    gameplay = GameplayRequirement()
    if score.dna_dimension == "hook":
        if "character" in score.dna_value:
            gameplay.need_character = True
        if "merge" in score.dna_value or "upgrade" in score.dna_value:
            gameplay.need_progression = True
            gameplay.need_merge_board = True
        if "evolution" in score.dna_value:
            gameplay.need_progression = True
    if "showcase" in score.dna_value:
        gameplay.need_reward_visible = True

    visual = VisualRequirement()
    if score.dna_dimension == "composition":
        visual.composition = score.dna_value
    if score.dna_dimension == "color":
        visual.color = score.dna_value

    # Build reason
    reason = (
        f"Historical ROAS pattern #{score.dna_value}\n"
        f"Confidence {score.confidence}\n"
        f"Impact {score.impact_score}"
    )

    return CreativeBlueprintV2(
        source_pattern=f"{score.dna_dimension}:{score.dna_value}",
        confidence=score.confidence,
        impact_score=score.impact_score,
        gameplay_requirement=gameplay,
        visual_requirement=visual,
        generation_reason=reason,
    )

blueprints_v2 = []
for s in impact_scores:
    if s.decision == "GENERATE":
        blueprints_v2.append(build_blueprint_v2(s))

# ═══════════════════════════════════════════════════════════
# Phase 1.4 Module 5: Production Rules
# ═══════════════════════════════════════════════════════════

production_rules = ProductionRules.from_impact_scores(
    project="merge_witches",
    scores=impact_scores,
    contrasts=contrasts,
)

# ═══════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════

print("=" * 65)
print("  PHASE 1.4: Creative Causality Validation")
print("  Merge Witches — Creative Factory V2")
print("=" * 65)

print(f"\n{'─'*50}")
print("GLOBAL:")
print(f"{'─'*50}")
print(f"  Creative Count:     {index.total}")
print(f"  Winners:            {index.winner_count}")
print(f"  Global Avg ROAS:    {global_avg_roas:.3f}")
print(f"  Global ROAS Std:    {global_roas_std:.3f}")

# ── Module 1: Pattern Confidence ──

print(f"\n{'─'*50}")
print("MODULE 1: Pattern Confidence Analysis")
print(f"{'─'*50}")
print(f"  {'Pattern':<45} {'n':>4} {'ROAS':>8} {'Lift':>6} {'Conf':>6} {'Rec':>6}")
print(f"  {'─'*75}")
for c in confidences[:15]:
    print(f"  {c.pattern_name:<45} {c.sample_size:>4} {c.avg_roas:>8.2f} "
          f"{c.lift_vs_global:>6.2f}x {c.confidence:>6.3f} {c.recommendation:>6}")
    if c.reasons:
        print(f"    {'':>45} → {', '.join(c.reasons)}")

# ── Module 2: Winner vs Loser Contrast ──

print(f"\n{'─'*50}")
print("MODULE 2: Winner vs Loser Contrast")
print(f"{'─'*50}")

for dim_name, dim_contrasts in contrasts.items():
    if not dim_contrasts:
        continue
    print(f"\n  [{dim_name.upper()}]")
    print(f"  {'Value':<25} {'W%':>6} {'L%':>6} {'Odds':>6} {'Verdict':<12}")
    print(f"  {'─'*55}")
    for c in dim_contrasts[:12]:
        print(f"  {c.value:<25} {c.winner_rate:>6.0%} {c.loser_rate:>6.0%} "
              f"{c.odds_ratio:>6.2f} {c.verdict:<12}")

# ── Module 3: DNA Impact Score ──

print(f"\n{'─'*50}")
print("MODULE 3: DNA Impact Score")
print(f"{'─'*50}")
print(f"  {'Dim':<15} {'Value':<25} {'Impact':>7} {'Lift':>6} {'Conf':>6} {'Sample':>6} {'Contrast':>7} {'Decision':>10}")
print(f"  {'─'*88}")
for s in impact_scores[:20]:
    dim = s.dna_dimension[:15] if s.dna_dimension else "unknown"
    print(f"  {dim:<15} {s.dna_value:<25} {s.impact_score:>7.3f} "
          f"{s.roas_lift:>6.3f} {s.confidence:>6.3f} {s.sample_weight:>6.3f} "
          f"{s.contrast_odds:>7.3f} {s.decision:>10}")

# ── Module 4: CreativeBlueprintV2 ──

print(f"\n{'─'*50}")
print("MODULE 4: CreativeBlueprintV2 (Phase 2 Input)")
print(f"{'─'*50}")
for i, bp in enumerate(blueprints_v2[:5]):
    print(f"\n  Blueprint V2 #{i+1}: {bp.source_pattern}")
    print(f"    Confidence: {bp.confidence}")
    print(f"    Impact:     {bp.impact_score}")
    print(f"    Gameplay:   {bp.gameplay_requirement.to_dict()}")
    print(f"    Visual:     {bp.visual_requirement.to_dict()}")
    print(f"    Reason:     {bp.generation_reason.split(chr(10))[0]}")

# ── Module 5: Production Rules ──

print(f"\n{'─'*50}")
print("MODULE 5: Validated Production Rules")
print(f"{'─'*50}")

print(f"\n  Project: {production_rules.project}")
print(f"  Preferred Hooks:   {production_rules.preferred_hooks}")
print(f"  Preferred Layouts: {production_rules.preferred_layouts}")
print(f"  Preferred Colors:  {production_rules.preferred_colors}")
print(f"  Avoid:             {production_rules.avoid}")

print(f"\n  Validated Rules ({len(production_rules.rules)}):")
for r in production_rules.rules:
    print(f"    {r['rule_id']:<10} {r['dimension']:<15} {r['value']:<25} "
          f"confidence:{r['confidence']:.2f}  impact:{r['impact_score']:.2f}  "
          f"decision:{r['decision']}")

# ── Summary ──

print(f"\n{'='*65}")
print("  PHASE 1.4 COMPLETE — Creative Causality Validation")
print(f"{'='*65}")
print(f"  Patterns analyzed:        {len(confidences)}")
print(f"  USE:                      {sum(1 for c in confidences if c.recommendation == 'USE')}")
print(f"  TEST:                     {sum(1 for c in confidences if c.recommendation == 'TEST')}")
print(f"  SKIP:                     {sum(1 for c in confidences if c.recommendation == 'SKIP')}")
print(f"  Contrast dimensions:      {len(contrasts)}")
print(f"  DNA impact scores:        {len(impact_scores)}")
print(f"  GENERATE decisions:       {sum(1 for s in impact_scores if s.decision == 'GENERATE')}")
print(f"  BlueprintV2 ready:        {len(blueprints_v2)}")
print(f"  Production rules:         {len(production_rules.rules)}")
print(f"\n  Next: Phase 2 — Gameplay Generator MVP")
print(f"  Input: CreativeBlueprintV2 (NOT raw images)")
print(f"  Driver: Validated production rules with confidence scores")

# ═══════════════════════════════════════════════════════════
# Save Results
# ═══════════════════════════════════════════════════════════

output = {
    "phase": "1.4",
    "global": {
        "creative_count": index.total,
        "winners": index.winner_count,
        "losers": index.loser_count,
        "avg_roas": round(global_avg_roas, 4),
        "roas_std": round(global_roas_std, 4),
    },
    "module_1_pattern_confidence": [
        {
            "pattern": c.pattern_name,
            "sample_size": c.sample_size,
            "avg_roas": round(c.avg_roas, 4),
            "confidence": c.confidence,
            "lift_vs_global": c.lift_vs_global,
            "recommendation": c.recommendation,
            "reasons": c.reasons,
        }
        for c in confidences
    ],
    "module_2_winner_loser_contrast": {
        dim: [
            {
                "dimension": c.dimension,
                "value": c.value,
                "winner_count": c.winner_count,
                "loser_count": c.loser_count,
                "winner_rate": c.winner_rate,
                "loser_rate": c.loser_rate,
                "odds_ratio": c.odds_ratio,
                "is_significant": c.is_significant,
                "verdict": c.verdict,
            }
            for c in dim_contrasts
        ]
        for dim, dim_contrasts in contrasts.items()
    },
    "module_3_dna_impact": [
        {
            "dimension": s.dna_dimension,
            "value": s.dna_value,
            "impact_score": s.impact_score,
            "roas_lift": s.roas_lift,
            "confidence": s.confidence,
            "sample_weight": s.sample_weight,
            "contrast_odds": s.contrast_odds,
            "decision": s.decision,
        }
        for s in impact_scores
    ],
    "module_4_blueprints_v2": [bp.to_dict() for bp in blueprints_v2],
    "module_5_production_rules": production_rules.to_dict(),
}

out_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "phase_14_causality.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n  Full report saved: {out_path}")

# ── Save creative_rules.json ──

rules_path = ROOT / "output" / "creative_analysis" / "creative_rules.json"
with open(rules_path, "w", encoding="utf-8") as f:
    json.dump(production_rules.to_dict(), f, ensure_ascii=False, indent=2)
print(f"  Production rules saved: {rules_path}")