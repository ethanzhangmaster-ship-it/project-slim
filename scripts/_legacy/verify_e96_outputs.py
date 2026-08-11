"""Verify E9.6 outputs."""
import json

r = json.loads(open("output/creative_matching/creative_archetype_rank.json", encoding="utf-8").read())
for cat in ["top_power_creatives", "top_collector_creatives", "top_explorer_creatives", "top_ltv_creatives", "top_iap_creatives"]:
    entries = r[cat][:3]
    print(f"{cat}:")
    for e in entries:
        name = e["creative_genome_name"][:50]
        print(f"  {name}... prob={e['probability']}, LTV=${e['expected_ltv']}, IAP={e['iap_potential']}")
    print()