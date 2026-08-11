"""P3.2 — 模型层测试：CEODailyReport / CEOAction 序列化与三态枚举。"""
from __future__ import annotations

import pytest

from src.operator.report.models import (
    ACTION_STATE_TITLE,
    ActionState,
    CEOAction,
    CEOActionStatus,
    CEODailyReport,
    ExecutionSummary,
    HealthSummary,
    OpportunityItem,
    RiskItem,
)
from src.ceo_intelligence.daily_operator.models import CompanyStatus


def _action(mode: ActionState, status: CEOActionStatus, aid="cea-000") -> CEOAction:
    return CEOAction(
        action_id=aid,
        game_id="g1",
        action_type="ua_scale",
        source="e17.3_decision+e17.8_sim+p2.4_execution",
        priority=0.1234,
        execution_mode=mode,
        status=status,
        explanation="已自动执行：ua_scale ｜ 预期收益 +12.0%，置信 95%，风险 10%。",
    )


def _report() -> CEODailyReport:
    return CEODailyReport(
        report_id="ceo-2026-07-30",
        date="2026-07-30",
        health_summary=HealthSummary(
            company_status="healthy",
            status_label="🟢 健康",
            game_count=8,
            total_revenue=1000.0,
            total_dau=3000,
            total_spend=100.0,
            avg_confidence=0.6,
            at_risk=["g2"],
            auto_count=2,
            approval_count=1,
            blocked_count=1,
            observed_count=0,
        ),
        opportunities=[
            OpportunityItem(1, "g1", "ua_scale", "ua_scale", 0.5, 0.12, 0.9, 0.8, "PASS")
        ],
        actions=[
            _action(ActionState.AUTO, CEOActionStatus.EXECUTED),
            _action(ActionState.APPROVAL, CEOActionStatus.AWAITING_APPROVAL, "cea-001"),
            _action(ActionState.BLOCKED, CEOActionStatus.PREVENTED, "cea-002"),
        ],
        risks=[RiskItem("warn", "风险游戏名单", "g2")],
        learning_summary=["（今日无新学习点，经验回流待真实执行累积）"],
        execution_summary=ExecutionSummary(
            total_executions=2, success=2, failed=0, rollback=0,
            blocked=0, health_level="green", warnings=[],
        ),
    )


class TestEnums:
    def test_action_state_values(self):
        assert ActionState.AUTO.value == "auto"
        assert ActionState.APPROVAL.value == "approval"
        assert ActionState.BLOCKED.value == "blocked"

    def test_action_status_values(self):
        assert CEOActionStatus.EXECUTED.value == "executed"
        assert CEOActionStatus.AWAITING_APPROVAL.value == "awaiting"
        assert CEOActionStatus.PREVENTED.value == "prevented"

    def test_state_title_mapping(self):
        assert ACTION_STATE_TITLE["auto"].startswith("✅")
        assert ACTION_STATE_TITLE["approval"].startswith("🖐")
        assert ACTION_STATE_TITLE["blocked"].startswith("⛔")


class TestCEOActionRoundTrip:
    def test_roundtrip(self):
        a = _action(ActionState.AUTO, CEOActionStatus.EXECUTED)
        d = a.to_dict()
        assert d["execution_mode"] == "auto"
        assert d["status"] == "executed"
        a2 = CEOAction.from_dict(d)
        assert a2 == a
        assert a2.execution_mode == ActionState.AUTO
        assert a2.status == CEOActionStatus.EXECUTED


class TestCEODailyReportRoundTrip:
    def test_roundtrip(self):
        r = _report()
        d = r.to_dict()
        assert d["report_id"] == "ceo-2026-07-30"
        assert d["company_status"] == "healthy"
        assert len(d["actions"]) == 3
        assert d["execution_summary"]["total_executions"] == 2
        r2 = CEODailyReport.from_dict(d)
        assert r2.report_id == r.report_id
        assert r2.date == r.date
        assert len(r2.actions) == 3
        assert r2.actions[0].execution_mode == ActionState.AUTO
        assert r2.health_summary.game_count == 8

    def test_top_level_company_status_mirrors_health(self):
        r = _report()
        assert r.to_dict()["company_status"] == r.health_summary.company_status


class TestReportFilters:
    def test_auto_filter(self):
        r = _report()
        assert len(r.auto_actions) == 1
        assert all(a.execution_mode == ActionState.AUTO for a in r.auto_actions)

    def test_approval_filter(self):
        r = _report()
        assert len(r.approval_actions) == 1

    def test_blocked_filter(self):
        r = _report()
        assert len(r.blocked_actions) == 1

    def test_real_api_default_false(self):
        r = _report()
        assert r.real_api_called is False

    def test_sections_roundtrip(self):
        r = _report()
        assert HealthSummary.from_dict(r.health_summary.to_dict()) == r.health_summary
        assert OpportunityItem.from_dict(
            r.opportunities[0].to_dict()
        ) == r.opportunities[0]
        assert RiskItem.from_dict(r.risks[0].to_dict()) == r.risks[0]
        assert ExecutionSummary.from_dict(
            r.execution_summary.to_dict()
        ) == r.execution_summary
