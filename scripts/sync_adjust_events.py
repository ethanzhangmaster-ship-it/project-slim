#!/usr/bin/env python3
"""Adjust App Events → DuckDB 自动同步

把游戏内所有事件（Install, Tutorial, Level5, Merge50, ShopOpen, OfferClick, Purchase）
同步到本地 DuckDB，支持自动计算:
  - P(Purchase | Event) = 事件到付费的转化率
  - 每个事件的日平均量
  - AEO 候选事件自动排序

数据源:
  - Adjust Event API (https://automate.adjust.com/reports-service/event)
  - 或 Adjust Raw Data Export (CSV)
  - 或 Adjust Callback → 本地接收

DuckDB 表结构:
  app_events:
    date, app, event_name, event_count, unique_users, revenue, paying_users

用法:
  python scripts/sync_adjust_events.py                    # 全量同步近30天
  python scripts/sync_adjust_events.py --days 30          # 指定天数
  python scripts/sync_adjust_events.py --from-csv events.csv  # 从CSV导入
"""
from __future__ import annotations

import argparse, json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ensure_schema(db_path: Path):
    """创建 app_events 表"""
    import duckdb
    conn = duckdb.connect(str(db_path), read_only=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_events (
            date DATE,
            app VARCHAR,
            event_name VARCHAR,
            event_count INTEGER,
            unique_users INTEGER,
            revenue DOUBLE,
            paying_users INTEGER,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, app, event_name)
        )
    """)
    conn.close()


def sync_from_adjust_api(db_path: Path, days: int):
    """从 Adjust Event API 拉取事件数据"""
    import requests, urllib3, duckdb
    urllib3.disable_warnings()

    token = os.environ.get("ADJUST_API_TOKEN", "")
    if not token:
        print("❌ ADJUST_API_TOKEN 未设置")
        return 0

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # Adjust Event API endpoint (不同于 report endpoint)
    # https://help.adjust.com/en/article/event-api
    base_url = "https://automate.adjust.com/reports-service/event"

    params = {
        "date_period": f"{start_date}:{end_date}",
        "dimensions": "app,event_name,day",
        "metrics": "events,revenue,paying_users",
        "ad_spend_mode": "network",
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    print(f"拉取: {start_date} → {end_date}")

    try:
        resp = requests.get(base_url, params=params, headers=headers, verify=False, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("rows", [])

        if not rows:
            print(f"⚠️  Adjust Event API 返回 {len(rows)} 行")
            print(f"   可能原因: 未开通 Event API / 无事件数据")
            print(f"   API 响应: {json.dumps(data, ensure_ascii=False)[:300]}")
            return 0

        conn = duckdb.connect(str(db_path), read_only=False)
        count = 0
        for row in rows:
            conn.execute("""
                INSERT OR REPLACE INTO app_events (date, app, event_name, event_count, unique_users, revenue, paying_users)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                row.get("day", ""),
                row.get("app", ""),
                row.get("event_name", ""),
                int(row.get("events", 0)),
                int(row.get("unique_users", 0)) if "unique_users" in row else int(row.get("events", 0)),
                float(row.get("revenue", 0)),
                int(row.get("paying_users", 0)),
            ])
            count += 1

        conn.close()
        print(f"✅ 同步 {count} 行到 DuckDB")
        return count

    except requests.HTTPError as e:
        print(f"❌ HTTP {e.response.status_code}: {e.response.text[:300]}")
        return 0
    except Exception as e:
        print(f"❌ 失败: {e}")
        return 0


