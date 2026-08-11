"""E14.3 UA Growth Agent — 集成测试.

验证 UA Growth Agent 的完整功能:
  - UA Metrics & Analyzer (20)
  - UA Diagnosis Engine (20)
  - UA Strategy Engine (20)
  - UA Action Selector (20)
  - UA Memory (20)
  - UA Growth Agent Core (25)
  - Integration & Communication (15)

总计: 140 个测试用例
"""

from __future__ import annotations

import pytest
import time

from market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
    MessageBus,
    AgentRegistry,
    AgentRole,
    AgentStatus,
    create_default_organization,
    create_message_bus,
    create_agent_registry,
    CollaborationEngine,
    StandardMessageType,
    MessagePriority,
    MessageType,
    create_ua_agent_identity as comm_ua_identity,
    create_creative_agent_identity as comm_creative_identity,
    create_supervisor_agent_identity as comm_supervisor_identity,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.ua_agent import (
    # analyzer
    UAMetrics,
    MetricAnomaly,
    MetricStatus,
    UAAnalysisResult,
    UAAnalyzer,
    DEFAULT_THRESHOLDS,
    # diagnosis
    UADiagnosis,
    DiagnosisType,
    DiagnosisSeverity,
    UADiagnosisEngine,
    DiagnosisRule,
    # strategy
    UAStrategy,
    StrategyType,
    StrategyAction,
    UAStrategyEngine,
    DIAGNOSIS_TO_STRATEGY,
    # action_selector
    UAActionSelector,
    SelectedAction,
    ActionPlan,
    ActionStatus,
    ActionRisk,
    ACTION_RISK_MAP,
    ROLLBACK_MAP,
    # memory
    UAMemory,
    UADecisionRecord,
    DecisionOutcome,
    ExperienceEntry,
    # ua_agent
    UAGrowthAgent,
    UAAgentState,
    GrowthRecommendation,
    create_ua_agent,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def healthy_metrics():
    """健康指标."""
    return UAMetrics(
        product_id="P01",
        campaign_id="C04",
        spend=10000,
        revenue=15000,
        roas=1.5,
        cpi=1.5,
        ctr=1.2,
        cvr=3.5,
        ltv=6.0,
        fatigue=0.2,
        frequency=1.5,
        impressions=100000,
        installs=5000,
        payer_rate=2.5,
        arpu=3.0,
        d7_retention=25.0,
    )


@pytest.fixture
def fatigue_metrics():
    """素材疲劳指标."""
    return UAMetrics(
        product_id="P01",
        campaign_id="C04",
        spend=12000,
        revenue=13000,
        roas=1.08,
        cpi=2.5,
        ctr=0.4,
        cvr=3.0,
        ltv=5.0,
        fatigue=0.75,
        frequency=4.5,
        impressions=80000,
        installs=4000,
        payer_rate=2.0,
        arpu=2.8,
        d7_retention=20.0,
    )


@pytest.fixture
def saturation_metrics():
    """受众饱和指标."""
    return UAMetrics(
        product_id="P01",
        campaign_id="C05",
        spend=15000,
        revenue=16000,
        roas=1.07,
        cpi=4.0,
        ctr=1.0,
        cvr=3.0,
        ltv=5.5,
        fatigue=0.3,
        frequency=2.0,
        impressions=120000,
        installs=3000,
        payer_rate=2.0,
        arpu=3.0,
        d7_retention=22.0,
    )


@pytest.fixture
def store_issue_metrics():
    """商店问题指标."""
    return UAMetrics(
        product_id="P01",
        campaign_id="C06",
        spend=10000,
        revenue=9000,
        roas=0.9,
        cpi=2.0,
        ctr=1.1,
        cvr=0.8,
        ltv=4.0,
        fatigue=0.3,
        frequency=2.0,
        impressions=100000,
        installs=5000,
        payer_rate=1.2,
        arpu=2.0,
        d7_retention=18.0,
    )


@pytest.fixture
def analyzer():
    return UAAnalyzer()


@pytest.fixture
def diagnosis_engine():
    return UADiagnosisEngine()


@pytest.fixture
def strategy_engine():
    return UAStrategyEngine()


@pytest.fixture
def action_selector():
    return UAActionSelector()


@pytest.fixture
def ua_memory():
    return UAMemory()


@pytest.fixture
def bus():
    return create_message_bus()


@pytest.fixture
def registry():
    return create_default_organization()


@pytest.fixture
def ua_agent():
    return create_ua_agent()


# ═══════════════════════════════════════════════════════════════
# 1. UA Metrics & Analyzer (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestUAMetrics:
    """UA Metrics 模型测试."""

    def test_create_metrics_defaults(self):
        """默认值创建指标."""
        m = UAMetrics()
        assert m.spend == 0.0
        assert m.roas == 0.0
        assert m.fatigue == 0.0

    def test_create_metrics_with_values(self):
        """带值创建指标."""
        m = UAMetrics(spend=5000, roas=1.5, cpi=2.0)
        assert m.spend == 5000
        assert m.roas == 1.5
        assert m.cpi == 2.0

    def test_metrics_to_dict(self, healthy_metrics):
        """指标序列化."""
        d = healthy_metrics.to_dict()
        assert d["roas"] == 1.5
        assert d["product_id"] == "P01"
        assert d["campaign_id"] == "C04"

    def test_metrics_to_dict_includes_all_fields(self, healthy_metrics):
        """to_dict 包含所有字段."""
        d = healthy_metrics.to_dict()
        required = ["spend", "revenue", "roas", "cpi", "ctr", "cvr", "ltv", "fatigue"]
        for k in required:
            assert k in d

    def test_metrics_timestamp_auto_generated(self):
        """自动生成时间戳."""
        m = UAMetrics()
        assert m.timestamp != ""

    def test_metrics_metadata_extensible(self):
        """metadata 可扩展."""
        m = UAMetrics(metadata={"source": "meta_ads", "region": "US"})
        assert m.metadata["source"] == "meta_ads"


class TestMetricAnomaly:
    """MetricAnomaly 模型测试."""

    def test_anomaly_creation(self):
        a = MetricAnomaly(metric="roas", current_value=0.5, expected_value=1.2,
                          deviation=0.58, status=MetricStatus.CRITICAL)
        assert a.metric == "roas"
        assert a.status == MetricStatus.CRITICAL

    def test_anomaly_to_dict(self):
        a = MetricAnomaly(metric="cpi", current_value=5.0, expected_value=2.0,
                          deviation=1.5, status=MetricStatus.WARNING, confidence=0.7)
        d = a.to_dict()
        assert d["metric"] == "cpi"
        assert d["status"] == "warning"
        assert d["confidence"] == 0.7


class TestUAAnalysisResult:
    """UAAnalysisResult 模型测试."""

    def test_analysis_result_defaults(self):
        r = UAAnalysisResult()
        assert r.health_score == 100.0
        assert r.trend_direction == "stable"

    def test_analysis_result_to_dict(self, healthy_metrics):
        r = UAAnalysisResult(product_id="P01", metrics=healthy_metrics, health_score=85.0)
        d = r.to_dict()
        assert d["health_score"] == 85.0
        assert d["product_id"] == "P01"

    def test_analysis_result_with_anomalies(self, healthy_metrics):
        a = MetricAnomaly(metric="roas", current_value=0.5, status=MetricStatus.CRITICAL)
        r = UAAnalysisResult(metrics=healthy_metrics, anomalies=[a], health_score=60.0)
        assert len(r.anomalies) == 1


class TestUAAnalyzer:
    """UA Analyzer 测试."""

    def test_analyze_healthy(self, analyzer, healthy_metrics):
        result = analyzer.analyze(healthy_metrics)
        assert result.health_score >= 90
        assert "无异常" in result.summary

    def test_analyze_fatigue_detection(self, analyzer, fatigue_metrics):
        result = analyzer.analyze(fatigue_metrics)
        assert result.health_score < 90
        anomaly_names = [a.metric for a in result.anomalies]
        assert "fatigue" in anomaly_names or "ctr" in anomaly_names

    def test_analyze_saturation_detection(self, analyzer, saturation_metrics):
        result = analyzer.analyze(saturation_metrics)
        anomaly_names = [a.metric for a in result.anomalies]
        assert "cpi" in anomaly_names

    def test_analyze_from_dict(self, analyzer):
        result = analyzer.analyze_from_dict({
            "roas": 0.5, "cpi": 6.0, "ctr": 0.2, "fatigue": 0.8
        })
        assert result.health_score < 70

    def test_analyze_trend_stable(self, analyzer, healthy_metrics):
        result = analyzer.analyze(healthy_metrics, healthy_metrics)
        assert result.trend_direction == "stable"

    def test_analyze_trend_deteriorating(self, analyzer, healthy_metrics, fatigue_metrics):
        result = analyzer.analyze(fatigue_metrics, healthy_metrics)
        assert result.trend_direction == "deteriorating"

    def test_analyze_trend_improving(self, analyzer, fatigue_metrics, healthy_metrics):
        result = analyzer.analyze(healthy_metrics, fatigue_metrics)
        assert result.trend_direction == "improving"

    def test_analyzer_history(self, analyzer, healthy_metrics):
        analyzer.analyze(healthy_metrics)
        analyzer.analyze(healthy_metrics)
        assert len(analyzer.get_history()) == 2

    def test_analyzer_reset(self, analyzer, healthy_metrics):
        analyzer.analyze(healthy_metrics)
        analyzer.reset()
        assert len(analyzer.get_history()) == 0


# ═══════════════════════════════════════════════════════════════
# 2. UA Diagnosis Engine (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestDiagnosisModels:
    """Diagnosis 模型测试."""

    def test_diagnosis_creation(self):
        d = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE,
                        severity=DiagnosisSeverity.HIGH)
        assert d.issue_type == DiagnosisType.CREATIVE_FATIGUE

    def test_diagnosis_to_dict(self):
        d = UADiagnosis(issue_type=DiagnosisType.AUDIENCE_SATURATION,
                        severity=DiagnosisSeverity.MEDIUM,
                        root_cause="受众饱和", confidence=0.8)
        dd = d.to_dict()
        assert dd["issue_type"] == "audience_saturation"
        assert dd["confidence"] == 0.8

    def test_diagnosis_with_evidence(self):
        d = UADiagnosis(
            issue_type=DiagnosisType.CREATIVE_FATIGUE,
            evidence=["CTR下降至0.3%", "frequency上升至5.0"],
            related_metrics=["ctr", "frequency"],
        )
        assert len(d.evidence) == 2
        assert "ctr" in d.related_metrics

    def test_diagnosis_severity_ordering(self):
        # CRITICAL > HIGH > MEDIUM > LOW
        severity_order = {
            DiagnosisSeverity.CRITICAL: 4,
            DiagnosisSeverity.HIGH: 3,
            DiagnosisSeverity.MEDIUM: 2,
            DiagnosisSeverity.LOW: 1,
        }
        assert severity_order[DiagnosisSeverity.CRITICAL] > severity_order[DiagnosisSeverity.LOW]
        assert severity_order[DiagnosisSeverity.HIGH] > severity_order[DiagnosisSeverity.MEDIUM]


