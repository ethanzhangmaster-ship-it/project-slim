"""E10.2 Mock Platform Adapter — Implements PlatformAdapter for testing.

Moved from E10.1 mock_adapter.py and retrofitted to implement
PlatformAdapter ABC. Preserves all original behavior:
  - Configurable failure_rate for chaos testing
  - No real platform API calls
  - Deterministic mock responses

Usage:
    from market_ops.execution_runtime.adapters import MockPlatformAdapter
    adapter = MockPlatformAdapter()
    result = adapter.update_budget("camp_001", 200.0)
"""

from __future__ import annotations

import random
import uuid
from typing import Any

from market_ops.execution_runtime.adapters.base_adapter import PlatformAdapter, AdapterResult
from market_ops.execution_runtime.adapters.exceptions import AdapterError


class MockPlatformAdapter(PlatformAdapter):
    """Mock adapter implementing PlatformAdapter for CI and local development.

    Args:
        failure_rate: Probability of simulated failure (0.0-1.0).
    """

    def __init__(self, failure_rate: float = 0.0) -> None:
        self._failure_rate = max(0.0, min(1.0, failure_rate))
        self._call_count = 0

    # ───────────────────────────────────────────────────────
    # PlatformAdapter interface
    # ───────────────────────────────────────────────────────

    @property
    def platform_name(self) -> str:
        return "mock"

    def create_campaign(self, config: dict[str, Any]) -> AdapterResult:
        """Maps to RETEST: create a new campaign with reduced budget."""
        self._call_count += 1
        self._maybe_fail("create_campaign")

        budget = config.get("budget", 50.0)
        return AdapterResult(
            success=True,
            platform=self.platform_name,
            external_id=f"mock_camp_{uuid.uuid4().hex[:8]}",
            operation="create_campaign",
            raw_response={
                "budget_applied": budget,
                "retest_mode": True,
                "execution_time_ms": random.randint(100, 300),
            },
        )

    def update_budget(self, campaign_id: str, amount: float) -> AdapterResult:
        """Maps to SCALE: increase campaign budget."""
        self._call_count += 1
        self._maybe_fail("update_budget")

        return AdapterResult(
            success=True,
            platform=self.platform_name,
            external_id=campaign_id,
            operation="update_budget",
            raw_response={
                "budget_applied": amount,
                "daily_budget": amount,
                "execution_time_ms": random.randint(100, 500),
            },
        )

    def pause_campaign(self, campaign_id: str) -> AdapterResult:
        """Maps to KILL: pause/disable a campaign."""
        self._call_count += 1
        self._maybe_fail("pause_campaign")

        return AdapterResult(
            success=True,
            platform=self.platform_name,
            external_id=campaign_id,
            operation="pause_campaign",
            raw_response={
                "status": "PAUSED",
                "effective_status": "DISABLED",
                "execution_time_ms": random.randint(50, 200),
            },
        )

    def get_metrics(
        self,
        campaign_id: str,
        date_range: dict[str, str] | None = None,
    ) -> AdapterResult:
        """Maps to WATCH: retrieve campaign metrics."""
        self._call_count += 1
        self._maybe_fail("get_metrics")

        return AdapterResult(
            success=True,
            platform=self.platform_name,
            external_id=campaign_id,
            operation="get_metrics",
            raw_response={
                "metrics": {
                    "impressions": random.randint(1000, 50000),
                    "clicks": random.randint(50, 2000),
                    "spend": round(random.uniform(50.0, 500.0), 2),
                    "revenue": round(random.uniform(80.0, 800.0), 2),
                    "roas": round(random.uniform(0.5, 2.5), 2),
                },
                "monitoring": True,
            },
        )

    # ───────────────────────────────────────────────────────
    # Legacy E10.1 compatibility API
    # ───────────────────────────────────────────────────────

    def execute(self, task: Any) -> Any:
        """Legacy E10.1 entry point — routes to new AdapterResult API.

        This method is retained so existing E10.1 tests continue to work
        without modification. Internally it delegates to the new interface.
        """
        from market_ops.execution_runtime.schemas import (
            ExecutionTask, ExecutionResult, ExecutionStatus, ActionType,
        )

        if not isinstance(task, ExecutionTask):
            raise TypeError("Expected ExecutionTask")

        action = task.action_type
        campaign_id = f"camp_{task.creative_id}"

        try:
            if action == ActionType.SCALE.value:
                result = self.update_budget(campaign_id, task.budget_change.get("after", 0.0))
            elif action == ActionType.KILL.value:
                result = self.pause_campaign(campaign_id)
            elif action == ActionType.WATCH.value:
                result = self.get_metrics(campaign_id)
            elif action == ActionType.RETEST.value:
                result = self.create_campaign({"budget": task.budget_change.get("after", 0.0)})
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
            )

        # Convert AdapterResult back to ExecutionResult for E10.1 compatibility
        return ExecutionResult(
            task_id=task.task_id,
            status=ExecutionStatus.COMPLETED.value if result.success else ExecutionStatus.FAILED.value,
            platform_response=result.raw_response,
            actual_change=task.budget_change,
            error_message=result.error_message or "",
        )

    def verify(self, task: Any) -> Any:
        """Legacy E10.1 verify — always succeeds."""
        from market_ops.execution_runtime.schemas import ExecutionResult, ExecutionStatus
        return ExecutionResult(
            task_id=task.task_id,
            status=ExecutionStatus.COMPLETED.value,
            platform_response={"verified": True, "platform": self.platform_name},
            actual_change=task.budget_change,
        )

    def rollback(self, task: Any) -> Any:
        """Legacy E10.1 rollback — restores original budget."""
        from market_ops.execution_runtime.schemas import ExecutionResult, ExecutionStatus
        budget_before = task.budget_change.get("before", 0.0)
        return ExecutionResult(
            task_id=task.task_id,
            status=ExecutionStatus.ROLLED_BACK.value,
            platform_response={"rolled_back": True, "platform": self.platform_name},
            actual_change={"before": budget_before, "after": budget_before},
        )

    # ───────────────────────────────────────────────────────
    # Helpers
    # ───────────────────────────────────────────────────────

    def _maybe_fail(self, operation: str) -> None:
        if random.random() < self._failure_rate:
            raise AdapterError(
                f"Mock adapter: simulated random failure in {operation}",
                platform=self.platform_name,
            )

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def failure_rate(self) -> float:
        return self._failure_rate
