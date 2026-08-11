"""E10.2 Phase 1 — Platform Adapter Architecture Acceptance Test.

8 AC covering:
  1. PlatformAdapter interface exists
  2. MockAdapter implements interface
  3. AdapterRegistry register/get
  4. Action mapping (SCALE/KILL/WATCH/RETEST)
  5. AdapterResult serialization
  6. Architecture isolation (no platform SDK imports)
  7. Performance (10,000 calls < 5s)
  8. E10.1 regression (Phase 1-7)
"""

from __future__ import annotations

import time

from market_ops.execution_runtime import (
    ExecutionTask,
    ExecutionStatus,
    ActionType,
)
from market_ops.execution_runtime.adapters import (
    PlatformAdapter,
    AdapterResult,
    AdapterRegistry,
    AdapterError,
    AdapterNotFoundError,
    AdapterAuthenticationError,
    MockPlatformAdapter,
)
from market_ops.execution_runtime.adapter_executor import AdapterExecutor


# ═══════════════════════════════════════════════════════════
# AC1 — Interface exists
# ═══════════════════════════════════════════════════════════

def test_ac1_interface_exists():
    """AC1: PlatformAdapter ABC and AdapterResult dataclass exist."""
    assert PlatformAdapter is not None
    result = AdapterResult(
        success=True,
        platform="test",
        external_id="ext_001",
        operation="update_budget",
    )
    assert result.success is True
    assert result.platform == "test"
    assert result.external_id == "ext_001"


# ═══════════════════════════════════════════════════════════
# AC2 — MockAdapter implements PlatformAdapter
# ═══════════════════════════════════════════════════════════

def test_ac2_mock_implements_interface():
    """AC2: MockPlatformAdapter implements PlatformAdapter ABC."""
    adapter = MockPlatformAdapter()
    assert isinstance(adapter, PlatformAdapter)
    assert hasattr(adapter, "platform_name")
    assert adapter.platform_name == "mock"

    assert callable(adapter.create_campaign)
    assert callable(adapter.update_budget)
    assert callable(adapter.pause_campaign)
    assert callable(adapter.get_metrics)


# ═══════════════════════════════════════════════════════════
# AC3 — Registry
# ═══════════════════════════════════════════════════════════

def test_ac3_registry_register_get():
    """AC3: AdapterRegistry.register() and get() work correctly."""
    registry = AdapterRegistry()
    adapter = MockPlatformAdapter()

    registry.register("facebook", adapter)
    assert registry.has_adapter("facebook") is True
    assert registry.count == 1

    retrieved = registry.get("facebook")
    assert retrieved is adapter

    retrieved_lower = registry.get("FACEBOOK")
    assert retrieved_lower is adapter

    platforms = registry.list_platforms()
    assert "facebook" in platforms


def test_ac3_registry_not_found():
    """AC3b: Registry raises AdapterNotFoundError for unknown platform."""
    registry = AdapterRegistry()
    try:
        registry.get("unknown")
        assert False, "Should have raised AdapterNotFoundError"
    except AdapterNotFoundError as exc:
        assert "unknown" in str(exc)


def test_ac3_registry_unregister():
    """AC3c: Registry can unregister a platform."""
    registry = AdapterRegistry()
    registry.register("tiktok", MockPlatformAdapter())
    assert registry.has_adapter("tiktok") is True

    registry.unregister("tiktok")
    assert registry.has_adapter("tiktok") is False


# ═══════════════════════════════════════════════════════════
# AC4 — Action mapping
# ═══════════════════════════════════════════════════════════

def test_ac4_action_mapping():
    """AC4: SCALE→update_budget, KILL→pause_campaign, WATCH→get_metrics, RETEST→create_campaign."""
    adapter = MockPlatformAdapter(failure_rate=0.0)

    result_scale = adapter.update_budget("camp_001", 200.0)
    assert result_scale.success is True
    assert result_scale.operation == "update_budget"
    assert result_scale.raw_response.get("budget_applied") == 200.0

    result_kill = adapter.pause_campaign("camp_001")
    assert result_kill.success is True
    assert result_kill.operation == "pause_campaign"
    assert result_kill.raw_response.get("effective_status") == "DISABLED"

    result_watch = adapter.get_metrics("camp_001")
    assert result_watch.success is True
    assert result_watch.operation == "get_metrics"
    assert "metrics" in result_watch.raw_response

    result_retest = adapter.create_campaign({"budget": 50.0})
    assert result_retest.success is True
    assert result_retest.operation == "create_campaign"
    assert result_retest.raw_response.get("retest_mode") is True


