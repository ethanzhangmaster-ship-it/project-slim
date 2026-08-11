"""Phase 1.6: Generation Feasibility Test.

Validates that CreativeGenerationSpecs can actually guide the
generation of Facebook ad creatives with high CTR potential.

No image generation. Only production interface quality validation.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_blueprint_validator import CreativeGenerationSpec
from market_ops.creative_generation_feasibility import (
    GenerationSpecQualityChecker,
    HumanReviewPromptGenerator,
    FeasibilityReport,
)

ROOT = Path(r"d:\project_slim\project_slim")

# ═══════════════════════════════════════════════════════════
# Load Phase 1.5 Generation Specs
# ═══════════════════════════════════════════════════════════

specs_path = ROOT / "output" / "creative_analysis" / "generation_specs.json"
with open(specs_path, "r", encoding="utf-8") as f:
    specs_data = json.load(f)

specs = [CreativeGenerationSpec.from_dict(s) for s in specs_data["specs"]]

# ═══════════════════════════════════════════════════════════
# Quality Check
# ═══════════════════════════════════════════════════════════

checker = GenerationSpecQualityChecker()
results = checker.check_all(specs)

# ═══════════════════════════════════════════════════════════
# Generate Review Prompts
# ═══════════════════════════════════════════════════════════

prompt_gen = HumanReviewPromptGenerator()
review_prompts = prompt_gen.generate_all(specs)

# ═══════════════════════════════════════════════════════════
# Build Report
# ═══════════════════════════════════════════════════════════

ready_results = [r for r in results if r.is_ready]
total_missing = sum(len(r.missing) for r in results)
avg_score = sum(r.readiness_score for r in results) / len(results) if results else 0

report = FeasibilityReport(
    total_specs=len(specs),
    ready_specs=len(ready_results),
    average_score=avg_score,
    total_missing=total_missing,
    quality_results=results,
    review_prompts=review_prompts,
    phase_2_ready=(len(ready_results) == len(specs) and total_missing == 0),
)

# ═══════════════════════════════════════════════════════════
# Print Report
# ═══════════════════════════════════════════════════════════

print(report.print_report())

# ═══════════════════════════════════════════════════════════
# Print Review Prompts
# ═══════════════════════════════════════════════════════════

if review_prompts:
    print(f"\n{'─'*50}")
    print(f"HUMAN REVIEW PROMPTS")
    print(f"{'─'*50}")
    for i, prompt in enumerate(review_prompts):
        print(f"\n{'='*55}")
        print(f"  REVIEW PROMPT #{i+1}")
        print(f"{'='*55}")
        print(prompt)

# ═══════════════════════════════════════════════════════════
# Save Results
# ═══════════════════════════════════════════════════════════

# Phase 1.6 full report
out_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "phase_16_feasibility.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

# Generation readiness (for Phase 2)
readiness_path = ROOT / "output" / "creative_analysis" / "generation_readiness.json"
readiness_data = {
    "phase": "1.6",
    "game": "merge_witches",
    "phase_2_ready": report.phase_2_ready,
    "average_score": round(avg_score, 1),
    "specs": [
        {
            "spec_id": r.spec_id,
            "readiness_score": r.readiness_score,
            "missing": r.missing,
            "is_ready": r.is_ready,
        }
        for r in results
    ],
    "review_prompts": review_prompts,
}
with open(readiness_path, "w", encoding="utf-8") as f:
    json.dump(readiness_data, f, ensure_ascii=False, indent=2)

print(f"\n  Full report saved:       {out_path}")
print(f"  Readiness data saved:    {readiness_path}")