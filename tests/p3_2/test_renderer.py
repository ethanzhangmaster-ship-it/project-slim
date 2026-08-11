"""P3.2 — Renderer 测试：决策单 Markdown 结构 + JSON 序列化（确定性）。"""
from __future__ import annotations

import json

from src.operator.report.models import (
    ActionState,
    CEOAction,
    CEOActionStatus,
    CEODailyReport,
    ExecutionSummary,
    HealthSummary,
    OpportunityItem,
    RiskItem,
)
from src.operator.report.renderer import (
    render_actions_json,
    render_markdown,
    render_report_json,
)


def _report() -> CEODailyReport:
    return CEODailyReport(
        report_id="ceo-2026-07-30",
        date="2026-07-30",
        health_summary=HealthSummary(
            company_status="attention", status_label="🟡 需关注",
            game_count=8, total_revenue=1000.0, total_dau=3000,
            total_spend=100.0, avg_confidence=0.6, at_risk=["g2"],
            auto_count=1, approval_count=1, blocked_count=1, observed_count=0,
        ),
        opportunities=[OpportunityItem(
            1, "g1", "ua_scale", "ua_scale", 0.5, 0.12, 0.9, 0.8, "PASS")],
        actions=[
            CEOAction("cea-000", "g1", "ua_scale",
                      "e17.3_decision+e17.8_sim+p2.4_execution", 0.5,
                      ActionState.AUTO, CEOActionStatus.EXECUTED,
                      "已自动执行：ua_scale ｜ 预期收益 +12.0%，置信 95%，风险 10%。"),
            CEOAction("cea-001", "g2", "monetization",
                      "e17.3_decision+p2.3_approval", 0.3,
                      ActionState.APPROVAL, CEOActionStatus.AWAITING_APPROVAL,
                      "等待 CEO 审批：monetization ｜ 风险 60%，置信 80%。"),
            CEOAction("cea-002", "g3", "ua_stop_loss",
                      "e17.8_simulation_gate", 0.2,
                      ActionState.BLOCKED, CEOActionStatus.PREVENTED,
                      "已被模拟闸门阻断：ua_stop_loss ｜ 负期望，模拟闸门阻断"),
        ],
        risks=[RiskItem("warn", "风险游戏名单", "g2"),
               RiskItem("critical", "恢复升级事件", "事件 inc9：已升级人工处理")],
        learning_summary=["🧠 动作 ua_scale：真实执行成功率 100%（n=1）"],
        execution_summary=ExecutionSummary(
            total_executions=1, success=1, failed=0, rollback=0, blocked=0,
            health_level="green", warnings=[], recovered=0, escalated=0,
            real_api_called=False,
        ),
    )


class TestMarkdownStructure:
    def test_title_and_sections(self):
        md = render_markdown(_report())
        assert "# 每日 CEO 决策单 · 2026-07-30" in md
        assert "## 一、今日健康概览" in md
        assert "## 二、今日最大机会" in md
        assert "## 三、今日行动队列" in md
        assert "## 四、风险与注意" in md
        assert "## 五、执行小结" in md
        assert "## 六、今日学习" in md

    def test_three_state_groups_present(self):
        md = render_markdown(_report())
        assert "✅ 已自动执行（AUTO EXECUTE）" in md
        assert "🖐 待你审批（APPROVAL REQUIRED）" in md
        assert "⛔ 已被阻断（BLOCKED）" in md

    def test_action_ids_and_source_visible(self):
        md = render_markdown(_report())
        assert "cea-000" in md and "cea-001" in md and "cea-002" in md
        assert "e17.3_decision+e17.8_sim+p2.4_execution" in md
        assert "e17.3_decision+p2.3_approval" in md
        assert "e17.8_simulation_gate" in md

    def test_explanation_visible(self):
        md = render_markdown(_report())
        assert "已自动执行：ua_scale" in md
        assert "等待 CEO 审批" in md
        assert "已被模拟闸门阻断" in md

    def test_dry_run_discipline_line(self):
        md = render_markdown(_report())
        assert "real_api_called" in md
        assert "DRY_RUN 纪律" in md

    def test_risks_rendered(self):
        md = render_markdown(_report())
        assert "风险游戏名单" in md
        assert "恢复升级事件" in md

    def test_deterministic(self):
        r = _report()
        assert render_markdown(r) == render_markdown(r)


class TestJsonSerialization:
    def test_report_json_keys(self):
        d = json.loads(render_report_json(_report()))
        assert d["report_id"] == "ceo-2026-07-30"
        for k in ("health_summary", "opportunities", "actions",
                 "risks", "learning_summary", "execution_summary"):
            assert k in d
        assert d["company_status"] == "attention"
        assert d["real_api_called"] is False

    def test_actions_json_shape(self):
        arr = json.loads(render_actions_json(_report()))
        assert isinstance(arr, list) and len(arr) == 3
        modes = {a["execution_mode"] for a in arr}
        assert modes == {"auto", "approval", "blocked"}
        for a in arr:
            assert "action_id" in a and "explanation" in a and "status" in a

    def test_json_roundtrip_into_model(self):
        r = _report()
        d = json.loads(render_report_json(r))
        r2 = CEODailyReport.from_dict(d)
        assert r2.report_id == r.report_id
        assert len(r2.actions) == 3
