"""P2.6.2 — FailureClassifier 验收（Test1 Classification）。

覆盖四类故障 + 未知：
- Provider Timeout -> PROVIDER_TIMEOUT / RETRY / LOW
- Authentication (401) -> AUTH_FAILURE / ESCALATE / HIGH
- State Drift        -> STATE_DRIFT / RECONCILE / MEDIUM
- Rollback Failure    -> ROLLBACK_FAILED / EMERGENCY_ESCALATE / CRITICAL
- Unknown            -> UNKNOWN / ESCALATE / HIGH (低置信度 0.3)
"""

import pytest

from src.execution.recovery.classifier import FailureClassifier
from src.execution.recovery.models import (
    FAILURE_AUTH,
    FAILURE_ROLLBACK_FAILED,
    FAILURE_STATE_DRIFT,
    FAILURE_TIMEOUT,
    FAILURE_UNKNOWN,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    TREATMENT_EMERGENCY_ESCALATE,
    TREATMENT_ESCALATE,
    TREATMENT_RECONCILE,
    TREATMENT_RETRY,
)
from tests.p2_6.conftest import (
    AlertStub,
    make_failed_outcome,
    make_outcome,
    make_request,
)


@pytest.fixture
def classifier():
    return FailureClassifier()


def test_classify_timeout_retry_low(classifier):
    outcome = make_failed_outcome("timeout")
    request = make_request(action="disable_network", risk=0.3)
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_TIMEOUT
    assert c.treatment == TREATMENT_RETRY
    assert c.severity == SEVERITY_LOW
    assert c.confidence == 1.0
    assert c.requires_escalation is False


def test_classify_auth_escalate_high(classifier):
    outcome = make_failed_outcome("auth")
    request = make_request(action="pause_campaign", risk=0.4)
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_AUTH
    assert c.treatment == TREATMENT_ESCALATE
    assert c.severity == SEVERITY_HIGH
    assert c.requires_escalation is True


def test_classify_drift_reconcile_medium(classifier):
    outcome = make_failed_outcome("drift")
    request = make_request(action="disable_network", risk=0.3)
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_STATE_DRIFT
    assert c.treatment == TREATMENT_RECONCILE
    assert c.severity == SEVERITY_MEDIUM
    assert c.requires_escalation is False


def test_classify_rollback_emergency_critical(classifier):
    outcome = make_failed_outcome("rollback")
    request = make_request(action="disable_network", risk=0.3)
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_ROLLBACK_FAILED
    assert c.treatment == TREATMENT_EMERGENCY_ESCALATE
    assert c.severity == SEVERITY_CRITICAL
    assert c.requires_escalation is True


def test_classify_unknown_escalate_low_confidence(classifier):
    outcome = make_failed_outcome("unknown")
    request = make_request(action="disable_network", risk=0.3)
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_UNKNOWN
    assert c.treatment == TREATMENT_ESCALATE
    assert c.severity == SEVERITY_HIGH
    assert c.confidence == 0.3
    assert c.requires_escalation is True


def test_classify_priority_rollback_over_timeout(classifier):
    # 回滚失败即使带 timeout 文本也应优先判为回滚失败
    outcome = make_failed_outcome("rollback", error="connection timeout then rollback failed")
    request = make_request()
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_ROLLBACK_FAILED
    assert c.severity == SEVERITY_CRITICAL


def test_classify_priority_auth_over_timeout(classifier):
    outcome = make_failed_outcome("auth", error="401 unauthorized and timeout")
    request = make_request()
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_AUTH


def test_classify_drift_via_alert_drifted_flag(classifier):
    # 无 after_state 漂移，但 Monitor 告警声称漂移
    outcome = make_outcome(
        "FAILED", provider="meta", action="pause_campaign", error="ok-ish",
    )
    alert = AlertStub(drifted=True)
    request = make_request(action="pause_campaign")
    c = classifier.classify(outcome, request=request, alert=alert)
    assert c.failure_type == FAILURE_STATE_DRIFT
    assert c.treatment == TREATMENT_RECONCILE


def test_classify_drift_via_alert_message(classifier):
    outcome = make_outcome("FAILED", error="everything fine")
    alert = AlertStub(message="detected state drift between intended and actual")
    request = make_request()
    c = classifier.classify(outcome, request=request, alert=alert)
    assert c.failure_type == FAILURE_STATE_DRIFT


def test_classify_rollback_via_escalated_flag(classifier):
    # P2.4 Rule5 把 escalated 置 True
    outcome = make_failed_outcome("timeout")
    outcome.escalated = True
    request = make_request()
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_ROLLBACK_FAILED
    assert c.severity == SEVERITY_CRITICAL


def test_classify_rollback_via_verdict_escalated(classifier):
    outcome = make_outcome(
        "ESCALATED", error="something went wrong", provider="max",
        action="disable_network",
    )
    request = make_request(action="disable_network")
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_ROLLBACK_FAILED


def test_classify_advances_incident_to_classified(classifier):
    outcome = make_failed_outcome("timeout")
    request = make_request()
    incident = None
    # 用 from_outcome 预建 incident，传入让 classifier 推进状态机
    from src.execution.recovery.models import RecoveryIncident
    incident = RecoveryIncident.from_outcome(outcome, request)
    assert incident.status == "DETECTED"
    classifier.classify(outcome, request=request, incident=incident)
    assert incident.status == "CLASSIFIED"
    assert incident.failure_type == FAILURE_TIMEOUT
    assert incident.severity == SEVERITY_LOW


def test_classify_5xx_is_timeout(classifier):
    outcome = make_failed_outcome("timeout", error="500 Internal Server Error")
    request = make_request()
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_TIMEOUT


def test_classify_rate_limit_is_timeout(classifier):
    outcome = make_failed_outcome("timeout", error="429 Too Many Requests")
    request = make_request()
    c = classifier.classify(outcome, request=request)
    assert c.failure_type == FAILURE_TIMEOUT
