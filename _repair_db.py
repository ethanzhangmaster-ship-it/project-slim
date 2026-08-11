"""Repair DB step by step with connection restarts."""
import duckdb

DB_PATH = "db/facebook_performance.duckdb"

# Step 1: Drop all indexes
print("Step 1: Drop indexes...")
conn = duckdb.connect(DB_PATH, read_only=False)
try:
    conn.execute("DROP INDEX IF EXISTS idx_var_exp")
    print("  Dropped idx_var_exp")
except Exception as e:
    print(f"  Drop idx_var_exp: {e}")
try:
    conn.execute("DROP INDEX IF EXISTS idx_var_creative")
    print("  Dropped idx_var_creative")
except Exception as e:
    print(f"  Drop idx_var_creative: {e}")
try:
    conn.execute("DROP INDEX IF EXISTS idx_exp_status")
    print("  Dropped idx_exp_status")
except Exception as e:
    print(f"  Drop idx_exp_status: {e}")
conn.commit()
conn.close()
print("  Connection closed.\n")

# Step 2: Do DELETEs
print("Step 2: Delete pipe_ data...")
conn = duckdb.connect(DB_PATH, read_only=False)
try:
    conn.execute("DELETE FROM variant WHERE experiment_id LIKE 'pipe_%'")
    cnt = conn.execute("SELECT COUNT(*) FROM variant WHERE experiment_id LIKE 'pipe_%'").fetchone()[0]
    print(f"  Remaining pipe_ variants: {cnt}")
except Exception as e:
    print(f"  DELETE variant error: {e}")
try:
    conn.execute("DELETE FROM experiment WHERE experiment_id LIKE 'pipe_%'")
    cnt = conn.execute("SELECT COUNT(*) FROM experiment WHERE experiment_id LIKE 'pipe_%'").fetchone()[0]
    print(f"  Remaining pipe_ experiments: {cnt}")
except Exception as e:
    print(f"  DELETE experiment error: {e}")
conn.commit()
conn.close()
print("  Connection closed.\n")

# Step 3: Recreate indexes
print("Step 3: Recreate indexes...")
conn = duckdb.connect(DB_PATH, read_only=False)
conn.execute("CREATE INDEX IF NOT EXISTS idx_var_exp ON variant(experiment_id)")
print("  Created idx_var_exp")
conn.execute("CREATE INDEX IF NOT EXISTS idx_var_creative ON variant(creative_id)")
print("  Created idx_var_creative")
conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_status ON experiment(status)")
print("  Created idx_exp_status")
conn.commit()
conn.close()

# Verify
conn = duckdb.connect(DB_PATH, read_only=True)
cnt = conn.execute("SELECT COUNT(*) FROM variant").fetchone()[0]
print(f"\nFinal: variant rows: {cnt}")
cnt2 = conn.execute("SELECT COUNT(*) FROM experiment").fetchone()[0]
print(f"  experiment rows: {cnt2}")
conn.close()
print("\nRepair complete!")