"""P2.5.1 — ExecutionEvent / ExecutionSummary / ExecutionMetrics 模型验收。"""

import pytest

from src.execution.monitor.models import (
    EVENT_CREATED,
    EVENT_VERIFIED,
    ExecutionEvent,
    ExecutionMetrics,
    ExecutionSummary,
    IllegalStateTransitionError,
    VALID_EVENT_TYPES,
    _ALLOWED_STATE_TRANSITIONS,
)

TEN_EVENTS = [
    "CREATED", "APPROVAL_GRANTED", "EXECUTION_STARTED", "PROVIDER_CALLED",
    "PROVIDER_SUCCESS", "PROVIDER_FAILED", "ROLLBACK_STARTED",
    "ROLLBACK_SUCCESS", "ROLLBACK_FAILED", "VERIFIED",
]


def test_ten_event_types_defined():
    assert len(VALID_EVENT_TYPES) == 10
    for name in TEN_EVENTS:
        assert name in VALID_EVENT_TYPES


def test_event_requires_valid_type():
    with pytest.raises(ValueError):
        ExecutionEvent(execution_id="exe_1", event_type="NOT_A_TYPE")


def test_event_defaults_filled():
    ev = ExecutionEvent(execution_id="exe_1", event_type=EVENT_CREATED)
    assert ev.event_id.startswith("evt_")
    assert ev.timestamp  # ISO filled
    assert ev.metadata == {}


def test_event_roundtrip():
    ev = ExecutionEvent(
        execution_id="exe_1", event_type=EVENT_VERIFIED, provider="max",
        action="update_waterfall", status="SUCCESS", metadata={"k": 1},
    )
    d = ev.to_dict()
    ev2 = ExecutionEvent.from_dict(d)
    assert ev2.event_id == ev.event_id
    assert ev2.event_type == ev.event_type
    assert ev2.provider == "max"
    assert ev2.metadata == {"k": 1}


def test_summary_drift_detection():
    s = ExecutionSummary(
        execution_id="exe_1", action="update_waterfall", target="g",
        provider="max", verdict="EXECUTED", status="SUCCESS", timestamp="t",
        intended_action="disable_network",
    )
    assert s.drifted is True
    s2 = ExecutionSummary(
        execution_id="exe_2", action="update_waterfall", target="g",
        provider="max", verdict="EXECUTED", status="SUCCESS", timestamp="t",
        intended_action="update_waterfall",
    )
    assert s2.drifted is False


def test_summary_roundtrip():
    s = ExecutionSummary(
        execution_id="exe_1", action="a", target="t", provider="max",
        verdict="EXECUTED", status="SUCCESS", timestamp="ts", is_real=True,
        intended_action="a", latency_seconds=3.5,
    )
    s2 = ExecutionSummary.from_dict(s.to_dict())
    assert s2.drifted is False
    assert s2.latency_seconds == 3.5
    assert s2.is_real is True


@pytest.mark.parametrize("verdict,bucket", [
    ("EXECUTED", "success"),
    ("RETURN_EXISTING", "success"),
    ("ROLLED_BACK", "rollback"),
    ("FAILED", "failed"),
    ("ESCALATED", "failed"),
    ("BLOCKED", "blocked"),
    ("WEIRD", "other"),
])
def test_metrics_classify(verdict, bucket):
    assert ExecutionMetrics._classify(verdict) == bucket


def test_metrics_from_summaries_all_success():
    summaries = [{"verdict": "EXECUTED"} for _ in range(10)]
    m = ExecutionMetrics.from_summaries(summaries)
    assert m.total_executions == 10
    assert m.success_rate == 1.0
    assert m.failure_rate == 0.0
    assert m.rollback_rate == 0.0


def test_metrics_from_summaries_mixed():
    summaries = (
        [{"verdict": "EXECUTED"}] * 7
        + [{"verdict": "FAILED"}] * 2
        + [{"verdict": "ROLLED_BACK"}] * 1
    )
    m = ExecutionMetrics.from_summaries(summaries)
    assert m.total_executions == 10
    assert abs(m.success_rate - 0.7) < 1e-6
    assert abs(m.failure_rate - 0.2) < 1e-6
    assert abs(m.rollback_rate - 0.1) < 1e-6


def test_metrics_empty():
    m = ExecutionMetrics.from_summaries([])
    assert m.total_executions == 0


def test_metrics_roundtrip():
    m = ExecutionMetrics(total_executions=5, success_rate=0.8, failure_rate=0.1,
                         rollback_rate=0.1, blocked_rate=0.0)
    m2 = ExecutionMetrics.from_dict(m.to_dict())
    assert m2.total_executions == 5
    assert abs(m2.success_rate - 0.8) < 1e-6


def test_state_transition_table_shape():
    # 每条合法迁移的目标集合必须是已知状态
    for src, targets in _ALLOWED_STATE_TRANSITIONS.items():
        for t in targets:
            assert t in _ALLOWED_STATE_TRANSITIONS
    assert IllegalStateTransitionError.__mro__[1] is ValueError
