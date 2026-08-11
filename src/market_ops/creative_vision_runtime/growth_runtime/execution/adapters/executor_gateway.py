"""E13.7 Executor Gateway — 统一执行网关.

作为 Real Execution Layer 的统一入口，负责:
  - 路由: 根据 ActionType + Platform → 选择正确的 Executor
  - 降级: 平台不可用时自动降级到 MOCK
  - 策略: 应用 ExecutionPolicy 控制执行模式
  - 验证: 执行后自动触发 Adjust 验证
  - 审计: 记录所有执行结果到 AuditLog

核心流程:
  ExecutionAction → PolicyEngine → Route → Executor → RealExecutionResult → AdjustVerifier → GatewayResult

连接:
  E13.5 Decision Engine → E13.6.2 Action Planner → E13.7 ExecutorGateway → Executor → Platform API
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..base_executor import (
    BaseExecutor,
    ExecutionResult,
    ExecutionResultStatus,
    GuardContext,
)
from ..models import ExecutionAction, ExecutionActionType, ExecutionDomain
from ..executor_registry import ExecutorRegistry
from .adapter_models import (
    ExecutionMode,
    PlatformType,
    RealExecutionResult,
    VerificationResult,
)
from .execution_policy import (
    PolicyDecision,
    PolicyEngine,
    create_safe_real_policy,
)
from .adjust_verifier import AdjustVerifier


# ═══════════════════════════════════════════════════════════════
# Gateway Result
# ═══════════════════════════════════════════════════════════════


class GatewayResultStatus(str):
    """网关结果状态."""
    SUCCESS = "success"
    FAILED = "failed"
    DEGRADED = "degraded"           # 降级到 MOCK
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"             # 安全策略阻止
    ROUTE_NOT_FOUND = "route_not_found"


@dataclass
class GatewayResult:
    """网关执行结果 — 包含完整的执行链路信息.

    Attributes:
        gateway_result_id: 网关结果 ID
        action_id: 关联的动作 ID
        action_type: 动作类型
        status: 网关结果状态
        policy_decision: 策略决策
        execution_result: 执行器执行结果
        real_result: 真实执行结果 (仅 REAL 模式)
        verification: 验证结果 (仅启用验证时)
        degraded: 是否降级
        degrade_reason: 降级原因
        error_message: 错误信息
        started_at: 开始时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    gateway_result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: str = ""
    status: str = GatewayResultStatus.SUCCESS
    policy_decision: PolicyDecision | None = None
    execution_result: ExecutionResult | None = None
    real_result: RealExecutionResult | None = None
    verification: VerificationResult | None = None
    degraded: bool = False
    degrade_reason: str = ""
    error_message: str = ""
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == GatewayResultStatus.SUCCESS

    @property
    def is_degraded(self) -> bool:
        return self.status == GatewayResultStatus.DEGRADED

    @property
    def needs_approval(self) -> bool:
        return self.status == GatewayResultStatus.APPROVAL_REQUIRED

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_result_id": self.gateway_result_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "status": self.status,
            "policy_decision": self.policy_decision.__dict__ if self.policy_decision else None,
            "execution_result": self.execution_result.to_dict() if self.execution_result else None,
            "real_result": self.real_result.to_dict() if self.real_result else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "degraded": self.degraded,
            "degrade_reason": self.degrade_reason,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Platform Router
# ═══════════════════════════════════════════════════════════════


# ActionType → PlatformType 映射
ACTION_PLATFORM_MAP: dict[ExecutionActionType, PlatformType] = {
    ExecutionActionType.CREATE_CAMPAIGN: PlatformType.META,
    ExecutionActionType.CREATE_AD_SET: PlatformType.META,
    ExecutionActionType.UPDATE_CAMPAIGN: PlatformType.META,
    ExecutionActionType.PAUSE_CAMPAIGN: PlatformType.META,
    ExecutionActionType.FREEZE_CAMPAIGN: PlatformType.META,
    ExecutionActionType.UPDATE_BUDGET: PlatformType.META,
    ExecutionActionType.SCALE_BUDGET: PlatformType.META,
    ExecutionActionType.REDUCE_BUDGET: PlatformType.META,
    ExecutionActionType.UPLOAD_CREATIVE: PlatformType.META,
    ExecutionActionType.PAUSE_CREATIVE: PlatformType.META,
    ExecutionActionType.CREATE_CREATIVE: PlatformType.INTERNAL,
    ExecutionActionType.MUTATE_CREATIVE: PlatformType.INTERNAL,
    ExecutionActionType.MONITOR: PlatformType.ADJUST,
    ExecutionActionType.COLLECT_RESULT: PlatformType.ADJUST,
}


