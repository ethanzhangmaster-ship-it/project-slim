"""E10.2 Adapter Executor — Bridge between ExecutionEngine and PlatformAdapter.

Translates ExecutionTask into PlatformAdapter calls and converts
AdapterResult back into ExecutionResult. ExecutionEngine remains
frozen; this module provides the integration point for E10.2.

Usage:
    registry = AdapterRegistry()
    registry.register("mock_platform", MockPlatformAdapter())
    executor = AdapterExecutor(registry)
    result = executor.run(task)
"""

from __future__ import annotations

from typing import Any

from market_ops.execution_runtime.schemas import (
    ExecutionTask, ExecutionResult, ExecutionStatus, ActionType,
)
from market_ops.execution_runtime.adapters.base_adapter import AdapterResult
from market_ops.execution_runtime.adapters.adapter_registry import AdapterRegistry
from market_ops.execution_runtime.adapters.exceptions import AdapterError


class AdapterExecutor:
    """Executes ExecutionTasks via registered PlatformAdapters.

    This is the bridge layer introduced in E10.2. It maps E10.1
    ActionTypes to PlatformAdapter methods without modifying
    ExecutionEngine internals.
    """

    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self.registry = registry or AdapterRegistry()

    def run(self, task: ExecutionTask) -> ExecutionResult:
        """Execute a task through the adapter layer.

        Args:
            task: The ExecutionTask to run.

        Returns:
            ExecutionResult compatible with E10.1 contracts.
        """
        platform = task.target_platform or "mock"
        adapter = self.registry.get(platform)

        action = task.action_type
        campaign_id = f"camp_{task.creative_id}"

        try:
            if action == ActionType.SCALE.value:
                adapter_result = adapter.update_budget(
                    campaign_id, task.budget_change.get("after", 0.0)
                )
            elif action == ActionType.KILL.value:
                adapter_result = adapter.pause_campaign(campaign_id)
            elif action == ActionType.WATCH.value:
                adapter_result = adapter.get_metrics(campaign_id)
            elif action == ActionType.RETEST.value:
                adapter_result = adapter.create_campaign(
                    {"budget": task.budget_change.get("after", 0.0)}
                )
            else:
                return ExecutionResult(
                    task_id=task.task_id,
                    status=ExecutionStatus.FAILED.value,
                    error_message=f"Unknown action type: {action}",
                )
        except AdapterError as exc:
            return ExecutionResult(
                task_id=task.task_id,
                status=ExecutionStatus.FAILED.value,
                error_message=str(exc),
                platform_response=exc.raw_response,
            )

        return self._to_execution_result(task, adapter_result)

    def verify(self, task: ExecutionTask) -> ExecutionResult:
        """Verify a task execution via the adapter layer.

        Args:
            task: The ExecutionTask to verify.

        Returns:
            ExecutionResult with verification status.
        """
        platform = task.target_platform or "mock"
        try:
            adapter = self.registry.get(platform)
            adapter_result = adapter.get_metrics(f"camp_{task.creative_id}")
            return ExecutionResult(
                task_id=task.task_id,
                status=ExecutionStatus.COMPLETED.value,
                platform_response={"verified": adapter_result.success, "platform": platform},
                actual_change=task.budget_change,
            )
        except AdapterError as exc:
            return ExecutionResult(
                task_id=task.task_id,
                status=ExecutionStatus.FAILED.value,
                error_message=str(exc),
            )

    def rollback(self, task: ExecutionTask) -> ExecutionResult:
        """Rollback a task via the adapter layer.

        Args:
            task: The ExecutionTask to rollback.

        Returns:
            ExecutionResult with rollback status.
        """
        platform = task.target_platform or "mock"
        try:
            adapter = self.registry.get(platform)
            campaign_id = f"camp_{task.creative_id}"
            budget_before = task.budget_change.get("before", 0.0)

            adapter_result = adapter.update_budget(campaign_id, budget_before)
            return ExecutionResult(
                task_id=task.task_id,
                status=ExecutionStatus.ROLLED_BACK.value,
                platform_response={
                    "rolled_back": adapter_result.success,
                    "platform": platform,
                    "restored_budget": budget_before,
                },
                actual_change={"before": budget_before, "after": budget_before},
            )
        except AdapterError as exc:
            return ExecutionResult(
                task_id=task.task_id,
                status=ExecutionStatus.FAILED.value,
                error_message=str(exc),
            )

    @staticmethod
    def _to_execution_result(task: ExecutionTask, adapter_result: AdapterResult) -> ExecutionResult:
        """Convert AdapterResult to ExecutionResult."""
        status = ExecutionStatus.COMPLETED.value if adapter_result.success else ExecutionStatus.FAILED.value
        return ExecutionResult(
            task_id=task.task_id,
            status=status,
            platform_response=adapter_result.raw_response,
            actual_change=task.budget_change,
            error_message=adapter_result.error_message or "",
            metrics={
                "platform": adapter_result.platform,
                "operation": adapter_result.operation,
                "external_id": adapter_result.external_id,
            },
        )
