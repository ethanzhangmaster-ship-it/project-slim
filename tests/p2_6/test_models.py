"""P2.6.1 — RecoveryIncident / FailureClassification / RecoveryPlan /
RecoveryResult / EscalationTicket / RecoveryExperienceRecord 模型验收。
"""

import pytest

from src.execution.recovery.models import (
    EscalationTicket,
    FailureClassification,
    IllegalIncidentTransitionError,
    INCIDENT_CLOSED,
    INCIDENT_CLASSIFIED,
    INCIDENT_DETECTED,
    INCIDENT_ESCALATED,
    INCIDENT_PLANNED,
    INCIDENT_RECOVERING,
    INCIDENT_VERIFIED,
    RecoveryAttempt,
    RecoveryExperienceRecord,
    RecoveryIncident,
    RecoveryPlan,
    RecoveryResult,
    RECOVERY_ESCALATED,
    RECOVERY_NOT_RECOVERED,
    RECOVERY_RECOVERED,
    RECOVERY_SKIPPED,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    STRATEGY_ESCALATION,
    STRATEGY_RETRY,
    TREATMENT_EMERGENCY_ESCALATE,
    TREATMENT_ESCALATE,
    TREATMENT_RECONCILE,
    TREATMENT_RETRY,
    VerificationResult,
    VERIFY_NOT_RECOVERED,
    VERIFY_RECOVERED,
    VERIFY_UNVERIFIABLE,
    reward_for,
    severity_rank,
)
from tests.p2_6.conftest import make_failed_outcome, make_outcome, make_request


# ---------------------------------------------------------------------------
# RecoveryIncident 状态机
# ---------------------------------------------------------------------------

def test_incident_defaults_filled():
    inc = RecoveryIncident(execution_id="exe_1")
    assert inc.incident_id.startswith("inc_")
    assert inc.status == INCIDENT_DETECTED
    assert inc.detected_at  # ISO
    assert inc.history == [(INCIDENT_DETECTED, inc.detected_at)]


def test_incident_valid_status_values():
    assert set(RecoveryIncident.__dataclass_fields__)  # sanity
    inc = RecoveryIncident(execution_id="exe_1", status=INCIDENT_PLANNED)
    assert inc.status == INCIDENT_PLANNED


def test_incident_invalid_status_raises():
    with pytest.raises(ValueError):
        RecoveryIncident(execution_id="exe_1", status="BOGUS")


def test_incident_invalid_failure_type_raises():
    with pytest.raises(ValueError):
        RecoveryIncident(execution_id="exe_1", failure_type="NOPE")


def test_incident_invalid_severity_raises():
    with pytest.raises(ValueError):
        RecoveryIncident(execution_id="exe_1", severity="EXTREME")


def test_incident_transition_happy_path():
    inc = RecoveryIncident(execution_id="exe_1")
    assert inc.status == INCIDENT_DETECTED
    inc.transition(INCIDENT_CLASSIFIED)
    inc.transition(INCIDENT_PLANNED)
    inc.transition(INCIDENT_RECOVERING)
    inc.transition(INCIDENT_VERIFIED)
    inc.transition(INCIDENT_CLOSED)
    assert inc.status == INCIDENT_CLOSED
    assert inc.is_terminal


def test_incident_illegal_transition_raises():
    inc = RecoveryIncident(execution_id="exe_1")
    with pytest.raises(IllegalIncidentTransitionError):
        # DETECTED 不能直接到 PLANNED
        inc.transition(INCIDENT_PLANNED)


def test_incident_terminal_no_further_transition():
    inc = RecoveryIncident(execution_id="exe_1", status=INCIDENT_CLOSED)
    with pytest.raises(IllegalIncidentTransitionError):
        inc.transition(INCIDENT_DETECTED)


def test_incident_from_outcome_extracts_fields():
    outcome = make_failed_outcome("timeout", action="disable_network",
                                  target="merge_witch", provider="max")
    request = make_request(action="disable_network", target="merge_witch", risk=0.3)
    inc = RecoveryIncident.from_outcome(outcome, request)
    assert inc.execution_id  # from context
    assert inc.action == "disable_network"
    assert inc.target == "merge_witch"
    assert inc.provider == "max"
    assert inc.mode == "production"
    assert "timeout" in inc.error.lower()
    assert inc.status == INCIDENT_DETECTED


