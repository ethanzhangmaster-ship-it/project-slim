"""P2.6.7 — Recovery Escalation 验收（Test6 Rollback Failure）。

覆盖：
- EscalationManager 生成工单 + 推进 incident -> ESCALATED
- HIGH+ 工单接 P2.3 审批工作流（approval_id 回填）
- CRITICAL 工单 halt_automation=True
- Jsonl/InMemory store：open / resolve / latest-wins / automation_halted
- 推荐动作缺省生成
"""

import pytest

from src.execution.recovery.escalation import (
    EscalationManager,
    InMemoryEscalationStore,
    JsonlEscalationStore,
)
from src.execution.recovery.models import (
    INCIDENT_ESCALATED,
    RecoveryIncident,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
)


class FakeApprovalWorkflow:
    """P2.3 审批工作流替身：submit -> 返回带 approval_id 的对象。"""

    def __init__(self):
        self.submitted = []

    def submit(self, request):
        class _Req:
            approval_id = "ap_123"
        self.submitted.append(request)
        return _Req()


def _incident(status="PLANNED", **kw):
    return RecoveryIncident(execution_id="exe_1", action="disable_network",
                            provider="max", status=status, **kw)


def test_escalate_creates_ticket_and_advances_incident():
    store = InMemoryEscalationStore()
    mgr = EscalationManager(store=store)
    inc = _incident()
    ticket = mgr.escalate(inc, SEVERITY_HIGH, "need human", request=None)
    assert ticket.severity == SEVERITY_HIGH
    assert ticket.halt_automation is False
    assert inc.status == INCIDENT_ESCALATED
    assert len(store.all()) == 1


def test_escalate_high_submits_to_approval_workflow():
    store = InMemoryEscalationStore()
    wf = FakeApprovalWorkflow()
    mgr = EscalationManager(store=store, approval_workflow=wf)
    inc = _incident()
    request = object()  # 任意 request 替身
    ticket = mgr.escalate(inc, SEVERITY_HIGH, "need human", request=request)
    assert ticket.approval_id == "ap_123"
    assert len(wf.submitted) == 1


def test_escalate_low_does_not_submit_approval():
    store = InMemoryEscalationStore()
    wf = FakeApprovalWorkflow()
    mgr = EscalationManager(store=store, approval_workflow=wf)
    inc = _incident()
    mgr.escalate(inc, SEVERITY_LOW, "auto only", request=object())
    assert len(wf.submitted) == 0


def test_critical_ticket_halts_automation():
    store = InMemoryEscalationStore()
    mgr = EscalationManager(store=store)
    inc = _incident()
    ticket = mgr.escalate(inc, SEVERITY_CRITICAL, "boom", request=None)
    assert ticket.halt_automation is True
    assert mgr.automation_halted() is True
    assert store.automation_halted() is True


def test_non_critical_does_not_halt():
    store = InMemoryEscalationStore()
    mgr = EscalationManager(store=store)
    inc = _incident()
    mgr.escalate(inc, SEVERITY_HIGH, "x", request=None)
    assert mgr.automation_halted() is False


def test_store_resolve_clears_halt():
    store = InMemoryEscalationStore()
    mgr = EscalationManager(store=store)
    inc = _incident()
    ticket = mgr.escalate(inc, SEVERITY_CRITICAL, "boom", request=None)
    assert mgr.automation_halted() is True
    mgr.resolve(ticket.ticket_id, "ops", "fixed")
    assert mgr.automation_halted() is False


def test_store_latest_wins_on_resolve():
    store = InMemoryEscalationStore()
    mgr = EscalationManager(store=store)
    inc = _incident()
    ticket = mgr.escalate(inc, SEVERITY_CRITICAL, "boom", request=None)
    mgr.resolve(ticket.ticket_id, "ops", "fixed")
    merged = {t["ticket_id"]: t for t in store.all()}
    assert merged[ticket.ticket_id]["record_status"] == "resolved"
    assert merged[ticket.ticket_id]["resolved_by"] == "ops"


def test_default_recommendation_generated():
    store = InMemoryEscalationStore()
    mgr = EscalationManager(store=store)
    inc = _incident()
    ticket = mgr.escalate(inc, SEVERITY_HIGH, "x", request=None)
    assert ticket.recommended_action  # 非空


def test_critical_recommendation_mentions_halt():
    store = InMemoryEscalationStore()
    mgr = EscalationManager(store=store)
    inc = _incident()
    ticket = mgr.escalate(inc, SEVERITY_CRITICAL, "x", request=None)
    assert "HALT" in ticket.recommended_action.upper()


def test_jsonl_store_roundtrip(tmp_path):
    path = tmp_path / "escalations.jsonl"
    store = JsonlEscalationStore(str(path))
    mgr = EscalationManager(store=store)
    inc = _incident()
    ticket = mgr.escalate(inc, SEVERITY_CRITICAL, "boom", request=None)
    assert path.exists()
    assert store.automation_halted() is True
    mgr.resolve(ticket.ticket_id, "ops", "fixed")
    assert store.automation_halted() is False


def test_elevation_incident_only_allows_valid_transition():
    # PLANNED -> ESCALATED 合法；已是 ESCALATED 再 escalated 不应崩溃
    store = InMemoryEscalationStore()
    mgr = EscalationManager(store=store)
    inc = _incident(status=INCIDENT_ESCALATED)
    ticket = mgr.escalate(inc, SEVERITY_HIGH, "x", request=None)
    assert inc.status == INCIDENT_ESCALATED
    assert ticket is not None
