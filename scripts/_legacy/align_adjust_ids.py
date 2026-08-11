#!/usr/bin/env python3
"""Adjust ↔ Facebook creative_id 对齐模块

问题: Adjust creative_id_network (18位) ≠ DuckDB creative_id (16位)
      → 851 个素材只有 35 个能匹配 → Intent Score 全用全局 2%

解法: 通过 Facebook Graph API 拉取 ad → creative 映射链
      Adjust creative_id_network → Facebook ad_id → Facebook creative_id → DuckDB creative_id

输出: DuckDB creative_id_mapping 表

用法:
  python scripts/align_adjust_ids.py                    # 全量对齐
  python scripts/align_adjust_ids.py --sample 10         # 采样测试
"""
from __future__ import annotations

import json, os, sys, time
from collections import defaultdict
from pathlib import Path

import duckdb
import requests as _req
import urllib3
urllib3.disable_warnings()

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
    conn = duckdb.connect(str(db_path), read_only=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS creative_id_mapping (
            adjust_creative_id VARCHAR,
            facebook_ad_id VARCHAR,
            facebook_creative_id VARCHAR,
            duckdb_creative_id VARCHAR,
            campaign_id VARCHAR,
            adset_id VARCHAR,
            source VARCHAR,
            matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()


def pull_facebook_ad_map(acct: str, token: str, ver: str = "v22.0", sample: int = 0) -> dict:
    """从 Facebook API 拉 ad_id → creative_id 映射
    
    返回: {ad_id: {creative_id, campaign_id, adset_id, ad_name}}
    """
    ad_map = {}
    url = f"https://graph.facebook.com/{ver}/act_{acct}/ads"
    params = {
        "access_token": token,
        "fields": "id,name,campaign_id,adset_id,creative{id}",
        "limit": 500 if sample == 0 else min(sample, 500),
    }

    session = _req.Session()
    session.verify = False

    page = 0
    while url:
        try:
            r = session.get(url, params=params, timeout=60)
            data = r.json()
            if "error" in data:
                print(f"  Facebook API error: {data['error']['message'][:100]}")
                break

            for ad in data.get("data", []):
                ad_id = ad.get("id", "")
                creative = ad.get("creative", {})
                creative_id = creative.get("id", "") if creative else ""
                if ad_id and creative_id:
                    ad_map[ad_id] = {
                        "facebook_creative_id": creative_id,
                        "campaign_id": ad.get("campaign_id", ""),
                        "adset_id": ad.get("adset_id", ""),
                        "ad_name": ad.get("name", ""),
                    }

            page += 1
            print(f"  Facebook page {page}: {len(ad_map)} ads mapped...")

            paging = data.get("paging", {})
            url = paging.get("next", "")
            params = None

            if sample and len(ad_map) >= sample:
                break

        except Exception as e:
            print(f"  Facebook API error: {e}")
            break

    return ad_map


def pull_adjust_creative_data(token: str) -> list[dict]:
    """从 Adjust 拉 creative_id_network 数据"""
    rows = []
    try:
        r = _req.get(
            "https://automate.adjust.com/reports-service/report",
            params={
                "date_period": "2026-06-01:2026-06-30",
                "dimensions": "app,creative_id_network",
                "metrics": "installs,first_paying_users_d0,revenue",
                "ad_spend_mode": "network",
            },
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            verify=False, timeout=30,
        )
        for row in r.json().get("rows", []):
            cid = str(row.get("creative_id_network", ""))
            app = row.get("app", "")
            if cid and cid != "unknown" and "P04" in app:
                rows.append({
                    "adjust_creative_id": cid,
                    "installs": int(row.get("installs", 0)),
                    "payers": int(row.get("first_paying_users_d0", 0)),
                    "revenue": float(row.get("revenue", 0)),
                })
    except Exception as e:
        print(f"  Adjust error: {e}")
    return rows


def build_mapping(db_path: Path, ad_map: dict, adjust_rows: list[dict]):
    """构建 Adjust → Facebook → DuckDB 三级映射"""
    conn = duckdb.connect(str(db_path), read_only=True)

    # DuckDB creative_id 列表
    db_cids = set(str(r[0]) for r in conn.execute(
        "SELECT DISTINCT creative_id FROM creative_performance WHERE LENGTH(creative_id) > 0"
    ).fetchall())

    # 构建 Facebook creative_id → DuckDB creative_id 映射
    # DuckDB creative_performance 的 creative_id 可能是 campaign_id
    fb_to_db = {}
    db_campaigns = conn.execute("""
        SELECT DISTINCT creative_id, campaign_id FROM creative_performance 
        WHERE LENGTH(creative_id) > 0 AND campaign_id IS NOT NULL
    """).fetchall()
    for db_cid, db_camp in db_campaigns:
        if db_camp:
            fb_to_db[str(db_camp)] = str(db_cid)

    conn.close()

    # 对齐
    matched = 0
    conn_w = duckdb.connect(str(db_path), read_only=False)

    for adj_row in adjust_rows:
        adj_cid = adj_row["adjust_creative_id"]

        # 尝试直接匹配 DuckDB
        if adj_cid in db_cids:
            conn_w.execute("""
                INSERT INTO creative_id_mapping 
                (adjust_creative_id, duckdb_creative_id, source)
                VALUES (?, ?, 'direct')
            """, [adj_cid, adj_cid])
            matched += 1
            continue

        # 通过 Facebook ad_id 匹配
        if adj_cid in ad_map:
            fb_info = ad_map[adj_cid]
            fb_creative = fb_info["facebook_creative_id"]
            fb_campaign = fb_info["campaign_id"]

            # 尝试通过 campaign_id 匹配 DuckDB
            db_cid = fb_to_db.get(fb_campaign, "")
            if db_cid:
                conn_w.execute("""
                    INSERT INTO creative_id_mapping
                    (adjust_creative_id, facebook_ad_id, facebook_creative_id, 
                     duckdb_creative_id, campaign_id, source)
                    VALUES (?, ?, ?, ?, ?, 'facebook_campaign')
                """, [adj_cid, adj_cid, fb_creative, db_cid, fb_campaign])
                matched += 1
                continue

        # 没匹配上，记录 adjust 侧数据
        conn_w.execute("""
            INSERT INTO creative_id_mapping
            (adjust_creative_id, source)
            VALUES (?, 'adjust_only')
        """, [adj_cid])

    conn_w.close()
    return matched


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Adjust ↔ Facebook creative_id 对齐")
    parser.add_argument("--sample", type=int, default=0, help="采样数量 (0=全量)")
    args = parser.parse_args()

    db_path = ROOT / "db" / "facebook_performance.duckdb"
    ensure_schema(db_path)

    acct = os.environ.get("META_AD_ACCOUNT_ID", "")
    meta_token = os.environ.get("META_ACCESS_TOKEN", "")
    adjust_token = os.environ.get("ADJUST_API_TOKEN", "")

    if not acct or not meta_token:
        print("❌ META_AD_ACCOUNT_ID / META_ACCESS_TOKEN 未设置")
        return

    print("=" * 60)
    print("  Adjust ↔ Facebook creative_id 对齐")
    print("=" * 60)

    # Step 1: Facebook ad map
    print("\n[1/3] 拉取 Facebook ad → creative 映射...")
    ad_map = pull_facebook_ad_map(acct, meta_token, sample=args.sample)
    print(f"  Facebook ad map: {len(ad_map)} 条")

    # Step 2: Adjust data
    print("\n[2/3] 拉取 Adjust creative 数据...")
    adjust_rows = pull_adjust_creative_data(adjust_token)
    print(f"  Adjust P04 creatives: {len(adjust_rows)} 条")

    # Step 3: 对齐
    print("\n[3/3] 构建映射...")
    matched = build_mapping(db_path, ad_map, adjust_rows)
    print(f"  匹配成功: {matched}/{len(adjust_rows)}")

    # 统计
    conn = duckdb.connect(str(db_path), read_only=True)
    stats = conn.execute("""
        SELECT source, COUNT(*) 
        FROM creative_id_mapping 
        WHERE duckdb_creative_id IS NOT NULL 
        GROUP BY source
    """).fetchall()
    print(f"\n  映射来源:")
    for src, cnt in stats:
        print(f"    {src}: {cnt}")
    conn.close()

    print(f"\n  ✅ 对齐完成! 运行 score_creatives.py 使用新映射")


if __name__ == "__main__":
    main()
