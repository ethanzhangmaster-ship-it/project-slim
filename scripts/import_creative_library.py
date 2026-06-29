"""将 creative_library.csv 导入 DuckDB creative_performance 表

creative_library.csv: 243 个 creative, 含 spend/installs/ctr/cvr + game/channel/hook_type
从中提取特征: game, channel, creative_type (图片/视频), hook_type 前缀

与现有 creative_features 互补, 丰富特征维度。
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


def extract_media_type(creative_name: str) -> str:
    """从 creative_name 提取媒体类型"""
    if "视频" in creative_name:
        return "video"
    if "图片" in creative_name:
        return "image"
    return "unknown"


def extract_market(creative_name: str) -> str:
    """从 creative_name 提取市场"""
    if "US" in creative_name:
        return "US"
    if "T1" in creative_name:
        return "T1"
    return "other"


def extract_game_from_name(creative_name: str) -> str:
    """从 creative_name 提取游戏"""
    m = re.match(r"(P\d{2})", creative_name)
    return m.group(1) if m else "unknown"


def main() -> int:
    db_path = ROOT / "db" / "facebook_performance.duckdb"
    csv_path = ROOT / "output" / "normalized" / "creative_library.csv"

    conn = duckdb.connect(str(db_path), read_only=False)

    # 确保 creative_performance 表存在
    conn.execute("""
        CREATE TABLE IF NOT EXISTS creative_performance (
            creative_id VARCHAR, campaign_id VARCHAR, adset_id VARCHAR,
            spend DOUBLE, impression INTEGER, click INTEGER, install INTEGER,
            ctr DOUBLE, ipm DOUBLE, cpi DOUBLE,
            roas_d1 DOUBLE, roas_d7 DOUBLE,
            date VARCHAR, project VARCHAR, collected_at TIMESTAMP
        )
    """)

    # 读取 CSV
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"  读取 {len(rows)} 个 creative")

    # 导入
    inserted = 0
    skipped = 0
    date_str = "2026-06-26"  # 统一日期

    for row in rows:
        creative_id = row["asset_id"].strip()
        if not creative_id:
            continue

        # 去重
        existing = conn.execute(
            "SELECT COUNT(*) FROM creative_performance WHERE creative_id = ? AND date = ?",
            [creative_id, date_str],
        ).fetchone()[0]
        if existing > 0:
            skipped += 1
            continue

        spend = float(row.get("spend", 0))
        installs = int(float(row.get("installs", 0)))
        ctr_val = float(row.get("ctr", 0))
        clicks = int(float(row.get("conversions", 0)) / max(float(row.get("cvr", 0.01)), 0.001)) if float(row.get("cvr", 0)) > 0 else 0
        # 用 CTR 反推 impressions
        impressions = int(clicks / ctr_val) if ctr_val > 0 and clicks > 0 else int(spend * 1000)  # rough estimate
        if impressions == 0:
            impressions = 100

        cpi = spend / installs if installs > 0 else 0

        conn.execute("""
            INSERT INTO creative_performance
            (creative_id, campaign_id, adset_id, spend, impression, click, install,
             ctr, ipm, cpi, roas_d7, date, project, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [
            creative_id,
            row.get("campaign_id", ""),
            row.get("adgroup_id", ""),
            spend,
            impressions,
            clicks,
            installs,
            ctr_val * 100,
            0.0,
            cpi,
            float(row.get("roas", 0)),
            date_str,
            row.get("game", "P04 Witch"),
        ])
        inserted += 1

    conn.commit()

    # 统计
    total = conn.execute("SELECT COUNT(*) FROM creative_performance").fetchone()[0]
    dates = conn.execute("SELECT COUNT(DISTINCT date) FROM creative_performance").fetchone()[0]
    creatives = conn.execute("SELECT COUNT(DISTINCT creative_id) FROM creative_performance").fetchone()[0]

    print(f"  导入: {inserted} 条新增, {skipped} 条跳过")
    print(f"  creative_performance: {total} 条, {dates} 个日期, {creatives} 个 creative")

    # 构建特征 variant
    print(f"\n  构建特征 variant...")

    # 清空旧的特征 experiment
    conn.execute("DELETE FROM variant WHERE experiment_id LIKE 'clib_%'")
    conn.execute("DELETE FROM experiment WHERE experiment_id LIKE 'clib_%'")

    # 为每个 creative 提取特征
    feature_configs = {
        "media_type": {
            "extractor": lambda r: extract_media_type(r["creative_name"]),
            "values": ["image", "video", "unknown"],
        },
        "market": {
            "extractor": lambda r: extract_market(r["creative_name"]),
            "values": ["US", "T1", "other"],
        },
        "game": {
            "extractor": lambda r: r["game"].strip(),
            "values": ["P02 Mermaid", "P04 Witch", "P07 Vampire"],
        },
        "channel": {
            "extractor": lambda r: r["channel"].strip(),
            "values": ["Facebook", "Google Ads"],
        },
    }

    import json
    total_variants = 0
    stats: dict[str, dict] = {}

    for gene_type, config in feature_configs.items():
        exp_id = f"clib_{gene_type}"
        conn.execute("""
            INSERT OR REPLACE INTO experiment (experiment_id, project, type, status, hypothesis, created_at)
            VALUES (?, 'CREATIVE_LIB', 'CREATIVE', 'RUNNING', ?, '2026-06-26')
        """, [exp_id, f"学习 {gene_type} 对 CPI 的影响"])

        value_stats: dict[str, dict] = {}
        for row in rows:
            cid = row["asset_id"].strip()
            if not cid:
                continue
            gene_value = config["extractor"](row)

            spend = float(row.get("spend", 0))
            installs = int(float(row.get("installs", 0)))
            cpi = spend / installs if installs > 0 else 999
            ctr = float(row.get("ctr", 0))

            if gene_value not in value_stats:
                value_stats[gene_value] = {"count": 0, "spend": 0, "installs": 0, "ctr_sum": 0.0}
            vs = value_stats[gene_value]
            vs["count"] += 1
            vs["spend"] += spend
            vs["installs"] += installs
            vs["ctr_sum"] += ctr

            # 写入 variant
            variant_id = f"clib_{gene_type}_{cid}"
            features = {gene_type: gene_value}
            conn.execute("""
                INSERT OR REPLACE INTO variant (variant_id, experiment_id, features, weight, creative_id, ad_id)
                VALUES (?, ?, ?, 1.0, ?, '')
            """, [variant_id, exp_id, json.dumps(features, ensure_ascii=False), cid])
            total_variants += 1

        # 计算加权 CPI
        for gv, vs in value_stats.items():
            vs["cpi"] = vs["spend"] / vs["installs"] if vs["installs"] > 0 else 999
            vs["avg_ctr"] = vs["ctr_sum"] / vs["count"] if vs["count"] > 0 else 0

        stats[gene_type] = value_stats

    conn.commit()

    # 输出统计
    print(f"  写入 {total_variants} 条 variant, {len(feature_configs)} 个 experiment\n")
    for gene_type, value_stats in stats.items():
        print(f"  📊 {gene_type}:")
        sorted_items = sorted(value_stats.items(),
                              key=lambda x: x[1]["cpi"])  # CPI 越低越好
        for gv, vs in sorted_items:
            print(f"      {gv:<15} n={vs['count']:>4}  spend=\${vs['spend']:,.0f}  "
                  f"installs={vs['installs']:,}  CPI=\${vs['cpi']:.2f}  CTR={vs['avg_ctr']:.1%}")

    conn.close()
    print(f"\n  🎉 creative_library 导入 + 特征构建完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
