"""E10.2 Phase 3 — Real Campaign Lifecycle Integration Test.

8 AC covering:
  1. Campaign Schema (Identity, Mutation, Snapshot)
  2. Campaign Registry (task_id → campaign_id)
  3. Budget Safety (30% cap, daily limit)
  4. SCALE Lifecycle (task → mutation → result)
  5. KILL Lifecycle (ACTIVE → PAUSED)
  6. Retry Engine (backoff, auth stop)
  7. Rate Limit (token bucket, block)
  8. Full Regression (E10.1 Phase1-7 + E10.2 Phase1-2)
"""

from __future__ import annotations

import time

from market_ops.execution_runtime import (
    ExecutionTask,
    ExecutionResult,
    ExecutionStatus,
    ActionType,
    ExecutionTarget,
)
from market_ops.execution_runtime.campaign_schema import (
    CampaignIdentity,
    CampaignMutation,
    CampaignSnapshot,
    CampaignStatus,
)
from market_ops.execution_runtime.campaign_registry import CampaignRegistry
from market_ops.execution_runtime.budget_guard import (
    BudgetGuard,
    BudgetGuardResult,
    BudgetGuardError,
)
from market_ops.execution_runtime.result_mapper import PlatformResultMapper
from market_ops.execution_runtime.rate_limit_controller import (
    RateLimitController,
    RateLimitStatus,
)
from market_ops.execution_runtime.adapter_retry import (
    RetryEngine,
    RetryExhaustedError,
    RetryDecision,
)
from market_ops.execution_runtime.adapters.base_adapter import AdapterResult
from market_ops.execution_runtime.adapters import (
    AdapterError,
    AdapterAuthenticationError,
    AdapterRateLimitError,
    MockPlatformAdapter,
    FacebookAdsAdapter,
    FacebookConfig,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_task(action: str = "SCALE", budget_before: float = 100.0, budget_after: float = 120.0) -> ExecutionTask:
    return ExecutionTask(
        creative_id="C001",
        action_type=action,
        budget_change={"before": budget_before, "after": budget_after},
        target_platform=ExecutionTarget.META_ADS.value,
    )


def _make_facebook_result(success: bool = True, operation: str = "update_budget") -> AdapterResult:
    return AdapterResult(
        success=success,
        platform="facebook",
        external_id="23842567890012345",
        operation=operation,
        raw_response={
            "data": {"id": "23842567890012345", "status": "ACTIVE", "daily_budget": "12000"},
            "metrics": {"impressions": 15000, "clicks": 450, "spend": 320.50, "cpm": 21.37, "cpc": 0.71, "ctr": 3.0},
        },
    )


# ═══════════════════════════════════════════════════════════
# AC1 — Campaign Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_campaign_identity():
    """AC1a: CampaignIdentity creates with correct fields."""
    identity = CampaignIdentity(
        task_id="task_001",
        campaign_id="23842567890012345",
        ad_account_id="act_123456",
        platform="facebook",
    )
    assert identity.task_id == "task_001"
    assert identity.campaign_id == "23842567890012345"
    assert identity.platform == "facebook"
    assert identity.identity_id != ""
    assert identity.created_at != ""

    data = identity.to_dict()
    assert data["task_id"] == "task_001"
    assert data["campaign_id"] == "23842567890012345"


def test_ac1_campaign_mutation():
    """AC1b: CampaignMutation records before/after delta."""
    mutation = CampaignMutation(
        campaign_id="c_001",
        task_id="t_001",
        action="SCALE",
        budget_before=100.0,
        budget_after=130.0,
        status_before=CampaignStatus.ACTIVE.value,
        status_after=CampaignStatus.ACTIVE.value,
    )
    assert mutation.budget_delta == 30.0
    assert mutation.is_scale is True
    assert mutation.is_kill is False
    assert mutation.to_dict()["budget_delta"] == 30.0


def test_ac1_campaign_snapshot():
    """AC1c: CampaignSnapshot captures post-mutation state."""
    snapshot = CampaignSnapshot(
        campaign_id="c_001",
        task_id="t_001",
        status=CampaignStatus.ACTIVE.value,
        daily_budget=130.0,
        impressions=15000,
        clicks=450,
        spend=320.50,
    )
    data = snapshot.to_dict()
    assert data["status"] == "ACTIVE"
    assert data["daily_budget"] == 130.0
    assert data["impressions"] == 15000


def test_ac1_campaign_status_enum():
    """AC1d: CampaignStatus enum has correct values."""
    assert CampaignStatus.UNKNOWN.value == "UNKNOWN"
    assert CampaignStatus.ACTIVE.value == "ACTIVE"
    assert CampaignStatus.PAUSED.value == "PAUSED"
    assert CampaignStatus.DELETED.value == "DELETED"


# ═══════════════════════════════════════════════════════════
# AC2 — Campaign Registry
# ═══════════════════════════════════════════════════════════

def test_ac2_registry_register_and_get():
    """AC2a: CampaignRegistry maps task_id → campaign_id."""
    registry = CampaignRegistry()
    identity = CampaignIdentity(task_id="t_001", campaign_id="23842567890012345", platform="facebook")
    registry.register("t_001", identity)

    assert registry.has_task("t_001") is True
    assert registry.has_campaign("23842567890012345") is True
    assert registry.identity_count == 1

    found = registry.get_campaign("t_001")
    assert found is not None
    assert found.campaign_id == "23842567890012345"

    by_campaign = registry.get_by_campaign_id("23842567890012345")
    assert by_campaign is not None
    assert by_campaign.task_id == "t_001"


def test_ac2_registry_mutations_and_snapshots():
    """AC2b: Registry tracks mutations and snapshots."""
    registry = CampaignRegistry()
    registry.register("t_001", CampaignIdentity(task_id="t_001", campaign_id="c_001"))

    mutation = CampaignMutation(campaign_id="c_001", task_id="t_001", action="SCALE", budget_before=100.0, budget_after=130.0)
    registry.record_mutation(mutation)

    snapshot = CampaignSnapshot(campaign_id="c_001", task_id="t_001", status="ACTIVE")
    registry.record_snapshot(snapshot)

    assert registry.mutation_count == 1
    assert registry.snapshot_count == 1
    assert len(registry.get_mutations("t_001")) == 1
    assert len(registry.get_snapshots("t_001")) == 1


def test_ac2_registry_list_campaigns():
    """AC2c: Registry can list all tracked IDs."""
    registry = CampaignRegistry()
    registry.register("t_001", CampaignIdentity(task_id="t_001", campaign_id="c_001"))
    registry.register("t_002", CampaignIdentity(task_id="t_002", campaign_id="c_002"))

    assert set(registry.list_campaign_ids()) == {"c_001", "c_002"}
    assert set(registry.list_task_ids()) == {"t_001", "t_002"}


# ═══════════════════════════════════════════════════════════
# AC3 — Budget Safety
# ═══════════════════════════════════════════════════════════

def test_ac3_budget_allow_safe_scale():
    """AC3a: BudgetGuard allows 100→120 (20% within 30% limit)."""
    guard = BudgetGuard(max_scale_ratio=0.30)
    result = guard.check(100.0, 120.0)
    assert result.allowed is True
    assert result.max_allowed == 120.0


def test_ac3_budget_reject_aggressive_scale():
    """AC3b: BudgetGuard rejects 100→500 (400% exceeds 30% limit)."""
    guard = BudgetGuard(max_scale_ratio=0.30)
    result = guard.check(100.0, 500.0)
    assert result.allowed is False
    assert "30%" in result.reason
    assert result.max_allowed == 130.0
    assert result.capped_budget == 130.0


def test_ac3_budget_daily_cap():
    """AC3c: BudgetGuard rejects when daily cap is exceeded."""
    guard = BudgetGuard(daily_cap=1000.0, max_scale_ratio=1.0)  # Higher ratio to test cap, not scale
    result = guard.check(100.0, 200.0, current_spend=900.0)
    assert result.allowed is False
    assert "Daily cap exceeded" in result.reason
    assert result.capped_budget == 100.0  # 100 remaining


def test_ac3_budget_minimum_floor():
    """AC3d: BudgetGuard rejects budget below minimum."""
    guard = BudgetGuard(min_budget=5.0)
    result = guard.check(10.0, 3.0)
    assert result.allowed is False
    assert "below minimum" in result.reason.lower()


def test_ac3_budget_get_safe_budget():
    """AC3e: get_safe_budget returns capped value for unsafe changes."""
    guard = BudgetGuard(max_scale_ratio=0.30)
    safe = guard.get_safe_budget(100.0, 500.0)
    assert safe == 130.0

    safe2 = guard.get_safe_budget(100.0, 120.0)
    assert safe2 == 120.0


def test_ac3_budget_guard_error():
    """AC3f: BudgetGuardError wraps BudgetGuardResult."""
    guard = BudgetGuard(max_scale_ratio=0.30)
    result = guard.check(100.0, 500.0)
    error = BudgetGuardError(result)
    assert error.result is result
    assert "30%" in str(error)


# ═══════════════════════════════════════════════════════════
# AC4 — SCALE Lifecycle
# ═══════════════════════════════════════════════════════════

def test_ac4_scale_full_lifecycle():
    """AC4: SCALE → Adapter → Mutation → Result."""
    task = _make_task("SCALE", 100.0, 130.0)
    adapter = MockPlatformAdapter(failure_rate=0.0)
    adapter_result = adapter.update_budget("camp_C001", 130.0)

    mapper = PlatformResultMapper()
    mutation = mapper.to_mutation(task, adapter_result)
    result = mapper.to_execution_result(task, adapter_result)
    snapshot = mapper.to_snapshot(task, adapter_result)

    # Mutation
    assert mutation.action == "SCALE"
    assert mutation.budget_before == 100.0
    assert mutation.budget_after == 130.0
    assert mutation.budget_delta == 30.0
    assert mutation.success is True

    # Result
    assert result.status == ExecutionStatus.COMPLETED.value
    assert result.platform_response["operation"] == "update_budget"

    # Snapshot
    assert snapshot.daily_budget == 130.0


# ═══════════════════════════════════════════════════════════
# AC5 — KILL Lifecycle
# ═══════════════════════════════════════════════════════════

def test_ac5_kill_full_lifecycle():
    """AC5: KILL → ACTIVE → PAUSED."""
    task = _make_task("KILL", 100.0, 0.0)
    adapter = MockPlatformAdapter(failure_rate=0.0)
    adapter_result = adapter.pause_campaign("camp_C001")

    mapper = PlatformResultMapper()
    mutation = mapper.to_mutation(task, adapter_result)
    result = mapper.to_execution_result(task, adapter_result)

    assert mutation.action == "KILL"
    assert mutation.status_before == CampaignStatus.ACTIVE.value
    assert mutation.status_after == CampaignStatus.PAUSED.value
    assert mutation.success is True

    assert result.status == ExecutionStatus.COMPLETED.value
    assert mutation.status_after == CampaignStatus.PAUSED.value


# ═══════════════════════════════════════════════════════════
# AC6 — Retry Engine
# ═══════════════════════════════════════════════════════════

def test_ac6_retry_success_on_first_attempt():
    """AC6a: RetryEngine succeeds on first attempt."""
    engine = RetryEngine(max_retries=3)
    call_count = [0]

    def fn():
        call_count[0] += 1
        return "ok"

    result = engine.execute(fn)
    assert result == "ok"
    assert call_count[0] == 1


def test_ac6_retry_with_timeout_then_success():
    """AC6b: RetryEngine retries on transient error then succeeds."""
    engine = RetryEngine(max_retries=3, base_delay=0.01)
    call_count = [0]

    def fn():
        call_count[0] += 1
        if call_count[0] < 3:
            raise AdapterError("timeout error", platform="test")
        return "success"

    start = time.time()
    result = engine.execute(fn)
    elapsed = time.time() - start

    assert result == "success"
    assert call_count[0] == 3
    assert elapsed < 2.0  # Very short delays


def test_ac6_retry_auth_stops_immediately():
    """AC6c: Auth errors are terminal — no retry."""
    engine = RetryEngine(max_retries=3)
    call_count = [0]

    def fn():
        call_count[0] += 1
        raise AdapterAuthenticationError("test", "Invalid token")

    try:
        engine.execute(fn)
        assert False, "Should have raised"
    except AdapterAuthenticationError:
        pass

    assert call_count[0] == 1  # Only called once


def test_ac6_retry_rate_limit_backoff():
    """AC6d: Rate limit errors retry with platform-specified delay."""
    engine = RetryEngine(max_retries=2, base_delay=0.01)
    call_count = [0]

    def fn():
        call_count[0] += 1
        if call_count[0] < 2:
            raise AdapterRateLimitError("test", retry_after=1)
        return "ok"

    result = engine.execute(fn)
    assert result == "ok"
    assert call_count[0] == 2


def test_ac6_retry_exhausted():
    """AC6e: RetryExhaustedError after all retries fail."""
    engine = RetryEngine(max_retries=2, base_delay=0.01)

    def fn():
        raise AdapterError("persistent failure", platform="test")

    try:
        engine.execute(fn)
        assert False, "Should have raised RetryExhaustedError"
    except RetryExhaustedError as exc:
        assert exc.attempts == 2
        assert "persistent failure" in str(exc)


def test_ac6_retry_backoff_sequence():
    """AC6f: Backoff follows 1s → 2s → 4s pattern."""
    engine = RetryEngine(max_retries=3, base_delay=1.0, backoff_factor=2.0)
    # 1 * 2^0 = 1, 1 * 2^1 = 2, 1 * 2^2 = 4
    assert engine._calc_backoff(0) == 1.0
    assert engine._calc_backoff(1) == 2.0
    assert engine._calc_backoff(2) == 4.0

    # Max delay cap
    engine2 = RetryEngine(max_retries=3, base_delay=1.0, max_delay=3.0, backoff_factor=10.0)
    assert engine2._calc_backoff(2) == 3.0  # Capped at max_delay


# ═══════════════════════════════════════════════════════════
# AC7 — Rate Limit
# ═══════════════════════════════════════════════════════════

def test_ac7_rate_limit_allow_under_capacity():
    """AC7a: RateLimitController allows requests within capacity."""
    controller = RateLimitController(capacity=10, refill_rate=100.0)
    for _ in range(10):
        assert controller.allow() is True
    assert controller.allow() is False  # 11th blocked
    assert controller.total_allowed == 10
    assert controller.total_blocked == 1


def test_ac7_rate_limit_refill():
    """AC7b: Tokens refill over time."""
    controller = RateLimitController(capacity=5, refill_rate=100.0)
    # Drain all tokens
    for _ in range(5):
        controller.allow()
    assert controller.allow() is False

    # Wait for refill
    time.sleep(0.05)
    assert controller.allow() is True  # Token refilled


def test_ac7_rate_limit_status():
    """AC7c: RateLimitStatus reports current state."""
    controller = RateLimitController(capacity=10, refill_rate=100.0)
    status = controller.status
    assert status.capacity == 10.0
    assert status.available == 10.0
    assert status.blocked is False

    # Drain
    for _ in range(10):
        controller.allow()
    status2 = controller.status
    assert status2.blocked is True


def test_ac7_rate_limit_wait_for_quota():
    """AC7d: wait_for_quota blocks until token available."""
    controller = RateLimitController(capacity=3, refill_rate=100.0)
    # Drain
    for _ in range(3):
        controller.allow()
    assert controller.allow() is False

    success = controller.wait_for_quota(timeout=1.0)
    assert success is True


def test_ac7_rate_limit_reset():
    """AC7e: Reset restores full capacity."""
    controller = RateLimitController(capacity=10, refill_rate=100.0)
    for _ in range(10):
        controller.allow()
    assert controller.available_tokens < 10.0

    controller.reset()
    assert controller.available_tokens == 10.0
    assert controller.total_allowed == 0
    assert controller.total_blocked == 0


# ═══════════════════════════════════════════════════════════
# AC8 — Full Regression
# ═══════════════════════════════════════════════════════════

def test_ac8_e101_runtime_api():
    """AC8a: E10.1 RuntimeAPI still works."""
    from market_ops.execution_runtime import RuntimeAPI

    api = RuntimeAPI()
    resp = api.create_execution({
        "creative_id": "C001",
        "action": "SCALE",
        "budget_change": {"current": 100.0, "target": 200.0},
        "confidence": 0.95,
        "reason": ["WINNER"],
    })
    assert resp.success is True


def test_ac8_e102_phase1_all_imports():
    """AC8b: E10.2 Phase 1 imports still work."""
    from market_ops.execution_runtime.adapters import (
        PlatformAdapter, AdapterResult, AdapterRegistry,
        MockPlatformAdapter, AdapterError,
    )
    assert PlatformAdapter is not None
    assert AdapterResult is not None


def test_ac8_e102_phase2_facebook_adapter():
    """AC8c: Facebook adapter still works in sandbox."""
    config = FacebookConfig(sandbox=True)
    adapter = FacebookAdsAdapter(config=config)
    result = adapter.update_budget("c_001", 200.0)
    assert result.success is True
    assert result.platform == "facebook"


def test_ac8_full_cycle_with_registry():
    """AC8d: Full lifecycle with registry integration."""
    task = _make_task("SCALE", 100.0, 130.0)
    adapter = MockPlatformAdapter()
    adapter_result = adapter.update_budget("camp_C001", 130.0)

    mapper = PlatformResultMapper()
    registry = CampaignRegistry()

    identity = mapper.to_identity(task, adapter_result, ad_account_id="act_123")
    registry.register(task.task_id, identity)

    mutation = mapper.to_mutation(task, adapter_result)
    registry.record_mutation(mutation)

    snapshot = mapper.to_snapshot(task, adapter_result)
    registry.record_snapshot(snapshot)

    assert registry.has_task(task.task_id)
    assert registry.mutation_count == 1
    assert registry.snapshot_count == 1


def test_ac8_budget_guard_integration():
    """AC8e: BudgetGuard integration with Facebook adapter."""
    guard = BudgetGuard(max_scale_ratio=0.30)
    task = _make_task("SCALE", 100.0, 500.0)

    # Check before executing
    result = guard.check(
        task.budget_change.get("before", 0.0),
        task.budget_change.get("after", 0.0),
    )
    assert result.allowed is False  # Blocked

    # Use safe budget
    safe_budget = guard.get_safe_budget(
        task.budget_change.get("before", 0.0),
        task.budget_change.get("after", 0.0),
    )
    assert safe_budget == 130.0

    # Execute with safe budget
    adapter = MockPlatformAdapter()
    adapter_result = adapter.update_budget("camp_C001", safe_budget)
    assert adapter_result.success is True
    assert adapter_result.raw_response["budget_applied"] == 130.0