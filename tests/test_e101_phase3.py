"""E10.1 Phase 3 — Approval Gate Acceptance Test.

9 AC covering:
  1. Schema completeness (ApprovalDecision)
  2. SAFE → AUTO approve
  3. WARNING → HUMAN pending
  4. CRITICAL → MANAGER pending
  5. Workflow approve flow
  6. Workflow reject flow
  7. Workflow expire flow
  8. Execution blocking (PENDING → no EXECUTING)
  9. Architecture isolation (no E9.9.5 imports)
"""

from __future__ import annotations

import pytest

from market_ops.execution_runtime import (
    ExecutionTask,
    ExecutionStatus,
    ActionType,
    ApprovalStatus,
    ApprovalLevel,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalWorkflow,
    ApprovalGate,
    ExecutionEngine,
)


# ═══════════════════════════════════════════════════════════
# AC1 — Schema completeness
# ═══════════════════════════════════════════════════════════

def test_ac1_schema_completeness():
    """AC1: ApprovalRequest and ApprovalDecision exist and are importable."""
    req = ApprovalRequest(task_id="t1", risk_level="SAFE")
    assert req.status == ApprovalStatus.PENDING.value

    dec = ApprovalDecision(task_id="t1", approval_level=ApprovalLevel.AUTO.value)
    assert dec.approval_level == ApprovalLevel.AUTO.value
    assert dec.status == ApprovalStatus.PENDING.value


# ═══════════════════════════════════════════════════════════
# AC2 — SAFE auto approve
# ═══════════════════════════════════════════════════════════

def test_ac2_safe_auto_approve():
    """AC2: SAFE risk + SCALE action → AUTO approval, status=APPROVED."""
    task = ExecutionTask(
        creative_id="c1",
        action_type=ActionType.SCALE.value,
        risk_level="SAFE",
        budget_change={"before": 100.0, "after": 110.0},
    )
    gate = ApprovalGate()
    decision = gate.check(task)

    assert decision.approval_level == ApprovalLevel.AUTO.value
    assert decision.status == ApprovalStatus.APPROVED.value
    assert decision.task_id == task.task_id


# ═══════════════════════════════════════════════════════════
# AC3 — WARNING human approval
# ═══════════════════════════════════════════════════════════

def test_ac3_warning_human_approval():
    """AC3: WARNING risk → HUMAN approval, status=PENDING."""
    task = ExecutionTask(
        creative_id="c1",
        action_type=ActionType.SCALE.value,
        risk_level="WARNING",
        budget_change={"before": 100.0, "after": 200.0},
    )
    gate = ApprovalGate()
    decision = gate.check(task)

    assert decision.approval_level == ApprovalLevel.HUMAN.value
    assert decision.status == ApprovalStatus.PENDING.value
    assert "WARNING" in decision.reason


# ═══════════════════════════════════════════════════════════
# AC4 — CRITICAL manager approval
# ═══════════════════════════════════════════════════════════

def test_ac4_critical_manager_approval():
    """AC4: CRITICAL risk → MANAGER approval, status=PENDING."""
    task = ExecutionTask(
        creative_id="c1",
        action_type=ActionType.SCALE.value,
        risk_level="CRITICAL",
        budget_change={"before": 100.0, "after": 500.0},
    )
    gate = ApprovalGate()
    decision = gate.check(task)

    assert decision.approval_level == ApprovalLevel.MANAGER.value
    assert decision.status == ApprovalStatus.PENDING.value
    assert "CRITICAL" in decision.reason


# ═══════════════════════════════════════════════════════════
# AC5 — Approval workflow: PENDING → approve → APPROVED
# ═══════════════════════════════════════════════════════════

def test_ac5_workflow_approve():
    """AC5: ApprovalWorkflow.create_request → approve → status=APPROVED."""
    workflow = ApprovalWorkflow()
    task = ExecutionTask(creative_id="c1", risk_level="WARNING")

    req = workflow.create_request(task, reason="test approval")
    assert req.status == ApprovalStatus.PENDING.value

    updated = workflow.approve(req.request_id, approved_by="ops_lead")
    assert updated is not None
    assert updated.status == ApprovalStatus.APPROVED.value
    assert updated.approved_by == "ops_lead"


