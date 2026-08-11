#!/usr/bin/env python3
"""Facebook 数据拉取脚本 — 在你本地有 Facebook 网络的环境运行

用法:
  python3 fetch_facebook_data_local.py

输出:
  output/facebook_fresh_data.json — 拉取的原始数据

将此文件传回项目，然后运行:
  python3 scripts/import_facebook_fresh.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
import urllib3
urllib3.disable_warnings()


# ============================================================================
# .env 自动加载（不依赖 python-dotenv，避免引入新依赖）
# ============================================================================
def _load_dotenv() -> None:
    """从项目根目录的 .env 文件加载环境变量（不覆盖已存在的）。"""
    # scripts/ → 项目根
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


# ============================================================================
# 配置 — 优先环境变量，回退到默认值
# ============================================================================

ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")

AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "1455525822955003")
API_VERSION = os.environ.get("META_API_VERSION", "v19.0")
LOOKBACK_DAYS = int(os.environ.get("META_CREATIVE_LOOKBACK_DAYS", "30"))

OUTPUT_FILE = "output/facebook_fresh_data.json"


def fetch_paginated(url: str, params: dict) -> list[dict]:
    """分页拉取"""
    results = []
    while url:
        try:
            r = requests.get(url, params=params, verify=False, timeout=60)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                print(f"  ❌ API Error: {data['error']['message']}")
                break
            results.extend(data.get("data", []))
            paging = data.get("paging", {})
            url = paging.get("next", "")
            params = None
            if url:
                print(f"    分页: {len(results)} rows...")
        except Exception as e:
            print(f"  ❌ 网络错误: {e}")
            break
    return results


def main() -> int:
    print("=" * 60)
    print("  Facebook Ads 数据拉取")
    print(f"  Account: act_{AD_ACCOUNT_ID}")
    print("=" * 60)

    if not ACCESS_TOKEN:
        print("⚠️  请先设置环境变量 META_ACCESS_TOKEN")
        return 1

    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    print(f"\n  日期范围: {start_date} → {end_date}")
    print(f"  测试连通性...")

    # Step 1: 验证 token
    try:
        r = requests.get(f"https://graph.facebook.com/{API_VERSION}/me",
                         params={"access_token": ACCESS_TOKEN},
                         verify=False, timeout=20)
        me = r.json()
        if "error" in me:
            print(f"  ❌ Token 无效: {me['error']['message']}")
            return 1
        print(f"  ✅ Token 有效: {me.get('name', '?')}")
    except Exception as e:
        print(f"  ❌ 无法连接 Facebook: {e}")
        return 1

    # Step 2: 获取广告账户列表
    print(f"\n  获取广告账户...")
    try:
        r = requests.get(f"https://graph.facebook.com/{API_VERSION}/me/adaccounts",
                         params={"access_token": ACCESS_TOKEN, "fields": "id,name"},
                         verify=False, timeout=20)
        accounts = r.json().get("data", [])
        print(f"  ✅ {len(accounts)} 个账户:")
        for a in accounts[:10]:
            print(f"    act_{a['id']} | {a.get('name', '?')}")
    except Exception as e:
        print(f"  ⚠️  {e}")

    # Step 3: 拉取 ads (获取 creative 信息)
    print(f"\n  拉取 ads (含 creative 信息)...")
    ad_params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,name,effective_status,campaign{name},adset{name},creative{id,name,title,thumbnail_url,image_url}",
        "limit": 500,
    }
    ads = fetch_paginated(f"https://graph.facebook.com/{API_VERSION}/act_{AD_ACCOUNT_ID}/ads", ad_params)
    print(f"  ✅ {len(ads)} 个 ad")

    # 构建 ad_id → creative_id 映射
    ad_creative_map = {}
    for ad in ads:
        ad_id = ad.get("id", "")
        creative = ad.get("creative", {})
        creative_id = creative.get("id", "")
        if ad_id and creative_id:
            ad_creative_map[ad_id] = {
                "creative_id": creative_id,
                "creative_name": creative.get("name", ""),
                "ad_name": ad.get("name", ""),
                "campaign_name": (ad.get("campaign") or {}).get("name", ""),
                "adset_name": (ad.get("adset") or {}).get("name", ""),
                "status": ad.get("effective_status", ""),
            }

    print(f"  ad→creative 映射: {len(ad_creative_map)} 条")

    # Step 4: 拉取 insights (performance 数据)
    print(f"\n  拉取 insights ({start_date} → {end_date})...")
    insight_params = {
        "access_token": ACCESS_TOKEN,
        "level": "ad",
        "time_range": json.dumps({"since": start_date.isoformat(), "until": end_date.isoformat()}),
        "fields": "ad_id,ad_name,campaign_name,adset_name,spend,impressions,clicks,ctr,actions,action_values",
        "limit": 500,
    }
    insights = fetch_paginated(
        f"https://graph.facebook.com/{API_VERSION}/act_{AD_ACCOUNT_ID}/insights",
        insight_params,
    )
    print(f"  ✅ {len(insights)} 条 insight")

    # Step 5: 合并
    print(f"\n  合并 ad + insight 数据...")
    merged = []
    for ins in insights:
        ad_id = ins.get("ad_id", "")
        ad_info = ad_creative_map.get(ad_id, {})
        merged.append({
            "creative_id": ad_info.get("creative_id", ad_id),
            "creative_name": ad_info.get("creative_name", ""),
            "ad_id": ad_id,
            "ad_name": ins.get("ad_name", ad_info.get("ad_name", "")),
            "campaign_name": ins.get("campaign_name", ad_info.get("campaign_name", "")),
            "adset_name": ins.get("adset_name", ad_info.get("adset_name", "")),
            "spend": float(ins.get("spend", 0)),
            "impressions": int(ins.get("impressions", 0)),
            "clicks": int(ins.get("clicks", 0)),
            "ctr": float(ins.get("ctr", 0)),
            "actions": ins.get("actions", []),
            "action_values": ins.get("action_values", []),
            "date_start": ins.get("date_start", ""),
            "date_stop": ins.get("date_stop", ""),
        })

    # 统计
    total_spend = sum(m["spend"] for m in merged)
    total_imp = sum(m["impressions"] for m in merged)
    total_clicks = sum(m["clicks"] for m in merged)
    unique_creatives = len(set(m["creative_id"] for m in merged if m["creative_id"]))
    dates = sorted(set(m["date_start"] for m in merged if m["date_start"]))

    print(f"\n  {'='*60}")
    print(f"  拉取结果:")
    print(f"    总记录: {len(merged)}")
    print(f"    唯一 creative: {unique_creatives}")
    print(f"    日期范围: {dates[0] if dates else '?'} → {dates[-1] if dates else '?'} ({len(dates)} 天)")
    print(f"    总 spend: \${total_spend:,.0f}")
    print(f"    总 impressions: {total_imp:,}")
    print(f"    总 clicks: {total_clicks:,}")

    # 保存
    output_path = Path(OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "pulled_at": date.today().isoformat(),
        "account_id": AD_ACCOUNT_ID,
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "stats": {
            "total_rows": len(merged),
            "unique_creatives": unique_creatives,
            "total_spend": total_spend,
            "total_impressions": total_imp,
            "total_clicks": total_clicks,
            "dates": dates,
        },
        "data": merged,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  ✅ 数据已保存: {output_path}")
    print(f"  文件大小: {output_path.stat().st_size / 1024:.0f} KB")
    print(f"\n  将此文件传回项目, 然后运行:")
    print(f"    python3 scripts/import_facebook_fresh.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
