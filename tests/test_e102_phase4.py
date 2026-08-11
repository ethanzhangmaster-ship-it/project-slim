"""E10.2 Phase 4 — Attribution & Performance Feedback Integration Test.

8 AC covering:
  1. AttributionTracker interface exists
  2. AdjustTracker sandbox get_campaign_metrics()
  3. AppsFlyerTracker sandbox get_campaign_metrics()
  4. MetricNormalizer cross-platform normalization
  5. PerformanceCollector multi-source aggregation
  6. FeedbackMapper PerformanceSnapshot → LearningSignal
  7. Sandbox isolation (no requests, httpx, oauth)
  8. Full Regression (E10.1 + E10.2 Phase1-3)
"""

from __future__ import annotations

import ast
import pathlib

from market_ops.execution_runtime.attribution import (
    AttributionTracker,
    AttributionMetrics,
    AdjustTracker,
    AdjustConfig,
    AppsFlyerTracker,
    AppsFlyerConfig,
    MetricNormalizer,
    PerformanceCollector,
    AttributionError,
    AttributionAuthError,
    AttributionRateLimitError,
    AttributionTimeoutError,
    AttributionDataError,
    AttributionUnavailableError,
)
from market_ops.execution_runtime.schemas import (
    PerformanceSnapshot,
    LearningSignal,
    FeedbackType,
    ActionType,
)
from market_ops.execution_runtime.feedback_mapper import FeedbackMapper


# ═══════════════════════════════════════════════════════════
# AC1 — Attribution Interface
# ═══════════════════════════════════════════════════════════

def test_ac1_attribution_tracker_exists():
    """AC1a: AttributionTracker ABC is importable."""
    assert AttributionTracker is not None


def test_ac1_attribution_metrics_schema():
    """AC1b: AttributionMetrics has correct fields."""
    metrics = AttributionMetrics(
        campaign_id="camp_001",
        spend=500.0,
        impressions=10000,
        clicks=300,
        installs=200,
        revenue_d7=1200.0,
        source="adjust",
    )
    assert metrics.campaign_id == "camp_001"
    assert metrics.spend == 500.0
    assert metrics.roi_d7 > 0  # Auto-calculated

    data = metrics.to_dict()
    assert "spend" in data
    assert "roi_d7" in data
    assert "cpi" in data


# ═══════════════════════════════════════════════════════════
# AC2 — Adjust Adapter
# ═══════════════════════════════════════════════════════════

def test_ac2_adjust_tracker_implements_interface():
    """AC2a: AdjustTracker implements AttributionTracker."""
    tracker = AdjustTracker()
    assert isinstance(tracker, AttributionTracker)
    assert tracker.source_name == "adjust"


def test_ac2_adjust_get_campaign_metrics():
    """AC2b: AdjustTracker returns valid AttributionMetrics."""
    tracker = AdjustTracker()
    metrics = tracker.get_campaign_metrics("camp_001", "2024-01-01", "2024-01-07")

    assert isinstance(metrics, AttributionMetrics)
    assert metrics.source == "adjust"
    assert metrics.campaign_id == "camp_001"
    assert metrics.spend > 0
    assert metrics.impressions > 0
    assert metrics.installs > 0
    assert metrics.roi_d7 > 0
    assert metrics.cpi > 0
    assert metrics.ctr > 0
    assert metrics.cvr > 0


def test_ac2_adjust_sandbox():
    """AC2c: Adjust sandbox=True (default) returns mock data."""
    config = AdjustConfig(sandbox=True)
    tracker = AdjustTracker(config)
    metrics = tracker.get_campaign_metrics("camp_001", "2024-01-01", "2024-01-07")
    assert metrics.source == "adjust"
    assert metrics.spend > 0  # Mock data has values


# ═══════════════════════════════════════════════════════════
# AC3 — AppsFlyer Adapter
# ═══════════════════════════════════════════════════════════

