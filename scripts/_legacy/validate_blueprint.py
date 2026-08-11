"""Phase 1.5: Creative Blueprint Reality Check.

Validates that ProductionRules → CreativeGenerationSpecs can
actually describe a real Facebook IAP game creative.

No image generation. Only production requirement definition validation.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_causality_validator import ProductionRules
from market_ops.creative_blueprint_validator import (
    CreativeBlueprintValidator,
    GenerationSpecBuilder,
    BlueprintCompletenessReport,
    CreativeGenerationSpec,
)

ROOT = Path(r"d:\project_slim\project_slim")

# ═══════════════════════════════════════════════════════════
# Load Phase 1.4 Production Rules
# ═══════════════════════════════════════════════════════════

rules_path = ROOT / "output" / "creative_analysis" / "creative_rules.json"
with open(rules_path, "r", encoding="utf-8") as f:
    rules_data = json.load(f)
rules = ProductionRules.from_dict(rules_data)

# Also load Phase 1.4 data for winner pattern count
phase14_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "phase_14_causality.json"
total_winner_patterns = 24  # default
if phase14_path.exists():
    with open(phase14_path, "r", encoding="utf-8") as f:
        phase14 = json.load(f)
    total_winner_patterns = phase14.get("global", {}).get("winners", 24)

# ═══════════════════════════════════════════════════════════
# Build Generation Specs from Rules
# ═══════════════════════════════════════════════════════════

builder = GenerationSpecBuilder()
specs = builder.build(rules)

# ═══════════════════════════════════════════════════════════
# Validate Each Spec
# ═══════════════════════════════════════════════════════════

validator = CreativeBlueprintValidator()
results = validator.validate_all(specs)

# ═══════════════════════════════════════════════════════════
# Build Report
# ═══════════════════════════════════════════════════════════

ready_specs = [s for s, r in zip(specs, results) if r.is_ready]
generation_prompts = [s.to_generation_prompt() for s in ready_specs]

not_ready = [r for r in results if not r.is_ready]

report = BlueprintCompletenessReport(
    total_winner_patterns=total_winner_patterns,
    specs_generated=len(specs),
    ready_for_generation=len(ready_specs),
    missing_gameplay=sum(1 for r in results if not r.gameplay_complete),
    missing_reward=sum(1 for r in results if not r.reward_complete),
    missing_hook=sum(1 for r in results if not r.hook_complete),
    missing_visual=sum(1 for r in results if not r.visual_complete),
    validation_results=results,
    ready_specs=ready_specs,
    generation_prompts=generation_prompts,
)

# ═══════════════════════════════════════════════════════════
# Print Report
# ═══════════════════════════════════════════════════════════

print(report.print_report())

# ═══════════════════════════════════════════════════════════
# Print Generation Prompts (for ready specs)
# ═══════════════════════════════════════════════════════════

if generation_prompts:
    print(f"\n{'─'*50}")
    print(f"GENERATION PROMPTS (Phase 2 Input)")
    print(f"{'─'*50}")
    for i, prompt in enumerate(generation_prompts):
        print(f"\n{'='*55}")
        print(f"  PROMPT #{i+1}")
        print(f"{'='*55}")
        print(prompt)

# ═══════════════════════════════════════════════════════════
# Save Results
# ═══════════════════════════════════════════════════════════

out_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "phase_15_blueprint_check.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

# Save generation specs for Phase 2
specs_path = ROOT / "output" / "creative_analysis" / "generation_specs.json"
specs_data = {
    "phase": "1.5",
    "game": "merge_witches",
    "total_specs": len(specs),
    "ready_specs": len(ready_specs),
    "specs": [s.to_dict() for s in ready_specs],
    "generation_prompts": generation_prompts,
}
with open(specs_path, "w", encoding="utf-8") as f:
    json.dump(specs_data, f, ensure_ascii=False, indent=2)

print(f"\n  Full report saved:      {out_path}")
print(f"  Generation specs saved: {specs_path}")