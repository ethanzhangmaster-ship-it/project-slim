"""E10.2 Phase 2 — Facebook Ads Adapter Acceptance Test.

8 AC covering:
  1. FacebookAdsAdapter implements PlatformAdapter
  2. SCALE → update_budget
  3. KILL → pause_campaign
  4. WATCH → get_metrics
  5. RETEST → create_campaign (duplicate)
  6. Error mapping (OAuth, Rate Limit, Timeout)
  7. Architecture isolation (no facebook-sdk, no requests)
  8. Regression (E10.1 Phase1-7 + E10.2 Phase1)
"""

from __future__ import annotations

import ast
import time

from market_ops.execution_runtime.adapters import (
    PlatformAdapter,
    AdapterResult,
    AdapterRegistry,
    AdapterError,
    AdapterAuthenticationError,
    AdapterRateLimitError,
    MockPlatformAdapter,
    FacebookAdsAdapter,
    FacebookConfig,
    FacebookClient,
    FacebookMapper,
)
from market_ops.execution_runtime.adapters.facebook.exceptions import (
    FacebookAdapterError,
    FacebookAuthError,
    FacebookRateLimitError,
    FacebookResourceError,
    FacebookTimeoutError,
    FacebookAPIError,
    map_facebook_error,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_adapter(sandbox: bool = True) -> FacebookAdsAdapter:
    """Create a FacebookAdsAdapter in sandbox mode."""
    config = FacebookConfig(sandbox=sandbox)
    return FacebookAdsAdapter(config=config)


# ═══════════════════════════════════════════════════════════
# AC1 — Interface
# ═══════════════════════════════════════════════════════════

def test_ac1_implements_platform_adapter():
    """AC1: FacebookAdsAdapter implements PlatformAdapter ABC."""
    adapter = _make_adapter()
    assert isinstance(adapter, PlatformAdapter)
    assert adapter.platform_name == "facebook"

    # All required methods
    assert callable(adapter.create_campaign)
    assert callable(adapter.update_budget)
    assert callable(adapter.pause_campaign)
    assert callable(adapter.get_metrics)


def test_ac1_config_from_env():
    """AC1b: FacebookConfig.from_env() works with defaults."""
    config = FacebookConfig()
    assert config.sandbox is True
    assert config.api_version == "v22.0"
    assert config.timeout == 30
    assert config.graph_url == "https://graph.facebook.com/v22.0"


def test_ac1_config_validate():
    """AC1c: FacebookConfig.validate() detects missing fields."""
    config = FacebookConfig()
    missing = config.validate()
    assert "app_id" in missing
    assert "access_token" in missing
    assert "ad_account_id" in missing

    config2 = FacebookConfig(app_id="123", access_token="tok", ad_account_id="act_1")
    assert config2.validate() == []
    assert config2.is_configured is True


# ═══════════════════════════════════════════════════════════
# AC2 — SCALE
# ═══════════════════════════════════════════════════════════

def test_ac2_scale_update_budget():
    """AC2: SCALE → update_budget with correct budget in cents."""
    adapter = _make_adapter()
    result = adapter.update_budget("23842567890012345", 500.0)

    assert result.success is True
    assert result.platform == "facebook"
    assert result.operation == "update_budget"
    assert result.external_id == "23842567890012345"
    assert result.raw_response.get("budget_applied") == 500.0
    assert result.raw_response.get("daily_budget_cents") == 50000


def test_ac2_scale_with_different_budgets():
    """AC2b: SCALE correctly converts various budget amounts to cents."""
    adapter = _make_adapter()

    test_cases = [
        (100.0, 10000),
        (1.0, 100),
        (0.5, 50),
        (1000.0, 100000),
        (99.99, 9999),
    ]
    for dollars, expected_cents in test_cases:
        result = adapter.update_budget("camp_001", dollars)
        assert result.success is True
        assert result.raw_response["daily_budget_cents"] == expected_cents


# ═══════════════════════════════════════════════════════════
# AC3 — KILL
# ═══════════════════════════════════════════════════════════

def test_ac3_kill_pause_campaign():
    """AC3: KILL → pause_campaign sets status=PAUSED."""
    adapter = _make_adapter()
    result = adapter.pause_campaign("23842567890012345")

    assert result.success is True
    assert result.platform == "facebook"
    assert result.operation == "pause_campaign"
    assert result.external_id == "23842567890012345"
    assert result.raw_response.get("effective_status") == "PAUSED"


# ═══════════════════════════════════════════════════════════
# AC4 — WATCH
# ═══════════════════════════════════════════════════════════

def test_ac4_watch_get_metrics():
    """AC4: WATCH → get_metrics returns campaign insights."""
    adapter = _make_adapter()
    result = adapter.get_metrics("23842567890012345")

    assert result.success is True
    assert result.platform == "facebook"
    assert result.operation == "get_metrics"
    assert result.external_id == "23842567890012345"

    metrics = result.raw_response.get("metrics", {})
    assert "impressions" in metrics
    assert "clicks" in metrics
    assert "spend" in metrics
    assert "cpm" in metrics
    assert "cpc" in metrics
    assert "ctr" in metrics
    assert result.raw_response.get("campaign_status") == "ACTIVE"


# ═══════════════════════════════════════════════════════════
# AC5 — RETEST
# ═══════════════════════════════════════════════════════════

def test_ac5_retest_create_campaign():
    """AC5: RETEST → create_campaign duplicates with new ID."""
    adapter = _make_adapter()
    result = adapter.create_campaign({
        "source_campaign_id": "23842567890012345",
        "budget": 50.0,
    })

    assert result.success is True
    assert result.platform == "facebook"
    assert result.operation == "create_campaign"
    assert "_copy_" in result.external_id
    assert "23842567890012345" in result.external_id


# ═══════════════════════════════════════════════════════════
# AC6 — Error Mapping
# ═══════════════════════════════════════════════════════════

def test_ac6_oauth_error():
    """AC6a: OAuth error (code 190) → FacebookAuthError."""
    exc = map_facebook_error(190, "Invalid OAuth access token")
    assert isinstance(exc, FacebookAuthError)
    assert isinstance(exc, AdapterAuthenticationError)
    assert exc.platform == "facebook"
    assert "Invalid OAuth access token" in str(exc)


def test_ac6_rate_limit_error():
    """AC6b: Rate limit (code 4) → FacebookRateLimitError."""
    exc = map_facebook_error(4, "Rate limit exceeded")
    assert isinstance(exc, FacebookRateLimitError)
    assert isinstance(exc, AdapterRateLimitError)
    assert exc.platform == "facebook"
    assert hasattr(exc, "retry_after")


def test_ac6_timeout_error():
    """AC6c: Timeout error (code 2) → FacebookTimeoutError."""
    exc = map_facebook_error(2, "Service temporarily unavailable")
    assert isinstance(exc, FacebookTimeoutError)
    assert isinstance(exc, FacebookAdapterError)
    assert "Service temporarily unavailable" in str(exc)


def test_ac6_resource_error():
    """AC6d: Resource error (code 100) → FacebookResourceError."""
    exc = map_facebook_error(100, "Invalid parameter")
    assert isinstance(exc, FacebookResourceError)
    assert isinstance(exc, FacebookAdapterError)


def test_ac6_unknown_error():
    """AC6e: Unknown error code → FacebookAPIError."""
    exc = map_facebook_error(999, "Some unknown error")
    assert isinstance(exc, FacebookAPIError)
    assert exc.error_code == 999


def test_ac6_error_hierarchy():
    """AC6f: All Facebook errors inherit from AdapterError."""
    errors = [
        FacebookAdapterError("base"),
        FacebookAuthError("auth"),
        FacebookRateLimitError(),
        FacebookResourceError("r1"),
        FacebookTimeoutError("op"),
        FacebookAPIError(1, "msg"),
    ]
    for err in errors:
        assert isinstance(err, AdapterError)
        assert isinstance(err, Exception)


# ═══════════════════════════════════════════════════════════
# AC7 — Architecture Isolation
# ═══════════════════════════════════════════════════════════

def test_ac7_no_platform_sdks_in_facebook_module():
    """AC7: Facebook adapter module MUST NOT import facebook-sdk or requests."""
    import market_ops.execution_runtime.adapters.facebook as fb_pkg

    forbidden_modules = [
        "facebook_business", "facebookads",
        "requests", "httpx", "aiohttp", "urllib3",
    ]

    pkg_dir = fb_pkg.__path__[0]
    import pathlib
    for py_file in pathlib.Path(pkg_dir).glob("*.py"):
        code = py_file.read_text(encoding="utf-8")
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.lower()
                    for kw in forbidden_modules:
                        assert kw not in name, f"Forbidden import '{kw}' in {py_file.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_name = node.module.lower()
                    # Allow internal facebook adapter imports
                    if "market_ops.execution_runtime.adapters.facebook" in mod_name:
                        continue
                    for kw in forbidden_modules:
                        assert kw not in mod_name, f"Forbidden import '{kw}' in {py_file.name}"


def test_ac7_facebook_client_uses_stdlib():
    """AC7b: FacebookClient uses urllib (stdlib), not requests."""
    import inspect
    source = inspect.getsource(FacebookClient)
    assert "urllib" in source
    assert "requests." not in source
    assert "httpx" not in source


# ═══════════════════════════════════════════════════════════
# AC8 — Regression
# ═══════════════════════════════════════════════════════════

def test_ac8_e101_runtime_api_still_works():
    """AC8: E10.1 RuntimeAPI still works with Facebook adapter present."""
    from market_ops.execution_runtime import RuntimeAPI, ExecutionStatus

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


def test_ac8_facebook_registered_in_registry():
    """AC8b: FacebookAdsAdapter can be registered and retrieved."""
    registry = AdapterRegistry()
    adapter = _make_adapter()
    registry.register("facebook", adapter)

    assert registry.has_adapter("facebook") is True
    retrieved = registry.get("facebook")
    assert retrieved is adapter
    assert isinstance(retrieved, PlatformAdapter)


def test_ac8_mock_adapter_still_works():
    """AC8c: MockPlatformAdapter continues to work alongside Facebook."""
    registry = AdapterRegistry()
    registry.register("mock", MockPlatformAdapter())
    registry.register("facebook", _make_adapter())

    mock_adapter = registry.get("mock")
    result = mock_adapter.update_budget("camp_001", 200.0)
    assert result.success is True
    assert result.platform == "mock"

    fb_adapter = registry.get("facebook")
    result2 = fb_adapter.update_budget("camp_002", 300.0)
    assert result2.success is True
    assert result2.platform == "facebook"


# ═══════════════════════════════════════════════════════════
# Bonus — FacebookMapper
# ═══════════════════════════════════════════════════════════

def test_mapper_to_cents_conversion():
    """Mapper: _to_cents converts dollars to cents correctly."""
    assert FacebookMapper._to_cents(500.0) == "50000"
    assert FacebookMapper._to_cents(1.0) == "100"
    assert FacebookMapper._to_cents(0.5) == "50"
    assert FacebookMapper._to_cents(99.99) == "9999"


def test_mapper_from_cents():
    """Mapper: from_cents converts cents back to dollars."""
    assert FacebookMapper.from_cents("50000") == 500.0
    assert FacebookMapper.from_cents(100) == 1.0
    assert FacebookMapper.from_cents("50") == 0.5


def test_mapper_action_mapping():
    """Mapper: map_action returns correct operation and params."""
    from market_ops.execution_runtime.schemas import ActionType

    mapper = FacebookMapper()

    scale = mapper.map_action(ActionType.SCALE.value, {"before": 100.0, "after": 500.0})
    assert scale["operation"] == "update_budget"
    assert scale["method"] == "POST"
    assert scale["params"]["daily_budget"] == "50000"

    kill = mapper.map_action(ActionType.KILL.value, {"before": 100.0, "after": 0.0})
    assert kill["operation"] == "pause_campaign"
    assert kill["params"]["status"] == "PAUSED"

    watch = mapper.map_action(ActionType.WATCH.value, {"before": 100.0, "after": 100.0})
    assert watch["operation"] == "get_metrics"
    assert watch["method"] == "GET"

    retest = mapper.map_action(ActionType.RETEST.value, {"before": 0.0, "after": 50.0}, {"budget": 50.0})
    assert retest["operation"] == "duplicate_campaign"
    assert retest["params"]["daily_budget"] == "5000"


# ═══════════════════════════════════════════════════════════
# Bonus — FacebookClient sandbox
# ═══════════════════════════════════════════════════════════

def test_client_sandbox_no_network():
    """FacebookClient in sandbox mode makes no real HTTP calls."""
    config = FacebookConfig(sandbox=True)
    client = FacebookClient(config)

    start = time.time()
    resp = client.get_campaign("12345")
    elapsed = time.time() - start

    assert resp["success"] is True
    assert elapsed < 0.5  # Should be instant, no network
    assert client.request_count == 1


def test_client_all_operations_in_sandbox():
    """FacebookClient sandbox handles all four operations."""
    config = FacebookConfig(sandbox=True)
    client = FacebookClient(config)

    resp1 = client.update_campaign_budget("c1", 50000)
    assert resp1["success"] is True

    resp2 = client.pause_campaign("c1")
    assert resp2["success"] is True

    resp3 = client.get_campaign("c1")
    assert resp3["success"] is True
    assert "insights" in resp3["data"]

    resp4 = client.duplicate_campaign("c1")
    assert resp4["success"] is True
    assert "copy" in resp4["data"]["id"]

    assert client.request_count == 4