# ═══════════════════════════════════════════════════════════
# AC5 — AdapterResult serialization
# ═══════════════════════════════════════════════════════════

def test_ac5_result_serialization():
    """AC5: AdapterResult.to_dict() produces correct JSON structure."""
    result = AdapterResult(
        success=True,
        platform="facebook",
        external_id="act_123_campaign_001",
        operation="budget_update",
        raw_response={"daily_budget": 200.0},
        error_message=None,
    )

    data = result.to_dict()
    assert data["success"] is True
    assert data["platform"] == "facebook"
    assert data["external_id"] == "act_123_campaign_001"
    assert data["operation"] == "budget_update"
    assert data["raw_response"]["daily_budget"] == 200.0
    assert data["error_message"] is None
    assert "timestamp" in data


# ═══════════════════════════════════════════════════════════
# AC6 — Architecture isolation
# ═══════════════════════════════════════════════════════════

def test_ac6_no_platform_sdks():
    """AC6: base_adapter.py must NOT import real platform SDKs.

    Uses AST parsing to check actual import statements,
    ignoring all docstrings and comments.
    """
    import ast
    import market_ops.execution_runtime.adapters.base_adapter as ba_module
    import market_ops.execution_runtime.adapters.adapter_registry as ar_module

    forbidden_modules = ["facebook", "google", "tiktok", "applovin", "adjust", "appsflyer"]

    for mod in [ba_module, ar_module]:
        source = mod.__file__ or ""
        code = open(source, encoding="utf-8").read()
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.lower()
                    for kw in forbidden_modules:
                        assert kw not in name, f"Forbidden import '{kw}' in {mod.__name__}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_name = node.module.lower()
                    for kw in forbidden_modules:
                        assert kw not in mod_name, f"Forbidden import '{kw}' in {mod.__name__}"


def test_ac6_exceptions_are_defined():
    """AC6b: All adapter exceptions are importable."""
    assert issubclass(AdapterError, Exception)
    assert issubclass(AdapterNotFoundError, AdapterError)
    assert issubclass(AdapterAuthenticationError, AdapterError)


# ═══════════════════════════════════════════════════════════
# AC7 — Performance
# ═══════════════════════════════════════════════════════════

def test_ac7_performance():
    """AC7: 10,000 adapter calls < 5s."""
    adapter = MockPlatformAdapter(failure_rate=0.0)
    start = time.time()
    for i in range(10000):
        adapter.update_budget(f"camp_{i}", 100.0 + i)
    elapsed = time.time() - start

    assert elapsed < 5.0, f"Expected < 5s, got {elapsed:.3f}s"


# ═══════════════════════════════════════════════════════════
# AC8 — E10.1 regression
# ═══════════════════════════════════════════════════════════

def test_ac8_e101_regression():
    """AC8: E10.1 RuntimeAPI still works after E10.2 adapter layer addition."""
    from market_ops.execution_runtime import RuntimeAPI

    api = RuntimeAPI()
    action = {
        "creative_id": "C001",
        "action": "SCALE",
        "budget_change": {"current": 100.0, "target": 200.0},
        "confidence": 0.95,
        "reason": ["WINNER"],
    }

    resp = api.create_execution(action)
    assert resp.success is True
    assert resp.data["status"] == ExecutionStatus.CREATED.value

    task_id = resp.data["task_id"]
    resp2 = api.execute_task(task_id)
    assert resp2.success is True
    assert resp2.data["status"] == ExecutionStatus.COMPLETED.value


def test_ac8_legacy_mock_compat():
    """AC8b: Legacy MockPlatformAdapter (E10.1 style) still works."""
    from market_ops.execution_runtime import MockPlatformAdapter

    task = ExecutionTask(
        creative_id="C002",
        action_type=ActionType.SCALE.value,
        budget_change={"before": 100.0, "after": 200.0},
    )

    adapter = MockPlatformAdapter(failure_rate=0.0)
    result = adapter.execute(task)

    assert result.status == ExecutionStatus.COMPLETED.value
    assert "budget_applied" in result.platform_response
