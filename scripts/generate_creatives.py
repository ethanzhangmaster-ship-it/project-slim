"""Phase 2.1: AI Creative Generator — Production Pipeline.

8-step production pipeline:
  1. Load Winner DNA → CreativeGenerationSpecs
  2. Phase 1.6.1 V2 Ad Readiness Gate
  3. Build Lovart Prompts (variations)
  4. Submit to Lovart Task Queue
  5. Worker Pool executes generation (3 concurrent workers)
  6. Download & validate images
  7. AI Creative Quality Gate
  8. Output report + Top 5 creatives

Acceptance criteria:
  - 4 blueprints x 5 variations = 20 tasks
  - Worker pool: 3 concurrent
  - Retry: 3 attempts with 10s/30s backoff
  - NO placeholder images
  - Quality PASS >= 15
  - Average Score >= 80
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_generation_manager import CreativeGenerationManager

ROOT = Path(r"d:\project_slim\project_slim")

# ═══════════════════════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════════════════════

print("=" * 65)
print("  PHASE 2.1: Lovart Production Adapter")
print("  Merge Witches — AI Creative Factory")
print("=" * 65)

# Create manager with production config
manager = CreativeGenerationManager(
    output_dir=ROOT / "output" / "creative_analysis" / "generated_creatives",
    db_path=ROOT / "output" / "creative_analysis" / "generations.db",
    specs_path=ROOT / "output" / "creative_analysis" / "generation_specs.json",
    rules_path=ROOT / "output" / "creative_analysis" / "creative_rules.json",
    num_workers=3,
    timeout=60,
    max_retries=3,
)

print(f"  Lovart API: {'AVAILABLE' if manager.adapter_available else 'UNAVAILABLE'}")
print(f"  Workers:    3")
print(f"  Timeout:    60s")
print(f"  Retries:    3 (10s/30s backoff)")
print(f"  Mode:       {'PRODUCTION' if manager.adapter_available else 'DRY RUN (no API)'}")
print()

# ── Step 1-6: Full pipeline ──
print("Starting generation pipeline...")
print()

result = manager.generate_batch(
    variations_per_spec=5,
    wait=True,
    max_wait=600,
)

# ═══════════════════════════════════════════════════════════
# Step 8: Report
# ═══════════════════════════════════════════════════════════

print()
print(result.report())

# Save reports
v2_out = ROOT / "output" / "creative_analysis" / "dna_cache" / "phase_161_readiness_v2.json"
v2_out.parent.mkdir(parents=True, exist_ok=True)
if result.v2_report:
    with open(v2_out, "w", encoding="utf-8") as f:
        json.dump(result.v2_report.to_dict(), f, ensure_ascii=False, indent=2)

quality_out = ROOT / "output" / "creative_analysis" / "generated_creatives" / "quality_report.json"
quality_out.parent.mkdir(parents=True, exist_ok=True)
if result.quality_report:
    with open(quality_out, "w", encoding="utf-8") as f:
        json.dump(result.quality_report.to_dict(), f, ensure_ascii=False, indent=2)

# Save batch result
batch_out = ROOT / "output" / "creative_analysis" / "generated_creatives" / "batch_result.json"
with open(batch_out, "w", encoding="utf-8") as f:
    json.dump({
        "batch_id": result.batch_id,
        "total_specs": result.total_specs,
        "ready_specs": result.ready_specs,
        "prompts_built": result.prompts_built,
        "tasks_submitted": result.tasks_submitted,
        "tasks_succeeded": result.tasks_succeeded,
        "tasks_failed": result.tasks_failed,
        "quality_pass": result.quality_pass,
        "quality_review": result.quality_review,
        "quality_fail": result.quality_fail,
        "avg_quality": result.avg_quality,
        "total_cost": result.total_cost,
        "total_time": result.total_time,
        "top_creatives": result.top_creatives,
        "errors": result.errors,
    }, f, ensure_ascii=False, indent=2)

print(f"  Reports saved:")
print(f"    V2 Readiness: {v2_out}")
print(f"    Quality Gate: {quality_out}")
print(f"    Batch:        {batch_out}")

# Acceptance check
accept_passed = result.quality_pass >= 15
accept_score = result.avg_quality >= 80
accept = accept_passed and accept_score

print()
print(f"  Acceptance Criteria:")
print(f"    PASS >= 15:  {'PASS' if accept_passed else 'FAIL'} ({result.quality_pass})")
print(f"    Avg >= 80:   {'PASS' if accept_score else 'FAIL'} ({result.avg_quality:.0f})")
print(f"    ─────────────────")
print(f"    OVERALL:     {'PASS' if accept else 'FAIL'}")

if accept:
    print()
    print("  Phase 2.1 complete. Ready for human review.")
    print("  Next: Human selects top creatives → Facebook test.")
else:
    print()
    print("  Phase 2.1 needs improvement before human review.")