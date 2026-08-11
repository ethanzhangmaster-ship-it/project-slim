"""P2.3.1 ApprovalRequest + P2.3.7 ExecutionAuthorization model tests."""

import pytest

from src.execution.approval.models import (
    ApprovalRequest,
    ExecutionAuthorization,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    impact_float,
    risk_category,
)


def _make_request(**overrides):
    base = dict(
        execution_request_id="req_abc",
        intent_id="int_abc",
        action="pause_campaign",
        domain="ua",
        target="p04",
        risk_level=RISK_MEDIUM,
        expected_impact=0.2,
        confidence=0.8,
        requested_by="ceo_agent",
    )
    base.update(overrides)
    return ApprovalRequest(**base)


class TestApprovalRequest:
    def test_defaults_pending_with_generated_id(self):
        req = _make_request()
        assert req.status == STATUS_PENDING
        assert req.approval_id.startswith("apr_")
        assert req.created_at
        assert req.resolved_at is None
        assert req.is_pending
        assert not req.is_approved
        assert not req.is_terminal

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            _make_request(status="WHATEVER")

    def test_to_from_dict_roundtrip(self):
        req = _make_request(status=STATUS_APPROVED)
        restored = ApprovalRequest.from_dict(req.to_dict())
        assert restored.approval_id == req.approval_id
        assert restored.execution_request_id == "req_abc"
        assert restored.action == "pause_campaign"
        assert restored.status == STATUS_APPROVED
        assert abs(restored.confidence - 0.8) < 1e-6

    def test_terminal_statuses(self):
        req = _make_request(status=STATUS_REJECTED)
        assert req.is_terminal


class TestRiskHelpers:
    def test_risk_category_bounds(self):
        assert risk_category(0.1) == RISK_LOW
        assert risk_category(0.3) == RISK_MEDIUM
        assert risk_category(0.59) == RISK_MEDIUM
        assert risk_category(0.6) == RISK_HIGH
        assert risk_category("bad") == RISK_HIGH

    def test_impact_float(self):
        assert abs(impact_float("0.5") - 0.5) < 1e-6
        assert abs(impact_float(None) - 0.0) < 1e-6
        assert abs(impact_float({"a": 1}) - 0.0) < 1e-6


class TestExecutionAuthorization:
    def test_defaults_ttl_24h(self):
        auth = ExecutionAuthorization(
            approval_id="apr_1", approved_by="ethan", allowed_action="pause_campaign"
        )
        assert auth.approved_at
        assert auth.expires_at > auth.approved_at
        assert not auth.is_expired()

    def test_allows_action_match(self):
        auth = ExecutionAuthorization(
            approval_id="apr_1", approved_by="ethan", allowed_action="pause_campaign"
        )
        assert auth.allows("pause_campaign")
        assert not auth.allows("scale_budget")
        assert not auth.allows("")

    def test_expired_token(self):
        auth = ExecutionAuthorization(
            approval_id="apr_1",
            approved_by="ethan",
            allowed_action="pause_campaign",
            approved_at="2026-07-01T00:00:00Z",
            expires_at="2026-07-02T00:00:00Z",
        )
        assert auth.is_expired(now="2026-07-03T00:00:00Z")
        assert not auth.is_expired(now="2026-07-01T12:00:00Z")

    def test_to_from_dict_roundtrip(self):
        auth = ExecutionAuthorization(
            approval_id="apr_1", approved_by="ethan", allowed_action="pause_campaign"
        )
        restored = ExecutionAuthorization.from_dict(auth.to_dict())
        assert restored.approval_id == "apr_1"
        assert restored.allowed_action == "pause_campaign"
        assert restored.expires_at == auth.expires_at
