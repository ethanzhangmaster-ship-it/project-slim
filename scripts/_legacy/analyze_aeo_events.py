#!/usr/bin/env python3
"""AEO 候选事件自动分析 — 数据驱动的优化事件选择

数据源优先级:
  1. Adjust Raw Data / Callbacks → 事件级漏斗
  2. Facebook App Events API → 事件统计
  3. 经验模型 (Merge IAP 默认排序)

输出:
  - 事件漏斗表 (Install → ... → Purchase)
  - P(Purchase|Event) 排序
  - 每日事件量检查
  - 推荐 AEO 目标 + 切换时机

用法:
  python scripts/analyze_aeo_events.py              # 自动选择数据源
  python scripts/analyze_aeo_events.py --source adjust  # 强制从 Adjust
  python scripts/analyze_aeo_events.py --source facebook # 强制从 Facebook
  python scripts/analyze_aeo_events.py --use-model     # 使用经验模型
"""
from __future__ import annotations

import json, os, sys, time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

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


# ============================================================================
# Merge IAP 经验模型 — 事件优先级排序
# ============================================================================

@dataclass
class AeoEventCandidate:
    event_name: str
    fb_standard_event: str  # Facebook 标准事件名
    priority: int  # 1=最高
    purchase_correlation: str  # 付费相关度
    typical_daily_count: str  # 典型日事件量
    reason: str


# 基于 Merge IAP 游戏的经验排序
MERGE_IAP_EVENT_PRIORITY = [
    AeoEventCandidate(
        "点击礼包/特惠", "fb_mobile_add_to_cart",
        priority=1, purchase_correlation="极高 (~35-40%)",
        typical_daily_count="20-80",
        reason="已产生明确消费意图，是 Purchase 的最近上游事件",
    ),
    AeoEventCandidate(
        "打开商城", "fb_mobile_content_view",
        priority=2, purchase_correlation="高 (~20-25%)",
        typical_daily_count="40-150",
        reason="主动浏览付费内容，事件量比 OfferClick 大，预测力略低",
    ),
    AeoEventCandidate(
        "Merge 50次", "fb_mobile_custom_event",
        priority=3, purchase_correlation="中高 (~12-15%)",
        typical_daily_count="70-200",
        reason="深度玩法参与，活跃度高，事件量稳定",
    ),
    AeoEventCandidate(
        "到达 Level 10", "fb_mobile_level_achieved",
        priority=4, purchase_correlation="中 (~6-8%)",
        typical_daily_count="150-300",
        reason="留存稳定，筛掉浅度用户，事件量大",
    ),
    AeoEventCandidate(
        "到达 Level 5", "fb_mobile_level_achieved",
        priority=5, purchase_correlation="中低 (~2-3%)",
        typical_daily_count="250-500",
        reason="量最大但预测力弱，仅在以上事件都不够量时使用",
    ),
    AeoEventCandidate(
        "完成 Tutorial", "fb_mobile_tutorial_completion",
        priority=6, purchase_correlation="低 (~1-1.5%)",
        typical_daily_count="400-1000",
        reason="事件量最大但几乎无预测力，仅作最后选择",
    ),
]


