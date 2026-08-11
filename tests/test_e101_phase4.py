"""E10.1 Phase 4 — Result Collector Acceptance Test.

8 AC covering:
  1. Schema completeness (ExecutionRecord, PerformanceSnapshot, CollectionEventType)
  2. Result collection from COMPLETED ExecutionResult
  3. Failed result handling
  4. Performance snapshot generation
  5. History query by task_id
  6. Collection event tracking
  7. Architecture isolation (no E9.9.5 imports)
  8. Performance (10,000 collections < 5s)
"""

from __future__ import annotations

import time

import pytest

from market_ops.execution_runtime import (
    ExecutionResult,
    ExecutionRecord,
    PerformanceSnapshot,
    ExecutionStatus,
    ActionType,
    CollectionEventType,
    ResultCollector,
    PerformanceTracker,
)


# ═══════════════════════════════════════════════════════════
# AC1 — Schema completeness
# ═══════════════════════════════════════════════════════════

def test_ac1_schema_completeness():
    """AC1: ExecutionRecord, PerformanceSnapshot, CollectionEventType importable."""
    record = ExecutionRecord(task_id="t1", final_status=ExecutionStatus.COMPLETED.value)
    assert record.record_id
    assert record.task_id == "t1"

    snap = PerformanceSnapshot(task_id="t1", roas=1.6)
    assert snap.snapshot_id
    assert snap.roas == 1.6

    assert CollectionEventType.RESULT_COLLECTED.value == "RESULT_COLLECTED"
    assert CollectionEventType.PERFORMANCE_UPDATED.value == "PERFORMANCE_UPDATED"


# ═══════════════════════════════════════════════════════════
# AC2 — Result collection (COMPLETED)
# ═══════════════════════════════════════════════════════════

def test_ac2_result_collection():
    """AC2: Collect a COMPLETED ExecutionResult into ExecutionRecord."""
    collector = ResultCollector()
    result = ExecutionResult(
        task_id="task-001",
        status=ExecutionStatus.COMPLETED.value,
        actual_change={"before": 100.0, "after": 200.0},
        platform_response={"verified": True},
        metrics={"action_type": ActionType.SCALE.value, "start_time": "2026-07-20T08:00:00+00:00"},
    )

    record = collector.collect(result)

    assert isinstance(record, ExecutionRecord)
    assert record.task_id == "task-001"
    assert record.final_status == ExecutionStatus.COMPLETED.value
    assert record.action_type == ActionType.SCALE.value
    assert record.approval_status == "APPROVED"
    assert record.platform_response.get("verified") is True
    assert record.execution_duration_ms >= 0


# ═══════════════════════════════════════════════════════════
# AC3 — Failed result handling
# ═══════════════════════════════════════════════════════════

def test_ac3_failed_result():
    """AC3: Collect a FAILED ExecutionResult — error_message and status preserved."""
    collector = ResultCollector()
    result = ExecutionResult(
        task_id="task-002",
        status=ExecutionStatus.FAILED.value,
        error_message="Mock adapter: simulated failure",
        metrics={"action_type": ActionType.SCALE.value},
    )

    record = collector.collect(result)

    assert record.final_status == ExecutionStatus.FAILED.value
    assert record.error_message == "Mock adapter: simulated failure"
    assert record.approval_status == "REJECTED"


# ═══════════════════════════════════════════════════════════
# AC4 — Performance snapshot
# ═══════════════════════════════════════════════════════════

def test_ac4_performance_snapshot():
    """AC4: Generate PerformanceSnapshot with business metrics."""
    collector = ResultCollector()
    result = ExecutionResult(
        task_id="task-003",
        status=ExecutionStatus.COMPLETED.value,
        actual_change={"before": 100.0, "after": 200.0},
        metrics={"action_type": ActionType.SCALE.value},
    )

    record = collector.collect(result)
    snap = collector.snapshot(record)

    assert isinstance(snap, PerformanceSnapshot)
    assert snap.task_id == "task-003"
    assert snap.impressions > 0
    assert snap.clicks > 0
    assert snap.spend > 0
    assert snap.revenue > 0
    assert snap.roas > 0
    assert snap.status == "active"


