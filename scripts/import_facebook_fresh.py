"""导入 fetch_facebook_data_local.py 拉取的数据到 DuckDB

用法:
  python3 scripts/import_facebook_fresh.py

读取 output/facebook_fresh_data.json，写入 creative_performance 表。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent


def main() -> int:
    input_path = ROOT / "output" / "facebook_fresh_data.json"
    if not input_path.exists():
        print(f"❌ 找不到 {input_path}")
        print(f"   请先将 fetch_facebook_data_local.py 拉取的数据文件放到此处")
        return 1

    with open(input_path, encoding="utf-8") as f:
        raw = json.load(f)

    data = raw.get("data", [])
    stats = raw.get("stats", {})
    print(f"加载 {len(data)} 条记录")
    print(f"日期: {stats.get('dates', [])[:3]}... ({len(stats.get('dates', []))} 天)")
    print(f"Spend: \${stats.get('total_spend', 0):,.0f}")

    db_path = ROOT / "db" / "facebook_performance.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)

    # 确保表存在
    conn.execute("""
        CREATE TABLE IF NOT EXISTS creative_performance (
            creative_id VARCHAR, campaign_id VARCHAR, adset_id VARCHAR,
            spend DOUBLE, impression INTEGER, click INTEGER, install INTEGER,
            ctr DOUBLE, ipm DOUBLE, cpi DOUBLE,
            roas_d1 DOUBLE, roas_d7 DOUBLE,
            date VARCHAR, project VARCHAR, collected_at TIMESTAMP
        )
    """)

    inserted = 0
    skipped = 0

    for row in data:
        creative_id = str(row.get("creative_id", ""))
        date_str = row.get("date_start", "")
        if not creative_id or not date_str:
            continue

        # 去重
        existing = conn.execute(
            "SELECT COUNT(*) FROM creative_performance WHERE creative_id = ? AND date = ?",
            [creative_id, date_str],
        ).fetchone()[0]
        if existing > 0:
            skipped += 1
            continue

        # 提取 installs
        actions = row.get("actions", [])
        installs = 0
        purchases = 0
        revenue = 0.0
        if isinstance(actions, list):
            for a in actions:
                if a.get("action_type") in ("mobile_app_install", "app_install", "omni_app_install"):
                    installs += int(a.get("value", 0))
                if a.get("action_type") in ("purchase", "omni_purchase", "offsite_conversion.fb_mobile_purchase"):
                    purchases += int(a.get("value", 0))

        # 提取 revenue
        action_values = row.get("action_values", [])
        if isinstance(action_values, list):
            for av in action_values:
                if av.get("action_type") in ("purchase", "omni_purchase"):
                    revenue += float(av.get("value", 0))

        spend = float(row.get("spend", 0))
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))
        ctr = float(row.get("ctr", 0))

        cpi = spend / installs if installs > 0 else 0
        roas_d7 = revenue / spend if spend > 0 else 0

        # 推测 project (从 campaign_name)
        campaign = str(row.get("campaign_name", ""))
        project = "P04 Witch"  # default
        for p in ["P02", "P04", "P07"]:
            if p in campaign:
                project = f"{p} Witch" if p == "P04" else (f"{p} Mermaid" if p == "P02" else f"{p} Vampire")
                break

        conn.execute("""
            INSERT INTO creative_performance
            (creative_id, campaign_id, adset_id, spend, impression, click, install,
             ctr, ipm, cpi, roas_d7, date, project, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [
            creative_id,
            str(row.get("campaign_name", "")),
            str(row.get("adset_name", "")),
            spend, impressions, clicks, installs,
            ctr,
            installs / max(impressions, 1) * 1000 if impressions > 0 else 0,
            cpi,
            roas_d7,
            date_str,
            project,
        ])
        inserted += 1

    conn.commit()

    # 验证
    total = conn.execute("SELECT COUNT(*) FROM creative_performance").fetchone()[0]
    dates = conn.execute("SELECT COUNT(DISTINCT date) FROM creative_performance").fetchone()[0]
    creatives = conn.execute("SELECT COUNT(DISTINCT creative_id) FROM creative_performance").fetchone()[0]

    print(f"\n导入完成:")
    print(f"  新增: {inserted} 条")
    print(f"  跳过 (已存在): {skipped} 条")
    print(f"  creative_performance 总计: {total} 条, {dates} 天, {creatives} creatives")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