def analyze_from_model() -> dict:
    """基于经验模型输出 AEO 推荐"""
    print("=" * 70)
    print("  AEO 候选事件分析 — 经验模型 (Merge IAP)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    print(f"\n  ⚠️  未检测到实时事件数据源，使用 Merge IAP 经验模型\n")

    print(f"  {'排名':<4} {'事件':<20} {'付费相关度':<12} {'日事件量':<12} {'选择':<6}")
    print(f"  {'-'*4} {'-'*20} {'-'*12} {'-'*12} {'-'*6}")

    for e in MERGE_IAP_EVENT_PRIORITY:
        fb_ready = "✅" if e.fb_standard_event else "⚠️"
        print(f"  {e.priority:<4} {e.event_name:<20} {e.purchase_correlation:<12} {e.typical_daily_count:<12} {fb_ready:<6}")

    # 推荐
    print(f"\n  {'='*70}")
    print(f"  📊 推荐 AEO 策略")
    print(f"  {'='*70}")
    print(f"  首选: {MERGE_IAP_EVENT_PRIORITY[0].event_name} ({MERGE_IAP_EVENT_PRIORITY[0].fb_standard_event})")
    print(f"    {MERGE_IAP_EVENT_PRIORITY[0].reason}")
    print(f"  备选: {MERGE_IAP_EVENT_PRIORITY[1].event_name} ({MERGE_IAP_EVENT_PRIORITY[1].fb_standard_event})")
    print(f"    {MERGE_IAP_EVENT_PRIORITY[1].reason}")
    print(f"  兜底: {MERGE_IAP_EVENT_PRIORITY[2].event_name} ({MERGE_IAP_EVENT_PRIORITY[2].fb_standard_event})")
    print(f"    {MERGE_IAP_EVENT_PRIORITY[2].reason}")

    return {"source": "model", "candidates": [{
        "event": e.event_name, "fb_event": e.fb_standard_event,
        "priority": e.priority, "correlation": e.purchase_correlation,
    } for e in MERGE_IAP_EVENT_PRIORITY]}


def analyze_from_adjust() -> dict:
    """从 Adjust API 拉取事件数据"""
    print("=" * 70)
    print("  AEO 候选事件分析 — Adjust 数据")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    adjust_token = os.environ.get("ADJUST_API_TOKEN", "")
    if not adjust_token:
        print("\n  ❌ ADJUST_API_TOKEN 未配置，回退到经验模型")
        return analyze_from_model()

    try:
        from market_ops.clients.adjust import AdjustClient

        # Adjust 的 events API endpoint
        import requests, urllib3
        urllib3.disable_warnings()

        # 尝试拉取事件数据
        base_url = "https://automate.adjust.com/reports-service/report"
        today = datetime.now().strftime("%Y-%m-%d")

        # 尝试用 event_metrics 拉事件级数据
        params = {
            "date_period": f"2026-05-29:{today}",
            "dimensions": "app,event_name,day",
            "metrics": "events,first_paying_users_d0",
            "ad_spend_mode": "network",
        }

        resp = requests.get(
            base_url,
            params=params,
            headers={"Authorization": f"Bearer {adjust_token}"},
            verify=False,
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("rows", [])
            if rows:
                return _process_event_rows(rows)
            else:
                print(f"\n  ⚠️  Adjust 返回空数据，可能需要不同的 API 端点")
                print(f"     请确认 Adjust 已配置事件回传 (Event Callbacks)")
                return analyze_from_model()
        else:
            print(f"\n  ⚠️  Adjust API 返回 {resp.status_code}: {resp.text[:200]}")
            return analyze_from_model()

    except Exception as e:
        print(f"\n  ❌ Adjust 数据拉取失败: {e}")
        return analyze_from_model()


def _process_event_rows(rows: list[dict]) -> dict:
    """处理 Adjust 事件数据，计算漏斗和 P(Purchase|Event)"""
    from collections import defaultdict

    event_counts = defaultdict(int)
    purchase_users = defaultdict(int)
    total_purchase = 0

    for row in rows:
        event = row.get("event_name", "unknown")
        count = int(row.get("events", 0))
        payers = int(row.get("first_paying_users_d0", 0))
        event_counts[event] += count
        purchase_users[event] += payers
        if "purchase" in event.lower():
            total_purchase += count

    # 计算
    results = []
    for event, count in sorted(event_counts.items(), key=lambda x: -x[1]):
        payers = purchase_users.get(event, 0)
        pct = (payers / count * 100) if count > 0 else 0
        daily = count / 30  # 近30天日均
        results.append({
            "event": event,
            "total_30d": count,
            "daily_avg": round(daily),
            "purchase_users": payers,
            "p_purchase_pct": round(pct, 2),
            "recommended": daily >= 50 and pct > 3,
        })

    print(f"\n  {'事件':<30} {'30天总量':>10} {'日均':>8} {'付费相关度':>10} {'推荐':>6}")
    print(f"  {'-'*30} {'-'*10} {'-'*8} {'-'*10} {'-'*6}")
    for r in results:
        tag = "✅" if r["recommended"] else ""
        print(f"  {r['event']:<30} {r['total_30d']:>10,} {r['daily_avg']:>8} {r['p_purchase_pct']:>8.1f}% {tag:>6}")

    return {"source": "adjust", "events": results}


def analyze_from_facebook() -> dict:
    """从 Facebook App Events API 拉取"""
    print("=" * 70)
    print("  AEO 候选事件分析 — Facebook App Events")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    token = os.environ.get("META_ACCESS_TOKEN", "")
    pixel_id = "259824536585005"  # Merge Witches pixel

    try:
        import requests, urllib3
        urllib3.disable_warnings()

        # Facebook App Events API (需要 app_id, 这里用 pixel)
        # 实际应该用: /{app_id}/app_event_types
        ver = "v22.0"
        resp = requests.get(
            f"https://graph.facebook.com/{ver}/{pixel_id}/stats",
            params={
                "access_token": token,
                "aggregation": "event",
                "time_range": json.dumps({"since": "2026-05-29", "until": datetime.now().strftime("%Y-%m-%d")}),
            },
            verify=False,
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                print(f"\n  Facebook Pixel 事件数据 ({len(data)} 种事件):")
                for item in data[:20]:
                    event = item.get("event", item.get("value", "?"))
                    count = item.get("count", item.get("value", 0))
                    print(f"    {event}: {count:,}")
                return {"source": "facebook", "raw": data}
            else:
                print("\n  ⚠️  无事件数据，Pixel 可能没有 App Events 配置")
                return analyze_from_model()
        else:
            print(f"\n  ⚠️  API 返回 {resp.status_code}")
            return analyze_from_model()

    except Exception as e:
        print(f"\n  ❌ 失败: {e}")
        return analyze_from_model()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AEO 候选事件自动分析")
    parser.add_argument("--source", choices=["adjust", "facebook", "model"], default="auto",
                        help="数据源 (默认 auto = 自动选择)")
    parser.add_argument("--use-model", action="store_true", help="强制使用经验模型")
    args = parser.parse_args()

    if args.use_model:
        result = analyze_from_model()
    elif args.source == "adjust":
        result = analyze_from_adjust()
    elif args.source == "facebook":
        result = analyze_from_facebook()
    else:
        # 自动选择: Adjust > Facebook > Model
        adjust_token = os.environ.get("ADJUST_API_TOKEN", "")
        if adjust_token:
            result = analyze_from_adjust()
        else:
            meta_token = os.environ.get("META_ACCESS_TOKEN", "")
            if meta_token:
                result = analyze_from_facebook()
            else:
                result = analyze_from_model()

    # 保存结果
    out_dir = ROOT / "output" / "aeo_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"aeo_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  完整报告: {out_path}")


if __name__ == "__main__":
    main()
