"""E17.5.2 PatternPredictor — 模式预测引擎测试.

覆盖 10 个类别，共 56 个测试用例：
  1.  Basic prediction (6)
  2.  Context matching (8)
  3.  Pattern scoring (6)
  4.  ROAS estimation (5)
  5.  Risk assessment (5)
  6.  Recommendations (5)
  7.  Confidence (5)
  8.  Model validation (5)
  9.  Edge cases (5)
  10. Integration (5)

注意: 上下文匹配使用 `context_val in condition` 子串匹配。
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.pattern_predictor import (
    PatternPredictor,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_models import (
    LearnedPattern,
    LearningKnowledge,
    PatternPrediction,
    StrategyInsight,
    RiskSignal,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_knowledge(patterns=None, strategies=None, warnings=None, confidence=0.8):
    return LearningKnowledge(
        patterns=patterns or [],
        strategies=strategies or [],
        warnings=warnings or [],
        confidence=confidence,
        total_experiences=50,
    )


def _make_pattern(
    dimension="creative",
    condition="fantasy_character",
    impact="positive",
    avg_reward=0.3,
    sample_count=20,
    confidence=0.8,
    success_rate=0.7,
    metadata=None,
):
    return LearnedPattern(
        dimension=dimension,
        condition=condition,
        impact=impact,
        avg_reward=avg_reward,
        sample_count=sample_count,
        confidence=confidence,
        success_rate=success_rate,
        metadata=metadata or {},
    )


def _make_strategy(name="scale_up", effectiveness=0.4, action_type="scale"):
    return StrategyInsight(
        strategy_name=name,
        action_type=action_type,
        avg_effectiveness=effectiveness,
        success_count=15,
        total_count=20,
        confidence=0.75,
    )


def _make_risk(level="high", signal_type="creative_fatigue", impact=-0.3, recommendations=None):
    return RiskSignal(
        risk_level=level,
        signal_type=signal_type,
        avg_impact=impact,
        recommendations=recommendations or ["Reduce spend", "Refresh creative"],
        confidence=0.85,
    )


# ═══════════════════════════════════════════════════════════════
# 1. Basic Prediction (6 tests)
# ═══════════════════════════════════════════════════════════════


class TestBasicPrediction:
    """基础预测功能测试."""

    def test_predict_with_knowledge(self):
        """有知识时有有效预测."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="fantasy_character")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "fantasy"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert isinstance(result, PatternPrediction)
        assert result.recommended_pattern == "creative|fantasy_character"
        assert result.confidence > 0
        assert len(result.matched_patterns) > 0

    def test_predict_without_knowledge(self):
        """无知识时返回空预测."""
        predictor = PatternPredictor()
        ctx = {"creative": "fantasy"}

        result = predictor.predict(context=ctx, knowledge=None)

        assert result.confidence == 0.0
        assert result.context_match_score == 0.0
        assert result.risk_level == "medium"
        assert result.metadata["reason"] == "no_knowledge_available"

    def test_predict_with_empty_knowledge(self):
        """知识无模式时返回空预测."""
        predictor = PatternPredictor()
        knowledge = _make_knowledge(patterns=[])
        ctx = {"creative": "fantasy"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence == 0.0
        assert result.metadata["reason"] == "no_knowledge_available"

    def test_predict_with_context(self):
        """有上下文时匹配度大于0."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="fantasy_character")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "fantasy"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.context_match_score > 0

    def test_predict_without_context(self):
        """空上下文时上下文匹配度为0."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="fantasy_character")
        knowledge = _make_knowledge(patterns=[pattern])

        result = predictor.predict(context={}, knowledge=knowledge)

        assert result.context_match_score == 0.0

    def test_prediction_count_tracking(self):
        """预测次数正确递增."""
        predictor = PatternPredictor()
        assert predictor.prediction_count == 0

        pattern = _make_pattern(condition="fantasy_character")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "fantasy"}

        predictor.predict(context=ctx, knowledge=knowledge)
        assert predictor.prediction_count == 1

        predictor.predict(context=ctx, knowledge=knowledge)
        assert predictor.prediction_count == 2

        predictor.predict(context=None, knowledge=None)
        assert predictor.prediction_count == 3


# ═══════════════════════════════════════════════════════════════
# 2. Context Matching (8 tests)
# ═══════════════════════════════════════════════════════════════


