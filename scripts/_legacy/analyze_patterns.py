"""Phase 1.3 Verification: Creative Intelligence Validation Layer.

Analyzes 176 CreativeEntities to discover winning patterns,
DNA performance correlations, and generate CreativeBlueprints.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_entity_v2_adapters import CreativeEntityBuilder
from market_ops.creative_validation_layer import (
    CreativeEntityIndex, WinnerPatternMiner, DNAPerformanceCorrelation,
    CreativeDecisionScorer, CreativeBlueprint,
)

ROOT = Path(r"d:\project_slim\project_slim")

# ═══ Load ═══

dna_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "all_creatives_dna.json"
entities = CreativeEntityBuilder.from_winner_dna_file(str(dna_path))

contrastive_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "contrastive_dna.json"
if contrastive_path.exists():
    entities = CreativeEntityBuilder.enrich_with_contrastive_dna(entities, str(contrastive_path))

index = CreativeEntityIndex(entities)

# ═══ Report ═══

print("=" * 65)
print("  PHASE 1.3: Creative Intelligence Validation Layer")
print("  Merge Witches — Creative Factory V2")
print("=" * 65)

# ── Section 1: Index Stats ──

print(f"\n{'─'*50}")
print("1. CreativeEntityIndex")
print(f"{'─'*50}")
s = index.stats()
print(f"  Total CreativeEntity: {s['total']}")
print(f"  Winners (ROAS>1):    {s['winners']}")
print(f"  Losers:              {s['losers']}")
print(f"  Neutrals:            {s['neutrals']}")
print(f"  With image:          {s['with_image']}")
print(f"  With performance:    {s['with_performance']}")
print(f"  With DNA:            {s['with_dna']}")
print(f"  Hook types:          {s['hook_types']}")
print(f"  Reward types:        {s['reward_types']}")
print(f"  Visual types:        {s['visual_types']}")

# ── Section 2: Top Winners ──

print(f"\n{'─'*50}")
print("2. Top 10 Winners")
print(f"{'─'*50}")
print(f"  {'Rank':<5} {'Creative ID':<18} {'ROAS':>8} {'Rev':>8} {'Spend':>8} {'Hook':<20}")
print(f"  {'─'*65}")
for i, w in enumerate(index.top_winners(10)):
    roas = w.performance.roas_d1 or 0
    rev = w.performance.revenue or 0
    spend = w.performance.spend or 0
    hook = w.dna.hook.type[:18]
    print(f"  {i+1:<5} {w.creative_id:<18} {roas:>8.2f} ${rev:>6.0f} ${spend:>6.0f} {hook:<20}")

# ── Section 3: Discovered Patterns ──

print(f"\n{'─'*50}")
print("3. Winner Patterns")
print(f"{'─'*50}")

miner = WinnerPatternMiner(index)
patterns = miner.mine()

# Group by type
for label, pattern_list in [
    ("Hook × Reward Patterns", [p for p in patterns if "hook_reward" in p.pattern_id]),
    ("Hook × Composition Patterns", [p for p in patterns if "hook_comp" in p.pattern_id]),
    ("Hook × Color Patterns", [p for p in patterns if "hook_color" in p.pattern_id]),
]:
    if not pattern_list:
        continue
    print(f"\n  [{label}]")
    print(f"  {'Pattern':<45} {'n':>4} {'ROAS':>8} {'Rev':>8}")
    print(f"  {'─'*65}")
    for p in pattern_list[:10]:
        print(f"  {p.name:<45} {p.sample_count:>4} {p.avg_roas:>8.2f} ${p.avg_revenue:>6.0f}")

# ── Section 4: DNA Performance Correlation ──

print(f"\n{'─'*50}")
print("4. DNA Performance Correlation")
print(f"{'─'*50}")

corr = DNAPerformanceCorrelation(index)
analysis = corr.analyze()

for dim_name, correlations in analysis.items():
    if not correlations:
        continue
    print(f"\n  [{dim_name.upper()}]")
    print(f"  {'Value':<25} {'n':>4} {'Avg ROAS':>10} {'Winner%':>8} {'Avg Rev':>8}")
    print(f"  {'─'*60}")
    for c in correlations[:10]:
        print(f"  {c.value:<25} {c.sample_count:>4} {c.avg_roas:>10.2f} {c.winner_rate:>7.0%} ${c.avg_revenue:>6.0f}")

# ── Section 5: Top Scored Creatives ──

print(f"\n{'─'*50}")
print("5. Creative Decision Score (Top 10)")
print(f"{'─'*50}")
scorer = CreativeDecisionScorer(index)
scores = scorer.score_all()

print(f"  {'Rank':<5} {'ID':<18} {'Total':>6} {'Perf':>6} {'Hook':>6} {'Game':>6} {'Reward':>6} {'Visual':>6}  Reasons")
print(f"  {'─'*80}")
for i, s in enumerate(scores[:10]):
    print(f"  {i+1:<5} {s.creative_id:<18} {s.total_score:>6.3f} {s.performance_score:>6.3f} "
          f"{s.hook_score:>6.3f} {s.gameplay_score:>6.3f} {s.reward_score:>6.3f} {s.visual_score:>6.3f}  "
          f"{'; '.join(s.reasons[:2])}")

# ── Section 6: Generation Blueprints (Top 3) ──

print(f"\n{'─'*50}")
print("6. Generation Blueprints for Phase 2")
print(f"{'─'*50}")

top_patterns = patterns[:3]
for i, p in enumerate(top_patterns):
    bp = CreativeBlueprint.from_pattern(p)
    print(f"\n  Blueprint {i+1}: {p.name}")
    print(f"  {'─'*40}")
    for k, v in bp.to_dict().items():
        print(f"    {k}: {v}")

# ── Summary ──

print(f"\n{'='*65}")
print("  PHASE 1.3 COMPLETE")
print(f"{'='*65}")
print(f"  Entities analyzed:  {index.total}")
print(f"  Patterns discovered: {len(patterns)}")
print(f"  DNA correlations:    {sum(len(v) for v in analysis.values())}")
print(f"  Creatives scored:    {len(scores)}")
print(f"  Blueprints ready:    {len(top_patterns)}")
print(f"\n  Next: Phase 2 — Lovart AI Creative Generator MVP")
print(f"  Input: CreativeBlueprint (NOT raw images)")
print(f"  Driver: Top patterns + decision scores")

# ── Save results ──

output = {
    "phase": "1.3",
    "index_stats": index.stats(),
    "top_winners": [
        {"creative_id": w.creative_id, "roas": w.performance.roas_d1,
         "revenue": w.performance.revenue, "spend": w.performance.spend,
         "hook": w.dna.hook.type}
        for w in index.top_winners(10)
    ],
    "patterns": [p.to_dict() for p in patterns],
    "correlations": {
        dim: [{"value": c.value, "n": c.sample_count, "avg_roas": c.avg_roas,
               "winner_rate": c.winner_rate, "avg_revenue": c.avg_revenue}
              for c in corrs]
        for dim, corrs in analysis.items()
    },
    "top_scores": [
        {"creative_id": s.creative_id, "total": s.total_score,
         "reasons": s.reasons}
        for s in scores[:10]
    ],
    "blueprints": [bp.to_dict() for bp in [CreativeBlueprint.from_pattern(p) for p in top_patterns]],
}

out_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "phase_13_validation.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n  Full report saved: {out_path}")