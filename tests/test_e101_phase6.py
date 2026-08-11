"""E10.1 Phase 6 — API + Export Acceptance Test.

8 AC covering:
  1. Schema completeness (APIResponse, ContractVersion, SchemaValidator)
  2. Create execution API
  3. Execute task API
  4. Query execution API
  5. Feedback API
  6. JSON export contract
  7. Architecture isolation (no E9.9.5 imports)
  8. Performance (10,000 API calls < 5s)
"""

from __future__ import annotations

import time

import pytest

from market_ops.execution_runtime import (
    APIResponse,
    ContractVersion,
    SchemaValidator,
    ExportService,
    RuntimeAPI,
    ExecutionRecord,
    PerformanceSnapshot,
    LearningSignal,
    FeedbackType,
    ExecutionStatus,
)


# ═══════════════════════════════════════════════════════════
# AC1 — Schema completeness
# ═══════════════════════════════════════════════════════════

def test_ac1_schema_completeness():
    """AC1: APIResponse, ContractVersion, SchemaValidator importable."""
    resp = APIResponse(success=True, data={"key": "value"})
    assert resp.success is True
    assert resp.version == ContractVersion.API

    assert ContractVersion.EXECUTION == "E10.1.execution.v1"
    assert ContractVersion.PERFORMANCE == "E10.1.performance.v1"
    assert ContractVersion.FEEDBACK == "E10.1.feedback.v1"

    validator = SchemaValidator()
    errors = validator.validate_execution({})
    assert len(errors) > 0


# ═══════════════════════════════════════════════════════════
# AC2 — Create API
# ═══════════════════════════════════════════════════════════

def test_ac2_create_api():
    """AC2: create_execution returns CREATED task."""
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
    assert "task_id" in resp.data
    assert resp.data["status"] == ExecutionStatus.CREATED.value
    assert resp.data["action_type"] == "SCALE"
    assert resp.version == ContractVersion.API


# ═══════════════════════════════════════════════════════════
# AC3 — Execute API
# ═══════════════════════════════════════════════════════════

def test_ac3_execute_api():
    """AC3: execute_task runs task and returns result."""
    api = RuntimeAPI()
    action = {
        "creative_id": "C002",
        "action": "SCALE",
        "budget_change": {"current": 100.0, "target": 200.0},
        "confidence": 0.95,
        "reason": ["WINNER"],
    }

    created = api.create_execution(action)
    task_id = created.data["task_id"]

    executed = api.execute_task(task_id)

    assert executed.success is True
    assert executed.data["status"] == ExecutionStatus.COMPLETED.value
    assert "result_id" in executed.data


# ═══════════════════════════════════════════════════════════
# AC4 — Query API
# ═══════════════════════════════════════════════════════════

def test_ac4_query_api():
    """AC4: get_execution returns task state."""
    api = RuntimeAPI()
    action = {
        "creative_id": "C003",
        "action": "WATCH",
        "budget_change": {"current": 100.0, "target": 100.0},
        "confidence": 0.8,
        "reason": ["MONITOR"],
    }

    created = api.create_execution(action)
    task_id = created.data["task_id"]

    queried = api.get_execution(task_id)

    assert queried.success is True
    assert queried.data["task_id"] == task_id
    assert queried.data["state"] == ExecutionStatus.CREATED.value
    assert queried.data["action_type"] == "WATCH"


def test_ac4_query_unknown():
    """AC4b: Query unknown task returns error."""
    api = RuntimeAPI()
    resp = api.get_execution("nonexistent")
    assert resp.success is False
    assert "not found" in resp.error.lower()


# ═══════════════════════════════════════════════════════════
# AC5 — Feedback API
# ═══════════════════════════════════════════════════════════

