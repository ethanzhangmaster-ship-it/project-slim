"""Check which top winners have eagle_filepath mappings."""
import csv
from pathlib import Path

mapping_path = Path(r"d:\project_slim\project_slim\output\video_intelligence\p04\creative_mapping_v2.csv")
with open(mapping_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Top winners from Step 1 (by composite score)
top_ids = [
    "2405756773259457", "997474472844091", "857176894106165",
    "1201953154798305", "609636024574727", "1053146360130696",
    "540575918612411", "793636452643102", "928636348223456",
    "1201953154798306"
]

print("=== Top Winners Eagle Filepath Check ===")
found = 0
for r in rows:
    cid = r.get("creative_id", "").strip()
    if cid in top_ids:
        found += 1
        fp = r.get("eagle_filepath", "").strip()
        fn = r.get("eagle_filename", "").strip()
        tn = r.get("thumbnail_url", "").strip()
        print(f"CID={cid}")
        print(f"  eagle_filepath: {fp}")
        print(f"  eagle_filename: {fn}")
        print(f"  thumbnail_url: {tn[:80]}...")
        print(f"  spend={r.get('spend','?')} revenue={r.get('revenue','?')}")
        print()

print(f"Found: {found}/{len(top_ids)}")

# Also: how many rows have eagle_filepath?
has_fp = [r for r in rows if r.get("eagle_filepath", "").strip()]
print(f"\nTotal rows with eagle_filepath: {len(has_fp)}/{len(rows)}")

# Sample thumbnail URLs
print("\n=== Sample Thumbnail URLs ===")
for r in rows[:5]:
    tn = r.get("thumbnail_url", "").strip()
    if tn:
        print(f"  {tn[:120]}")