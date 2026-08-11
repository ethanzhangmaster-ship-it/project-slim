"""E17.8 — Growth Simulation Engine 主入口（Agent）。

补全三级执行门中缺席的 Simulation 门：
Recommendation(E17.2) → **Simulation(E17.8)** → Approval(E17.3 队列) → Execution(E17.6)

- build(dec_report, memory_graph?) → PortfolioSimulationReport
  只模拟可执行出口（EXECUTE / APPROVE）；OBSERVE / REJECT 本来就不落地，跳过。
- run_pipeline() 串 E17.1 → E17.4 → **E17.8 闸门** → E17.6：
  被闸门 BLOCK 的决策，其作战计划不进执行层（按 plan.decision_id == decision.audit_id 过滤）。

复用不重写：E17.4 strategy run_pipeline（上游）、E17.6 GrowthExecutionRouterAgent（下游）、
E17.3 OpportunitySimulator 基线 + E17.7 图谱记忆先验（priors）。
SIM 纪律：summary.real_api_called 恒为 False（本层纯计算）。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .engine import DeterministicSimulator
from .models import (
    CounterfactualComparison,
    DecisionSimulation,
    PortfolioSimulationReport,
    PreFlightStatus,
    SimulationScenario,
)
from .priors import get_prior, opportunity_type_of
from .store import JsonlSimulationStore

# 可执行出口才需要执行前模拟
_ACTIONABLE = {"execute", "approve"}


class GrowthSimulationAgent:
    """对外 API：build(dec_report, memory_graph?) → PortfolioSimulationReport。"""

    def __init__(
        self,
        simulator: Optional[DeterministicSimulator] = None,
        store: Optional[JsonlSimulationStore] = None,
    ):
        self.simulator = simulator or DeterministicSimulator()
        self.store = store

    def build(
        self,
        dec_report,
        memory_graph=None,
        scenarios: Optional[List[SimulationScenario]] = None,
        created_at: str = "",
    ) -> PortfolioSimulationReport:
        scen_list = scenarios if scenarios is not None else self.simulator.scenarios
        sims: List[DecisionSimulation] = []
        skipped = 0
        for decision in dec_report.decisions:
            dtype = (
                decision.decision_type.value
                if hasattr(decision.decision_type, "value")
                else str(decision.decision_type)
            )
            if dtype not in _ACTIONABLE:
                skipped += 1
                continue
            prior = get_prior(
                opportunity_type_of(decision.opportunity_id), memory_graph
            )
            sims.append(
                self.simulator.simulate_decision(decision, prior, scen_list)
            )

        portfolio = self.simulator.simulate_portfolio(sims, scen_list)
        comparisons = self._comparisons(sims, scen_list)

        report = PortfolioSimulationReport(
            created_at=created_at,
            total_decisions=len(sims),
            simulations=sims,
            portfolio=portfolio,
            comparisons=comparisons,
            summary={
                "pass": sum(
                    1 for s in sims if s.flag.status == PreFlightStatus.PASS
                ),
                "review": sum(
                    1 for s in sims if s.flag.status == PreFlightStatus.REVIEW
                ),
                "block": sum(
                    1 for s in sims if s.flag.status == PreFlightStatus.BLOCK
                ),
                "skipped": skipped,
                "scenarios": [sc.id for sc in scen_list],
                "memory_prior_used": any(
                    s.prior.source == "static+memory" for s in sims
                ),
                "real_api_called": False,
            },
        )
        if self.store is not None:
            self.store.record(report)
        return report

    @staticmethod
    def _comparisons(
        sims: List[DecisionSimulation], scenarios: List[SimulationScenario]
    ) -> List[CounterfactualComparison]:
        """每个决策：非基线情景 vs 基线的反事实对比。"""
        ids = [sc.id for sc in scenarios]
        if "baseline" not in ids:
            return []
        out: List[CounterfactualComparison] = []
        for sim in sims:
            for sid in ids:
                if sid == "baseline":
                    continue
                out.append(
                    DeterministicSimulator.compare_counterfactual(
                        sim, sid, "baseline"
                    )
                )
        return out


# --------------------------------------------------------------------------- #
# 端到端：Reality → Opportunity → Decision → Strategy → [Simulation 闸门] → Execution
# --------------------------------------------------------------------------- #
def run_pipeline(
    company,
    *,
    store=None,
    opportunity_memory=None,
    decision_memory=None,
    strategy_memory=None,
    memory_graph=None,
    scenarios: Optional[List[SimulationScenario]] = None,
    simulator: Optional[DeterministicSimulator] = None,
    simulation_store: Optional[JsonlSimulationStore] = None,
    execute: bool = True,
    execution_router=None,
    execution_memory=None,
    approval_outbox=None,
    segment: str = "global",
    top_n: int = 10,
    approval_queue_path: str = "data/ceo/approval_queue.jsonl",
    audit_dir: str = "data/ceo/audit",
    created_at: str = "",
) -> Tuple[object, object, PortfolioSimulationReport, List]:
    """E17.1 → E17.4 → E17.8 闸门 → E17.6（默认全 SIM）。

    返回 (dec_report, portfolio, sim_report, exec_reports)。
    BLOCK 决策的作战计划被挡下，不进入 E17.6。
    """
    from src.ceo_intelligence.strategy_planner.agent import (
        run_pipeline as _strategy_pipeline,
    )

    dec_report, portfolio = _strategy_pipeline(
        company,
        store=store,
        opportunity_memory=opportunity_memory,
        decision_memory=decision_memory,
        strategy_memory=strategy_memory,
        segment=segment,
        top_n=top_n,
        approval_queue_path=approval_queue_path,
        audit_dir=audit_dir,
        created_at=created_at,
    )

    agent = GrowthSimulationAgent(simulator=simulator, store=simulation_store)
    sim_report = agent.build(
        dec_report,
        memory_graph=memory_graph,
        scenarios=scenarios,
        created_at=created_at,
    )

    exec_reports: List = []
    if execute:
        from src.ceo_intelligence.execution_router.agent import (
            GrowthExecutionRouterAgent,
        )
        from src.ceo_intelligence.execution_router.router import ExecutionRouter

        blocked = set(sim_report.blocked_decision_ids())
        allowed_plans = [
            p for p in portfolio.plans if p.decision_id not in blocked
        ]
        if execution_router is None:
            from audit.trail import AuditTrail

            execution_router = ExecutionRouter(
                audit=AuditTrail(audit_dir=audit_dir),
                memory=execution_memory,
                outbox=approval_outbox,
            )
        exec_agent = GrowthExecutionRouterAgent(router=execution_router)
        exec_reports = [exec_agent.execute_plan(p) for p in allowed_plans]

    return dec_report, portfolio, sim_report, exec_reports


__all__ = ["GrowthSimulationAgent", "run_pipeline"]
