"""P3.3.3 — Adaptive Strategy Controller（闭环编排器）。

把 Planner → Simulator → Contract → Approval → SafeExecutor → Feedback 串成
完整闭环，并维护 §4 状态机。

安全边界（铁律）：
- 本模块**绝不** import 任何具体 Provider；
- 唯一出口是注入的 ApprovalService + SafeExecutor（其内部已挂
  build_execution_router(authorization_gate=AuthorizationGate)）；
- 若策略需 MANUAL 审批但调用方未提供 approver，则停在 RECOVERY_REQUIRED，
  绝不为「绕过审批」而自行放行；
- DRY_RUN 路径 real_api_called 恒 False（由 Provider 基类保证）。
"""
from __future__ import annotations

from typing import Any, Optional

from src.ceo_intelligence.simulation_engine.models import PreFlightStatus
from src.execution.approval.roles import minimum_role_for
from src.execution.contracts import build_contract
from src.execution.models import ExecutionMode

from .feedback import AdaptiveStrategyFeedback
from .models import (
    AdaptiveStrategyRequest,
    AdaptiveStrategyResult,
    FinalStatus,
    Stage,
)
from .planner import AdaptiveStrategyPlanner, PlannedAction, UnknownStrategyError
from .simulator import AdaptiveStrategySimulator


class AdaptiveStrategyController:
    """Strategy Proposal 的生产级落地闭环控制器。"""

    def __init__(
        self,
        *,
        approval_service: Any,
        safe_executor: Any,
        registry: Any,
        planner: AdaptiveStrategyPlanner,
        simulator: AdaptiveStrategySimulator,
        feedback: AdaptiveStrategyFeedback,
        memory: Any,
        graph: Any = None,
    ) -> None:
        self.approval = approval_service
        self.safe_executor = safe_executor
        self.registry = registry
        self.planner = planner
        self.simulator = simulator
        self.feedback = feedback
        self.memory = memory
        self.graph = graph

    # ------------------------------------------------------------------
    @staticmethod
    def _set_stage(result: AdaptiveStrategyResult, stage: Stage) -> None:
        """切换阶段并把它记录进 trace（契约 §8 Case 6 要求阶段跃迁审计）。"""
        result.stage = stage.value
        result.trace.append(stage.value)

    # ------------------------------------------------------------------
    def run(self, request: AdaptiveStrategyRequest) -> AdaptiveStrategyResult:
        result = AdaptiveStrategyResult(
            proposal_id=request.proposal_id,
            strategy_id=request.strategy_id,
            target=request.target,
        )
        result.trace.append(Stage.CREATED.value)

        # 1) CREATED —— 适配成 GrowthDecision
        try:
            plan: PlannedAction = self.planner.plan(request)
        except UnknownStrategyError as exc:
            self._set_stage(result, Stage.CREATED)
            result.final_status = FinalStatus.BLOCKED_UNSUPPORTED.value
            result.errors.append(str(exc))
            result.trace.append("plan failed (unsupported/unknown): " + str(exc))
            return result

        result.strategy_id = plan.template.strategy_id
        result.target = request.target
        result.action = plan.template.execution_action.value
        result.trace.append("planned: " + plan.template.strategy_id)

        # 2) SIMULATION_PENDING —— 执行前闸门
        self._set_stage(result, Stage.SIMULATION_PENDING)
        try:
            sim = self.simulator.simulate(plan.decision)
        except Exception as exc:  # noqa: BLE001
            self._set_stage(result, Stage.SIMULATION_FAIL)
            result.final_status = FinalStatus.SIMULATION_FAIL.value
            result.errors.append("simulation error: " + str(exc))
            result.trace.append("simulation error: " + str(exc))
            return result

        result.simulation_flag = sim.flag.status.value
        result.simulation_detail = sim.flag.reason
        if sim.flag.status == PreFlightStatus.BLOCK:
            self._set_stage(result, Stage.SIMULATION_FAIL)
            result.final_status = FinalStatus.SIMULATION_FAIL.value
            result.errors.append("pre-flight BLOCK: " + sim.flag.reason)
            result.trace.append("simulation BLOCK: " + sim.flag.reason)
            return result
        # PASS 或 REVIEW 均继续进入审批（REVIEW 仅作标记，不阻断闭环）
        self._set_stage(result, Stage.SIMULATION_PASS)
        result.trace.append("simulation " + sim.flag.status.value.upper())

        # 3) 构造执行合同（必须传 registry，否则空表 → BLOCKED）
        contract = build_contract(plan.decision, registry=self.registry)
        if contract.blocked or contract.request is None or contract.request.intent is None:
            self._set_stage(result, Stage.SIMULATION_FAIL)
            result.final_status = FinalStatus.EXECUTION_FAILED.value
            msg = "contract blocked: " + contract.reason if contract.blocked else \
                "contract produced no execution request"
            result.errors.append(msg)
            result.trace.append(msg)
            return result

        exec_request = contract.request
        # re-merge Provider 参数（mapper 会丢弃 network / ad_unit_id / campaign_id）
        impact = dict(exec_request.intent.expected_impact or {})
        impact.update(plan.provider_params)
        exec_request.intent.expected_impact = impact
        # 设置运行模式
        try:
            exec_request.mode = ExecutionMode(request.mode)
        except Exception:  # noqa: BLE001
            exec_request.mode = ExecutionMode.DRY_RUN

        # 4) APPROVAL_PENDING —— 提交审批
        self._set_stage(result, Stage.APPROVAL_PENDING)
        submit_result = self.approval.submit(exec_request, requested_by=request.source)
        approval_request = submit_result.request
        result.approval_status = submit_result.outcome

        authorization = None
        if submit_result.auto_approved:
            authorization = submit_result.authorization
            result.trace.append("auto-approved by policy")
        elif submit_result.outcome == "DENY":
            self._set_stage(result, Stage.APPROVAL_REJECTED)
            result.final_status = FinalStatus.APPROVAL_REJECTED.value
            result.errors.append("policy denied: " + submit_result.reason)
            result.trace.append("policy DENY")
            return result
        else:
            # MANUAL / ADMIN：需要人工审批人
            if not request.approver:
                self._set_stage(result, Stage.RECOVERY_REQUIRED)
                result.final_status = FinalStatus.RECOVERY_REQUIRED.value
                result.errors.append(
                    "MANUAL approval required but no approver supplied"
                )
                result.trace.append("MANUAL waiting for human -> RECOVERY_REQUIRED")
                return result
            role = request.approver_role or minimum_role_for(
                plan.template.execution_action.value
            )
            try:
                authorization = self.approval.approve(
                    approval_request.approval_id, request.approver, role
                )
                result.trace.append(f"approved by {request.approver} ({role})")
            except Exception as exc:  # noqa: BLE001
                self._set_stage(result, Stage.APPROVAL_REJECTED)
                result.final_status = FinalStatus.APPROVAL_REJECTED.value
                result.errors.append("approve failed: " + str(exc))
                result.trace.append("approve failed: " + str(exc))
                return result

        # 5) AUTHORIZED —— 挂载授权令牌
        self._set_stage(result, Stage.AUTHORIZED)
        exec_request = self.approval.authorize(exec_request, authorization)

        # 6) EXECUTING —— 经 SafeExecutor（内部挂 Router + AuthorizationGate）
        self._set_stage(result, Stage.EXECUTING)
        outcome = self.safe_executor.execute(exec_request)
        result.execution_verdict = outcome.verdict
        result.execution_result = (
            outcome.result.to_dict() if hasattr(outcome.result, "to_dict") else None
        )
        result.real_api_called = (
            bool(getattr(outcome.result, "real_api_called", False))
            if outcome.result is not None
            else False
        )

        # 7) 闭环最后一环：反馈 → 策略经验
        fb = self.feedback.process(
            plan.template.strategy_id, outcome, action_id=request.proposal_id
        )
        result.feedback = fb.to_dict()

        if outcome.ok:
            self._set_stage(result, Stage.COMPLETED)
            result.final_status = FinalStatus.COMPLETED.value
            result.trace.append("COMPLETED + feedback recorded")
        else:
            self._set_stage(result, Stage.EXECUTION_FAILED)
            result.final_status = FinalStatus.EXECUTION_FAILED.value
            result.errors.append("execution verdict: " + outcome.verdict)
            result.trace.append("execution FAILED: " + outcome.verdict)
        return result