# ═══════════════════════════════════════════════════════════
# AC6 — Reject flow: PENDING → reject → REJECTED
# ═══════════════════════════════════════════════════════════

def test_ac6_workflow_reject():
    """AC6: ApprovalWorkflow.create_request → reject → status=REJECTED."""
    workflow = ApprovalWorkflow()
    task = ExecutionTask(creative_id="c1", risk_level="WARNING")

    req = workflow.create_request(task, reason="test reject")
    assert req.status == ApprovalStatus.PENDING.value

    updated = workflow.reject(req.request_id)
    assert updated is not None
    assert updated.status == ApprovalStatus.REJECTED.value


# ═══════════════════════════════════════════════════════════
# AC7 — Expiration: PENDING → expire → EXPIRED
# ═══════════════════════════════════════════════════════════

def test_ac7_workflow_expire():
    """AC7: ApprovalWorkflow.create_request → expire → status=EXPIRED."""
    workflow = ApprovalWorkflow()
    task = ExecutionTask(creative_id="c1", risk_level="WARNING")

    req = workflow.create_request(task, reason="test expire")
    assert req.status == ApprovalStatus.PENDING.value

    updated = workflow.expire(req.request_id)
    assert updated is not None
    assert updated.status == ApprovalStatus.EXPIRED.value


# ═══════════════════════════════════════════════════════════
# AC8 — Execution blocking
# ═══════════════════════════════════════════════════════════

def test_ac8_execution_blocking():
    """AC8: PENDING approval blocks execution (task never reaches EXECUTING)."""
    engine = ExecutionEngine()
    task = ExecutionTask(
        creative_id="c1",
        action_type=ActionType.SCALE.value,
        risk_level="WARNING",
        budget_change={"before": 100.0, "after": 200.0},
    )
    engine._tasks[task.task_id] = task

    result = engine.execute(task)

    # Task should be blocked at PENDING_APPROVAL
    assert task.status == ExecutionStatus.PENDING_APPROVAL.value
    assert result.status == ExecutionStatus.PENDING_APPROVAL.value

    # Must NOT have reached EXECUTING
    events = engine.get_events_for_task(task.task_id)
    executing_events = [e for e in events if e.new_state == ExecutionStatus.EXECUTING.value]
    assert len(executing_events) == 0


def test_ac8_execution_unblocks_after_approval():
    """AC8b: After manual approval, task can proceed to COMPLETED."""
    engine = ExecutionEngine()
    task = ExecutionTask(
        creative_id="c1",
        action_type=ActionType.SCALE.value,
        risk_level="WARNING",
        budget_change={"before": 100.0, "after": 200.0},
    )
    engine._tasks[task.task_id] = task

    # First execution blocked
    result = engine.execute(task)
    assert task.status == ExecutionStatus.PENDING_APPROVAL.value

    # Approve via engine
    engine.approve_task(task.task_id, approved_by="ops_lead")
    assert task.status == ExecutionStatus.APPROVED.value

    # Re-execute
    result2 = engine.execute(task)
    assert result2.status == ExecutionStatus.COMPLETED.value


# ═══════════════════════════════════════════════════════════
# AC9 — Architecture isolation
# ═══════════════════════════════════════════════════════════

def test_ac9_no_e995_imports():
    """AC9: Approval Gate must NOT import E9.9.5 decision layer modules."""
    import market_ops.execution_runtime.approval_gate as ag_module
    import market_ops.execution_runtime.approval_workflow as aw_module
    import market_ops.execution_runtime.execution_engine as ee_module

    forbidden = ["scale_engine", "risk_controller", "portfolio_manager", "winner_detector", "kill_engine"]

    for mod in [ag_module, aw_module, ee_module]:
        source = mod.__file__ or ""
        # Check module globals for any forbidden imports
        for name in dir(mod):
            if name.startswith("_"):
                continue
            for f in forbidden:
                assert f not in name.lower(), f"Forbidden import '{f}' found in {mod.__name__}"


def test_ac9_package_imports_allowed():
    """AC9b: All execution_runtime internal imports are allowed."""
    from market_ops.execution_runtime import (
        ApprovalGate, ApprovalWorkflow, ApprovalDecision,
        ApprovalRequest, ApprovalStatus, ApprovalLevel,
        ExecutionEngine, ExecutionTask, ExecutionStatus,
    )
    # If import succeeds, AC passes
    assert True
