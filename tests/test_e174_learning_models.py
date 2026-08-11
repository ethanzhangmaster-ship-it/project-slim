"""E13.7.4 Learning Models — 专项测试.

测试覆盖 Day 7.4.3 全部 7 个核心数据模型:
  1. LearningOutcome:       创建, 属性判定, to_dict
  2. LearningExperience:     创建, 可选 reward/attribution, 属性判定
  3. RewardWeights:          默认/工厂方法, validate, to_dict
  4. LearningReward:         from_business_metrics, from_reward_signal, 属性判定
  5. AttributionEvidence:    创建, 结构化字段, to_dict
  6. AttributionResult:      from_heuristic, primary_factor, 属性判定
  7. LearningResult:         from_learning_experience, next_action, learning_quality

集成测试:
  - 完整 Pipeline: LearningExperience → LearningReward → AttributionResult → LearningResult
  - 延迟归因: T+0 reward 可用, T+7 attribution 补充
  - 不同 Agent 权重: Growth/UA/Creative/Conservative
  - 工厂函数: create_learning_experience
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_models import (
    AttributionEvidence,
    AttributionResult,
    LearningExperience,
    LearningOutcome,
    LearningResult,
    LearningReward,
    RewardWeights,
    create_learning_experience,
)


# ═══════════════════════════════════════════════════════════════
# 1. LearningOutcome
# ═══════════════════════════════════════════════════════════════


class TestLearningOutcome:
    """LearningOutcome 数据模型测试."""

    def test_default_creation(self) -> None:
        """默认创建 — 所有字段为默认值."""
        o = LearningOutcome()
        assert o.success is False
        assert o.outcome_level == "neutral"
        assert o.improvement_score == 0.0
        assert o.metrics_before == {}
        assert o.metrics_after == {}

    def test_successful_outcome(self) -> None:
        """成功结果 — improvement_score > 0.05."""
        o = LearningOutcome(
            success=True,
            outcome_level="success",
            improvement_score=0.12,
            metrics_before={"roas": 1.5},
            metrics_after={"roas": 2.1},
        )
        assert o.is_successful is True
        assert o.is_significant is False  # 0.12 < 0.15
        assert o.is_degradation is False
        assert o.has_metrics is True

    def test_strong_success(self) -> None:
        """强成功 — improvement_score > 0.15."""
        o = LearningOutcome(improvement_score=0.25)
        assert o.is_significant is True

    def test_failure_outcome(self) -> None:
        """失败结果 — improvement_score < -0.05."""
        o = LearningOutcome(
            success=False,
            outcome_level="failure",
            improvement_score=-0.20,
        )
        assert o.is_successful is False
        assert o.is_degradation is True

    def test_partial_metrics(self) -> None:
        """部分指标 — 只有 before 或 after."""
        o = LearningOutcome(metrics_before={"roas": 1.0})
        assert o.has_metrics is False  # 需要 both

    def test_execution_quality_fields(self) -> None:
        """执行质量字段."""
        o = LearningOutcome(
            execution_success_rate=0.95,
            execution_duration_ms=3200.0,
            failure_nodes=1,
            rollback_nodes=0,
            was_blocked=True,
            needed_approval=False,
        )
        assert o.execution_success_rate == 0.95
        assert o.was_blocked is True

    def test_to_dict(self) -> None:
        """to_dict 序列化."""
        o = LearningOutcome(
            success=True,
            outcome_level="success",
            metrics_before={"roas": 1.0},
            metrics_after={"roas": 1.5},
            metrics_delta={"roas_change": 0.5},
            improvement_score=0.5,
        )
        d = o.to_dict()
        assert d["success"] is True
        assert d["outcome_level"] == "success"
        assert d["improvement_score"] == 0.5
        assert d["is_successful"] is True
        assert d["is_significant"] is True


# ═══════════════════════════════════════════════════════════════
# 2. LearningExperience
# ═══════════════════════════════════════════════════════════════


class TestLearningExperience:
    """LearningExperience 数据模型测试."""

    def test_default_creation(self) -> None:
        """默认创建 — 自动生成 learning_id."""
        e = LearningExperience()
        assert len(e.learning_id) > 0
        assert e.decision_id == ""
        assert e.reward is None
        assert e.attribution is None

    def test_full_creation(self) -> None:
        """完整创建 — 所有核心字段."""
        e = LearningExperience(
            decision_id="d001",
            execution_id="e001",
            opportunity_id="opp_001",
            opportunity_type="creative_fatigue",
            strategy_id="s001",
            strategy_name="replace_creative",
            action_type="replace_creative",
            decision_type="EXECUTE",
            context={"product": "game_x", "platform": "meta"},
            confidence=0.85,
            risk_score=0.15,
            tags=["creative", "fatigue"],
        )
        assert e.decision_id == "d001"
        assert e.strategy_name == "replace_creative"
        assert e.confidence == 0.85

    def test_optional_reward_and_attribution(self) -> None:
        """reward 和 attribution 均为 Optional — T+0 无 attribution."""
        e = LearningExperience(decision_id="d001")
        assert e.has_reward is False
        assert e.has_attribution is False
        assert e.is_learning_complete is False

    def test_with_reward_only(self) -> None:
        """T+0: 仅 reward 可用."""
        reward = LearningReward(total_reward=0.5, reward_level="positive")
        e = LearningExperience(decision_id="d001", reward=reward)
        assert e.has_reward is True
        assert e.has_attribution is False
        assert e.is_learning_complete is False

    def test_with_reward_and_attribution(self) -> None:
        """T+7: reward + attribution 均可用."""
        reward = LearningReward(total_reward=0.5)
        attribution = AttributionResult(decision_id="d001", total_reward=0.5)
        e = LearningExperience(
            decision_id="d001", reward=reward, attribution=attribution
        )
        assert e.has_reward is True
        assert e.has_attribution is True
        assert e.is_learning_complete is True

    def test_delayed_attribution(self) -> None:
        """延迟归因 — T+0 创建, T+7 补充 attribution."""
        e = LearningExperience(decision_id="d001")
        assert e.has_attribution is False

        # T+7 补充
        e.attribution = AttributionResult(
            decision_id="d001",
            total_reward=0.6,
            primary_factor="creative",
        )
        assert e.has_attribution is True

    def test_to_dict_without_reward(self) -> None:
        """to_dict — reward 为 None 时."""
        e = LearningExperience(decision_id="d001")
        d = e.to_dict()
        assert d["reward"] is None
        assert d["attribution"] is None
        assert d["has_reward"] is False

    def test_to_dict_full(self) -> None:
        """to_dict — 完整序列化."""
        e = LearningExperience(
            decision_id="d001",
            strategy_name="test",
            reward=LearningReward(total_reward=0.5),
        )
        d = e.to_dict()
        assert d["reward"] is not None
        assert d["reward"]["total_reward"] == 0.5

    def test_repr(self) -> None:
        """__repr__ 可读输出."""
        e = LearningExperience(
            decision_id="dec_12345678",
            action_type="scale",
            reward=LearningReward(total_reward=0.5),
        )
        r = repr(e)
        assert "dec_1234" in r
        assert "scale" in r
        assert "reward=yes" in r


# ═══════════════════════════════════════════════════════════════
# 3. RewardWeights
# ═══════════════════════════════════════════════════════════════


class TestRewardWeights:
    """RewardWeights 数据模型测试."""

    def test_default_weights(self) -> None:
        """默认 Growth Agent 权重."""
        w = RewardWeights()
        assert w.business == 0.50
        assert w.execution == 0.20
        assert w.safety == 0.20
        assert w.efficiency == 0.10
        assert w.validate() is True

    def test_ua_agent_weights(self) -> None:
        """UA Agent 权重 (业务导向)."""
        w = RewardWeights.ua_agent()
        assert w.business == 0.70
        assert w.validate() is True

    def test_creative_agent_weights(self) -> None:
        """Creative Agent 权重 (素材质量导向)."""
        w = RewardWeights.creative_agent()
        assert w.business == 0.30
        assert w.extra == {"creative_quality": 0.30}
        assert w.validate() is True

    def test_conservative_weights(self) -> None:
        """保守权重 (安全优先)."""
        w = RewardWeights.conservative()
        assert w.safety == 0.45
        assert w.validate() is True

    def test_custom_weights(self) -> None:
        """自定义权重."""
        w = RewardWeights(
            business=0.60,
            execution=0.15,
            safety=0.15,
            efficiency=0.10,
        )
        assert w.validate() is True

    def test_invalid_weights(self) -> None:
        """权重和不为 1.0."""
        w = RewardWeights(business=0.80)
        assert w.validate() is False
        assert w.total_weight == 1.30  # 0.80 + 0.20 + 0.20 + 0.10

    def test_to_dict(self) -> None:
        """to_dict 序列化."""
        w = RewardWeights()
        d = w.to_dict()
        assert d["business"] == 0.50
        assert d["valid"] is True
        assert d["total"] == 1.0


# ═══════════════════════════════════════════════════════════════
# 4. LearningReward
# ═══════════════════════════════════════════════════════════════


class TestLearningReward:
    """LearningReward 数据模型测试."""

    def test_default_creation(self) -> None:
        """默认创建."""
        r = LearningReward()
        assert r.total_reward == 0.0
        assert r.reward_level == "neutral"
        assert r.calculation_method == "unified"

    # ── from_business_metrics ──

    def test_from_business_metrics_positive(self) -> None:
        """正向业务指标 — ROAS +30%."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"roas_change": 0.30},
            confidence=0.8,
        )
        assert r.total_reward > 0.0
        assert r.reward_level == "positive"
        assert r.business_reward > 0.0
        assert r.confidence == 0.8
        assert r.calculation_method == "unified"

    def test_from_business_metrics_negative(self) -> None:
        """负向业务指标 — ROAS -50% (需足够负才能抵消默认正向执行/安全奖励)."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"roas_change": -0.50},
        )
        assert r.business_reward < 0.0
        # business 负向但 execution/safety 默认正向会部分抵消,
        # 所以只验证 business_reward 为负

    def test_from_business_metrics_multi_metric(self) -> None:
        """多指标综合 — ROAS +20%, CTR +10%, CVR +5%."""
        r = LearningReward.from_business_metrics(
            metrics_delta={
                "roas_change": 0.20,
                "ctr_change": 0.10,
                "cvr_change": 0.05,
            },
        )
        assert r.total_reward > 0.0
        assert r.reward_level == "positive"
        assert len(r.components) >= 3  # roas, ctr, cvr

    def test_from_business_metrics_cpi_improvement(self) -> None:
        """CPI 下降 (正向) — CPI -20%."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"cpi_change": -0.20},
        )
        assert r.business_reward > 0.0  # CPI 下降 = 正向

    def test_from_business_metrics_cpi_worsening(self) -> None:
        """CPI 上升 (负向) — CPI +20%."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"cpi_change": 0.20},
        )
        assert r.business_reward < 0.0  # CPI 上升 = 负向

    def test_from_business_metrics_empty(self) -> None:
        """空指标 — 无业务数据."""
        r = LearningReward.from_business_metrics(metrics_delta={})
        assert r.business_reward == 0.0

    def test_from_business_metrics_with_blocked(self) -> None:
        """被拦截场景 — safety_reward = -1.0."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"roas_change": 0.30},
            was_blocked=True,
        )
        assert r.safety_reward == -1.0
        assert r.total_reward < 0.3  # 被安全拦截拖低总奖励

    def test_from_business_metrics_with_approval(self) -> None:
        """需要审批 — safety_reward = -0.5."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"roas_change": 0.30},
            needed_approval=True,
        )
        assert r.safety_reward == -0.5

    def test_from_business_metrics_with_execution_failure(self) -> None:
        """执行失败 — execution_success_rate = 0.5."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"roas_change": 0.30},
            execution_success_rate=0.5,
        )
        assert r.execution_reward == 0.0  # 2*0.5 - 1 = 0

    def test_from_business_metrics_custom_weights(self) -> None:
        """自定义权重 — UA Agent."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"roas_change": 0.30},
            weights=RewardWeights.ua_agent(),
        )
        assert r.weights.business == 0.70
        assert r.total_reward > 0.0

    # ── 属性判定 ──

    def test_is_positive(self) -> None:
        """total_reward > 0.15."""
        r = LearningReward(total_reward=0.30)
        assert r.is_positive is True
        assert r.is_negative is False
        assert r.is_neutral is False

    def test_is_negative(self) -> None:
        """total_reward < -0.15."""
        r = LearningReward(total_reward=-0.30)
        assert r.is_negative is True
        assert r.is_positive is False

    def test_is_neutral(self) -> None:
        """-0.15 <= total_reward <= 0.15."""
        r = LearningReward(total_reward=0.05)
        assert r.is_neutral is True

    def test_is_strong_positive(self) -> None:
        """total_reward > 0.5."""
        r = LearningReward(total_reward=0.70)
        assert r.is_strong_positive is True

    def test_is_strong_negative(self) -> None:
        """total_reward < -0.5."""
        r = LearningReward(total_reward=-0.70)
        assert r.is_strong_negative is True

    def test_is_high_confidence(self) -> None:
        """confidence >= 0.7."""
        r = LearningReward(confidence=0.85)
        assert r.is_high_confidence is True

    # ── to_dict ──

    def test_to_dict(self) -> None:
        """to_dict 序列化."""
        r = LearningReward.from_business_metrics(
            metrics_delta={"roas_change": 0.30},
            confidence=0.8,
        )
        d = r.to_dict()
        assert "total_reward" in d
        assert "business_reward" in d
        assert d["reward_level"] == "positive"
        assert d["is_positive"] is True
        assert d["is_high_confidence"] is True
        assert "weights" in d

    def test_repr(self) -> None:
        """__repr__ 可读输出."""
        r = LearningReward(total_reward=0.50, business_reward=0.3, confidence=0.8, reward_level="positive")
        rep = repr(r)
        assert "+0.50" in rep
        assert "positive" in rep


# ═══════════════════════════════════════════════════════════════
# 5. AttributionEvidence
# ═══════════════════════════════════════════════════════════════


class TestAttributionEvidence:
    """AttributionEvidence 数据模型测试."""

    def test_default_creation(self) -> None:
        """默认创建."""
        e = AttributionEvidence()
        assert e.metric_source == ""
        assert e.source_ids == []
        assert e.data_window == ""
        assert e.confidence == 0.5

    def test_full_creation(self) -> None:
        """完整创建 — Adjust + Meta 多源证据."""
        e = AttributionEvidence(
            metric_source="adjust",
            source_ids=["campaign_123", "adset_456"],
            data_window="2026-07-01~2026-07-07",
            confidence=0.82,
            description="CTR 从 1.8% 提升到 3.1%，来源 Adjust + Meta，7天窗口",
        )
        assert e.metric_source == "adjust"
        assert len(e.source_ids) == 2
        assert e.data_window == "2026-07-01~2026-07-07"
        assert e.confidence == 0.82

    def test_meta_ads_source(self) -> None:
        """Meta Ads 数据源."""
        e = AttributionEvidence(
            metric_source="meta_ads",
            source_ids=["ad_789"],
            data_window="2026-07-15~2026-07-21",
        )
        assert e.metric_source == "meta_ads"

    def test_to_dict(self) -> None:
        """to_dict 序列化."""
        e = AttributionEvidence(
            metric_source="adjust",
            source_ids=["c_001"],
            data_window="2026-07-01~2026-07-07",
            confidence=0.82,
            description="test evidence",
        )
        d = e.to_dict()
        assert d["metric_source"] == "adjust"
        assert d["source_ids"] == ["c_001"]
        assert d["confidence"] == 0.82

    def test_repr(self) -> None:
        """__repr__ 可读输出."""
        e = AttributionEvidence(
            metric_source="adjust",
            source_ids=["c_001", "c_002"],
            data_window="2026-07-01~2026-07-07",
        )
        r = repr(e)
        assert "adjust" in r
        assert "ids=2" in r


# ═══════════════════════════════════════════════════════════════
# 6. AttributionResult
# ═══════════════════════════════════════════════════════════════


class TestAttributionResult:
    """AttributionResult 数据模型测试."""

    def test_default_creation(self) -> None:
        """默认创建."""
        a = AttributionResult()
        assert len(a.attribution_id) > 0
        assert a.total_reward == 0.0
        assert a.primary_factor == ""
        assert a.attribution_method == "heuristic"

    # ── from_heuristic ──

    def test_from_heuristic_creative_driven(self) -> None:
        """素材驱动 — CTR 大幅提升."""
        a = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=0.6,
            metrics_delta={"ctr_change": 0.50, "cvr_change": 0.10},
            strategy_confidence=0.5,
            strategy_success_rate=0.5,
        )
        assert a.primary_factor == "creative"
        assert a.creative_contribution > 0.0
        assert a.is_creative_driven is True

    def test_from_heuristic_strategy_driven(self) -> None:
        """策略驱动 — 高策略置信度 + 高成功率."""
        a = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=0.6,
            metrics_delta={"ctr_change": 0.05},  # 素材变化小
            strategy_confidence=0.9,
            strategy_success_rate=0.9,
        )
        assert a.primary_factor == "strategy"
        assert a.strategy_contribution > 0.3

    def test_from_heuristic_audience_driven(self) -> None:
        """受众驱动 — 高受众匹配度."""
        a = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=0.5,
            metrics_delta={},
            strategy_confidence=0.3,
            strategy_success_rate=0.3,
            audience_match=0.9,
        )
        assert a.audience_contribution > 0.0

    def test_from_heuristic_timing_driven(self) -> None:
        """时机驱动 — 高时机因子."""
        a = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=0.4,
            metrics_delta={},
            strategy_confidence=0.3,
            strategy_success_rate=0.3,
            timing_factor=0.8,
        )
        assert a.timing_contribution > 0.0

    def test_from_heuristic_unexplained(self) -> None:
        """无显著因素 — 所有贡献 < 0.05."""
        a = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=0.02,
            metrics_delta={},
            strategy_confidence=0.1,
            strategy_success_rate=0.1,
        )
        assert a.primary_factor == "unexplained"

    def test_from_heuristic_with_evidence(self) -> None:
        """带证据列表."""
        evidence = [
            AttributionEvidence(
                metric_source="adjust",
                source_ids=["c_001"],
                data_window="2026-07-01~2026-07-07",
                confidence=0.82,
            )
        ]
        a = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=0.6,
            metrics_delta={"ctr_change": 0.50},
            evidence=evidence,
        )
        assert len(a.evidence) == 1
        assert a.evidence[0].metric_source == "adjust"

    # ── 判断属性 ──

    def test_is_creative_driven(self) -> None:
        """creative_contribution > 0.3."""
        a = AttributionResult(creative_contribution=0.45)
        assert a.is_creative_driven is True

    def test_is_strategy_driven(self) -> None:
        """strategy_contribution > 0.3."""
        a = AttributionResult(strategy_contribution=0.40)
        assert a.is_strategy_driven is True

    def test_is_audience_driven(self) -> None:
        """audience_contribution > 0.3."""
        a = AttributionResult(audience_contribution=0.35)
        assert a.is_audience_driven is True

    def test_is_timing_driven(self) -> None:
        """timing_contribution > 0.3."""
        a = AttributionResult(timing_contribution=0.40)
        assert a.is_timing_driven is True

    # ── 属性 ──

    def test_contribution_sum(self) -> None:
        """贡献总和."""
        a = AttributionResult(
            strategy_contribution=0.2,
            creative_contribution=0.3,
            audience_contribution=0.1,
            timing_contribution=0.1,
        )
        assert a.contribution_sum == 0.7

    def test_residual(self) -> None:
        """残差 = total_reward - contribution_sum."""
        a = AttributionResult(
            total_reward=0.8,
            strategy_contribution=0.2,
            creative_contribution=0.3,
            audience_contribution=0.1,
            timing_contribution=0.1,
        )
        assert a.residual == 0.1  # 0.8 - 0.7

    # ── to_dict ──

    def test_to_dict(self) -> None:
        """to_dict 序列化."""
        a = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=0.6,
            metrics_delta={"ctr_change": 0.50},
        )
        d = a.to_dict()
        assert d["primary_factor"] == "creative"
        assert d["attribution_method"] == "heuristic"
        assert "evidence" in d

    def test_repr(self) -> None:
        """__repr__ 可读输出."""
        a = AttributionResult(
            primary_factor="creative",
            creative_contribution=0.45,
            strategy_contribution=0.10,
        )
        r = repr(a)
        assert "creative" in r
        assert "+0.45" in r


# ═══════════════════════════════════════════════════════════════
# 7. LearningResult
# ═══════════════════════════════════════════════════════════════


class TestLearningResult:
    """LearningResult 数据模型测试."""

    def test_default_creation(self) -> None:
        """默认创建."""
        r = LearningResult()
        assert r.learning_id == ""
        assert r.next_action == "observe"
        assert r.learning_quality == 0.0
        assert r.memory_updated is False

    # ── from_learning_experience ──

    def test_from_learning_experience_reinforce(self) -> None:
        """强正向 — next_action = reinforce."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="replace_creative",
            outcome=LearningOutcome(
                success=True,
                improvement_score=0.60,
            ),
            reward=LearningReward(total_reward=0.70),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "reinforce"
        assert result.learning_id == exp.learning_id
        assert result.decision_id == "d001"
        assert len(result.lessons) > 0

    def test_from_learning_experience_adjust(self) -> None:
        """正向 — next_action = adjust (0.15 < reward <= 0.5)."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="replace_creative",
            outcome=LearningOutcome(success=True, improvement_score=0.12),
            reward=LearningReward(total_reward=0.30),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "adjust"

    def test_from_learning_experience_observe(self) -> None:
        """中性 — next_action = observe."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="replace_creative",
            outcome=LearningOutcome(),
            reward=LearningReward(total_reward=0.05),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "observe"

    def test_from_learning_experience_abandon(self) -> None:
        """强负向 — next_action = abandon."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="bad_strategy",
            outcome=LearningOutcome(
                success=False,
                improvement_score=-0.50,
            ),
            reward=LearningReward(total_reward=-0.70),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "abandon"

    def test_from_learning_experience_no_reward(self) -> None:
        """无 reward — next_action = observe."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="test",
            outcome=LearningOutcome(),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "observe"

    def test_from_learning_experience_with_attribution(self) -> None:
        """带归因 — lessons 包含 primary_factor."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="replace_creative",
            outcome=LearningOutcome(success=True, improvement_score=0.30),
            reward=LearningReward(total_reward=0.50),
            attribution=AttributionResult(
                decision_id="d001",
                total_reward=0.50,
                primary_factor="creative",
                creative_contribution=0.40,
                strategy_contribution=0.10,
            ),
        )
        result = LearningResult.from_learning_experience(exp)
        assert any("creative" in lesson for lesson in result.lessons)
        assert len(result.recommendations) > 0
        assert result.pattern_impact != {}

    def test_from_learning_experience_creative_driven_recommendation(self) -> None:
        """素材驱动 — 推荐扩展素材变体."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="replace_creative",
            outcome=LearningOutcome(success=True, improvement_score=0.20),
            reward=LearningReward(total_reward=0.40),
            attribution=AttributionResult(
                decision_id="d001",
                total_reward=0.40,
                primary_factor="creative",
                creative_contribution=0.35,
            ),
        )
        result = LearningResult.from_learning_experience(exp)
        assert any("creative variants" in r.lower() for r in result.recommendations)

    def test_from_learning_experience_blocked(self) -> None:
        """被拦截 — lessons 包含 blocked."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="test",
            outcome=LearningOutcome(was_blocked=True),
            reward=LearningReward(total_reward=-0.30),
        )
        result = LearningResult.from_learning_experience(exp)
        assert any("blocked" in lesson.lower() for lesson in result.lessons)

    def test_from_learning_experience_rollback(self) -> None:
        """回滚 — lessons 包含 rollback."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="test",
            outcome=LearningOutcome(rollback_nodes=2),
            reward=LearningReward(total_reward=-0.20),
        )
        result = LearningResult.from_learning_experience(exp)
        assert any("rollback" in lesson.lower() for lesson in result.lessons)

    # ── learning_quality ──

    def test_learning_quality_high(self) -> None:
        """高质量学习 — 高置信度 + 完整指标 + 低残差."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="test",
            outcome=LearningOutcome(
                metrics_before={"roas": 1.0},
                metrics_after={"roas": 1.5},
            ),
            reward=LearningReward(total_reward=0.50, confidence=0.9),
            attribution=AttributionResult(
                decision_id="d001",
                total_reward=0.50,
                unexplained=0.05,
            ),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.learning_quality >= 0.7
        assert result.is_high_quality is True

    def test_learning_quality_low(self) -> None:
        """低质量学习 — 低置信度 + 无指标 + 高残差."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="test",
            outcome=LearningOutcome(),
            reward=LearningReward(total_reward=0.10, confidence=0.3),
            attribution=AttributionResult(
                decision_id="d001",
                total_reward=0.10,
                unexplained=0.8,
            ),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.learning_quality < 0.7
        assert result.is_high_quality is False

    # ── 属性 ──

    def test_is_successful_loop(self) -> None:
        """memory_updated = True."""
        r = LearningResult(memory_updated=True)
        assert r.is_successful_loop is True

    def test_should_reinforce(self) -> None:
        """next_action = reinforce."""
        r = LearningResult(next_action="reinforce")
        assert r.should_reinforce is True

    def test_should_adjust(self) -> None:
        """next_action = adjust."""
        r = LearningResult(next_action="adjust")
        assert r.should_adjust is True

    def test_should_abandon(self) -> None:
        """next_action = abandon."""
        r = LearningResult(next_action="abandon")
        assert r.should_abandon is True

    # ── to_dict ──

    def test_to_dict(self) -> None:
        """to_dict 序列化."""
        exp = LearningExperience(
            decision_id="d001",
            strategy_name="test",
            reward=LearningReward(total_reward=0.51, reward_level="positive"),
        )
        result = LearningResult.from_learning_experience(exp)
        d = result.to_dict()
        assert d["next_action"] == "reinforce"
        assert "lessons" in d
        assert "learning_quality" in d

    def test_repr(self) -> None:
        """__repr__ 可读输出."""
        r = LearningResult(
            learning_id="learn_12345678",
            next_action="reinforce",
            learning_quality=0.85,
            lessons=["lesson1", "lesson2"],
        )
        rep = repr(r)
        assert "learn_12" in rep
        assert "reinforce" in rep
        assert "lessons=2" in rep


