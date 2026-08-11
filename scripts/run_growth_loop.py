"""Growth Loop V2 入口脚本 — 串联 Meta Ads 数据流与 GrowthLoopOrchestrator。

接线 2 实现：将 FeedbackController 产出的信号直接喂给 Orchestrator.run_cycle()，
完成 "Meta Ads API → 聚合 → 信号 → 诊断 → 假设 → 策略 → 动作 → 执行 → 评估" 全链路。

接线 1 实现：在执行前注入 RealityGate 数据可信度门控。
接线 3 实现：用产品侧数据 (七域快照+PlayerProfile) 富集广告侧指标。

数据流:
  ┌───────────────────────────────────────────────────────────────┐
  │  Meta Ads API                                                  │
  │    ↓ fetch_performance_rows (当前周期 + 上一周期)              │
  │  aggregate_by_creative → {creative_id: metrics}                │
  │    ↓                                                           │
  │  接线 3: MetricsAdapter (七域快照 + PlayerProfile 富集)         │
  │    ↓                                                           │
  │  generate_predictions → RealityPrediction 列表                 │
  │    ↓                                                           │
  │  FeedbackController.evaluate → FeedbackResult.triggered        │
  │    ↓ (信号 + current_metrics + previous_metrics)               │
  │  接线 1: RealityGate 审计 (可信分门控)                          │
  │    ↓                                                           │
  │  GrowthLoopOrchestrator.run_cycle                              │
  │    ├─ Phase A: 评估到期 PendingEvaluation                      │
  │    ├─ Phase B: Diagnose → Hypothesize → Select → Plan → Execute│
  │    └─ Phase C: 持久化全部状态                                   │
  │    ↓                                                           │
  │  CycleResult (含诊断/假设/策略/动作/执行结果)                   │
  └───────────────────────────────────────────────────────────────┘

用法:
    # Dry-run (默认, 不调用真实 API, 不执行真实动作)
    python scripts/run_growth_loop.py --days 7

    # 真实执行 (调用 Meta Ads API + 执行平台动作)
    python scripts/run_growth_loop.py --days 7 --live

    # 启用接线 3 指标适配 (七域快照富集)
    python scripts/run_growth_loop.py --days 7 --enrich-metrics

    # 启用接线 3 + IAA 收入归因
    python scripts/run_growth_loop.py --days 7 --enrich-metrics --player-app-id com.game.x

    # 指定持久化目录和观察窗口
    python scripts/run_growth_loop.py --days 7 --data-dir data/growth_loop --window-hours 168
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from dotenv import load_dotenv

from market_ops.clients.meta_ads import MetaAdsCreativeClient
from market_ops.creative_vision_runtime.reality.feedback import (
    FeedbackController,
    FeedbackResult,
)
from market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)
from market_ops.models import AdsPerformanceRow

# 复用 run_feedback_bridge 中的聚合和预测逻辑
from scripts.run_feedback_bridge import (
    MemoryEnricher,
    aggregate_by_creative,
    fetch_facebook_data,
    generate_predictions,
)

from scripts.growth_loop_orchestrator import GrowthLoopOrchestrator, CycleResult
from scripts.meta_ads_adapter import MetaAdsPlatformAdapter
from scripts.metrics_adapter import MetricsAdapter, EnrichmentReport

# RealityGate 接线 1: 导入 Reality 审计组件
from growth_reality.snapshot import build_company_snapshot
from growth_reality.validation.auditor import RealityAuditor


# ── 阈值常量 ──────────────────────────────────────────────

# 日预算估算: 用近 N 天日均花费作为当前预算的近似
# (Meta API 的 daily_budget 字段需要单独调用获取，这里用 spend/days 近似)
BUDGET_ESTIMATE_DAYS = 1

# 最小花费阈值 (USD), 低于此值的 creative 不纳入 Growth Loop
MIN_SPEND_FOR_LOOP = 10.0


# ──────────────────────────────────────────────
# RealityGate 审计 (接线 1)
# ──────────────────────────────────────────────


def run_reality_audit(
    game_name: str,
    current_metrics: dict[str, dict[str, float]],
    data_dir: str = "data",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """运行 Reality 审计，返回可信分和 game_id 映射。

    构建一个简化的 CompanySnapshot (单游戏), 调用 RealityAuditor 审计,
    提取 RealityScore 用于 ActionExecutor 门控。

    Args:
        game_name: 游戏名称 (如 "P04")
        current_metrics: 创意级指标 {creative_id: {spend, clicks, ...}}
        data_dir: 审计数据目录

    Returns:
        (reality_scores, creative_to_game_map)
        - reality_scores: {game_id: RealityScore}
        - creative_to_game_map: {creative_id: game_id}
    """
    from growth_reality.models import (
        GrowthRealitySnapshot,
        RevenueFact,
        AcquisitionFact,
        CreativeFact,
        ProductFact,
    )

    # 汇总创意级指标 → 游戏级 Fact
    total_spend = sum(m.get("spend", 0.0) for m in current_metrics.values())
    total_installs = sum(m.get("installs", 0) for m in current_metrics.values())
    total_revenue = sum(m.get("revenue", 0.0) for m in current_metrics.values())
    total_clicks = sum(m.get("clicks", 0) for m in current_metrics.values())
    total_impressions = sum(m.get("impressions", 0) for m in current_metrics.values())

    avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
    avg_cpi = total_spend / total_installs if total_installs > 0 else 0.0
    avg_roas = total_revenue / total_spend if total_spend > 0 else 0.0

    snap = GrowthRealitySnapshot(
        game_id=game_name,
        timestamp=date.today().isoformat(),
        revenue=RevenueFact(daily_revenue=total_revenue),
        acquisition=AcquisitionFact(
            spend=total_spend,
            installs=total_installs,
            cpi=avg_cpi,
            roas=avg_roas,
        ),
        creative=CreativeFact(ctr=avg_ctr),
        product=ProductFact(),
        confidence=0.85,
        sources=["meta_ads"],
        real_confidence=0.8,
        real_domains=["revenue", "acquisition", "creative"],
    )

    company = build_company_snapshot([snap], snap.timestamp)

    auditor = RealityAuditor(data_dir=data_dir)
    report = auditor.audit(
        company,
        adjust_by_game={game_name: total_revenue * 0.6},  # IAP 近似
        max_by_game={game_name: total_revenue * 0.4},      # Ads 近似
        reported_by_game={game_name: total_revenue},
    )

    # 提取 RealityScore
    reality_scores: dict[str, Any] = {}
    for entry in report.entries:
        if entry.score:
            reality_scores[entry.game_id] = entry.score
            level = entry.score.decision_level
            print(
                f"  RealityScore[{entry.game_id}]: "
                f"composite={entry.score.composite:.3f} "
                f"level={level} "
                f"(coverage={entry.score.coverage:.2f} "
                f"freshness={entry.score.freshness:.2f} "
                f"consistency={entry.score.consistency:.2f})"
            )

    # 构建 creative_id → game_id 映射 (所有 creative 归属同一 game)
    creative_to_game = {cid: game_name for cid in current_metrics}

    return reality_scores, creative_to_game


def make_game_id_resolver(
    creative_to_game: dict[str, str],
) -> Any:
    """创建 creative_id → game_id 解析器。"""
    def resolver(creative_id: str) -> str:
        return creative_to_game.get(creative_id, "")
    return resolver


# ──────────────────────────────────────────────
# 数据准备
# ──────────────────────────────────────────────


def load_meta_ads_data(
    access_token: str,
    ad_account_id: str,
    api_version: str,
    game_name: str,
    days: int,
) -> tuple[list[AdsPerformanceRow], list[AdsPerformanceRow]]:
    """拉取当前周期和上一周期的 Meta Ads 数据。

    Returns:
        (current_rows, previous_rows)
    """
    print(f"  拉取当前周期数据 ({days} 天)...")
    end = date.today()
    start = end - timedelta(days=days)
    current_rows = fetch_facebook_data(
        access_token, ad_account_id, api_version, game_name, days
    )

    print(f"  拉取上一周期数据 (用于趋势对比)...")
    prev_end = start
    prev_start = prev_end - timedelta(days=days)
    client = MetaAdsCreativeClient(
        access_token=access_token,
        ad_account_id=ad_account_id,
        api_version=api_version,
        default_game_name=game_name,
    )
    try:
        prev_rows = client.fetch_performance_rows(prev_start, prev_end)
    except Exception as exc:
        print(f"  ⚠ 上一周期数据拉取失败: {exc}")
        print(f"  ⚠ 将使用空数据集 (趋势对比将不可用)")
        prev_rows = []
    print(f"  当前周期: {len(current_rows)} 条 ({start} ~ {end})")
    print(f"  上一周期: {len(prev_rows)} 条 ({prev_start} ~ {prev_end})")
    return current_rows, prev_rows


def build_creative_to_adset_map(
    rows: list[AdsPerformanceRow],
) -> dict[str, str]:
    """构建 creative_id → adset_id 映射。

    AdsPerformanceRow 不含 adset_id 字段, 这里用 ad_id 作为 adset 的近似
    (Facebook Ads 中 ad 隶属于 adset, 同一 creative 可能在多个 adset 中,
    此处取第一次出现的 ad_id 作为占位)。

    对于 creative_id 为空的行, 用 ad_id 同时作为 key 和 value。
    """
    mapping: dict[str, str] = {}
    for row in rows:
        cid = row.creative_id or row.ad_id
        if cid and cid not in mapping:
            # 用 ad_id 作为 adset_id 近似
            mapping[cid] = row.ad_id or cid
    return mapping


def estimate_current_budgets(
    current_metrics: dict[str, dict[str, float]],
    days: int,
) -> dict[str, float]:
    """从当前周期花费估算各 adset 的日预算。

    Args:
        current_metrics: {creative_id: {spend, clicks, ...}}
        days: 当前周期天数

    Returns:
        {adset_id: daily_budget} — adset_id 此处用 creative_id 近似
    """
    daily_budgets: dict[str, float] = {}
    for cid, metrics in current_metrics.items():
        spend = metrics.get("spend", 0.0)
        if spend < MIN_SPEND_FOR_LOOP:
            continue
        # 日均花费作为当前预算估计
        daily = spend / max(BUDGET_ESTIMATE_DAYS, 1)
        daily_budgets[cid] = round(daily, 2)
    return daily_budgets


def filter_actionable_signals(
    feedback: FeedbackResult,
    current_metrics: dict[str, dict[str, float]],
) -> list[Any]:
    """从 FeedbackResult 中筛选可进入 Growth Loop 的信号。

    过滤条件:
      1. 信号已触发 (在 feedback.triggered 中)
      2. 对应 creative 有足够的 spend (>= MIN_SPEND_FOR_LOOP)
      3. 信号类型非 DATA_COLLECTION (数据收集型不进入 Loop)
    """
    actionable: list[Any] = []
    seen_ids: set[str] = set()

    for signal in feedback.triggered:
        creative_id = getattr(signal, "creative_id", "")
        signal_id = getattr(signal, "signal_id", "")
        if signal_id in seen_ids:
            continue

        # 过滤 DATA_COLLECTION 信号
        st = getattr(signal, "signal_type", None)
        st_value = st.value if hasattr(st, "value") else str(st)
        if st_value == "data_collection":
            continue

        # 检查 spend 是否足够
        metrics = current_metrics.get(creative_id, {})
        if metrics.get("spend", 0.0) < MIN_SPEND_FOR_LOOP:
            continue

        seen_ids.add(signal_id)
        actionable.append(signal)

    return actionable


# ──────────────────────────────────────────────
# 接线 3: 指标适配层 (MetricsAdapter)
# ──────────────────────────────────────────────


def enrich_metrics_with_product_data(
    ads_metrics: dict[str, dict[str, float]],
    td_project_id: int = 102,
    td_lookback_days: int = 30,
    player_app_id: str = "",
    player_start: str = "",
    player_end: str = "",
) -> tuple[dict[str, dict[str, float]], EnrichmentReport | None]:
    """用产品侧数据 (七域快照 + PlayerProfile) 富集广告侧指标。

    接线 3 的核心: 以广告平台数据为主源, 用产品侧真实收入 (IAP+IAA) 替换
    广告侧反推的 revenue, 并附加产品上下文 (留存/ARPU/LTV) 到 _context 字段。

    所有产品侧数据源都是可选的 — 任一源缺失时降级为广告侧原值,
    不影响 Growth Loop 主流程。

    Args:
        ads_metrics: aggregate_by_creative 输出的广告侧指标
        td_project_id: ThinkingData 项目 ID (七域快照)
        td_lookback_days: 七域快照回溯天数
        player_app_id: PlayerProfile 应用 ID
        player_start/end: PlayerProfile 时间范围 (ISO 字符串)

    Returns:
        (adapted_metrics, report)
        - adapted_metrics: 富集后的指标, 可直接传入 Orchestrator
        - report: EnrichmentReport 或 None (无任何产品侧数据时)
    """
    if not ads_metrics:
        return ads_metrics, None

    seven_domain_snapshots: dict[str, Any] | None = None
    player_profiles: list[Any] | None = None

    # ── 源 1: 七域快照 (parallel_analyze) ──
    try:
        from market_ops.creative_vision_runtime.reality.thinkingdata_reality import (
            ThinkingDataReality,
        )
        from market_ops.creative_vision_runtime.reality.analyzers import (
            parallel_analyze,
        )

        td = ThinkingDataReality()  # client=None 时各 analyzer 降级为 mock
        seven_domain_snapshots = parallel_analyze(
            td,
            project_id=td_project_id,
            lookback_days=td_lookback_days,
        )
        print(
            f"  七域快照: {len(seven_domain_snapshots)} 个域 "
            f"(project_id={td_project_id}, lookback={td_lookback_days}d)"
        )
    except Exception as exc:
        print(f"  ⚠ 七域快照拉取失败: {exc}")
        print(f"  ⚠ 将仅使用广告侧指标 (无产品上下文)")

    # ── 源 2: PlayerProfile (IAA 收入归因) ──
    if player_app_id:
        try:
            from operation.player_monetization.events.collector import EventCollector

            collector = EventCollector()
            player_profiles = collector.collect(
                app_id=player_app_id,
                start=player_start,
                end=player_end,
            )
            print(
                f"  PlayerProfile: {len(player_profiles)} 个玩家 "
                f"(app_id={player_app_id})"
            )
        except Exception as exc:
            print(f"  ⚠ PlayerProfile 拉取失败: {exc}")

    # 无任何产品侧数据 → 直接返回
    if not seven_domain_snapshots and not player_profiles:
        print("  ⚠ 无产品侧数据, 跳过指标适配")
        return ads_metrics, None

    # ── 调用 MetricsAdapter 适配 ──
    adapter = MetricsAdapter()
    adapted, report = adapter.adapt(
        ads_metrics=ads_metrics,
        seven_domain_snapshots=seven_domain_snapshots,
        player_profiles=player_profiles,
        creative_attribution=None,  # TODO: 从归因系统获取 user_id → creative_id
    )

    print(
        f"  MetricsAdapter: 富集完成 "
        f"(revenue_enriched={report.revenue_enriched}/"
        f"{report.total_creatives}, "
        f"context_added={report.context_added})"
    )
    if report.revenue_discrepancies:
        print(
            f"  ⚠ 收入偏差 > 30%: {len(report.revenue_discrepancies)} 个 creative "
            f"(广告侧 vs 产品侧)"
        )

    return adapted, report


# ──────────────────────────────────────────────
# 报告输出
# ──────────────────────────────────────────────


def print_cycle_report(
    result: CycleResult,
    feedback: FeedbackResult,
    store: ExperienceStore,
    live: bool,
    enrichment_report: EnrichmentReport | None = None,
) -> None:
    """打印 Growth Loop 单轮执行报告。"""
    print("\n" + "=" * 70)
    mode = "LIVE" if live else "DRY-RUN"
    print(f"  Growth Loop V2 — Cycle {result.cycle_number} Report [{mode}]")
    print("=" * 70)

    # ── 指标适配摘要 (接线 3) ──
    if enrichment_report is not None:
        print(f"\n🔌 接线 3 — 指标适配 (MetricsAdapter):")
        print(f"   总 creative: {enrichment_report.total_creatives}")
        print(f"   revenue 富集: {enrichment_report.revenue_enriched}")
        print(f"   installs 校验: {enrichment_report.installs_enriched}")
        print(f"   上下文附加: {enrichment_report.context_added}")
        if enrichment_report.revenue_discrepancies:
            print(
                f"   ⚠ 收入偏差 > 30%: "
                f"{len(enrichment_report.revenue_discrepancies)} 个 creative"
            )

    # ── Phase A: 到期评估 ──
    print(f"\n📋 Phase A — 到期评估:")
    print(f"   已评估: {result.evaluated_count}")
    print(f"   已过期: {result.expired_count}")
    if result.outcomes:
        for oc in result.outcomes[:5]:
            print(
                f"   • action={oc.action_id[:16]}... "
                f"outcome={oc.outcome.value} "
                f"improvement={oc.improvement:+.4f}"
            )
        if len(result.outcomes) > 5:
            print(f"   ... 共 {len(result.outcomes)} 条")

    # ── Phase B: 新动作 ──
    print(f"\n🔧 Phase B — Growth Loop 执行:")
    print(f"   输入信号: {len(result.signal_ids)}")
    print(f"   诊断结果: {len(result.diagnoses)}")

    # 诊断详情
    if result.diagnoses:
        for d in result.diagnoses[:5]:
            print(
                f"   • [{d.creative_id[:16]}] "
                f"root_cause={d.root_cause.value} "
                f"confidence={d.confidence:.2f}"
            )

    print(f"   生成假设: {len(result.hypotheses)}")
    if result.hypotheses:
        for h in result.hypotheses[:5]:
            print(
                f"   • [{h.creative_id[:16] if hasattr(h, 'creative_id') else 'N/A'}] "
                f"confidence={h.confidence:.2f} "
                f"basis={h.basis} "
                f"actionable={h.is_actionable}"
            )

    print(f"   选择策略: {len(result.strategies)}")
    if result.strategies:
        for s in result.strategies[:5]:
            print(
                f"   • [{s.target_creative_id[:16]}] "
                f"type={s.strategy_type.value} "
                f"intensity={s.intensity:.2f}"
            )

    print(f"   规划动作: {len(result.actions)}")
    print(f"   跳过 (NOOP): {result.actions_skipped}")
    print(f"   执行结果: {len(result.execution_results)}")

    if result.execution_results:
        for r in result.execution_results[:5]:
            print(
                f"   • action={r.action_id[:16]}... "
                f"status={r.status.value} "
                f"success={r.success}"
            )

    print(f"   创建待评估: {result.pending_created}")

    # ── Feedback 摘要 ──
    print(f"\n⚡ FeedbackController 摘要:")
    print(f"   信号总数: {len(feedback.signals)}")
    print(f"   触发信号: {len(feedback.triggered)}")
    print(f"   行动建议: {len(feedback.actions)}")
    print(f"   摘要: {feedback.summary or '(无)'}")

    # ── 经验存储 ──
    stats = store.get_stats()
    print(f"\n📦 ExperienceStore:")
    print(f"   总记录: {stats.total_records}")
    print(f"   成功率: {stats.success_rate:.1%}")
    print(f"   平均改善: {stats.mean_improvement:+.4f}")

    # ── 耗时 ──
    print(f"\n⏱ 耗时: {result.duration_ms} ms")

    print("\n" + "=" * 70)
    print("  ✅ Growth Loop V2 闭环完成")
    print("     Meta Ads → Prediction → Feedback → Diagnose → Strategy → Execute")
    print("=" * 70 + "\n")


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Growth Loop V2 入口: Meta Ads → FeedbackController → "
            "GrowthLoopOrchestrator 全链路闭环"
        )
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="当前周期天数 (默认 7, 会自动取前一个同等长度周期做对比)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="真实执行模式 (调用真实 API + 执行平台动作). 默认 dry-run",
    )
    parser.add_argument(
        "--data-dir",
        default="data/growth_loop",
        help="Growth Loop 持久化数据目录 (默认 data/growth_loop)",
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=168,
        help="观察窗口小时数 (默认 168h = 7 天, 到期后评估动作效果)",
    )
    parser.add_argument(
        "--product-id",
        default="",
        help="产品 ID (写入 ExperienceRecord.context.product_id)",
    )
    parser.add_argument(
        "--enrich-metrics",
        action="store_true",
        help="启用接线 3 指标适配: 用七域快照+PlayerProfile 富集广告侧指标",
    )
    parser.add_argument(
        "--td-project-id",
        type=int,
        default=102,
        help="ThinkingData 项目 ID (七域快照, 默认 102)",
    )
    parser.add_argument(
        "--td-lookback-days",
        type=int,
        default=30,
        help="七域快照回溯天数 (默认 30)",
    )
    parser.add_argument(
        "--player-app-id",
        default="",
        help="PlayerProfile 应用 ID (启用 IAA 收入归因)",
    )
    args = parser.parse_args()

    load_dotenv()

    access_token = os.getenv("META_ACCESS_TOKEN", "")
    ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
    api_version = os.getenv("META_API_VERSION", "v22.0")
    game_name = os.getenv("DEFAULT_GAME_NAME", "P04")

    dry_run = not args.live

    # ── Step 1: 拉取 Meta Ads 数据 ──
    print("\n步骤 1/7: 拉取 Meta Ads 数据...")
    if not access_token or not ad_account_id:
        print("❌ 缺少 META_ACCESS_TOKEN 或 META_AD_ACCOUNT_ID, 请检查 .env 文件")
        print("   (设置 --live 需要真实凭据; dry-run 模式可使用沙箱凭据)")
        if not dry_run:
            return 1
        # dry-run 模式下允许继续 (Orchestrator 会用 MockPlatformAdapter)

    current_rows: list[AdsPerformanceRow] = []
    previous_rows: list[AdsPerformanceRow] = []

    if access_token and ad_account_id:
        try:
            current_rows, previous_rows = load_meta_ads_data(
                access_token, ad_account_id, api_version, game_name, args.days
            )
        except Exception as exc:
            print(f"  ⚠ Meta Ads 数据拉取失败: {exc}")
            print(f"  ⚠ 将使用空数据集 (Growth Loop 将只执行 Phase A)")
    else:
        print("  ⚠ 无凭据, 跳过 Meta Ads 数据拉取 (将使用空数据集)")

    if not current_rows:
        print("  ⚠ 当前周期无数据, Growth Loop 将只执行 Phase A (到期评估)")

    # ── Step 2: 聚合指标 ──
    print("\n步骤 2/7: 按 creative 聚合指标...")
    current_metrics = aggregate_by_creative(current_rows)
    previous_metrics = aggregate_by_creative(previous_rows)
    print(f"  当前周期 creative 数: {len(current_metrics)}")
    print(f"  上一周期 creative 数: {len(previous_metrics)}")

    # 构建映射
    creative_to_adset_map = build_creative_to_adset_map(current_rows)
    current_budgets = estimate_current_budgets(current_metrics, args.days)
    print(f"  creative→adset 映射: {len(creative_to_adset_map)} 条")
    print(f"  当前预算估计: {len(current_budgets)} 个 adset")

    # ── Step 3: 指标适配层 (接线 3) ──
    print("\n步骤 3/7: 指标适配 (接线 3: MetricsAdapter)...")
    enrichment_report: EnrichmentReport | None = None
    if args.enrich_metrics and current_metrics:
        player_start = (date.today() - timedelta(days=args.days)).isoformat()
        player_end = date.today().isoformat()
        current_metrics, enrichment_report = enrich_metrics_with_product_data(
            ads_metrics=current_metrics,
            td_project_id=args.td_project_id,
            td_lookback_days=args.td_lookback_days,
            player_app_id=args.player_app_id,
            player_start=player_start,
            player_end=player_end,
        )
    else:
        print("  (未启用 --enrich-metrics, 使用纯广告侧指标)")

    # ── Step 4: 生成预测 + FeedbackController 评估 ──
    print("\n步骤 4/7: 生成预测并送入 FeedbackController...")

    # 加载历史经验增强预测
    store = ExperienceStore()
    enricher = MemoryEnricher(store)
    mem = enricher.get_summary()
    print(f"  历史经验: {mem['total_records']} 条, 追踪创意: {mem['tracked_creatives']} 个")

    predictions = generate_predictions(
        current_metrics, previous_metrics, enricher=enricher
    )
    print(f"  生成预测: {len(predictions)} 条")

    controller = FeedbackController()
    feedback = controller.evaluate(predictions)
    print(f"  FeedbackController: {len(feedback.signals)} 信号, {len(feedback.triggered)} 触发")

    # 筛选可进入 Growth Loop 的信号
    signals = filter_actionable_signals(feedback, current_metrics)
    print(f"  进入 Growth Loop 的信号: {len(signals)} 条")

    # ── Step 5: RealityGate 审计 (接线 1) ──
    print("\n步骤 5/7: RealityGate 数据可信度审计...")
    reality_scores: dict[str, Any] = {}
    game_id_resolver: Any = None

    if current_metrics:
        try:
            reality_scores, creative_to_game = run_reality_audit(
                game_name=game_name,
                current_metrics=current_metrics,
                data_dir="data",
            )
            game_id_resolver = make_game_id_resolver(creative_to_game)
            print(f"  RealityGate: {len(reality_scores)} 个游戏可信分已注入")
            # 统计门控等级
            blocked = sum(
                1 for s in reality_scores.values()
                if s.decision_level == "BLOCKED"
            )
            approve = sum(
                1 for s in reality_scores.values()
                if s.decision_level == "APPROVE"
            )
            execute = sum(
                1 for s in reality_scores.values()
                if s.decision_level == "EXECUTE"
            )
            print(f"  门控分布: BLOCKED={blocked} APPROVE={approve} EXECUTE={execute}")
        except Exception as exc:
            print(f"  ⚠ RealityGate 审计失败: {exc}")
            print(f"  ⚠ 将跳过 RealityGate 门控 (无保护执行)")
    else:
        print("  ⚠ 无 current_metrics, 跳过 RealityGate 审计")

    # ── Step 6: 初始化 Orchestrator 并执行 run_cycle ──
    print("\n步骤 6/7: 初始化 GrowthLoopOrchestrator 并执行 run_cycle...")

    # 构建 PlatformAdapter
    adapter: Any = None
    if args.live and access_token and ad_account_id:
        try:
            from market_ops.execution_runtime.adapters.facebook import FacebookClient
            client = FacebookClient()
            adapter = MetaAdsPlatformAdapter(client)
            print(f"  PlatformAdapter: MetaAdsPlatformAdapter (live)")
        except Exception as exc:
            print(f"  ⚠ 创建 MetaAdsPlatformAdapter 失败: {exc}, 回退到 Mock")
    # adapter=None 时 ActionExecutor 内部会用 MockPlatformAdapter

    orchestrator = GrowthLoopOrchestrator(
        data_dir=args.data_dir,
        adapter=adapter,
        store=store,
        observation_window_hours=args.window_hours,
        dry_run=dry_run,
        reality_scores=reality_scores if reality_scores else None,
        game_id_resolver=game_id_resolver,
    )
    print(f"  Orchestrator: loop_id={orchestrator.state.loop_id}")
    print(f"  待评估队列: {orchestrator.pending_count} 条")
    print(f"  RealityGate: {'已注入' if reality_scores else '未启用'}")
    print(f"  模式: {'DRY-RUN' if dry_run else 'LIVE'}")

    # 构造 post_metrics_provider (用于 Phase A 评估到期动作)
    # 简单实现: 从 current_metrics 中取对应 creative 的指标
    def post_metrics_provider(pending: Any) -> dict[str, float]:
        cid = getattr(pending, "creative_id", "")
        return current_metrics.get(cid, {})

    result = orchestrator.run_cycle(
        signals=signals if signals else None,
        current_metrics=current_metrics,
        previous_metrics=previous_metrics,
        creative_to_adset_map=creative_to_adset_map,
        current_budgets=current_budgets,
        post_metrics_provider=post_metrics_provider,
    )

    # ── Step 7: 打印报告 ──
    print("\n步骤 7/7: 输出报告...")
    print_cycle_report(
        result,
        feedback,
        orchestrator.store,
        live=args.live,
        enrichment_report=enrichment_report,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
