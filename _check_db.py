"""Check DB schema and state before pipeline run."""
import duckdb

conn = duckdb.connect("db/facebook_performance.duckdb", read_only=True)

tables = conn.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
).fetchall()
print("Tables:", [t[0] for t in tables])

for tbl in ["variant", "experiment", "creative_performance", "creative_features"]:
    try:
        cols = conn.execute(
            f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{tbl}'"
        ).fetchall()
        print(f"\n{tbl} columns: {[(c[0], c[1]) for c in cols]}")
        cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  rows: {cnt}")
    except Exception as e:
        print(f"\n{tbl}: {e}")

conn.close()