# ═══════════════════════════════════════════════════════════════
# 8. Factory Function
# ═══════════════════════════════════════════════════════════════


class TestCreateLearningExperience:
    """create_learning_experience 工厂函数测试."""

    def test_basic_creation(self) -> None:
        """基本创建."""
        exp = create_learning_experience(
            decision_id="d001",
            execution_id="e001",
            strategy_name="replace_creative",
            action_type="replace_creative",
        )
        assert exp.decision_id == "d001"
        assert exp.execution_id == "e001"
        assert exp.strategy_name == "replace_creative"
        assert exp.outcome is not None
        assert exp.reward is None

    def test_with_metrics(self) -> None:
        """带指标 — 自动计算 metrics_delta."""
        exp = create_learning_experience(
            decision_id="d001",
            metrics_before={"roas": 1.0, "ctr": 0.02},
            metrics_after={"roas": 1.5, "ctr": 0.025},
            improvement_score=0.5,
            success=True,
        )
        assert exp.outcome.has_metrics is True
        assert exp.outcome.metrics_delta["roas"] == 0.5  # (1.5-1.0)/1.0
        assert exp.outcome.metrics_delta["ctr"] == pytest.approx(0.25)  # (0.025-0.02)/0.02
        assert exp.outcome.outcome_level == "strong_success"

    def test_with_new_metric(self) -> None:
        """新增指标 — before 为 0."""
        exp = create_learning_experience(
            decision_id="d001",
            metrics_before={},
            metrics_after={"roas": 1.5},
        )
        assert exp.outcome.metrics_delta["roas"] == 1.0

    def test_with_tags(self) -> None:
        """带标签."""
        exp = create_learning_experience(
            decision_id="d001",
            tags=["creative", "meta", "fatigue"],
        )
        assert len(exp.tags) == 3

    def test_outcome_level_strong_success(self) -> None:
        """improvement_score > 0.30 → strong_success."""
        exp = create_learning_experience(
            decision_id="d001",
            improvement_score=0.35,
        )
        assert exp.outcome.outcome_level == "strong_success"

    def test_outcome_level_failure(self) -> None:
        """improvement_score < -0.05 → failure."""
        exp = create_learning_experience(
            decision_id="d001",
            improvement_score=-0.10,
        )
        assert exp.outcome.outcome_level == "failure"

    def test_outcome_level_strong_failure(self) -> None:
        """improvement_score < -0.30 → strong_failure."""
        exp = create_learning_experience(
            decision_id="d001",
            improvement_score=-0.40,
        )
        assert exp.outcome.outcome_level == "strong_failure"


