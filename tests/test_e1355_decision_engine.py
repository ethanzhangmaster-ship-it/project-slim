"""E13.5.5 Decision Engine — 测试套件.

覆盖:
  - Models (DecisionType, DecisionScore, DecisionPlan, DecisionOutput, DecisionInput)
  - DecisionScorer (单策略评分, 批量评分, 风险调整, 筛选)
  - DecisionExplainer (解释生成, 各维度解释)
  - DecisionMemory (记录, 反馈, 查询, 统计)
  - DecisionEngine (完整决策流程, 决策规则, 边界情况)
  - Integration (端到端流程: Opportunity → Strategy → Risk → Decision → Memory)
"""

from unittest.mock import MagicMock

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision import (
    DecisionEngine,
    DecisionExplainer,
    DecisionExperience,
    DecisionInput,
    DecisionMemory,
    DecisionOutput,
    DecisionPlan,
    DecisionScore,
    DecisionScorer,
    DecisionType,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
    GrowthOpportunity,
    OpportunityType,
    StrategyCandidate,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.risk_models import (
    RiskAssessment,
    RiskContext,
    RiskDecision,
    RiskLevel,
    RiskPolicy,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_candidate(
    strategy_id: str = "S001",
    name: str = "replace_creative",
    historical_score: float = 0.78,
    confidence: float = 0.85,
    risk: float = 0.15,
) -> StrategyCandidate:
    """创建测试用 StrategyCandidate."""
    return StrategyCandidate(
        strategy_id=strategy_id,
        strategy_name=name,
        historical_score=historical_score,
        confidence_score=confidence,
        risk_score=risk,
        final_score=historical_score * confidence * (1 - risk),
    )


def make_risk_assessment(
    strategy_id: str = "S001",
    strategy_name: str = "replace_creative",
    risk_score: float = 0.15,
    risk_level: RiskLevel = RiskLevel.SAFE,
    decision: RiskDecision = RiskDecision.ALLOW,
    reasons: list[str] | None = None,
    recommendations: list[str] | None = None,
) -> RiskAssessment:
    """创建测试用 RiskAssessment."""
    assessment = RiskAssessment(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        risk_score=risk_score,
        risk_level=risk_level,
        decision=decision,
    )
    if reasons:
        for r in reasons:
            assessment.add_reason(r)
    if recommendations:
        for r in recommendations:
            assessment.add_recommendation(r)
    return assessment


def make_opportunity(
    opportunity_id: str = "opp_001",
    opp_type: OpportunityType = OpportunityType.CREATIVE_REFRESH,
    confidence: float = 0.91,
    reason: str = "CTR dropped 35%",
) -> GrowthOpportunity:
    """创建测试用 GrowthOpportunity."""
    return GrowthOpportunity(
        opportunity_id=opportunity_id,
        opportunity_type=opp_type,
        confidence=confidence,
        reason=reason,
        impact_score=0.75,
        urgency=0.6,
    )


def make_input(
    opportunity=None,
    strategies=None,
    risks=None,
) -> DecisionInput:
    """创建测试用 DecisionInput."""
    return DecisionInput(
        opportunity=opportunity,
        strategies=strategies or [],
        risks=risks or {},
    )


# ═══════════════════════════════════════════════════════════════
# Models Tests (~15 tests)
# ═══════════════════════════════════════════════════════════════


class TestDecisionType:
    """DecisionType 枚举测试."""

    def test_all_values_present(self):
        """验证所有决策类型枚举值存在."""
        assert DecisionType.EXECUTE.value == "execute"
        assert DecisionType.TEST.value == "test"
        assert DecisionType.HOLD.value == "hold"
        assert DecisionType.BLOCK.value == "block"
        assert DecisionType.ESCALATE.value == "escalate"

    def test_is_string_enum(self):
        """验证 DecisionType 是字符串枚举."""
        assert isinstance(DecisionType.EXECUTE.value, str)
        assert DecisionType.EXECUTE == "execute"


class TestDecisionScore:
    """DecisionScore 模型测试."""

    def test_default_values(self):
        """验证默认值."""
        score = DecisionScore()
        assert score.strategy_id == ""
        assert score.strategy_reward == 0.0
        assert score.final_score == 0.0
        assert score.rank == 0

    def test_full_construction(self):
        """验证完整构造."""
        score = DecisionScore(
            strategy_id="S001",
            strategy_name="Test",
            strategy_reward=0.8,
            confidence=0.9,
            risk_score=0.1,
            final_score=0.72,
            rank=1,
        )
        assert score.strategy_id == "S001"
        assert score.final_score == 0.72

    def test_is_viable(self):
        """验证可行性判断."""
        assert DecisionScore(final_score=0.5).is_viable
        assert DecisionScore(final_score=0.3).is_viable
        assert not DecisionScore(final_score=0.29).is_viable
        assert not DecisionScore(final_score=0.0).is_viable

    def test_is_strong(self):
        """验证强推荐判断."""
        assert DecisionScore(final_score=0.8).is_strong
        assert DecisionScore(final_score=0.6).is_strong
        assert not DecisionScore(final_score=0.59).is_strong

    def test_risk_adjusted_reward(self):
        """验证风险调整后收益."""
        score = DecisionScore(
            strategy_reward=0.8,
            risk_score=0.2,
            risk_adjusted_reward=0.64,
        )
        assert score.risk_adjusted_reward == 0.64

    def test_to_dict(self):
        """验证序列化."""
        score = DecisionScore(
            strategy_id="S001",
            strategy_name="Test",
            strategy_reward=0.78,
            confidence=0.85,
            risk_score=0.15,
            risk_adjusted_reward=0.663,
            final_score=0.56355,
            rank=1,
        )
        d = score.to_dict()
        assert d["strategy_id"] == "S001"
        assert d["rank"] == 1
        assert 0.56 < d["final_score"] < 0.57


class TestDecisionPlan:
    """DecisionPlan 模型测试."""

    def test_default_plan(self):
        """验证默认计划."""
        plan = DecisionPlan()
        assert plan.target_entity == "creative"
        assert plan.duration_days == 7
        assert plan.test_budget == 0.0

    def test_test_budget_plan(self):
        """验证测试预算计划."""
        plan = DecisionPlan(
            test_budget=500.0,
            duration_days=3,
            params={"generate_creatives": 5},
        )
        assert plan.has_test_budget
        assert not plan.has_execute_budget
        assert plan.duration_days == 3

    def test_execute_budget_plan(self):
        """验证执行预算计划."""
        plan = DecisionPlan(execute_budget=2000.0, duration_days=7)
        assert plan.has_execute_budget
        assert not plan.has_test_budget

    def test_rollout_steps(self):
        """验证分阶段执行步骤."""
        plan = DecisionPlan(rollout_steps=[
            {"step": 1, "action": "create_campaign", "budget": 100},
            {"step": 2, "action": "start_spend", "budget": 500},
        ])
        assert len(plan.rollout_steps) == 2

    def test_to_dict(self):
        """验证序列化."""
        plan = DecisionPlan(
            action_type="test",
            test_budget=500,
            duration_days=3,
        )
        d = plan.to_dict()
        assert d["action_type"] == "test"
        assert d["test_budget"] == 500


class TestDecisionOutput:
    """DecisionOutput 模型测试."""

    def test_default_output(self):
        """验证默认输出."""
        output = DecisionOutput()
        assert output.decision_type == DecisionType.HOLD
        assert output.confidence == 0.0
        assert not output.is_executable

    def test_execute_output(self):
        """验证 EXECUTE 决策."""
        output = DecisionOutput(decision_type=DecisionType.EXECUTE)
        assert output.is_executable
        assert output.is_testable is False

    def test_block_output(self):
        """验证 BLOCK 决策."""
        output = DecisionOutput(decision_type=DecisionType.BLOCK)
        assert output.is_blocked
        assert not output.is_executable

    def test_escalate_output(self):
        """验证 ESCALATE 决策."""
        output = DecisionOutput(decision_type=DecisionType.ESCALATE)
        assert output.is_escalated
        assert output.requires_approval is False  # depends on flag

    def test_alternatives(self):
        """验证备选方案."""
        alt1 = DecisionScore(strategy_id="S002", strategy_name="alt1")
        alt2 = DecisionScore(strategy_id="S003", strategy_name="alt2")
        output = DecisionOutput(alternatives=[alt1, alt2])
        assert output.has_alternatives
        assert output.alternative_count == 2
        assert output.get_top_alternative() == alt1

    def test_no_alternatives(self):
        """验证无备选方案."""
        output = DecisionOutput()
        assert not output.has_alternatives
        assert output.get_top_alternative() is None

    def test_to_dict(self):
        """验证序列化."""
        plan = DecisionPlan(action_type="test", test_budget=500)
        output = DecisionOutput(
            opportunity_id="opp_001",
            strategy_id="S001",
            strategy_name="Test",
            decision_type=DecisionType.TEST,
            confidence=0.85,
            action_plan=plan,
        )
        d = output.to_dict()
        assert d["decision_type"] == "test"
        assert d["confidence"] == 0.85
        assert d["action_plan"] is not None


class TestDecisionInput:
    """DecisionInput 模型测试."""

    def test_empty_input(self):
        """验证空输入."""
        inp = DecisionInput()
        assert not inp.has_opportunity
        assert not inp.has_strategies
        assert inp.strategy_count == 0

    def test_full_input(self):
        """验证完整输入."""
        opp = make_opportunity()
        strategies = [make_candidate("S001"), make_candidate("S002")]
        risks = {"S001": make_risk_assessment("S001")}
        inp = DecisionInput(opportunity=opp, strategies=strategies, risks=risks)
        assert inp.has_opportunity
        assert inp.has_strategies
        assert inp.strategy_count == 2


# ═══════════════════════════════════════════════════════════════
# DecisionScorer Tests (~20 tests)
# ═══════════════════════════════════════════════════════════════


class TestDecisionScorerSingle:
    """单策略评分测试."""

    def test_perfect_score(self):
        """完美策略: 高收益 + 高置信 + 零风险."""
        scorer = DecisionScorer()
        candidate = make_candidate(historical_score=1.0, confidence=1.0, risk=0.0)
        risk = make_risk_assessment(risk_score=0.0)
        score = scorer.score_strategy(candidate, risk)
        assert score.final_score == pytest.approx(1.0, abs=0.01)
        assert score.risk_adjusted_reward == pytest.approx(1.0, abs=0.01)

    def test_zero_reward(self):
        """零收益策略."""
        scorer = DecisionScorer()
        candidate = make_candidate(historical_score=0.0, confidence=0.9)
        score = scorer.score_strategy(candidate)
        assert score.final_score == 0.0

    def test_high_risk_penalty(self):
        """高风险惩罚: 风险 0.8 严重拉低总分."""
        scorer = DecisionScorer()
        candidate = make_candidate(historical_score=0.8, confidence=0.9, risk=0.8)
        risk = make_risk_assessment(risk_score=0.8)
        score = scorer.score_strategy(candidate, risk)
        assert score.final_score < 0.3

    def test_no_risk_assessment(self):
        """无风险评估: 默认 risk_score=0."""
        scorer = DecisionScorer()
        candidate = make_candidate(historical_score=0.8, confidence=0.9)
        score = scorer.score_strategy(candidate, None)
        assert score.risk_score == 0.0
        assert score.final_score == pytest.approx(0.72, abs=0.01)

    def test_risk_adjusted_reward(self):
        """风险调整后收益: reward × (1-risk)."""
        scorer = DecisionScorer()
        candidate = make_candidate(historical_score=0.8, confidence=0.9)
        risk = make_risk_assessment(risk_score=0.25)
        score = scorer.score_strategy(candidate, risk)
        assert score.risk_adjusted_reward == pytest.approx(0.6, abs=0.01)

    def test_values_clamped(self):
        """验证值被限制在 [0, 1]."""
        scorer = DecisionScorer()
        candidate = make_candidate(historical_score=1.5, confidence=2.0, risk=-0.5)
        risk = make_risk_assessment(risk_score=1.5)
        score = scorer.score_strategy(candidate, risk)
        assert 0.0 <= score.final_score <= 1.0
        assert 0.0 <= score.strategy_reward <= 1.0
        assert 0.0 <= score.risk_score <= 1.0


class TestDecisionScorerBatch:
    """批量评分测试."""

    def test_score_all_ranking(self):
        """验证批量评分后的排序."""
        scorer = DecisionScorer()
        candidates = [
            make_candidate("S1", "best", historical_score=0.9, confidence=0.9, risk=0.1),
            make_candidate("S2", "mid", historical_score=0.6, confidence=0.7, risk=0.3),
            make_candidate("S3", "worst", historical_score=0.4, confidence=0.5, risk=0.7),
        ]
        risks = {
            "S1": make_risk_assessment("S1", risk_score=0.1),
            "S2": make_risk_assessment("S2", risk_score=0.3),
            "S3": make_risk_assessment("S3", risk_score=0.7),
        }
        scores = scorer.score_all(candidates, risks)
        assert len(scores) == 3
        assert scores[0].strategy_id == "S1"  # best first
        assert scores[0].rank == 1
        assert scores[2].strategy_id == "S3"  # worst last
        assert scores[2].rank == 3

    def test_score_all_top_n(self):
        """验证 top_n 截断."""
        scorer = DecisionScorer()
        candidates = [make_candidate(f"S{i}") for i in range(10)]
        scores = scorer.score_all(candidates, top_n=3)
        assert len(scores) == 3

    def test_score_all_empty(self):
        """验证空列表."""
        scorer = DecisionScorer()
        scores = scorer.score_all([])
        assert scores == []

    def test_score_all_no_risks(self):
        """验证无风险评估的批量评分."""
        scorer = DecisionScorer()
        candidates = [
            make_candidate("S1", historical_score=0.9, confidence=0.9),
            make_candidate("S2", historical_score=0.5, confidence=0.5),
        ]
        scores = scorer.score_all(candidates)
        assert len(scores) == 2
        assert scores[0].strategy_id == "S1"

    def test_score_all_partial_risks(self):
        """验证部分策略有风险评估."""
        scorer = DecisionScorer()
        candidates = [
            make_candidate("S1", historical_score=0.8, confidence=0.9),
            make_candidate("S2", historical_score=0.8, confidence=0.9),
        ]
        risks = {"S1": make_risk_assessment("S1", risk_score=0.9)}
        scores = scorer.score_all(candidates, risks)
        # S1 高风险 → 低分, S2 无风险 → 高分
        assert scores[0].strategy_id == "S2"


class TestDecisionScorerFilter:
    """评分筛选测试."""

    def test_get_best(self):
        scorer = DecisionScorer()
        candidates = [
            make_candidate("S1", historical_score=0.9),
            make_candidate("S2", historical_score=0.5),
        ]
        scores = scorer.score_all(candidates)
        best = scorer.get_best(scores)
        assert best is not None
        assert best.strategy_id == "S1"

    def test_get_best_empty(self):
        scorer = DecisionScorer()
        assert scorer.get_best([]) is None

    def test_get_viable(self):
        scorer = DecisionScorer(min_viable_score=0.5)
        candidates = [
            make_candidate("S1", historical_score=0.9, confidence=0.9),
            make_candidate("S2", historical_score=0.3, confidence=0.3),
        ]
        scores = scorer.score_all(candidates)
        viable = scorer.get_viable(scores)
        assert len(viable) == 1
        assert viable[0].strategy_id == "S1"

    def test_get_strong(self):
        scorer = DecisionScorer(strong_score=0.6)
        candidates = [
            make_candidate("S1", historical_score=0.9, confidence=0.9),
            make_candidate("S2", historical_score=0.5, confidence=0.5),
        ]
        scores = scorer.score_all(candidates)
        strong = scorer.get_strong(scores)
        assert len(strong) == 1

    def test_get_by_risk_level(self):
        scorer = DecisionScorer()
        candidates = [
            make_candidate("S1", historical_score=0.8, confidence=0.9),
            make_candidate("S2", historical_score=0.8, confidence=0.9),
        ]
        risks = {
            "S1": make_risk_assessment("S1", risk_score=0.1),
            "S2": make_risk_assessment("S2", risk_score=0.9),
        }
        scores = scorer.score_all(candidates, risks)
        low_risk = scorer.get_by_risk_level(scores, max_risk=0.5)
        assert len(low_risk) == 1
        assert low_risk[0].strategy_id == "S1"


class TestDecisionScorerWeights:
    """评分权重测试."""

    def test_custom_weights(self):
        """自定义权重影响评分."""
        default = DecisionScorer()
        heavy_risk = DecisionScorer(risk_weight=2.0)
        candidate = make_candidate(historical_score=0.8, confidence=0.9)
        risk = make_risk_assessment(risk_score=0.5)
        s_default = default.score_strategy(candidate, risk)
        s_heavy = heavy_risk.score_strategy(candidate, risk)
        # 风险权重更高 → 评分更低
        assert s_heavy.final_score < s_default.final_score

    def test_reward_weight(self):
        """奖励权重影响评分."""
        scorer = DecisionScorer(reward_weight=0.5)
        candidate = make_candidate(historical_score=0.64, confidence=1.0)
        score = scorer.score_strategy(candidate)
        # reward^0.5 = 0.8, × 1.0 × 1.0 = 0.8
        assert score.final_score == pytest.approx(0.8, abs=0.01)


# ═══════════════════════════════════════════════════════════════
# DecisionExplainer Tests (~20 tests)
# ═══════════════════════════════════════════════════════════════


class TestDecisionExplainer:
    """决策解释器测试."""

    def test_explain_execute(self):
        """验证 EXECUTE 决策解释."""
        explainer = DecisionExplainer()
        decision = DecisionOutput(
            decision_type=DecisionType.EXECUTE,
            strategy_name="replace_creative",
            confidence=0.87,
            risk_score=0.15,
            risk_level="safe",
            final_score=0.66,
        )
        opp = make_opportunity(reason="CTR dropped 35%")
        risk = make_risk_assessment(risk_score=0.15)
        score = DecisionScore(
            strategy_id="S001",
            strategy_name="replace_creative",
            strategy_reward=0.78,
            confidence=0.87,
            risk_score=0.15,
            final_score=0.66,
        )
        result = explainer.explain(decision, opp, risk, score)
        assert len(result.reasons) > 0
        assert "CTR" in result.explanation or "检测到" in result.explanation
        assert "replace_creative" in result.explanation

    def test_explain_block(self):
        """验证 BLOCK 决策解释."""
        explainer = DecisionExplainer()
        decision = DecisionOutput(
            decision_type=DecisionType.BLOCK,
            strategy_name="aggressive_budget",
            risk_score=0.85,
            risk_level="critical",
        )
        risk = make_risk_assessment(
            risk_score=0.85,
            risk_level=RiskLevel.CRITICAL,
            decision=RiskDecision.BLOCK,
            reasons=["历史失败率过高"],
        )
        result = explainer.explain(decision, risk=risk)
        assert "BLOCK" in result.explanation.upper() or "禁止" in result.explanation

    def test_explain_test(self):
        """验证 TEST 决策解释."""
        explainer = DecisionExplainer()
        decision = DecisionOutput(
            decision_type=DecisionType.TEST,
            strategy_name="creative_mutation_v3",
            confidence=0.65,
            risk_score=0.22,
        )
        result = explainer.explain(decision)
        assert "TEST" in result.explanation.upper() or "测试" in result.explanation

    def test_explain_with_history(self):
        """验证包含历史经验的解释."""
        explainer = DecisionExplainer()
        decision = DecisionOutput(
            decision_type=DecisionType.EXECUTE,
            strategy_name="replace_creative",
            confidence=0.87,
        )
        history = {"similar_cases": 12, "success_rate": 0.83, "total_experiences": 50}
        result = explainer.explain(decision, history=history)
        assert "12" in result.explanation
        assert "83" in result.explanation or "0.83" in result.explanation

    def test_explain_with_warnings(self):
        """验证包含警告的解释."""
        explainer = DecisionExplainer()
        decision = DecisionOutput(
            decision_type=DecisionType.ESCALATE,
            strategy_name="risky_strategy",
            risk_score=0.7,
        )
        risk = make_risk_assessment(
            risk_score=0.7,
            risk_level=RiskLevel.HIGH,
            decision=RiskDecision.WARNING,
            recommendations=["建议小预算验证"],
        )
        result = explainer.explain(decision, risk=risk)
        assert len(result.warnings) > 0

    def test_explain_no_opportunity(self):
        """验证无机会时的解释."""
        explainer = DecisionExplainer()
        decision = DecisionOutput(
            decision_type=DecisionType.HOLD,
            strategy_name="unknown",
        )
        result = explainer.explain(decision)
        assert result.explanation  # 不崩溃

    def test_explain_opportunity_descriptions(self):
        """验证所有机会类型的描述."""
        explainer = DecisionExplainer()
        for opp_type in OpportunityType:
            desc = explainer.explain_opportunity_type(opp_type.value)
            assert desc  # 有描述
            assert desc != opp_type.value  # 不是原始值

    def test_explain_decision_descriptions(self):
        """验证所有决策类型的描述."""
        explainer = DecisionExplainer()
        for dt in DecisionType:
            desc = explainer.explain_decision_type(dt)
            assert desc

    def test_explain_risk_descriptions(self):
        """验证所有风险等级的描述."""
        explainer = DecisionExplainer()
        for rl in RiskLevel:
            desc = explainer.explain_risk_level(rl.value)
            assert desc

    def test_explain_with_expected_impact(self):
        """验证预期影响解释."""
        explainer = DecisionExplainer()
        plan = DecisionPlan(expected_roas_impact=0.22)
        decision = DecisionOutput(
            decision_type=DecisionType.TEST,
            strategy_name="creative_mutation",
            action_plan=plan,
            expected_reward=0.78,
        )
        result = explainer.explain(decision)
        assert "22" in result.explanation or "0.22" in result.explanation

    def test_explain_with_alternatives(self):
        """验证包含备选方案的解释."""
        explainer = DecisionExplainer()
        alt1 = DecisionScore(strategy_id="S002", strategy_name="budget_optimize")
        alt2 = DecisionScore(strategy_id="S003", strategy_name="audience_expand")
        decision = DecisionOutput(
            decision_type=DecisionType.TEST,
            strategy_name="replace_creative",
            alternatives=[alt1, alt2],
        )
        result = explainer.explain(decision)
        assert "budget_optimize" in result.explanation or "audience_expand" in result.explanation


# ═══════════════════════════════════════════════════════════════
# DecisionMemory Tests (~20 tests)
# ═══════════════════════════════════════════════════════════════


class TestDecisionExperience:
    """DecisionExperience 模型测试."""

    def test_default_experience(self):
        """验证默认经验."""
        exp = DecisionExperience()
        assert exp.result == "pending"
        assert not exp.is_resolved

    def test_resolve_success(self):
        """验证成功结果."""
        exp = DecisionExperience()
        exp.resolve("success", {"roas_change": 0.15}, "策略有效")
        assert exp.is_resolved
        assert exp.is_success
        assert not exp.is_failure
        assert exp.result_metrics == {"roas_change": 0.15}

    def test_resolve_failure(self):
        """验证失败结果."""
        exp = DecisionExperience()
        exp.resolve("failure", reason="预算超支")
        assert exp.is_failure
        assert exp.result_reason == "预算超支"

    def test_resolve_partial(self):
        """验证部分成功."""
        exp = DecisionExperience()
        exp.resolve("partial", lessons=["需要更长时间测试"])
        assert exp.is_partial
        assert len(exp.lessons_learned) == 1

    def test_to_dict(self):
        """验证序列化."""
        exp = DecisionExperience(
            decision_id="dec_001",
            strategy_id="S001",
            strategy_name="Test",
            confidence=0.85,
        )
        d = exp.to_dict()
        assert d["decision_id"] == "dec_001"
        assert d["result"] == "pending"


class TestDecisionMemoryRecord:
    """决策记忆记录测试."""

    def test_record_decision(self):
        """验证记录决策."""
        memory = DecisionMemory()
        decision = DecisionOutput(
            opportunity_id="opp_001",
            strategy_id="S001",
            strategy_name="Test",
            decision_type=DecisionType.TEST,
            confidence=0.85,
            risk_score=0.15,
        )
        exp = memory.record_decision(decision, opportunity_type="creative_refresh")
        assert exp.decision_id == decision.decision_id
        assert exp.result == "pending"
        assert memory.total_experiences == 1
        assert memory.pending_count == 1

    def test_record_outcome(self):
        """验证记录结果."""
        memory = DecisionMemory()
        decision = DecisionOutput(
            strategy_id="S001",
            decision_type=DecisionType.TEST,
        )
        memory.record_decision(decision)
        exp = memory.record_outcome(
            decision.decision_id,
            "success",
            {"roas_change": 0.12},
        )
        assert exp is not None
        assert exp.is_success
        assert memory.resolved_count == 1

    def test_record_outcome_not_found(self):
        """验证查询不存在的决策."""
        memory = DecisionMemory()
        exp = memory.record_outcome("nonexistent", "success")
        assert exp is None


class TestDecisionMemoryQuery:
    """决策记忆查询测试."""

    def test_get_by_strategy(self):
        """验证按策略查询."""
        memory = DecisionMemory()
        for i in range(3):
            decision = DecisionOutput(strategy_id=f"S00{i}", decision_type=DecisionType.TEST)
            memory.record_decision(decision)
        results = memory.get_by_strategy("S001")
        assert len(results) == 1

    def test_get_by_opportunity(self):
        """验证按机会查询."""
        memory = DecisionMemory()
        decision = DecisionOutput(opportunity_id="opp_001", strategy_id="S001", decision_type=DecisionType.TEST)
        memory.record_decision(decision)
        results = memory.get_by_opportunity("opp_001")
        assert len(results) == 1

    def test_find_similar(self):
        """验证相似经验查询."""
        memory = DecisionMemory()
        for i in range(5):
            decision = DecisionOutput(
                strategy_id="S001",
                decision_type=DecisionType.TEST,
                confidence=0.8,
            )
            memory.record_decision(decision, opportunity_type="creative_refresh")
        results = memory.find_similar(
            opportunity_type="creative_refresh",
            strategy_id="S001",
        )
        assert len(results) == 5

    def test_find_similar_filtered(self):
        """验证过滤查询."""
        memory = DecisionMemory()
        decision = DecisionOutput(strategy_id="S001", decision_type=DecisionType.TEST)
        memory.record_decision(decision, opportunity_type="creative_refresh")
        results = memory.find_similar(opportunity_type="budget_optimization")
        assert len(results) == 0

    def test_get_recent(self):
        """验证最近经验."""
        memory = DecisionMemory()
        for i in range(10):
            decision = DecisionOutput(strategy_id=f"S{i}", decision_type=DecisionType.TEST)
            memory.record_decision(decision)
        recent = memory.get_recent(limit=5)
        assert len(recent) == 5

    def test_get_pending(self):
        """验证待观察决策."""
        memory = DecisionMemory()
        decision = DecisionOutput(strategy_id="S001", decision_type=DecisionType.TEST)
        memory.record_decision(decision)
        pending = memory.get_pending()
        assert len(pending) == 1
        memory.record_outcome(decision.decision_id, "success")
        assert len(memory.get_pending()) == 0


class TestDecisionMemoryStats:
    """决策记忆统计测试."""

    def test_statistics(self):
        """验证统计."""
        memory = DecisionMemory()
        # 记录 3 个决策，2 个成功，1 个失败
        for i in range(3):
            decision = DecisionOutput(strategy_id=f"S{i}", decision_type=DecisionType.TEST)
            memory.record_decision(decision, opportunity_type="creative_refresh")
        memory.record_outcome(
            memory.get_recent()[0].decision_id, "success"
        )
        memory.record_outcome(
            memory.get_recent()[1].decision_id, "success"
        )
        memory.record_outcome(
            memory.get_recent()[2].decision_id, "failure"
        )
        stats = memory.get_statistics(opportunity_type="creative_refresh")
        assert stats["total_experiences"] == 3
        assert stats["resolved"] == 3
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_strategy_success_rate(self):
        """验证策略成功率."""
        memory = DecisionMemory()
        for i in range(5):
            decision = DecisionOutput(strategy_id="S001", decision_type=DecisionType.TEST)
            memory.record_decision(decision)
            result = "success" if i < 4 else "failure"
            memory.record_outcome(decision.decision_id, result)
        rate = memory.get_strategy_success_rate("S001")
        assert rate == 0.8

    def test_opportunity_success_rate(self):
        """验证机会类型成功率."""
        memory = DecisionMemory()
        decision = DecisionOutput(strategy_id="S001", decision_type=DecisionType.TEST)
        memory.record_decision(decision, opportunity_type="creative_refresh")
        memory.record_outcome(decision.decision_id, "success")
        rate = memory.get_opportunity_success_rate("creative_refresh")
        assert rate == 1.0

    def test_clear(self):
        """验证清空记忆."""
        memory = DecisionMemory()
        decision = DecisionOutput(strategy_id="S001", decision_type=DecisionType.TEST)
        memory.record_decision(decision)
        assert memory.total_experiences == 1
        memory.clear()
        assert memory.total_experiences == 0


class TestDecisionMemoryMax:
    """决策记忆容量测试."""

    def test_max_experiences(self):
        """验证最大经验数限制."""
        memory = DecisionMemory(max_experiences=5)
        for i in range(10):
            decision = DecisionOutput(strategy_id=f"S{i}", decision_type=DecisionType.TEST)
            memory.record_decision(decision)
        assert memory.total_experiences <= 5


# ═══════════════════════════════════════════════════════════════
# DecisionEngine Tests (~25 tests)
# ═══════════════════════════════════════════════════════════════


class TestDecisionEngineDecide:
    """决策引擎核心流程测试."""

    def test_decide_execute(self):
        """高置信度 + 低风险 → EXECUTE."""
        engine = DecisionEngine()
        opp = make_opportunity(confidence=0.91)
        s1 = make_candidate("S001", "replace_creative", historical_score=0.85, confidence=0.9, risk=0.1)
        risk = make_risk_assessment("S001", risk_score=0.1)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.EXECUTE
        assert output.strategy_id == "S001"
        assert output.is_executable

    def test_decide_test(self):
        """中等置信度 → TEST."""
        engine = DecisionEngine()
        opp = make_opportunity(confidence=0.7)
        s1 = make_candidate("S001", "creative_mutation", historical_score=0.65, confidence=0.65, risk=0.2)
        risk = make_risk_assessment("S001", risk_score=0.2)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.TEST
        assert output.action_plan is not None
        assert output.action_plan.test_budget > 0

    def test_decide_block_high_risk(self):
        """高风险 → BLOCK."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S001", "aggressive_budget", historical_score=0.6, confidence=0.7, risk=0.9)
        risk = make_risk_assessment("S001", risk_score=0.9)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.BLOCK
        assert output.is_blocked

    def test_decide_escalate(self):
        """中高风险 → ESCALATE."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S001", "risky_strategy", historical_score=0.7, confidence=0.75, risk=0.7)
        risk = make_risk_assessment("S001", risk_score=0.7)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.ESCALATE

    def test_decide_hold_low_confidence(self):
        """低置信度 → HOLD."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S001", "unknown", historical_score=0.3, confidence=0.3, risk=0.1)
        risk = make_risk_assessment("S001", risk_score=0.1)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.HOLD

    def test_decide_empty_strategies(self):
        """无策略 → HOLD."""
        engine = DecisionEngine()
        inp = make_input(make_opportunity(), [])
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.HOLD
        assert "无可用策略" in output.reasons[0]

    def test_decide_picks_best_strategy(self):
        """验证选择评分最高的策略."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S1", "best", historical_score=0.9, confidence=0.9, risk=0.1)
        s2 = make_candidate("S2", "mid", historical_score=0.6, confidence=0.7, risk=0.3)
        s3 = make_candidate("S3", "worst", historical_score=0.4, confidence=0.5, risk=0.5)
        risks = {
            "S1": make_risk_assessment("S1", risk_score=0.1),
            "S2": make_risk_assessment("S2", risk_score=0.3),
            "S3": make_risk_assessment("S3", risk_score=0.5),
        }
        inp = make_input(opp, [s1, s2, s3], risks)
        output = engine.decide(inp)
        assert output.strategy_id == "S1"

    def test_decide_alternatives(self):
        """验证备选方案."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S1", "best", historical_score=0.9, confidence=0.9)
        s2 = make_candidate("S2", "alt1", historical_score=0.8, confidence=0.8)
        s3 = make_candidate("S3", "alt2", historical_score=0.7, confidence=0.7)
        inp = make_input(opp, [s1, s2, s3])
        output = engine.decide(inp)
        assert output.alternative_count >= 1

    def test_decide_records_memory(self):
        """验证决策被记录到记忆."""
        memory = DecisionMemory()
        engine = DecisionEngine(memory=memory)
        opp = make_opportunity()
        s1 = make_candidate("S001", "test", historical_score=0.8, confidence=0.8)
        inp = make_input(opp, [s1])
        output = engine.decide(inp)
        assert memory.total_experiences == 1
        exp = memory.get_by_decision(output.decision_id)
        assert exp is not None
        assert exp.strategy_id == "S001"

    def test_decide_generates_explanation(self):
        """验证决策包含解释."""
        engine = DecisionEngine()
        opp = make_opportunity(reason="CTR dropped 35%")
        s1 = make_candidate("S001", "replace_creative", historical_score=0.85, confidence=0.9, risk=0.1)
        risk = make_risk_assessment("S001", risk_score=0.1)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.explanation
        assert len(output.reasons) > 0

    def test_decide_with_dict_strategies(self):
        """验证 dict 格式策略也可处理."""
        engine = DecisionEngine()
        strategy_dict = {
            "strategy_id": "S001",
            "strategy_name": "test",
            "historical_score": 0.8,
            "confidence_score": 0.85,
            "risk_score": 0.1,
        }
        inp = make_input(opportunity=make_opportunity(), strategies=[strategy_dict])
        output = engine.decide(inp)
        assert output.strategy_id == "S001"

    def test_decide_with_dict_opportunity(self):
        """验证 dict 格式机会也可处理."""
        engine = DecisionEngine()
        opp_dict = {"opportunity_id": "opp_001", "opportunity_type": "creative_refresh"}
        s1 = make_candidate("S001", "test", historical_score=0.8, confidence=0.8)
        inp = make_input(opportunity=opp_dict, strategies=[s1])
        output = engine.decide(inp)
        assert output.opportunity_id == "opp_001"


class TestDecisionEngineRules:
    """决策规则详尽测试."""

    def test_rule_high_risk_blocks(self):
        """Rule: risk >= 0.80 → BLOCK."""
        engine = DecisionEngine(block_risk_threshold=0.80)
        risk = make_risk_assessment("S001", risk_score=0.85)
        s1 = make_candidate("S001", confidence=0.9, risk=0.85)
        inp = make_input(make_opportunity(), [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.BLOCK

    def test_rule_escalate_high_risk(self):
        """Rule: risk >= 0.65 → ESCALATE."""
        engine = DecisionEngine(escalate_risk_threshold=0.65)
        risk = make_risk_assessment("S001", risk_score=0.7)
        s1 = make_candidate("S001", confidence=0.8, risk=0.7)
        inp = make_input(make_opportunity(), [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.ESCALATE

    def test_rule_low_confidence_holds(self):
        """Rule: confidence < 0.50 → HOLD."""
        engine = DecisionEngine(hold_confidence_threshold=0.50)
        s1 = make_candidate("S001", confidence=0.4, risk=0.1)
        inp = make_input(make_opportunity(), [s1])
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.HOLD

    def test_rule_execute_high_confidence_low_risk(self):
        """Rule: 高置信度 + 低风险 + 高收益 → EXECUTE."""
        engine = DecisionEngine(
            test_confidence_threshold=0.70,
            execute_reward_threshold=0.60,
        )
        risk = make_risk_assessment("S001", risk_score=0.1)
        s1 = make_candidate("S001", historical_score=0.85, confidence=0.85, risk=0.1)
        inp = make_input(make_opportunity(), [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.EXECUTE

    def test_rule_default_test(self):
        """Rule: 默认情况 → TEST."""
        engine = DecisionEngine()
        s1 = make_candidate("S001", historical_score=0.6, confidence=0.6, risk=0.2)
        risk = make_risk_assessment("S001", risk_score=0.2)
        inp = make_input(make_opportunity(), [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.TEST

    def test_custom_thresholds(self):
        """自定义阈值."""
        engine = DecisionEngine(
            block_risk_threshold=0.5,
            execute_reward_threshold=0.3,
            test_confidence_threshold=0.4,
        )
        risk = make_risk_assessment("S001", risk_score=0.6)
        s1 = make_candidate("S001", confidence=0.3, risk=0.6)
        inp = make_input(make_opportunity(), [s1], {"S001": risk})
        output = engine.decide(inp)
        # risk=0.6 >= block=0.5 → BLOCK
        assert output.decision_type == DecisionType.BLOCK


class TestDecisionEngineActionPlan:
    """执行计划测试."""

    def test_execute_plan_has_budget(self):
        """EXECUTE 计划有执行预算."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S001", historical_score=0.9, confidence=0.9, risk=0.05)
        risk = make_risk_assessment("S001", risk_score=0.05)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.action_plan is not None
        assert output.action_plan.execute_budget > 0

    def test_test_plan_has_test_budget(self):
        """TEST 计划有测试预算."""
        engine = DecisionEngine(default_test_budget=500)
        s1 = make_candidate("S001", historical_score=0.6, confidence=0.6, risk=0.2)
        risk = make_risk_assessment("S001", risk_score=0.2)
        inp = make_input(make_opportunity(), [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.action_plan is not None
        assert output.action_plan.test_budget == 500
        assert output.action_plan.duration_days == 3

    def test_block_plan_no_budget(self):
        """BLOCK 计划无预算."""
        engine = DecisionEngine()
        s1 = make_candidate("S001", confidence=0.5, risk=0.9)
        risk = make_risk_assessment("S001", risk_score=0.9)
        inp = make_input(make_opportunity(), [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.action_plan is not None
        assert output.action_plan.test_budget == 0
        assert output.action_plan.execute_budget == 0


# ═══════════════════════════════════════════════════════════════
# Integration Tests (~20 tests)
# ═══════════════════════════════════════════════════════════════


class TestFullDecisionFlow:
    """端到端决策流程测试."""

    def test_full_flow_execute(self):
        """完整流程: Opportunity → Strategy → Risk → EXECUTE."""
        engine = DecisionEngine()
        opp = make_opportunity(
            opp_type=OpportunityType.CREATIVE_REFRESH,
            confidence=0.91,
            reason="Creative fatigue: CTR -35%",
        )
        strategies = [
            make_candidate("S1", "replace_creative", historical_score=0.82, confidence=0.9, risk=0.1),
            make_candidate("S2", "increase_budget", historical_score=0.62, confidence=0.7, risk=0.3),
            make_candidate("S3", "duplicate_campaign", historical_score=0.45, confidence=0.6, risk=0.4),
        ]
        risks = {
            "S1": make_risk_assessment("S1", risk_score=0.15, risk_level=RiskLevel.SAFE),
            "S2": make_risk_assessment("S2", risk_score=0.72, risk_level=RiskLevel.HIGH),
            "S3": make_risk_assessment("S3", risk_score=0.55, risk_level=RiskLevel.MEDIUM),
        }
        inp = make_input(opp, strategies, risks)
        output = engine.decide(inp)

        # 验证选中最优策略 S1
        assert output.strategy_id == "S1"
        assert output.decision_type == DecisionType.EXECUTE
        assert output.confidence > 0.8
        assert output.risk_score <= 0.2
        assert output.explanation
        assert len(output.reasons) > 0

    def test_full_flow_test(self):
        """完整流程: 中等置信度 → TEST."""
        engine = DecisionEngine()
        opp = make_opportunity(confidence=0.7)
        strategies = [
            make_candidate("S1", "creative_mutation", historical_score=0.65, confidence=0.65, risk=0.2),
            make_candidate("S2", "budget_adjust", historical_score=0.55, confidence=0.6, risk=0.3),
        ]
        risks = {
            "S1": make_risk_assessment("S1", risk_score=0.2),
            "S2": make_risk_assessment("S2", risk_score=0.3),
        }
        inp = make_input(opp, strategies, risks)
        output = engine.decide(inp)

        assert output.decision_type == DecisionType.TEST
        assert output.action_plan is not None
        assert output.action_plan.test_budget > 0
        assert output.action_plan.duration_days == 3

    def test_full_flow_block(self):
        """完整流程: 高风险 → BLOCK."""
        engine = DecisionEngine()
        opp = make_opportunity()
        strategies = [
            make_candidate("S1", "aggressive_scale", historical_score=0.55, confidence=0.6, risk=0.9),
        ]
        risks = {"S1": make_risk_assessment("S1", risk_score=0.9, risk_level=RiskLevel.CRITICAL)}
        inp = make_input(opp, strategies, risks)
        output = engine.decide(inp)

        assert output.decision_type == DecisionType.BLOCK
        assert output.is_blocked

    def test_full_flow_memory_feedback(self):
        """完整流程: 决策 → 执行 → 反馈."""
        memory = DecisionMemory()
        engine = DecisionEngine(memory=memory)

        # 决策
        opp = make_opportunity()
        s1 = make_candidate("S001", historical_score=0.8, confidence=0.85)
        inp = make_input(opp, [s1])
        output = engine.decide(inp)

        assert memory.total_experiences == 1

        # 反馈
        exp = memory.record_outcome(
            output.decision_id,
            "success",
            {"roas_change": 0.15, "ctr_change": 0.05},
            "策略有效",
            ["replace_creative 在 creative_fatigue 场景下表现良好"],
        )
        assert exp is not None
        assert exp.is_success
        assert exp.result_metrics["roas_change"] == 0.15
        assert len(exp.lessons_learned) == 1

    def test_full_flow_multiple_rounds(self):
        """多轮决策循环."""
        memory = DecisionMemory()
        engine = DecisionEngine(memory=memory)

        for round_num in range(5):
            opp = make_opportunity(opportunity_id=f"opp_{round_num:03d}")
            s1 = make_candidate(f"S{round_num:03d}", historical_score=0.7 + round_num * 0.05, confidence=0.8)
            inp = make_input(opp, [s1])
            output = engine.decide(inp)
            memory.record_outcome(
                output.decision_id,
                "success" if round_num < 4 else "failure",
            )

        assert memory.total_experiences == 5
        assert memory.resolved_count == 5
        stats = memory.get_statistics()
        assert stats["success_count"] == 4
        assert stats["failure_count"] == 1

    def test_full_flow_opportunity_type_tracking(self):
        """验证机会类型跟踪."""
        memory = DecisionMemory()
        engine = DecisionEngine(memory=memory)

        opp = make_opportunity(
            opp_type=OpportunityType.CREATIVE_REFRESH,
            confidence=0.91,
        )
        s1 = make_candidate("S001", historical_score=0.85, confidence=0.9)
        inp = make_input(opp, [s1])
        engine.decide(inp)

        similar = memory.find_similar(opportunity_type="creative_refresh")
        assert len(similar) == 1

    def test_full_flow_strategy_success_rate_evolution(self):
        """验证策略成功率随时间演化."""
        memory = DecisionMemory()
        engine = DecisionEngine(memory=memory)

        # 前 3 次成功
        for i in range(3):
            opp = make_opportunity(opportunity_id=f"opp_{i}")
            s1 = make_candidate("S001", historical_score=0.8, confidence=0.85)
            inp = make_input(opp, [s1])
            output = engine.decide(inp)
            memory.record_outcome(output.decision_id, "success")

        # 后 2 次失败
        for i in range(3, 5):
            opp = make_opportunity(opportunity_id=f"opp_{i}")
            s1 = make_candidate("S001", historical_score=0.8, confidence=0.85)
            inp = make_input(opp, [s1])
            output = engine.decide(inp)
            memory.record_outcome(output.decision_id, "failure")

        rate = memory.get_strategy_success_rate("S001")
        assert rate == 0.6  # 3/5

    def test_full_flow_decision_requires_approval(self):
        """验证高风险决策需要审批."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S001", confidence=0.8, risk=0.7)
        risk = make_risk_assessment("S001", risk_score=0.7)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert output.requires_approval

    def test_full_flow_safe_decision_no_approval(self):
        """验证低风险决策不需要审批."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S001", historical_score=0.85, confidence=0.9, risk=0.1)
        risk = make_risk_assessment("S001", risk_score=0.1)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)
        assert not output.requires_approval


class TestEdgeCases:
    """边界情况测试."""

    def test_all_zero_scores(self):
        """全零评分的策略."""
        engine = DecisionEngine()
        s1 = make_candidate("S001", historical_score=0.0, confidence=0.0, risk=0.0)
        inp = make_input(make_opportunity(), [s1])
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.HOLD

    def test_single_strategy(self):
        """只有一个策略."""
        engine = DecisionEngine()
        s1 = make_candidate("S001", historical_score=0.8, confidence=0.85)
        inp = make_input(make_opportunity(), [s1])
        output = engine.decide(inp)
        assert output.strategy_id == "S001"

    def test_many_strategies(self):
        """大量策略 (>10)."""
        engine = DecisionEngine()
        strategies = [make_candidate(f"S{i:03d}", historical_score=0.5 + i * 0.01) for i in range(50)]
        inp = make_input(make_opportunity(), strategies)
        output = engine.decide(inp)
        assert output.strategy_id  # 有选中策略

    def test_risk_score_at_boundary(self):
        """风险在边界值."""
        engine = DecisionEngine(block_risk_threshold=0.80)
        risk = make_risk_assessment("S001", risk_score=0.799)
        s1 = make_candidate("S001", confidence=0.8, risk=0.799)
        inp = make_input(make_opportunity(), [s1], {"S001": risk})
        output = engine.decide(inp)
        # 0.799 < 0.80 → 不 BLOCK
        assert output.decision_type != DecisionType.BLOCK

        risk2 = make_risk_assessment("S001", risk_score=0.801)
        s1b = make_candidate("S001", confidence=0.8, risk=0.801)
        inp2 = make_input(make_opportunity(), [s1b], {"S001": risk2})
        output2 = engine.decide(inp2)
        # 0.801 >= 0.80 → BLOCK
        assert output2.decision_type == DecisionType.BLOCK

    def test_confidence_at_boundary(self):
        """置信度在边界值."""
        engine = DecisionEngine(hold_confidence_threshold=0.50)
        s1 = make_candidate("S001", confidence=0.49, risk=0.1)
        inp = make_input(make_opportunity(), [s1])
        output = engine.decide(inp)
        assert output.decision_type == DecisionType.HOLD

        s2 = make_candidate("S001", confidence=0.51, risk=0.1)
        inp2 = make_input(make_opportunity(), [s2])
        output2 = engine.decide(inp2)
        assert output2.decision_type != DecisionType.HOLD

    def test_missing_risk_assessment(self):
        """部分策略缺少风险评估."""
        engine = DecisionEngine()
        s1 = make_candidate("S1", historical_score=0.8, confidence=0.85)
        s2 = make_candidate("S2", historical_score=0.7, confidence=0.75)
        risks = {"S1": make_risk_assessment("S1", risk_score=0.9)}
        inp = make_input(make_opportunity(), [s1, s2], risks)
        output = engine.decide(inp)
        # S1 高风险 → S2 胜出
        assert output.strategy_id == "S2"

    def test_decision_output_has_all_fields(self):
        """验证 DecisionOutput 包含所有必要字段."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S001", historical_score=0.85, confidence=0.9)
        risk = make_risk_assessment("S001", risk_score=0.1)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)

        assert output.decision_id
        assert output.opportunity_id
        assert output.strategy_id
        assert output.strategy_name
        assert output.decision_type
        assert output.confidence >= 0
        assert output.risk_score >= 0
        assert output.final_score >= 0
        assert output.action_plan is not None
        assert output.explanation
        assert output.created_at

    def test_explanation_consistency(self):
        """验证解释与决策类型一致."""
        engine = DecisionEngine()
        opp = make_opportunity()
        s1 = make_candidate("S001", historical_score=0.85, confidence=0.9, risk=0.1)
        risk = make_risk_assessment("S001", risk_score=0.1)
        inp = make_input(opp, [s1], {"S001": risk})
        output = engine.decide(inp)

        assert "EXECUTE" in output.explanation.upper() or "执行" in output.explanation
        assert output.strategy_name in output.explanation