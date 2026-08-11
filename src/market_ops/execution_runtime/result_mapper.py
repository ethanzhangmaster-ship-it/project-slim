"""E10.2 Phase 3 — Platform Result Mapper.

Maps platform adapter responses (AdapterResult) back into E10.1
ExecutionResult objects with proper campaign lifecycle data.

Flow:
    Platform API Response
        │
        ▼
    AdapterResult
        │
        ▼
    PlatformResultMapper
        │
        ├── ExecutionResult
        ├── CampaignMutation
        └── CampaignSnapshot
"""

from __future__ import annotations

from typing import Any

from market_ops.execution_runtime.schemas import (
    ExecutionTask,
    ExecutionResult,
    ExecutionStatus,
    ActionType,
)
from market_ops.execution_runtime.adapters.base_adapter import AdapterResult
from market_ops.execution_runtime.campaign_schema import (
    CampaignIdentity,
    CampaignMutation,
    CampaignSnapshot,
    CampaignStatus,
)


class PlatformResultMapper:
    """Maps platform adapter responses to E10.1 domain objects.

    Stateless mapper. Thread-safe.

    Usage:
        mapper = PlatformResultMapper()
        result = mapper.to_execution_result(task, adapter_result)
        mutation = mapper.to_mutation(task, adapter_result)
        snapshot = mapper.to_snapshot(task, adapter_result)
    """

    def to_execution_result(self, task: ExecutionTask, adapter_result: AdapterResult) -> ExecutionResult:
        """Convert AdapterResult to ExecutionResult.

        Maps platform-specific response fields into the standard
        E10.1 ExecutionResult format.

        Args:
            task: The original ExecutionTask.
            adapter_result: Result from platform adapter.

        Returns:
            ExecutionResult with platform response data.
        """
        raw = adapter_result.raw_response
        data = raw.get("data", {})

        status = ExecutionStatus.COMPLETED.value if adapter_result.success else ExecutionStatus.FAILED.value

        return ExecutionResult(
            task_id=task.task_id,
            status=status,
            platform_response={
                "platform": adapter_result.platform,
                "operation": adapter_result.operation,
                "external_id": adapter_result.external_id,
                "campaign_status": data.get("status", "UNKNOWN"),
                "daily_budget_cents": data.get("daily_budget", "0"),
                **raw.get("metrics", {}),
            },
            actual_change=task.budget_change,
            error_message=adapter_result.error_message or "",
            metrics={
                "platform": adapter_result.platform,
                "operation": adapter_result.operation,
                "external_id": adapter_result.external_id,
            },
        )

    def to_mutation(self, task: ExecutionTask, adapter_result: AdapterResult) -> CampaignMutation:
        """Create a CampaignMutation from adapter result.

        Captures the before/after delta for audit trail.

        Args:
            task: The original ExecutionTask.
            adapter_result: Result from platform adapter.

        Returns:
            CampaignMutation recording the change.
        """
        raw = adapter_result.raw_response

        action = task.action_type
        budget_before = task.budget_change.get("before", 0.0)
        budget_after = task.budget_change.get("after", 0.0)

        if action == ActionType.KILL.value:
            status_before = CampaignStatus.ACTIVE.value
            status_after = CampaignStatus.PAUSED.value
        elif action == ActionType.RETEST.value:
            status_before = CampaignStatus.UNKNOWN.value
            status_after = CampaignStatus.PAUSED.value  # New copies start paused
        else:
            status_before = CampaignStatus.ACTIVE.value
            status_after = CampaignStatus.ACTIVE.value

        return CampaignMutation(
            campaign_id=adapter_result.external_id,
            task_id=task.task_id,
            action=action,
            platform=adapter_result.platform,
            budget_before=budget_before,
            budget_after=budget_after,
            status_before=status_before,
            status_after=status_after,
            success=adapter_result.success,
            error_message=adapter_result.error_message or "",
            raw_response=raw,
        )

    def to_snapshot(self, task: ExecutionTask, adapter_result: AdapterResult) -> CampaignSnapshot:
        """Create a CampaignSnapshot from adapter result.

        Captures the post-mutation campaign state for performance tracking.

        Args:
            task: The original ExecutionTask.
            adapter_result: Result from platform adapter.

        Returns:
            CampaignSnapshot with current campaign state.
        """
        raw = adapter_result.raw_response
        data = raw.get("data", {})
        metrics = raw.get("metrics", {})

        return CampaignSnapshot(
            campaign_id=adapter_result.external_id,
            task_id=task.task_id,
            platform=adapter_result.platform,
            status=data.get("status", data.get("campaign_status", CampaignStatus.UNKNOWN.value)),
            daily_budget=task.budget_change.get("after", 0.0),
            impressions=metrics.get("impressions", 0),
            clicks=metrics.get("clicks", 0),
            spend=metrics.get("spend", 0.0),
            cpm=metrics.get("cpm", 0.0),
            cpc=metrics.get("cpc", 0.0),
            ctr=metrics.get("ctr", 0.0),
        )

    def to_identity(self, task: ExecutionTask, adapter_result: AdapterResult, ad_account_id: str = "") -> CampaignIdentity:
        """Create a CampaignIdentity from adapter result.

        Args:
            task: The original ExecutionTask.
            adapter_result: Result from platform adapter.
            ad_account_id: Platform ad account ID.

        Returns:
            CampaignIdentity linking task to platform campaign.
        """
        return CampaignIdentity(
            task_id=task.task_id,
            campaign_id=adapter_result.external_id,
            ad_account_id=ad_account_id,
            platform=adapter_result.platform,
        )