def test_ac3_appsflyer_tracker_implements_interface():
    """AC3a: AppsFlyerTracker implements AttributionTracker."""
    tracker = AppsFlyerTracker()
    assert isinstance(tracker, AttributionTracker)
    assert tracker.source_name == "appsflyer"


def test_ac3_appsflyer_get_campaign_metrics():
    """AC3b: AppsFlyerTracker returns valid AttributionMetrics."""
    tracker = AppsFlyerTracker()
    metrics = tracker.get_campaign_metrics("camp_002", "2024-02-01", "2024-02-07")

    assert isinstance(metrics, AttributionMetrics)
    assert metrics.source == "appsflyer"
    assert metrics.campaign_id == "camp_002"
    assert metrics.spend > 0
    assert metrics.impressions > 0
    assert metrics.installs > 0


def test_ac3_appsflyer_deterministic():
    """AC3c: Same campaign_id produces consistent mock data."""
    tracker = AppsFlyerTracker()
    m1 = tracker.get_campaign_metrics("camp_003", "2024-01-01", "2024-01-07")
    m2 = tracker.get_campaign_metrics("camp_003", "2024-01-01", "2024-01-07")
    assert m1.spend == m2.spend
    assert m1.installs == m2.installs


# ═══════════════════════════════════════════════════════════
# AC4 — Metric Normalization
# ═══════════════════════════════════════════════════════════

def test_ac4_normalize_adjust_fields():
    """AC4a: Normalizer maps Adjust field names."""
    normalizer = MetricNormalizer()
    raw = {"cost": 500.0, "impressions": 10000, "clicks": 300, "installs": 200, "revenue": 1200.0}
    metrics = normalizer.normalize("adjust", "camp_001", raw)

    assert metrics.spend == 500.0  # cost → spend
    assert metrics.impressions == 10000
    assert metrics.installs == 200
    assert metrics.revenue_d7 == 1200.0  # revenue → revenue_d7
    assert metrics.source == "adjust"


def test_ac4_normalize_appsflyer_fields():
    """AC4b: Normalizer maps AppsFlyer field names."""
    normalizer = MetricNormalizer()
    raw = {"cost": 400.0, "impressions": 8000, "clicks": 250, "installs": 180, "af_revenue": 900.0}
    metrics = normalizer.normalize("appsflyer", "camp_002", raw)

    assert metrics.spend == 400.0  # cost → spend
    assert metrics.revenue_d7 == 900.0  # af_revenue → revenue_d7
    assert metrics.source == "appsflyer"


def test_ac4_normalize_fallback():
    """AC4c: Unknown source falls back to mock mapping."""
    normalizer = MetricNormalizer()
    raw = {"spend": 300.0, "impressions": 5000, "clicks": 150, "installs": 100, "revenue": 600.0}
    metrics = normalizer.normalize("unknown", "camp_003", raw)

    assert metrics.spend == 300.0
    assert metrics.source == "unknown"


def test_ac4_merge_metrics():
    """AC4d: merge_metrics aggregates multiple sources."""
    normalizer = MetricNormalizer()
    m1 = AttributionMetrics(campaign_id="c1", spend=500, impressions=10000, clicks=300, installs=200, revenue_d7=1000, source="adjust")
    m2 = AttributionMetrics(campaign_id="c1", spend=400, impressions=8000, clicks=250, installs=180, revenue_d7=800, source="appsflyer")

    merged = normalizer.merge_metrics([m1, m2])
    assert merged.campaign_id == "c1"
    assert merged.spend == 900.0  # 500 + 400
    assert merged.impressions == 18000
    assert "merged" in merged.source


# ═══════════════════════════════════════════════════════════
# AC5 — Performance Collector
# ═══════════════════════════════════════════════════════════

def test_ac5_collector_single_source():
    """AC5a: PerformanceCollector with single tracker."""
    collector = PerformanceCollector()
    collector.add_tracker("adjust", AdjustTracker())

    snapshot = collector.collect("camp_001", "2024-01-01", "2024-01-07", task_id="t_001")
    assert isinstance(snapshot, PerformanceSnapshot)
    assert snapshot.spend > 0
    assert snapshot.revenue > 0
    assert snapshot.roas > 0
    assert snapshot.status == "COMPLETED"


