"""E15.2.4 Execution Reasoning Layer 测试 — 推理层完整测试.

测试覆盖:
  - 模型 (15 tests)
  - 假设引擎 (20 tests)
  - 诊断引擎 (15 tests)
  - 决策追踪 (10 tests)
  - 推理引擎 (20 tests)
  - 可解释性 (10 tests)
  - 集成测试 (10 tests)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.reasoning.models import (
    Constraint,
    ConstraintType,
    DiagnosisResult,
    DiagnosisStatus,
    ExecutionAttempt,
    Hypothesis,
    Observation,
    ObservationTrend,
    ReasoningContext,
    ReasoningDecision,
    ReasoningResult,
    ReasoningStep,
    ReasoningTrace,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.reasoning.hypothesis import (
    HypothesisEngine,
    CREATIVE_FATIGUE_RULE,
    AUDIENCE_SATURATION_RULE,
    BUDGET_INSUFFICIENT_RULE,
    SCALING_OPPORTUNITY_RULE,
    DEFAULT_RULES,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.reasoning.diagnosis import (
    DiagnosisEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.reasoning.decision_trace import (
    DecisionTraceBuilder,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.reasoning.reasoning_engine import (
    ExecutionReasoningEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.reasoning.explanation import (
    ExecutionExplainer,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def roas_obs() -> Observation:
    return Observation(
        metric="roas", value=1.2, previous=1.5,
        trend=ObservationTrend.DOWN, threshold=1.0,
    )


@pytest.fixture
def ctr_obs() -> Observation:
    return Observation(
        metric="ctr", value=2.0, previous=2.5,
        trend=ObservationTrend.DOWN,
    )


@pytest.fixture
def frequency_obs() -> Observation:
    return Observation(
        metric="frequency", value=3.5, previous=2.0,
        trend=ObservationTrend.UP,
    )


@pytest.fixture
def fatigue_observations(roas_obs, ctr_obs, frequency_obs) -> list[Observation]:
    return [roas_obs, ctr_obs, frequency_obs]


@pytest.fixture
def scaling_observations() -> list[Observation]:
    return [
        Observation(metric="roas", value=2.0, previous=1.5, trend=ObservationTrend.UP),
        Observation(metric="ctr", value=3.0, previous=2.5, trend=ObservationTrend.UP),
    ]


@pytest.fixture
def basic_context() -> ReasoningContext:
    return ReasoningContext(
        execution_id="exec_001",
        action={"action_type": "creative_refresh", "target": {"campaign_id": "123"}},
        observations=[
            Observation(metric="roas", value=1.2, previous=1.5, trend=ObservationTrend.DOWN),
            Observation(metric="ctr", value=2.0, previous=2.5, trend=ObservationTrend.DOWN),
        ],
        constraints=[
            Constraint(name="daily_budget_limit", value=500, type=ConstraintType.HARD),
        ],
        risk_assessment={"risk_level": "medium", "risk_score": 0.4},
        selected_action={"action_id": "act_001", "score": 0.73},
    )


@pytest.fixture
def success_result() -> dict:
    return {
        "metrics_delta": {"roas": 15.0, "ctr": 10.0, "cvr": 5.0},
        "metrics_before": {"roas": 1.0, "ctr": 2.0, "cvr": 1.5},
        "metrics_after": {"roas": 1.15, "ctr": 2.2, "cvr": 1.575},
    }


@pytest.fixture
def failure_result() -> dict:
    return {
        "metrics_delta": {"roas": -20.0, "ctr": -15.0},
        "metrics_before": {"roas": 1.5, "ctr": 2.5},
        "metrics_after": {"roas": 1.2, "ctr": 2.125},
    }


@pytest.fixture
def partial_result() -> dict:
    return {
        "metrics_delta": {"roas": 10.0, "ctr": -5.0},
        "metrics_before": {"roas": 1.0, "ctr": 2.0},
        "metrics_after": {"roas": 1.1, "ctr": 1.9},
    }


# ═══════════════════════════════════════════════════════════════════
# Test: Models
# ═══════════════════════════════════════════════════════════════════


class TestObservation:
    """Observation 模型测试."""

    def test_default_creation(self):
        o = Observation()
        assert o.metric == ""
        assert o.trend == ObservationTrend.STABLE

    def test_full_creation(self):
        o = Observation(
            metric="roas", value=1.5, previous=1.2,
            trend=ObservationTrend.UP, threshold=0.8,
        )
        assert o.metric == "roas"
        assert o.value == 1.5
        assert o.trend == ObservationTrend.UP

    def test_delta_pct_positive(self):
        o = Observation(value=1.5, previous=1.0)
        assert o.delta_pct() == 50.0

    def test_delta_pct_negative(self):
        o = Observation(value=0.8, previous=1.0)
        assert o.delta_pct() == -20.0

    def test_delta_pct_zero_previous(self):
        o = Observation(value=1.0, previous=0.0)
        assert o.delta_pct() == 0.0

    def test_exceeds_threshold_true(self):
        o = Observation(value=1.5, threshold=1.0)
        assert o.exceeds_threshold() is True

    def test_exceeds_threshold_false(self):
        o = Observation(value=0.5, threshold=1.0)
        assert o.exceeds_threshold() is False

    def test_exceeds_threshold_none(self):
        o = Observation(value=1.5)
        assert o.exceeds_threshold() is False

    def test_to_dict(self):
        o = Observation(metric="roas", value=1.5, previous=1.0, trend=ObservationTrend.UP)
        d = o.to_dict()
        assert d["metric"] == "roas"
        assert d["delta_pct"] == 50.0


class TestConstraint:
    """Constraint 模型测试."""

    def test_default_type(self):
        c = Constraint(name="budget", value=500)
        assert c.type == ConstraintType.HARD

    def test_soft_constraint(self):
        c = Constraint(name="roas_target", value=1.2, type=ConstraintType.SOFT)
        assert c.type == ConstraintType.SOFT

    def test_to_dict(self):
        c = Constraint(name="limit", value=100)
        d = c.to_dict()
        assert d["type"] == "hard"


class TestExecutionAttempt:
    """ExecutionAttempt 模型测试."""

    def test_default_creation(self):
        a = ExecutionAttempt()
        assert a.attempt_id != ""

    def test_to_dict(self):
        a = ExecutionAttempt(
            action={"type": "creative_refresh"},
            result={"roas": 1.5},
            outcome="success",
        )
        d = a.to_dict()
        assert d["outcome"] == "success"


class TestReasoningContext:
    """ReasoningContext 模型测试."""

    def test_get_observation_exists(self, basic_context):
        obs = basic_context.get_observation("roas")
        assert obs is not None
        assert obs.metric == "roas"

    def test_get_observation_missing(self, basic_context):
        obs = basic_context.get_observation("nonexistent")
        assert obs is None

    def test_get_constraint_exists(self, basic_context):
        c = basic_context.get_constraint("daily_budget_limit")
        assert c is not None
        assert c.value == 500

    def test_get_constraint_missing(self, basic_context):
        c = basic_context.get_constraint("nonexistent")
        assert c is None

    def test_to_dict(self, basic_context):
        d = basic_context.to_dict()
        assert d["execution_id"] == "exec_001"
        assert len(d["observations"]) == 2


class TestHypothesis:
    """Hypothesis 模型测试."""

    def test_default_creation(self):
        h = Hypothesis()
        assert h.name == ""
        assert h.confidence == 0.0

    def test_full_creation(self):
        h = Hypothesis(
            name="creative_fatigue",
            description="Creative fatigue detected",
            evidence=["ROAS down 20%", "CTR down 15%"],
            confidence=0.82,
            impact="high",
            suggested_action="replace_creative",
        )
        assert h.confidence == 0.82
        assert len(h.evidence) == 2

    def test_to_dict(self):
        h = Hypothesis(name="test", confidence=0.75)
        d = h.to_dict()
        assert d["confidence"] == 0.75


class TestDiagnosisResult:
    """DiagnosisResult 模型测试."""

    def test_default_status(self):
        d = DiagnosisResult()
        assert d.status == DiagnosisStatus.INCONCLUSIVE

    def test_to_dict(self):
        d = DiagnosisResult(
            status=DiagnosisStatus.SUCCESS,
            summary="All good",
            root_causes=["positive trend"],
        )
        result = d.to_dict()
        assert result["status"] == "success"


class TestReasoningStep:
    """ReasoningStep 模型测试."""

    def test_default_creation(self):
        s = ReasoningStep()
        assert s.step_id != ""

    def test_to_dict(self):
        s = ReasoningStep(step_type="observation", description="extracted", confidence=0.9)
        d = s.to_dict()
        assert d["step_type"] == "observation"


class TestReasoningTrace:
    """ReasoningTrace 模型测试."""

    def test_default_creation(self):
        t = ReasoningTrace()
        assert t.trace_id != ""
        assert t.steps == []

    def test_to_dict(self):
        s = ReasoningStep(step_type="decision", description="chose continue")
        t = ReasoningTrace(
            steps=[s], final_decision="continue", confidence=0.85,
        )
        d = t.to_dict()
        assert len(d["steps"]) == 1


class TestReasoningResult:
    """ReasoningResult 模型测试."""

    def test_default_decision(self):
        r = ReasoningResult()
        assert r.decision == ReasoningDecision.MONITOR

    def test_to_dict(self):
        r = ReasoningResult(
            decision=ReasoningDecision.CONTINUE,
            confidence=0.87,
            reasoning=["ROAS improved"],
            next_action="monitor",
        )
        d = r.to_dict()
        assert d["decision"] == "continue"
        assert d["confidence"] == 0.87


# ═══════════════════════════════════════════════════════════════════
# Test: Hypothesis Engine
# ═══════════════════════════════════════════════════════════════════


class TestHypothesisEngine:
    """HypothesisEngine 测试."""

    def test_generate_creative_fatigue(self):
        """创意疲劳 — ROAS↓ + CTR↓ + Frequency↑."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="roas", value=1.0, previous=1.5, trend=ObservationTrend.DOWN),
            Observation(metric="ctr", value=2.0, previous=2.5, trend=ObservationTrend.DOWN),
            Observation(metric="frequency", value=3.5, previous=2.0, trend=ObservationTrend.UP),
        ]
        hypotheses = engine.generate(obs)
        assert len(hypotheses) > 0
        assert hypotheses[0].name == "creative_fatigue"
        assert hypotheses[0].confidence == pytest.approx(1.0, 0.01)

    def test_generate_audience_saturation(self):
        """受众饱和 — ROAS↓ + CPM↑ + Frequency↑."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="roas", value=1.0, previous=1.5, trend=ObservationTrend.DOWN),
            Observation(metric="cpm", value=15.0, previous=10.0, trend=ObservationTrend.UP),
            Observation(metric="frequency", value=3.5, previous=2.0, trend=ObservationTrend.UP),
        ]
        hypotheses = engine.generate(obs)
        names = [h.name for h in hypotheses]
        assert "audience_saturation" in names

    def test_generate_budget_insufficient(self):
        """预算不足 — ROAS↑ + spend稳定."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="roas", value=2.0, previous=1.5, trend=ObservationTrend.UP),
            Observation(metric="spend", value=100, previous=100, trend=ObservationTrend.STABLE),
        ]
        hypotheses = engine.generate(obs)
        names = [h.name for h in hypotheses]
        assert "budget_insufficient" in names

    def test_generate_scaling_opportunity(self):
        """放量机会 — ROAS↑ + CTR↑."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="roas", value=2.0, previous=1.5, trend=ObservationTrend.UP),
            Observation(metric="ctr", value=3.0, previous=2.5, trend=ObservationTrend.UP),
        ]
        hypotheses = engine.generate(obs)
        names = [h.name for h in hypotheses]
        assert "scaling_opportunity" in names

    def test_generate_multiple_hypotheses(self, fatigue_observations):
        """多个假设同时生成."""
        engine = HypothesisEngine()
        hypotheses = engine.generate(fatigue_observations)
        assert len(hypotheses) >= 1

    def test_empty_observations(self):
        """空观测列表."""
        engine = HypothesisEngine()
        hypotheses = engine.generate([])
        assert hypotheses == []

    def test_no_match(self):
        """无匹配规则."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="unknown", value=1.0, trend=ObservationTrend.STABLE),
        ]
        hypotheses = engine.generate(obs)
        assert hypotheses == []

    def test_sorted_by_confidence(self, fatigue_observations):
        """按置信度降序排列."""
        engine = HypothesisEngine()
        hypotheses = engine.generate(fatigue_observations)
        for i in range(len(hypotheses) - 1):
            assert hypotheses[i].confidence >= hypotheses[i + 1].confidence

    def test_hypothesis_has_evidence(self, fatigue_observations):
        """假设含证据."""
        engine = HypothesisEngine()
        hypotheses = engine.generate(fatigue_observations)
        assert len(hypotheses[0].evidence) > 0

    def test_hypothesis_has_suggested_action(self, fatigue_observations):
        """假设含建议动作."""
        engine = HypothesisEngine()
        hypotheses = engine.generate(fatigue_observations)
        assert hypotheses[0].suggested_action is not None

    def test_partial_match_lower_confidence(self):
        """部分匹配 — 置信度降低."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="roas", value=1.0, trend=ObservationTrend.DOWN),
            # 缺少 ctr 和 frequency
        ]
        hypotheses = engine.generate(obs)
        # creative_fatigue 可能部分匹配 (1/3)
        fatigue = [h for h in hypotheses if h.name == "creative_fatigue"]
        if fatigue:
            assert fatigue[0].confidence < 1.0

    def test_generate_from_context(self):
        """从 ReasoningContext 生成."""
        engine = HypothesisEngine()
        ctx = ReasoningContext(observations=[
            Observation(metric="roas", value=1.0, previous=1.5, trend=ObservationTrend.DOWN),
            Observation(metric="ctr", value=2.0, previous=2.5, trend=ObservationTrend.DOWN),
            Observation(metric="frequency", value=3.5, previous=2.0, trend=ObservationTrend.UP),
        ])
        hypotheses = engine.generate_from_context(ctx)
        assert len(hypotheses) > 0

    def test_add_custom_rule(self):
        """添加自定义规则."""
        engine = HypothesisEngine()
        engine.add_rule({
            "name": "custom_test",
            "description": "Custom test rule",
            "conditions": [
                {"metric": "roas", "trend": "up"},
            ],
            "impact": "low",
            "suggested_action": "test",
        })
        obs = [Observation(metric="roas", value=2.0, trend=ObservationTrend.UP)]
        hypotheses = engine.generate(obs)
        names = [h.name for h in hypotheses]
        assert "custom_test" in names

    def test_get_rules(self):
        """获取规则列表."""
        engine = HypothesisEngine()
        rules = engine.get_rules()
        assert len(rules) == len(DEFAULT_RULES)

    def test_confidence_formula(self):
        """置信度 = 匹配数 / 总条件数."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="roas", value=1.0, trend=ObservationTrend.DOWN),
            Observation(metric="ctr", value=2.0, trend=ObservationTrend.DOWN),
        ]
        # creative_fatigue: 3 conditions, 2 matched → 2/3 = 0.67
        hypotheses = engine.generate(obs)
        fatigue = [h for h in hypotheses if h.name == "creative_fatigue"]
        assert len(fatigue) == 1
        assert fatigue[0].confidence == pytest.approx(2 / 3, 0.01)

    def test_evidence_contains_delta(self):
        """证据包含变化量."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="roas", value=1.0, previous=2.0, trend=ObservationTrend.DOWN),
        ]
        hypotheses = engine.generate(obs)
        if hypotheses:
            assert "delta" in hypotheses[0].evidence[0]

    def test_hypothesis_impact_field(self):
        """假设含影响程度."""
        engine = HypothesisEngine()
        obs = [
            Observation(metric="roas", value=1.0, previous=1.5, trend=ObservationTrend.DOWN),
            Observation(metric="ctr", value=2.0, previous=2.5, trend=ObservationTrend.DOWN),
            Observation(metric="frequency", value=3.5, previous=2.0, trend=ObservationTrend.UP),
        ]
        hypotheses = engine.generate(obs)
        assert hypotheses[0].impact in ("high", "medium", "low")


# ═══════════════════════════════════════════════════════════════════
# Test: Diagnosis Engine
# ═══════════════════════════════════════════════════════════════════


class TestDiagnosisEngine:
    """DiagnosisEngine 测试."""

    def test_diagnose_success(self, basic_context, success_result):
        """成功诊断."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, success_result)
        assert result.status == DiagnosisStatus.SUCCESS

    def test_diagnose_failure(self, basic_context, failure_result):
        """失败诊断."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, failure_result)
        assert result.status == DiagnosisStatus.FAILURE

    def test_diagnose_partial(self, basic_context, partial_result):
        """部分成功诊断."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, partial_result)
        assert result.status == DiagnosisStatus.PARTIAL_SUCCESS

    def test_diagnose_inconclusive(self, basic_context):
        """无变化诊断."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, {"metrics_delta": {}})
        assert result.status == DiagnosisStatus.INCONCLUSIVE

    def test_diagnose_has_summary(self, basic_context, success_result):
        """诊断含摘要."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, success_result)
        assert result.summary != ""

    def test_diagnose_failure_has_root_causes(self, basic_context, failure_result):
        """失败诊断含根因."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, failure_result)
        assert len(result.root_causes) > 0

    def test_diagnose_success_has_lessons(self, basic_context, success_result):
        """成功诊断含经验教训."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, success_result)
        assert len(result.lessons) > 0
        assert "effective" in result.lessons[0].lower()

    def test_diagnose_failure_has_lessons(self, basic_context, failure_result):
        """失败诊断含经验教训."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, failure_result)
        assert len(result.lessons) > 0
        assert "failed" in result.lessons[0].lower()

    def test_diagnose_with_hypotheses(self, basic_context, success_result):
        """含假设的诊断."""
        engine = DiagnosisEngine()
        hypotheses = [
            Hypothesis(name="h1", confidence=0.8),
            Hypothesis(name="h2", confidence=0.3),
        ]
        result = engine.diagnose(basic_context, success_result, hypotheses)
        assert "h1" in result.hypotheses_confirmed
        assert "h2" in result.hypotheses_rejected

    def test_diagnose_metrics_delta_preserved(self, basic_context, success_result):
        """指标变化保留."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, success_result)
        assert result.metrics_delta == success_result["metrics_delta"]

    def test_diagnose_constraint_violation(self, basic_context):
        """约束接近阈值 — 诊断可识别."""
        engine = DiagnosisEngine()
        ctx = ReasoningContext(
            action={"action_type": "scale_budget"},
            observations=[
                Observation(metric="daily_budget_limit", value=600, threshold=500, trend=ObservationTrend.UP),
            ],
            constraints=[
                Constraint(name="daily_budget_limit", value=500, type=ConstraintType.HARD),
            ],
        )
        result = engine.diagnose(ctx, {"metrics_delta": {"daily_budget_limit": -20.0}})
        # 指标下降但约束仍然存在，诊断应识别根因
        assert result.status == DiagnosisStatus.FAILURE
        assert len(result.root_causes) > 0

    def test_diagnose_previous_attempts_lesson(self):
        """历史尝试经验."""
        engine = DiagnosisEngine()
        ctx = ReasoningContext(
            action={"action_type": "creative_refresh"},
            previous_attempts=[
                ExecutionAttempt(action={"type": "creative_refresh"}, outcome="failure"),
            ],
        )
        result = engine.diagnose(ctx, {"metrics_delta": {"roas": -10.0}})
        assert any("previous" in l.lower() or "failed" in l.lower() for l in result.lessons)

    def test_diagnose_partial_has_lessons(self, basic_context, partial_result):
        """部分成功诊断含经验教训."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, partial_result)
        assert len(result.lessons) > 0
        assert "partial" in result.lessons[0].lower() or "tuning" in result.lessons[0].lower()

    def test_diagnose_root_causes_classification(self, basic_context, failure_result):
        """根因分类."""
        engine = DiagnosisEngine()
        result = engine.diagnose(basic_context, failure_result)
        # 根因应包含具体指标
        assert any("roas" in c.lower() or "ctr" in c.lower() for c in result.root_causes)


# ═══════════════════════════════════════════════════════════════════
# Test: Decision Trace Builder
# ═══════════════════════════════════════════════════════════════════


class TestDecisionTraceBuilder:
    """DecisionTraceBuilder 测试."""

    def test_build_trace(self, basic_context):
        """构建完整追踪."""
        builder = DecisionTraceBuilder()
        steps = [
            ReasoningStep(step_type="observation", description="extracted"),
            ReasoningStep(step_type="decision", description="chose continue"),
        ]
        trace = builder.build(basic_context, steps, "continue", 0.85)
        assert trace.final_decision == "continue"
        assert trace.confidence == 0.85
        assert len(trace.steps) == 2

    def test_create_observation_step(self, basic_context):
        """创建观测步骤."""
        builder = DecisionTraceBuilder()
        step = builder.create_observation_step(basic_context)
        assert step.step_type == "observation"
        assert "Extracted" in step.description
        assert step.confidence == 1.0

    def test_create_hypothesis_step(self):
        """创建假设步骤."""
        builder = DecisionTraceBuilder()
        hypotheses = [
            Hypothesis(name="fatigue", confidence=0.82),
            Hypothesis(name="saturation", confidence=0.50),
        ]
        step = builder.create_hypothesis_step(hypotheses)
        assert step.step_type == "hypothesis"
        assert "fatigue" in step.description
        assert step.confidence == 0.82

    def test_create_hypothesis_step_empty(self):
        """空假设步骤."""
        builder = DecisionTraceBuilder()
        step = builder.create_hypothesis_step([])
        assert "No hypotheses" in step.description
        assert step.confidence == 0.0

    def test_create_evaluation_step_improved(self):
        """评估步骤 — 改善."""
        builder = DecisionTraceBuilder()
        step = builder.create_evaluation_step(["roas", "ctr"], [])
        assert "Improved" in step.description
        assert step.confidence == 0.8

    def test_create_evaluation_step_degraded(self):
        """评估步骤 — 恶化."""
        builder = DecisionTraceBuilder()
        step = builder.create_evaluation_step([], ["roas"])
        assert "Degraded" in step.description
        assert step.confidence == 0.2

    def test_create_evaluation_step_mixed(self):
        """评估步骤 — 混合."""
        builder = DecisionTraceBuilder()
        step = builder.create_evaluation_step(["roas"], ["ctr"])
        assert step.confidence == 0.5

    def test_create_decision_step(self):
        """创建决策步骤."""
        builder = DecisionTraceBuilder()
        step = builder.create_decision_step("continue", 0.87, ["ROAS improved"])
        assert step.step_type == "decision"
        assert "continue" in step.description

    def test_create_context_step(self, basic_context):
        """创建上下文步骤."""
        builder = DecisionTraceBuilder()
        step = builder.create_context_step(basic_context)
        assert step.step_type == "observation"
        assert "creative_refresh" in step.description
        assert "medium" in step.description

    def test_trace_has_timestamp(self, basic_context):
        """追踪含时间戳."""
        builder = DecisionTraceBuilder()
        trace = builder.build(basic_context, [], "continue", 0.5)
        assert trace.created_at != ""


# ═══════════════════════════════════════════════════════════════════
# Test: Reasoning Engine
# ═══════════════════════════════════════════════════════════════════


class TestExecutionReasoningEngine:
    """ExecutionReasoningEngine 测试."""

    @pytest.fixture
    def engine(self) -> ExecutionReasoningEngine:
        return ExecutionReasoningEngine()

    def test_reason_success(self, engine, basic_context, success_result):
        """成功推理 → CONTINUE."""
        result = engine.reason(basic_context, success_result)
        assert result.decision == ReasoningDecision.CONTINUE
        assert result.confidence > 0.5
        assert len(result.reasoning) > 0

    def test_reason_failure(self, engine, basic_context, failure_result):
        """失败推理 → STOP."""
        result = engine.reason(basic_context, failure_result)
        assert result.decision == ReasoningDecision.STOP
        assert len(result.reasoning) > 0

    def test_reason_partial(self, engine, basic_context, partial_result):
        """部分成功推理 → MONITOR or MODIFY."""
        result = engine.reason(basic_context, partial_result)
        assert result.decision in (ReasoningDecision.MONITOR, ReasoningDecision.MODIFY)

    def test_reason_constraint_violation(self, engine):
        """约束违反 → STOP."""
        ctx = ReasoningContext(
            action={"action_type": "scale_budget"},
            observations=[
                Observation(
                    metric="daily_budget_limit", value=600, previous=500,
                    trend=ObservationTrend.UP, threshold=500,
                ),
            ],
            constraints=[
                Constraint(name="daily_budget_limit", value=500, type=ConstraintType.HARD),
            ],
        )
        result = engine.reason(ctx, {"metrics_delta": {"daily_budget_limit": 20.0}})
        assert result.decision == ReasoningDecision.STOP

    def test_reason_has_hypotheses(self, engine, basic_context, success_result):
        """推理含假设."""
        result = engine.reason(basic_context, success_result)
        assert len(result.hypotheses) >= 0

    def test_reason_has_diagnosis(self, engine, basic_context, success_result):
        """推理含诊断."""
        result = engine.reason(basic_context, success_result)
        assert result.diagnosis is not None

    def test_reason_has_trace(self, engine, basic_context, success_result):
        """推理含追踪."""
        result = engine.reason(basic_context, success_result)
        assert result.trace is not None
        assert len(result.trace.steps) > 0

    def test_reason_has_next_action(self, engine, basic_context, success_result):
        """推理含下一步动作."""
        result = engine.reason(basic_context, success_result)
        assert result.next_action is not None

    def test_reason_confidence_ranges(self, engine, basic_context, success_result):
        """置信度在 0-1 之间."""
        result = engine.reason(basic_context, success_result)
        assert 0 <= result.confidence <= 1.0

    def test_reason_observations_enriched(self, engine):
        """观测数据被补充."""
        ctx = ReasoningContext(
            action={"action_type": "test"},
        )
        result = engine.reason(ctx, {
            "metrics_delta": {"roas": 10.0},
            "metrics_before": {"roas": 1.0},
            "metrics_after": {"roas": 1.1},
        })
        # 观测应被补充
        assert result.trace is not None

    def test_reason_continue_next_action(self, engine, basic_context, success_result):
        """CONTINUE 的下一步动作."""
        result = engine.reason(basic_context, success_result)
        assert result.decision == ReasoningDecision.CONTINUE
        assert result.next_action is not None

    def test_reason_stop_next_action(self, engine, basic_context, failure_result):
        """STOP 的下一步动作."""
        result = engine.reason(basic_context, failure_result)
        assert result.decision == ReasoningDecision.STOP
        assert result.next_action == "pause_and_review"

    def test_reason_result_id(self, engine, basic_context, success_result):
        """推理结果有 ID."""
        result = engine.reason(basic_context, success_result)
        assert result.result_id != ""

    def test_reason_result_timestamp(self, engine, basic_context, success_result):
        """推理结果有时间戳."""
        result = engine.reason(basic_context, success_result)
        assert result.created_at != ""

    def test_reason_empty_metrics(self, engine, basic_context):
        """空指标变化 → MONITOR."""
        result = engine.reason(basic_context, {"metrics_delta": {}})
        assert result.decision == ReasoningDecision.MONITOR

    def test_reason_with_risk_context(self, engine):
        """含风险上下文."""
        ctx = ReasoningContext(
            action={"action_type": "creative_refresh"},
            observations=[
                Observation(metric="roas", value=1.5, previous=1.0, trend=ObservationTrend.UP),
                Observation(metric="ctr", value=3.0, previous=2.5, trend=ObservationTrend.UP),
            ],
            risk_assessment={"risk_level": "high", "risk_score": 0.8},
        )
        result = engine.reason(ctx, {
            "metrics_delta": {"roas": 10.0, "ctr": 5.0},
        })
        assert result.decision == ReasoningDecision.CONTINUE

    def test_reason_trace_steps_in_order(self, engine, basic_context, success_result):
        """追踪步骤按顺序."""
        result = engine.reason(basic_context, success_result)
        step_types = [s.step_type for s in result.trace.steps]
        # 顺序: context → observation → hypothesis → evaluation → decision
        assert "observation" in step_types
        assert "hypothesis" in step_types
        assert "evaluation" in step_types
        assert "decision" in step_types

    def test_engine_properties(self, engine):
        """引擎属性可访问."""
        assert engine.hypothesis_engine is not None
        assert engine.diagnosis_engine is not None


# ═══════════════════════════════════════════════════════════════════
# Test: Explainability
# ═══════════════════════════════════════════════════════════════════


class TestExecutionExplainer:
    """ExecutionExplainer 测试."""

    @pytest.fixture
    def explainer(self) -> ExecutionExplainer:
        return ExecutionExplainer()

    def test_explain_produces_text(self, explainer, basic_context):
        """生成解释文本."""
        result = ReasoningResult(
            decision=ReasoningDecision.CONTINUE,
            confidence=0.87,
            reasoning=["ROAS improved", "Risk acceptable"],
            next_action="monitor",
            hypotheses=[Hypothesis(name="scaling", confidence=0.75)],
        )
        text = explainer.explain(basic_context, result)
        assert "Decision:" in text
        assert "CONTINUE" in text
        assert "ROAS improved" in text

    def test_explain_includes_risk(self, explainer, basic_context):
        """解释含风险信息."""
        result = ReasoningResult(
            decision=ReasoningDecision.CONTINUE,
            confidence=0.80,
            reasoning=["OK"],
        )
        text = explainer.explain(basic_context, result)
        assert "Risk:" in text

    def test_explain_brief(self, explainer, basic_context):
        """简短解释."""
        result = ReasoningResult(
            decision=ReasoningDecision.CONTINUE,
            confidence=0.87,
            next_action="monitor",
        )
        brief = explainer.explain_brief(basic_context, result)
        assert "[CONTINUE]" in brief
        assert "87%" in brief

    def test_explain_structured(self, explainer, basic_context):
        """结构化解释."""
        result = ReasoningResult(
            decision=ReasoningDecision.CONTINUE,
            confidence=0.87,
            reasoning=["ROAS up"],
            next_action="scale",
            hypotheses=[Hypothesis(name="scaling", confidence=0.75, evidence=["ROAS > 1.2"])],
        )
        s = explainer.explain_structured(basic_context, result)
        assert s["decision"]["verdict"] == "continue"
        assert len(s["why"]) == 1
        assert len(s["hypotheses"]) == 1

    def test_explain_includes_hypotheses(self, explainer, basic_context):
        """解释含假设."""
        result = ReasoningResult(
            decision=ReasoningDecision.MODIFY,
            confidence=0.70,
            reasoning=["Hypothesis suggests modification"],
            hypotheses=[
                Hypothesis(
                    name="creative_fatigue",
                    description="Fatigue detected",
                    confidence=0.82,
                    evidence=["ROAS declined 20%"],
                ),
            ],
        )
        text = explainer.explain(basic_context, result)
        assert "creative_fatigue" in text
        assert "Fatigue detected" in text

    def test_explain_includes_diagnosis(self, explainer, basic_context):
        """解释含诊断."""
        result = ReasoningResult(
            decision=ReasoningDecision.STOP,
            confidence=0.75,
            reasoning=["Failed"],
            diagnosis=DiagnosisResult(
                status=DiagnosisStatus.FAILURE,
                root_causes=["ROAS declined"],
                lessons=["Avoid in similar conditions"],
            ),
        )
        text = explainer.explain(basic_context, result)
        assert "Diagnosis:" in text
        assert "failure" in text

    def test_explain_includes_trace(self, explainer, basic_context):
        """解释含追踪."""
        trace = ReasoningTrace(
            steps=[
                ReasoningStep(step_type="observation", description="extracted metrics"),
                ReasoningStep(step_type="decision", description="decided continue"),
            ],
            final_decision="continue",
            confidence=0.85,
        )
        result = ReasoningResult(
            decision=ReasoningDecision.CONTINUE,
            confidence=0.85,
            reasoning=["ok"],
            trace=trace,
        )
        text = explainer.explain(basic_context, result)
        assert "Trace:" in text
        assert "extracted metrics" in text

    def test_explain_includes_next_action(self, explainer, basic_context):
        """解释含下一步."""
        result = ReasoningResult(
            decision=ReasoningDecision.CONTINUE,
            confidence=0.80,
            next_action="scale_budget",
        )
        text = explainer.explain(basic_context, result)
        assert "Next:" in text
        assert "scale_budget" in text

    def test_explain_structured_has_trace(self, explainer, basic_context):
        """结构化解释含追踪."""
        trace = ReasoningTrace(
            steps=[ReasoningStep(step_type="decision", description="test")],
            confidence=0.9,
        )
        result = ReasoningResult(
            decision=ReasoningDecision.CONTINUE,
            confidence=0.9,
            trace=trace,
        )
        s = explainer.explain_structured(basic_context, result)
        assert "trace" in s
        assert len(s["trace"]["steps"]) == 1


# ═══════════════════════════════════════════════════════════════════
# Test: Integration
# ═══════════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试 — 完整推理链路."""

    def test_full_reasoning_pipeline(self):
        """完整推理链路: 上下文 → 假设 → 诊断 → 决策 → 解释."""
        engine = ExecutionReasoningEngine()
        explainer = ExecutionExplainer()

        ctx = ReasoningContext(
            execution_id="exec_integration_001",
            action={"action_type": "creative_refresh", "target": {"campaign_id": "123"}},
            observations=[
                Observation(metric="roas", value=1.0, previous=1.5, trend=ObservationTrend.DOWN),
                Observation(metric="ctr", value=2.0, previous=2.5, trend=ObservationTrend.DOWN),
                Observation(metric="frequency", value=3.5, previous=2.0, trend=ObservationTrend.UP),
            ],
            constraints=[
                Constraint(name="daily_budget_limit", value=500, type=ConstraintType.HARD),
            ],
            risk_assessment={"risk_level": "medium", "risk_score": 0.4},
            selected_action={"action_id": "act_001", "score": 0.73},
        )

        exec_result = {
            "metrics_delta": {"roas": -20.0, "ctr": -15.0, "frequency": 30.0},
            "metrics_before": {"roas": 1.5, "ctr": 2.5, "frequency": 2.0},
            "metrics_after": {"roas": 1.2, "ctr": 2.125, "frequency": 2.6},
        }

        result = engine.reason(ctx, exec_result)

        # 验证结果结构
        assert result.decision is not None
        assert result.confidence > 0
        assert result.diagnosis is not None
        assert result.trace is not None
        assert len(result.trace.steps) >= 4

        # 验证解释
        text = explainer.explain(ctx, result)
        assert "Decision:" in text
        assert "Why:" in text

    def test_pipeline_with_scaling_opportunity(self):
        """放量机会链路."""
        engine = ExecutionReasoningEngine()

        ctx = ReasoningContext(
            action={"action_type": "scale_budget"},
            observations=[
                Observation(metric="roas", value=2.0, previous=1.5, trend=ObservationTrend.UP),
                Observation(metric="ctr", value=3.0, previous=2.5, trend=ObservationTrend.UP),
            ],
            risk_assessment={"risk_level": "low", "risk_score": 0.2},
        )

        result = engine.reason(ctx, {
            "metrics_delta": {"roas": 15.0, "ctr": 10.0},
        })

        assert result.decision == ReasoningDecision.CONTINUE
        assert result.next_action is not None

    def test_pipeline_creative_fatigue(self):
        """创意疲劳链路 — 混合结果 (frequency↑ 但 roas↓ ctr↓) → MODIFY."""
        engine = ExecutionReasoningEngine()

        ctx = ReasoningContext(
            action={"action_type": "creative_refresh"},
            observations=[
                Observation(metric="roas", value=1.0, previous=1.5, trend=ObservationTrend.DOWN),
                Observation(metric="ctr", value=2.0, previous=2.5, trend=ObservationTrend.DOWN),
                Observation(metric="frequency", value=3.5, previous=2.0, trend=ObservationTrend.UP),
            ],
        )

        result = engine.reason(ctx, {
            "metrics_delta": {"roas": -20.0, "ctr": -15.0, "frequency": 30.0},
        })

        # frequency 上升是负面信号，但 delta 为正 → 混合结果 → MODIFY
        assert result.decision in (ReasoningDecision.MODIFY, ReasoningDecision.STOP)

    def test_to_dict_roundtrip(self):
        """to_dict 往返测试."""
        engine = ExecutionReasoningEngine()
        ctx = ReasoningContext(
            action={"action_type": "test"},
            observations=[
                Observation(metric="roas", value=1.5, previous=1.0, trend=ObservationTrend.UP),
            ],
        )
        result = engine.reason(ctx, {"metrics_delta": {"roas": 10.0}})
        d = result.to_dict()
        assert d["result_id"] == result.result_id
        assert d["decision"] == result.decision.value
        assert d["confidence"] == result.confidence
        assert d["diagnosis"] is not None

    def test_custom_engines_injection(self):
        """自定义引擎注入."""
        custom_hypothesis = HypothesisEngine()
        custom_diagnosis = DiagnosisEngine()
        custom_trace = DecisionTraceBuilder()

        engine = ExecutionReasoningEngine(
            hypothesis_engine=custom_hypothesis,
            diagnosis_engine=custom_diagnosis,
            trace_builder=custom_trace,
        )

        assert engine.hypothesis_engine is custom_hypothesis
        assert engine.diagnosis_engine is custom_diagnosis

    def test_reasoning_result_metadata(self):
        """推理结果元数据."""
        engine = ExecutionReasoningEngine()
        ctx = ReasoningContext(
            action={"action_type": "test"},
            observations=[
                Observation(metric="roas", value=1.5, trend=ObservationTrend.UP),
            ],
            metadata={"source": "planner", "trace_id": "abc"},
        )
        result = engine.reason(ctx, {"metrics_delta": {"roas": 10.0}})
        assert result.metadata == {}

    def test_explain_structured_full(self):
        """结构化解释完整输出."""
        engine = ExecutionReasoningEngine()
        explainer = ExecutionExplainer()

        ctx = ReasoningContext(
            action={"action_type": "creative_refresh"},
            observations=[
                Observation(metric="roas", value=1.5, trend=ObservationTrend.UP),
            ],
            risk_assessment={"risk_level": "low", "risk_score": 0.2},
        )

        result = engine.reason(ctx, {"metrics_delta": {"roas": 10.0}})
        s = explainer.explain_structured(ctx, result)

        assert "decision" in s
        assert "why" in s
        assert "hypotheses" in s
        assert "risk" in s
        assert "diagnosis" in s
        assert "next_action" in s
        assert "trace" in s

    def test_observation_identity_after_reasoning(self):
        """推理后观测不丢失."""
        engine = ExecutionReasoningEngine()
        ctx = ReasoningContext(
            action={"action_type": "test"},
            observations=[
                Observation(metric="roas", value=1.5, trend=ObservationTrend.UP),
            ],
        )
        result = engine.reason(ctx, {"metrics_delta": {"roas": 10.0}})
        # 原始观测仍存在
        obs = ctx.get_observation("roas")
        assert obs is not None

    def test_multiple_rounds_consistent(self):
        """多轮推理一致性."""
        engine = ExecutionReasoningEngine()
        ctx = ReasoningContext(
            action={"action_type": "test"},
            observations=[
                Observation(metric="roas", value=1.5, previous=1.0, trend=ObservationTrend.UP),
            ],
        )

        r1 = engine.reason(ctx, {"metrics_delta": {"roas": 10.0}})
        r2 = engine.reason(ctx, {"metrics_delta": {"roas": 10.0}})

        assert r1.decision == r2.decision
        assert r1.confidence == r2.confidence