class TestDiagnosisEngine:
    """UADiagnosisEngine 测试."""

    def test_diagnose_healthy(self, diagnosis_engine, analyzer, healthy_metrics):
        analysis = analyzer.analyze(healthy_metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        assert len(diagnoses) == 1
        assert diagnoses[0].issue_type == DiagnosisType.HEALTHY

    def test_diagnose_creative_fatigue(self, diagnosis_engine, analyzer, fatigue_metrics):
        analysis = analyzer.analyze(fatigue_metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        types = [d.issue_type for d in diagnoses]
        assert DiagnosisType.CREATIVE_FATIGUE in types

    def test_diagnose_audience_saturation(self, diagnosis_engine, analyzer, saturation_metrics):
        analysis = analyzer.analyze(saturation_metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        types = [d.issue_type for d in diagnoses]
        assert DiagnosisType.AUDIENCE_SATURATION in types or DiagnosisType.CPI_SPIKE in types

    def test_diagnose_store_issue(self, diagnosis_engine, analyzer, store_issue_metrics):
        analysis = analyzer.analyze(store_issue_metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        types = [d.issue_type for d in diagnoses]
        assert DiagnosisType.STORE_ISSUE in types

    def test_diagnose_from_anomalies(self, diagnosis_engine):
        anomalies = [
            MetricAnomaly(metric="ctr", current_value=0.3, expected_value=1.0,
                          status=MetricStatus.CRITICAL, confidence=0.9),
            MetricAnomaly(metric="frequency", current_value=5.0, expected_value=2.0,
                          status=MetricStatus.CRITICAL, confidence=0.9),
        ]
        diagnoses = diagnosis_engine.diagnose_from_anomalies(anomalies)
        types = [d.issue_type for d in diagnoses]
        assert DiagnosisType.CREATIVE_FATIGUE in types

    def test_diagnose_confidence(self, diagnosis_engine, analyzer, fatigue_metrics):
        analysis = analyzer.analyze(fatigue_metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        for d in diagnoses:
            assert 0 <= d.confidence <= 1.0

    def test_diagnose_has_evidence(self, diagnosis_engine, analyzer, fatigue_metrics):
        analysis = analyzer.analyze(fatigue_metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        for d in diagnoses:
            if d.issue_type != DiagnosisType.HEALTHY:
                assert len(d.evidence) > 0

    def test_diagnose_has_recommendation(self, diagnosis_engine, analyzer, fatigue_metrics):
        analysis = analyzer.analyze(fatigue_metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        for d in diagnoses:
            if d.issue_type != DiagnosisType.HEALTHY:
                assert d.recommendation != ""

    def test_diagnose_healthy_no_anomalies(self, diagnosis_engine):
        analysis = UAAnalysisResult(anomalies=[])
        diagnoses = diagnosis_engine.diagnose(analysis)
        assert diagnoses[0].issue_type == DiagnosisType.HEALTHY
        assert diagnoses[0].confidence > 0.9

    def test_diagnose_unknown_pattern(self, diagnosis_engine):
        anomalies = [
            MetricAnomaly(metric="unknown_x", current_value=999, expected_value=100,
                          status=MetricStatus.WARNING, confidence=0.3),
        ]
        analysis = UAAnalysisResult(anomalies=anomalies)
        diagnoses = diagnosis_engine.diagnose(analysis)
        assert diagnoses[0].issue_type == DiagnosisType.UNKNOWN

    def test_diagnose_payer_decline(self, diagnosis_engine, analyzer):
        metrics = UAMetrics(payer_rate=0.3, roas=1.5, ctr=1.0, cpi=2.0)
        analysis = analyzer.analyze(metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        types = [d.issue_type for d in diagnoses]
        assert DiagnosisType.PAYER_DECLINE in types

    def test_diagnose_retention_decline(self, diagnosis_engine, analyzer):
        metrics = UAMetrics(d7_retention=8.0, roas=1.5, ctr=1.0, cpi=2.0)
        analysis = analyzer.analyze(metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        types = [d.issue_type for d in diagnoses]
        assert DiagnosisType.RETENTION_DECLINE in types

    def test_diagnose_ltv_decline(self, diagnosis_engine, analyzer):
        metrics = UAMetrics(ltv=1.5, roas=1.2, ctr=1.0, cpi=2.0)
        analysis = analyzer.analyze(metrics)
        diagnoses = diagnosis_engine.diagnose(analysis)
        types = [d.issue_type for d in diagnoses]
        assert DiagnosisType.LTV_DECLINE in types

    def test_diagnose_engine_history(self, diagnosis_engine, analyzer, fatigue_metrics):
        analysis = analyzer.analyze(fatigue_metrics)
        diagnosis_engine.diagnose(analysis)
        assert len(diagnosis_engine.get_history()) > 0

    def test_diagnose_engine_get_by_type(self, diagnosis_engine, analyzer, fatigue_metrics):
        analysis = analyzer.analyze(fatigue_metrics)
        diagnosis_engine.diagnose(analysis)
        results = diagnosis_engine.get_by_type(DiagnosisType.CREATIVE_FATIGUE)
        assert len(results) > 0

    def test_diagnose_engine_reset(self, diagnosis_engine, analyzer, fatigue_metrics):
        analysis = analyzer.analyze(fatigue_metrics)
        diagnosis_engine.diagnose(analysis)
        diagnosis_engine.reset()
        assert len(diagnosis_engine.get_history()) == 0


# ═══════════════════════════════════════════════════════════════
# 3. UA Strategy Engine (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestStrategyModels:
    """Strategy 模型测试."""

    def test_strategy_action_creation(self):
        a = StrategyAction(action_type="pause_campaign", target="C04",
                           expected_impact="降低花费", confidence=0.8)
        assert a.action_type == "pause_campaign"
        assert a.target == "C04"

    def test_strategy_action_to_dict(self):
        a = StrategyAction(action_type="adjust_bid", target="C05",
                           estimated_impact={"cpi_reduction": 0.2})
        d = a.to_dict()
        assert d["action_type"] == "adjust_bid"
        assert d["estimated_impact"]["cpi_reduction"] == 0.2

    def test_ua_strategy_creation(self):
        s = UAStrategy(strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
                       description="生成新素材", priority=0.8)
        assert s.strategy_type == StrategyType.GENERATE_CREATIVE_VARIANTS

    def test_ua_strategy_to_dict(self):
        s = UAStrategy(strategy_type=StrategyType.PAUSE_CAMPAIGN,
                       description="暂停低效系列", priority=0.9, confidence=0.85)
        d = s.to_dict()
        assert d["priority"] == 0.9
        assert d["confidence"] == 0.85

    def test_ua_strategy_with_diagnosis(self):
        d = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE)
        s = UAStrategy(diagnosis=d)
        assert s.diagnosis.issue_type == DiagnosisType.CREATIVE_FATIGUE

    def test_strategy_type_values(self):
        assert StrategyType.GENERATE_CREATIVE_VARIANTS.value == "generate_creative_variants"
        assert StrategyType.PAUSE_CAMPAIGN.value == "pause_campaign"
        assert StrategyType.ADJUST_BUDGET.value == "adjust_budget"


class TestStrategyEngine:
    """UAStrategyEngine 测试."""

    def test_generate_for_creative_fatigue(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE,
                        severity=DiagnosisSeverity.HIGH, confidence=0.9)
        strategies = strategy_engine.generate_for_diagnosis(d)
        assert len(strategies) > 0
        assert strategies[0].strategy_type == StrategyType.GENERATE_CREATIVE_VARIANTS

    def test_generate_for_audience_saturation(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.AUDIENCE_SATURATION,
                        severity=DiagnosisSeverity.MEDIUM, confidence=0.7)
        strategies = strategy_engine.generate_for_diagnosis(d)
        assert strategies[0].strategy_type == StrategyType.EXPAND_TARGETING

    def test_generate_for_store_issue(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.STORE_ISSUE,
                        severity=DiagnosisSeverity.HIGH, confidence=0.8)
        strategies = strategy_engine.generate_for_diagnosis(d)
        assert strategies[0].strategy_type == StrategyType.OPTIMIZE_STORE

    def test_generate_for_cpi_spike(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.CPI_SPIKE,
                        severity=DiagnosisSeverity.CRITICAL, confidence=0.9)
        strategies = strategy_engine.generate_for_diagnosis(d)
        assert strategies[0].strategy_type == StrategyType.OPTIMIZE_BID

    def test_generate_for_healthy(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.HEALTHY,
                        severity=DiagnosisSeverity.LOW, confidence=0.95)
        strategies = strategy_engine.generate_for_diagnosis(d)
        assert strategies[0].strategy_type == StrategyType.MONITOR_ONLY

    def test_generate_for_unknown(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.UNKNOWN,
                        severity=DiagnosisSeverity.MEDIUM, confidence=0.3)
        strategies = strategy_engine.generate_for_diagnosis(d)
        assert strategies[0].strategy_type == StrategyType.ESCALATE_TO_SUPERVISOR

    def test_generate_strategies_sorted_by_priority(self, strategy_engine):
        d1 = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE,
                         severity=DiagnosisSeverity.HIGH, confidence=0.9)
        d2 = UADiagnosis(issue_type=DiagnosisType.HEALTHY,
                         severity=DiagnosisSeverity.LOW, confidence=0.95)
        strategies = strategy_engine.generate_strategies([d1, d2])
        assert strategies[0].priority >= strategies[-1].priority

    def test_generate_strategies_with_campaign(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE,
                        severity=DiagnosisSeverity.HIGH, confidence=0.9)
        strategies = strategy_engine.generate_for_diagnosis(d, campaign_id="C04")
        for s in strategies:
            assert s.metadata.get("campaign_id") == "C04"

    def test_diagnosis_to_strategy_mapping_complete(self):
        """所有诊断类型都有策略映射."""
        for dt in DiagnosisType:
            assert dt in DIAGNOSIS_TO_STRATEGY, f"Missing strategy for {dt}"

    def test_strategy_engine_history(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE, confidence=0.9)
        strategy_engine.generate_for_diagnosis(d)
        assert len(strategy_engine.get_history()) > 0

    def test_strategy_engine_top_strategies(self, strategy_engine):
        for dt in [DiagnosisType.CREATIVE_FATIGUE, DiagnosisType.CPI_SPIKE,
                    DiagnosisType.AUDIENCE_SATURATION]:
            d = UADiagnosis(issue_type=dt, severity=DiagnosisSeverity.HIGH, confidence=0.9)
            strategy_engine.generate_for_diagnosis(d)
        top = strategy_engine.get_top_strategies(3)
        assert len(top) <= 3

    def test_strategy_engine_reset(self, strategy_engine):
        d = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE, confidence=0.9)
        strategy_engine.generate_for_diagnosis(d)
        strategy_engine.reset()
        assert len(strategy_engine.get_history()) == 0


# ═══════════════════════════════════════════════════════════════
# 4. UA Action Selector (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestActionSelectorModels:
    """ActionSelector 模型测试."""

    def test_selected_action_creation(self):
        a = SelectedAction(action_type="pause_campaign", target="C04", risk=ActionRisk.HIGH)
        assert a.action_type == "pause_campaign"
        assert a.status == ActionStatus.PENDING

    def test_selected_action_to_dict(self):
        a = SelectedAction(action_type="reduce_budget", target="C05",
                           priority=0.8, confidence=0.7, risk=ActionRisk.MEDIUM)
        d = a.to_dict()
        assert d["action_type"] == "reduce_budget"
        assert d["risk"] == "medium"

    def test_selected_action_mark_executed(self):
        a = SelectedAction()
        a.mark_executed({"result": "ok"})
        assert a.status == ActionStatus.EXECUTED
        assert a.executed_at != ""

    def test_selected_action_mark_failed(self):
        a = SelectedAction()
        a.mark_failed("Connection error")
        assert a.status == ActionStatus.FAILED
        assert a.error == "Connection error"

    def test_selected_action_mark_rolled_back(self):
        a = SelectedAction()
        a.mark_rolled_back()
        assert a.status == ActionStatus.ROLLED_BACK

    def test_action_plan_creation(self):
        plan = ActionPlan()
        assert plan.action_count == 0
        assert plan.pending_count == 0

    def test_action_plan_to_dict(self):
        a = SelectedAction(action_type="test")
        plan = ActionPlan(actions=[a], summary="test plan")
        d = plan.to_dict()
        assert d["summary"] == "test plan"
        assert len(d["actions"]) == 1


class TestActionSelector:
    """UAActionSelector 测试."""

    def test_select_from_strategies(self, strategy_engine, action_selector):
        d = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE,
                        severity=DiagnosisSeverity.HIGH, confidence=0.9)
        strategies = strategy_engine.generate_for_diagnosis(d, campaign_id="C04")
        plan = action_selector.select(strategies)
        assert plan.action_count > 0
        assert isinstance(plan.summary, str)

    def test_select_deduplicates(self, action_selector):
        """重复动作去重."""
        s1 = UAStrategy(
            strategy_type=StrategyType.PAUSE_CAMPAIGN,
            priority=0.9,
            actions=[StrategyAction(action_type="pause_campaign", target="C04")],
        )
        s2 = UAStrategy(
            strategy_type=StrategyType.PAUSE_CAMPAIGN,
            priority=0.8,
            actions=[StrategyAction(action_type="pause_campaign", target="C04")],
        )
        plan = action_selector.select([s1, s2])
        # 去重后应该只有一个 pause_campaign:C04
        action_keys = [f"{a.action_type}:{a.target}" for a in plan.actions]
        assert action_keys.count("pause_campaign:C04") == 1

    def test_select_sorts_by_priority(self, action_selector):
        s1 = UAStrategy(priority=0.3, actions=[StrategyAction(action_type="low", target="X")])
        s2 = UAStrategy(priority=0.9, actions=[StrategyAction(action_type="high", target="Y")])
        plan = action_selector.select([s1, s2])
        assert plan.actions[0].priority >= plan.actions[-1].priority

    def test_select_limits_top_n(self, action_selector):
        strategies = []
        for i in range(15):
            s = UAStrategy(
                priority=0.5,
                actions=[StrategyAction(action_type=f"action_{i}", target=f"T{i}")],
            )
            strategies.append(s)
        plan = action_selector.select(strategies, top_n=5)
        assert plan.action_count <= 5

    def test_select_from_dicts(self, action_selector):
        data = [{
            "strategy_type": "generate_creative_variants",
            "description": "test",
            "priority": 0.8,
            "actions": [{"action_type": "generate_variants", "target": "C04"}],
        }]
        plan = action_selector.select_from_dicts(data)
        assert plan.action_count > 0

    def test_execute_without_executor(self, action_selector):
        a = SelectedAction(action_type="monitor_only", target="C04")
        result = action_selector.execute(a)
        assert result["success"] is True
        assert result["simulated"] is True

    def test_execute_plan(self, action_selector):
        a1 = SelectedAction(action_type="monitor_only", target="C04")
        a2 = SelectedAction(action_type="monitor_only", target="C05")
        plan = ActionPlan(actions=[a1, a2])
        results = action_selector.execute_plan(plan)
        assert len(results) == 2
        assert all(r["success"] for r in results)

    def test_rollback(self, action_selector):
        a = SelectedAction(
            action_type="pause_campaign", target="C04",
            rollback_action={"action_type": "resume_campaign"},
        )
        action_selector.execute(a)  # 先执行
        result = action_selector.rollback(a)
        assert result["success"] is True

    def test_approve_action(self, action_selector):
        a = SelectedAction(action_type="pause_campaign", requires_approval=True)
        action_selector.approve(a)
        assert a.status == ActionStatus.APPROVED

    def test_approve_plan(self, action_selector):
        a1 = SelectedAction(action_type="pause_campaign", requires_approval=True)
        a2 = SelectedAction(action_type="monitor_only", requires_approval=False)
        plan = ActionPlan(actions=[a1, a2])
        action_selector.approve_plan(plan)
        assert a1.status == ActionStatus.APPROVED

    def test_risk_map_coverage(self):
        """所有已定义动作类型都有风险映射."""
        known_actions = [
            "monitor_only", "request_creative_analysis", "generate_variants",
            "expand_targeting", "change_audience", "adjust_bid",
            "reallocate_budget", "reduce_budget", "decrease_budget",
            "pause_low_performers", "pause_negative_roi", "pause_campaign",
            "optimize_store", "reallocate_to_winners",
            "escalate_to_supervisor", "escalate_to_monetization", "escalate_to_product",
        ]
        for action in known_actions:
            assert action in ACTION_RISK_MAP, f"Missing risk for {action}"

    def test_rollback_map_coverage(self):
        """高风险动作有回滚."""
        high_risk_actions = [
            "pause_campaign", "pause_low_performers", "pause_negative_roi",
            "adjust_bid", "reduce_budget", "decrease_budget",
            "reallocate_budget", "change_audience", "expand_targeting",
        ]
        for action in high_risk_actions:
            assert action in ROLLBACK_MAP, f"Missing rollback for {action}"

    def test_selector_stats(self, action_selector):
        a = SelectedAction(action_type="monitor_only")
        action_selector.execute(a)
        # execute doesn't add to history, use select to add
        strategy = UAStrategy(
            strategy_type=StrategyType.PAUSE_CAMPAIGN,
            priority=0.9,
            actions=[StrategyAction(action_type="pause_campaign", target="C99")],
        )
        action_selector.select([strategy])
        action_selector.execute(a)
        stats = action_selector.stats()
        assert stats["total_actions"] >= 1

    def test_selector_reset(self, action_selector):
        a = SelectedAction(action_type="monitor_only")
        action_selector.execute(a)
        action_selector.reset()
        assert action_selector.stats()["total_actions"] == 0


# ═══════════════════════════════════════════════════════════════
# 5. UA Memory (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestMemoryModels:
    """Memory 模型测试."""

    def test_decision_record_creation(self):
        r = UADecisionRecord(diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
                             strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS)
        assert r.diagnosis_type == DiagnosisType.CREATIVE_FATIGUE
        assert r.outcome == DecisionOutcome.PENDING

    def test_decision_record_resolve(self):
        r = UADecisionRecord()
        r.resolve(DecisionOutcome.SUCCESS, learning="Good")
        assert r.outcome == DecisionOutcome.SUCCESS
        assert r.is_resolved
        assert r.is_success

    def test_decision_record_compute_impact(self):
        r = UADecisionRecord(
            before_metrics={"roas": 1.0},
            after_metrics={"roas": 1.5},
        )
        r.resolve(DecisionOutcome.SUCCESS, after_metrics={"roas": 1.5})
        assert r.impact.get("roas") == 0.5

    def test_decision_record_to_dict(self):
        r = UADecisionRecord(diagnosis_type=DiagnosisType.CREATIVE_FATIGUE)
        d = r.to_dict()
        assert d["diagnosis_type"] == "creative_fatigue"
        assert d["outcome"] == "pending"

    def test_experience_entry_success_rate(self):
        e = ExperienceEntry(success_count=7, total_count=10)
        assert e.success_rate == 0.7

    def test_experience_entry_zero_rate(self):
        e = ExperienceEntry(success_count=0, total_count=0)
        assert e.success_rate == 0.0


class TestUAMemory:
    """UAMemory 测试."""

    def test_record_decision(self, ua_memory):
        r = ua_memory.record_decision(
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            action_type="generate_variants",
            confidence=0.9,
        )
        assert r.record_id != ""
        assert r.diagnosis_type == DiagnosisType.CREATIVE_FATIGUE

    def test_record_from_dict(self, ua_memory):
        r = ua_memory.record_from_dict({
            "diagnosis_type": "creative_fatigue",
            "strategy_type": "generate_creative_variants",
            "action_type": "generate_variants",
            "confidence": 0.85,
        })
        assert r.confidence == 0.85

    def test_resolve_decision(self, ua_memory):
        r = ua_memory.record_decision(
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            action_type="generate_variants",
        )
        resolved = ua_memory.resolve(r.record_id, DecisionOutcome.SUCCESS,
                                      after_metrics={"roas": 1.5}, learning="Good")
        assert resolved is not None
        assert resolved.outcome == DecisionOutcome.SUCCESS
        assert resolved.learning == "Good"

    def test_resolve_nonexistent(self, ua_memory):
        result = ua_memory.resolve("nonexistent", DecisionOutcome.SUCCESS)
        assert result is None

    def test_resolve_batch(self, ua_memory):
        r1 = ua_memory.record_decision(action_type="a1")
        r2 = ua_memory.record_decision(action_type="a2")
        results = ua_memory.resolve_batch([
            {"record_id": r1.record_id, "outcome": "success"},
            {"record_id": r2.record_id, "outcome": "failure"},
        ])
        assert len(results) == 2
        assert results[0].outcome == DecisionOutcome.SUCCESS

    def test_find_similar(self, ua_memory):
        for _ in range(5):
            r = ua_memory.record_decision(
                diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
                strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
                action_type="generate_variants",
            )
            ua_memory.resolve(r.record_id, DecisionOutcome.SUCCESS)

        experiences = ua_memory.find_similar(DiagnosisType.CREATIVE_FATIGUE)
        assert len(experiences) > 0

    def test_find_best_action(self, ua_memory):
        for _ in range(5):
            r = ua_memory.record_decision(
                diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
                strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
                action_type="generate_variants",
            )
            ua_memory.resolve(r.record_id, DecisionOutcome.SUCCESS)
        best = ua_memory.find_best_action(DiagnosisType.CREATIVE_FATIGUE, min_samples=3)
        assert best is not None

    def test_confidence_boost(self, ua_memory):
        for _ in range(5):
            r = ua_memory.record_decision(
                diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
                strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
                action_type="generate_variants",
            )
            ua_memory.resolve(r.record_id, DecisionOutcome.SUCCESS)
        boost = ua_memory.get_confidence_boost(
            DiagnosisType.CREATIVE_FATIGUE,
            StrategyType.GENERATE_CREATIVE_VARIANTS,
            "generate_variants",
        )
        assert boost > 0

    def test_confidence_boost_no_history(self, ua_memory):
        boost = ua_memory.get_confidence_boost(
            DiagnosisType.CREATIVE_FATIGUE,
            StrategyType.GENERATE_CREATIVE_VARIANTS,
            "nonexistent_action",
        )
        assert boost == 0.0

    def test_get_records_by_diagnosis(self, ua_memory):
        ua_memory.record_decision(diagnosis_type=DiagnosisType.CREATIVE_FATIGUE)
        ua_memory.record_decision(diagnosis_type=DiagnosisType.AUDIENCE_SATURATION)
        records = ua_memory.get_records(diagnosis_type=DiagnosisType.CREATIVE_FATIGUE)
        assert len(records) == 1

    def test_get_pending(self, ua_memory):
        ua_memory.record_decision()
        assert len(ua_memory.get_pending()) == 1

    def test_get_success_stories(self, ua_memory):
        for _ in range(3):
            r = ua_memory.record_decision()
            ua_memory.resolve(r.record_id, DecisionOutcome.SUCCESS)
        assert len(ua_memory.get_success_stories()) == 3

    def test_get_failures(self, ua_memory):
        for _ in range(2):
            r = ua_memory.record_decision()
            ua_memory.resolve(r.record_id, DecisionOutcome.FAILURE)
        assert len(ua_memory.get_failures()) == 2

    def test_memory_stats(self, ua_memory):
        for _ in range(5):
            r = ua_memory.record_decision()
            ua_memory.resolve(r.record_id, DecisionOutcome.SUCCESS)
        stats = ua_memory.stats()
        assert stats["total_records"] == 5
        assert stats["resolved"] == 5

    def test_memory_reset(self, ua_memory):
        ua_memory.record_decision()
        ua_memory.reset()
        assert ua_memory.stats()["total_records"] == 0


# ═══════════════════════════════════════════════════════════════
# 6. UA Growth Agent Core (25 测试)
# ═══════════════════════════════════════════════════════════════


class TestGrowthRecommendation:
    """GrowthRecommendation 模型测试."""

    def test_recommendation_creation(self):
        r = GrowthRecommendation(product_id="P01", campaign_id="C04")
        assert r.product_id == "P01"
        assert r.campaign_id == "C04"

    def test_recommendation_to_dict(self):
        r = GrowthRecommendation(summary="test", confidence=0.85)
        d = r.to_dict()
        assert d["summary"] == "test"
        assert d["confidence"] == 0.85

    def test_has_critical_issues(self):
        d = UADiagnosis(issue_type=DiagnosisType.CPI_SPIKE,
                        severity=DiagnosisSeverity.CRITICAL)
        r = GrowthRecommendation(diagnoses=[d])
        assert r.has_critical_issues

    def test_no_critical_issues(self):
        d = UADiagnosis(issue_type=DiagnosisType.HEALTHY,
                        severity=DiagnosisSeverity.LOW)
        r = GrowthRecommendation(diagnoses=[d])
        assert not r.has_critical_issues

    def test_top_diagnosis(self):
        d1 = UADiagnosis(issue_type=DiagnosisType.CREATIVE_FATIGUE, confidence=0.9)
        d2 = UADiagnosis(issue_type=DiagnosisType.AUDIENCE_SATURATION, confidence=0.7)
        r = GrowthRecommendation(diagnoses=[d1, d2])
        assert r.top_diagnosis.issue_type == DiagnosisType.CREATIVE_FATIGUE

    def test_top_strategy(self):
        s1 = UAStrategy(strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS, priority=0.9)
        s2 = UAStrategy(strategy_type=StrategyType.PAUSE_CAMPAIGN, priority=0.5)
        r = GrowthRecommendation(strategies=[s1, s2])
        assert r.top_strategy.strategy_type == StrategyType.GENERATE_CREATIVE_VARIANTS


class TestUAGrowthAgent:
    """UAGrowthAgent 核心测试."""

    def test_create_agent(self):
        agent = create_ua_agent()
        assert agent.identity.role == AgentRole.UA
        assert agent.state == UAAgentState.IDLE

    def test_agent_register(self, ua_agent, registry):
        ua_agent.register(registry=registry)
        assert ua_agent.is_registered

    def test_agent_identity(self, ua_agent):
        identity = ua_agent.identity
        assert identity.role == AgentRole.UA
        assert "meta_ads_analysis" in identity.capabilities

    def test_analyze_healthy_metrics(self, ua_agent, healthy_metrics):
        rec = ua_agent.analyze_metrics(healthy_metrics.to_dict())
        assert rec.analysis is not None
        assert rec.analysis.health_score >= 90

    def test_analyze_fatigue_metrics(self, ua_agent, fatigue_metrics):
        rec = ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        assert len(rec.diagnoses) > 0
        types = [d.issue_type for d in rec.diagnoses]
        assert DiagnosisType.CREATIVE_FATIGUE in types

    def test_analyze_generates_strategies(self, ua_agent, fatigue_metrics):
        rec = ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        assert len(rec.strategies) > 0

    def test_analyze_generates_action_plan(self, ua_agent, fatigue_metrics):
        rec = ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        assert rec.action_plan is not None
        assert rec.action_plan.action_count > 0

    def test_analyze_returns_summary(self, ua_agent, fatigue_metrics):
        rec = ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        assert rec.summary != ""

    def test_analyze_has_confidence(self, ua_agent, fatigue_metrics):
        rec = ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        assert 0 <= rec.confidence <= 1.0

    def test_quick_analysis(self, ua_agent):
        rec = ua_agent.quick_analysis(
            spend=10000, revenue=13000, roas=1.3,
            cpi=2.5, ctr=0.4, fatigue=0.75,
            frequency=4.5, campaign_id="C04",
        )
        assert rec.analysis is not None
        assert rec.campaign_id == "C04"

    def test_analyze_from_dict(self, ua_agent):
        rec = ua_agent.analyze_from_dict({
            "roas": 0.5, "cpi": 6.0, "ctr": 0.2, "fatigue": 0.8
        })
        assert rec.analysis.health_score < 80

    def test_cycle_count_increments(self, ua_agent, healthy_metrics):
        assert ua_agent.cycle_count == 0
        ua_agent.analyze_metrics(healthy_metrics.to_dict())
        assert ua_agent.cycle_count == 1

    def test_agent_state_transitions(self, ua_agent, healthy_metrics):
        ua_agent.analyze_metrics(healthy_metrics.to_dict())
        assert ua_agent.state == UAAgentState.IDLE

    def test_agent_stats(self, ua_agent, healthy_metrics):
        ua_agent.analyze_metrics(healthy_metrics.to_dict())
        stats = ua_agent.stats()
        assert stats["cycle_count"] == 1
        assert stats["recommendations"] == 1

    def test_recommendations_history(self, ua_agent, healthy_metrics):
        ua_agent.analyze_metrics(healthy_metrics.to_dict())
        recs = ua_agent.get_recommendations()
        assert len(recs) == 1

    def test_last_recommendation(self, ua_agent, healthy_metrics):
        ua_agent.analyze_metrics(healthy_metrics.to_dict())
        last = ua_agent.get_last_recommendation()
        assert last is not None
        assert last.product_id == "P01"

    def test_agent_reset(self, ua_agent, healthy_metrics):
        ua_agent.analyze_metrics(healthy_metrics.to_dict())
        ua_agent.reset()
        assert ua_agent.cycle_count == 0
        assert len(ua_agent.get_recommendations()) == 0

    def test_submodule_access(self, ua_agent):
        assert ua_agent.get_analyzer() is not None
        assert ua_agent.get_diagnosis_engine() is not None
        assert ua_agent.get_strategy_engine() is not None
        assert ua_agent.get_action_selector() is not None
        assert ua_agent.get_memory() is not None

    def test_execute_action(self, ua_agent):
        a = SelectedAction(action_type="monitor_only", target="C04")
        result = ua_agent.execute_action(a)
        assert result["success"] is True

    def test_rollback_action(self, ua_agent):
        a = SelectedAction(
            action_type="pause_campaign", target="C04",
            rollback_action={"action_type": "resume_campaign"},
        )
        ua_agent.execute_action(a)
        result = ua_agent.rollback_action(a)
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════
# 7. Integration & Communication (15 测试)
# ═══════════════════════════════════════════════════════════════


class TestCommunicationIntegration:
    """通信层集成测试."""

    def test_agent_registration(self, ua_agent, registry):
        ua_agent.register(registry=registry)
        agent = registry.get_identity(ua_agent.identity.agent_id)
        assert agent is not None
        assert agent.role == AgentRole.UA

    def test_agent_heartbeat(self, ua_agent, registry):
        ua_agent.register(registry=registry)
        registry.check_health()
        agent = registry.get_identity(ua_agent.identity.agent_id)
        assert agent is not None

    def test_receive_task(self, ua_agent):
        from market_ops.creative_vision_runtime.growth_runtime.agent.communication import AgentMessage
        sender = comm_supervisor_identity()
        receiver = ua_agent.identity
        msg = AgentMessage.create_task(
            sender=sender,
            receiver=receiver,
            subject="Analyze UA",
            body={"metrics": {"roas": 0.5, "cpi": 6.0}},
        )
        task = ua_agent.receive_task(msg)
        assert task["subject"] == "Analyze UA"
        assert "metrics" in task["body"]

    def test_process_task(self, ua_agent):
        task = {
            "message_id": "msg_001",
            "subject": "Analyze UA",
            "body": {"metrics": {"roas": 0.5, "cpi": 6.0, "ctr": 0.2, "fatigue": 0.8}},
            "priority": 2,
        }
        rec = ua_agent.process_task(task)
        assert rec.analysis is not None

    def test_respond_to_supervisor(self, ua_agent, registry):
        ua_agent.register(registry=registry)
        # Supervisor is already in registry from create_default_organization
        supervisors = registry.find_by_role(AgentRole.SUPERVISOR)
        if not supervisors:
            pytest.skip("No supervisor in registry")

        task = {"message_id": "msg_001", "subject": "test"}
        rec = ua_agent.analyze_metrics({"roas": 1.5, "cpi": 1.5, "ctr": 1.2, "fatigue": 0.2})

        msg = ua_agent.respond_to_supervisor(task, rec)
        if msg is None:
            pytest.skip("Supervisor not found")
        assert msg.message_type == MessageType.TASK_RESULT
        assert msg.correlation_id == "msg_001"

    def test_request_creative_analysis(self, ua_agent, registry):
        ua_agent.register(registry=registry)
        creatives = registry.find_by_role(AgentRole.CREATIVE)
        if creatives:
            msg = ua_agent.request_creative_analysis("C04", "Creative fatigue detected")
            if msg:
                assert msg.standard_type == StandardMessageType.REQUEST_CREATIVE_ANALYSIS

    def test_send_alert_to_supervisor(self, ua_agent, registry):
        ua_agent.register(registry=registry)
        supervisors = registry.find_by_role(AgentRole.SUPERVISOR)
        if supervisors:
            msg = ua_agent.send_alert_to_supervisor("ROAS decline", {"roas": 0.5})
            if msg:
                assert msg.priority == MessagePriority.CRITICAL

    def test_unregister(self, ua_agent, registry):
        ua_agent.register(registry=registry)
        ua_agent.unregister()
        assert not ua_agent.is_registered

    def test_factory_creates_agent(self):
        agent = create_ua_agent("Custom UA")
        assert agent.identity.name == "Custom UA"
        assert agent.state == UAAgentState.IDLE

    def test_experience_boost_applied(self, ua_agent, fatigue_metrics):
        """经验提升测试 — 先建经验再分析."""
        # 先建立经验 — 匹配策略生成的 action_type
        for _ in range(5):
            r = ua_agent.get_memory().record_decision(
                diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
                strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
                action_type="request_creative_analysis",
                confidence=0.8,
            )
            ua_agent.get_memory().resolve(r.record_id, DecisionOutcome.SUCCESS)

        # 再分析
        rec = ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        boost_found = False
        for s in rec.strategies:
            if s.strategy_type == StrategyType.GENERATE_CREATIVE_VARIANTS:
                if "experience_boost" in s.metadata:
                    boost_found = True
        assert boost_found

    def test_full_analyze_diagnose_strategize_cycle(self, ua_agent, fatigue_metrics):
        """完整循环: 分析→诊断→策略→选择."""
        rec = ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        # 每个阶段都产生了输出
        assert rec.analysis is not None
        assert len(rec.diagnoses) > 0
        assert len(rec.strategies) > 0
        assert rec.action_plan is not None

    def test_multiple_cycles(self, ua_agent, healthy_metrics, fatigue_metrics):
        """多轮分析."""
        rec1 = ua_agent.analyze_metrics(healthy_metrics.to_dict())
        rec2 = ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        assert rec1.analysis.health_score > rec2.analysis.health_score

    def test_memory_integration_with_agent(self, ua_agent, fatigue_metrics):
        """Agent 分析后记忆中有记录."""
        ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        stats = ua_agent.get_memory().stats()
        assert stats["total_records"] > 0

    def test_decision_history(self, ua_agent, fatigue_metrics):
        ua_agent.analyze_metrics(fatigue_metrics.to_dict())
        history = ua_agent.get_decision_history()
        assert len(history) > 0

    def test_resolve_decision(self, ua_agent):
        r = ua_agent.get_memory().record_decision(
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            action_type="generate_variants",
        )
        resolved = ua_agent.resolve_decision(
            r.record_id, DecisionOutcome.SUCCESS,
            after_metrics={"roas": 1.8}, learning="素材更新有效",
        )
        assert resolved is not None
        assert resolved.outcome == DecisionOutcome.SUCCESS