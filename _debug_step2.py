"""Run pipeline step by step to find exact error."""
import sys
import traceback
import json
from collections import defaultdict
from pathlib import Path
import duckdb

ROOT = Path("c:/Users/ethan/Downloads/project_slim")
sys.path.insert(0, str(ROOT / "src"))
db_path = ROOT / "db" / "facebook_performance.duckdb"

# Step 2: 特征构建 - do it manually to find the error
conn = duckdb.connect(str(db_path), read_only=False)

# 清空 pipeline 生成的旧数据
try:
    conn.execute("DELETE FROM variant WHERE experiment_id LIKE 'pipe_%'")
    print("DELETE variant OK")
    conn.execute("DELETE FROM experiment WHERE experiment_id LIKE 'pipe_%'")
    print("DELETE experiment OK")
except Exception as e:
    print(f"DELETE ERROR: {e}")
    traceback.print_exc()

# 从 creative_library 导入的特征维度
gene_types = {}

gene_types["channel"] = {
    "feature_sql": """
        SELECT DISTINCT creative_id, 'Facebook' as gene_value
        FROM creative_performance WHERE creative_id != ''
    """,
}

gene_types["color_tone"] = {
    "feature_sql": """
        SELECT cf.creative_id, cf.warm_cool as gene_value
        FROM creative_features cf
        WHERE cf.warm_cool IS NOT NULL AND cf.warm_cool != ''
    """,
}

# Try game type separately
gene_types["game"] = {
    "feature_sql": """
        SELECT v.creative_id, cp.project as gene_value
        FROM creative_performance cp
        JOIN (SELECT DISTINCT creative_id FROM creative_performance WHERE creative_id != '') v
          ON cp.creative_id = v.creative_id
        WHERE cp.project IS NOT NULL AND cp.project != ''
    """,
}

total_variants = 0
ts = "2026-06-30T00:00:00"

for gene_type, config in gene_types.items():
    exp_id = f"pipe_{gene_type}"
    print(f"\nProcessing {gene_type}...")

    # 创建 experiment
    try:
        conn.execute("""
            INSERT OR REPLACE INTO experiment (experiment_id, project, type, status, hypothesis, created_at)
            VALUES (?, 'PIPELINE', 'CREATIVE', 'RUNNING', ?, ?)
        """, [exp_id, f"FinalBandit 学习 {gene_type}", ts])
        print(f"  experiment INSERT OK")
    except Exception as e:
        print(f"  experiment INSERT ERROR: {e}")
        traceback.print_exc()

    # 拉取 creative → gene_value 映射
    rows = conn.execute(config["feature_sql"]).fetchall()
    print(f"  Got {len(rows)} rows")

    if not rows:
        continue

    value_counts: dict[str, int] = defaultdict(int)
    for cid, gv in rows:
        if not cid or not gv:
            continue
        value_counts[gv] += 1
        variant_id = f"pipe_{gene_type}_{cid}"
        features = {gene_type: gv}
        try:
            conn.execute("""
                INSERT OR REPLACE INTO variant (variant_id, experiment_id, features, weight, creative_id, ad_id)
                VALUES (?, ?, ?, 1.0, ?, '')
            """, [variant_id, exp_id, json.dumps(features, ensure_ascii=False), cid])
            total_variants += 1
        except Exception as e:
            print(f"  INSERT ERROR for {variant_id}: {e}")
            traceback.print_exc()
            break

    print(f"  {gene_type}: {len(value_counts)} arms, variants processed")

conn.commit()
conn.close()
print(f"\nTotal variants: {total_variants}")