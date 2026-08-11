#!/usr/bin/env python3
"""Show P04 data source details."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB = ROOT / "db" / "facebook_performance.duckdb"

conn = duckdb.connect(str(DB), read_only=True)

# Date range
print("=" * 60)
print("P04 Witch - 数据源和维度说明")
print("=" * 60)

r = conn.execute("""
    SELECT MIN(date), MAX(date), COUNT(DISTINCT date) 
    FROM creative_performance 
    WHERE project = 'P04 Witch'
""").fetchone()
print(f"\n时间范围: {r[0]} ~ {r[1]} (共 {r[2]} 天)")
print(f"数据表: creative_performance (DuckDB)")
print(f"数据来源: Facebook Ads Insights API")
print(f"广告账户: act_1455525822955003 (META_API)")
print(f"平台区分: campaign_id LIKE 'P4-AND-%' vs 'P4-IOS-%'")
print(f"聚合维度: creative_id 级别")
print(f"指标: SUM(spend), SUM(install), 加权 ROAS, CPI=spend/install")

# Android per day
print("\n" + "=" * 60)
print("Android (P4-AND-*) 每日数据")
print("=" * 60)
rows = conn.execute("""
    SELECT date, SUM(spend) as spend, SUM(install) as installs,
           CASE WHEN SUM(spend) > 0 THEN SUM(roas_d7 * spend)/SUM(spend) ELSE 0 END as roas
    FROM creative_performance
    WHERE project = 'P04 Witch' AND campaign_id LIKE 'P4-AND-%'
    GROUP BY date ORDER BY date
""").fetchall()
total_spend_a = 0
total_inst_a = 0
for r in rows:
    total_spend_a += r[1]
    total_inst_a += r[2]
    print(f"  {r[0]} | ${r[1]:>8,.0f} | {r[2]:>6,} installs | ROAS={r[3]:.3f}")
print(f"  {'TOTAL':10s} | ${total_spend_a:>8,.0f} | {total_inst_a:>6,} installs")

# iOS per day
print("\n" + "=" * 60)
print("iOS (P4-IOS-*) 每日数据")
print("=" * 60)
rows = conn.execute("""
    SELECT date, SUM(spend) as spend, SUM(install) as installs,
           CASE WHEN SUM(spend) > 0 THEN SUM(roas_d7 * spend)/SUM(spend) ELSE 0 END as roas
    FROM creative_performance
    WHERE project = 'P04 Witch' AND campaign_id LIKE 'P4-IOS-%'
    GROUP BY date ORDER BY date
""").fetchall()
total_spend_i = 0
total_inst_i = 0
for r in rows:
    total_spend_i += r[1]
    total_inst_i += r[2]
    print(f"  {r[0]} | ${r[1]:>8,.0f} | {r[2]:>6,} installs | ROAS={r[3]:.3f}")
print(f"  {'TOTAL':10s} | ${total_spend_i:>8,.0f} | {total_inst_i:>6,} installs")

# Summary
print("\n" + "=" * 60)
print("汇总")
print("=" * 60)
print(f"  Android: ${total_spend_a:,.0f} spend | {total_inst_a:,} installs | CPI=${total_spend_a/total_inst_a:.2f}" if total_inst_a else "  Android: no data")
print(f"  iOS:     ${total_spend_i:,.0f} spend | {total_inst_i:,} installs | CPI=${total_spend_i/total_inst_i:.2f}" if total_inst_i else "  iOS: no data")

# Check Other category
print("\n" + "=" * 60)
print("Other (非 P4-AND/IOS 前缀的 campaign)")
print("=" * 60)
rows = conn.execute("""
    SELECT campaign_id, SUM(spend) as spend, COUNT(DISTINCT creative_id) as creatives
    FROM creative_performance
    WHERE project = 'P04 Witch' 
      AND campaign_id NOT LIKE 'P4-AND-%' 
      AND campaign_id NOT LIKE 'P4-IOS-%'
    GROUP BY campaign_id
    ORDER BY spend DESC
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {r[0]:50s} | ${r[1]:>8,.0f} | {r[2]} creatives")

conn.close()