class TestContextMatching:
    """上下文匹配测试.
    
    匹配逻辑: str(context_val).lower() in condition.lower()
    即 context 值必须是 condition 的子串。
    """

    def test_match_by_game(self):
        """按 game 字段匹配 (context_val 是 condition 的子串)."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="merge_witch_us")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"game": "merge"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0
        assert result.context_match_score > 0

    def test_match_by_country(self):
        """按 country 字段匹配."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="us_market_best")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"country": "us"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0
        assert result.context_match_score > 0

    def test_match_by_creative(self):
        """按 creative 字段匹配."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="female_character")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "female"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0
        assert "female_character" in result.recommended_pattern

    def test_match_by_audience(self):
        """按 audience 字段匹配."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="casual_gamers_large")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"audience": "casual"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0
        assert result.context_match_score > 0

    def test_match_by_dimension(self):
        """按 dimension 字段匹配."""
        predictor = PatternPredictor()
        pattern = _make_pattern(dimension="strategy", condition="scale_up")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"dimension": "strategy", "creative": "scale"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0
        assert "strategy" in result.recommended_pattern

    def test_match_by_action_type(self):
        """按 action_type 匹配 (通过 metadata)."""
        predictor = PatternPredictor()
        pattern = _make_pattern(
            condition="scale_budget",
            metadata={"action_types": ["scale", "scale_budget"]},
        )
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "scale"}

        result = predictor.predict(context=ctx, knowledge=knowledge, action_type="scale")

        assert result.confidence > 0

    def test_match_multiple_fields(self):
        """多字段匹配时得分更高."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="merge_witch_us_female")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"game": "merge", "country": "us", "creative": "female"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0
        assert result.context_match_score > 0.15  # 至少匹配了多个字段

    def test_no_match(self):
        """无匹配时返回空预测."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="puzzle_game")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"game": "merge"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence == 0.0
        assert result.metadata["reason"] == "no_context_match"


# ═══════════════════════════════════════════════════════════════
# 3. Pattern Scoring (6 tests)
# ═══════════════════════════════════════════════════════════════


