#!/usr/bin/env python3
"""Deep dive into P04 data: dates, Adjust data, and other tables."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB = ROOT / "db" / "facebook_performance.duckdb"

conn = duckdb.connect(str(DB), read_only=True)

# 1. Check ALL date values in creative_performance
print("=" * 70)
print("1. creative_performance - 所有日期值")
print("=" * 70)
rows = conn.execute("""
    SELECT date, COUNT(*) as rows, SUM(spend) as spend, 
           COUNT(DISTINCT creative_id) as creatives,
           COUNT(DISTINCT campaign_id) as campaigns
    FROM creative_performance
    WHERE project = 'P04 Witch'
    GROUP BY date ORDER BY date
""").fetchall()
for r in rows:
    print(f"  {r[0]} | {r[1]:5d} rows | ${r[2]:>10,.0f} | {r[3]:5d} creatives | {r[4]:2d} campaigns")
print(f"  Total distinct dates: {len(rows)}")

# 2. Check collected_at timestamps
print("\n" + "=" * 70)
print("2. creative_performance - collected_at 时间戳")
print("=" * 70)
rows = conn.execute("""
    SELECT DATE_TRUNC('day', collected_at) as col_day, 
           COUNT(*) as rows, 
           SUM(spend) as spend
    FROM creative_performance
    WHERE project = 'P04 Witch'
    GROUP BY col_day ORDER BY col_day
""").fetchall()
for r in rows:
    print(f"  {r[0]} | {r[1]:5d} rows | ${r[2]:>10,.0f}")

# 3. Check app_events (Adjust data)
print("\n" + "=" * 70)
print("3. app_events - Adjust 数据")
print("=" * 70)
cols = conn.execute("DESCRIBE app_events").fetchall()
print(f"  Columns: {[c[0] for c in cols]}")
rows = conn.execute("""
    SELECT date, app, event_name, SUM(event_count) as events, SUM(revenue) as revenue
    FROM app_events
    WHERE app LIKE '%P04%' OR app LIKE '%witch%' OR app LIKE '%merge%'
    GROUP BY date, app, event_name
    ORDER BY date DESC
    LIMIT 20
""").fetchall()
if rows:
    for r in rows:
        print(f"  {r[0]} | {r[1]:20s} | {r[2]:20s} | {r[3]:>8,} events | ${r[4]:>10,.2f}")
else:
    print("  No matching P04 data in app_events")
    # Check all apps
    apps = conn.execute("SELECT DISTINCT app FROM app_events").fetchall()
    print(f"  Available apps: {[a[0] for a in apps]}")
    # Check date range
    dr = conn.execute("SELECT MIN(date), MAX(date), COUNT(DISTINCT date) FROM app_events").fetchone()
    print(f"  Date range: {dr[0]} ~ {dr[1]} ({dr[2]} distinct dates)")

# 4. Check creative_id_mapping
print("\n" + "=" * 70)
print("4. creative_id_mapping - Adjust 映射")
print("=" * 70)
try:
    cols = conn.execute("DESCRIBE creative_id_mapping").fetchall()
    print(f"  Columns: {[c[0] for c in cols]}")
    cnt = conn.execute("SELECT COUNT(*) FROM creative_id_mapping").fetchone()[0]
    print(f"  Total rows: {cnt}")
    # Check if any P04
    samples = conn.execute("""
        SELECT * FROM creative_id_mapping LIMIT 3
    """).fetchall()
    for s in samples:
        print(f"  {dict(zip([c[0] for c in cols], s))}")
except Exception as e:
    print(f"  Error: {e}")

# 5. Check creative_scores
print("\n" + "=" * 70)
print("5. creative_scores - 素材评分")
print("=" * 70)
try:
    cnt = conn.execute("""
        SELECT COUNT(*) FROM creative_scores WHERE project = 'P04 Witch'
    """).fetchone()[0]
    print(f"  P04 Witch rows: {cnt}")
    samples = conn.execute("""
        SELECT creative_id, creative_name, spend, installs, roas_d7, creative_score, final_score, scored_at
        FROM creative_scores WHERE project = 'P04 Witch'
        ORDER BY spend DESC LIMIT 5
    """).fetchall()
    for s in samples:
        print(f"  {s[0]} | {s[1]:30s} | ${s[2]:>8,.0f} | {s[3]:>6,} | ROAS={s[4]:.3f} | score={s[5]:.1f} | {s[7]}")
except Exception as e:
    print(f"  Error: {e}")

# 6. Look at RL state data
print("\n" + "=" * 70)
print("6. rl_state_t - RL 状态数据")
print("=" * 70)
try:
    rows = conn.execute("""
        SELECT date, COUNT(*) as rows, SUM(spend) as spend, SUM(installs) as installs
        FROM rl_state_t
        WHERE creative_id IN (SELECT DISTINCT creative_id FROM creative_performance WHERE project = 'P04 Witch')
        GROUP BY date ORDER BY date DESC
        LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0]} | {r[1]:5d} rows | ${r[2]:>10,.0f} | {r[3]:>6,} installs")
except Exception as e:
    print(f"  Error: {e}")

# 7. Check Facebook API data freshness
print("\n" + "=" * 70)
print("7. ad_graph 最新数据")
print("=" * 70)
try:
    dr = conn.execute("SELECT MIN(pulled_at), MAX(pulled_at), COUNT(*) FROM ad_graph").fetchone()
    print(f"  ad_graph: {dr[0]} ~ {dr[1]} ({dr[2]} rows)")
    # Check P04
    cnt = conn.execute("""
        SELECT COUNT(*) FROM ad_graph 
        WHERE ad_name LIKE 'P4%' OR campaign_name LIKE 'P4%'
    """).fetchone()[0]
    print(f"  P4 related rows: {cnt}")
except Exception as e:
    print(f"  Error: {e}")

conn.close()