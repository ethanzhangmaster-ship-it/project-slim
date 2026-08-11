import duckdb
c = duckdb.connect("db/facebook_performance.duckdb", read_only=True)
cols = c.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='action_log'").fetchall()
print("action_log columns:", cols)
rows = c.execute("SELECT COUNT(*) FROM action_log").fetchone()[0]
print("rows:", rows)
if rows > 0:
    r = c.execute("SELECT * FROM action_log LIMIT 1").fetchone()
    print("sample:", r)
c.close()