def sync_from_csv(db_path: Path, csv_path: str):
    """从 CSV 文件导入事件数据

    CSV 格式:
      date,app,event_name,event_count,unique_users,revenue,paying_users
      2026-06-01,P04 Witch,install,1200,1200,0,0
      2026-06-01,P04 Witch,tutorial_complete,980,980,0,0
      2026-06-01,P04 Witch,purchase,25,25,450.00,25
    """
    import csv, duckdb

    conn = duckdb.connect(str(db_path), read_only=False)
    count = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conn.execute("""
                INSERT OR REPLACE INTO app_events (date, app, event_name, event_count, unique_users, revenue, paying_users)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                row.get("date", ""),
                row.get("app", "P04 Witch"),
                row.get("event_name", ""),
                int(row.get("event_count", 0)),
                int(row.get("unique_users", 0)),
                float(row.get("revenue", 0)),
                int(row.get("paying_users", 0)),
            ])
            count += 1

    conn.close()
    print(f"✅ 从 CSV 导入 {count} 行")


def analyze_events(db_path: Path):
    """分析事件数据, 计算 P(Purchase|Event) 并输出 AEO 推荐"""
    import duckdb

    conn = duckdb.connect(str(db_path), read_only=True)

    # 检查是否有数据
    total = conn.execute("SELECT COUNT(*) FROM app_events").fetchone()[0]
    if total == 0:
        print("\n⚠️  暂无事件数据，请先运行同步")
        conn.close()
        return

    # 获取总 Purchase 用户数作为基准
    purchase_row = conn.execute("""
        SELECT SUM(paying_users), SUM(event_count)
        FROM app_events WHERE event_name LIKE '%purchase%' OR event_name LIKE '%pay%'
    """).fetchone()
    total_payers = purchase_row[0] or 0

    # 计算每个事件的统计
    print("\n" + "=" * 80)
    print(f"  App 事件漏斗分析 (近30天)")
    print(f"  总付费用户: {total_payers:,}")
    print("=" * 80)

    rows = conn.execute("""
        SELECT 
            event_name,
            SUM(event_count) as total_30d,
            CAST(SUM(event_count) / 30.0 AS INTEGER) as daily_avg,
            SUM(paying_users) as total_payers,
            CASE WHEN SUM(event_count) > 0 
                 THEN ROUND(SUM(paying_users) * 100.0 / SUM(event_count), 2) 
                 ELSE 0 END as p_purchase
        FROM app_events
        GROUP BY event_name
        ORDER BY p_purchase DESC
    """).fetchall()

    # 按付费转化率排序输出
    print(f"\n  {'事件':<30} {'30天总量':>10} {'日均':>8} {'付费用户':>10} {'P(Purchase)':>12} {'推荐':>6}")
    print(f"  {'-'*30} {'-'*10} {'-'*8} {'-'*10} {'-'*12} {'-'*6}")

    for r in rows:
        event, total, daily, payers, pct = r
        # 推荐条件: 日均 ≥ 50 且 P(Purchase) ≥ 3%
        recommended = daily >= 50 and pct >= 3.0
        tag = "✅ AEO" if recommended else ""
        print(f"  {event[:30]:<30} {total:>10,} {daily:>8} {payers:>10,} {pct:>11.2f}% {tag:>6}")

    # 推荐
    candidates = [r for r in rows if r[3] >= 50 and r[4] >= 3.0]
    candidates.sort(key=lambda r: -r[4])

    print(f"\n  {'='*80}")
    print(f"  📊 AEO 推荐")
    print(f"  {'='*80}")

    if candidates:
        best = candidates[0]
        print(f"  首选优化事件: {best[0]} (P(Purchase)={best[4]:.1f}%, 日均{best[3]:,}个)")
        if len(candidates) > 1:
            print(f"  备选: {', '.join(c[0] for c in candidates[1:3])}")
    else:
        print(f"  ⚠️  没有满足条件的事件 (日均≥50 且 P(Purchase)≥3%)")
        print(f"  建议: 选 P(Purchase) 最高且日均最接近50的事件")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Adjust App Events → DuckDB 同步 + AEO 分析")
    parser.add_argument("--days", type=int, default=30, help="同步天数")
    parser.add_argument("--from-csv", type=str, default=None, help="从 CSV 导入")
    parser.add_argument("--analyze-only", action="store_true", help="仅分析已有数据")
    args = parser.parse_args()

    db_path = ROOT / "db" / "facebook_performance.duckdb"
    ensure_schema(db_path)

    if args.analyze_only:
        analyze_events(db_path)
        return

    if args.from_csv:
        sync_from_csv(db_path, args.from_csv)
    else:
        count = sync_from_adjust_api(db_path, args.days)
        if count == 0:
            print("\n📋 如果 Adjust Event API 不可用，可以通过以下方式导入:")
            print(f"   1. CSV 导入: python scripts/sync_adjust_events.py --from-csv events.csv")
            print(f"   2. CSV 格式: date,app,event_name,event_count,unique_users,revenue,paying_users")
            print(f"   3. 从 Adjust Datascape 导出 → 转换为上述格式")

    analyze_events(db_path)


if __name__ == "__main__":
    main()