# ═══════════════════════════════════════════════════════════════
# Executor Gateway
# ═══════════════════════════════════════════════════════════════


class ExecutorGateway:
    """统一执行网关 — 真实执行层的核心路由.

    职责:
      1. 接收 ExecutionAction
      2. 通过 PolicyEngine 计算执行模式
      3. 路由到正确的 Executor (Meta/Creative/Adjust)
      4. 处理降级和安全检查
      5. 触发 Adjust 验证 (REAL 模式)
      6. 返回统一的 GatewayResult

    用法:
        gateway = ExecutorGateway(
            meta_executor=meta_executor,
            creative_executor=creative_executor,
            verifier=adjust_verifier,
        )

        # 执行单个动作
        result = gateway.execute(action, guard_context)

        # 执行动作列表
        results = gateway.execute_batch(actions, guard_context)

        if result.is_success:
            print(f"成功: {result.real_result.platform_entity_id}")
        elif result.is_degraded:
            print(f"已降级: {result.degrade_reason}")
    """

    # Default routing: domain → executor
    DOMAIN_ROUTING: dict[ExecutionDomain, PlatformType] = {
        ExecutionDomain.CAMPAIGN: PlatformType.META,
        ExecutionDomain.CREATIVE: PlatformType.INTERNAL,
        ExecutionDomain.BUDGET: PlatformType.META,
        ExecutionDomain.MONITOR: PlatformType.ADJUST,
    }

    def __init__(
        self,
        meta_executor: BaseExecutor | None = None,
        creative_executor: BaseExecutor | None = None,
        verifier: AdjustVerifier | None = None,
        policy_engine: PolicyEngine | None = None,
        registry: ExecutorRegistry | None = None,
        name: str = "ExecutorGateway",
    ):
        self._name = name
        self._meta_executor = meta_executor
        self._creative_executor = creative_executor
        self._verifier = verifier
        self._policy_engine = policy_engine or PolicyEngine()
        self._registry = registry

        # 统计
        self._total_requests: int = 0
        self._success_count: int = 0
        self._degraded_count: int = 0
        self._approval_count: int = 0
        self._failure_count: int = 0

    # ── 主入口 ────────────────────────────────────────────────

    def execute(
        self,
        action: ExecutionAction,
        guard_context: GuardContext | None = None,
        verify: bool = True,
    ) -> GatewayResult:
        """执行单个动作.

        Args:
            action: 要执行的 ExecutionAction
            guard_context: 安全上下文
            verify: 是否触发 Adjust 验证

        Returns:
            GatewayResult: 网关执行结果
        """
        self._total_requests += 1
        started_at = datetime.now(timezone.utc).isoformat()
        guard_context = guard_context or GuardContext()

        # 1. 策略评估
        platform = self._resolve_platform(action)
        policy_decision = self._policy_engine.evaluate(
            action_type=action.action_type.value,
            platform=platform,
        )

        # 2. 审批检查
        if policy_decision.needs_approval:
            self._approval_count += 1
            return GatewayResult(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=GatewayResultStatus.APPROVAL_REQUIRED,
                policy_decision=policy_decision,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        # 3. 降级检查
        if policy_decision.degraded:
            return self._execute_degraded(
                action, guard_context, policy_decision, started_at
            )

        # 4. 路由到 Executor
        executor = self._route(action)
        if executor is None:
            self._failure_count += 1
            return GatewayResult(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=GatewayResultStatus.ROUTE_NOT_FOUND,
                policy_decision=policy_decision,
                error_message=f"no_executor_for: {action.action_type.value}",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        # 5. 设置执行模式
        self._apply_mode(executor, policy_decision.resolved_mode)

        # 6. 执行
        try:
            execution_result = executor.execute(action, guard_context)
        except Exception as e:
            # 执行异常 → 尝试降级
            if self._policy_engine.policy.degrade_on_failure:
                self._degraded_count += 1
                return GatewayResult(
                    action_id=action.action_id,
                    action_type=action.action_type.value,
                    status=GatewayResultStatus.DEGRADED,
                    policy_decision=policy_decision,
                    degraded=True,
                    degrade_reason=f"execution_error: {e}",
                    error_message=str(e),
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            self._failure_count += 1
            return GatewayResult(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=GatewayResultStatus.FAILED,
                policy_decision=policy_decision,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        # 7. 构建 RealExecutionResult
        real_result = self._build_real_result(action, execution_result, policy_decision)

        # 8. Adjust 验证
        verification = None
        if verify and policy_decision.resolved_mode == ExecutionMode.REAL:
            if self._verifier and real_result:
                verification = self._verifier.verify(real_result)

        # 9. 构建最终结果
        completed_at = datetime.now(timezone.utc).isoformat()
        status = self._compute_status(execution_result)

        if status == GatewayResultStatus.SUCCESS:
            self._success_count += 1
        else:
            self._failure_count += 1

        return GatewayResult(
            action_id=action.action_id,
            action_type=action.action_type.value,
            status=status,
            policy_decision=policy_decision,
            execution_result=execution_result,
            real_result=real_result,
            verification=verification,
            started_at=started_at,
            completed_at=completed_at,
        )

    def execute_batch(
        self,
        actions: list[ExecutionAction],
        guard_context: GuardContext | None = None,
        verify: bool = True,
        stop_on_failure: bool = False,
    ) -> list[GatewayResult]:
        """批量执行动作.

        Args:
            actions: 动作列表
            guard_context: 安全上下文
            verify: 是否触发 Adjust 验证
            stop_on_failure: 遇到失败是否停止

        Returns:
            list[GatewayResult]: 结果列表
        """
        results: list[GatewayResult] = []
        for action in actions:
            result = self.execute(action, guard_context, verify)
            results.append(result)

            if stop_on_failure and result.status == GatewayResultStatus.FAILED:
                break

        return results

    def execute_plan(
        self,
        actions: list[ExecutionAction],
        guard_context: GuardContext | None = None,
        verify: bool = True,
    ) -> list[GatewayResult]:
        """执行计划 — 批量执行，失败自动回滚.

        Args:
            actions: 动作列表
            guard_context: 安全上下文
            verify: 是否触发 Adjust 验证

        Returns:
            list[GatewayResult]: 结果列表
        """
        results: list[GatewayResult] = []
        for action in actions:
            result = self.execute(action, guard_context, verify)
            results.append(result)

            if result.status == GatewayResultStatus.FAILED:
                # 回滚之前成功的动作
                self._rollback_previous(results)
                break

        return results

    # ── 路由 ──────────────────────────────────────────────────

    def _route(self, action: ExecutionAction) -> BaseExecutor | None:
        """路由执行器.

        优先级:
          1. ExecutorRegistry (如果配置了)
          2. 领域路由 (CAMPAIGN → Meta, CREATIVE → Creative)
          3. 默认执行器
        """
        # 1. Registry 优先
        if self._registry and self._registry.has(action.action_type):
            return self._registry.get(action.action_type)

        # 2. 领域路由
        platform = self._resolve_platform(action)
        if platform == PlatformType.META:
            return self._meta_executor
        elif platform == PlatformType.INTERNAL:
            return self._creative_executor

        # 3. Registry 默认
        if self._registry:
            return self._registry.get(action.action_type)

        return None

    def _resolve_platform(self, action: ExecutionAction) -> PlatformType:
        """解析目标平台."""
        # 优先 action 显式指定
        platform_str = action.metadata.get("platform", "")
        if platform_str:
            try:
                return PlatformType(platform_str)
            except ValueError:
                pass

        # 从映射表查找
        return ACTION_PLATFORM_MAP.get(action.action_type, PlatformType.META)

    # ── 模式应用 ──────────────────────────────────────────────

    def _apply_mode(
        self,
        executor: BaseExecutor,
        mode: ExecutionMode,
    ) -> None:
        """应用执行模式到 Executor."""
        try:
            if hasattr(executor, "mode"):
                # Check if mode has a setter (property with setter)
                executor_type = type(executor)
                mode_attr = getattr(executor_type, "mode", None)
                if mode_attr is not None and hasattr(mode_attr, "fset") and mode_attr.fset is not None:
                    executor.mode = mode
        except (AttributeError, TypeError):
            pass

    # ── 降级执行 ──────────────────────────────────────────────

    def _execute_degraded(
        self,
        action: ExecutionAction,
        guard_context: GuardContext,
        policy_decision: PolicyDecision,
        started_at: str,
    ) -> GatewayResult:
        """降级执行 — 使用 MOCK 模式."""
        self._degraded_count += 1

        # 降级到 MOCK 模式执行
        executor = self._route(action)
        if executor and hasattr(executor, "mode"):
            executor.mode = ExecutionMode.MOCK

        execution_result = None
        if executor:
            try:
                execution_result = executor.execute(action, guard_context)
            except Exception:
                pass

        return GatewayResult(
            action_id=action.action_id,
            action_type=action.action_type.value,
            status=GatewayResultStatus.DEGRADED,
            policy_decision=policy_decision,
            execution_result=execution_result,
            degraded=True,
            degrade_reason=policy_decision.degrade_reason.value if policy_decision.degrade_reason else "unknown",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── 回滚 ──────────────────────────────────────────────────

    def _rollback_previous(self, results: list[GatewayResult]) -> None:
        """回滚之前成功的动作."""
        for result in results:
            if result.is_success and result.execution_result:
                # 标记已回滚 (实际回滚由 Executor._rollback 处理)
                result.metadata["rolled_back"] = True
                result.metadata["rolled_back_at"] = datetime.now(timezone.utc).isoformat()

    # ── 结果构建 ──────────────────────────────────────────────

    def _build_real_result(
        self,
        action: ExecutionAction,
        execution_result: ExecutionResult,
        policy_decision: PolicyDecision,
    ) -> RealExecutionResult | None:
        """从 ExecutionResult 构建 RealExecutionResult."""
        platform = self._resolve_platform(action)
        platform_entity_id = execution_result.metadata.get("platform_entity_id", "")

        return RealExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type.value,
            platform=platform,
            mode=policy_decision.resolved_mode,
            success=execution_result.is_success,
            platform_entity_id=platform_entity_id,
            platform_entity_url=execution_result.metadata.get("platform_entity_url", ""),
            verified=False,
            started_at=execution_result.started_at,
            completed_at=execution_result.completed_at,
            error_message=execution_result.error_message,
            metadata={
                "executor": execution_result.executor,
                "policy": policy_decision.policy_name,
            },
        )

    def _compute_status(self, execution_result: ExecutionResult) -> str:
        """根据执行结果计算网关状态."""
        if execution_result.is_success:
            return GatewayResultStatus.SUCCESS
        elif execution_result.needs_approval:
            return GatewayResultStatus.APPROVAL_REQUIRED
        else:
            return GatewayResultStatus.FAILED

    # ── 降级管理 ──────────────────────────────────────────────

    def degrade_platform(
        self,
        platform: PlatformType,
        reason: str,
    ) -> None:
        """降级指定平台."""
        from .execution_policy import DegradeReason
        try:
            degrade_reason = DegradeReason(reason)
        except ValueError:
            degrade_reason = DegradeReason.API_UNAVAILABLE
        self._policy_engine.degrade_platform(platform, degrade_reason)

    def restore_platform(self, platform: PlatformType) -> None:
        """恢复平台."""
        self._policy_engine.restore_platform(platform)

    # ── 查询接口 ──────────────────────────────────────────────

    def can_execute(self, action: ExecutionAction) -> bool:
        """检查是否可以执行."""
        policy_decision = self._policy_engine.evaluate(
            action_type=action.action_type.value,
            platform=self._resolve_platform(action),
        )
        return (
            not policy_decision.needs_approval
            and not policy_decision.degraded
        )

    def needs_approval(self, action: ExecutionAction) -> bool:
        """检查是否需要审批."""
        policy_decision = self._policy_engine.evaluate(
            action_type=action.action_type.value,
            platform=self._resolve_platform(action),
        )
        return policy_decision.needs_approval

    def get_risk_level(self, action: ExecutionAction) -> str:
        """获取动作风险等级."""
        policy_decision = self._policy_engine.evaluate(
            action_type=action.action_type.value,
            platform=self._resolve_platform(action),
        )
        return policy_decision.risk_level.value

    # ── 统计 ──────────────────────────────────────────────────

    @property
    def total_requests(self) -> int:
        return self._total_requests

    @property
    def success_rate(self) -> float:
        if self._total_requests == 0:
            return 1.0
        return self._success_count / self._total_requests

    def stats(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "total_requests": self._total_requests,
            "success_count": self._success_count,
            "degraded_count": self._degraded_count,
            "approval_count": self._approval_count,
            "failure_count": self._failure_count,
            "success_rate": round(self.success_rate, 4),
            "policy": self._policy_engine.stats(),
            "verifier": self._verifier.stats() if self._verifier else None,
        }

    def reset(self) -> None:
        """重置统计."""
        self._total_requests = 0
        self._success_count = 0
        self._degraded_count = 0
        self._approval_count = 0
        self._failure_count = 0
        self._policy_engine.clear_degraded()
        if self._verifier:
            self._verifier.reset()