#!/usr/bin/env python3
"""Query P04 Witch by platform (Android/iOS) and show top spending images/videos."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB = ROOT / "db" / "facebook_performance.duckdb"

conn = duckdb.connect(str(DB), read_only=True)

# 1. Check table structure
print("=" * 80)
print("=== creative_performance 列 ===")
cols = conn.execute("DESCRIBE creative_performance").fetchall()
for c in cols:
    print(f"  {c[0]:30s} {c[1]}")

print()
print("=== creative_features 列 ===")
cols = conn.execute("DESCRIBE creative_features").fetchall()
for c in cols:
    print(f"  {c[0]:30s} {c[1]}")

# 2. Check for platform/os fields
print("\n=== 检查平台字段 ===")
# Get all column names
all_cols = [c[0].lower() for c in conn.execute("DESCRIBE creative_performance").fetchall()]
print(f"Columns: {all_cols}")

# Check for platform-related columns
for keyword in ['platform', 'os', 'android', 'ios', 'device', 'bundle', 'app', 'store']:
    matches = [c for c in all_cols if keyword in c]
    if matches:
        print(f"  '{keyword}' matches: {matches}")

# Check bundle values
try:
    bundles = conn.execute("""
        SELECT DISTINCT bundle FROM creative_performance 
        WHERE project = 'P04 Witch' AND bundle IS NOT NULL
    """).fetchall()
    print(f"\nBundle values: {[b[0] for b in bundles]}")
except Exception as e:
    print(f"No bundle: {e}")

# Check all distinct values for potential platform indicators
print("\n=== 检查所有可能的平台区分字段 ===")
for col in ['bundle', 'app_name', 'app_id', 'store', 'platform', 'os', 'device_type']:
    if col in all_cols:
        vals = conn.execute(f"SELECT DISTINCT {col} FROM creative_performance WHERE project = 'P04 Witch' AND {col} IS NOT NULL").fetchall()
        print(f"  {col}: {[v[0] for v in vals[:20]]}")

# 3. Try to find platform split
print("\n\n=== P04 Witch 按平台统计 ===")

# Check if creative_id contains platform hints
# Try bundle-based split
samples = conn.execute("""
    SELECT creative_id, bundle, creative_type, media_type, SUM(spend) as spend
    FROM creative_performance
    WHERE project = 'P04 Witch'
    GROUP BY ALL
    ORDER BY spend DESC
    LIMIT 10
""").fetchall()
print("\nTop 10 by spend (with bundle):")
for r in samples:
    print(f"  {r[0]} | bundle={r[1]} | type={r[2]} | media={r[3]} | spend=${r[4]:,.0f}")

# Check ad_graph for platform info
print("\n=== ad_graph 表 ===")
try:
    cols = conn.execute("DESCRIBE ad_graph").fetchall()
    print(f"Columns: {[c[0] for c in cols]}")
except Exception as e:
    print(f"No ad_graph: {e}")

# Check all tables
print("\n=== 所有表 ===")
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
for t in tables:
    print(f"  {t[0]}")

conn.close()