# ---------------------------------------------------------------------------
# 组装工厂：把已有的 P2.2 / P2.3 / P2.4 / P3.3 部件组合起来。
# 共享同一 approval_store（Rule 4 一次性消费依赖它）是关键纪律。
# ---------------------------------------------------------------------------
def build_adaptive_strategy_engine(
    *,
    approval_store: Any = None,
    memory_path: Optional[str] = None,
    providers: Optional[list] = None,
    graph: Any = None,
    policy: Any = None,
    simulator: Any = None,
    prior_provider: Any = None,
):
    """一键装配 AdaptiveStrategyController（共享 store 的闭环）。"""
    from src.execution.approval.service import ApprovalService
    from src.execution.approval.store import InMemoryApprovalStore
    from src.execution.approval.workflow import AuthorizationGate
    from src.execution.providers import build_default_registry, build_execution_router
    from src.execution.safe_executor.executor import build_safe_executor
    from src.operator.strategy.memory import StrategyMemoryAdapter

    store = approval_store or InMemoryApprovalStore()
    registry = build_default_registry()
    router = build_execution_router(
        registry=registry,
        providers=providers,
        approval_store=store,
        authorization_gate=AuthorizationGate(store=store),
    )
    safe_executor = build_safe_executor(router)
    approval_service = ApprovalService(store=store, policy=policy, router=router)
    memory = StrategyMemoryAdapter(store_path=memory_path)
    planner = AdaptiveStrategyPlanner()
    sim = AdaptiveStrategySimulator(
        graph=graph, simulator=simulator, prior_provider=prior_provider
    )
    feedback = AdaptiveStrategyFeedback(memory)

    return AdaptiveStrategyController(
        approval_service=approval_service,
        safe_executor=safe_executor,
        registry=registry,
        planner=planner,
        simulator=sim,
        feedback=feedback,
        memory=memory,
        graph=graph,
    )


__all__ = ["AdaptiveStrategyController", "build_adaptive_strategy_engine"]
