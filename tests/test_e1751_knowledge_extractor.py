"""E13.7.5.1 Learning Knowledge Extractor — 专项测试.

测试覆盖:
  1. Basic extraction:       空/不足/正常/无奖励/无归因
  2. Pattern extraction:     按因子/按action_type/正向/负向/去重/min_evidence
  3. Strategy extraction:    策略洞察/最佳上下文/警告/趋势/拦截
  4. Risk detection:         创意疲劳/策略衰减/预算效率/受众饱和/无风险/高风险/排序
  5. Confidence:             有模式/有策略/空/不足
  6. Model validation:       LearnedPattern/StrategyInsight/RiskSignal/LearningKnowledge
  7. Edge cases:             大奖励/极负奖励/重复/混合
  8. Integration:            完整pipeline/增量提取/不同min_evidence/count tracking
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_knowledge_extractor import (
    LearningKnowledgeExtractor,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_models import (
    AttributionEvidence,
    AttributionResult,
    LearnedPattern,
    LearningExperience,
    LearningKnowledge,
    LearningOutcome,
    LearningReward,
    RiskSignal,
    StrategyInsight,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_experience(
    learning_id: str = "",
    action_type: str = "replace_creative",
    strategy_name: str = "default_strategy",
    total_reward: float = 0.5,
    decision_id: str = "",
    context: dict[str, Any] | None = None,
    was_blocked: bool = False,
) -> LearningExperience:
    """创建测试用 LearningExperience."""
    outcome = LearningOutcome(success=total_reward > 0.15, was_blocked=was_blocked)
    reward = LearningReward(total_reward=total_reward, business_reward=total_reward)
    return LearningExperience(
        learning_id=learning_id,
        action_type=action_type,
        strategy_name=strategy_name,
        decision_id=decision_id or learning_id,
        outcome=outcome,
        reward=reward,
        context=context or {},
    )


def _make_attribution(
    decision_id: str,
    primary_factor: str = "creative",
    creative_contribution: float = 0.5,
    audience_contribution: float = 0.3,
    source: str = "test",
) -> AttributionResult:
    """创建测试用 AttributionResult."""
    evidence = AttributionEvidence(metric_source=source, source_ids=[source])
    return AttributionResult(
        decision_id=decision_id,
        primary_factor=primary_factor,
        creative_contribution=creative_contribution,
        audience_contribution=audience_contribution,
        evidence=[evidence],
    )


def _make_extractor(
    min_evidence: int = 10,
    min_confidence: float = 0.50,
) -> LearningKnowledgeExtractor:
    """创建测试用 Extractor (默认 min_evidence=10, min_confidence=0.50)."""
    return LearningKnowledgeExtractor(min_evidence=min_evidence, min_confidence=min_confidence)


# ═══════════════════════════════════════════════════════════════
# 1. Basic Extraction
# ═══════════════════════════════════════════════════════════════


class TestBasicExtraction:
    """基础提取 — 空/不足/正常/无奖励/无归因."""

    def test_extract_with_empty_experiences(self) -> None:
        """空经验列表 → confidence=0.0."""
        extractor = _make_extractor()
        knowledge = extractor.extract([], [], [])
        assert knowledge.confidence == 0.0
        assert knowledge.total_experiences == 0
        assert knowledge.patterns == []
        assert knowledge.strategies == []
        assert knowledge.warnings == []
        assert knowledge.extraction_method == "statistical"
        assert "insufficient_experiences" in knowledge.metadata.get("reason", "")

    def test_extract_with_insufficient_experiences(self) -> None:
        """经验数不足 min_evidence=10 → confidence=0.0."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}")
            for i in range(5)
        ]
        knowledge = extractor.extract(experiences, [], [])
        assert knowledge.confidence == 0.0
        assert knowledge.total_experiences == 5
        assert knowledge.patterns == []
        assert knowledge.strategies == []
        assert knowledge.warnings == []
        assert knowledge.metadata["min_required"] == 10

    def test_extract_with_normal_experiences(self) -> None:
        """15 条正常经验 → 输出 patterns + strategies."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        assert knowledge.total_experiences == 15
        assert knowledge.confidence > 0.0
        assert knowledge.extraction_method == "statistical"

    def test_extract_with_no_rewards_explicit(self) -> None:
        """显式传入空 rewards 列表 + 经验无 reward → 仍可提取."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        assert knowledge.total_experiences == 15

    def test_extract_with_no_attributions(self) -> None:
        """无归因数据 → 仅按 action_type 提取模式."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], [])
        assert knowledge.total_experiences == 15


# ═══════════════════════════════════════════════════════════════
# 2. Pattern Extraction
# ═══════════════════════════════════════════════════════════════


class TestPatternExtraction:
    """模式提取 — 因子/action_type/正向/负向/去重/阈值."""

    def test_extract_patterns_by_factor(self) -> None:
        """按 primary_factor=creative 分组提取模式."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        # 应有 factor-based pattern
        factor_patterns = [p for p in knowledge.patterns if p.dimension == "creative"]
        assert len(factor_patterns) >= 1

    def test_extract_patterns_by_action_type(self) -> None:
        """按 action_type 分组提取模式."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        action_patterns = [p for p in knowledge.patterns if p.dimension == "action_type"]
        assert len(action_patterns) >= 1
        assert action_patterns[0].condition == "replace_creative"

    def test_extract_positive_patterns(self) -> None:
        """正向奖励 → impact=positive."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.8, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        positive = [p for p in knowledge.patterns if p.impact == "positive"]
        assert len(positive) >= 1

    def test_extract_negative_patterns(self) -> None:
        """负向奖励 → impact=negative."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=-0.8, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        negative = [p for p in knowledge.patterns if p.impact == "negative"]
        assert len(negative) >= 1

    def test_pattern_deduplication(self) -> None:
        """同 dimension+condition 去重，保留置信度最高的."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        # 验证无重复 dimension+condition
        keys = [(p.dimension, p.condition) for p in knowledge.patterns]
        assert len(keys) == len(set(keys))

    def test_pattern_min_evidence_threshold(self) -> None:
        """因子分组不足 min_evidence → 不产生该维度模式."""
        extractor = _make_extractor(min_evidence=10)
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(5)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(5)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        assert knowledge.confidence == 0.0
        assert knowledge.patterns == []


