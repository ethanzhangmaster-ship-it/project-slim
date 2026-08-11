"""E17.9 — Daily Pipeline（一键 CEO Daily Run）。

串联：Reality(E17.1) → Opportunity(E17.2) → Decision(E17.3) → Strategy(E17.4)
      → Simulation 闸门(E17.8) → Execution(E17.6)

与 E17.8 run_pipeline 的差别（运营安全铁律，比闸门更严格）：
- E17.8 只挡 BLOCK；E17.9 的自动执行只放行「EXECUTE 决策 + 模拟 PASS」。
- APPROVE 决策、模拟 REVIEW 的 EXECUTE 决策 → 一律进「等待审批」，不自动落地。
- BLOCK → 阻断，不进执行层。

SIM 纪律：默认全 SIM，real_api_called 恒 False。复用不重写：
上游全链路直接调 E17.8 simulation_engine.run_pipeline(execute=False)。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.ceo_intelligence.simulation_engine.agent import (
    run_pipeline as _sim_pipeline,
)

from .models import ActionKind, DailyActionItem


class DailyGrowthPipeline:
    """run(company) → (dec_report, portfolio, sim_report, exec_reports, actions)。"""

    def __init__(
        self,
        *,
        store=None,
        opportunity_memory=None,
        decision_memory=None,
        strategy_memory=None,
        memory_graph=None,
        execution_router=None,
        execution_memory=None,
        approval_outbox=None,
        segment: str = "global",
        top_n: int = 10,
        approval_queue_path: str = "data/ceo/approval_queue.jsonl",
        audit_dir: str = "data/ceo/audit",
    ):
        self.store = store
        self.opportunity_memory = opportunity_memory
        self.decision_memory = decision_memory
        self.strategy_memory = strategy_memory
        self.memory_graph = memory_graph
        self.execution_router = execution_router
        self.execution_memory = execution_memory
        self.approval_outbox = approval_outbox
        self.segment = segment
        self.top_n = top_n
        self.approval_queue_path = approval_queue_path
        self.audit_dir = audit_dir

    # ------------------------------------------------------------------ #
    def run(
        self, company, created_at: str = ""
    ) -> Tuple[Any, Any, Any, List[Any], List[DailyActionItem]]:
        # 上游全链路（E17.1→E17.4→E17.8 闸门），先不执行
        dec_report, portfolio, sim_report, _ = _sim_pipeline(
            company,
            store=self.store,
            opportunity_memory=self.opportunity_memory,
            decision_memory=self.decision_memory,
            strategy_memory=self.strategy_memory,
            memory_graph=self.memory_graph,
            execute=False,
            segment=self.segment,
            top_n=self.top_n,
            approval_queue_path=self.approval_queue_path,
            audit_dir=self.audit_dir,
            created_at=created_at,
        )

        gates = self._gates_by_audit_id(sim_report)
        blocked = set(sim_report.blocked_decision_ids())

        # 安全铁律：只有 EXECUTE + 模拟 PASS 的计划才自动执行
        auto_ids = {
            d.audit_id
            for d in dec_report.decisions
            if self._dtype(d) == "execute" and gates.get(d.audit_id) == "pass"
        }
        allowed_plans = [p for p in portfolio.plans if p.decision_id in auto_ids]
        exec_reports = self._execute(allowed_plans)
        exec_by_decision = {r.decision_id: r for r in exec_reports}

        actions = self._build_actions(
            dec_report, gates, blocked, auto_ids, exec_by_decision
        )
        return dec_report, portfolio, sim_report, exec_reports, actions

    # ------------------------------------------------------------------ #
    def _execute(self, plans: List[Any]) -> List[Any]:
        if not plans:
            return []
        from src.ceo_intelligence.execution_router.agent import (
            GrowthExecutionRouterAgent,
        )
        from src.ceo_intelligence.execution_router.router import ExecutionRouter

        router = self.execution_router
        if router is None:
            from audit.trail import AuditTrail

            router = ExecutionRouter(
                audit=AuditTrail(audit_dir=self.audit_dir),
                memory=self.execution_memory,
                outbox=self.approval_outbox,
            )
        agent = GrowthExecutionRouterAgent(router=router)
        return [agent.execute_plan(p) for p in plans]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _dtype(decision) -> str:
        t = decision.decision_type
        return t.value if hasattr(t, "value") else str(t)

    @staticmethod
    def _gates_by_audit_id(sim_report) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for s in sim_report.simulations:
            if s.decision_audit_id:
                status = s.flag.status
                out[s.decision_audit_id] = (
                    status.value if hasattr(status, "value") else str(status)
                )
        return out

    def _build_actions(
        self,
        dec_report,
        gates: Dict[str, str],
        blocked: set,
        auto_ids: set,
        exec_by_decision: Dict[str, Any],
    ) -> List[DailyActionItem]:
        actions: List[DailyActionItem] = []
        for d in dec_report.decisions:
            dtype = self._dtype(d)
            if dtype in ("observe", "reject"):
                continue  # 本来不落地，不进今日行动
            opp_type = (
                d.opportunity_id.rsplit(":", 1)[-1] if d.opportunity_id else ""
            )
            if d.audit_id in blocked:
                sim_reason = self._gate_reason(d.audit_id, dec_report, gates)
                actions.append(
                    DailyActionItem(
                        kind=ActionKind.BLOCK,
                        game_id=d.game_id,
                        action=d.action,
                        detail=sim_reason or "模拟闸门阻断（负期望）",
                        decision_audit_id=d.audit_id,
                        opportunity_type=opp_type,
                    )
                )
            elif d.audit_id in auto_ids:
                rep = exec_by_decision.get(d.audit_id)
                detail = (
                    f"已自动下发执行层（执行状态：{rep.status}）" if rep is not None
                    else "已自动下发执行层"
                )
                actions.append(
                    DailyActionItem(
                        kind=ActionKind.AUTO,
                        game_id=d.game_id,
                        action=d.action,
                        detail=detail,
                        decision_audit_id=d.audit_id,
                        opportunity_type=opp_type,
                    )
                )
            else:
                gate = gates.get(d.audit_id, "")
                if dtype == "approve":
                    detail = "决策引擎判定需人工审批（已进审批队列）"
                elif gate == "review":
                    detail = "模拟闸门 REVIEW：需人工复核后执行"
                else:
                    detail = "等待人工确认"
                actions.append(
                    DailyActionItem(
                        kind=ActionKind.APPROVAL,
                        game_id=d.game_id,
                        action=d.action,
                        detail=detail,
                        decision_audit_id=d.audit_id,
                        opportunity_type=opp_type,
                    )
                )
        return actions

    @staticmethod
    def _gate_reason(audit_id: str, dec_report, gates: Dict[str, str]) -> str:
        return f"模拟闸门 {gates.get(audit_id, 'block').upper()}：不进入执行层"


__all__ = ["DailyGrowthPipeline"]
