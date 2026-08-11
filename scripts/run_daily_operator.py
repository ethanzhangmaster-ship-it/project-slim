"""P3.1 — Daily Operator 唯一命令行入口。

一条命令跑完整每日增长经营流程（13 阶段）：
  Reality → Audit → Opportunity → Simulation → Decision
  → Approval(P2.3) → Execution(P2.4) → Monitor(P2.5) → Recovery(P2.6)
  → Memory → StrategyLoop(P3.3) → CEOReport(P3.2) → Report

跑法（launchforge/ 根目录）：
  python scripts/run_daily_operator.py                 # demo：确定性 SIM 舰队（离线）
  python scripts/run_daily_operator.py --date 2026-07-30
  python scripts/run_daily_operator.py --force         # 强制重跑（越过幂等门）
  python scripts/run_daily_operator.py --prod          # 生产：GameRegistry + 四真实源

退出码：COMPLETED/SKIPPED=0，PARTIAL=1，FAILED=2。
产物：outputs/operator/<date>/{daily_report.md, daily_report.json, actions.json,
      strategy_insights.json, strategy_proposals.json, strategy_states.json}
      + data/operator*/runs.jsonl。

安全纪律：恒 DRY_RUN；real_api_called 出现 True 即打印告警（demo 下属于异常）。
P3.3 Strategy Loop 只产出策略洞察/建议（进 Simulation Queue），绝不自动执行。
"""
import argparse
import sys
from datetime import date as _date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ceo_intelligence.daily_operator.memory import JsonlOperatorMemory
from src.operator import RunStatus, build_growth_operator
from src.operator.state import OperatorRunStore


# --------------------------------------------------------------------------- #
# demo 舰队（确定性 SIM，复用 demo_e17_9 的构造模式）
# --------------------------------------------------------------------------- #
def build_demo_company(root: Path, n: int = 12):
    from src.growth_reality.feature_store import GrowthFeatureStore
    from src.growth_reality.models import (
        AcquisitionFact,
        AsoFact,
        CreativeFact,
        GrowthRealitySnapshot,
        ProductFact,
        RevenueFact,
    )
    from src.growth_reality.snapshot import build_company_snapshot

    store = GrowthFeatureStore(root=str(root / "gr"))
    gids = [f"demo_game_{i:03d}" for i in range(n)]
    for i, gid in enumerate(gids):
        d0 = GrowthRealitySnapshot(
            gid, "d0",
            revenue=RevenueFact(daily_revenue=1000.0, payer_count=10),
            acquisition=AcquisitionFact(spend=100.0, installs=1000, cpi=0.1, roas=2.0),
            creative=CreativeFact(ctr=0.05, fatigue_score=0.30, creative_score=0.60),
            aso=AsoFact(ranking=10, store_cvr=0.10, rating=3.5, review_velocity=4.0),
            product=ProductFact(dau=3000 + i, retention=0.3, conversion=0.02),
            confidence=0.6 + (i % 3) * 0.1,
            sources=["sim"],
        )
        # 施加确定性变化：收入跌 / ROAS 跌 / 素材疲劳 / 商店 CVR 跌 轮转
        rev1, roas1, spend1, ctr1, fat1, cvr1 = 1000.0, 2.0, 100.0, 0.05, 0.30, 0.10
        p = i % 4
        if p == 0:
            rev1 = 1000.0 * (1 - (0.20 + (i % 5) * 0.04))
        elif p == 1:
            roas1 = 2.0 * (1 - (0.15 + (i % 5) * 0.04))
            spend1 = 100.0 * (1 + (0.20 + (i % 5) * 0.04))
        elif p == 2:
            ctr1 = 0.05 * (1 - (0.20 + (i % 5) * 0.04))
            fat1 = min(0.95, 0.70 + (i % 5) * 0.05)
        else:
            cvr1 = 0.10 * (1 - (0.15 + (i % 5) * 0.04))
        d1 = GrowthRealitySnapshot(
            gid, "d1",
            revenue=RevenueFact(daily_revenue=rev1, payer_count=10),
            acquisition=AcquisitionFact(spend=spend1, installs=1000, cpi=0.1, roas=roas1),
            creative=CreativeFact(ctr=ctr1, fatigue_score=fat1, creative_score=0.60),
            aso=AsoFact(ranking=10, store_cvr=cvr1, rating=3.5, review_velocity=4.0),
            product=ProductFact(dau=3000 + i, retention=0.3, conversion=0.02),
            confidence=0.6 + (i % 3) * 0.1,
            sources=["sim"],
        )
        store.append(d0)
        store.append(d1)
    latest = [store.latest(g) for g in gids]
    return build_company_snapshot(latest, _date.today().isoformat()), store, gids


