"""P3.2 — Sections 测试：各 section 数据装配（纯 READ，不重算）。"""
from __future__ import annotations

from types import SimpleNamespace

from src.ceo_intelligence.daily_operator.models import (
    ActionKind,
    CompanyStatus,
    DailyActionItem,
    GamePriority,
    OperatorDayRecord,
)

from src.operator.report.sections import (
    build_execution_summary,
    build_health_summary,
    build_learning,
    build_opportunities,
    build_risks,
)


def _company(**kw):
    base = dict(
        game_count=8, total_revenue=1000.0, total_dau=3000,
        total_spend=100.0, avg_confidence=0.6, at_risk=["g2"],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _daily(status=CompanyStatus.HEALTHY, record=None, actions=None):
    return SimpleNamespace(
        company_status=status,
        date="2026-07-30",
        summary={"real_api_called": False},
        record=record,
        actions=actions or [],
    )


class TestHealthSummary:
    def test_basic_mapping(self):
        comp = _company()
        rec = OperatorDayRecord(
            date="2026-07-30", executed=2, approved=1, blocked=1,
            observed=0, company_status="healthy",
        )
        hs = build_health_summary(comp, _daily(record=rec), record=rec)
        assert hs.game_count == 8
        assert hs.total_revenue == 1000.0
        assert hs.total_dau == 3000
        assert hs.auto_count == 2
        assert hs.approval_count == 1
        assert hs.blocked_count == 1
        assert hs.company_status == "healthy"
        assert hs.status_label.startswith("🟢")

    def test_no_company_safe(self):
        hs = build_health_summary(None, _daily(), record=None)
        assert hs.game_count == 0
        assert hs.auto_count == 0


class TestOpportunities:
    def test_mapping(self):
        pri = [
            GamePriority(1, "g1", "ua_scale", "收入下滑",
                        opportunity_type="ua_scale", decision_type="execute",
                        gate="pass", priority_score_value=0.5, impact=0.12,
                        confidence=0.9, urgency=0.8, sim_score=1.0),
        ]
        ops = build_opportunities(pri)
        assert len(ops) == 1
        assert ops[0].rank == 1
        assert ops[0].game_id == "g1"
        assert ops[0].priority_score == 0.5
        assert ops[0].sim_gate == "PASS"

    def test_empty(self):
        assert build_opportunities([]) == []


class TestRisks:
    def _exec_report(self, warnings=("w1",), health="yellow"):
        return SimpleNamespace(warnings=list(warnings), health_level=health)

    def test_warnings_and_at_risk(self):
        comp = _company(at_risk=["g2"])
        daily = _daily(actions=[])
        risks = build_risks(comp, daily, self._exec_report(), recoveries=[])
        titles = [r.title for r in risks]
        assert "执行告警" in titles
        assert "风险游戏名单" in titles
        assert any("g2" in r.detail for r in risks)

    def test_block_action_creates_risk(self):
        comp = _company(at_risk=[])
        daily = _daily(actions=[
            DailyActionItem(kind=ActionKind.BLOCK, game_id="g3",
                            action="ua_stop_loss", detail="负期望闸门",
                            decision_audit_id="d3", opportunity_type="ua_stop_loss"),
        ])
        risks = build_risks(comp, daily, None, recoveries=[])
        assert any(r.title == "模拟闸门阻断" for r in risks)

    def test_escalation_is_critical(self):
        comp = _company(at_risk=[])
        rec = [SimpleNamespace(status="escalated", incident_id="inc9"),
               SimpleNamespace(status="recovered", incident_id="inc8")]
        risks = build_risks(comp, _daily(), None, recoveries=rec)
        crit = [r for r in risks if r.level == "critical"]
        assert any("inc9" in r.detail for r in crit)

    def test_no_risk_placeholder(self):
        risks = build_risks(_company(at_risk=[]), _daily(actions=[]), None, [])
        assert risks[0].level == "info"


class TestLearning:
    def test_combines_exec_and_patterns(self):
        er = SimpleNamespace(learnings=["l1", "l2"])
        out = build_learning(er, patterns=["p1"])
        assert out == ["l1", "l2", "p1"]

    def test_placeholder_when_empty(self):
        out = build_learning(None, patterns=None)
        assert len(out) == 1
        assert "无新学习点" in out[0]


class TestExecutionSummary:
    def test_mapping_and_recovery_counts(self):
        er = SimpleNamespace(
            total_executions=3, success=2, failed=1, rollback=0,
            blocked=0, health_level="yellow", warnings=["ww"],
        )
        rec = [SimpleNamespace(status="recovered"), SimpleNamespace(status="escalated")]
        es = build_execution_summary(er, recoveries=rec, real_api_called=False)
        assert es.total_executions == 3
        assert es.success == 2
        assert es.failed == 1
        assert es.recovered == 1
        assert es.escalated == 1
        assert es.real_api_called is False

    def test_none_exec_report(self):
        es = build_execution_summary(None, recoveries=[], real_api_called=True)
        assert es.total_executions == 0
        assert es.real_api_called is True