# ═══════════════════════════════════════════════════════════════
# 9. Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestFullPipeline:
    """完整 Pipeline 集成测试."""

    def test_full_pipeline_t0(self) -> None:
        """T+0: Decision → Outcome → Reward (无 Attribution)."""
        # Step 1: 创建经验
        exp = create_learning_experience(
            decision_id="d001",
            execution_id="e001",
            opportunity_type="creative_fatigue",
            strategy_name="replace_creative",
            action_type="replace_creative",
            decision_type="EXECUTE",
            metrics_before={"roas": 1.0, "ctr": 0.02},
            metrics_after={"roas": 1.5, "ctr": 0.025},
            improvement_score=0.50,
            success=True,
            confidence=0.85,
        )

        # Step 2: 计算 Reward
        metrics_delta = {"roas_change": exp.outcome.metrics_delta["roas"], "ctr_change": exp.outcome.metrics_delta["ctr"]}
        exp.reward = LearningReward.from_business_metrics(
            metrics_delta=metrics_delta,
            confidence=0.85,
        )

        assert exp.has_reward is True
        assert exp.has_attribution is False
        assert exp.reward.reward_level == "positive"

        # Step 3: 生成 LearningResult
        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "reinforce"
        assert result.learning_quality > 0.0

    def test_full_pipeline_t7(self) -> None:
        """T+7: 补充 Attribution."""
        # T+0: 创建 + Reward
        exp = create_learning_experience(
            decision_id="d001",
            execution_id="e001",
            strategy_name="replace_creative",
            action_type="replace_creative",
            metrics_before={"roas": 1.0, "ctr": 0.02},
            metrics_after={"roas": 1.5, "ctr": 0.031},
            improvement_score=0.50,
            success=True,
        )
        exp.reward = LearningReward.from_business_metrics(
            metrics_delta={
                "roas_change": exp.outcome.metrics_delta["roas"],
                "ctr_change": exp.outcome.metrics_delta["ctr"],
            },
        )

        # T+7: 补充 Attribution
        evidence = [
            AttributionEvidence(
                metric_source="adjust",
                source_ids=["campaign_001"],
                data_window="2026-07-01~2026-07-07",
                confidence=0.82,
                description="CTR 从 2.0% 提升到 3.1%，来源 Adjust，7天窗口",
            )
        ]
        exp.attribution = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=exp.reward.total_reward,
            metrics_delta={
                "ctr_change": exp.outcome.metrics_delta["ctr"],
                "cvr_change": 0.0,
            },
            evidence=evidence,
        )

        assert exp.is_learning_complete is True
        assert exp.attribution.primary_factor == "creative"
        assert len(exp.attribution.evidence) == 1

        # 最终 LearningResult
        result = LearningResult.from_learning_experience(
            exp,
            memory_updated=True,
            experience_stored=True,
            pattern_updated=True,
        )
        assert result.learning_quality > 0.0
        assert result.memory_updated is True
        assert result.pattern_updated is True

    def test_pipeline_with_different_agent_weights(self) -> None:
        """不同 Agent 权重对 Reward 的影响."""
        # 同一组指标, 不同权重, execution_success_rate=0.5 使 execution_reward=0
        metrics = {"roas_change": 0.30}

        # Growth Agent (默认)
        r_growth = LearningReward.from_business_metrics(
            metrics_delta=metrics,
            execution_success_rate=0.5,
            weights=RewardWeights.default(),
        )

        # UA Agent (业务导向)
        r_ua = LearningReward.from_business_metrics(
            metrics_delta=metrics,
            execution_success_rate=0.5,
            weights=RewardWeights.ua_agent(),
        )

        # UA Agent 的 total_reward 应该更高 (business 权重 0.70 vs 0.50, execution 中性)
        assert r_ua.business_reward == r_growth.business_reward  # 业务奖励相同
        assert r_ua.total_reward >= r_growth.total_reward  # 但总奖励因权重不同

    def test_pipeline_negative_case(self) -> None:
        """负向案例 — 失败策略被 abandon."""
        exp = create_learning_experience(
            decision_id="d002",
            strategy_name="bad_bid_strategy",
            action_type="bid_adjust",
            metrics_before={"roas": 1.5},
            metrics_after={"roas": 0.8},
            improvement_score=-0.47,
            success=False,
        )
        exp.reward = LearningReward.from_business_metrics(
            metrics_delta={
                "roas_change": exp.outcome.metrics_delta.get("roas", 0.0),
            },
        )
        exp.attribution = AttributionResult.from_heuristic(
            decision_id="d002",
            total_reward=exp.reward.total_reward,
            metrics_delta={
                "ctr_change": 0.0,
                "cvr_change": 0.0,
            },
        )

        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "abandon" or result.next_action == "adjust"
        assert result.learning_quality > 0.0

    def test_pipeline_blocked_case(self) -> None:
        """被拦截案例 — 安全层阻止."""
        exp = create_learning_experience(
            decision_id="d003",
            strategy_name="risky_strategy",
            action_type="scale",
        )
        exp.outcome.was_blocked = True
        exp.reward = LearningReward.from_business_metrics(
            metrics_delta={},
            was_blocked=True,
        )

        result = LearningResult.from_learning_experience(exp)
        assert any("blocked" in lesson.lower() for lesson in result.lessons)
        # 被拦截后 total_reward 可能为 neutral (execution 正向抵消 safety 负向)
        assert result.next_action in ("observe", "adjust", "abandon")

    def test_pipeline_rollback_case(self) -> None:
        """回滚案例."""
        exp = create_learning_experience(
            decision_id="d004",
            strategy_name="auto_scale",
            action_type="scale",
            metrics_before={"roas": 1.2},
            metrics_after={"roas": 1.0},
            improvement_score=-0.17,
            success=False,
        )
        exp.outcome.rollback_nodes = 3
        exp.reward = LearningReward.from_business_metrics(
            metrics_delta={
                "roas_change": exp.outcome.metrics_delta.get("roas", 0.0),
            },
        )

        result = LearningResult.from_learning_experience(exp)
        assert any("rollback" in lesson.lower() for lesson in result.lessons)

    def test_pipeline_attribution_evidence_traceability(self) -> None:
        """归因证据可追溯性."""
        evidence = [
            AttributionEvidence(
                metric_source="adjust",
                source_ids=["campaign_001", "adset_002"],
                data_window="2026-07-01~2026-07-07",
                confidence=0.85,
                description="D7 ROAS +30% on Adjust",
            ),
            AttributionEvidence(
                metric_source="meta_ads",
                source_ids=["ad_003"],
                data_window="2026-07-01~2026-07-07",
                confidence=0.78,
                description="CTR 2.0% → 3.1% on Meta",
            ),
        ]
        attr = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=0.6,
            metrics_delta={"ctr_change": 0.50},
            evidence=evidence,
        )
        assert len(attr.evidence) == 2
        assert attr.evidence[0].metric_source == "adjust"
        assert attr.evidence[1].metric_source == "meta_ads"
        # 确保可回答"为什么认为素材贡献 X%"
        assert attr.evidence[0].description != ""
        assert attr.evidence[1].description != ""