def test_ac5_feedback_api():
    """AC5: get_feedback returns LearningSignal after execution."""
    api = RuntimeAPI()
    action = {
        "creative_id": "C004",
        "action": "SCALE",
        "budget_change": {"current": 100.0, "target": 200.0},
        "confidence": 0.95,
        "reason": ["WINNER"],
    }

    created = api.create_execution(action)
    task_id = created.data["task_id"]

    # Execute to generate feedback
    api.execute_task(task_id)

    feedback = api.get_feedback(task_id)

    assert feedback.success is True
    assert "feedback_type" in feedback.data
    assert "recommendation" in feedback.data
    assert "confidence" in feedback.data


def test_ac5_feedback_not_found():
    """AC5b: Feedback for non-executed task returns error."""
    api = RuntimeAPI()
    resp = api.get_feedback("nonexistent")
    assert resp.success is False
    assert "No feedback" in resp.error


# ═══════════════════════════════════════════════════════════
# AC6 — JSON Export
# ═══════════════════════════════════════════════════════════

def test_ac6_json_export():
    """AC6: ExportService produces versioned JSON payloads."""
    service = ExportService()

    record = ExecutionRecord(
        task_id="task-001",
        action_type="SCALE",
        final_status=ExecutionStatus.COMPLETED.value,
    )
    payload = service.export_execution(record)
    assert payload["schema"] == ContractVersion.EXECUTION
    assert "record" in payload

    snap = PerformanceSnapshot(
        task_id="task-001",
        impressions=10000,
        clicks=500,
        spend=200.0,
        revenue=360.0,
        roas=1.8,
        status="active",
    )
    payload2 = service.export_snapshot(snap)
    assert payload2["schema"] == ContractVersion.PERFORMANCE
    assert "snapshot" in payload2

    signal = LearningSignal(
        task_id="task-001",
        feedback_type=FeedbackType.SUCCESS.value,
        confidence=0.92,
        recommendation="SCALE_VALIDATED",
    )
    payload3 = service.export_feedback(signal)
    assert payload3["schema"] == ContractVersion.FEEDBACK
    assert "signal" in payload3


def test_ac6_json_write():
    """AC6b: ExportService writes JSON to disk."""
    import tempfile
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        service = ExportService(output_dir=tmpdir)
        record = ExecutionRecord(task_id="task-002", action_type="KILL")
        payload = service.export_execution(record)
        path = service.write(payload, "test_record.json")

        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["schema"] == ContractVersion.EXECUTION


# ═══════════════════════════════════════════════════════════
# AC7 — Architecture isolation
# ═══════════════════════════════════════════════════════════

def test_ac7_no_e995_imports():
    """AC7: RuntimeAPI and ExportService must NOT import E9.9.5 modules."""
    import market_ops.execution_runtime.runtime_api as ra_module
    import market_ops.execution_runtime.export_service as es_module

    forbidden = ["scale_engine", "risk_controller", "portfolio_manager", "winner_detector", "kill_engine"]

    for mod in [ra_module, es_module]:
        for name in dir(mod):
            if name.startswith("_"):
                continue
            for f in forbidden:
                assert f not in name.lower(), f"Forbidden import '{f}' found in {mod.__name__}"


def test_ac7_package_imports_allowed():
    """AC7b: All execution_runtime internal imports are allowed."""
    from market_ops.execution_runtime import (
        RuntimeAPI, ExportService, SchemaValidator,
        APIResponse, ContractVersion,
    )
    assert True


# ═══════════════════════════════════════════════════════════
# AC8 — Performance
# ═══════════════════════════════════════════════════════════

def test_ac8_performance():
    """AC8: 10,000 create + execute API calls < 5s."""
    api = RuntimeAPI()

    start = time.time()
    for i in range(10000):
        action = {
            "creative_id": f"C{i}",
            "action": "WATCH",
            "budget_change": {"current": 100.0, "target": 100.0},
            "confidence": 0.8,
            "reason": ["MONITOR"],
        }
        created = api.create_execution(action)
        api.execute_task(created.data["task_id"])
    elapsed = time.time() - start

    assert elapsed < 5.0, f"Expected < 5s, got {elapsed:.3f}s"
