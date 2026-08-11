"""E10.1 Phase 5 — Feedback Loop Acceptance Test.

8 AC covering:
  1. Schema completeness (FeedbackType, LearningSignal)
  2. SUCCESS feedback (ROAS >= 1.5)
  3. NEUTRAL feedback (1.0 <= ROAS < 1.5)
  4. WARNING feedback (0.7 <= ROAS < 1.0)
  5. FAILURE feedback (status=failed or ROAS < 0.7)
  6. Signal history query by task_id
  7. Architecture isolation (no E9.9.5 imports)
  8. Performance (10,000 snapshots < 5s)
"""

from __future__ import annotations

import time

import pytest

from market_ops.execution_runtime import (
    PerformanceSnapshot,
    LearningSignal,
    FeedbackType,
    FeedbackLoop,
)


# ═══════════════════════════════════════════════════════════
# AC1 — Schema completeness
# ═══════════════════════════════════════════════════════════

def test_ac1_schema_completeness():
    """AC1: FeedbackType and LearningSignal are importable and functional."""
    assert FeedbackType.SUCCESS.value == "SUCCESS"
    assert FeedbackType.NEUTRAL.value == "NEUTRAL"
    assert FeedbackType.WARNING.value == "WARNING"
    assert FeedbackType.FAILURE.value == "FAILURE"

    signal = LearningSignal(task_id="t1", feedback_type=FeedbackType.SUCCESS.value)
    assert signal.signal_id
    assert signal.feedback_type == "SUCCESS"


# ═══════════════════════════════════════════════════════════
# AC2 — SUCCESS feedback
# ═══════════════════════════════════════════════════════════

def test_ac2_success_feedback():
    """AC2: ROAS=1.8, active → SUCCESS, SCALE_VALIDATED."""
    loop = FeedbackLoop()
    snapshot = PerformanceSnapshot(
        task_id="task-s1",
        roas=1.8,
        status="active",
        spend=200.0,
        revenue=360.0,
    )

    signal = loop.generate(snapshot)

    assert signal.feedback_type == FeedbackType.SUCCESS.value
    assert signal.recommendation == "SCALE_VALIDATED"
    assert signal.confidence > 0.8
    assert signal.metrics["roas"] == 1.8


# ═══════════════════════════════════════════════════════════
# AC3 — NEUTRAL feedback
# ═══════════════════════════════════════════════════════════

def test_ac3_neutral_feedback():
    """AC3: ROAS=1.2 → NEUTRAL, KEEP_MONITORING."""
    loop = FeedbackLoop()
    snapshot = PerformanceSnapshot(
        task_id="task-n1",
        roas=1.2,
        status="active",
        spend=100.0,
        revenue=120.0,
    )

    signal = loop.generate(snapshot)

    assert signal.feedback_type == FeedbackType.NEUTRAL.value
    assert signal.recommendation == "KEEP_MONITORING"
    assert 0.5 <= signal.confidence <= 0.79


# ═══════════════════════════════════════════════════════════
# AC4 — WARNING feedback
# ═══════════════════════════════════════════════════════════

def test_ac4_warning_feedback():
    """AC4: ROAS=0.8 → WARNING, OPTIMIZATION_REQUIRED."""
    loop = FeedbackLoop()
    snapshot = PerformanceSnapshot(
        task_id="task-w1",
        roas=0.8,
        status="active",
        spend=100.0,
        revenue=80.0,
    )

    signal = loop.generate(snapshot)

    assert signal.feedback_type == FeedbackType.WARNING.value
    assert signal.recommendation == "OPTIMIZATION_REQUIRED"
    assert 0.3 <= signal.confidence <= 0.49


# ═══════════════════════════════════════════════════════════
# AC5 — FAILURE feedback
# ═══════════════════════════════════════════════════════════

def test_ac5_failure_status():
    """AC5: status=failed → FAILURE, STOP_LEARNING."""
    loop = FeedbackLoop()
    snapshot = PerformanceSnapshot(
        task_id="task-f1",
        roas=0.0,
        status="failed",
        spend=0.0,
        revenue=0.0,
    )

    signal = loop.generate(snapshot)

    assert signal.feedback_type == FeedbackType.FAILURE.value
    assert signal.recommendation == "STOP_LEARNING"
    assert signal.confidence == 0.0


def test_ac5_failure_low_roas():
    """AC5b: ROAS < 0.7 → FAILURE, STOP_LEARNING."""
    loop = FeedbackLoop()
    snapshot = PerformanceSnapshot(
        task_id="task-f2",
        roas=0.5,
        status="active",
        spend=100.0,
        revenue=50.0,
    )

    signal = loop.generate(snapshot)

    assert signal.feedback_type == FeedbackType.FAILURE.value
    assert signal.recommendation == "STOP_LEARNING"
    assert signal.confidence == 0.0


# ═══════════════════════════════════════════════════════════
# AC6 — Signal history
# ═══════════════════════════════════════════════════════════

def test_ac6_signal_history():
    """AC6: Query all feedback signals for a task."""
    loop = FeedbackLoop()

    for roas in [1.8, 1.2, 0.8]:
        snapshot = PerformanceSnapshot(
            task_id="task-history",
            roas=roas,
            status="active",
        )
        loop.generate(snapshot)

    history = loop.get_history("task-history")
    assert len(history) == 3
    for s in history:
        assert s.task_id == "task-history"

    # Unknown task returns empty list
    assert loop.get_history("unknown") == []


# ═══════════════════════════════════════════════════════════
# AC7 — Architecture isolation
# ═══════════════════════════════════════════════════════════

def test_ac7_no_e995_imports():
    """AC7: FeedbackLoop must NOT import E9.9.5 decision layer modules."""
    import market_ops.execution_runtime.feedback_loop as fl_module

    forbidden = ["scale_engine", "risk_controller", "portfolio_manager", "winner_detector", "kill_engine"]

    for name in dir(fl_module):
        if name.startswith("_"):
            continue
        for f in forbidden:
            assert f not in name.lower(), f"Forbidden import '{f}' found in {fl_module.__name__}"


def test_ac7_package_imports_allowed():
    """AC7b: All execution_runtime internal imports are allowed."""
    from market_ops.execution_runtime import (
        FeedbackLoop, FeedbackType, LearningSignal, PerformanceSnapshot,
    )
    assert True


# ═══════════════════════════════════════════════════════════
# AC8 — Performance
# ═══════════════════════════════════════════════════════════

def test_ac8_performance():
    """AC8: 10,000 snapshot analyses < 5s."""
    loop = FeedbackLoop()

    start = time.time()
    for i in range(10000):
        snapshot = PerformanceSnapshot(
            task_id=f"task-{i}",
            roas=1.2 + (i % 10) * 0.1,
            status="active",
        )
        loop.generate(snapshot)
    elapsed = time.time() - start

    assert elapsed < 5.0, f"Expected < 5s, got {elapsed:.3f}s"
    assert len(loop.signals) == 10000