# ═══════════════════════════════════════════════════════════════
# 3. Strategy Extraction
# ═══════════════════════════════════════════════════════════════


class TestStrategyExtraction:
    """策略提取 — 洞察/最佳上下文/警告/趋势/拦截."""

    def test_extract_strategies_normal(self) -> None:
        """正常策略提取."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], [])
        assert len(knowledge.strategies) >= 1
        assert knowledge.strategies[0].strategy_name == "strategy_a"
        assert knowledge.strategies[0].action_type == "replace_creative"
        assert knowledge.strategies[0].total_count == 15
        assert knowledge.strategies[0].avg_effectiveness > 0

    def test_strategy_best_context(self) -> None:
        """验证最佳上下文填充."""
        extractor = _make_extractor()
        context = {"product": "game_a", "platform": "ios"}
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context=context,
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], [])
        assert len(knowledge.strategies) >= 1
        # product 和 platform 出现频率 >= 50% (15*0.5=7.5)
        assert "product" in knowledge.strategies[0].best_context
        assert "platform" in knowledge.strategies[0].best_context

    def test_strategy_warnings_negative_rate(self) -> None:
        """高负奖励率 → 警告."""
        extractor = _make_extractor()
        # 6 条负奖励, 9 条正奖励 → neg_rate = 6/15 = 0.4 > 0.3
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=-0.5 if i < 6 else 0.5,
                decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], [])
        assert len(knowledge.strategies) >= 1
        assert any("negative reward" in w.lower() for w in knowledge.strategies[0].warnings)

    def test_strategy_declining_trend(self) -> None:
        """奖励趋势下降 → 警告."""
        extractor = _make_extractor()
        # 前 7 条高奖励, 后 8 条低奖励 → 下降趋势
        experiences = [
            _make_experience(
                learning_id=f"e{i}",
                total_reward=0.5 if i < 7 else -0.2,
                decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], [])
        assert len(knowledge.strategies) >= 1
        assert any("declining" in w.lower() for w in knowledge.strategies[0].warnings)

    def test_strategy_blocked_executions(self) -> None:
        """有拦截执行 → 警告."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                was_blocked=(i == 0),
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], [])
        assert len(knowledge.strategies) >= 1
        assert any("blocked" in w.lower() for w in knowledge.strategies[0].warnings)


# ═══════════════════════════════════════════════════════════════
# 4. Risk Detection
# ═══════════════════════════════════════════════════════════════


