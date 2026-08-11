"""E13.7.4.4 Agent Reporting — 测试套件.

覆盖:
  - Report Models (AgentReport, ReportSection, ReportMetric, ReportEvidence, ReportQuery)
  - Decision Report (DecisionReportBuilder, create_decision_report)
  - Execution Report (ExecutionReportBuilder, create_execution_report)
  - Health Report (HealthReportBuilder, create_health_report)
  - Learning Report (LearningReportBuilder, create_learning_report)
  - Agent Reporter (AgentReporter, cycle lifecycle, query API, render)
  - Report Store (InMemoryReportStore, FileReportStore, query, stats)
  - Integration (完整 Agent 周期报告)
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.reporting import (
    # Enums
    ReportType,
    ReportFormat,
    ReportStatus,
    # Models
    ReportMetric,
    ReportEvidence,
    ReportSection,
    ReportSummary,
    AgentReport,
    ReportQuery,
    # Decision
    DecisionReportBuilder,
    DecisionEntry,
    DecisionEvidence,
    DecisionHypothesis,
    ObservedMetric,
    create_decision_report,
    # Execution
    ExecutionReportBuilder,
    ExecutionAction,
    ExecutionTask,
    create_execution_report,
    # Health
    HealthReportBuilder,
    create_health_report,
    # Learning
    LearningReportBuilder,
    LearningEntry,
    PatternUpdate,
    MemoryFeedback,
    create_learning_report,
    # Reporter
    AgentReporter,
    create_agent_reporter,
    # Store
    ReportStore,
    InMemoryReportStore,
    FileReportStore,
    create_report_store,
)


# ═══════════════════════════════════════════════════════════════
# Test Report Models
# ═══════════════════════════════════════════════════════════════


class TestReportType:
    """测试 ReportType 枚举."""

    def test_all_types(self):
        assert ReportType.OBSERVATION == "observation"
        assert ReportType.REASONING == "reasoning"
        assert ReportType.DECISION == "decision"
        assert ReportType.EXECUTION == "execution"
        assert ReportType.LEARNING == "learning"
        assert ReportType.HEALTH == "health"

    def test_report_format(self):
        assert ReportFormat.JSON == "json"
        assert ReportFormat.MARKDOWN == "markdown"
        assert ReportFormat.TEXT == "text"
        assert ReportFormat.HTML == "html"

    def test_report_status(self):
        assert ReportStatus.DRAFT == "draft"
        assert ReportStatus.FINAL == "final"
        assert ReportStatus.ARCHIVED == "archived"


class TestReportMetric:
    """测试 ReportMetric."""

    def test_default_creation(self):
        m = ReportMetric(name="ROAS", value=1.5)
        assert m.name == "ROAS"
        assert m.value == 1.5
        assert m.trend == "stable"

    def test_with_trend(self):
        m = ReportMetric(name="CTR", value=0.03, trend="up", change_pct=0.15)
        assert m.trend == "up"
        assert m.change_pct == 0.15

    def test_with_alert(self):
        m = ReportMetric(name="error_rate", value=0.4, threshold=0.3, is_alert=True)
        assert m.is_alert
        assert m.threshold == 0.3

    def test_to_dict(self):
        m = ReportMetric(name="ROAS", value=1.5, unit="", trend="up")
        d = m.to_dict()
        assert d["name"] == "ROAS"
        assert d["value"] == 1.5
        assert d["trend"] == "up"


class TestReportEvidence:
    """测试 ReportEvidence."""

    def test_default_creation(self):
        e = ReportEvidence(source="PatternMemory", reference="similar cases = 18")
        assert e.source == "PatternMemory"
        assert e.confidence == 1.0

    def test_to_dict(self):
        e = ReportEvidence(source="KG", reference="ref", confidence=0.8)
        d = e.to_dict()
        assert d["confidence"] == 0.8


class TestReportSection:
    """测试 ReportSection."""

    def test_default_creation(self):
        s = ReportSection()
        assert s.type == ReportType.OBSERVATION
        assert s.section_id != ""

    def test_custom_creation(self):
        s = ReportSection(
            type=ReportType.DECISION,
            title="Test Decision",
            content="Some content",
            summary="Decision summary",
            confidence=0.85,
        )
        assert s.type == ReportType.DECISION
        assert s.title == "Test Decision"
        assert s.confidence == 0.85

    def test_to_dict(self):
        s = ReportSection(
            type=ReportType.DECISION,
            title="Test",
            content="Content",
            metrics=[ReportMetric(name="ROAS", value=1.5)],
            confidence=0.9,
        )
        d = s.to_dict()
        assert d["type"] == "decision"
        assert len(d["metrics"]) == 1
        assert d["confidence"] == 0.9

    def test_to_markdown(self):
        s = ReportSection(
            type=ReportType.DECISION,
            title="Test Decision",
            content="Decision content",
            summary="Summary text",
            metrics=[ReportMetric(name="ROAS", value=1.5, trend="up")],
            evidence=[ReportEvidence(source="Memory", reference="case 18")],
            confidence=0.85,
        )
        md = s.to_markdown()
        assert "## Test Decision" in md
        assert "**Summary text**" in md
        assert "Decision content" in md
        assert "ROAS" in md
        assert "Memory" in md
        assert "85%" in md

    def test_to_text(self):
        s = ReportSection(
            type=ReportType.DECISION,
            title="Test",
            summary="Summary",
            content="Content",
            metrics=[ReportMetric(name="ROAS", value=1.5)],
            confidence=0.85,
        )
        txt = s.to_text()
        assert "[DECISION]" in txt
        assert "Summary" in txt
        assert "85%" in txt


class TestReportSummary:
    """测试 ReportSummary."""

    def test_default(self):
        s = ReportSummary()
        assert s.total_sections == 0
        assert s.risk_level == "low"

    def test_to_dict(self):
        s = ReportSummary(
            total_sections=5,
            decision_count=2,
            key_findings=["ROAS declined"],
        )
        d = s.to_dict()
        assert d["total_sections"] == 5
        assert d["decision_count"] == 2


class TestAgentReport:
    """测试 AgentReport."""

    def test_default_creation(self):
        r = AgentReport()
        assert r.report_id != ""
        assert r.status == ReportStatus.DRAFT
        assert len(r.sections) == 0

    def test_add_section(self):
        r = AgentReport()
        s = ReportSection(type=ReportType.DECISION, title="Test", confidence=0.8)
        r.add_section(s)
        assert len(r.sections) == 1
        assert r.summary.decision_count == 1
        assert r.overall_confidence == 0.8

    def test_add_multiple_sections(self):
        r = AgentReport()
        r.add_section(ReportSection(type=ReportType.DECISION, confidence=0.8))
        r.add_section(ReportSection(type=ReportType.DECISION, confidence=0.6))
        r.add_section(ReportSection(type=ReportType.EXECUTION, confidence=0.9))
        assert r.summary.total_sections == 3
        assert r.summary.decision_count == 2
        assert r.summary.execution_count == 1
        assert r.overall_confidence == pytest.approx((0.8 + 0.6 + 0.9) / 3)

    def test_get_sections_by_type(self):
        r = AgentReport()
        r.add_section(ReportSection(type=ReportType.DECISION))
        r.add_section(ReportSection(type=ReportType.EXECUTION))
        r.add_section(ReportSection(type=ReportType.DECISION))
        decisions = r.get_sections_by_type(ReportType.DECISION)
        assert len(decisions) == 2

    def test_get_section_by_id(self):
        r = AgentReport()
        s = ReportSection(type=ReportType.DECISION)
        r.add_section(s)
        found = r.get_section_by_id(s.section_id)
        assert found is not None
        assert found.section_id == s.section_id

    def test_get_section_by_id_not_found(self):
        r = AgentReport()
        assert r.get_section_by_id("nonexistent") is None

    def test_finalize(self):
        r = AgentReport()
        r.finalize()
        assert r.status == ReportStatus.FINAL

    def test_archive(self):
        r = AgentReport()
        r.archive()
        assert r.status == ReportStatus.ARCHIVED

    def test_to_dict(self):
        r = AgentReport(agent_id="ua_01", cycle_id="c001")
        r.add_section(ReportSection(type=ReportType.DECISION, confidence=0.8))
        d = r.to_dict()
        assert d["agent_id"] == "ua_01"
        assert d["cycle_id"] == "c001"
        assert len(d["sections"]) == 1

    def test_to_markdown(self):
        r = AgentReport(agent_id="ua_01", cycle_id="c001")
        r.add_section(ReportSection(type=ReportType.DECISION, title="Decision", content="test"))
        md = r.to_markdown()
        assert "# Agent Report" in md
        assert "ua_01" in md
        assert "c001" in md

    def test_to_text(self):
        r = AgentReport(agent_id="ua_01", cycle_id="c001")
        r.add_section(ReportSection(type=ReportType.DECISION, title="Decision", content="test"))
        txt = r.to_text()
        assert "=== Agent Report" in txt
        assert "ua_01" in txt

    def test_from_dict(self):
        r = AgentReport(agent_id="ua_01", cycle_id="c001")
        r.add_section(ReportSection(
            type=ReportType.DECISION,
            title="Test",
            metrics=[ReportMetric(name="ROAS", value=1.5)],
            evidence=[ReportEvidence(source="M", reference="r")],
        ))
        d = r.to_dict()
        r2 = AgentReport.from_dict(d)
        assert r2.agent_id == "ua_01"
        assert len(r2.sections) == 1
        assert r2.sections[0].title == "Test"

    def test_tags_and_metadata(self):
        r = AgentReport(tags=["production", "critical"], metadata={"version": "1.0"})
        assert "production" in r.tags
        assert r.metadata["version"] == "1.0"


class TestReportQuery:
    """测试 ReportQuery."""

    def test_default(self):
        q = ReportQuery()
        assert q.limit == 50
        assert q.offset == 0

    def test_match_agent_id(self):
        q = ReportQuery(agent_id="ua_01")
        r1 = AgentReport(agent_id="ua_01")
        r2 = AgentReport(agent_id="ua_02")
        assert q.match(r1)
        assert not q.match(r2)

    def test_match_cycle_id(self):
        q = ReportQuery(cycle_id="c001")
        r1 = AgentReport(cycle_id="c001")
        r2 = AgentReport(cycle_id="c002")
        assert q.match(r1)
        assert not q.match(r2)

    def test_match_status(self):
        q = ReportQuery(status=ReportStatus.FINAL)
        r1 = AgentReport()
        r1.finalize()
        r2 = AgentReport()
        assert q.match(r1)
        assert not q.match(r2)

    def test_match_tags(self):
        q = ReportQuery(tags=["production"])
        r1 = AgentReport(tags=["production", "critical"])
        r2 = AgentReport(tags=["development"])
        assert q.match(r1)
        assert not q.match(r2)

    def test_match_report_type(self):
        q = ReportQuery(report_type=ReportType.DECISION)
        r1 = AgentReport()
        r1.add_section(ReportSection(type=ReportType.DECISION))
        r2 = AgentReport()
        r2.add_section(ReportSection(type=ReportType.EXECUTION))
        assert q.match(r1)
        assert not q.match(r2)

    def test_match_time_range(self):
        q = ReportQuery(start_time="2026-01-01", end_time="2026-12-31")
        r1 = AgentReport(timestamp="2026-06-15T00:00:00+00:00")
        r2 = AgentReport(timestamp="2025-01-01T00:00:00+00:00")
        assert q.match(r1)
        assert not q.match(r2)


# ═══════════════════════════════════════════════════════════════
# Test Decision Report
# ═══════════════════════════════════════════════════════════════


class TestObservedMetric:
    """测试 ObservedMetric."""

    def test_trend_up(self):
        m = ObservedMetric(name="ROAS", value=2.0, previous_value=1.0)
        assert m.trend == "up"
        assert m.change == 1.0
        assert m.change_pct == 1.0

    def test_trend_down(self):
        m = ObservedMetric(name="ROAS", value=0.5, previous_value=1.0)
        assert m.trend == "down"
        assert m.change_pct == -0.5

    def test_trend_stable(self):
        m = ObservedMetric(name="ROAS", value=1.0, previous_value=1.0)
        assert m.trend == "stable"

    def test_no_previous(self):
        m = ObservedMetric(name="ROAS", value=1.5)
        assert m.trend == "stable"
        assert m.change == 0.0

    def test_threshold_breach(self):
        m = ObservedMetric(name="fatigue", value=0.85, threshold=0.7, threshold_breach=True)
        assert m.threshold_breach

    def test_to_report_metric(self):
        m = ObservedMetric(name="ROAS", value=1.5, previous_value=1.0, unit="")
        rm = m.to_report_metric()
        assert rm.name == "ROAS"
        assert rm.trend == "up"


class TestDecisionReportBuilder:
    """测试 DecisionReportBuilder."""

    def test_build_empty(self):
        builder = DecisionReportBuilder()
        section = builder.build()
        assert section.type == ReportType.DECISION
        assert section.confidence == 0.0

    def test_build_with_observations(self):
        builder = DecisionReportBuilder()
        builder.add_observation("ROAS", 0.53, previous_value=0.75)
        builder.add_observation("CTR", 0.03, previous_value=0.05)
        section = builder.build()
        assert len(section.metrics) == 2
        assert section.metrics[0].name == "ROAS"

    def test_build_with_reasoning(self):
        builder = DecisionReportBuilder()
        builder.add_reasoning("CTR 下降 34%")
        builder.add_reasoning("同 DNA 已运行 12 天")
        section = builder.build()
        assert "CTR" in section.content
        assert "12 天" in section.content

    def test_build_with_hypothesis(self):
        builder = DecisionReportBuilder()
        builder.add_hypothesis("rescue hook 提升 payer rate", 0.75, "5000 impressions")
        section = builder.build()
        assert "rescue hook" in section.content
        assert "75%" in section.content

    def test_build_with_decision(self):
        builder = DecisionReportBuilder()
        entry = DecisionEntry(
            action="CREATE_CREATIVE_VARIANTS",
            target="Witch Merge",
            reason="素材疲劳触发",
            confidence=0.87,
            evidence=[
                DecisionEvidence(
                    source="PatternMemory",
                    description="similar cases = 18",
                    confidence=0.86,
                ),
            ],
            expected_outcome="CTR +15%, ROAS +8%",
            risk_level="low",
        )
        builder.add_decision(entry)
        section = builder.build()
        assert "CREATE_CREATIVE_VARIANTS" in section.content
        assert "Witch Merge" in section.content
        assert "87%" in section.content
        assert section.confidence == 0.87
        assert "Decision: CREATE_CREATIVE_VARIANTS" in section.summary

    def test_build_multiple_decisions(self):
        builder = DecisionReportBuilder()
        builder.add_decision(DecisionEntry(action="A1", target="T1", reason="R1", confidence=0.8))
        builder.add_decision(DecisionEntry(action="A2", target="T2", reason="R2", confidence=0.6))
        section = builder.build()
        assert section.confidence == 0.7

    def test_build_with_evidence(self):
        builder = DecisionReportBuilder()
        ev = DecisionEvidence(source="PatternMemory", description="18 cases", confidence=0.86)
        builder.add_decision(DecisionEntry(
            action="A", target="T", reason="R", confidence=0.8, evidence=[ev],
        ))
        section = builder.build()
        assert len(section.evidence) == 1

    def test_create_decision_report_helper(self):
        section = create_decision_report(
            campaign_name="Test Campaign",
            observations={"ROAS": (0.53, 0.75), "CTR": (0.03, 0.05)},
            reasoning_points=["CTR 下降", "素材疲劳"],
            decisions=[
                {"action": "MUTATE_CREATIVE", "reason": "疲劳", "confidence": 0.87},
            ],
            similar_cases=18,
            success_rate=0.72,
        )
        assert section.type == ReportType.DECISION
        assert len(section.metrics) == 2
        assert "MUTATE_CREATIVE" in section.summary


# ═══════════════════════════════════════════════════════════════
# Test Execution Report
# ═══════════════════════════════════════════════════════════════


class TestExecutionTask:
    """测试 ExecutionTask."""

    def test_default(self):
        t = ExecutionTask(task_id="t1", task_name="Test")
        assert t.success_count == 0
        assert t.success_rate == 1.0

    def test_with_actions(self):
        t = ExecutionTask(task_id="t1", task_name="Test")
        t.actions = [
            ExecutionAction(action_id="a1", action_type="create", target="c1", status="success"),
            ExecutionAction(action_id="a2", action_type="update", target="c2", status="failure"),
            ExecutionAction(action_id="a3", action_type="delete", target="c3", status="success"),
        ]
        assert t.success_count == 2
        assert t.failure_count == 1
        assert t.success_rate == 2 / 3


class TestExecutionReportBuilder:
    """测试 ExecutionReportBuilder."""

    def test_build_empty(self):
        builder = ExecutionReportBuilder()
        section = builder.build()
        assert section.type == ReportType.EXECUTION

    def test_build_with_task(self):
        builder = ExecutionReportBuilder()
        task = builder.set_task("Generate Mutation", "基于疲劳检测触发")
        builder.add_action(task, "generate_dna", "creative_123", status="success", result="生成 3 个变异体")
        builder.add_action(task, "upload", "meta_ads", status="success", result="上传成功")
        section = builder.build()
        assert "Generate Mutation" in section.content
        assert "2/2" in section.content  # 2/2 succeeded
        assert section.confidence == 1.0

    def test_build_with_failure(self):
        builder = ExecutionReportBuilder()
        task = builder.set_task("Test Task")
        builder.add_action(task, "a1", "t1", status="success")
        builder.add_action(task, "a2", "t2", status="failure", error="API timeout")
        section = builder.build()
        assert "API timeout" in section.content
        assert "1/2" in section.content
        assert section.confidence == 0.5

    def test_build_with_rollback(self):
        builder = ExecutionReportBuilder()
        task = builder.set_task("Test Task")
        builder.add_action(task, "a1", "t1", status="success")
        builder.add_action(task, "a2", "t2", status="rollback", result="rolled back")
        section = builder.build()
        assert "rollback" in section.content
        assert "rolled back" in section.content

    def test_build_with_safety_info(self):
        builder = ExecutionReportBuilder()
        task = builder.set_task(
            "Test Task",
            risk_level="high",
            approval_required=True,
            approval_status="pending",
        )
        builder.add_action(task, "a1", "t1", status="success")
        section = builder.build()
        assert "HIGH" in section.content
        assert "PENDING" in section.content

    def test_build_with_spend_roas(self):
        builder = ExecutionReportBuilder()
        task = builder.set_task("Test Task", spend=100.0, roas=1.42)
        builder.add_action(task, "a1", "t1", status="success")
        section = builder.build()
        assert "$100.00" in section.content
        assert "1.42" in section.content

    def test_build_metrics(self):
        builder = ExecutionReportBuilder()
        task = builder.set_task("T1")
        builder.add_action(task, "a1", "t1", status="success")
        builder.add_action(task, "a2", "t2", status="failure")
        section = builder.build()
        metric_names = [m.name for m in section.metrics]
        assert "total_actions" in metric_names
        assert "execution_success_rate" in metric_names

    def test_create_execution_report_helper(self):
        section = create_execution_report(
            task_name="Generate Mutation",
            actions=[
                {"action_type": "generate_dna", "target": "c1", "status": "success", "result": "OK"},
                {"action_type": "upload", "target": "meta", "status": "success", "result": "OK"},
            ],
            risk_level="low",
        )
        assert section.type == ReportType.EXECUTION
        assert "Generate Mutation" in section.content


# ═══════════════════════════════════════════════════════════════
# Test Health Report
# ═══════════════════════════════════════════════════════════════


class TestHealthReportBuilder:
    """测试 HealthReportBuilder."""

    def test_build_healthy(self):
        builder = HealthReportBuilder()
        builder.set_status("healthy")
        section = builder.build()
        assert "HEALTHY" in section.content
        assert section.confidence == 1.0

    def test_build_safe_mode(self):
        builder = HealthReportBuilder()
        builder.set_status("safe_mode", previous_status="healthy", status_changed=True)
        section = builder.build()
        assert "SAFE_MODE" in section.content
        assert "healthy" in section.content
        assert section.confidence == 0.3

    def test_build_with_metrics(self):
        builder = HealthReportBuilder()
        builder.set_status("warning")
        builder.add_execution_metrics(failure_rate=0.15, execution_success_rate=0.85)
        builder.add_tool_metrics(api_success_rate=0.72, timeout_count=8)
        section = builder.build()
        assert "failure_rate" in section.content
        assert "api_success_rate" in section.content

    def test_build_with_rules(self):
        builder = HealthReportBuilder()
        builder.set_status("degraded")
        builder.add_triggered_rules(["execution_failure", "tool_failure"])
        section = builder.build()
        assert "execution_failure" in section.content
        assert "tool_failure" in section.content

    def test_build_with_warnings_and_errors(self):
        builder = HealthReportBuilder()
        builder.set_status("warning")
        builder.add_warnings(["Meta API timeout increasing"])
        builder.add_errors(["Connection refused"])
        section = builder.build()
        assert "Meta API timeout" in section.content
        assert "Connection refused" in section.content

    def test_build_with_recommendations(self):
        builder = HealthReportBuilder()
        builder.set_status("degraded")
        builder.add_recommendation("暂停自动执行")
        builder.add_recommendation("切换模拟模式")
        section = builder.build()
        assert "暂停自动执行" in section.content
        assert "切换模拟模式" in section.content

    def test_build_with_alerts(self):
        builder = HealthReportBuilder()
        builder.set_status("warning")
        builder.set_alerts(active=3, critical=1)
        section = builder.build()
        assert "3 active" in section.content
        assert "1 critical" in section.content

    def test_status_confidence_mapping(self):
        mapping = {
            "healthy": 1.0,
            "warning": 0.7,
            "degraded": 0.5,
            "safe_mode": 0.3,
            "failed": 0.0,
        }
        for status, expected_conf in mapping.items():
            builder = HealthReportBuilder()
            builder.set_status(status)
            section = builder.build()
            assert section.confidence == expected_conf

    def test_create_health_report_helper(self):
        section = create_health_report(
            status="warning",
            triggered_rules=["execution_failure"],
            warnings=["timeout increasing"],
            recommendations=["暂停执行"],
            active_alerts=2,
            execution_metrics={"failure_rate": 0.15},
        )
        assert "WARNING" in section.content
        assert "execution_failure" in section.content


# ═══════════════════════════════════════════════════════════════
# Test Learning Report
# ═══════════════════════════════════════════════════════════════


class TestLearningReportBuilder:
    """测试 LearningReportBuilder."""

    def test_build_empty(self):
        builder = LearningReportBuilder()
        section = builder.build()
        assert section.type == ReportType.LEARNING
        assert "no updates" in section.summary

    def test_build_with_learning(self):
        builder = LearningReportBuilder()
        builder.add_learning(LearningEntry(
            action="mutate_creative",
            condition="fatigue > 0.8",
            reward=0.32,
            confidence=0.91,
            experience_count=5,
            source="ExecutionFeedback",
        ))
        section = builder.build()
        assert "mutate_creative" in section.content
        assert "fatigue > 0.8" in section.content
        assert "+32%" in section.content
        assert "91%" in section.content
        assert section.confidence == 0.91

    def test_build_with_pattern_updates(self):
        builder = LearningReportBuilder()
        builder.add_pattern_update(PatternUpdate(
            pattern_name="rescue_hook_effectiveness",
            old_value=0.65,
            new_value=0.78,
            change="improved",
        ))
        section = builder.build()
        assert "rescue_hook_effectiveness" in section.content
        assert "improved" in section.content

    def test_build_with_memory_feedback(self):
        builder = LearningReportBuilder()
        builder.add_memory_feedback(MemoryFeedback(
            memory_type="pattern",
            key="mutate_creative_fatigue",
            action="update",
            value="reward +32%, confidence 0.91",
        ))
        section = builder.build()
        assert "mutate_creative_fatigue" in section.content
        assert "update" in section.content

    def test_build_with_performance_changes(self):
        builder = LearningReportBuilder()
        builder.add_performance_change("avg_ROAS", 1.2, 1.5)
        builder.add_performance_change("avg_CTR", 0.03, 0.04)
        section = builder.build()
        assert "avg_ROAS" in section.content
        assert "Performance Delta" in section.content

    def test_build_metrics(self):
        builder = LearningReportBuilder()
        builder.add_learning(LearningEntry(action="A", condition="C", reward=0.3, confidence=0.9))
        builder.add_learning(LearningEntry(action="B", condition="D", reward=0.2, confidence=0.7))
        section = builder.build()
        metric_names = [m.name for m in section.metrics]
        assert "learning_count" in metric_names
        assert "learning_confidence_avg" in metric_names

    def test_create_learning_report_helper(self):
        section = create_learning_report(
            learnings=[
                {"action": "mutate", "condition": "fatigue > 0.8", "reward": 0.32, "confidence": 0.91},
            ],
            pattern_updates=[
                {"name": "hook_effect", "old": 0.65, "new": 0.78, "change": "improved"},
            ],
            memory_feedbacks=[
                {"type": "pattern", "key": "mutate_fatigue", "action": "update", "value": "reward +32%"},
            ],
        )
        assert "mutate" in section.content
        assert "hook_effect" in section.content


# ═══════════════════════════════════════════════════════════════
# Test Report Store
# ═══════════════════════════════════════════════════════════════


class TestInMemoryReportStore:
    """测试 InMemoryReportStore."""

    def test_initial_empty(self):
        store = InMemoryReportStore()
        assert store.count() == 0
        assert store.get_latest() is None

    def test_save_and_get(self):
        store = InMemoryReportStore()
        r = AgentReport(agent_id="ua_01", cycle_id="c001")
        store.save(r)
        assert store.count() == 1
        assert store.get(r.report_id) is not None

    def test_save_and_get_latest(self):
        store = InMemoryReportStore()
        r1 = AgentReport(agent_id="ua_01", cycle_id="c001")
        r2 = AgentReport(agent_id="ua_01", cycle_id="c002")
        store.save(r1)
        store.save(r2)
        latest = store.get_latest("ua_01")
        assert latest is not None
        assert latest.report_id == r2.report_id

    def test_get_latest_with_agent_filter(self):
        store = InMemoryReportStore()
        store.save(AgentReport(agent_id="ua_01"))
        store.save(AgentReport(agent_id="ua_02"))
        latest = store.get_latest("ua_01")
        assert latest is not None
        assert latest.agent_id == "ua_01"

    def test_get_history(self):
        store = InMemoryReportStore()
        for i in range(10):
            store.save(AgentReport(agent_id="ua_01", cycle_id=f"c{i:03d}"))
        history = store.get_history("ua_01", limit=5)
        assert len(history) == 5

    def test_get_history_order(self):
        """历史报告按时间倒序 (最新在前)."""
        store = InMemoryReportStore()
        r1 = AgentReport(agent_id="ua_01", cycle_id="c001")
        r2 = AgentReport(agent_id="ua_01", cycle_id="c002")
        store.save(r1)
        store.save(r2)
        history = store.get_history("ua_01")
        assert history[0].cycle_id == "c002"
        assert history[1].cycle_id == "c001"

    def test_query_by_agent_id(self):
        store = InMemoryReportStore()
        store.save(AgentReport(agent_id="ua_01"))
        store.save(AgentReport(agent_id="ua_01"))
        store.save(AgentReport(agent_id="ua_02"))
        results = store.query(ReportQuery(agent_id="ua_01"))
        assert len(results) == 2

    def test_query_by_status(self):
        store = InMemoryReportStore()
        r1 = AgentReport()
        r1.finalize()
        store.save(r1)
        store.save(AgentReport())  # draft
        results = store.query(ReportQuery(status=ReportStatus.FINAL))
        assert len(results) == 1

    def test_query_limit(self):
        store = InMemoryReportStore()
        for i in range(10):
            store.save(AgentReport(agent_id="ua_01"))
        results = store.query(ReportQuery(limit=3))
        assert len(results) == 3

    def test_capacity_control(self):
        store = InMemoryReportStore(max_reports=5)
        for i in range(10):
            store.save(AgentReport(agent_id="ua_01"))
        assert store.count() == 5

    def test_stats(self):
        store = InMemoryReportStore()
        r = AgentReport()
        r.add_section(ReportSection(type=ReportType.DECISION))
        r.add_section(ReportSection(type=ReportType.EXECUTION))
        store.save(r)
        stats = store.stats()
        assert stats["total_reports"] == 1
        assert "decision" in stats["types"]

    def test_clear(self):
        store = InMemoryReportStore()
        store.save(AgentReport())
        store.clear()
        assert store.count() == 0

    def test_get_non_existent(self):
        store = InMemoryReportStore()
        assert store.get("nonexistent") is None


class TestFileReportStore:
    """测试 FileReportStore."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_initial_empty(self, temp_dir):
        store = FileReportStore(base_dir=temp_dir)
        assert store.count() == 0

    def test_save_and_get(self, temp_dir):
        store = FileReportStore(base_dir=temp_dir)
        r = AgentReport(agent_id="ua_01", cycle_id="c001")
        store.save(r)
        assert store.count() == 1
        retrieved = store.get(r.report_id)
        assert retrieved is not None
        assert retrieved.agent_id == "ua_01"

    def test_save_persists_to_disk(self, temp_dir):
        store = FileReportStore(base_dir=temp_dir)
        r = AgentReport(agent_id="ua_01")
        r.add_section(ReportSection(type=ReportType.DECISION, confidence=0.8))
        store.save(r)

        # 创建新 store 实例验证持久化
        store2 = FileReportStore(base_dir=temp_dir)
        assert store2.count() == 1
        retrieved = store2.get(r.report_id)
        assert retrieved is not None
        assert len(retrieved.sections) == 1

    def test_get_latest(self, temp_dir):
        store = FileReportStore(base_dir=temp_dir)
        store.save(AgentReport(agent_id="ua_01", cycle_id="c001", timestamp="2026-01-01T00:00:00+00:00"))
        store.save(AgentReport(agent_id="ua_01", cycle_id="c002", timestamp="2026-01-02T00:00:00+00:00"))
        latest = store.get_latest("ua_01")
        assert latest is not None
        assert latest.cycle_id == "c002"

    def test_get_history(self, temp_dir):
        store = FileReportStore(base_dir=temp_dir)
        for i in range(5):
            store.save(AgentReport(agent_id="ua_01", cycle_id=f"c{i:03d}"))
        history = store.get_history("ua_01", limit=3)
        assert len(history) == 3

    def test_clear(self, temp_dir):
        store = FileReportStore(base_dir=temp_dir)
        store.save(AgentReport())
        store.clear()
        assert store.count() == 0

    def test_stats(self, temp_dir):
        store = FileReportStore(base_dir=temp_dir)
        store.save(AgentReport())
        stats = store.stats()
        assert stats["total_reports"] == 1

    def test_create_report_store_factory(self, temp_dir):
        mem_store = create_report_store("memory")
        assert isinstance(mem_store, InMemoryReportStore)

        file_store = create_report_store("file", base_dir=temp_dir)
        assert isinstance(file_store, FileReportStore)


