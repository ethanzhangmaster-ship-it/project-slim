"""Verify E9.5 output files."""
import json
from collections import Counter
from pathlib import Path

base = Path("output/player_intelligence")

# 1. player_genomes.json
pg = json.loads((base / "player_genomes.json").read_text(encoding="utf-8"))
print(f"player_genomes.json: {len(pg)} players")
archs = Counter(p["archetype"] for p in pg)
print(f"  Archetypes: {dict(archs)}")

# 2. archetype_report.json
ar = json.loads((base / "archetype_report.json").read_text(encoding="utf-8"))
print(f"\narchetype_report.json: {len(ar)} archetypes")
for a in ar:
    print(f"  {a['archetype']} ({a['display_name']}): {a['player_count']} players, "
          f"payer_rate={a['payer_rate']}, LTV=${a['avg_d30_ltv']}")

# 3. creative_archetype_matrix.json
cam = json.loads((base / "creative_archetype_matrix.json").read_text(encoding="utf-8"))
print(f"\ncreative_archetype_matrix.json: {len(cam)} entries")
for e in cam[:5]:
    print(f"  {e['creative_genome_name']} -> {e['player_archetype']}: "
          f"{e['player_count']} players, fitness={e['fitness_score']}, "
          f"payer_rate={e['payer_rate']}, LTV=${e['avg_d30_ltv']}")

# 4. Sample PlayerGenome
sample = pg[0]
print(f"\nSample PlayerGenome:")
print(f"  player_id: {sample['player_id']}")
print(f"  archetype: {sample['archetype']} ({sample['archetype_display']})")
print(f"  confidence: {sample['archetype_confidence']}")
print(f"  value: {sample['value_segment']}")
print(f"  explanation: {sample['explanation']}")
print(f"  payment: is_payer={sample['payment_profile']['is_payer']}, "
      f"trigger={sample['payment_profile']['trigger_type']}")

print("\nAll 3 output files verified successfully.")