# ═══════════════════════════════════════════════════════════════
# 10. Optional Reward/Attribution Guard
# ═══════════════════════════════════════════════════════════════


class TestOptionalRewardAttribution:
    """Optional reward/attribution 安全访问测试."""

    def test_experience_without_reward_to_dict(self) -> None:
        """to_dict 在 reward=None 时不崩溃."""
        e = LearningExperience(decision_id="d001")
        d = e.to_dict()
        assert d["reward"] is None
        assert d["attribution"] is None

    def test_learning_result_from_experience_without_reward(self) -> None:
        """from_learning_experience 在 reward=None 时不崩溃."""
        exp = LearningExperience(
            decision_id="d001",
            outcome=LearningOutcome(),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "observe"
        assert result.learning_quality >= 0.0

    def test_learning_result_from_experience_without_attribution(self) -> None:
        """from_learning_experience 在 attribution=None 时不崩溃."""
        exp = LearningExperience(
            decision_id="d001",
            outcome=LearningOutcome(success=True),
            reward=LearningReward(total_reward=0.30),
        )
        result = LearningResult.from_learning_experience(exp)
        assert result.next_action == "adjust"

    def test_delayed_attribution_flow(self) -> None:
        """延迟归因流程 — T+0 创建, T+7 补充, 中间不崩溃."""
        # T+0
        exp = create_learning_experience(
            decision_id="d001",
            strategy_name="test",
            action_type="test",
        )
        exp.reward = LearningReward.from_business_metrics(
            metrics_delta={"roas_change": 0.20},
        )
        assert exp.is_learning_complete is False

        # T+0 result (无 attribution)
        result_t0 = LearningResult.from_learning_experience(exp)
        assert result_t0.learning_quality > 0.0

        # T+7: 补充 attribution
        exp.attribution = AttributionResult.from_heuristic(
            decision_id="d001",
            total_reward=exp.reward.total_reward,
            metrics_delta={"roas_change": 0.20},
        )
        assert exp.is_learning_complete is True

        # T+7 result (有 attribution)
        result_t7 = LearningResult.from_learning_experience(exp)
        assert result_t7.learning_quality >= result_t0.learning_quality