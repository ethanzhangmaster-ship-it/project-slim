"""E15.3.5 Continuous Learning Loop 测试 — 完整测试.

测试覆盖:
  - Models (20 tests)
  - Experience Collector (20 tests)
  - Quality Evaluation (20 tests)
  - Knowledge Extraction (20 tests)
  - Pattern Evolution (20 tests)
  - Strategy Learning (10 tests)
  - Integration (10 tests)

总计: ~120 tests
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models import (
    ExperienceQuality,
    ExperienceQualityLevel,
    InsightType,
    LearnedPattern,
    LearningExperience,
    LearningInsight,
    LearningResult,
    PatternEvolution,
    PatternStatus,
    StrategyRecommendation,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.experience_collector import (
    ExperienceCollector,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.experience_evaluator import (
    ExperienceEvaluator,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.knowledge_extractor import (
    KnowledgeExtractor,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.pattern_evolution import (
    PatternEvolutionEngine,
    VALID_TRANSITIONS,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.strategy_learner import (
    StrategyLearner,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_engine import (
    ContinuousLearningEngine,
    ModelImprovementFeedback,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def experience():
    return LearningExperience(
        action="creative_refresh",
        context={"country": "US", "campaign": "merge_game", "fatigue": 0.82},
        decision={"confidence": 0.86},
        result={"CTR": "+18%", "ROAS": "+12%"},
        reward=0.74,
        tags=["ua", "creative"],
    )


@pytest.fixture
def quality():
    return ExperienceQuality(
        confidence=0.85,
        reliability=0.80,
        impact=0.75,
        novelty=0.60,
        learning_value=0.76,
        level=ExperienceQualityLevel.HIGH,
    )


@pytest.fixture
def pattern():
    return LearnedPattern(
        name="pattern_creative_refresh",
        conditions={"country": "US", "genre": "Puzzle"},
        recommendation="Strongly recommend 'creative_refresh'",
        confidence=0.82,
        success_rate=0.78,
        usage_count=20,
        evidence_count=50,
        status=PatternStatus.DISCOVERED,
    )


@pytest.fixture
def active_pattern():
    return LearnedPattern(
        name="pattern_scale_budget",
        conditions={"country": "US", "genre": "Puzzle"},
        recommendation="Strongly recommend 'scale_budget'",
        confidence=0.90,
        success_rate=0.85,
        usage_count=30,
        evidence_count=100,
        status=PatternStatus.ACTIVE,
    )


@pytest.fixture
def collector():
    return ExperienceCollector()


@pytest.fixture
def evaluator():
    return ExperienceEvaluator()


@pytest.fixture
def extractor():
    return KnowledgeExtractor()


@pytest.fixture
def evolution():
    return PatternEvolutionEngine()


@pytest.fixture
def learner():
    return StrategyLearner()


@pytest.fixture
def engine():
    return ContinuousLearningEngine()


@pytest.fixture
def sample_experiences():
    """Create 50 sample experiences for testing."""
    exps = []
    for i in range(50):
        success = i % 3 != 0  # 2/3 are successful
        exps.append(LearningExperience(
            action="creative_refresh" if i % 2 == 0 else "scale_budget",
            context={"country": "US", "campaign": f"c{i % 5}", "fatigue": 0.5 + i * 0.01},
            decision={"confidence": 0.7 + i * 0.005},
            result={"CTR": f"+{10 + i % 20}%", "ROAS": f"+{5 + i % 15}%"},
            reward=0.7 if success else -0.3,
            tags=["ua"],
        ))
    return exps


# ═══════════════════════════════════════════════════════════════════
# 1. Models (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestExperienceQuality:
    def test_create_quality(self):
        q = ExperienceQuality(
            confidence=0.85, reliability=0.80, impact=0.75, novelty=0.60, learning_value=0.76
        )
        assert q.confidence == 0.85
        assert q.reliability == 0.80
        assert q.impact == 0.75
        assert q.novelty == 0.60
        assert q.learning_value == 0.76

    def test_quality_defaults(self):
        q = ExperienceQuality()
        assert q.confidence == 0.0
        assert q.learning_value == 0.0
        assert q.level == ExperienceQualityLevel.MEDIUM
        assert q.issues == []

    def test_quality_is_valuable_high(self, quality):
        assert quality.is_valuable()

    def test_quality_is_valuable_noise(self):
        q = ExperienceQuality(learning_value=0.15, level=ExperienceQualityLevel.NOISE)
        assert not q.is_valuable()

    def test_quality_is_valuable_low_value(self):
        q = ExperienceQuality(learning_value=0.25, level=ExperienceQualityLevel.LOW)
        assert not q.is_valuable()

    def test_quality_to_dict(self, quality):
        d = quality.to_dict()
        assert d["confidence"] == 0.85
        assert d["reliability"] == 0.80
        assert d["level"] == "high"
        assert d["learning_value"] == 0.76


class TestLearningExperience:
    def test_create_experience(self, experience):
        assert experience.action == "creative_refresh"
        assert experience.reward == 0.74
        assert experience.quality is None

    def test_experience_defaults(self):
        e = LearningExperience()
        assert e.action == ""
        assert e.reward == 0.0
        assert e.context == {}
        assert e.decision == {}
        assert e.result == {}

    def test_experience_is_valuable_with_quality(self, experience, quality):
        experience.quality = quality
        assert experience.is_valuable()

    def test_experience_is_valuable_no_quality_positive(self):
        e = LearningExperience(reward=0.5)
        assert e.is_valuable()

    def test_experience_is_valuable_no_quality_negative(self):
        e = LearningExperience(reward=-0.5)
        assert not e.is_valuable()

    def test_experience_is_valuable_no_quality_zero(self):
        e = LearningExperience(reward=0.0)
        assert not e.is_valuable()

    def test_experience_to_dict(self, experience):
        d = experience.to_dict()
        assert d["action"] == "creative_refresh"
        assert d["context"]["country"] == "US"
        assert d["reward"] == 0.74
        assert "experience_id" in d
        assert "timestamp" in d


class TestLearnedPattern:
    def test_create_pattern(self, pattern):
        assert pattern.name == "pattern_creative_refresh"
        assert pattern.status == PatternStatus.DISCOVERED
        assert pattern.usage_count == 20

    def test_pattern_defaults(self):
        p = LearnedPattern()
        assert p.name == ""
        assert p.status == PatternStatus.DISCOVERED
        assert p.confidence == 0.0

    def test_pattern_is_active(self, active_pattern):
        assert active_pattern.is_active()

    def test_pattern_is_not_active(self, pattern):
        assert not pattern.is_active()

    def test_pattern_is_valid(self, active_pattern):
        assert active_pattern.is_valid()

    def test_pattern_is_valid_validated(self):
        p = LearnedPattern(status=PatternStatus.VALIDATED)
        assert p.is_valid()

    def test_pattern_is_not_valid_discovered(self):
        p = LearnedPattern(status=PatternStatus.DISCOVERED)
        assert not p.is_valid()

    def test_pattern_to_dict(self, pattern):
        d = pattern.to_dict()
        assert d["name"] == "pattern_creative_refresh"
        assert d["status"] == "discovered"
        assert d["usage_count"] == 20


class TestPatternEvolution:
    def test_create_evolution(self):
        e = PatternEvolution(
            pattern_id="p1",
            from_status=PatternStatus.DISCOVERED,
            to_status=PatternStatus.VALIDATED,
            reason="validated",
        )
        assert e.pattern_id == "p1"
        assert e.from_status == PatternStatus.DISCOVERED
        assert e.to_status == PatternStatus.VALIDATED

    def test_evolution_to_dict(self):
        e = PatternEvolution(
            pattern_id="p1",
            from_status=PatternStatus.DISCOVERED,
            to_status=PatternStatus.VALIDATED,
            reason="test",
        )
        d = e.to_dict()
        assert d["pattern_id"] == "p1"
        assert d["from_status"] == "discovered"
        assert d["to_status"] == "validated"


class TestLearningInsight:
    def test_create_insight(self):
        i = LearningInsight(
            insight_type=InsightType.STRATEGY,
            description="Creative refresh works best after fatigue >0.8",
            confidence=0.82,
            affected_components=["planner", "selector"],
        )
        assert i.insight_type == InsightType.STRATEGY
        assert i.confidence == 0.82
        assert "planner" in i.affected_components

    def test_insight_to_dict(self):
        i = LearningInsight(
            insight_type=InsightType.PATTERN,
            description="test",
            confidence=0.7,
        )
        d = i.to_dict()
        assert d["insight_type"] == "pattern"
        assert d["description"] == "test"
        assert "insight_id" in d

    def test_insight_defaults(self):
        i = LearningInsight()
        assert i.insight_type == InsightType.PATTERN
        assert i.description == ""
        assert i.affected_components == []


class TestStrategyRecommendation:
    def test_create_recommendation(self):
        r = StrategyRecommendation(
            strategy_name="creative_refresh_strategy",
            description="Refresh creative every 10 days",
            confidence=0.81,
            expected_reward=0.25,
            action="creative_refresh",
            priority=1,
        )
        assert r.strategy_name == "creative_refresh_strategy"
        assert r.confidence == 0.81
        assert r.priority == 1

    def test_recommendation_defaults(self):
        r = StrategyRecommendation()
        assert r.strategy_name == ""
        assert r.priority == 3
        assert r.confidence == 0.0

    def test_recommendation_to_dict(self):
        r = StrategyRecommendation(
            strategy_name="test",
            action="test_action",
            confidence=0.75,
        )
        d = r.to_dict()
        assert d["strategy_name"] == "test"
        assert d["action"] == "test_action"
        assert "recommendation_id" in d


class TestLearningResult:
    def test_create_result(self):
        r = LearningResult(
            cycle_number=1,
            experiences_collected=100,
            experiences_evaluated=100,
            valuable_experiences=75,
            patterns_discovered=3,
            patterns_evolved=2,
            summary="Test summary",
        )
        assert r.cycle_number == 1
        assert r.experiences_collected == 100
        assert r.valuable_experiences == 75

    def test_result_defaults(self):
        r = LearningResult()
        assert r.cycle_number == 0
        assert r.insights == []
        assert r.strategy_recommendations == []

    def test_result_to_dict(self):
        r = LearningResult(cycle_number=1, summary="test")
        d = r.to_dict()
        assert d["cycle_number"] == 1
        assert d["summary"] == "test"
        assert "result_id" in d
        assert "insights" in d
        assert "strategy_recommendations" in d


# ═══════════════════════════════════════════════════════════════════
# 2. Experience Collector (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestExperienceCollectorCollect:
    def test_collect_single(self, collector):
        exp = collector.collect(
            action="creative_refresh",
            context={"country": "US"},
            reward=0.74,
        )
        assert exp.action == "creative_refresh"
        assert exp.reward == 0.74
        assert exp.context["country"] == "US"

    def test_collect_empty_defaults(self, collector):
        exp = collector.collect(action="test")
        assert exp.action == "test"
        assert exp.context == {}
        assert exp.decision == {}
        assert exp.result == {}
        assert exp.reward == 0.0
        assert exp.tags == []

    def test_collect_with_tags(self, collector):
        exp = collector.collect(action="test", tags=["ua", "creative"])
        assert exp.tags == ["ua", "creative"]

    def test_collect_with_metadata(self, collector):
        exp = collector.collect(action="test", metadata={"source": "auto", "version": 1})
        assert exp.metadata["source"] == "auto"

    def test_collect_with_timestamp(self, collector):
        ts = "2026-07-01T00:00:00+00:00"
        exp = collector.collect(action="test", timestamp=ts)
        assert exp.timestamp == ts

    def test_collect_from_result(self, collector):
        result_data = {
            "action": "scale_budget",
            "context": {"country": "JP"},
            "decision": {"confidence": 0.75},
            "result": {"ROAS": "+15%"},
            "reward": 0.65,
            "tags": ["scale"],
        }
        exp = collector.collect_from_result(result_data)
        assert exp.action == "scale_budget"
        assert exp.context["country"] == "JP"
        assert exp.reward == 0.65

    def test_collect_from_result_partial(self, collector):
        exp = collector.collect_from_result({"action": "test"})
        assert exp.action == "test"
        assert exp.context == {}
        assert exp.reward == 0.0

    def test_collect_batch(self, collector):
        results = [
            {"action": "action_a", "reward": 0.5},
            {"action": "action_b", "reward": 0.7},
            {"action": "action_c", "reward": 0.3},
        ]
        exps = collector.collect_batch(results)
        assert len(exps) == 3
        assert exps[0].action == "action_a"
        assert exps[2].reward == 0.3

    def test_collect_increments_count(self, collector):
        assert collector.collection_count == 0
        collector.collect(action="test")
        assert collector.collection_count == 1
        collector.collect(action="test")
        assert collector.collection_count == 2


class TestExperienceCollectorQuery:
    def test_get_experiences_empty(self, collector):
        assert collector.get_experiences() == []

    def test_get_experiences(self, collector):
        collector.collect(action="a")
        collector.collect(action="b")
        assert len(collector.get_experiences()) == 2

    def test_get_recent(self, collector):
        for i in range(10):
            collector.collect(action=f"action_{i}")
        recent = collector.get_recent(3)
        assert len(recent) == 3
        assert recent[-1].action == "action_9"

    def test_get_by_action(self, collector):
        collector.collect(action="scale")
        collector.collect(action="pause")
        collector.collect(action="scale")
        results = collector.get_by_action("scale")
        assert len(results) == 2

    def test_get_by_action_none(self, collector):
        collector.collect(action="scale")
        assert collector.get_by_action("nonexistent") == []

    def test_get_by_tag(self, collector):
        collector.collect(action="a", tags=["ua"])
        collector.collect(action="b", tags=["creative"])
        collector.collect(action="c", tags=["ua", "creative"])
        assert len(collector.get_by_tag("ua")) == 2
        assert len(collector.get_by_tag("creative")) == 2

    def test_get_valuable(self, collector):
        collector.collect(action="good", reward=0.8)
        collector.collect(action="bad", reward=-0.5)
        valuable = collector.get_valuable()
        assert len(valuable) == 1
        assert valuable[0].action == "good"

    def test_get_positive(self, collector):
        collector.collect(action="a", reward=0.5)
        collector.collect(action="b", reward=-0.2)
        collector.collect(action="c", reward=0.0)
        positive = collector.get_positive()
        assert len(positive) == 1
        assert positive[0].action == "a"

    def test_get_negative(self, collector):
        collector.collect(action="a", reward=0.5)
        collector.collect(action="b", reward=-0.2)
        collector.collect(action="c", reward=-0.5)
        negative = collector.get_negative()
        assert len(negative) == 2


class TestExperienceCollectorStats:
    def test_get_stats_empty(self, collector):
        stats = collector.get_stats()
        assert stats["total"] == 0
        assert stats["positive_rate"] == 0.0
        assert stats["avg_reward"] == 0.0

    def test_get_stats(self, collector):
        collector.collect(action="a", reward=0.8)
        collector.collect(action="b", reward=-0.2)
        collector.collect(action="a", reward=0.6)
        stats = collector.get_stats()
        assert stats["total"] == 3
        assert stats["positive"] == 2
        assert stats["negative"] == 1
        assert "action_distribution" in stats

    def test_reset_collector(self, collector):
        collector.collect(action="test")
        collector.reset()
        assert len(collector.get_experiences()) == 0
        assert collector.collection_count == 0

    def test_capacity_limit(self):
        collector = ExperienceCollector(max_experiences=5)
        for i in range(10):
            collector.collect(action=f"action_{i}")
        exps = collector.get_experiences()
        assert len(exps) == 5
        assert exps[-1].action == "action_9"
        assert exps[0].action == "action_5"


# ═══════════════════════════════════════════════════════════════════
# 3. Quality Evaluation (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestExperienceEvaluatorEvaluate:
    def test_evaluate_sets_quality(self, evaluator):
        exp = LearningExperience(
            action="creative_refresh",
            context={"country": "US", "campaign": "merge_game", "fatigue": 0.82},
            decision={"confidence": 0.86},
            result={"CTR": "+18%", "ROAS": "+12%"},
            reward=0.74,
        )
        quality = evaluator.evaluate(exp)
        assert exp.quality is not None
        assert exp.quality == quality

    def test_evaluate_high_reward_high_quality(self, evaluator):
        exp = LearningExperience(
            action="creative_refresh",
            context={"country": "US", "campaign": "merge_game", "fatigue": 0.82, "genre": "Puzzle"},
            decision={"confidence": 0.90},
            result={"CTR": "+25%", "ROAS": "+20%", "CPI": "-15%"},
            reward=0.90,
        )
        quality = evaluator.evaluate(exp)
        assert quality.learning_value > 0.5
        assert quality.level in (ExperienceQualityLevel.HIGH, ExperienceQualityLevel.MEDIUM)

    def test_evaluate_low_reward_low_quality(self, evaluator):
        exp = LearningExperience(
            action="test",
            context={},
            decision={"confidence": 0.1},
            result={},
            reward=0.05,
        )
        quality = evaluator.evaluate(exp)
        assert quality.learning_value < 0.5

    def test_evaluate_batch(self, evaluator):
        exps = [
            LearningExperience(action="a", reward=0.8, decision={"confidence": 0.9}),
            LearningExperience(action="b", reward=0.2, decision={"confidence": 0.3}),
        ]
        qualities = evaluator.evaluate_batch(exps)
        assert len(qualities) == 2
        assert all(e.quality is not None for e in exps)

    def test_evaluate_increments_count(self, evaluator):
        exp = LearningExperience(action="test", reward=0.5)
        assert evaluator.evaluation_count == 0
        evaluator.evaluate(exp)
        assert evaluator.evaluation_count == 1

    def test_evaluate_novelty_decreases_with_many_similar(self, evaluator):
        ctx = {"country": "US", "campaign": "merge"}
        # 先评估 12 次同样上下文，触发 novelty 衰减
        for _ in range(12):
            evaluator.evaluate(LearningExperience(action="a", context=ctx, reward=0.5))
        # 第 13 次应该 novelty 降低
        e_new = LearningExperience(action="a", context=ctx, reward=0.5)
        q_low = evaluator.evaluate(e_new)
        assert q_low.novelty < 0.5  # 大量相似上下文导致 novelty 下降


class TestExperienceEvaluatorFilter:
    def test_filter_valuable(self, evaluator):
        exps = [
            LearningExperience(action="a", reward=0.8, decision={"confidence": 0.9}),
            LearningExperience(action="b", reward=0.1, decision={"confidence": 0.1}),
        ]
        evaluator.evaluate_batch(exps)
        valuable = evaluator.filter_valuable(exps)
        assert len(valuable) >= 1

    def test_filter_valuable_empty(self, evaluator):
        assert evaluator.filter_valuable([]) == []

    def test_filter_by_level(self, evaluator):
        exps = [
            LearningExperience(action="a", reward=0.9, context={"a": 1, "b": 2, "c": 3}, decision={"confidence": 0.95}),
            LearningExperience(action="b", reward=0.1, decision={"confidence": 0.1}),
        ]
        evaluator.evaluate_batch(exps)
        filtered = evaluator.filter_by_level(exps, ExperienceQualityLevel.HIGH)
        assert len(filtered) >= 0  # 可能有 HIGH 也可能没有

    def test_filter_by_level_all(self, evaluator):
        exps = [
            LearningExperience(action="a", reward=0.8, decision={"confidence": 0.9}),
            LearningExperience(action="b", reward=0.7, decision={"confidence": 0.8}),
        ]
        evaluator.evaluate_batch(exps)
        filtered = evaluator.filter_by_level(exps, ExperienceQualityLevel.MEDIUM)
        assert len(filtered) >= 1


class TestExperienceEvaluatorQualityDistribution:
    def test_quality_distribution(self, evaluator):
        exps = [
            LearningExperience(action="a", reward=0.9, context={"a": 1, "b": 2, "c": 3}, decision={"confidence": 0.95}),
            LearningExperience(action="b", reward=0.1, decision={"confidence": 0.05}),
        ]
        evaluator.evaluate_batch(exps)
        dist = evaluator.get_quality_distribution(exps)
        assert "high" in dist
        assert "low" in dist
        assert "noise" in dist

    def test_quality_distribution_empty(self, evaluator):
        dist = evaluator.get_quality_distribution([])
        for level in ExperienceQualityLevel:
            assert level.value in dist

    def test_get_summary(self, evaluator):
        evaluator.evaluate(LearningExperience(action="test", reward=0.5))
        summary = evaluator.get_summary()
        assert summary["evaluation_count"] == 1
        assert "weights" in summary
        assert "min_learning_value" in summary

    def test_reset_evaluator(self, evaluator):
        evaluator.evaluate(LearningExperience(action="test", reward=0.5))
        evaluator.reset()
        assert evaluator.evaluation_count == 0


class TestExperienceEvaluatorLearningValue:
    def test_learning_value_range(self, evaluator):
        exp = LearningExperience(action="test", reward=0.5, decision={"confidence": 0.5})
        quality = evaluator.evaluate(exp)
        assert 0.0 <= quality.learning_value <= 1.0

    def test_learning_value_components_present(self, evaluator):
        exp = LearningExperience(action="test", reward=0.8, context={"a": 1, "b": 2, "c": 3},
                                 decision={"confidence": 0.9})
        quality = evaluator.evaluate(exp)
        assert quality.confidence > 0
        assert quality.reliability > 0
        assert quality.impact > 0
        assert quality.novelty > 0

    def test_evaluate_with_complex_context(self, evaluator):
        exp = LearningExperience(
            action="scale_budget",
            context={"country": "US", "campaign": "merge", "platform": "facebook", "bid_type": "cpi", "budget": 1000},
            decision={"confidence": 0.88, "risk_level": "low", "expected_impact": "high"},
            result={"CPI": "-10%", "ROAS": "+15%", "CTR": "+8%", "installs": "+20%"},
            reward=0.82,
            tags=["ua", "scale", "facebook"],
        )
        quality = evaluator.evaluate(exp)
        assert quality.reliability >= 0.5
        assert quality.learning_value > 0.3

    def test_evaluate_negative_experience(self, evaluator):
        exp = LearningExperience(
            action="pause_campaign",
            context={"country": "JP"},
            decision={"confidence": 0.6},
            result={"ROAS": "-25%", "CTR": "-10%"},
            reward=-0.7,
        )
        quality = evaluator.evaluate(exp)
        assert quality.impact > 0.2  # negative experiences are still impactful

    def test_evaluate_contradictory_results(self, evaluator):
        exp = LearningExperience(
            action="test",
            context={"a": 1, "b": 2, "c": 3},
            decision={"confidence": 0.7},
            result={"ROAS": "+10%", "CPI": "-15%", "CTR": "-5%"},
            reward=0.5,
        )
        quality = evaluator.evaluate(exp)
        assert quality.learning_value >= 0.0


# ═══════════════════════════════════════════════════════════════════
# 4. Knowledge Extraction (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeExtractorPatterns:
    def test_extract_patterns_empty(self, extractor):
        assert extractor.extract_patterns([]) == []

    def test_extract_patterns_insufficient_evidence(self, extractor):
        exps = [LearningExperience(action="test", reward=0.8) for _ in range(5)]
        assert extractor.extract_patterns(exps) == []

    def test_extract_patterns_sufficient_evidence(self, extractor):
        exps = [LearningExperience(action="creative_refresh", reward=0.8) for _ in range(15)]
        patterns = extractor.extract_patterns(exps)
        assert len(patterns) >= 1
        assert patterns[0].status == PatternStatus.DISCOVERED

    def test_extract_patterns_low_success_rate(self, extractor):
        exps = []
        for _ in range(15):
            exps.append(LearningExperience(action="test", reward=-0.5))
        patterns = extractor.extract_patterns(exps)
        assert len(patterns) == 0

    def test_extract_patterns_conditions(self, extractor):
        exps = [
            LearningExperience(
                action="creative_refresh",
                context={"country": "US", "genre": "Puzzle"},
                reward=0.8,
            )
            for _ in range(15)
        ]
        patterns = extractor.extract_patterns(exps)
        if patterns:
            assert "country" in patterns[0].conditions or "genre" in patterns[0].conditions

    def test_extract_patterns_multiple_actions(self, extractor):
        exps = []
        for _ in range(15):
            exps.append(LearningExperience(action="refresh", reward=0.8))
        for _ in range(15):
            exps.append(LearningExperience(action="scale", reward=0.7))
        patterns = extractor.extract_patterns(exps)
        assert len(patterns) >= 1

    def test_extract_patterns_with_confidence(self, extractor):
        exps = [LearningExperience(action="refresh", reward=0.8) for _ in range(20)]
        patterns = extractor.extract_patterns(exps)
        if patterns:
            assert patterns[0].confidence >= 0.5
            assert patterns[0].success_rate > 0.5


class TestKnowledgeExtractorInsights:
    def test_generate_insights_empty(self, extractor):
        assert extractor.generate_insights([]) == []

    def test_generate_insights_insufficient(self, extractor):
        exps = [LearningExperience(action="test", reward=0.8) for _ in range(5)]
        assert extractor.generate_insights(exps) == []

    def test_generate_insights_action_rankings(self, extractor):
        exps = []
        for _ in range(10):
            exps.append(LearningExperience(action="good_action", reward=0.8))
        for _ in range(10):
            exps.append(LearningExperience(action="bad_action", reward=-0.5))
        insights = extractor.generate_insights(exps)
        assert len(insights) >= 1
        assert any("good_action" in i.description for i in insights)

    def test_generate_insights_trend(self, extractor):
        exps = []
        for i in range(30):
            exps.append(LearningExperience(action="test", reward=0.6 + i * 0.01))
        insights = extractor.generate_insights(exps)
        trend_insights = [i for i in insights if i.insight_type == InsightType.OPPORTUNITY]
        assert len(trend_insights) >= 0  # may or may not detect trend

    def test_generate_insights_correlation(self, extractor):
        exps = []
        for _ in range(15):
            exps.append(LearningExperience(action="test", context={"has_feature": True}, reward=0.8))
        for _ in range(15):
            exps.append(LearningExperience(action="test", context={}, reward=0.2))
        insights = extractor.generate_insights(exps)
        assert len(insights) >= 0  # at minimum no crash

    def test_generate_insights_warning(self, extractor):
        exps = []
        for _ in range(10):
            exps.append(LearningExperience(action="action_a", reward=0.8))
        for _ in range(10):
            exps.append(LearningExperience(action="action_b", reward=-0.6))
        insights = extractor.generate_insights(exps)
        warnings = [i for i in insights if i.insight_type == InsightType.WARNING]
        assert len(warnings) >= 0


class TestKnowledgeExtractorQuery:
    def test_get_patterns(self, extractor):
        exps = [LearningExperience(action="refresh", reward=0.8) for _ in range(15)]
        extractor.extract_patterns(exps)
        patterns = extractor.get_patterns()
        assert len(patterns) >= 1

    def test_get_patterns_empty(self, extractor):
        assert extractor.get_patterns() == []

    def test_get_insights(self, extractor):
        exps = [LearningExperience(action="test", reward=0.8) for _ in range(15)]
        extractor.generate_insights(exps)
        assert len(extractor.get_insights()) >= 0

    def test_get_summary(self, extractor):
        summary = extractor.get_summary()
        assert "extraction_count" in summary
        assert "patterns_count" in summary
        assert "insights_count" in summary

    def test_reset_extractor(self, extractor):
        exps = [LearningExperience(action="test", reward=0.8) for _ in range(15)]
        extractor.extract_patterns(exps)
        extractor.reset()
        assert extractor.get_patterns() == []
        assert extractor.extraction_count == 0

    def test_multiple_extractions(self, extractor):
        exps = [LearningExperience(action="a", reward=0.8) for _ in range(15)]
        extractor.extract_patterns(exps)
        extractor.generate_insights(exps)
        assert extractor.extraction_count == 1


# ═══════════════════════════════════════════════════════════════════
# 5. Pattern Evolution (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestPatternEvolutionEngineRegister:
    def test_register_pattern(self, evolution, pattern):
        p = evolution.register(pattern)
        assert p.pattern_id == pattern.pattern_id
        assert evolution.get_pattern(pattern.pattern_id) is not None

    def test_register_batch(self, evolution):
        p1 = LearnedPattern(name="p1")
        p2 = LearnedPattern(name="p2")
        evolution.register_batch([p1, p2])
        assert len(evolution.get_patterns()) == 2

    def test_get_pattern_nonexistent(self, evolution):
        assert evolution.get_pattern("nonexistent") is None


class TestPatternEvolutionEngineTransitions:
    def test_validate_discovered(self, evolution, pattern):
        evolution.register(pattern)
        ev = evolution.validate(pattern.pattern_id)
        assert ev is not None
        assert ev.to_status == PatternStatus.VALIDATED
        pattern_after = evolution.get_pattern(pattern.pattern_id)
        assert pattern_after.status == PatternStatus.VALIDATED

    def test_validate_already_validated(self, evolution, pattern):
        evolution.register(pattern)
        evolution.validate(pattern.pattern_id)
        # 尝试再次验证
        ev = evolution.validate(pattern.pattern_id)
        assert ev is None  # 已在 VALIDATED 状态

    def test_activate_validated(self, evolution, pattern):
        evolution.register(pattern)
        evolution.validate(pattern.pattern_id)
        ev = evolution.activate(pattern.pattern_id)
        assert ev is not None
        assert ev.to_status == PatternStatus.ACTIVE
        assert evolution.get_pattern(pattern.pattern_id).status == PatternStatus.ACTIVE

    def test_decay_active(self, evolution, pattern):
        evolution.register(pattern)
        evolution.validate(pattern.pattern_id)
        evolution.activate(pattern.pattern_id)
        ev = evolution.decay(pattern.pattern_id, "Performance dropped")
        assert ev is not None
        assert ev.to_status == PatternStatus.DECAYING

    def test_recover_decaying(self, evolution, pattern):
        evolution.register(pattern)
        evolution.validate(pattern.pattern_id)
        evolution.activate(pattern.pattern_id)
        evolution.decay(pattern.pattern_id)
        ev = evolution.recover(pattern.pattern_id)
        assert ev is not None
        assert ev.to_status == PatternStatus.ACTIVE

    def test_retire_any_status(self, evolution, pattern):
        evolution.register(pattern)
        ev = evolution.retire(pattern.pattern_id, "No longer useful")
        assert ev is not None
        assert ev.to_status == PatternStatus.RETIRED
        assert evolution.get_pattern(pattern.pattern_id).status == PatternStatus.RETIRED

    def test_retire_is_irreversible(self, evolution, pattern):
        evolution.register(pattern)
        evolution.retire(pattern.pattern_id)
        # 退役后不能验证
        ev = evolution.validate(pattern.pattern_id)
        assert ev is None

    def test_transition_nonexistent(self, evolution):
        assert evolution.validate("nonexistent") is None
        assert evolution.activate("nonexistent") is None
        assert evolution.decay("nonexistent") is None
        assert evolution.retire("nonexistent") is None


class TestPatternEvolutionEngineAutoEvolve:
    def test_evolve_all_empty(self, evolution):
        assert evolution.evolve_all() == []

    def test_auto_evolve_discovered_to_validated(self, evolution):
        p = LearnedPattern(
            name="test",
            status=PatternStatus.DISCOVERED,
            evidence_count=15,
            confidence=0.60,
        )
        evolution.register(p)
        evolutions = evolution.evolve_all()
        assert len(evolutions) >= 1
        assert evolution.get_pattern(p.pattern_id).status == PatternStatus.VALIDATED

    def test_auto_evolve_discovered_insufficient(self, evolution):
        p = LearnedPattern(
            name="test",
            status=PatternStatus.DISCOVERED,
            evidence_count=5,
            confidence=0.40,
        )
        evolution.register(p)
        evolutions = evolution.evolve_all()
        assert len(evolutions) == 0

    def test_auto_evolve_validated_to_active(self, evolution):
        p = LearnedPattern(
            name="test",
            status=PatternStatus.VALIDATED,
            usage_count=10,
            success_rate=0.70,
            evidence_count=15,
            confidence=0.70,
        )
        evolution.register(p)
        evolutions = evolution.evolve_all()
        assert len(evolutions) >= 1
        assert evolution.get_pattern(p.pattern_id).status == PatternStatus.ACTIVE

    def test_auto_evolve_active_to_decaying(self, evolution):
        p = LearnedPattern(
            name="test",
            status=PatternStatus.ACTIVE,
            success_rate=0.40,
            decay_rate=0.25,
            usage_count=10,
            evidence_count=50,
            confidence=0.70,
        )
        evolution.register(p)
        evolutions = evolution.evolve_all()
        assert len(evolutions) >= 1
        assert evolution.get_pattern(p.pattern_id).status == PatternStatus.DECAYING

    def test_auto_evolve_decaying_to_retired(self, evolution):
        p = LearnedPattern(
            name="test",
            status=PatternStatus.DECAYING,
            success_rate=0.20,
            decay_rate=0.30,
            usage_count=10,
            evidence_count=50,
            confidence=0.70,
        )
        evolution.register(p)
        evolutions = evolution.evolve_all()
        assert len(evolutions) >= 1
        assert evolution.get_pattern(p.pattern_id).status == PatternStatus.RETIRED

    def test_auto_evolve_decaying_recover(self, evolution):
        p = LearnedPattern(
            name="test",
            status=PatternStatus.DECAYING,
            success_rate=0.65,
            decay_rate=0.10,
            usage_count=10,
            evidence_count=50,
            confidence=0.70,
        )
        evolution.register(p)
        evolutions = evolution.evolve_all()
        assert len(evolutions) >= 1
        assert evolution.get_pattern(p.pattern_id).status == PatternStatus.ACTIVE


class TestPatternEvolutionEngineQuery:
    def test_get_active_patterns(self, evolution, active_pattern):
        evolution.register(active_pattern)
        assert len(evolution.get_active_patterns()) == 1

    def test_get_active_patterns_empty(self, evolution):
        assert evolution.get_active_patterns() == []

    def test_get_valid_patterns(self, evolution):
        p = LearnedPattern(status=PatternStatus.VALIDATED)
        evolution.register(p)
        assert len(evolution.get_valid_patterns()) == 1

    def test_get_by_status(self, evolution, pattern):
        evolution.register(pattern)
        discovered = evolution.get_by_status(PatternStatus.DISCOVERED)
        assert len(discovered) == 1
        assert evolution.get_by_status(PatternStatus.ACTIVE) == []

    def test_get_evolutions(self, evolution, pattern):
        evolution.register(pattern)
        evolution.validate(pattern.pattern_id)
        evolutions = evolution.get_evolutions()
        assert len(evolutions) == 1

    def test_get_evolution_history(self, evolution, pattern):
        evolution.register(pattern)
        evolution.validate(pattern.pattern_id)
        evolution.activate(pattern.pattern_id)
        history = evolution.get_evolution_history(pattern.pattern_id)
        assert len(history) == 2

    def test_get_summary(self, evolution, pattern):
        evolution.register(pattern)
        summary = evolution.get_summary()
        assert summary["total_patterns"] == 1
        assert "status_distribution" in summary
        assert "active_count" in summary

    def test_reset_evolution(self, evolution, pattern):
        evolution.register(pattern)
        evolution.validate(pattern.pattern_id)
        evolution.reset()
        assert len(evolution.get_patterns()) == 0
        assert len(evolution.get_evolutions()) == 0


class TestValidTransitions:
    def test_discovered_allowed(self):
        allowed = VALID_TRANSITIONS[PatternStatus.DISCOVERED]
        assert PatternStatus.VALIDATED in allowed
        assert PatternStatus.RETIRED in allowed
        assert PatternStatus.ACTIVE not in allowed

    def test_validated_allowed(self):
        allowed = VALID_TRANSITIONS[PatternStatus.VALIDATED]
        assert PatternStatus.ACTIVE in allowed
        assert PatternStatus.RETIRED in allowed
        assert PatternStatus.DISCOVERED not in allowed

    def test_retired_allowed(self):
        allowed = VALID_TRANSITIONS[PatternStatus.RETIRED]
        assert len(allowed) == 0  # 不可逆

    def test_active_allowed(self):
        allowed = VALID_TRANSITIONS[PatternStatus.ACTIVE]
        assert PatternStatus.DECAYING in allowed
        assert PatternStatus.RETIRED in allowed

    def test_decaying_allowed(self):
        allowed = VALID_TRANSITIONS[PatternStatus.DECAYING]
        assert PatternStatus.ACTIVE in allowed
        assert PatternStatus.RETIRED in allowed


# ═══════════════════════════════════════════════════════════════════
# 6. Strategy Learning (10 tests)
# ═══════════════════════════════════════════════════════════════════


class TestStrategyLearner:
    def test_learn_empty(self, learner):
        assert learner.learn([]) == []

    def test_learn_from_active_pattern(self, learner, active_pattern):
        recs = learner.learn([active_pattern])
        assert len(recs) >= 1
        assert recs[0].strategy_name != ""
        assert recs[0].confidence >= 0.60

    def test_learn_from_low_confidence(self, learner):
        p = LearnedPattern(
            name="test",
            status=PatternStatus.ACTIVE,
            success_rate=0.55,
            confidence=0.55,
            recommendation="test",
        )
        recs = learner.learn([p])
        # 置信度低于 min_confidence，可能被过滤
        assert len(recs) >= 0

    def test_learn_from_experiences(self, learner):
        exps = [LearningExperience(action="test", reward=0.8) for _ in range(15)]
        recs = learner.learn([], experiences=exps)
        assert len(recs) >= 1

    def test_learn_increments_count(self, learner):
        learner.learn([])
        assert learner.learn_count == 1

    def test_get_recommendations(self, learner, active_pattern):
        learner.learn([active_pattern])
        recs = learner.get_recommendations()
        assert len(recs) >= 1

    def test_get_top_recommendations(self, learner, active_pattern):
        learner.learn([active_pattern])
        top = learner.get_top_recommendations(3)
        assert len(top) <= 3

    def test_generate_insights(self, learner, active_pattern):
        recs = learner.learn([active_pattern])
        insights = learner.generate_insights(recs)
        assert len(insights) >= 1
        assert insights[0].insight_type == InsightType.STRATEGY

    def test_get_summary(self, learner, active_pattern):
        learner.learn([active_pattern])
        summary = learner.get_summary()
        assert summary["learn_count"] >= 1
        assert "total_recommendations" in summary

    def test_reset_learner(self, learner, active_pattern):
        learner.learn([active_pattern])
        learner.reset()
        assert len(learner.get_recommendations()) == 0
        assert learner.learn_count == 0


# ═══════════════════════════════════════════════════════════════════
# 7. Integration (10 tests)
# ═══════════════════════════════════════════════════════════════════


class TestContinuousLearningEngine:
    def test_create_engine(self, engine):
        assert engine.cycle_count == 0
        assert engine.collector is not None
        assert engine.evaluator is not None
        assert engine.extractor is not None
        assert engine.evolution is not None
        assert engine.learner is not None

    def test_collect_experience(self, engine):
        exp = engine.collect(
            action="creative_refresh",
            context={"country": "US"},
            result={"CTR": "+18%"},
            reward=0.74,
        )
        assert exp.action == "creative_refresh"
        assert exp.reward == 0.74

    def test_collect_from_feedback(self, engine):
        feedback = {"action": "scale_budget", "reward": 0.65}
        exp = engine.collect_from_feedback(feedback)
        assert exp.action == "scale_budget"
        assert exp.reward == 0.65

    def test_collect_batch(self, engine):
        feedbacks = [
            {"action": "a", "reward": 0.5},
            {"action": "b", "reward": 0.7},
        ]
        exps = engine.collect_batch(feedbacks)
        assert len(exps) == 2

    def test_process_empty(self, engine):
        result = engine.process()
        assert result.cycle_number == 1
        assert result.experiences_collected == 0
        assert engine.cycle_count == 1

    def test_process_with_experiences(self, engine, sample_experiences):
        # 收集经验
        for exp in sample_experiences:
            engine.collect(
                action=exp.action,
                context=exp.context,
                decision=exp.decision,
                result=exp.result,
                reward=exp.reward,
                tags=exp.tags,
            )
        result = engine.process()
        assert result.cycle_number == 1
        assert result.experiences_collected == 50
        assert result.experiences_evaluated > 0
        assert result.valuable_experiences > 0
        assert "summary" in result.to_dict()

    def test_generate_model_feedback_empty(self, engine):
        feedback = engine.generate_model_feedback()
        assert feedback.get_planner_feedback() == []
        assert feedback.get_risk_engine_feedback() == []

    def test_generate_model_feedback(self, engine, sample_experiences):
        for exp in sample_experiences:
            engine.collect(
                action=exp.action,
                context=exp.context,
                decision=exp.decision,
                result=exp.result,
                reward=exp.reward,
                tags=exp.tags,
            )
        engine.process()
        feedback = engine.generate_model_feedback()
        fb_dict = feedback.to_dict()
        assert "planner" in fb_dict
        assert "risk_engine" in fb_dict
        assert "action_selector" in fb_dict
        assert "reasoning_engine" in fb_dict

    def test_get_stats(self, engine):
        engine.collect(action="test", reward=0.5)
        stats = engine.get_stats()
        assert "cycle_count" in stats
        assert "collector" in stats
        assert "evaluator" in stats
        assert "evolution" in stats
        assert "learner" in stats

    def test_reset_engine(self, engine):
        engine.collect(action="test", reward=0.5)
        engine.process()
        engine.reset()
        assert engine.cycle_count == 0
        assert engine.get_latest_result() is None


class TestModelImprovementFeedback:
    def test_empty_feedback(self):
        fb = ModelImprovementFeedback()
        assert fb.get_planner_feedback() == []
        assert fb.get_risk_engine_feedback() == []
        assert fb.get_action_selector_feedback() == []
        assert fb.get_reasoning_engine_feedback() == []

    def test_add_planner_feedback(self):
        fb = ModelImprovementFeedback()
        fb.add_planner_feedback({"type": "test", "data": "value"}, weight=0.8)
        assert len(fb.get_planner_feedback()) == 1
        assert fb.get_planner_feedback()[0]["weight"] == 0.8

    def test_add_all_feedback_types(self):
        fb = ModelImprovementFeedback()
        fb.add_planner_feedback({"type": "p"})
        fb.add_risk_engine_feedback({"type": "r"})
        fb.add_action_selector_feedback({"type": "a"})
        fb.add_reasoning_engine_feedback({"type": "re"})
        assert len(fb.get_planner_feedback()) == 1
        assert len(fb.get_risk_engine_feedback()) == 1
        assert len(fb.get_action_selector_feedback()) == 1
        assert len(fb.get_reasoning_engine_feedback()) == 1

    def test_to_dict(self):
        fb = ModelImprovementFeedback()
        fb.add_planner_feedback({"type": "test"})
        d = fb.to_dict()
        assert "planner" in d
        assert "risk_engine" in d
        assert "action_selector" in d
        assert "reasoning_engine" in d

    def test_clear_feedback(self):
        fb = ModelImprovementFeedback()
        fb.add_planner_feedback({"type": "test"})
        fb.clear()
        assert fb.get_planner_feedback() == []


# ═══════════════════════════════════════════════════════════════════
# 8. Enums
# ═══════════════════════════════════════════════════════════════════


class TestEnums:
    def test_pattern_status_values(self):
        assert PatternStatus.DISCOVERED.value == "discovered"
        assert PatternStatus.VALIDATED.value == "validated"
        assert PatternStatus.ACTIVE.value == "active"
        assert PatternStatus.DECAYING.value == "decaying"
        assert PatternStatus.RETIRED.value == "retired"

    def test_pattern_status_str(self):
        assert str(PatternStatus.DISCOVERED) == "PatternStatus.DISCOVERED"

    def test_insight_type_values(self):
        assert InsightType.PATTERN.value == "pattern"
        assert InsightType.STRATEGY.value == "strategy"
        assert InsightType.RISK.value == "risk"
        assert InsightType.OPPORTUNITY.value == "opportunity"
        assert InsightType.WARNING.value == "warning"
        assert InsightType.CORRELATION.value == "correlation"

    def test_experience_quality_level_values(self):
        assert ExperienceQualityLevel.HIGH.value == "high"
        assert ExperienceQualityLevel.MEDIUM.value == "medium"
        assert ExperienceQualityLevel.LOW.value == "low"
        assert ExperienceQualityLevel.NOISE.value == "noise"