# ═══════════════════════════════════════════════════════════════
# Test Agent Reporter
# ═══════════════════════════════════════════════════════════════


class TestAgentReporter:
    """测试 AgentReporter."""

    def test_create_reporter(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        assert reporter.agent_id == "ua_01"
        assert reporter.current_report is None

    def test_start_cycle(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        report = reporter.start_cycle("c001")
        assert report.cycle_id == "c001"
        assert report.agent_id == "ua_01"
        assert report.status == ReportStatus.DRAFT

    def test_finalize(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        report = reporter.finalize()
        assert report.status == ReportStatus.FINAL

    def test_finalize_without_start(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        report = reporter.finalize()
        assert report.status == ReportStatus.FINAL

    def test_save_and_get_latest(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_decision_section(
            campaign_name="Test",
            observations={"ROAS": (0.53, 0.75)},
            reasoning_points=["CTR decline"],
            decisions=[{"action": "MUTATE", "reason": "fatigue", "confidence": 0.87}],
        )
        reporter.finalize()
        reporter.save()

        latest = reporter.get_latest()
        assert latest is not None
        assert latest.cycle_id == "c001"

    def test_add_decision_section(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        section = reporter.add_decision_section(
            campaign_name="Test",
            observations={"ROAS": (0.53, 0.75)},
            reasoning_points=["CTR 下降"],
            decisions=[{"action": "MUTATE", "reason": "fatigue", "confidence": 0.87}],
            similar_cases=18,
            success_rate=0.72,
        )
        assert section.type == ReportType.DECISION
        assert reporter.current_report.summary.decision_count == 1

    def test_add_execution_section(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        section = reporter.add_execution_section(
            task_name="Generate Mutation",
            actions=[
                {"action_type": "generate_dna", "target": "c1", "status": "success"},
                {"action_type": "upload", "target": "meta", "status": "success"},
            ],
            risk_level="low",
        )
        assert section.type == ReportType.EXECUTION
        assert reporter.current_report.summary.execution_count == 1

    def test_add_health_section(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        section = reporter.add_health_section(
            status="healthy",
            execution_metrics={"failure_rate": 0.05},
        )
        assert section.type == ReportType.HEALTH

    def test_add_learning_section(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        section = reporter.add_learning_section(
            learnings=[
                {"action": "mutate", "condition": "fatigue > 0.8", "reward": 0.32, "confidence": 0.91},
            ],
        )
        assert section.type == ReportType.LEARNING
        assert reporter.current_report.summary.learning_count == 1

    def test_add_section_direct(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.add_section(ReportSection(type=ReportType.DECISION, confidence=0.8))
        assert reporter.current_report.summary.decision_count == 1

    def test_full_cycle_report(self):
        """完整 Agent 周期报告."""
        reporter = create_agent_reporter(agent_id="ua_agent_01")
        reporter.start_cycle("cycle_001")

        # Decision
        reporter.add_decision_section(
            campaign_name="Witch Merge",
            observations={
                "ROAS": (0.53, 0.75),
                "Creative fatigue": (0.82, 0.5),
                "Frequency": (4.7, 3.2),
            },
            reasoning_points=[
                "当前素材 CTR 下降 34%",
                "同 DNA 已运行 12 天",
            ],
            decisions=[
                {
                    "action": "CREATE_CREATIVE_VARIANTS",
                    "target": "Witch Merge",
                    "reason": "素材疲劳触发",
                    "confidence": 0.87,
                    "expected": "CTR +15%, ROAS +8%",
                },
            ],
            similar_cases=18,
            success_rate=0.72,
        )

        # Execution
        reporter.add_execution_section(
            task_name="Generate Creative Mutation",
            description="基于疲劳检测触发素材变异",
            actions=[
                {"action_type": "generate_dna", "target": "creative_123", "status": "success", "result": "生成 3 个变异体"},
                {"action_type": "upload_meta", "target": "meta_ads", "status": "success", "result": "上传成功"},
                {"action_type": "create_campaign_test", "target": "camp_test", "status": "success", "result": "测试活动创建"},
            ],
            risk_level="low",
            approval_status="not_required",
            spend=100.0,
            roas=1.42,
        )

        # Health
        reporter.add_health_section(
            status="healthy",
            execution_metrics={"execution_success_rate": 0.95, "failure_rate": 0.05},
            tool_metrics={"api_success_rate": 0.98, "timeout_count": 0},
        )

        # Learning
        reporter.add_learning_section(
            learnings=[
                {
                    "action": "mutate_creative",
                    "condition": "fatigue > 0.8",
                    "reward": 0.32,
                    "confidence": 0.91,
                    "experience_count": 5,
                },
            ],
            pattern_updates=[
                {"name": "fatigue_threshold", "old": 0.7, "new": 0.75, "change": "improved"},
            ],
        )

        report = reporter.finalize()
        reporter.save()

        assert report.status == ReportStatus.FINAL
        assert report.summary.decision_count == 1
        assert report.summary.execution_count == 1
        assert report.summary.learning_count == 1
        assert report.summary.total_sections == 4

        # 验证可以查询
        latest = reporter.get_latest()
        assert latest is not None
        assert latest.cycle_id == "cycle_001"

    def test_render_json(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_decision_section(
            decisions=[{"action": "TEST", "reason": "test", "confidence": 0.8}],
        )
        json_str = reporter.render(format=ReportFormat.JSON)
        data = json.loads(json_str)
        assert data["agent_id"] == "ua_01"
        assert len(data["sections"]) == 1

    def test_render_markdown(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_decision_section(
            decisions=[{"action": "TEST", "reason": "test", "confidence": 0.8}],
        )
        md = reporter.render(format=ReportFormat.MARKDOWN)
        assert "# Agent Report" in md
        assert "ua_01" in md

    def test_render_text(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_decision_section(
            decisions=[{"action": "TEST", "reason": "test", "confidence": 0.8}],
        )
        txt = reporter.render(format=ReportFormat.TEXT)
        assert "=== Agent Report" in txt
        assert "ua_01" in txt

    def test_render_none(self):
        reporter = create_agent_reporter()
        assert reporter.render() == ""

    def test_get_decision_history(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_decision_section(
            decisions=[{"action": "A1", "reason": "R1", "confidence": 0.8}],
        )
        reporter.finalize()
        reporter.save()

        reporter.start_cycle("c002")
        reporter.add_decision_section(
            decisions=[{"action": "A2", "reason": "R2", "confidence": 0.7}],
        )
        reporter.finalize()
        reporter.save()

        history = reporter.get_decision_history()
        assert len(history) == 2

    def test_get_execution_history(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_execution_section(
            task_name="T1",
            actions=[{"action_type": "a1", "target": "t1", "status": "success"}],
        )
        reporter.finalize()
        reporter.save()

        history = reporter.get_execution_history()
        assert len(history) == 1

    def test_get_learning_history(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_learning_section(
            learnings=[{"action": "A", "condition": "C", "reward": 0.3, "confidence": 0.9}],
        )
        reporter.finalize()
        reporter.save()

        history = reporter.get_learning_history()
        assert len(history) == 1

    def test_get_health_history(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_health_section(status="healthy")
        reporter.finalize()
        reporter.save()

        history = reporter.get_health_history()
        assert len(history) == 1

    def test_status(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.finalize()
        reporter.save()

        status = reporter.status()
        assert status["agent_id"] == "ua_01"
        assert status["total_reports"] == 1

    def test_query(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        for i in range(3):
            reporter.start_cycle(f"c{i:03d}")
            reporter.finalize()
            reporter.save()

        results = reporter.query(ReportQuery(limit=2))
        assert len(results) == 2

    def test_get_report(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        report = reporter.finalize()
        reporter.save()

        retrieved = reporter.get_report(report.report_id)
        assert retrieved is not None
        assert retrieved.report_id == report.report_id

    def test_get_history(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        for i in range(5):
            reporter.start_cycle(f"c{i:03d}")
            reporter.finalize()
            reporter.save()

        history = reporter.get_history(limit=3)
        assert len(history) == 3

    def test_reset(self):
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.reset()
        assert reporter.current_report is None

    def test_on_report_finalized_callback(self):
        finalized = []
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.on_report_finalized(lambda r: finalized.append(r.report_id))
        reporter.start_cycle("c001")
        reporter.finalize()
        assert len(finalized) == 1

    def test_create_with_file_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = create_agent_reporter(agent_id="ua_01", store_type="file", base_dir=tmpdir)
            reporter.start_cycle("c001")
            reporter.finalize()
            reporter.save()
            assert reporter.get_latest() is not None


# ═══════════════════════════════════════════════════════════════
# Test Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """测试报告系统集成."""

    def test_full_agent_cycle_with_all_reports(self):
        """完整 Agent 周期: 所有 4 种报告."""
        reporter = create_agent_reporter(agent_id="growth_agent_01")

        # Cycle 1: 正常
        reporter.start_cycle("cycle_001")
        reporter.add_decision_section(
            campaign_name="Campaign A",
            observations={"ROAS": (1.5, 1.3), "CTR": (0.04, 0.03)},
            reasoning_points=["ROAS improvement", "CTR positive"],
            decisions=[{"action": "SCALE_BUDGET", "reason": "ROAS > 1.3", "confidence": 0.85}],
        )
        reporter.add_execution_section(
            task_name="Scale Budget",
            actions=[{"action_type": "increase_budget", "target": "camp_a", "status": "success"}],
            risk_level="medium",
        )
        reporter.add_health_section(status="healthy")
        reporter.add_learning_section(
            learnings=[{"action": "scale", "condition": "ROAS > 1.3", "reward": 0.15, "confidence": 0.9}],
        )
        reporter.finalize()
        reporter.save()

        # Cycle 2: 异常
        reporter.start_cycle("cycle_002")
        reporter.add_decision_section(
            campaign_name="Campaign B",
            observations={"ROAS": (0.4, 1.5), "CTR": (0.01, 0.04)},
            reasoning_points=["ROAS crashed", "素材疲劳"],
            decisions=[{"action": "PAUSE_CAMPAIGN", "reason": "ROAS < 0.5", "confidence": 0.92}],
        )
        reporter.add_execution_section(
            task_name="Pause Campaign",
            actions=[{"action_type": "pause", "target": "camp_b", "status": "success"}],
        )
        reporter.add_health_section(
            status="warning",
            triggered_rules=["execution_failure"],
            warnings=["ROAS anomaly detected"],
            execution_metrics={"failure_rate": 0.08},
        )
        reporter.add_learning_section(
            learnings=[{"action": "pause", "condition": "ROAS < 0.5", "reward": 0.5, "confidence": 0.92}],
        )
        reporter.finalize()
        reporter.save()

        # 验证存储
        history = reporter.get_history()
        assert len(history) == 2

        decisions = reporter.get_decision_history()
        assert len(decisions) == 2

        healths = reporter.get_health_history()
        assert len(healths) == 2

        # 最新报告
        latest = reporter.get_latest()
        assert latest is not None
        assert latest.cycle_id == "cycle_002"

        # 状态
        status = reporter.status()
        assert status["total_reports"] == 2

    def test_report_rendering_pipeline(self):
        """报告渲染 Pipeline: JSON → Markdown → Text."""
        reporter = create_agent_reporter(agent_id="ua_01")
        reporter.start_cycle("c001")
        reporter.add_decision_section(
            campaign_name="Test",
            observations={"ROAS": (0.53, 0.75)},
            reasoning_points=["CTR decline"],
            decisions=[{"action": "MUTATE", "reason": "fatigue", "confidence": 0.87}],
        )
        reporter.add_execution_section(
            task_name="Generate Mutation",
            actions=[{"action_type": "generate_dna", "target": "c1", "status": "success"}],
        )
        reporter.finalize()

        # JSON
        json_str = reporter.render(format=ReportFormat.JSON)
        data = json.loads(json_str)
        assert data["agent_id"] == "ua_01"

        # Markdown
        md = reporter.render(format=ReportFormat.MARKDOWN)
        assert "# Agent Report" in md
        assert "## Growth Agent Decision Report" in md
        assert "## Growth Agent Execution Report" in md

        # Text
        txt = reporter.render(format=ReportFormat.TEXT)
        assert "=== Agent Report" in txt
        assert "[DECISION]" in txt
        assert "[EXECUTION]" in txt

    def test_multi_cycle_reporting(self):
        """多周期报告: 50 个周期."""
        reporter = create_agent_reporter(agent_id="ua_01")
        for i in range(50):
            reporter.start_cycle(f"cycle_{i:03d}")
            reporter.add_decision_section(
                decisions=[{"action": f"ACTION_{i}", "reason": f"reason_{i}", "confidence": 0.8}],
            )
            reporter.finalize()
            reporter.save()

        assert reporter.store.count() == 50
        history = reporter.get_history(limit=10)
        assert len(history) == 10

    def test_report_query_filtering(self):
        """报告查询过滤."""
        reporter = create_agent_reporter(agent_id="ua_01")
        for i in range(5):
            reporter.start_cycle(f"c{i:03d}")
            reporter.add_decision_section(
                decisions=[{"action": "A", "reason": "R", "confidence": 0.8}],
            )
            reporter.finalize()
            reporter.save()

        # 按 agent_id
        results = reporter.query(ReportQuery(agent_id="ua_01"))
        assert len(results) == 5

        # 按 cycle_id
        results = reporter.query(ReportQuery(cycle_id="c002"))
        assert len(results) == 1

        # 按 report_type
        results = reporter.query(ReportQuery(report_type=ReportType.DECISION))
        assert len(results) == 5

        results = reporter.query(ReportQuery(report_type=ReportType.HEALTH))
        assert len(results) == 0


# ═══════════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """测试边界情况."""

    def test_empty_report(self):
        """空报告."""
        r = AgentReport()
        assert r.overall_confidence == 0.0
        assert r.summary.total_sections == 0
        md = r.to_markdown()
        assert "# Agent Report" in md

    def test_section_with_no_content(self):
        """无内容的 section."""
        s = ReportSection(type=ReportType.DECISION, title="Empty")
        md = s.to_markdown()
        assert "## Empty" in md

    def test_decision_builder_no_decisions(self):
        """无决策的 builder."""
        builder = DecisionReportBuilder()
        builder.add_observation("ROAS", 1.5)
        builder.add_reasoning("test")
        section = builder.build()
        assert "no decision" in section.summary.lower()

    def test_execution_builder_no_actions(self):
        """无动作的 builder."""
        builder = ExecutionReportBuilder()
        builder.set_task("Empty Task")
        section = builder.build()
        assert "0/0" in section.content

    def test_learning_builder_no_updates(self):
        """无更新的 builder."""
        builder = LearningReportBuilder()
        section = builder.build()
        assert "no updates" in section.summary

    def test_store_query_empty(self):
        """空存储查询."""
        store = InMemoryReportStore()
        results = store.query(ReportQuery())
        assert results == []

    def test_reporter_no_cycles(self):
        """无周期的 reporter."""
        reporter = create_agent_reporter(agent_id="ua_01")
        assert reporter.get_latest() is None
        assert reporter.get_history() == []

    def test_large_report(self):
        """大量 sections."""
        r = AgentReport(agent_id="ua_01")
        for i in range(100):
            r.add_section(ReportSection(type=ReportType.DECISION, title=f"Decision {i}", confidence=0.8))
        assert r.summary.total_sections == 100
        assert r.summary.decision_count == 100

    def test_metric_with_zero_division(self):
        """零除保护."""
        m = ObservedMetric(name="test", value=1.0, previous_value=0.0)
        assert m.change_pct == 0.0

    def test_section_serialization_roundtrip(self):
        """section 序列化往返."""
        s = ReportSection(
            type=ReportType.DECISION,
            title="Test",
            content="Content",
            metrics=[ReportMetric(name="ROAS", value=1.5)],
            evidence=[ReportEvidence(source="M", reference="r")],
            confidence=0.85,
        )
        d = s.to_dict()
        # 重建
        s2 = ReportSection(
            section_id=d["section_id"],
            type=ReportType(d["type"]),
            title=d["title"],
            content=d["content"],
            summary=d["summary"],
            confidence=d["confidence"],
            timestamp=d["timestamp"],
            parent_id=d["parent_id"],
        )
        for m_data in d["metrics"]:
            s2.metrics.append(ReportMetric(**m_data))
        for e_data in d["evidence"]:
            s2.evidence.append(ReportEvidence(**e_data))
        assert s2.title == "Test"
        assert len(s2.metrics) == 1
        assert s2.metrics[0].name == "ROAS"

    def test_health_report_all_statuses(self):
        """所有健康状态都能生成报告."""
        for status in ["healthy", "warning", "degraded", "safe_mode", "failed"]:
            builder = HealthReportBuilder()
            builder.set_status(status)
            section = builder.build()
            assert status.upper() in section.content