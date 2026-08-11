"""Test DuckDB INSERT OR REPLACE with mixed ? and literals."""
import duckdb
import json

conn = duckdb.connect(":memory:")

# Create test table
conn.execute("""
    CREATE TABLE variant (
        variant_id VARCHAR PRIMARY KEY,
        experiment_id VARCHAR,
        features VARCHAR,
        weight DOUBLE,
        creative_id VARCHAR,
        ad_id VARCHAR
    )
""")

# Test 1: INSERT with mixed ? and literals
try:
    conn.execute("""
        INSERT INTO variant (variant_id, experiment_id, features, weight, creative_id, ad_id)
        VALUES (?, ?, ?, 1.0, ?, '')
    """, ["test_v1", "exp_test", json.dumps({"key": "value"}), "creative_123"])
    print("Test 1 (mixed ? and literals): OK")
    row = conn.execute("SELECT * FROM variant").fetchone()
    print(f"  Row: {row}")
except Exception as e:
    print(f"Test 1 ERROR: {e}")

# Clear
conn.execute("DELETE FROM variant")

# Test 2: All parameters
try:
    conn.execute("""
        INSERT INTO variant (variant_id, experiment_id, features, weight, creative_id, ad_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ["test_v1", "exp_test", json.dumps({"key": "value"}), 1.0, "creative_123", ""])
    print("Test 2 (all parameters): OK")
    row = conn.execute("SELECT * FROM variant").fetchone()
    print(f"  Row: {row}")
except Exception as e:
    print(f"Test 2 ERROR: {e}")

conn.close()