def test_incident_roundtrip():
    inc = RecoveryIncident(execution_id="exe_1", action="pause_campaign",
                           provider="meta", severity=SEVERITY_HIGH)
    d = inc.to_dict()
    inc2 = RecoveryIncident.from_dict(d)
    assert inc2.incident_id == inc.incident_id
    assert inc2.action == "pause_campaign"
    assert inc2.severity == SEVERITY_HIGH
    assert inc2.provider == "meta"


# ---------------------------------------------------------------------------
# FailureClassification
# ---------------------------------------------------------------------------

def test_classification_requires_escalation_flag():
    c = FailureClassification(
        incident_id="inc_1", failure_type="AUTH_FAILURE",
        treatment=TREATMENT_ESCALATE, severity=SEVERITY_HIGH,
    )
    assert c.requires_escalation is True
    c2 = FailureClassification(
        incident_id="inc_2", failure_type="PROVIDER_TIMEOUT",
        treatment=TREATMENT_RETRY, severity=SEVERITY_LOW,
    )
    assert c2.requires_escalation is False
    c3 = FailureClassification(
        incident_id="inc_3", failure_type="ROLLBACK_FAILED",
        treatment=TREATMENT_EMERGENCY_ESCALATE, severity=SEVERITY_CRITICAL,
    )
    assert c3.requires_escalation is True


def test_classification_invalid_treatment_raises():
    with pytest.raises(ValueError):
        FailureClassification(
            incident_id="x", failure_type="PROVIDER_TIMEOUT",
            treatment="NOPE", severity=SEVERITY_LOW,
        )


def test_classification_roundtrip():
    c = FailureClassification(
        incident_id="inc_1", failure_type="STATE_DRIFT",
        treatment=TREATMENT_RECONCILE, severity=SEVERITY_MEDIUM,
        confidence=0.7,
    )
    c2 = FailureClassification.from_dict(c.to_dict())
    assert c2.failure_type == "STATE_DRIFT"
    assert c2.treatment == TREATMENT_RECONCILE
    assert c2.confidence == 0.7


# ---------------------------------------------------------------------------
# RecoveryPlan
# ---------------------------------------------------------------------------

def test_plan_escalation_forces_escalate_only():
    p = RecoveryPlan(incident_id="i", strategy=STRATEGY_ESCALATION)
    assert p.escalate_only is True
    assert p.strategy == STRATEGY_ESCALATION


def test_plan_max_attempts_must_be_positive():
    with pytest.raises(ValueError):
        RecoveryPlan(incident_id="i", strategy=STRATEGY_RETRY, max_attempts=0)


def test_plan_invalid_strategy_raises():
    with pytest.raises(ValueError):
        RecoveryPlan(incident_id="i", strategy="TELEPORT")


def test_plan_roundtrip():
    p = RecoveryPlan(
        incident_id="i", strategy=STRATEGY_RETRY, action="disable_network",
        max_attempts=3, backoff=[1.0, 5.0, 30.0], risk_level=0.4,
        expected_state={"status": "PAUSED"},
    )
    p2 = RecoveryPlan.from_dict(p.to_dict())
    assert p2.strategy == STRATEGY_RETRY
    assert p2.max_attempts == 3
    assert p2.backoff == [1.0, 5.0, 30.0]
    assert p2.expected_state == {"status": "PAUSED"}


def test_plan_defaults():
    p = RecoveryPlan(incident_id="i", strategy=STRATEGY_RETRY)
    assert p.plan_id.startswith("rcp_")
    assert p.max_attempts == 1
    assert p.escalate_only is False


# ---------------------------------------------------------------------------
# RecoveryResult / VerificationResult / RecoveryAttempt
# ---------------------------------------------------------------------------

def test_recovery_result_recovered_property():
    r = RecoveryResult(incident_id="i", status=RECOVERY_RECOVERED)
    assert r.recovered is True
    assert r.escalated is False
    r2 = RecoveryResult(incident_id="i", status=RECOVERY_ESCALATED)
    assert r2.escalated is True
    assert r2.recovered is False


def test_recovery_result_invalid_status_raises():
    with pytest.raises(ValueError):
        RecoveryResult(incident_id="i", status="HALF")


