"""从 Facebook Graph API 拉取最近 N 天 creative performance 数据, 导入 DuckDB

读取 .env 中的 META_ACCESS_TOKEN 和 META_AD_ACCOUNT_ID,
调用 MetaAdsCreativeClient 拉取 insights, 写入 creative_performance 表。
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb

# 加载 .env
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def main() -> int:
    access_token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    ad_account_id = os.environ.get("META_AD_ACCOUNT_ID", "").strip()
    api_version = os.environ.get("META_API_VERSION", "v19.0").strip()
    game_name = os.environ.get("DEFAULT_GAME_NAME", "P04 Witch").strip()

    if not access_token:
        print("❌ 缺少 META_ACCESS_TOKEN")
        return 1
    if not ad_account_id:
        print("❌ 缺少 META_AD_ACCOUNT_ID")
        return 1

    # 日期范围: 最近 30 天
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    print(f"📡 Facebook Ads API {api_version}")
    print(f"   Account: act_{ad_account_id}")
    print(f"   Date range: {start_date} → {end_date}")
    print(f"   Game: {game_name}")
    print()

    # 拉取数据
    from market_ops.clients.meta_ads import MetaAdsCreativeClient

    client = MetaAdsCreativeClient(
        access_token=access_token,
        ad_account_id=ad_account_id,
        api_version=api_version,
        default_game_name=game_name,
    )

    print("  拉取 insights...")
    try:
        rows = client.fetch_creative_rows(start_date, end_date)
        print(f"  ✅ 获取 {len(rows)} 个 creative")
    except Exception as e:
        print(f"  ❌ API 调用失败: {e}")
        return 1

    if not rows:
        print("  ⚠️ 无数据返回 (可能 token 过期或账户无投放数据)")
        return 0

    # 导入 DuckDB
    db_path = ROOT / "db" / "facebook_performance.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)

    # 确保表存在
    conn.execute("""
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
        )
    """)

    # 按日期逐条写入 (避免覆盖已有不同日期的数据)
    today_str = end_date.isoformat()
    inserted = 0
    skipped = 0
    for row in rows:
        creative_id = row.asset_id
        # 检查是否已存在 (同 creative_id + 同日期)
        existing = conn.execute(
            "SELECT COUNT(*) FROM creative_performance WHERE creative_id = ? AND date = ?",
            [creative_id, today_str],
        ).fetchone()[0]
        if existing > 0:
            skipped += 1
            continue

        conn.execute("""
            INSERT INTO creative_performance
            (creative_id, campaign_id, adset_id, spend, impression, click, install,
             ctr, ipm, cpi, roas_d7, date, project, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [
            creative_id,
            row.campaign_id or "",
            row.adgroup_id or "",
            row.spend,
            int(row.impressions),
            int(row.clicks),
            int(row.installs),
            row.ctr * 100,  # Facebook API 返回小数, DB 存百分比
            0.0,  # ipm
            row.spend / row.installs if row.installs > 0 else 0.0,  # cpi
            row.roas,  # roas_d7
            today_str,
            row.game or game_name,
        ])
        inserted += 1

    conn.commit()

    # 验证
    total = conn.execute("SELECT COUNT(*) FROM creative_performance").fetchone()[0]
    dates = conn.execute(
        "SELECT COUNT(DISTINCT date) FROM creative_performance"
    ).fetchone()[0]
    by_project = conn.execute(
        "SELECT project, COUNT(*), SUM(spend), SUM(install) FROM creative_performance GROUP BY project"
    ).fetchall()

    print(f"\n  导入: {inserted} 条新增, {skipped} 条跳过 (已存在)")
    print(f"  creative_performance 总计: {total} 条, {dates} 个日期")
    print(f"\n  按项目:")
    for p, n, spend, installs in by_project:
        print(f"    {p}: {n} 条 | \${spend:,.0f} | {installs} 安装")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
