"""E9.6 End-to-End Verification Script."""
import sys
import json
from pathlib import Path

sys.path.insert(0, 'src')

from market_ops.creative_matching import MatchingEngine, run_e96_pipeline


def main():
    print('=' * 60)
    print('E9.6: Creative -> Archetype Matching Engine — E2E Verification')
    print('=' * 60)

    # Run full pipeline
    result = run_e96_pipeline()

    if result.get("status") == "error":
        print(f"\nERROR: {result.get('message')}")
        return

    # Summary
    summary = result["summary"]
    print(f"\n--- Pipeline Summary ---")
    print(f"Total creatives analyzed: {summary['total_creatives']}")
    print(f"Avg expected LTV: ${summary['avg_expected_ltv']}")
    print(f"Avg expected payer_rate: {summary['avg_expected_payer_rate']}")
    print(f"Avg expected D30 retention: {summary['avg_expected_d30_retention']}")
    print(f"Avg IAP potential: {summary['avg_iap_potential']}")

    print(f"\nPrimary archetype distribution:")
    for arch, count in sorted(summary['primary_archetype_distribution'].items(), key=lambda x: -x[1]):
        pct = count / summary['total_creatives'] * 100
        print(f"  {arch}: {count} ({pct:.1f}%)")

    print(f"\n--- Top 5 Highest Expected LTV Creatives ---")
    for c in summary['top_ltv_creatives']:
        print(f"  {c['creative_id']}: {c['genome'][:50]}...")
        print(f"    primary={c['primary_archetype']}, LTV=${c['expected_ltv']}, payer_rate={c['expected_payer_rate']}")

    print(f"\n--- Top 5 Highest IAP Potential Creatives ---")
    for c in summary['top_iap_creatives']:
        print(f"  {c['creative_id']}: {c['genome'][:50]}...")
        print(f"    primary={c['primary_archetype']}, IAP={c['iap_potential']}, LTV=${c['expected_ltv']}")

    print(f"\n--- Export Files ---")
    for k, v in result['export_paths'].items():
        size_kb = Path(v).stat().st_size / 1024 if Path(v).exists() else 0
        print(f"  {k}: {v} ({size_kb:.1f} KB)")

    # Verify output files
    print(f"\n--- Output File Verification ---")
    pred_path = Path(result['export_paths']['creative_prediction'])
    rank_path = Path(result['export_paths']['creative_archetype_rank'])

    with open(pred_path, 'r', encoding='utf-8') as f:
        preds = json.load(f)
    print(f"  creative_prediction.json: {len(preds)} entries")

    # Check sample prediction
    if preds:
        sample = preds[0]
        print(f"  Sample prediction:")
        print(f"    creative_id: {sample['creative_id']}")
        print(f"    primary_archetype: {sample['primary_archetype']}")
        print(f"    expected LTV: ${sample['expected']['ltv']}")
        for arch, p in sample['prediction'].items():
            print(f"      {arch}: prob={p['adjusted_probability']}, LTV=${p['expected_metrics']['ltv']}")

    with open(rank_path, 'r', encoding='utf-8') as f:
        ranks = json.load(f)
    print(f"\n  creative_archetype_rank.json: {len(ranks)} ranking categories")
    for cat, entries in ranks.items():
        print(f"    {cat}: {len(entries)} entries")

    print(f"\n=== E9.6 Verification PASSED ===")


if __name__ == '__main__':
    main()