def test_recovery_result_has_no_redundant_from_dict():
    # RecoveryResult 作为引擎返回值，序列化只走 to_dict（记忆层只存 status）
    r = RecoveryResult(
        incident_id="i", plan_id="p", status=RECOVERY_NOT_RECOVERED,
        attempts=3, message="exhausted",
    )
    d = r.to_dict()
    assert d["status"] == RECOVERY_NOT_RECOVERED
    assert d["attempts"] == 3
    assert "attempt_log" in d


def test_verification_result_recovered_property():
    v = VerificationResult(incident_id="i", status=VERIFY_RECOVERED)
    assert v.recovered is True
    v2 = VerificationResult(incident_id="i", status=VERIFY_NOT_RECOVERED)
    assert v2.recovered is False
    v3 = VerificationResult(incident_id="i", status=VERIFY_UNVERIFIABLE)
    assert v3.recovered is False


def test_verification_invalid_status_raises():
    with pytest.raises(ValueError):
        VerificationResult(incident_id="i", status="MAYBE")


def test_attempt_roundtrip_defaults():
    a = RecoveryAttempt(attempt=1, waited_seconds=1.0, ok=True, verdict="EXECUTED")
    assert a.started_at  # filled
    d = a.to_dict()
    assert d["attempt"] == 1
    assert d["ok"] is True


# ---------------------------------------------------------------------------
# EscalationTicket（CRITICAL 自动 halt）
# ---------------------------------------------------------------------------

def test_ticket_critical_auto_halts():
    t = EscalationTicket(incident_id="i", severity=SEVERITY_CRITICAL,
                         reason="boom")
    assert t.halt_automation is True


def test_ticket_non_critical_no_halt():
    t = EscalationTicket(incident_id="i", severity=SEVERITY_HIGH, reason="x")
    assert t.halt_automation is False


def test_ticket_roundtrip():
    t = EscalationTicket(incident_id="i", severity=SEVERITY_HIGH, reason="x",
                         approval_id="ap_1")
    t2 = EscalationTicket.from_dict(t.to_dict())
    assert t2.severity == SEVERITY_HIGH
    assert t2.approval_id == "ap_1"


# ---------------------------------------------------------------------------
# RecoveryExperienceRecord + reward_for + severity_rank
# ---------------------------------------------------------------------------

def test_reward_for_table():
    assert reward_for(RECOVERY_RECOVERED) == 0.8
    assert reward_for(RECOVERY_NOT_RECOVERED) == 0.0
    assert reward_for(RECOVERY_ESCALATED) == 0.2
    assert reward_for(RECOVERY_SKIPPED) == 0.0
    assert reward_for("UNKNOWN_STATUS") == 0.0


def test_experience_record_success_flag():
    # 模型本身不自算 reward（由 RecoveryMemoryBridge 通过 reward_for 注入）
    r = RecoveryExperienceRecord(
        failure="PROVIDER_TIMEOUT", action="disable_network",
        recovery=STRATEGY_RETRY, result=RECOVERY_RECOVERED,
    )
    assert r.success is True
    assert r.reward == 0.0  # 默认 0，由 bridge 覆写
    r2 = RecoveryExperienceRecord(
        failure="AUTH_FAILURE", action="pause_campaign",
        recovery=STRATEGY_ESCALATION, result=RECOVERY_ESCALATED,
    )
    assert r2.success is False
    assert r2.reward == 0.0
    # bridge 注入后的 reward 由 reward_for 决定
    from src.execution.recovery.models import reward_for
    assert reward_for(RECOVERY_RECOVERED) == 0.8
    assert reward_for(RECOVERY_ESCALATED) == 0.2


def test_experience_record_roundtrip():
    r = RecoveryExperienceRecord(
        failure="STATE_DRIFT", action="reconcile", recovery="RECONCILE",
        result=RECOVERY_RECOVERED, provider="max", attempts=1,
    )
    r2 = RecoveryExperienceRecord.from_dict(r.to_dict())
    assert r2.failure == "STATE_DRIFT"
    assert r2.success is True
    assert r2.attempts == 1


def test_severity_rank_ordering():
    assert severity_rank(SEVERITY_LOW) < severity_rank(SEVERITY_MEDIUM)
    assert severity_rank(SEVERITY_MEDIUM) < severity_rank(SEVERITY_HIGH)
    assert severity_rank(SEVERITY_HIGH) < severity_rank(SEVERITY_CRITICAL)
    # 未知级别按 HIGH 保守处理
    assert severity_rank("BOGUS") == severity_rank(SEVERITY_HIGH)