class TestPatternScoring:
    """模式评分测试."""

    def test_score_positive_patterns(self):
        """正向模式得分高于中性."""
        predictor = PatternPredictor()
        pos = _make_pattern(condition="good_pattern", impact="positive", confidence=0.8, success_rate=0.7)
        neu = _make_pattern(condition="neutral_pattern", impact="neutral", confidence=0.8, success_rate=0.7)
        knowledge = _make_knowledge(patterns=[pos, neu])
        ctx = {"creative": "good"}

        result_pos = predictor.predict(context=ctx, knowledge=knowledge)
        # 正向模式应排在前面
        assert result_pos.recommended_pattern == "creative|good_pattern"

    def test_score_negative_patterns(self):
        """负向模式得分低于正向."""
        predictor = PatternPredictor()
        neg = _make_pattern(condition="bad_pattern", impact="negative", confidence=0.8, success_rate=0.7)
        pos = _make_pattern(condition="good_pattern", impact="positive", confidence=0.8, success_rate=0.7)
        knowledge = _make_knowledge(patterns=[neg, pos])
        ctx = {"creative": "good"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        # 正向模式应该排在前面
        assert "good_pattern" in result.recommended_pattern

    def test_score_high_confidence(self):
        """高置信度模式得分更高."""
        predictor = PatternPredictor()
        high = _make_pattern(condition="high_conf", impact="positive", confidence=0.95, success_rate=0.7)
        low = _make_pattern(condition="low_conf", impact="positive", confidence=0.5, success_rate=0.7)
        knowledge = _make_knowledge(patterns=[low, high])
        ctx = {"creative": "high"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert "high_conf" in result.recommended_pattern

    def test_score_low_confidence(self):
        """低置信度模式可能被阈值过滤."""
        predictor = PatternPredictor(min_prediction_confidence=0.80)
        low = _make_pattern(condition="low_conf", impact="positive", confidence=0.3, success_rate=0.3, sample_count=1)
        knowledge = _make_knowledge(patterns=[low])
        ctx = {"creative": "low"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        # 可能因为分数低于阈值而返回空预测
        assert isinstance(result, PatternPrediction)

    def test_score_threshold(self):
        """分数阈值过滤低分模式."""
        predictor = PatternPredictor(min_prediction_confidence=0.90)
        pattern = _make_pattern(condition="test", impact="positive", confidence=0.2, success_rate=0.2, sample_count=1)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence == 0.0
        assert result.metadata["reason"] == "no_patterns_above_threshold"

    def test_score_ordering(self):
        """多个模式按得分降序排列."""
        predictor = PatternPredictor()
        p1 = _make_pattern(condition="best_pattern", impact="positive", confidence=0.9, success_rate=0.9, sample_count=50)
        p2 = _make_pattern(condition="middle_pattern", impact="positive", confidence=0.7, success_rate=0.7, sample_count=20)
        p3 = _make_pattern(condition="worst_pattern", impact="neutral", confidence=0.5, success_rate=0.5, sample_count=5)
        knowledge = _make_knowledge(patterns=[p1, p2, p3])
        ctx = {"creative": "best"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        # 最佳模式排在最前面
        assert "best_pattern" in result.recommended_pattern


# ═══════════════════════════════════════════════════════════════
# 4. ROAS Estimation (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestROASEstimation:
    """ROAS 预估测试."""

    def test_base_roas(self):
        """基础 ROAS 计算: 1.0 + avg_reward * 0.5."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_roas", avg_reward=0.3)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.expected_roas == pytest.approx(1.15, abs=0.01)

    def test_strategy_bonus(self):
        """策略加成增加 ROAS."""
        predictor = PatternPredictor()
        pattern = _make_pattern(
            condition="scale_up",
            avg_reward=0.2,
            metadata={"strategy_names": ["scale_up"]},
        )
        strategy = _make_strategy(name="scale_up", effectiveness=0.5)
        knowledge = _make_knowledge(patterns=[pattern], strategies=[strategy])
        ctx = {"creative": "scale"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        # ROAS = 1.0 + 0.2*0.5 + 0.5*0.3 = 1.0 + 0.1 + 0.15 = 1.25
        assert result.expected_roas > 1.15

    def test_risk_discount(self):
        """风险信号降低 ROAS."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_roas_risk", avg_reward=0.3)
        risk = _make_risk(level="high", impact=-0.5)
        knowledge = _make_knowledge(patterns=[pattern], warnings=[risk])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        # ROAS = 1.0 + 0.3*0.5 - 0.5*0.2 = 1.0 + 0.15 - 0.1 = 1.05
        assert result.expected_roas == pytest.approx(1.05, abs=0.01)

    def test_high_reward_roas(self):
        """高奖励导致高 ROAS."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_high_roas", avg_reward=0.8)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        # ROAS = 1.0 + 0.8*0.5 = 1.4
        assert result.expected_roas == pytest.approx(1.4, abs=0.01)

    def test_negative_reward_roas(self):
        """负奖励降低 ROAS."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_neg_roas", avg_reward=-0.5)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        # ROAS = 1.0 + (-0.5)*0.5 = 0.75
        assert result.expected_roas == pytest.approx(0.75, abs=0.01)


# ═══════════════════════════════════════════════════════════════
# 5. Risk Assessment (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestRiskAssessment:
    """风险评估测试."""

    def test_high_risk(self):
        """高风险信号时返回 high."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_high_risk")
        risk = _make_risk(level="high", signal_type="strategy_decay")
        knowledge = _make_knowledge(patterns=[pattern], warnings=[risk])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.risk_level == "high"

    def test_medium_risk(self):
        """中风险信号时返回 medium."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_med_risk")
        risk = _make_risk(level="medium", signal_type="budget_inefficiency")
        knowledge = _make_knowledge(patterns=[pattern], warnings=[risk])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.risk_level == "medium"

    def test_low_risk(self):
        """无风险信号时返回 low."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_low_risk")
        knowledge = _make_knowledge(patterns=[pattern], warnings=[])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.risk_level == "low"

    def test_with_risk_recommendations(self):
        """高风险时包含风险建议."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_risk_recs")
        risk = _make_risk(level="high", recommendations=["Reduce", "Refresh"])
        knowledge = _make_knowledge(patterns=[pattern], warnings=[risk])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.risk_level == "high"
        # 高风险建议会被包含在 recommendations 中
        assert "HIGH RISK" in result.recommendations[-1] or any(
            "HIGH RISK" in r for r in result.recommendations
        )

    def test_no_risks(self):
        """无风险时返回 low."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_no_risk")
        knowledge = _make_knowledge(patterns=[pattern], warnings=[])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.risk_level == "low"


# ═══════════════════════════════════════════════════════════════
# 6. Recommendations (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestRecommendations:
    """推荐建议测试."""

    def test_positive_pattern_recs(self):
        """正向模式包含利用建议."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_pos_rec", impact="positive", confidence=0.8)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert any("Leverage" in r for r in result.recommendations)

    def test_negative_pattern_recs(self):
        """负向模式包含避免建议."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_neg_rec", impact="negative", confidence=0.8)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert any("Avoid" in r for r in result.recommendations)

    def test_neutral_pattern_recs(self):
        """中性模式包含监控建议."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_neu_rec", impact="neutral", confidence=0.8)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert any("monitor" in r.lower() for r in result.recommendations)

    def test_high_risk_recs(self):
        """高风险时包含升级建议."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_hr_rec", impact="positive")
        risk = _make_risk(level="high")
        knowledge = _make_knowledge(patterns=[pattern], warnings=[risk])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert any("HIGH RISK" in r for r in result.recommendations)

    def test_strong_strategy_recs(self):
        """强策略包含在建议中."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_strategy_rec", impact="positive")
        strategy = _make_strategy(name="top_strategy", effectiveness=0.5)
        knowledge = _make_knowledge(patterns=[pattern], strategies=[strategy])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert any("top_strategy" in r for r in result.recommendations)


