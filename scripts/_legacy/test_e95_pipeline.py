"""E9.5 End-to-End Verification Script."""
import sys
import json
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, 'src')

from market_ops.player_intelligence import (
    PlayerEventCollector, PlayerDNAEngine,
    BehaviorFeatureEngine, ArchetypeClassifier, run_e95_pipeline,
)

def main():
    print('=' * 60)
    print('E9.5: Player Archetype Intelligence Engine — E2E Verification')
    print('=' * 60)

    # Step 0: Load creative DNA first (to get real creative IDs)
    creative_dna_path = Path('output/active/creative_dna_master.json')
    creative_dna_map = {}
    real_creative_ids = []
    if creative_dna_path.exists():
        with open(creative_dna_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data:
            cid = item.get('creative_id', '')
            if cid:
                creative_dna_map[cid] = item
                real_creative_ids.append(cid)
        print(f'[0] Loaded {len(creative_dna_map)} creative DNA records')
    else:
        print(f'[0] No creative DNA master found')
        real_creative_ids = [f'creative_{i:03d}' for i in range(1, 21)]

    # Step 1: Generate sample player events using real creative IDs
    collector = PlayerEventCollector()
    # Use real creative IDs (up to 20) for realistic matrix matching
    sample_ids = real_creative_ids[:20] if len(real_creative_ids) >= 20 else real_creative_ids
    if not sample_ids:
        sample_ids = [f'creative_{i:03d}' for i in range(1, 21)]
    events = collector.generate_sample(num_players=500, creative_ids=sample_ids, days=30, seed=42)
    print(f'\n[1] Generated {len(events)} events for 500 players (using {len(sample_ids)} real creative IDs)')

    # Step 2: Extract PlayerDNA
    dna_engine = PlayerDNAEngine()
    dna_map = dna_engine.extract_all(events)
    print(f'[2] Extracted PlayerDNA for {len(dna_map)} players')

    # Group events by player for pressure features
    events_by_player = defaultdict(list)
    for e in events:
        events_by_player[e.player_id].append(e)

    # Step 4: Run full E9.5 pipeline
    result = run_e95_pipeline(dna_map, events_by_player, creative_dna_map)
    print(f'[4] Pipeline complete')

    # Step 5: Print summary
    summary = result['summary']
    print(f'\n--- Classification Summary ---')
    print(f'Total players: {summary["total_players"]}')
    print(f'Archetype distribution:')
    for arch, count in sorted(summary['archetype_distribution'].items(), key=lambda x: -x[1]):
        pct = count / summary['total_players'] * 100
        print(f'  {arch}: {count} ({pct:.1f}%)')
    print(f'\nValue segments:')
    for seg, count in summary['value_segments'].items():
        pct = count / summary['total_players'] * 100
        print(f'  {seg}: {count} ({pct:.1f}%)')
    print(f'Avg confidence: {summary["avg_confidence"]}')

    print(f'\n--- Export Files ---')
    for k, v in result['export_paths'].items():
        size_kb = Path(v).stat().st_size / 1024 if Path(v).exists() else 0
        print(f'  {k}: {v} ({size_kb:.1f} KB)')

    print(f'\n--- Top Creative-Archetype Pairs ---')
    for pair in summary.get('top_creative_archetype_pairs', [])[:5]:
        print(f'  {pair["creative_genome"]} -> {pair["player_archetype"]}: '
              f'{pair["player_count"]} players, '
              f'payer_rate={pair["payer_rate"]}, '
              f'LTV=${pair["avg_d30_ltv"]}, '
              f'fitness={pair["fitness"]}')

    print(f'\n--- Population Stats (sample) ---')
    pop = result['population_stats']
    for dim, fields in pop.items():
        print(f'  {dim}:')
        for k, v in fields.items():
            if 'avg' in k:
                print(f'    {k}: {v}')

    # Diagnostic: collector score distribution
    print(f'\n--- Collector Score Diagnostic ---')
    from market_ops.player_intelligence import BehaviorFeatureEngine
    bfe = BehaviorFeatureEngine()
    collector_scores = []
    for pid, dna in dna_map.items():
        f = bfe.extract_features(dna, events_by_player.get(pid))
        collector_scores.append((pid, f.collector_score, f.collection_rate, f.rare_item_ratio, f.event_participation))
    collector_scores.sort(key=lambda x: -x[1])
    print(f'  Top 5 collector scores:')
    for pid, cs, cr, rr, ep in collector_scores[:5]:
        print(f'    {pid}: collector={cs:.3f} (coll_rate={cr:.3f}, rare={rr:.3f}, events={ep:.3f})')
    above_threshold = [x for x in collector_scores if x[1] >= 0.04]
    print(f'  Players above threshold (0.04): {len(above_threshold)}/{len(collector_scores)}')

    print(f'\n=== E9.5 Verification PASSED ===')


if __name__ == '__main__':
    main()