class TestRiskDetection:
    """风险检测 — 创意疲劳/策略衰减/预算效率/受众饱和/无风险/排序."""

    def test_detect_creative_fatigue(self) -> None:
        """创意贡献下降 → creative_fatigue 风险."""
        extractor = _make_extractor()
        # 15 条 creative 经验，前 5 条高 creative_contribution，后 5 条低
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="creative_update", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(
                decision_id=f"d{i}",
                primary_factor="creative",
                creative_contribution=0.5 if i < 5 else 0.1,
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        creative_risks = [w for w in knowledge.warnings if w.signal_type == "creative_fatigue"]
        assert len(creative_risks) >= 1

    def test_detect_strategy_decay(self) -> None:
        """奖励衰减 → strategy_decay 风险."""
        extractor = _make_extractor()
        # 前 5 条高奖励, 后 5 条低奖励 → recent_avg < older_avg - 0.2
        experiences = [
            _make_experience(
                learning_id=f"e{i}",
                total_reward=0.5 if i < 5 else -0.2,
                decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(10)
        ]
        knowledge = extractor.extract(experiences, [], [])
        decay_risks = [w for w in knowledge.warnings if w.signal_type == "strategy_decay"]
        assert len(decay_risks) >= 1

    def test_detect_budget_inefficiency(self) -> None:
        """预算动作负奖励率高 → budget_inefficiency 风险."""
        extractor = _make_extractor()
        # 8 条 budget action, 5 条负奖励 → neg_rate = 5/8 = 0.625 > 0.4
        experiences = [
            _make_experience(
                learning_id=f"e{i}",
                total_reward=-0.5 if i < 5 else 0.3,
                decision_id=f"d{i}",
                action_type="budget_adjust", strategy_name="strategy_a",
            )
            for i in range(8)
        ]
        # 需要足够总经验数通过 min_evidence (10)
        extra = [
            _make_experience(
                learning_id=f"extra{i}", total_reward=0.5, decision_id=f"extra{i}",
                action_type="other", strategy_name="other_strategy",
            )
            for i in range(5)
        ]
        knowledge = extractor.extract(experiences + extra, [], [])
        budget_risks = [w for w in knowledge.warnings if w.signal_type == "budget_inefficiency"]
        assert len(budget_risks) >= 1

    def test_detect_audience_saturation(self) -> None:
        """受众贡献为负 → audience_saturation 风险."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="audience_targeting", strategy_name="strategy_a",
            )
            for i in range(8)
        ]
        attributions = [
            _make_attribution(
                decision_id=f"d{i}",
                primary_factor="audience",
                audience_contribution=-0.2,
            )
            for i in range(8)
        ]
        extra = [
            _make_experience(
                learning_id=f"extra{i}", total_reward=0.5, decision_id=f"extra{i}",
                action_type="other", strategy_name="other_strategy",
            )
            for i in range(5)
        ]
        knowledge = extractor.extract(experiences + extra, [], attributions)
        audience_risks = [w for w in knowledge.warnings if w.signal_type == "audience_saturation"]
        assert len(audience_risks) >= 1

    def test_no_risk_detection(self) -> None:
        """所有条件不满足 → 无风险信号."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(
                decision_id=f"d{i}",
                primary_factor="creative",
                creative_contribution=0.5,
                audience_contribution=0.3,
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        assert knowledge.warnings == []

    def test_high_risk_detection(self) -> None:
        """高风险信号 — creative_contribution 近期 < 0."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="creative_update", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(
                decision_id=f"d{i}",
                primary_factor="creative",
                creative_contribution=0.5 if i < 5 else -0.1,
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        high_risks = [w for w in knowledge.warnings if w.risk_level == "high"]
        assert len(high_risks) >= 1

    def test_medium_risk_detection(self) -> None:
        """中风险信号 — 策略衰减 (recent_avg >= -0.15)."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}",
                total_reward=0.5 if i < 5 else 0.0,
                decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(10)
        ]
        knowledge = extractor.extract(experiences, [], [])
        medium_risks = [w for w in knowledge.warnings if w.risk_level == "medium"]
        assert len(medium_risks) >= 1

    def test_risk_sorting(self) -> None:
        """风险按 critical > high > medium > low 排序."""
        extractor = _make_extractor()
        # 策略衰减 → medium risk
        experiences = [
            _make_experience(
                learning_id=f"e{i}",
                total_reward=0.5 if i < 5 else 0.0,
                decision_id=f"d{i}",
                action_type="replace_creative",
                strategy_name="strategy_a",
            )
            for i in range(10)
        ]
        knowledge = extractor.extract(experiences, [], [])
        risks = knowledge.warnings
        # 按 risk_level 排序验证
        levels = [r.risk_level for r in risks]
        level_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for i in range(len(levels) - 1):
            assert level_order[levels[i]] <= level_order[levels[i + 1]]


# ═══════════════════════════════════════════════════════════════
# 5. Confidence
# ═══════════════════════════════════════════════════════════════


class TestConfidence:
    """整体置信度计算."""

    def test_overall_confidence_with_patterns(self) -> None:
        """有模式 + 策略 → 置信度 > 0."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        assert knowledge.confidence > 0.0

    def test_overall_confidence_with_strategies_only(self) -> None:
        """仅有策略无模式 → 置信度仍 > 0."""
        extractor = _make_extractor()
        # 使用不同的 action_type 和 strategy_name 避免产生 factor pattern
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
            )
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], [])
        assert knowledge.confidence > 0.0

    def test_overall_confidence_empty(self) -> None:
        """空经验 → confidence=0.0."""
        extractor = _make_extractor()
        knowledge = extractor.extract([], [], [])
        assert knowledge.confidence == 0.0

    def test_overall_confidence_insufficient(self) -> None:
        """经验不足 → confidence=0.0."""
        extractor = _make_extractor(min_evidence=10)
        knowledge = extractor.extract(
            [_make_experience(learning_id="e1", total_reward=0.5)],
            [], [],
        )
        assert knowledge.confidence == 0.0


# ═══════════════════════════════════════════════════════════════
# 6. Model Validation
# ═══════════════════════════════════════════════════════════════


class TestModelValidation:
    """模型属性验证."""

    def test_learned_pattern_properties(self) -> None:
        """LearnedPattern is_strong / is_reliable 属性."""
        # 强模式: confidence >= 0.7, sample_count >= 10
        strong = LearnedPattern(
            dimension="creative", condition="cond_a", impact="positive",
            avg_reward=0.5, sample_count=15, confidence=0.8, success_rate=0.9,
        )
        assert strong.is_strong is True
        assert strong.is_reliable is True

        # 可靠但非强: confidence >= 0.5, sample_count >= 5, 但 confidence < 0.7
        reliable = LearnedPattern(
            dimension="creative", condition="cond_b", impact="neutral",
            avg_reward=0.2, sample_count=8, confidence=0.6, success_rate=0.5,
        )
        assert reliable.is_strong is False
        assert reliable.is_reliable is True

        # 不可靠: sample_count < 5
        weak = LearnedPattern(
            dimension="creative", condition="cond_c", impact="neutral",
            avg_reward=0.0, sample_count=3, confidence=0.3, success_rate=0.3,
        )
        assert weak.is_strong is False
        assert weak.is_reliable is False

    def test_strategy_insight_properties(self) -> None:
        """StrategyInsight success_rate 属性."""
        insight = StrategyInsight(
            strategy_name="s1", action_type="a1",
            avg_effectiveness=0.5, success_count=12, total_count=15,
            confidence=0.7,
        )
        assert insight.success_rate == pytest.approx(12 / 15)

        # total_count=0 边界
        empty = StrategyInsight(strategy_name="s2", action_type="a2")
        assert empty.success_rate == 0.0

    def test_risk_signal_properties(self) -> None:
        """RiskSignal 字段完整性."""
        signal = RiskSignal(
            signal_type="creative_fatigue",
            risk_level="high",
            condition="Creative contribution declining",
            frequency=10,
            avg_impact=-0.2,
            confidence=0.75,
            recommendations=["R1", "R2"],
        )
        assert signal.signal_type == "creative_fatigue"
        assert signal.risk_level == "high"
        assert signal.frequency == 10
        assert signal.avg_impact == -0.2
        assert signal.confidence == 0.75
        assert len(signal.recommendations) == 2

    def test_learning_knowledge_properties(self) -> None:
        """LearningKnowledge 聚合属性."""
        patterns = [
            LearnedPattern(
                dimension="creative", condition="c1", impact="positive",
                avg_reward=0.6, sample_count=15, confidence=0.85, success_rate=0.9,
            ),
        ]
        strategies = [
            StrategyInsight(
                strategy_name="s1", action_type="a1",
                avg_effectiveness=0.5, success_count=10, total_count=15,
                confidence=0.7,
            ),
        ]
        warnings = [
            RiskSignal(
                signal_type="strategy_decay", risk_level="critical",
                condition="decay", frequency=5, avg_impact=-0.3, confidence=0.8,
            ),
        ]
        knowledge = LearningKnowledge(
            patterns=patterns,
            strategies=strategies,
            warnings=warnings,
            confidence=0.6,
            total_experiences=15,
            extraction_method="statistical",
        )
        assert knowledge.pattern_count == 1
        assert knowledge.strategy_count == 1
        assert knowledge.warning_count == 1
        assert knowledge.has_strong_patterns is True
        assert knowledge.has_critical_risks is True


# ═══════════════════════════════════════════════════════════════
# 7. Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况 — 大奖励/极负/重复/混合."""

    def test_very_large_rewards(self) -> None:
        """total_reward 接近 1.0."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.95, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        assert knowledge.confidence > 0.0
        for p in knowledge.patterns:
            assert p.avg_reward >= 0.0

    def test_very_negative_rewards(self) -> None:
        """total_reward 接近 -1.0."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=-0.95, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        # 有负向模式
        negative = [p for p in knowledge.patterns if p.impact == "negative"]
        assert len(negative) >= 1

    def test_duplicate_experiences(self) -> None:
        """重复 learning_id 的经验 → 正常处理，不崩溃."""
        extractor = _make_extractor()
        base = _make_experience(
            learning_id="dup_id", total_reward=0.5, decision_id="d0",
            action_type="replace_creative", strategy_name="strategy_a",
            context={"opportunity_type": "creative_fatigue"},
        )
        experiences = [base] * 15
        attributions = [_make_attribution(decision_id="d0", primary_factor="creative")] * 15
        knowledge = extractor.extract(experiences, [], attributions)
        assert knowledge.total_experiences == 15

    def test_mixed_positive_negative(self) -> None:
        """正负奖励混合."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5 if i < 8 else -0.5,
                decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)
        assert knowledge.confidence > 0.0


# ═══════════════════════════════════════════════════════════════
# 8. Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试 — 完整 pipeline/增量/不同 min_evidence/count tracking."""

    def test_full_extraction_pipeline(self) -> None:
        """完整提取 pipeline: experiences → patterns + strategies + risks."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]
        knowledge = extractor.extract(experiences, [], attributions)

        assert knowledge.total_experiences == 15
        assert knowledge.extraction_method == "statistical"
        assert knowledge.confidence > 0.0
        assert knowledge.pattern_count >= 1
        assert knowledge.strategy_count >= 1
        # 验证 pattern 有 source_experience_ids
        for p in knowledge.patterns:
            assert len(p.source_experience_ids) > 0
        # 验证 strategy 有 total_count
        for s in knowledge.strategies:
            assert s.total_count > 0

    def test_incremental_extraction(self) -> None:
        """两次提取 → extraction_count 递增."""
        extractor = _make_extractor()
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(15)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(15)
        ]

        assert extractor.extraction_count == 0
        extractor.extract(experiences, [], attributions)
        assert extractor.extraction_count == 1
        extractor.extract(experiences, [], attributions)
        assert extractor.extraction_count == 2

    def test_different_min_evidence_values(self) -> None:
        """不同 min_evidence → 影响是否提取."""
        experiences = [
            _make_experience(
                learning_id=f"e{i}", total_reward=0.5, decision_id=f"d{i}",
                action_type="replace_creative", strategy_name="strategy_a",
                context={"opportunity_type": "creative_fatigue"},
            )
            for i in range(8)
        ]
        attributions = [
            _make_attribution(decision_id=f"d{i}", primary_factor="creative")
            for i in range(8)
        ]

        # min_evidence=5 → 应提取
        low_extractor = _make_extractor(min_evidence=5)
        low_knowledge = low_extractor.extract(experiences, [], attributions)
        assert low_knowledge.confidence > 0.0

        # min_evidence=10 → 不足
        high_extractor = _make_extractor(min_evidence=10)
        high_knowledge = high_extractor.extract(experiences, [], attributions)
        assert high_knowledge.confidence == 0.0

    def test_extraction_count_tracking(self) -> None:
        """extraction_count 属性正确追踪."""
        extractor = _make_extractor()
        assert extractor.extraction_count == 0

        extractor.extract([], [], [])
        assert extractor.extraction_count == 1

        # 不足 min_evidence 也计数
        extractor.extract(
            [_make_experience(learning_id="e1", total_reward=0.5)],
            [], [],
        )
        assert extractor.extraction_count == 2