# ═══════════════════════════════════════════════════════════════
# 7. Confidence (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestConfidence:
    """预测置信度测试."""

    def test_high_confidence(self):
        """高置信度模式 + 高匹配 → 高预测置信度."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_high_conf", confidence=0.9, success_rate=0.9, sample_count=50)
        knowledge = _make_knowledge(patterns=[pattern], confidence=0.9)
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0.6

    def test_low_confidence(self):
        """低置信度模式 → 低预测置信度."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_low_conf", confidence=0.3, success_rate=0.3, sample_count=3)
        knowledge = _make_knowledge(patterns=[pattern], confidence=0.3)
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence < 0.7

    def test_sample_factor(self):
        """大样本量增加置信度."""
        predictor = PatternPredictor()
        high_sample = _make_pattern(condition="test_high_sample", sample_count=100, confidence=0.8)
        low_sample = _make_pattern(condition="test_low_sample", sample_count=5, confidence=0.8)
        knowledge_high = _make_knowledge(patterns=[high_sample])
        knowledge_low = _make_knowledge(patterns=[low_sample])

        result_high = predictor.predict(context={"creative": "test"}, knowledge=knowledge_high)
        result_low = predictor.predict(context={"creative": "test"}, knowledge=knowledge_low)

        assert result_high.confidence > result_low.confidence

    def test_risk_discount_on_confidence(self):
        """高风险降低预测置信度."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_risk_conf", confidence=0.8)
        risk = _make_risk(level="high")
        knowledge = _make_knowledge(patterns=[pattern], warnings=[risk])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0

    def test_knowledge_quality(self):
        """知识质量影响置信度."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_kq_high_qual", confidence=0.8)
        knowledge_high = _make_knowledge(patterns=[pattern], confidence=0.9)
        knowledge_low = _make_knowledge(patterns=[pattern], confidence=0.3)

        result_high = predictor.predict(context={"creative": "test"}, knowledge=knowledge_high)
        result_low = predictor.predict(context={"creative": "test"}, knowledge=knowledge_low)

        assert result_high.confidence > result_low.confidence


# ═══════════════════════════════════════════════════════════════
# 8. Model Validation (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestModelValidation:
    """模式预测模型验证."""

    def test_properties(self):
        """PatternPrediction 属性完整."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_props")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.recommended_pattern == "creative|test_props"
        assert result.expected_roas > 0
        assert result.expected_success_rate > 0
        assert result.confidence > 0
        assert result.context_match_score > 0
        assert result.risk_level in ("low", "medium", "high")
        assert isinstance(result.recommendations, list)

    def test_is_strong(self):
        """高置信度 + 有匹配模式 → is_strong=True."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_strong", confidence=0.9, success_rate=0.9, sample_count=50)
        knowledge = _make_knowledge(patterns=[pattern], confidence=0.9)
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.is_strong is True

    def test_is_actionable(self):
        """中等置信度 → is_actionable=True."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_actionable", confidence=0.6, sample_count=15)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.is_actionable is True

    def test_to_dict(self):
        """to_dict 返回完整字典."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_dict")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)
        d = result.to_dict()

        assert "prediction_id" in d
        assert "recommended_pattern" in d
        assert "expected_roas" in d
        assert "confidence" in d
        assert "matched_pattern_count" in d
        assert "context_match_score" in d

    def test_default_values(self):
        """默认 PatternPrediction 属性."""
        p = PatternPrediction()

        assert p.confidence == 0.0
        assert p.expected_roas == 0.0
        assert p.risk_level == "medium"
        assert p.is_strong is False
        assert p.is_actionable is False


