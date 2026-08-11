"""E17.6 — Growth Execution Router 主入口（Agent）。

输入：E17.4 GrowthStrategyPlan（作战计划）
输出：ExecutionReport {execution_id, status, actions:[{action, result}]}

依赖顺序执行：按 source_task_order 升序；前置任务非 SUCCESS 时下游 SKIPPED
（WAITING_APPROVAL 的下游同样跳过——待人工批准后重跑）。

run_pipeline() 串联 E17.1 → E17.2 → E17.3 → E17.4 → E17.6（大脑到手脚全链路）。
SIM 纪律：默认路由表全 SIM，real_api_called 永远 False。
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Tuple

from src.ceo_intelligence.strategy_planner.agent import (
    run_pipeline as _strategy_pipeline,
)
from src.ceo_intelligence.strategy_planner.models import (
    GrowthStrategyPlan,
    PortfolioStrategyPlan,
)

from .executor import ActionCompiler
from .memory import ExecutionMemory
from .models import ExecutionReport, ExecutionResult, ExecutionStatus
from .router import ApprovalOutbox, ExecutionRouter

_S = ExecutionStatus


class GrowthExecutionRouterAgent:
    """对外 API：execute_plan(strategy_plan) → ExecutionReport。"""

    def __init__(
        self,
        router: Optional[ExecutionRouter] = None,
        compiler: Optional[ActionCompiler] = None,
    ):
        self.router = router or ExecutionRouter()
        self.compiler = compiler or ActionCompiler()

    # ------------------------------------------------------------------ #
    def execute_plan(self, plan: GrowthStrategyPlan) -> ExecutionReport:
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        actions = self.compiler.compile_plan(plan)
        results_by_order: Dict[int, ExecutionResult] = {}
        items: List[Dict] = []

        for action in actions:  # 已按 order 升序
            blocked = self._blocked_reason(action.dependency, results_by_order)
            if blocked:
                result = self.router.record_skip(action, blocked, execution_id=execution_id)
            else:
                result = self.router.route(action, execution_id=execution_id)
            results_by_order[action.source_task_order] = result
            items.append({"action": action.to_dict(), "result": result.to_dict()})

        summary = self._summarize(results_by_order)
        return ExecutionReport(
            execution_id=execution_id,
            game_id=plan.game_id,
            decision_id=plan.decision_id,
            strategy_type=plan.strategy_type,
            status=self._overall_status(summary),
            actions=items,
            summary=summary,
        )

    def approve(self, action_id: str, *, approver: str = "human",
                reason: str = "") -> ExecutionResult:
        return self.router.approve(action_id, approver=approver, reason=reason)

    def reject(self, action_id: str, *, approver: str = "human", reason: str = "") -> None:
        self.router.reject(action_id, approver=approver, reason=reason)

    def pending_approvals(self):
        return self.router.pending_approvals()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _blocked_reason(dependency: List[str],
                        results_by_order: Dict[int, ExecutionResult]) -> str:
        for dep in dependency:
            try:
                dep_order = int(dep)
            except ValueError:
                continue
            dep_result = results_by_order.get(dep_order)
            if dep_result is None:
                return f"skipped: dependency task {dep} not executed"
            if dep_result.status != _S.SUCCESS:
                return (
                    f"skipped: dependency task {dep} is "
                    f"{dep_result.status.value}"
                )
        return ""

    @staticmethod
    def _summarize(results_by_order: Dict[int, ExecutionResult]) -> Dict:
        rows = list(results_by_order.values())
        return {
            "total": len(rows),
            "success": sum(1 for r in rows if r.status == _S.SUCCESS),
            "waiting_approval": sum(1 for r in rows if r.status == _S.WAITING_APPROVAL),
            "failed": sum(1 for r in rows if r.status in (_S.FAILED, _S.ROLLBACK)),
            "skipped": sum(1 for r in rows if r.status == _S.SKIPPED),
            "rolled_back": sum(1 for r in rows if r.rolled_back),
            "real_api_called": any(r.real_api_called for r in rows),
        }

    @staticmethod
    def _overall_status(summary: Dict) -> str:
        if summary["failed"] > 0:
            return "failed"
        if summary["waiting_approval"] > 0:
            return "waiting_approval"
        if summary["success"] == summary["total"] and summary["total"] > 0:
            return "success"
        return "partial"


# --------------------------------------------------------------------------- #
# 端到端流水线：Reality → Opportunity → Decision → Strategy → Execution
# --------------------------------------------------------------------------- #
def run_pipeline(
    company,
    *,
    store=None,
    opportunity_memory=None,
    decision_memory=None,
    strategy_memory=None,
    execution_router: Optional[ExecutionRouter] = None,
    execution_memory: Optional[ExecutionMemory] = None,
    approval_outbox: Optional[ApprovalOutbox] = None,
    segment: str = "global",
    top_n: int = 10,
    approval_queue_path: str = "data/ceo/approval_queue.jsonl",
    audit_dir: str = "data/ceo/audit",
    created_at: str = "",
) -> Tuple[object, PortfolioStrategyPlan, List[ExecutionReport]]:
    """E17.1 → E17.2 → E17.3 → E17.4 → E17.6 全链路（默认全 SIM）。"""
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
    if execution_router is None:
        from audit.trail import AuditTrail

        execution_router = ExecutionRouter(
            audit=AuditTrail(audit_dir=audit_dir),
            memory=execution_memory,
            outbox=approval_outbox,
        )
    router = execution_router
    agent = GrowthExecutionRouterAgent(router=router)
    reports = [agent.execute_plan(p) for p in portfolio.plans]
    return dec_report, portfolio, reports


__all__ = ["GrowthExecutionRouterAgent", "run_pipeline"]
