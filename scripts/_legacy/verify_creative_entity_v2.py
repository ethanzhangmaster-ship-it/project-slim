"""Phase 1.2 Verification: Build a complete CreativeEntity from real data."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_entity_v2 import (
    CreativeEntity, PerformanceData, CreativeDNA, CreativeAsset,
    HookDNA, GameplayDNA, RewardDNA, VisualDNA, PsychologyDNA,
    CreativeLineage, GenerationHistory, GenerationRecord,
    SourceType, AttributionSource, HookType, GameplayGenre,
)
from market_ops.creative_entity_v2_adapters import (
    CreativeEntityBuilder, DNAAdapter,
)

ROOT = Path(r"d:\project_slim\project_slim")

# ═══ Build from real data ═══

# 1. Load from all_creatives_dna.json (our downloaded winners)
dna_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "all_creatives_dna.json"
entities = CreativeEntityBuilder.from_winner_dna_file(str(dna_path))
print(f"Built {len(entities)} CreativeEntities from all_creatives_dna.json")

# 2. Enrich with contrastive DNA
contrastive_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "contrastive_dna.json"
if contrastive_path.exists():
    entities = CreativeEntityBuilder.enrich_with_contrastive_dna(
        entities, str(contrastive_path)
    )
    print(f"Enriched with contrastive DNA")

# 3. Pick the best winner
winners = [e for e in entities if e.is_winner]
winners.sort(key=lambda e: e.performance.roas_d1 or 0, reverse=True)
best = winners[0]

# 4. Enrich with a generation record
best.generation.add(GenerationRecord(
    generation_id=f"gen_{best.creative_id}_v1",
    model="pil_composite",
    prompt="Hybrid Renderer V1.4",
    input_dna=best.dna.to_dict(),
    output_asset=best.asset.image_path,
    publish_status="draft",
))

# 5. Display
print(f"\n{'='*60}")
print(f"CreativeEntity V2 — Complete View")
print(f"{'='*60}")
print(f"\n[Basic]")
print(f"  creative_id: {best.creative_id}")
print(f"  project_id: {best.project_id}")
print(f"  source_type: {best.source_type}")
print(f"  is_winner: {best.is_winner}")
print(f"  is_original: {best.is_original}")
print(f"  has_image: {best.has_image}")
print(f"  has_performance: {best.has_performance}")
print(f"  has_dna: {best.has_dna}")

print(f"\n[Asset]")
print(f"  image_path: {Path(best.asset.image_path).name if best.asset.image_path else 'N/A'}")

print(f"\n[Performance]")
perf = best.performance
print(f"  spend: ${perf.spend:,.0f}" if perf.spend else "  spend: N/A")
print(f"  revenue: ${perf.revenue:,.0f}" if perf.revenue else "  revenue: N/A")
print(f"  roas_d1: {perf.roas_d1:.2f}" if perf.roas_d1 else "  roas_d1: N/A")
print(f"  installs: {perf.installs}" if perf.installs else "  installs: N/A")
print(f"  purchases: {perf.purchases}" if perf.purchases else "  purchases: N/A")
print(f"  attribution: {perf.attribution_source}")

print(f"\n[DNA]")
print(f"  hook.type: {best.dna.hook.type}")
print(f"  hook.emotion: {best.dna.hook.emotion}")
print(f"  gameplay.genre: {best.dna.gameplay.genre}")
print(f"  gameplay.mechanic: {best.dna.gameplay.mechanic}")
print(f"  reward.type: {best.dna.reward.type}")
print(f"  visual.color: {best.dna.visual.color}")
print(f"  visual.composition: {best.dna.visual.composition}")
print(f"  visual.lighting: {best.dna.visual.lighting}")
print(f"  psychology.motivation: {best.dna.psychology.motivation}")
print(f"  raw_summary: {best.dna.raw_summary[:80]}")

print(f"\n[Lineage]")
print(f"  parent: {best.lineage.parent_creative_id or '(none — original)'}")
print(f"  is_original: {best.lineage.is_original}")

print(f"\n[Generation History]")
print(f"  total: {best.generation.total_generations}")
for r in best.generation.records:
    print(f"  - {r.generation_id}: model={r.model}, status={r.publish_status}")

print(f"\n[Metadata]")
print(f"  {json.dumps(best.metadata, indent=2)}")

# 6. Full JSON
json_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "creative_entity_v2_demo.json"
with open(json_path, "w", encoding="utf-8") as f:
    f.write(best.to_json())
print(f"\n{'='*60}")
print(f"Full JSON saved to: {json_path}")
print(f"{'='*60}")

# 7. Summary
print(f"\n{best.summary()}")

# 8. Tier breakdown
from collections import Counter
tiers = Counter(e.source_type for e in entities)
winners_count = sum(1 for e in entities if e.is_winner)
print(f"\nEntity Stats:")
print(f"  Total: {len(entities)}")
print(f"  Winners (ROAS>1): {winners_count}")
print(f"  With image: {sum(1 for e in entities if e.has_image)}")
print(f"  With performance: {sum(1 for e in entities if e.has_performance)}")
print(f"  With DNA: {sum(1 for e in entities if e.has_dna)}")