"""P2.6.4 — RecoveryPlanner 验收。

覆盖：
- TIMEOUT + 低风险 -> RETRY 计划（max_attempts=3, backoff=[1,5,30]）
- STATE_DRIFT -> RECONCILE 计划
- AUTH / EMERGENCY -> ESCALATION 计划（escalate_only=True）
- HIGH/CRITICAL severity 强制升级
- 高风险动作（risk>=0.7）即使可重试也升级
- 推进 incident CLASSIFIED -> PLANNED
"""

import pytest

from src.execution.recovery.classifier import FailureClassifier
from src.execution.recovery.models import (
    FAILURE_AUTH,
    FAILURE_ROLLBACK_FAILED,
    FAILURE_STATE_DRIFT,
    FAILURE_TIMEOUT,
    INCIDENT_CLASSIFIED,
    INCIDENT_PLANNED,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    STRATEGY_ESCALATION,
    STRATEGY_RECONCILE,
    STRATEGY_RETRY,
)
from src.execution.recovery.planner import (
    RecoveryPlanner,
    RISK_ESCALATE_THRESHOLD,
)
from src.execution.recovery.models import RecoveryIncident
from tests.p2_6.conftest import make_failed_outcome, make_request


@pytest.fixture
def planner():
    return RecoveryPlanner()


def _classify(kind, request):
    outcome = make_failed_outcome(kind)
    return FailureClassifier().classify(outcome, request=request)


def test_plan_timeout_low_risk_is_retry(planner):
    request = make_request(action="disable_network", risk=0.3)
    c = _classify("timeout", request)
    plan = planner.plan(c, action=request.intent.action, target="merge_witch",
                         provider="max", risk=0.3)
    assert plan.strategy == STRATEGY_RETRY
    assert plan.max_attempts == 3
    assert plan.backoff == [1.0, 5.0, 30.0]
    assert plan.escalate_only is False


def test_plan_drift_is_reconcile(planner):
    request = make_request(action="disable_network", risk=0.3)
    c = _classify("drift", request)
    plan = planner.plan(c, action=request.intent.action, target="merge_witch",
                         provider="max", risk=0.3)
    assert plan.strategy == STRATEGY_RECONCILE
    assert plan.escalate_only is False


def test_plan_auth_is_escalation(planner):
    request = make_request(action="pause_campaign", risk=0.4)
    c = _classify("auth", request)
    plan = planner.plan(c, action=request.intent.action, target="merge_witch",
                         provider="meta", risk=0.4)
    assert plan.strategy == STRATEGY_ESCALATION
    assert plan.escalate_only is True


def test_plan_rollback_is_escalation(planner):
    request = make_request(action="disable_network", risk=0.3)
    c = _classify("rollback", request)
    plan = planner.plan(c, action=request.intent.action, target="merge_witch",
                         provider="max", risk=0.3)
    assert plan.strategy == STRATEGY_ESCALATION
    assert plan.escalate_only is True


def test_plan_high_severity_forces_escalation(planner):
    # TIMEOUT 本身可重试，但若 severity=HIGH 强制升级
    from src.execution.recovery.models import FailureClassification
    c = FailureClassification(
        incident_id="i", failure_type=FAILURE_TIMEOUT, treatment="RETRY",
        severity=SEVERITY_HIGH,
    )
    plan = planner.plan(c, action="disable_network", risk=0.3)
    assert plan.strategy == STRATEGY_ESCALATION
    assert plan.escalate_only is True


def test_plan_critical_severity_forces_escalation(planner):
    from src.execution.recovery.models import FailureClassification
    c = FailureClassification(
        incident_id="i", failure_type=FAILURE_STATE_DRIFT, treatment="RECONCILE",
        severity=SEVERITY_CRITICAL,
    )
    plan = planner.plan(c, action="disable_network", risk=0.3)
    assert plan.strategy == STRATEGY_ESCALATION
    assert plan.escalate_only is True


def test_plan_high_risk_forces_escalation(planner):
    # TIMEOUT + 高风险(0.7) -> 升级（钱类高危不自动重放）
    request = make_request(action="scale_budget", risk=0.7)
    c = _classify("timeout", request)
    plan = planner.plan(c, action=request.intent.action, target="merge_witch",
                         provider="max", risk=0.7)
    assert plan.strategy == STRATEGY_ESCALATION
    assert plan.escalate_only is True


def test_plan_risk_just_below_threshold_still_retries(planner):
    # risk=0.69 < 0.7 -> 仍可重试
    request = make_request(action="disable_network", risk=0.69)
    c = _classify("timeout", request)
    plan = planner.plan(c, action=request.intent.action, target="merge_witch",
                         provider="max", risk=0.69)
    assert plan.strategy == STRATEGY_RETRY
    assert plan.escalate_only is False


def test_risk_threshold_constant():
    assert RISK_ESCALATE_THRESHOLD == 0.7


def test_plan_advances_incident_to_planned(planner):
    request = make_request(action="disable_network", risk=0.3)
    outcome = make_failed_outcome("timeout")
    incident = RecoveryIncident.from_outcome(outcome, request)
    incident.transition(INCIDENT_CLASSIFIED)
    assert incident.status == INCIDENT_CLASSIFIED
    c = FailureClassifier().classify(outcome, request=request, incident=incident)
    planner.plan(c, action=request.intent.action, target="merge_witch",
                 provider="max", risk=0.3, incident=incident)
    assert incident.status == INCIDENT_PLANNED


def test_plan_escalate_reason_recorded(planner):
    request = make_request(action="scale_budget", risk=0.8)
    c = _classify("timeout", request)
    plan = planner.plan(c, action=request.intent.action, target="merge_witch",
                         provider="max", risk=0.8)
    assert "risk" in plan.notes.lower()


def test_plan_rollback_action_carried(planner):
    request = make_request(action="disable_network", risk=0.3)
    c = _classify("rollback", request)
    plan = planner.plan(c, action="disable_network", target="merge_witch",
                         provider="max", risk=0.3, rollback_action="enable_network")
    assert plan.rollback_action == "enable_network"
