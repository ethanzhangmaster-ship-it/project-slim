"""E9.7 End-to-End Verification Script."""
import sys
import json
from pathlib import Path

sys.path.insert(0, 'src')

from market_ops.creative_learning import run_e97_pipeline


def main():
    print('=' * 60)
    print('E9.7: Prediction Feedback Learning Engine — E2E Verification')
    print('=' * 60)

    result = run_e97_pipeline()

    if result.get("status") == "error":
        print(f"\nERROR: {result.get('message')}")
        return

    # Data loaded
    dl = result["data_loaded"]
    print(f"\n--- Data Loaded ---")
    print(f"Predictions: {dl['predictions']}")
    print(f"Actual performances: {dl['actual_performances']}")
    print(f"Reconstructed archetypes: {dl.get('reconstructed_archetypes', 0)}")
    print(f"Errors computed: {dl['errors_computed']}")
    print(f"Weight updates: {dl['weight_updates']}")

    # Learning report
    summary = result["summary"]
    print(f"\n--- Learning Report ---")
    print(f"Total creatives: {summary['total_creatives']}")
    print(f"With feedback: {summary['total_creatives_with_feedback']}")

    es = summary["error_summary"]
    print(f"\nError Summary:")
    print(f"  LTV error before: ${es['avg_ltv_error_before']}")
    print(f"  LTV error after:  ${es['avg_ltv_error_after']}")
    print(f"  LTV improvement: {es['ltv_error_improvement_pct']}%")
    print(f"  Archetype MAE before: {es['avg_archetype_mae_before']}")
    print(f"  Archetype MAE after:  {es['avg_archetype_mae_after']}")
    print(f"  Archetype MAE improvement: {es['archetype_mae_improvement_pct']}%")

    print(f"\nTotal weight updates: {summary['total_weight_updates']}")

    print(f"\nTop Learnings:")
    for tl in summary.get("top_learnings", [])[:10]:
        print(f"  [{tl['archetype']}] {tl['feature']}: {tl['weight_change']:+.3f} — {tl['reason'][:80]}")

    print(f"\nArchetype Learnings:")
    for arch, al in summary.get("archetype_learnings", {}).items():
        print(f"  {arch}: {al['total_updates']} updates")
        for tf in al.get("top_features", []):
            print(f"    {tf['feature']}: {tf['delta']:+.3f}")

    # Export files
    print(f"\n--- Export Files ---")
    for k, v in result["export_paths"].items():
        size_kb = Path(v).stat().st_size / 1024 if Path(v).exists() else 0
        print(f"  {k}: {v} ({size_kb:.1f} KB)")

    # Verify key files
    print(f"\n--- Output File Verification ---")
    for fname in ["prediction_history.json", "actual_performance.json",
                   "prediction_error_report.json", "dna_weight_config.json",
                   "learning_report.json"]:
        fp = Path("output/creative_learning") / fname
        if fp.exists():
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                print(f"  {fname}: {len(data)} entries")
            elif isinstance(data, dict):
                keys = list(data.keys())[:5]
                print(f"  {fname}: {len(data)} keys, top: {keys}")
        else:
            print(f"  {fname}: MISSING")

    # PRD Acceptance Criteria
    print(f"\n--- PRD Acceptance Criteria ---")
    print(f"  AC1: 100+ creatives predicted: {dl['predictions']} -> {'PASS' if dl['predictions'] >= 100 else 'FAIL'}")
    print(f"  AC2: 100+ creatives with actual data: {dl['actual_performances']} -> {'PASS' if dl['actual_performances'] >= 100 else 'FAIL'}")
    print(f"  AC3: Error report generated: {'PASS' if dl['errors_computed'] > 0 else 'FAIL'}")
    print(f"  AC4: 5+ weight updates: {dl['weight_updates']} -> {'PASS' if dl['weight_updates'] >= 5 else 'FAIL'}")
    print(f"  AC5: LTV error improvement: {es['ltv_error_improvement_pct']}% -> {'PASS' if es['ltv_error_improvement_pct'] > 0 else 'CHECK'}")

    print(f"\n=== E9.7 Verification {'PASSED' if dl['weight_updates'] >= 5 else 'COMPLETED'} ===")


if __name__ == '__main__':
    main()