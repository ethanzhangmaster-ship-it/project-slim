#!/usr/bin/env python3
"""Query P04 Witch by platform (Android/iOS) - Part 2: find platform data."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB = ROOT / "db" / "facebook_performance.duckdb"

conn = duckdb.connect(str(DB), read_only=True)

# Check all tables and their columns
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
print("=== 所有表及列 ===")
for t in tables:
    tname = t[0]
    cols = conn.execute(f"DESCRIBE {tname}").fetchall()
    col_names = [f"{c[0]}({c[1]})" for c in cols]
    print(f"  {tname}: {', '.join(col_names[:15])}")

# Check campaign_id / adset_id naming for platform hints
print("\n\n=== P04 Witch campaign_id 样本 ===")
campaigns = conn.execute("""
    SELECT campaign_id, SUM(spend) as spend, COUNT(DISTINCT creative_id) as creatives
    FROM creative_performance
    WHERE project = 'P04 Witch'
    GROUP BY campaign_id
    ORDER BY spend DESC
    LIMIT 20
""").fetchall()
for c in campaigns:
    print(f"  {c[0]:50s} | ${c[1]:>10,.0f} | {c[2]} creatives")

print("\n\n=== P04 Witch adset_id 样本 ===")
adsets = conn.execute("""
    SELECT adset_id, SUM(spend) as spend, COUNT(DISTINCT creative_id) as creatives
    FROM creative_performance
    WHERE project = 'P04 Witch'
    GROUP BY adset_id
    ORDER BY spend DESC
    LIMIT 20
""").fetchall()
for a in adsets:
    print(f"  {a[0]:50s} | ${a[1]:>10,.0f} | {a[2]} creatives")

# Check unified_state
print("\n\n=== unified_state 样本 ===")
try:
    rows = conn.execute("SELECT * FROM unified_state LIMIT 3").fetchall()
    cols = [c[0] for c in conn.execute("DESCRIBE unified_state").fetchall()]
    for r in rows:
        print(dict(zip(cols, r)))
except Exception as e:
    print(f"Error: {e}")

# Check ad_graph
print("\n\n=== ad_graph 样本 ===")
try:
    rows = conn.execute("SELECT * FROM ad_graph LIMIT 3").fetchall()
    cols = [c[0] for c in conn.execute("DESCRIBE ad_graph").fetchall()]
    for r in rows:
        print(dict(zip(cols, r)))
except Exception as e:
    print(f"Error: {e}")

# Check contextual_state
print("\n\n=== contextual_state 样本 ===")
try:
    rows = conn.execute("SELECT * FROM contextual_state LIMIT 3").fetchall()
    cols = [c[0] for c in conn.execute("DESCRIBE contextual_state").fetchall()]
    for r in rows:
        print(dict(zip(cols, r)))
except Exception as e:
    print(f"Error: {e}")

conn.close()