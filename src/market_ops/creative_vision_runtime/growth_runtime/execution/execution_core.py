"""E13.6.3 Execution Engine — 执行引擎核心.

消费 ActionPlan，通过 ExecutorRegistry 路由到对应 Executor，使用 StateMachine 管理
生命周期，通过 AuditLog 记录所有执行结果。

核心流程:
  ActionPlan
      ↓
  ExecutionEngine.execute()
      ↓
  [按 execution_order 遍历 ActionNode]
      ↓
  ExecutorRegistry.get(action_type)
      ↓
  BaseExecutor.execute(action, guard_context)
      ↓
  StateMachine.transition()
      ↓
  AuditLog.record()
      ↓
  ExecutionResult

连接:
  E13.6.2 ActionPlanner → E13.6.3 ExecutionEngine → E13.6.5 Feedback Loop
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .action_models import ActionNode, ActionPlan, ActionStatus, PlanPhase
from .audit_log import AuditLog
from .base_executor import (
    BaseExecutor,
    ExecutionResult,
    ExecutionResultStatus,
    GuardContext,
)
from .execution_context import ExecutionContext
from .executor_registry import ExecutorRegistry
from .models import ExecutionAction, ExecutionActionType, ExecutionDomain, ExecutionPriority
from .state_machine import ExecutionPhase, ExecutionStateMachine


# ═══════════════════════════════════════════════════════════════
# Engine Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class EngineResult:
    """引擎执行结果 — 整个 ActionPlan 的执行结果汇总.

    Attributes:
        plan_id: 执行的计划 ID
        task_id: 关联的任务 ID
        node_results: 每个 ActionNode 的执行结果映射
        execution_order: 实际执行顺序
        total_nodes: 总节点数
        success_count: 成功节点数
        failure_count: 失败节点数
        skipped_count: 跳过节点数
        rollback_count: 回滚节点数
        status: 整体状态
        started_at: 开始时间
        completed_at: 完成时间
        error_message: 错误信息
        metadata: 扩展元数据
    """
    plan_id: str = ""
    task_id: str = ""
    node_results: dict[str, ExecutionResult] = field(default_factory=dict)
    execution_order: list[str] = field(default_factory=list)
    total_nodes: int = 0
    success_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    rollback_count: int = 0
    status: ExecutionResultStatus = ExecutionResultStatus.SUCCESS
    started_at: str = ""
    completed_at: str = ""
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionResultStatus.SUCCESS

    @property
    def has_failures(self) -> bool:
        return self.failure_count > 0

    @property
    def success_rate(self) -> float:
        if self.total_nodes == 0:
            return 1.0
        return self.success_count / self.total_nodes

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "node_results": {k: v.to_dict() for k, v in self.node_results.items()},
            "execution_order": self.execution_order,
            "total_nodes": self.total_nodes,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "skipped_count": self.skipped_count,
            "rollback_count": self.rollback_count,
            "status": self.status.value,
            "success_rate": round(self.success_rate, 4),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    def stats(self) -> dict[str, Any]:
        return {
            "total": self.total_nodes,
            "success": self.success_count,
            "failure": self.failure_count,
            "skipped": self.skipped_count,
            "rollback": self.rollback_count,
            "success_rate": round(self.success_rate, 4),
        }


# ═══════════════════════════════════════════════════════════════
# Execution Engine
# ═══════════════════════════════════════════════════════════════


class ExecutionEngine:
    """执行引擎 — 消费 ActionPlan，驱动 Executor 执行.

    用法:
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.CREATE_CREATIVE, CreativeExecutor())
        registry.register(ExecutionActionType.MONITOR, MonitorExecutor())

        engine = ExecutionEngine(registry)
        result = engine.execute(action_plan)
    """

    def __init__(
        self,
        registry: ExecutorRegistry | None = None,
        audit_log: AuditLog | None = None,
    ):
        self._registry = registry or ExecutorRegistry()
        self._audit_log = audit_log or AuditLog()
        self._state_machines: dict[str, ExecutionStateMachine] = {}

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def registry(self) -> ExecutorRegistry:
        return self._registry

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    # ── 主入口 ────────────────────────────────────────────────

    def execute(
        self,
        plan: ActionPlan,
        guard_context: GuardContext | None = None,
        context: ExecutionContext | None = None,
        decision_id: str = "",
        reason: str = "",
    ) -> EngineResult:
        """执行 ActionPlan.

        Args:
            plan: 要执行的 ActionPlan
            guard_context: 安全上下文 (兼容旧接口)
            context: 执行上下文 (E13.6.3, 优先于 guard_context)
            decision_id: 关联的决策 ID
            reason: 执行原因

        Returns:
            EngineResult: 执行结果汇总
        """
        # 优先使用 ExecutionContext
        if context is not None:
            guard_context = context.guard_context
            decision_id = decision_id or context.decision_id
            reason = reason or context.reason

        guard_context = guard_context or GuardContext()
        started_at = datetime.now(timezone.utc).isoformat()

        result = EngineResult(
            plan_id=plan.plan_id,
            task_id=plan.task_id,
            started_at=started_at,
        )

        # 获取执行顺序
        execution_order = plan.execution_order
        if not execution_order:
            execution_order = [n.node_id for n in plan.nodes]

        result.execution_order = execution_order
        result.total_nodes = len(execution_order)

        # 按顺序执行每个节点
        for node_id in execution_order:
            node = plan.get_node(node_id)
            if node is None:
                continue

            # 创建状态机
            sm = ExecutionStateMachine(node_id=node_id)
            self._state_machines[node_id] = sm

            try:
                # 1. 校验
                sm.mark_validating("开始校验")

                # 2. 获取执行器
                executor = self._registry.get(node.action.action_type)
                if executor is None:
                    sm.mark_skipped(f"未注册的执行器: {node.action.action_type.value}")
                    result.skipped_count += 1
                    continue

                # 3. 就绪
                sm.mark_ready("校验通过")

                # 4. 执行
                sm.mark_executing("开始执行")
                node_result = executor.execute(node.action, guard_context)

                # 5. 记录结果
                result.node_results[node_id] = node_result

                if node_result.is_success:
                    sm.mark_success("执行成功")
                    sm.mark_completed("完成")
                    result.success_count += 1
                elif node_result.needs_approval:
                    sm.mark_pending_approval("需要审批")
                    result.skipped_count += 1
                elif node_result.is_failed:
                    sm.mark_failed(node_result.error_message or "执行失败")
                    result.failure_count += 1

                    # 尝试回滚
                    if plan.rollback_enabled:
                        self._try_rollback(node, sm, result)

                # 审计记录
                self._audit_log.record(
                    node_result,
                    reason=reason,
                    node_id=node_id,
                    plan_id=plan.plan_id,
                    task_id=plan.task_id,
                    decision_id=decision_id,
                )

            except Exception as e:
                sm.mark_failed(str(e))
                result.failure_count += 1

                error_result = ExecutionResult(
                    action_id=node.action.action_id,
                    action_type=node.action.action_type,
                    status=ExecutionResultStatus.FAILED,
                    executor="unknown",
                    error_message=str(e),
                    reason=str(e),
                )
                result.node_results[node_id] = error_result

                self._audit_log.record(
                    error_result,
                    reason=reason,
                    node_id=node_id,
                    plan_id=plan.plan_id,
                    task_id=plan.task_id,
                    decision_id=decision_id,
                )

        # 汇总
        result.completed_at = datetime.now(timezone.utc).isoformat()
        if result.failure_count > 0:
            result.status = ExecutionResultStatus.FAILED
        elif result.skipped_count == result.total_nodes:
            result.status = ExecutionResultStatus.SKIPPED
        else:
            result.status = ExecutionResultStatus.SUCCESS

        return result

    # ── 回滚 ──────────────────────────────────────────────────

    def _try_rollback(
        self,
        node: ActionNode,
        sm: ExecutionStateMachine,
        result: EngineResult,
    ) -> None:
        """尝试回滚失败的节点."""
        try:
            sm.mark_rollback_pending("准备回滚")

            executor = self._registry.get(node.action.action_type)
            if executor:
                sm.mark_rollback_executing("执行回滚")
                rollback_result = executor.rollback(node.action)

                if rollback_result.status == ExecutionResultStatus.ROLLED_BACK:
                    sm.mark_rolled_back("回滚完成")
                    result.rollback_count += 1
                else:
                    sm.mark_failed("回滚失败")
            else:
                sm.mark_failed("无回滚执行器")

        except Exception:
            sm.mark_failed("回滚异常")

    # ── 回滚整个计划 ──────────────────────────────────────────

    def rollback_plan(self, plan: ActionPlan) -> EngineResult:
        """回滚整个 ActionPlan (按 rollback_order 逆序执行).

        Args:
            plan: 要回滚的 ActionPlan

        Returns:
            EngineResult: 回滚结果
        """
        rollback_order = plan.rollback_order
        if not rollback_order:
            return EngineResult(
                plan_id=plan.plan_id,
                task_id=plan.task_id,
                status=ExecutionResultStatus.SKIPPED,
                error_message="无回滚顺序",
            )

        started_at = datetime.now(timezone.utc).isoformat()
        result = EngineResult(
            plan_id=plan.plan_id,
            task_id=plan.task_id,
            started_at=started_at,
            total_nodes=len(rollback_order),
        )

        for node_id in rollback_order:
            node = plan.get_node(node_id)
            if node is None:
                continue

            executor = self._registry.get(node.action.action_type)
            if executor is None:
                result.skipped_count += 1
                continue

            try:
                rollback_result = executor.rollback(node.action)
                result.node_results[node_id] = rollback_result

                if rollback_result.status == ExecutionResultStatus.ROLLED_BACK:
                    result.rollback_count += 1
                else:
                    result.failure_count += 1

                self._audit_log.record(
                    rollback_result,
                    reason="plan_rollback",
                    node_id=node_id,
                    plan_id=plan.plan_id,
                    task_id=plan.task_id,
                )

            except Exception as e:
                result.failure_count += 1

        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.status = (
            ExecutionResultStatus.SUCCESS
            if result.failure_count == 0
            else ExecutionResultStatus.FAILED
        )
        return result

    # ── 状态机查询 ────────────────────────────────────────────

    def get_state_machine(self, node_id: str) -> ExecutionStateMachine | None:
        """获取节点的状态机."""
        return self._state_machines.get(node_id)

    def get_all_state_machines(self) -> dict[str, ExecutionStateMachine]:
        """获取所有状态机."""
        return dict(self._state_machines)

    def get_running_nodes(self) -> list[str]:
        """获取正在运行的节点."""
        return [
            nid for nid, sm in self._state_machines.items()
            if sm.is_running
        ]

    def get_failed_nodes(self) -> list[str]:
        """获取失败的节点."""
        return [
            nid for nid, sm in self._state_machines.items()
            if sm.is_failed
        ]

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "registry": self._registry.stats(),
            "audit_log": self._audit_log.stats(),
            "active_state_machines": len(self._state_machines),
        }