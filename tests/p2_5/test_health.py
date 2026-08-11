"""P2.5.4 — SLA Monitor + Provider Health + Execution Health Score 验收。"""

from src.execution.monitor.health import (
    GREEN_THRESHOLD,
    YELLOW_THRESHOLD,
    ExecutionHealthScore,
    ProviderHealth,
    compute_health_score,
    compute_metrics,
    compute_provider_health,
    latency_level,
    latency_score,
)
from src.execution.monitor.models import HEALTH_GREEN, HEALTH_RED, HEALTH_YELLOW
from src.execution.safe_executor.models import (
    VERDICT_EXECUTED,
    VERDICT_FAILED,
)
from tests.p2_5.conftest import make_outcome

# ---- SLA 阈值边界 ----------------------------------------------------------

def test_max_sla_green():
    # 规格：<5s GREEN（5.0 落在 5–30 区间，归 YELLOW）
    assert latency_level("max", 4.9) == HEALTH_GREEN


def test_max_sla_yellow():
    assert latency_level("max", 5.0) == HEALTH_YELLOW  # 区间下界含 5
    assert latency_level("max", 5.1) == HEALTH_YELLOW
    assert latency_level("max", 30.0) == HEALTH_YELLOW  # <= 30


def test_max_sla_red():
    assert latency_level("max", 30.1) == HEALTH_RED


def test_meta_sla_boundaries():
    assert latency_level("meta", 9.9) == HEALTH_GREEN
    assert latency_level("meta", 60.0) == HEALTH_YELLOW
    assert latency_level("meta", 60.1) == HEALTH_RED


def test_play_no_sla_always_green():
    assert latency_level("play", 999.0) == HEALTH_GREEN
    assert latency_level("play", 0.0) == HEALTH_GREEN


def test_latency_score_mapping():
    assert latency_score(HEALTH_GREEN) == 1.0
    assert latency_score(HEALTH_YELLOW) == 0.6
    assert latency_score(HEALTH_RED) == 0.2


# ---- Provider Health --------------------------------------------------------

def test_compute_provider_health_per_provider():
    outs = [
        make_outcome(VERDICT_EXECUTED, provider="max", latency_seconds=3.0),
        make_outcome(VERDICT_EXECUTED, provider="max", latency_seconds=4.0),
        make_outcome(VERDICT_EXECUTED, provider="meta", latency_seconds=15.0),
    ]
    ph = compute_provider_health([__summary(o) for o in outs])
    assert "max" in ph and "meta" in ph
    assert ph["max"].executions == 2
    assert ph["max"].success_rate == 1.0
    assert ph["meta"].avg_latency == 15.0
    assert ph["meta"].latency_level == HEALTH_YELLOW


def __summary(o):
    from src.execution.monitor.collector import ExecutionEventCollector
    return ExecutionEventCollector().summarize(None, o)


# ---- Metrics ----------------------------------------------------------------

def test_compute_metrics_aggregate():
    outs = [make_outcome(VERDICT_EXECUTED) for _ in range(8)] + [
        make_outcome(VERDICT_FAILED) for _ in range(2)
    ]
    m = compute_metrics(outs)
    assert m.total_executions == 10
    assert abs(m.success_rate - 0.8) < 1e-6
    assert abs(m.failure_rate - 0.2) < 1e-6


# ---- Health Score 公式 ------------------------------------------------------

def test_health_score_all_green():
    outs = [make_outcome(VERDICT_EXECUTED, provider="max", latency_seconds=3.0)
            for _ in range(5)]
    hs = compute_health_score(outs)
    assert hs.success_rate == 1.0
    assert hs.provider_health == 1.0
    assert hs.latency_score == 1.0
    assert hs.rollback_safety == 1.0
    assert hs.score == 1.0
    assert hs.level == HEALTH_GREEN


def test_health_score_all_red():
    outs = [make_outcome(VERDICT_FAILED, provider="max", latency_seconds=3.0)
            for _ in range(5)]
    hs = compute_health_score(outs)
    # success 0, provider 0, latency 1.0, rollback 1.0 => 0.3
    assert hs.score == 0.3
    assert hs.level == HEALTH_RED


def test_health_score_yellow_boundary():
    # 1 executed + 1 failed (max, 3s): success 0.5, provider 0.5, latency 1.0, rollback 1.0
    outs = [
        make_outcome(VERDICT_EXECUTED, provider="max", latency_seconds=3.0),
        make_outcome(VERDICT_FAILED, provider="max", latency_seconds=3.0),
    ]
    hs = compute_health_score(outs)
    # 0.5*0.4 + 0.5*0.3 + 1.0*0.2 + 1.0*0.1 = 0.65 -> YELLOW
    assert abs(hs.score - 0.65) < 1e-6
    assert hs.level == HEALTH_YELLOW


def test_health_score_from_components_formula():
    hs = ExecutionHealthScore.from_components(0.8, 0.7, 0.6, 0.9)
    expected = 0.8 * 0.4 + 0.7 * 0.3 + 0.6 * 0.2 + 0.9 * 0.1
    assert abs(hs.score - expected) < 1e-6
    assert GREEN_THRESHOLD == 0.8 and YELLOW_THRESHOLD == 0.6


def test_health_score_roundtrip():
    hs = compute_health_score([make_outcome(VERDICT_EXECUTED)])
    hs2 = ExecutionHealthScore.from_dict(hs.to_dict())
    assert hs2.level == hs.level
    assert hs2.score == hs.score