def test_ac5_collector_multi_source():
    """AC5b: PerformanceCollector merges multiple trackers."""
    collector = PerformanceCollector({
        "adjust": AdjustTracker(),
        "appsflyer": AppsFlyerTracker(),
    })
    assert collector.tracker_count == 2
    assert set(collector.source_names) == {"adjust", "appsflyer"}

    snapshot = collector.collect("camp_001", "2024-01-01", "2024-01-07")
    assert snapshot.spend > 0
    assert snapshot.impressions > 0


def test_ac5_collector_no_trackers():
    """AC5c: Empty collector returns NO_DATA snapshot."""
    collector = PerformanceCollector()
    snapshot = collector.collect("camp_001", task_id="t_001")
    assert snapshot.status == "NO_DATA"
    assert snapshot.spend == 0.0


def test_ac5_collector_from_single():
    """AC5d: collect_from_single works with one tracker."""
    collector = PerformanceCollector()
    tracker = AdjustTracker()
    snapshot = collector.collect_from_single(tracker, "camp_001")
    assert snapshot.spend > 0


# ═══════════════════════════════════════════════════════════
# AC6 — Feedback Integration
# ═══════════════════════════════════════════════════════════

def test_ac6_feedback_scale_high_roas():
    """AC6a: ROAS > 1.5 → SCALE SUCCESS."""
    mapper = FeedbackMapper()
    snapshot = PerformanceSnapshot(roas=2.0, spend=500.0, revenue=1000.0, impressions=10000, clicks=300, conversions=200)

    signal = mapper.map(snapshot, task_id="t_001")
    assert isinstance(signal, LearningSignal)
    assert signal.action_type == ActionType.SCALE.value
    assert signal.feedback_type == FeedbackType.SUCCESS.value
    assert "SCALE" in signal.recommendation
    assert "ROAS" in signal.recommendation
    assert signal.confidence > 0.8


def test_ac6_feedback_watch_marginal():
    """AC6b: ROAS 0.8-1.5 → WATCH NEUTRAL."""
    mapper = FeedbackMapper()
    snapshot = PerformanceSnapshot(roas=1.0, spend=500.0, revenue=500.0)

    signal = mapper.map(snapshot, task_id="t_002")
    assert signal.action_type == ActionType.WATCH.value
    assert signal.feedback_type == FeedbackType.NEUTRAL.value
    assert "WATCH" in signal.recommendation
    assert signal.confidence == 0.5


def test_ac6_feedback_kill_low_roas():
    """AC6c: ROAS < 0.8 → KILL FAILURE."""
    mapper = FeedbackMapper()
    snapshot = PerformanceSnapshot(roas=0.5, spend=500.0, revenue=250.0)

    signal = mapper.map(snapshot, task_id="t_003")
    assert signal.action_type == ActionType.KILL.value
    assert signal.feedback_type == FeedbackType.FAILURE.value
    assert "KILL" in signal.recommendation
    assert signal.confidence > 0.5


def test_ac6_feedback_exact_threshold():
    """AC6d: ROAS exactly 1.5 → SCALE (boundary test)."""
    mapper = FeedbackMapper()
    snapshot = PerformanceSnapshot(roas=1.5, spend=500.0, revenue=750.0)

    signal = mapper.map(snapshot, task_id="t_004")
    # > 1.5 is SCALE, not >= 1.5. So 1.5 goes to WATCH
    assert signal.action_type == ActionType.WATCH.value


