"""Verify closed-loop results."""
import duckdb

conn = duckdb.connect("db/facebook_performance.duckdb", read_only=True)

print("=== 闭环验证 ===")
print()

# 1. state_t (unified_state) table
rows = conn.execute("SELECT COUNT(*) FROM unified_state").fetchone()[0]
print(f"unified_state: {rows} 行")

# 2. RL state_t
rows = conn.execute("SELECT COUNT(*) FROM rl_state_t").fetchone()[0]
print(f"rl_state_t: {rows} 行")

# 3. reward distribution
print("\nreward 分布:")
for r in conn.execute("""
    SELECT reward_type, COUNT(*) as cnt, ROUND(AVG(reward), 6) as avg_reward
    FROM rl_state_t
    WHERE reward > 0
    GROUP BY reward_type
    ORDER BY cnt DESC
""").fetchall():
    print(f"  {r[0]}: {r[1]} rows, avg_reward={r[2]}")

# 4. FinalBandit experiment results
print("\nFinalBandit 实验结果:")
for r in conn.execute("""
    SELECT e.experiment_id, e.status,
           (SELECT COUNT(*) FROM variant v WHERE v.experiment_id = e.experiment_id) as variants
    FROM experiment e
    WHERE e.experiment_id LIKE 'pipe_%'
""").fetchall():
    print(f"  {r[0]}: status={r[1]}, variants={r[2]}")

# 5. Policy directives
print("\nPolicy Directives:")
import json
with open("output/pipeline_directives.json") as f:
    d = json.load(f)
    for gene, directive in d["directives"].items():
        print(f"  {gene}: target={directive['target']}, rate={directive['rate']:.3f}")

# 6. Winner summary
print("\nWinner Summary:")
for r in conn.execute("""
    SELECT variant_id, experiment_id, CAST(features AS VARCHAR) as feats
    FROM variant
    WHERE experiment_id IN ('pipe_game', 'pipe_color_tone', 'pipe_layout')
    ORDER BY experiment_id
    LIMIT 5
""").fetchall():
    print(f"  {r[0]}: {r[1]} → {r[2]}")

conn.close()
print("\n✅ 闭环完成")