def build_demo_scheduler(business_date: str):
    demo_root = Path("data") / "operator_demo"
    company, feature_store, gids = build_demo_company(demo_root)
    return build_growth_operator(
        run_store=OperatorRunStore(str(demo_root / "runs.jsonl")),
        company=company,
        game_ids=gids,
        feature_store=feature_store,
        operator_memory=JsonlOperatorMemory(
            str(demo_root / "operator_memory.jsonl")
        ),
        approval_queue_path=str(demo_root / "approval_queue.jsonl"),
        audit_dir=str(demo_root / "audit"),
        report_dir=str(Path("reports") / "daily"),
    )


def build_prod_scheduler(business_date: str):
    """生产：GameRegistry 全舰队 + 四真实源（顺序即覆盖优先级，不可乱动）。"""
    from src.growth_reality.agent import GrowthRealityHub
    from src.growth_reality.feature_store import GrowthFeatureStore
    from src.growth_reality.production_sources.adjust_source import (
        AdjustRealitySource,
    )
    from src.growth_reality.production_sources.max_source import MaxRealitySource
    from src.growth_reality.production_sources.meta_source import MetaRealitySource
    from src.growth_reality.registry import GameRegistry, RegistryRealitySource

    registry = GameRegistry()
    sources = [
        RegistryRealitySource(registry=registry),
        MaxRealitySource(mode="production", registry=registry,
                         as_of=business_date),
        MetaRealitySource(mode="production", registry=registry,
                          as_of=business_date),
        AdjustRealitySource(mode="production", registry=registry,
                            as_of=business_date),
    ]
    hub = GrowthRealityHub(
        sources=sources, store=GrowthFeatureStore("data/growth_reality")
    )
    return build_growth_operator(
        hub=hub,
        game_ids=registry.all_game_ids(),
    )


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="P3.1 Daily Operator")
    parser.add_argument("--date", default=_date.today().isoformat())
    parser.add_argument("--force", action="store_true", help="越过幂等门重跑")
    parser.add_argument("--prod", action="store_true",
                        help="生产模式（GameRegistry + 四真实源，仍 DRY_RUN）")
    args = parser.parse_args()

    scheduler = (
        build_prod_scheduler(args.date) if args.prod
        else build_demo_scheduler(args.date)
    )
    result = scheduler.run_daily_cycle(args.date, force=args.force)

    print("=" * 72)
    print(f"P3.1 Daily Operator ｜ {args.date} ｜ run_id={result.run_id} ｜ "
          f"状态：{result.status.value.upper()}")
    print("=" * 72)
    for st in result.stages:
        mark = {"ok": "✅", "skipped": "⏭️", "failed": "❌"}.get(st.status, "?")
        print(f"  {mark} {st.stage:<16} {st.detail}")
    if result.status == RunStatus.SKIPPED:
        print(f"  ⏭️ 幂等拦截：{result.summary.get('reason', '')}"
              f"（上次状态 {result.summary.get('previous_status', '')}；"
              f"--force 可重跑）")
    if result.errors:
        print("  错误：")
        for e in result.errors:
            print(f"    - {e}")
    print(f"  决策：{result.decisions}")
    print(f"  执行：{result.executions}")
    print(f"  real_api_called：{result.real_api_called}"
          + ("  ⚠️ 出现真实调用！" if result.real_api_called else "（DRY_RUN 纪律）"))
    if result.report_id:
        print(f"  决策单：{result.report_id}")
    # CEO 三文件（决策单 JSON / 行动队列）取自 ceo_report 阶段 payload
    ceo_payload = {}
    for st in result.stages:
        if st.stage == "ceo_report":
            ceo_payload = st.payload
            break
    ceo_json = ceo_payload.get("ceo_report_json", "")
    actions = ceo_payload.get("actions_path", "")
    if ceo_json:
        print(f"  决策单 JSON：{ceo_json}")
    if actions:
        print(f"  行动队列：{actions}")
    # P3.3 策略反馈产物（洞察/建议/状态，均不执行）
    strategy_payload = {}
    for st in result.stages:
        if st.stage == "strategy_loop":
            strategy_payload = st.payload
            break
    si = strategy_payload.get("strategy_insights", "")
    sp = strategy_payload.get("strategy_proposals", "")
    ss = strategy_payload.get("strategy_states", "")
    if si:
        print(f"  策略洞察：{si}")
    if sp:
        print(f"  策略建议：{sp}")
    if ss:
        print(f"  策略状态：{ss}")

    if result.status in (RunStatus.COMPLETED, RunStatus.SKIPPED):
        return 0
    if result.status == RunStatus.PARTIAL:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
