"""E15.0.9 Execution Adapter Wiring — 连接现有模块到 ExecutionRouter.

将 E15.0 现有模块 (Safety Governor, Audit, Monitoring) 通过钩子机制
集成到 E15.0.9 ExecutionRouter 中，实现:

  GrowthAction → Safety Governor → ExecutionRouter → Adapter → Audit + Monitoring

核心组件:
  - SafetyGovernorAdapter: 将 GrowthAction 映射到 SafetyGovernor.evaluate()
  - AuditHookAdapter:      将 AdapterExecutionResult 记录到 AuditService
  - MetricsHookAdapter:    将执行结果记录到 MetricsCollector

用法:
    from growth_runtime.execution.wiring import wire_execution_layer

    router = ExecutionRouter(registry)
    safety = SafetyGovernor()
    audit = AuditService()
    metrics = MetricsCollector()

    wire_execution_layer(router, safety=safety, audit=audit, metrics=metrics)
    result = router.execute(action)  # 自动经过 Safety → Audit → Metrics
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

from .adapter_base import AdapterExecutionResult, AdapterResultStatus
from .growth_action import ActionType, GrowthAction

if TYPE_CHECKING:
    from ..safety.governor import SafetyGovernor
    from ..audit.audit_service import AuditService
    from ..monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# ActionType Mapping: E15.0.9 → E15.0.3 Safety
# ═══════════════════════════════════════════════════════════════

# 延迟导入避免循环依赖
def _get_safety_action_type():
    from ..safety.governor import ActionType as SafetyActionType
    return SafetyActionType


ACTION_TYPE_TO_SAFETY_MAP: dict[ActionType, str] = {
    ActionType.UPDATE_CAMPAIGN_BUDGET: "BUDGET_CHANGE",
    ActionType.PAUSE_CAMPAIGN: "PAUSE_CAMPAIGN",
    ActionType.RESUME_CAMPAIGN: "RESUME_CAMPAIGN",
    ActionType.CREATE_CAMPAIGN: "CREATE_CAMPAIGN",
    ActionType.UPLOAD_CREATIVE: "UPLOAD_CREATIVE",
    ActionType.MUTATE_CREATIVE: "MUTATE_CREATIVE",
    # 无直接映射的动作默认通过安全校验
}

# 不需要安全检查的动作类型 (低风险)
SKIP_SAFETY_ACTIONS: set[ActionType] = {
    ActionType.MONITOR,
    ActionType.NOOP,
    ActionType.VERIFY_ATTRIBUTION,
    ActionType.SYNC_METADATA,
}


# ═══════════════════════════════════════════════════════════════
# Safety Governor Adapter
# ═══════════════════════════════════════════════════════════════


def create_safety_governor_hook(
    governor: "SafetyGovernor",
) -> Callable[[GrowthAction], bool]:
    """创建 Safety Governor 钩子函数.

    将 E15.0.9 GrowthAction 映射到 E15.0.3 SafetyGovernor.evaluate().

    Args:
        governor: SafetyGovernor 实例

    Returns:
        Callable[[GrowthAction], bool]: 可注册到 ExecutionRouter 的安全检查函数
    """
    SafetyActionType = _get_safety_action_type()

    def safety_check(action: GrowthAction) -> bool:
        """安全检查: 将 GrowthAction 映射到 SafetyGovernor."""
        # 跳过低风险动作
        if action.action_type in SKIP_SAFETY_ACTIONS:
            return True

        # 获取映射的 Safety ActionType
        safety_type_str = ACTION_TYPE_TO_SAFETY_MAP.get(action.action_type)
        if safety_type_str is None:
            # 未知动作类型 — 默认通过但记录警告
            logger.warning(
                f"No safety mapping for action type: {action.action_type.value}, "
                f"allowing by default"
            )
            return True

        try:
            safety_action_type = SafetyActionType(safety_type_str)
        except ValueError:
            logger.error(f"Invalid safety action type: {safety_type_str}")
            return False

        # 构建 SafetyGovernor 参数
        params: dict[str, Any] = {}

        if action.action_type == ActionType.UPDATE_CAMPAIGN_BUDGET:
            params["current_budget"] = action.parameters.get("old_budget", 0)
            params["new_budget"] = action.parameters.get("new_budget", 0)
        elif action.action_type == ActionType.PAUSE_CAMPAIGN:
            params["roas"] = action.parameters.get("roas", 0.5)
            params["risk_level"] = action.parameters.get("risk_level", "high")
        elif action.action_type == ActionType.RESUME_CAMPAIGN:
            params["roas"] = action.parameters.get("roas", 2.0)
        elif action.action_type == ActionType.MUTATE_CREATIVE:
            params["mutation_type"] = action.parameters.get("mutation_type", "visual")

        # 调用 SafetyGovernor
        decision = governor.evaluate(
            action_type=safety_action_type,
            params=params,
            campaign_id=action.target,
            game_id=action.game_id,
        )

        if not decision.approved:
            logger.info(
                f"Safety blocked action {action.action_type.value} "
                f"on {action.target}: {decision.reason}"
            )

        return decision.approved

    return safety_check


# ═══════════════════════════════════════════════════════════════
# Audit Hook Adapter
# ═══════════════════════════════════════════════════════════════


def create_audit_hook(
    audit_service: "AuditService",
) -> Callable[[GrowthAction, AdapterExecutionResult], None]:
    """创建审计钩子函数.

    将 AdapterExecutionResult 记录到 AuditService.

    Args:
        audit_service: AuditService 实例

    Returns:
        Callable[[GrowthAction, AdapterExecutionResult], None]: 可注册到 ExecutionRouter 的审计钩子
    """
    from ..audit.models import ExecutionStatus as AuditExecutionStatus

    def audit_hook(action: GrowthAction, result: AdapterExecutionResult) -> None:
        """审计钩子: 记录执行结果到 AuditService."""
        try:
            # 映射状态 (Audit 模块的 ExecutionStatus: PENDING/EXECUTING/SUCCESS/FAILED/ROLLED_BACK/APPROVED/REJECTED)
            if result.status == AdapterResultStatus.SUCCESS:
                audit_status = AuditExecutionStatus.SUCCESS
            elif result.status == AdapterResultStatus.BLOCKED:
                audit_status = AuditExecutionStatus.REJECTED
            elif result.status == AdapterResultStatus.ROLLED_BACK:
                audit_status = AuditExecutionStatus.ROLLED_BACK
            elif result.status == AdapterResultStatus.SKIPPED:
                audit_status = AuditExecutionStatus.FAILED
            elif result.status == AdapterResultStatus.PENDING_APPROVAL:
                audit_status = AuditExecutionStatus.PENDING
            elif result.status == AdapterResultStatus.TIMED_OUT:
                audit_status = AuditExecutionStatus.FAILED
            else:
                audit_status = AuditExecutionStatus.FAILED

            # 先记录决策 (如果还没有 audit_id)
            audit_result = audit_service.log_decision(
                agent_id=action.metadata.get("agent_id", "growth_agent"),
                game_id=action.game_id,
                input_context=action.metadata.get("input_context", {}),
                detected_problem=action.metadata.get("detected_problem", ""),
                decision=action.metadata.get("decision", action.action_type.value),
                action=action.action_type.value,
                confidence=action.metadata.get("confidence", 0.8),
                safety_decision=(
                    "approved" if result.status != AdapterResultStatus.BLOCKED
                    else "blocked"
                ),
            )

            # 记录执行结果
            audit_service.log_execution_result(
                audit_id=audit_result.audit_id,
                status=audit_status,
                result=result.to_dict(),
                rollback_record_id=result.metadata.get("rollback_record_id", ""),
            )
        except Exception as e:
            logger.warning(f"Audit hook failed: {e}")

    return audit_hook


# ═══════════════════════════════════════════════════════════════
# Metrics Hook Adapter
# ═══════════════════════════════════════════════════════════════


def create_metrics_hook(
    metrics_collector: "MetricsCollector",
) -> Callable[[GrowthAction, AdapterExecutionResult], None]:
    """创建监控指标钩子函数.

    将执行结果记录到 MetricsCollector.

    Args:
        metrics_collector: MetricsCollector 实例

    Returns:
        Callable[[GrowthAction, AdapterExecutionResult], None]: 可注册到 ExecutionRouter 的监控钩子
    """

    def metrics_hook(action: GrowthAction, result: AdapterExecutionResult) -> None:
        """监控钩子: 记录执行指标."""
        try:
            is_success = result.status == AdapterResultStatus.SUCCESS
            is_rollback = result.status == AdapterResultStatus.ROLLED_BACK
            is_approval = result.status == AdapterResultStatus.PENDING_APPROVAL

            metrics_collector.record_execution(
                success=is_success,
                rollback=is_rollback,
                approval_waiting=is_approval,
            )

            # 记录业务指标 (如果结果中包含)
            if "business_metrics" in result.metadata:
                bm = result.metadata["business_metrics"]
                metrics_collector.record_business(
                    spend=bm.get("spend", 0.0),
                    revenue=bm.get("revenue", 0.0),
                    ltv=bm.get("ltv", 0.0),
                    installs=bm.get("installs", 0),
                    purchases=bm.get("purchases", 0),
                    impressions=bm.get("impressions", 0),
                    clicks=bm.get("clicks", 0),
                )
        except Exception as e:
            logger.warning(f"Metrics hook failed: {e}")

    return metrics_hook


# ═══════════════════════════════════════════════════════════════
# High-Level Wiring
# ═══════════════════════════════════════════════════════════════


def wire_execution_layer(
    router: "ExecutionRouter",  # noqa: F821
    safety: "SafetyGovernor | None" = None,
    audit: "AuditService | None" = None,
    metrics: "MetricsCollector | None" = None,
) -> None:
    """一键接入: 将 Safety / Audit / Monitoring 连接到 ExecutionRouter.

    连接后的执行链路:
      GrowthAction → Safety Governor → ExecutionRouter → Adapter → Audit + Metrics

    Args:
        router:   ExecutionRouter 实例
        safety:   SafetyGovernor 实例 (可选)
        audit:    AuditService 实例 (可选)
        metrics:  MetricsCollector 实例 (可选)

    用法:
        from growth_runtime.execution.wiring import wire_execution_layer

        wire_execution_layer(router, safety=safety, audit=audit, metrics=metrics)
        result = router.execute(action)  # 自动经过完整链路
    """
    if safety is not None:
        safety_hook = create_safety_governor_hook(safety)
        router.register_safety_governor(safety_hook)
        logger.info("Safety Governor wired to ExecutionRouter")

    if audit is not None:
        audit_hook = create_audit_hook(audit)
        router.register_audit_hook(audit_hook)
        logger.info("Audit Service wired to ExecutionRouter")

    if metrics is not None:
        metrics_hook = create_metrics_hook(metrics)
        router.register_post_hook(metrics_hook)
        logger.info("Metrics Collector wired to ExecutionRouter")


__all__ = [
    "ACTION_TYPE_TO_SAFETY_MAP",
    "SKIP_SAFETY_ACTIONS",
    "create_safety_governor_hook",
    "create_audit_hook",
    "create_metrics_hook",
    "wire_execution_layer",
]