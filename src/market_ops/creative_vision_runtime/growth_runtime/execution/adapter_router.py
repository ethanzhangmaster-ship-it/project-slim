"""E15.0.9 Execution Router — 执行路由器.

将 GrowthAction 自动路由到正确的平台适配器，是 Execution Adapter Layer
的核心调度组件。

核心流程:
    GrowthAction → ExecutionRouter → AdapterRegistry → ExecutionAdapter → AdapterExecutionResult

与 E13.7 ExecutorGateway 的关系:
  - ExecutionRouter: E15.0.9 高层路由器 (输入 GrowthAction, 输出 AdapterExecutionResult)
  - ExecutorGateway:  E13.7 底层网关 (输入 ExecutionAction, 输出 GatewayResult)
  - ExecutionRouter 内部可委托给 ExecutorGateway 完成底层执行

设计原则:
  - 自动路由: 根据 ActionType 自动选择 Adapter
  - 安全集成: 可选 Safety Governor 在执行前校验
  - 审计集成: 可选 AuditService 记录所有执行结果
  - 监控集成: 可选 MetricsCollector 记录执行指标
  - 异常隔离: 单个 Adapter 失败不影响 Router 状态
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .adapter_base import (
    AdapterExecutionResult,
    AdapterResultStatus,
    ExecutionAdapter,
)
from .adapter_registry import AdapterRegistry
from .growth_action import ActionType, GrowthAction

logger = logging.getLogger(__name__)


class ExecutionRouter:
    """E15.0.9 执行路由器 — 将 GrowthAction 路由到平台适配器.

    用法:
        router = ExecutionRouter(registry)
        router.register_safety_governor(safety.check)
        router.register_audit_hook(audit.log_execution_result)

        result = router.execute(action)
        if result.success:
            print(f"Executed: {result.external_id}")

    安全链:
        GrowthAction → SafetyGovernor → ExecutionRouter → Adapter → Result → Audit
    """

    def __init__(
        self,
        registry: AdapterRegistry | None = None,
    ):
        self._registry = registry if registry is not None else AdapterRegistry()
        self._safety_governor: Callable[[GrowthAction], bool] | None = None
        self._audit_hooks: list[Callable[[GrowthAction, AdapterExecutionResult], None]] = []
        self._pre_hooks: list[Callable[[GrowthAction], None]] = []
        self._post_hooks: list[Callable[[GrowthAction, AdapterExecutionResult], None]] = []
        self._route_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0
        self._blocked_count: int = 0

    @property
    def registry(self) -> AdapterRegistry:
        return self._registry

    # ── Hook Registration ─────────────────────────────────────

    def register_safety_governor(
        self,
        governor: Callable[[GrowthAction], bool],
    ) -> None:
        """注册安全检查函数.

        Args:
            governor: 接收 GrowthAction，返回 True 表示通过
        """
        self._safety_governor = governor

    def register_audit_hook(
        self,
        hook: Callable[[GrowthAction, AdapterExecutionResult], None],
    ) -> None:
        """注册审计钩子 — 在每次执行后调用.

        Args:
            hook: 接收 (action, result) 用于记录审计日志
        """
        self._audit_hooks.append(hook)

    def register_pre_hook(
        self,
        hook: Callable[[GrowthAction], None],
    ) -> None:
        """注册前置钩子 — 在执行前调用."""
        self._pre_hooks.append(hook)

    def register_post_hook(
        self,
        hook: Callable[[GrowthAction, AdapterExecutionResult], None],
    ) -> None:
        """注册后置钩子 — 在执行后调用."""
        self._post_hooks.append(hook)

    # ── 主执行入口 ────────────────────────────────────────────

    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        """执行 GrowthAction — 统一入口.

        流程:
          1. 前置钩子
          2. 安全检查 (Safety Governor)
          3. 查找适配器 (AdapterRegistry)
          4. 适配器校验 (Adapter.validate)
          5. 适配器执行 (Adapter.execute)
          6. 后置钩子 + 审计钩子

        Args:
            action: GrowthAction 高层动作

        Returns:
            AdapterExecutionResult: 统一执行结果
        """
        self._route_count += 1

        # 1. 前置钩子
        for hook in self._pre_hooks:
            try:
                hook(action)
            except Exception as e:
                logger.warning(f"Pre-hook failed: {e}")

        # 2. 安全检查
        if self._safety_governor is not None:
            try:
                if not self._safety_governor(action):
                    self._blocked_count += 1
                    result = AdapterExecutionResult.blocked_result(
                        action,
                        reason="Blocked by Safety Governor",
                    )
                    self._run_audit_hooks(action, result)
                    return result
            except Exception as e:
                logger.error(f"Safety governor error: {e}")
                self._blocked_count += 1
                result = AdapterExecutionResult.blocked_result(
                    action,
                    reason=f"Safety governor error: {e}",
                )
                self._run_audit_hooks(action, result)
                return result

        # 3. 查找适配器
        adapter = self._registry.get(action.action_type)
        if adapter is None:
            self._failure_count += 1
            result = AdapterExecutionResult.failure_result(
                action,
                error=f"No adapter registered for action type: {action.action_type.value}",
            )
            self._run_audit_hooks(action, result)
            return result

        # 4. 适配器校验
        try:
            if not adapter.validate(action):
                self._failure_count += 1
                result = AdapterExecutionResult.skipped_result(
                    action,
                    reason=f"Validation failed for {action.action_type.value}",
                    adapter_name=adapter.name,
                )
                self._run_audit_hooks(action, result)
                return result
        except Exception as e:
            self._failure_count += 1
            result = AdapterExecutionResult.failure_result(
                action,
                error=f"Validation error: {e}",
                adapter_name=adapter.name,
            )
            self._run_audit_hooks(action, result)
            return result

        # 5. 执行
        try:
            result = adapter.execute(action)
        except Exception as e:
            self._failure_count += 1
            logger.exception(f"Adapter execution failed: {e}")
            result = AdapterExecutionResult.failure_result(
                action,
                error=f"Execution error: {e}",
                adapter_name=adapter.name,
            )

        # 6. 统计
        if result.success:
            self._success_count += 1
        elif result.status == AdapterResultStatus.BLOCKED:
            self._blocked_count += 1
        else:
            self._failure_count += 1

        # 7. 后置钩子 + 审计钩子
        for hook in self._post_hooks:
            try:
                hook(action, result)
            except Exception as e:
                logger.warning(f"Post-hook failed: {e}")

        self._run_audit_hooks(action, result)

        return result

    # ── Rollback ──────────────────────────────────────────────

    def rollback(
        self,
        action: GrowthAction,
        result: AdapterExecutionResult,
    ) -> AdapterExecutionResult:
        """回滚动作.

        Args:
            action: 原始 GrowthAction
            result: 原始执行结果

        Returns:
            AdapterExecutionResult: 回滚结果
        """
        adapter = self._registry.get(action.action_type)
        if adapter is None:
            return AdapterExecutionResult.failure_result(
                action,
                error=f"No adapter registered for rollback: {action.action_type.value}",
            )

        try:
            rollback_result = adapter.rollback(action, result)
            self._run_audit_hooks(action, rollback_result)
            return rollback_result
        except Exception as e:
            logger.exception(f"Rollback failed: {e}")
            return AdapterExecutionResult.failure_result(
                action,
                error=f"Rollback error: {e}",
                adapter_name=adapter.name,
            )

    # ── Batch Execution ───────────────────────────────────────

    def execute_batch(
        self,
        actions: list[GrowthAction],
        stop_on_failure: bool = False,
    ) -> list[AdapterExecutionResult]:
        """批量执行动作.

        Args:
            actions:         GrowthAction 列表
            stop_on_failure: 失败时是否停止后续执行

        Returns:
            list[AdapterExecutionResult]: 执行结果列表
        """
        results: list[AdapterExecutionResult] = []
        for action in actions:
            result = self.execute(action)
            results.append(result)
            if stop_on_failure and not result.success:
                # 标记剩余动作为跳过
                for remaining in actions[len(results):]:
                    results.append(
                        AdapterExecutionResult.skipped_result(
                            remaining,
                            reason="Stopped due to previous failure",
                        )
                    )
                break
        return results

    # ── Internal ──────────────────────────────────────────────

    def _run_audit_hooks(
        self,
        action: GrowthAction,
        result: AdapterExecutionResult,
    ) -> None:
        """执行所有审计钩子."""
        for hook in self._audit_hooks:
            try:
                hook(action, result)
            except Exception as e:
                logger.warning(f"Audit hook failed: {e}")

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "route_count": self._route_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "blocked_count": self._blocked_count,
            "success_rate": round(
                self._success_count / max(self._route_count, 1), 4
            ),
            "registry": self._registry.stats(),
            "has_safety_governor": self._safety_governor is not None,
            "audit_hooks": len(self._audit_hooks),
        }

    def __repr__(self) -> str:
        return (
            f"ExecutionRouter(routes={self._route_count}, "
            f"success={self._success_count}, "
            f"adapters={len(self._registry.get_unique_adapters())})"
        )


__all__ = ["ExecutionRouter"]