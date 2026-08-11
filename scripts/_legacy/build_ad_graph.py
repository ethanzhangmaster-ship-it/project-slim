#!/usr/bin/env python3
"""构建 Ad Graph — 从 Facebook API 拉取 Ads-level 完整数据

输出: DuckDB ad_graph 表 (ad_id → creative_id → image_url → text → spend → ...)

这是整个系统的"唯一事实源"，后续 Adjust 对齐、Intent Score、Revenue Score 都基于此表。
"""
from __future__ import annotations

import json, os, sys, time, hashlib
from datetime import datetime
from pathlib import Path

import duckdb
import requests
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
        CREATE TABLE IF NOT EXISTS ad_graph (
            ad_id VARCHAR PRIMARY KEY,
            ad_name VARCHAR,
            adset_id VARCHAR,
            adset_name VARCHAR,
            campaign_id VARCHAR,
            campaign_name VARCHAR,
            creative_id VARCHAR,
            image_url VARCHAR,
            thumbnail_url VARCHAR,
            primary_text VARCHAR,
            headline VARCHAR,
            call_to_action VARCHAR,
            creative_hash VARCHAR,
            -- 性能
            impressions INTEGER,
            clicks INTEGER,
            spend DOUBLE,
            ctr DOUBLE,
            cpm DOUBLE,
            cpc DOUBLE,
            installs INTEGER,
            purchases INTEGER,
            purchase_value DOUBLE,
            -- 元数据
            status VARCHAR,
            pulled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # creative 去重表 (同一个 creative 可能被多个 ad 使用)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS creative_graph (
            creative_id VARCHAR PRIMARY KEY,
            creative_hash VARCHAR,
            image_url VARCHAR,
            primary_text VARCHAR,
            headline VARCHAR,
            call_to_action VARCHAR,
            pulled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()


def pull_ads(acct: str, token: str, ver: str = "v22.0", lookback_days: int = 14):
    """拉取 Ads 级别完整数据"""
    session = requests.Session()
    session.verify = False

    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=lookback_days)

    print(f"拉取: {start} → {end}")

    # Step 1: 拉取所有 ads (含 creative 信息)
    print("[1/3] 拉取 Ads + Creative 信息...")
    ad_map = {}
    url = f"https://graph.facebook.com/{ver}/act_{acct}/ads"
    params = {
        "access_token": token,
        "fields": "id,name,status,adset_id,adset{name},campaign_id,campaign{name},"
                  "creative{id,title,body,image_url,thumbnail_url,"
                  "call_to_action_type,object_story_spec}",
        "limit": 500,
    }

    page = 0
    while url:
        try:
            r = session.get(url, params=params, timeout=60)
            data = r.json()
            if "error" in data:
                print(f"  API error: {data['error']['message'][:100]}")
                break

            for ad in data.get("data", []):
                ad_id = ad.get("id", "")
                creative = ad.get("creative", {})
                adset = ad.get("adset", {})
                campaign = ad.get("campaign", {})

                oss = creative.get("object_story_spec", {}) or {}
                link_data = oss.get("link_data", {}) or {}
                
                ad_map[ad_id] = {
                    "ad_id": ad_id,
                    "ad_name": ad.get("name", ""),
                    "adset_id": ad.get("adset_id", ""),
                    "adset_name": adset.get("name", ""),
                    "campaign_id": ad.get("campaign_id", ""),
                    "campaign_name": campaign.get("name", ""),
                    "creative_id": creative.get("id", ""),
                    "image_url": creative.get("image_url", "") or link_data.get("image_hash", ""),
                    "thumbnail_url": creative.get("thumbnail_url", ""),
                    "primary_text": creative.get("body", "") or link_data.get("message", ""),
                    "headline": creative.get("title", "") or link_data.get("name", ""),
                    "call_to_action": creative.get("call_to_action_type", "") or 
                                      (link_data.get("call_to_action", {}).get("type", "") if isinstance(link_data.get("call_to_action"), dict) else ""),
                    "status": ad.get("status", ad.get("effective_status", "")),
                }

            page += 1
            print(f"  Page {page}: {len(ad_map)} ads")

            paging = data.get("paging", {})
            url = paging.get("next", "")
            params = None

        except Exception as e:
            print(f"  Error: {e}")
            break

    # Step 2: 拉取 insights (性能数据)
    print(f"\n[2/3] 拉取 Insights...")
    insights_url = f"https://graph.facebook.com/{ver}/act_{acct}/insights"
    insights_params = {
        "access_token": token,
        "level": "ad",
        "time_range": json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
        "fields": "ad_id,ad_name,impressions,clicks,spend,ctr,cpm,cpc,"
                  "actions,action_values",
        "limit": 500,
    }

    perf_map = {}
    page = 0
    url = insights_url
    while url:
        try:
            r = session.get(url, params=insights_params, timeout=60)
            data = r.json()
            if "error" in data:
                print(f"  API error: {data['error']['message'][:100]}")
                break

            for ins in data.get("data", []):
                ad_id = ins.get("ad_id", "")
                if not ad_id:
                    continue

                # 提取 installs / purchases
                installs = 0
                purchases = 0
                purchase_value = 0.0
                for action in ins.get("actions", []):
                    at = action.get("action_type", "")
                    if "install" in at.lower() or "app_install" in at.lower():
                        installs += int(action.get("value", 0))
                    if "purchase" in at.lower() or "fb_mobile_purchase" in at.lower():
                        purchases += int(action.get("value", 0))
                for av in ins.get("action_values", []):
                    if "purchase" in av.get("action_type", "").lower():
                        purchase_value += float(av.get("value", 0))

                perf_map[ad_id] = {
                    "impressions": int(ins.get("impressions", 0)),
                    "clicks": int(ins.get("clicks", 0)),
                    "spend": float(ins.get("spend", 0)),
                    "ctr": float(ins.get("ctr", 0)),
                    "cpm": float(ins.get("cpm", 0)),
                    "cpc": float(ins.get("cpc", 0)),
                    "installs": installs,
                    "purchases": purchases,
                    "purchase_value": purchase_value,
                }

            page += 1
            print(f"  Page {page}: {len(perf_map)} ad insights")

            paging = data.get("paging", {})
            url = paging.get("next", "")
            insights_params = None

        except Exception as e:
            print(f"  Error: {e}")
            break

    # Step 3: 合并 + 生成 creative_hash + 写入 DB
    print(f"\n[3/3] 合并 + 写入 DuckDB...")
    conn = duckdb.connect(str(ROOT / "db" / "facebook_performance.duckdb"), read_only=False)

    ad_count = 0
    creative_set = set()

    for ad_id, ad_info in ad_map.items():
        perf = perf_map.get(ad_id, {})
        creative_id = ad_info.get("creative_id", "")

        # 生成 creative_hash
        hash_input = (
            (ad_info.get("image_url") or "") +
            (ad_info.get("primary_text") or "") +
            (ad_info.get("headline") or "")
        )
        creative_hash = hashlib.sha1(hash_input.encode()).hexdigest()[:16] if hash_input else ""

        # 写入 ad_graph
        conn.execute("""
            INSERT OR REPLACE INTO ad_graph 
            (ad_id, ad_name, adset_id, adset_name, campaign_id, campaign_name,
             creative_id, image_url, thumbnail_url, primary_text, headline, call_to_action,
             creative_hash, impressions, clicks, spend, ctr, cpm, cpc,
             installs, purchases, purchase_value, status, pulled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [
            ad_id, ad_info.get("ad_name"), ad_info.get("adset_id"), ad_info.get("adset_name"),
            ad_info.get("campaign_id"), ad_info.get("campaign_name"),
            creative_id, ad_info.get("image_url"), ad_info.get("thumbnail_url"),
            ad_info.get("primary_text"), ad_info.get("headline"), ad_info.get("call_to_action"),
            creative_hash,
            perf.get("impressions", 0), perf.get("clicks", 0), perf.get("spend", 0),
            perf.get("ctr", 0), perf.get("cpm", 0), perf.get("cpc", 0),
            perf.get("installs", 0), perf.get("purchases", 0), perf.get("purchase_value", 0),
            ad_info.get("status", ""),
        ])
        ad_count += 1

        # 写入 creative_graph (去重)
        if creative_id and creative_id not in creative_set:
            creative_set.add(creative_id)
            conn.execute("""
                INSERT OR REPLACE INTO creative_graph
                (creative_id, creative_hash, image_url, primary_text, headline, call_to_action, pulled_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [
                creative_id, creative_hash, ad_info.get("image_url"),
                ad_info.get("primary_text"), ad_info.get("headline"),
                ad_info.get("call_to_action"),
            ])

    conn.close()

    print(f"\n  ✅ ad_graph: {ad_count} 条")
    print(f"  ✅ creative_graph: {len(creative_set)} 条")
    print(f"  ✅ 数据已写入 DuckDB")


def main():
    acct = os.environ.get("META_AD_ACCOUNT_ID", "")
    token = os.environ.get("META_ACCESS_TOKEN", "")

    if not acct or not token:
        print("❌ META_AD_ACCOUNT_ID / META_ACCESS_TOKEN 未设置")
        return

    db_path = ROOT / "db" / "facebook_performance.duckdb"
    ensure_schema(db_path)

    print("=" * 60)
    print("  构建 Ad Graph")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    pull_ads(acct, token)


if __name__ == "__main__":
    main()
