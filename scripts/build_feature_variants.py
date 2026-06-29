"""特征数据补全 — creative_features → FeatureSpace → variant 表

从 creative_features 提取有区分度的字段, 映射到 FinalBandit FeatureSpace:
- warm_cool → color_tone (warm / neutral / cool)
- left_right_layout / center_layout → layout (left_right / center / top_bottom)  
- saturation 分段 → saturation_level (low / medium / high)
- brightness 分段 → brightness_level (dark / medium / bright)

每个 creative 生成一条 variant 记录, 写入 variant 表。
同时关联 creative_performance, 用于后续 backfill 和 FinalBandit 学习。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


# ============================================================================
# 特征提取函数
# ============================================================================

def map_color_tone(warm_cool: str) -> str:
    """warm_cool → color_tone FeatureSpace"""
    if warm_cool in ("warm", "neutral", "cool"):
        return warm_cool
    return "neutral"  # default


def map_layout(left_right: bool, center: bool) -> str:
    """layout 推导 → layout FeatureSpace"""
    if left_right:
        return "left_right"
    elif center:
        return "center"
    else:
        return "top_bottom"


def map_saturation_level(saturation: float) -> str:
    """saturation 分段 → saturation_level"""
    if saturation < 0.35:
        return "low"
    elif saturation < 0.50:
        return "medium"
    else:
        return "high"


def map_brightness_level(brightness: float) -> str:
    """brightness 分段 → brightness_level"""
    if brightness < 0.35:
        return "dark"
    elif brightness < 0.55:
        return "medium"
    else:
        return "bright"


# ============================================================================
# 主流程
# ============================================================================

def main() -> int:
    db_path = ROOT / "db" / "facebook_performance.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)

    # 1. 读取 creative_features (有 performance 数据的)
    rows = conn.execute("""
        SELECT 
            cf.creative_id,
            cf.warm_cool,
            cf.left_right_layout,
            cf.center_layout,
            cf.saturation,
            cf.brightness,
            cf.project,
            COALESCE(cp.imp_sum, 0) as total_imp,
            COALESCE(cp.roas_avg, 0) as roas_d7,
            COALESCE(cp.ctr_avg, 0) as ctr
        FROM creative_features cf
        LEFT JOIN (
            SELECT creative_id,
                   SUM(impression) as imp_sum,
                   AVG(ctr) as ctr_avg,
                   CASE WHEN SUM(spend) > 0 
                        THEN SUM(roas_d7 * spend) / SUM(spend) 
                        ELSE 0 END as roas_avg
            FROM creative_performance
            GROUP BY creative_id
        ) cp ON cf.creative_id = cp.creative_id
    """).fetchall()
    cols = [d[0] for d in conn.description]

    print(f"  读取 {len(rows)} 个 creative (含 performance)")

    # 转为 dict 方便访问
    data = [dict(zip(cols, r)) for r in rows]

    # 2. 清空旧 variant + experiment (project=FEATURE_MAP)
    conn.execute("DELETE FROM variant WHERE experiment_id LIKE 'feat_%'")
    conn.execute("DELETE FROM experiment WHERE experiment_id LIKE 'feat_%'")

    # 3. 为每个 gene_type 创建 experiment, 为每个 creative 创建 variant
    gene_types = {
        "color_tone": {
            "mapper": lambda r: map_color_tone(r["warm_cool"]),
            "values": ["warm", "neutral", "cool"],
        },
        "layout": {
            "mapper": lambda r: map_layout(r["left_right_layout"], r["center_layout"]),
            "values": ["left_right", "center", "top_bottom"],
        },
        "saturation_level": {
            "mapper": lambda r: map_saturation_level(r["saturation"]),
            "values": ["low", "medium", "high"],
        },
        "brightness_level": {
            "mapper": lambda r: map_brightness_level(r["brightness"]),
            "values": ["dark", "medium", "bright"],
        },
    }

    stats: dict[str, dict] = {}
    total_variants = 0

    for gene_type, config in gene_types.items():
        exp_id = f"feat_{gene_type}"
        project = "FEATURE_MAP"
        ts = datetime.now().isoformat()

        # 创建 experiment
        conn.execute("""
            INSERT OR REPLACE INTO experiment
                (experiment_id, project, type, status, hypothesis, created_at)
            VALUES (?, ?, 'CREATIVE', 'RUNNING', ?, ?)
        """, [exp_id, project, f"学习 {gene_type} 对 ROAS 的影响", ts])

        # 统计每个 gene_value 的 creative 数和 performance
        value_stats: dict[str, dict] = {}
        for row in data:
            cid = row["creative_id"]
            gene_value = config["mapper"](row)
            total_imp = int(row["total_imp"]) if row["total_imp"] else 0
            roas = float(row["roas_d7"]) if row["roas_d7"] else 0
            ctr = float(row["ctr"]) if row["ctr"] else 0

            if gene_value not in value_stats:
                value_stats[gene_value] = {
                    "count": 0, "total_imp": 0, "roas_sum": 0.0, "roas_w": 0.0,
                    "ctr_sum": 0.0, "ctr_w": 0,
                }
            vs = value_stats[gene_value]
            vs["count"] += 1
            vs["total_imp"] += total_imp
            if total_imp > 0:
                vs["roas_sum"] += roas * total_imp
                vs["roas_w"] += total_imp
                vs["ctr_sum"] += ctr * total_imp
                vs["ctr_w"] += total_imp

            # 写入 variant
            variant_id = f"feat_{gene_type}_{cid}"
            features = {gene_type: gene_value}
            conn.execute("""
                INSERT OR REPLACE INTO variant
                    (variant_id, experiment_id, features, weight, creative_id, ad_id)
                VALUES (?, ?, ?, 1.0, ?, '')
            """, [variant_id, exp_id, json.dumps(features, ensure_ascii=False), cid])
            total_variants += 1

        # 计算加权平均
        for gv, vs in value_stats.items():
            vs["avg_roas"] = vs["roas_sum"] / vs["roas_w"] if vs["roas_w"] > 0 else 0
            vs["avg_ctr"] = vs["ctr_sum"] / vs["ctr_w"] if vs["ctr_w"] > 0 else 0

        stats[gene_type] = value_stats

    conn.commit()

    # 4. 输出统计
    print(f"\n  写入 {total_variants} 条 variant, {len(gene_types)} 个 experiment\n")
    for gene_type, value_stats in stats.items():
        print(f"  📊 {gene_type}:")
        sorted_items = sorted(value_stats.items(),
                              key=lambda x: x[1]["avg_roas"], reverse=True)
        for gv, vs in sorted_items:
            print(f"      {gv:<12} n={vs['count']:>4}  imp={vs['total_imp']:>10,}  "
                  f"ROAS={vs['avg_roas']:.3f}  CTR={vs['avg_ctr']:.1f}%")

    # 5. 验证
    for gene_type in gene_types:
        vc = conn.execute(
            "SELECT COUNT(*) FROM variant WHERE experiment_id = ?",
            [f"feat_{gene_type}"],
        ).fetchone()[0]
        print(f"\n  ✅ variant 表: feat_{gene_type} = {vc} 条")

    conn.close()
    print(f"\n  🎉 特征数据补全完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
