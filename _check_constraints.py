"""Check foreign keys and try to reproduce the error."""
import duckdb

conn = duckdb.connect("db/facebook_performance.duckdb", read_only=False)

# Check all constraints
all_constraints = conn.execute("""
    SELECT table_name, constraint_type, constraint_text
    FROM duckdb_constraints
""").fetchall()
print("All constraints:")
for c in all_constraints:
    print(f"  {c}")

# Check all tables
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
print("\nAll tables:")
for t in tables:
    print(f"  {t[0]}")

# Try the DELETE that the pipeline does
print("\nTrying DELETE FROM variant WHERE experiment_id LIKE 'pipe_%'...")
try:
    conn.execute("DELETE FROM variant WHERE experiment_id LIKE 'pipe_%'")
    print("  DELETE variant OK")
except Exception as e:
    print(f"  DELETE variant ERROR: {e}")

print("\nTrying DELETE FROM experiment WHERE experiment_id LIKE 'pipe_%'...")
try:
    conn.execute("DELETE FROM experiment WHERE experiment_id LIKE 'pipe_%'")
    print("  DELETE experiment OK")
except Exception as e:
    print(f"  DELETE experiment ERROR: {e}")

conn.rollback()
conn.close()