def test_ac4_kill_snapshot():
    """AC4b: KILL action produces stopped snapshot."""
    collector = ResultCollector()
    result = ExecutionResult(
        task_id="task-004",
        status=ExecutionStatus.COMPLETED.value,
        actual_change={"before": 100.0, "after": 0.0},
        metrics={"action_type": ActionType.KILL.value},
    )

    record = collector.collect(result)
    snap = collector.snapshot(record)

    assert snap.impressions == 0
    assert snap.spend == 0.0
    assert snap.status == "stopped"


# ═══════════════════════════════════════════════════════════
# AC5 — History query
# ═══════════════════════════════════════════════════════════

def test_ac5_history_query():
    """AC5: Query execution history by task_id."""
    collector = ResultCollector()

    for i in range(3):
        result = ExecutionResult(
            task_id="task-history",
            status=ExecutionStatus.COMPLETED.value,
            metrics={"action_type": ActionType.SCALE.value},
        )
        collector.collect(result)

    history = collector.get_history("task-history")
    assert len(history) == 3
    for r in history:
        assert r.task_id == "task-history"

    # Unknown task returns empty list
    assert collector.get_history("unknown") == []


# ═══════════════════════════════════════════════════════════
# AC6 — Collection event tracking
# ═══════════════════════════════════════════════════════════

def test_ac6_event_tracking():
    """AC6: collect() and snapshot() generate CollectionEvents."""
    collector = ResultCollector()
    result = ExecutionResult(
        task_id="task-event",
        status=ExecutionStatus.COMPLETED.value,
        metrics={"action_type": ActionType.WATCH.value},
    )

    record = collector.collect(result)
    collector.snapshot(record)

    events = collector.events
    event_types = [e["event_type"] for e in events]

    assert CollectionEventType.RESULT_COLLECTED.value in event_types
    assert CollectionEventType.PERFORMANCE_UPDATED.value in event_types

    for e in events:
        assert "timestamp" in e
        assert e["task_id"] == "task-event"


# ═══════════════════════════════════════════════════════════
# AC7 — Architecture isolation
# ═══════════════════════════════════════════════════════════

def test_ac7_no_e995_imports():
    """AC7: Result Collector must NOT import E9.9.5 decision layer modules."""
    import market_ops.execution_runtime.result_collector as rc_module
    import market_ops.execution_runtime.performance_tracker as pt_module

    forbidden = ["scale_engine", "risk_controller", "portfolio_manager", "winner_detector", "kill_engine"]

    for mod in [rc_module, pt_module]:
        for name in dir(mod):
            if name.startswith("_"):
                continue
            for f in forbidden:
                assert f not in name.lower(), f"Forbidden import '{f}' found in {mod.__name__}"


def test_ac7_package_imports_allowed():
    """AC7b: All execution_runtime internal imports are allowed."""
    from market_ops.execution_runtime import (
        ResultCollector, PerformanceTracker,
        ExecutionRecord, PerformanceSnapshot, CollectionEventType,
    )
    assert True


# ═══════════════════════════════════════════════════════════
# AC8 — Performance
# ═══════════════════════════════════════════════════════════

def test_ac8_performance():
    """AC8: 10,000 collections + snapshots < 5s."""
    collector = ResultCollector()

    start = time.time()
    for i in range(10000):
        result = ExecutionResult(
            task_id=f"task-{i}",
            status=ExecutionStatus.COMPLETED.value,
            metrics={"action_type": ActionType.SCALE.value},
        )
        record = collector.collect(result)
        collector.snapshot(record)
    elapsed = time.time() - start

    assert elapsed < 5.0, f"Expected < 5s, got {elapsed:.3f}s"
    assert len(collector.records) == 10000
    assert len(collector.snapshots) == 10000
