"""将Facebook insights数据导入DuckDB creative_performance表

复用FacebookAdsCollector的表结构,数据源为现有的summary.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb

DB_PATH = ROOT / "db" / "facebook_performance.duckdb"
SUMMARY = ROOT / "output" / "facebook_ads_data" / "summary.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS creative_performance (
    creative_id VARCHAR,
    campaign_id VARCHAR,
    adset_id VARCHAR,
    spend DOUBLE,
    impression INTEGER,
    click INTEGER,
    install INTEGER,
    ctr DOUBLE,
    ipm DOUBLE,
    cpi DOUBLE,
    roas_d1 DOUBLE,
    roas_d7 DOUBLE,
    date VARCHAR,
    project VARCHAR,
    collected_at TIMESTAMP
);
"""

INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_creative_date ON creative_performance(creative_id, date);"


def main():
    with open(SUMMARY, "r", encoding="utf-8") as f:
        s = json.load(f)

    conn = duckdb.connect(str(DB_PATH), read_only=False)
    conn.execute(SCHEMA)
    conn.execute(INDEX_SQL)

    # 清空旧数据
    conn.execute("DELETE FROM creative_performance")

    count = 0
    for acc in s["accounts"]:
        project = acc["project"]
        # 建立 ad_name → creative_id 映射
        ad_map = {}
        for ad in acc.get("ads", []):
            ad_name = ad.get("name", "")
            creative_id = ad.get("creative_id", "")
            if creative_id and ad_name:
                ad_map[ad_name] = creative_id

        # 导入insights_30d
        for ins in acc.get("insights_30d", []):
            ad_name = ins.get("ad_name", "")
            creative_id = ad_map.get(ad_name, "")
            if not creative_id:
                continue

            conn.execute("""
                INSERT INTO creative_performance
                (creative_id, spend, impression, click, install, ctr, ipm, cpi,
                 roas_d7, date, project, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [
                creative_id,
                float(ins.get("spend", 0)),
                int(ins.get("impressions", 0)),
                int(ins.get("clicks", 0)),
                int(ins.get("installs", 0)),
                float(ins.get("ctr", 0)),
                float(ins.get("ipm", 0)),
                float(ins.get("cpi", 0)),
                float(ins.get("roas", 0)),
                ins.get("date_start", ""),
                project,
            ])
            count += 1

    conn.commit()

    # 验证
    total = conn.execute("SELECT COUNT(*) FROM creative_performance").fetchone()[0]
    by_project = conn.execute(
        "SELECT project, COUNT(*), SUM(spend), SUM(install) FROM creative_performance GROUP BY project"
    ).fetchall()

    print(f"导入完成: {count} 条 → creative_performance 表")
    print(f"总计: {total} 条")
    print(f"\n按项目:")
    for p, n, spend, installs in by_project:
        print(f"  {p}: {n} 条 | ${spend:,.0f} | {installs} 安装")

    conn.close()


if __name__ == "__main__":
    main()