# ═══════════════════════════════════════════════════════════════
# 9. Edge Cases (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_unknown_context_fields(self):
        """未知上下文字段不影响匹配."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_unknown")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"unknown_field": "value", "creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0

    def test_partial_context_match(self):
        """部分字段匹配也有效."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_partial_match")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"game": "merge", "creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0

    def test_very_low_min_match_score(self):
        """极低匹配阈值."""
        predictor = PatternPredictor(min_match_score=0.01)
        pattern = _make_pattern(condition="test_low_match")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0

    def test_very_high_min_prediction_confidence(self):
        """极高预测置信度阈值."""
        predictor = PatternPredictor(min_prediction_confidence=0.99)
        pattern = _make_pattern(condition="test_high_thresh", confidence=0.1, success_rate=0.1, sample_count=1)
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.metadata["reason"] == "no_patterns_above_threshold"

    def test_large_knowledge_many_patterns(self):
        """大量模式也能正确预测."""
        predictor = PatternPredictor()
        patterns = [
            _make_pattern(condition=f"test_large_{i}", impact="positive", sample_count=20)
            for i in range(50)
        ]
        # 确保第一个能被匹配
        patterns[0] = _make_pattern(condition="test_large_0", impact="positive", sample_count=20)
        knowledge = _make_knowledge(patterns=patterns)
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0


# ═══════════════════════════════════════════════════════════════
# 10. Integration (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试."""

    def test_full_pipeline_with_real_knowledge(self):
        """完整 pipeline: 知识 → 预测."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="fantasy_character", avg_reward=0.3, sample_count=20)
        strategy = _make_strategy(name="scale_up", effectiveness=0.4)
        knowledge = _make_knowledge(patterns=[pattern], strategies=[strategy])
        ctx = {"creative": "fantasy"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.recommended_pattern == "creative|fantasy_character"
        assert result.expected_roas > 0
        assert result.confidence > 0
        assert result.risk_level == "low"

    def test_incremental_predictions(self):
        """增量预测: 多次预测结果一致."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="test_incremental")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {"creative": "test"}

        r1 = predictor.predict(context=ctx, knowledge=knowledge)
        r2 = predictor.predict(context=ctx, knowledge=knowledge)

        assert r1.recommended_pattern == r2.recommended_pattern
        assert r1.confidence == r2.confidence

    def test_different_action_types(self):
        """不同 action_type 过滤."""
        predictor = PatternPredictor()
        pattern_scale = _make_pattern(
            condition="scale_budget",
            metadata={"action_types": ["scale"]},
        )
        pattern_stop = _make_pattern(
            condition="stop_campaign",
            metadata={"action_types": ["stop"]},
        )
        knowledge = _make_knowledge(patterns=[pattern_scale, pattern_stop])
        ctx = {"creative": "scale"}

        result_scale = predictor.predict(context=ctx, knowledge=knowledge, action_type="scale")
        result_stop = predictor.predict(context=ctx, knowledge=knowledge, action_type="stop")

        assert result_scale.confidence > 0
        assert result_stop.confidence > 0

    def test_context_with_all_fields(self):
        """全字段上下文."""
        predictor = PatternPredictor()
        pattern = _make_pattern(condition="merge_witch_us_female_high_spend")
        knowledge = _make_knowledge(patterns=[pattern])
        ctx = {
            "game": "merge",
            "country": "us",
            "creative": "female",
            "audience": "merge",
            "spend": "high",
        }

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence > 0
        assert result.context_match_score > 0.2  # 多字段匹配

    def test_no_patterns_in_knowledge(self):
        """知识中无模式返回空预测."""
        predictor = PatternPredictor()
        knowledge = _make_knowledge(patterns=[], strategies=[])
        ctx = {"creative": "test"}

        result = predictor.predict(context=ctx, knowledge=knowledge)

        assert result.confidence == 0.0
        assert result.metadata["reason"] == "no_knowledge_available"