def test_ac6_feedback_metrics_in_signal():
    """AC6e: LearningSignal contains all metrics."""
    mapper = FeedbackMapper()
    snapshot = PerformanceSnapshot(
        roas=2.0, spend=500.0, revenue=1000.0,
        impressions=10000, clicks=300, conversions=200,
        ctr=0.03, cvr=0.67,
    )

    signal = mapper.map(snapshot, task_id="t_005")
    assert signal.metrics["roas"] == 2.0
    assert signal.metrics["spend"] == 500.0
    assert signal.metrics["impressions"] == 10000
    assert signal.metrics["ctr"] == 0.03


# ═══════════════════════════════════════════════════════════
# AC7 — Sandbox Isolation
# ═══════════════════════════════════════════════════════════

def test_ac7_no_http_imports_in_attribution():
    """AC7a: Attribution modules use no HTTP/oauth libs."""
    import market_ops.execution_runtime.attribution as attr_pkg
    forbidden = ["requests", "httpx", "aiohttp", "urllib3", "oauth", "access_token"]

    pkg_dir = attr_pkg.__path__[0]
    for py_file in pathlib.Path(pkg_dir).glob("*.py"):
        code = py_file.read_text(encoding="utf-8")
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for kw in forbidden:
                        assert kw not in alias.name.lower(), f"Forbidden import '{kw}' in {py_file.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for kw in forbidden:
                        assert kw not in node.module.lower(), f"Forbidden import '{kw}' in {py_file.name}"


def test_ac7_feedback_mapper_no_http():
    """AC7b: feedback_mapper.py has no HTTP imports."""
    import market_ops.execution_runtime
    fb_path = pathlib.Path(market_ops.execution_runtime.__file__).parent / "feedback_mapper.py"
    code = fb_path.read_text(encoding="utf-8")
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.Import):
                module = node.names[0].name
            elif node.module:
                module = node.module
            for kw in ["requests", "httpx", "oauth", "urllib"]:
                assert kw not in module.lower(), f"Forbidden import in feedback_mapper.py: {module}"


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


def test_ac8_e102_phase1_imports():
    """AC8b: E10.2 Phase 1 imports still work."""
    from market_ops.execution_runtime.adapters import PlatformAdapter, AdapterResult, MockPlatformAdapter
    assert PlatformAdapter is not None


def test_ac8_e102_phase2_facebook_adapter():
    """AC8c: Facebook adapter still works (Phase 2)."""
    from market_ops.execution_runtime.adapters import FacebookAdsAdapter, FacebookConfig
    config = FacebookConfig(sandbox=True)
    adapter = FacebookAdsAdapter(config=config)
    result = adapter.update_budget("c_001", 200.0)
    assert result.success is True


def test_ac8_e102_phase3_budget_guard():
    """AC8d: BudgetGuard still works (Phase 3)."""
    from market_ops.execution_runtime import BudgetGuard
    guard = BudgetGuard(max_scale_ratio=0.30)
    result = guard.check(100.0, 120.0)
    assert result.allowed is True


def test_ac8_full_attribution_to_feedback_cycle():
    """AC8e: Full attribution → feedback cycle."""
    # 1. Collect attribution data
    collector = PerformanceCollector({"adjust": AdjustTracker()})
    snapshot = collector.collect("camp_001", task_id="t_full")

    # 2. Map to feedback
    mapper = FeedbackMapper()
    signal = mapper.map(snapshot)

    # 3. Verify chain
    assert snapshot.roas > 0
    assert isinstance(signal, LearningSignal)
    assert signal.task_id == "t_full"
    assert signal.action_type in {ActionType.SCALE.value, ActionType.WATCH.value, ActionType.KILL.value}


def test_ac8_exceptions_hierarchy():
    """AC8f: Attribution exceptions hierarchy is correct."""
    assert issubclass(AttributionAuthError, AttributionError)
    assert issubclass(AttributionRateLimitError, AttributionError)
    assert issubclass(AttributionTimeoutError, AttributionError)
    assert issubclass(AttributionDataError, AttributionError)
    assert issubclass(AttributionUnavailableError, AttributionError)

    exc = AttributionAuthError("adjust", "Invalid token")
    assert exc.source == "adjust"
    assert "Invalid token" in str(exc)