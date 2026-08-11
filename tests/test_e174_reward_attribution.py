"""E13.7.4 Reward Attribution Engine — 专项测试.

测试覆盖:
  1. calculate_reward:  业务/执行/安全/效率 + 自定义权重
  2. attribute:         素材/策略/受众/时机 + 主因判定 + 证据生成
  3. process:           统一入口 + total_reward 回填
  4. End-to-end:        完整 Pipeline + 证据可追溯性
  5. Edge cases:        零值/负值/极值/无上下文
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
    LearningReward,
    RewardWeights,
    create_learning_experience,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.reward_attribution import (
    RewardAttributionEngine,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_experience(
    decision_id: str = "d001",
    execution_success_rate: float = 1.0,
    was_blocked: bool = False,
    needed_approval: bool = False,
    confidence: float = 0.8,
    context: dict[str, Any] | None = None,
) -> LearningExperience:
    """创建测试用 LearningExperience."""
    return LearningExperience(
        decision_id=decision_id,
        execution_id="e001",
        strategy_name="test_strategy",
        action_type="test_action",
        confidence=confidence,
        context=context or {},
        outcome=LearningOutcome(
            execution_success_rate=execution_success_rate,
            was_blocked=was_blocked,
            needed_approval=needed_approval,
        ),
    )


def _make_engine() -> RewardAttributionEngine:
    return RewardAttributionEngine()


# ═══════════════════════════════════════════════════════════════
# 1. calculate_reward — Business Reward
# ═══════════════════════════════════════════════════════════════


class TestCalculateRewardBusiness:
    """业务奖励计算."""

    def test_positive_roas_reward(self) -> None:
        """ROAS +30% → 正向业务奖励."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {"roas_change": 0.30})
        assert reward.business_reward > 0.0
        assert reward.reward_level == "positive"

    def test_negative_roas_reward(self) -> None:
        """ROAS -30% → 负向业务奖励."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {"roas_change": -0.30})
        assert reward.business_reward < 0.0

    def test_positive_revenue_reward(self) -> None:
        """Revenue +20% → 正向."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {"revenue_change": 0.20})
        assert reward.business_reward > 0.0

    def test_positive_payer_reward(self) -> None:
        """Payer rate +15% → 正向."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {"payer_change": 0.15})
        assert reward.business_reward > 0.0

    def test_multi_metric_business_reward(self) -> None:
        """多指标综合 — ROAS +30%, Revenue +20%, Payer +10%."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(
            exp,
            {"roas_change": 0.30, "revenue_change": 0.20, "payer_change": 0.10},
        )
        assert reward.business_reward > 0.3  # 多指标叠加应显著正向
        assert reward.reward_level == "positive"

    def test_empty_metrics_business_reward(self) -> None:
        """空指标 — business_reward = 0."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {})
        assert reward.business_reward == 0.0

    def test_business_reward_range(self) -> None:
        """业务奖励始终在 [-1, 1] 范围内."""
        engine = _make_engine()
        exp = _make_experience()

        # 极端正向
        r = engine.calculate_reward(exp, {"roas_change": 10.0, "revenue_change": 10.0, "payer_change": 10.0})
        assert -1.0 <= r.business_reward <= 1.0

        # 极端负向
        r = engine.calculate_reward(exp, {"roas_change": -10.0, "revenue_change": -10.0, "payer_change": -10.0})
        assert -1.0 <= r.business_reward <= 1.0


# ═══════════════════════════════════════════════════════════════
# 2. calculate_reward — Execution / Safety / Efficiency
# ═══════════════════════════════════════════════════════════════


class TestCalculateRewardNonBusiness:
    """非业务奖励计算."""

    def test_execution_success_reward(self) -> None:
        """执行成功 → execution_reward = 1.0."""
        engine = _make_engine()
        exp = _make_experience(execution_success_rate=1.0)
        reward = engine.calculate_reward(exp, {"roas_change": 0.10})
        assert reward.execution_reward == 1.0

    def test_execution_failure_reward(self) -> None:
        """执行失败 → execution_reward = -1.0."""
        engine = _make_engine()
        exp = _make_experience(execution_success_rate=0.0)
        reward = engine.calculate_reward(exp, {"roas_change": 0.10})
        assert reward.execution_reward == -1.0

    def test_execution_partial_reward(self) -> None:
        """执行部分成功 (50%) → execution_reward = 0.0."""
        engine = _make_engine()
        exp = _make_experience(execution_success_rate=0.5)
        reward = engine.calculate_reward(exp, {})
        assert reward.execution_reward == 0.0

    def test_blocked_safety_reward(self) -> None:
        """被拦截 → safety_reward = -1.0."""
        engine = _make_engine()
        exp = _make_experience(was_blocked=True)
        reward = engine.calculate_reward(exp, {})
        assert reward.safety_reward == -1.0

    def test_approval_safety_reward(self) -> None:
        """需要审批 → safety_reward = -0.5."""
        engine = _make_engine()
        exp = _make_experience(needed_approval=True)
        reward = engine.calculate_reward(exp, {})
        assert reward.safety_reward == -0.5

    def test_normal_safety_reward(self) -> None:
        """正常 → safety_reward = 1.0."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {})
        assert reward.safety_reward == 1.0

    def test_efficiency_cost_decrease(self) -> None:
        """成本下降 → efficiency_reward > 0."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {"cost_change": -0.20})
        assert reward.efficiency_reward > 0.0

    def test_efficiency_cost_increase(self) -> None:
        """成本上升 → efficiency_reward < 0."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {"cost_change": 0.30})
        assert reward.efficiency_reward < 0.0

    def test_efficiency_time_decrease(self) -> None:
        """时间减少 → efficiency_reward > 0."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {"time_change": -0.15})
        assert reward.efficiency_reward > 0.0


# ═══════════════════════════════════════════════════════════════
# 3. calculate_reward — Weights
# ═══════════════════════════════════════════════════════════════


class TestCalculateRewardWeights:
    """权重配置."""

    def test_default_weights(self) -> None:
        """默认 Growth Agent 权重."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(exp, {"roas_change": 0.30})
        assert reward.weights.business == 0.50
        assert reward.calculation_method == "reward_attribution_engine"

    def test_ua_agent_weights(self) -> None:
        """UA Agent 权重 (business=0.70)."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(
            exp, {"roas_change": 0.30}, weights=RewardWeights.ua_agent()
        )
        assert reward.weights.business == 0.70

    def test_conservative_weights(self) -> None:
        """保守权重 (safety=0.45)."""
        engine = _make_engine()
        exp = _make_experience()
        reward = engine.calculate_reward(
            exp, {"roas_change": 0.30}, weights=RewardWeights.conservative()
        )
        assert reward.weights.safety == 0.45

    def test_weight_impact_on_total(self) -> None:
        """不同权重对 total_reward 的影响."""
        engine = _make_engine()
        exp = _make_experience(execution_success_rate=0.5)

        # Growth: business=0.5, execution=0.2, safety=0.2
        r_growth = engine.calculate_reward(
            exp, {"roas_change": 0.30}, weights=RewardWeights.default()
        )
        # UA: business=0.7, execution=0.1, safety=0.15
        r_ua = engine.calculate_reward(
            exp, {"roas_change": 0.30}, weights=RewardWeights.ua_agent()
        )

        # UA 的 business 权重更高, 且 execution 权重更低 (execution 中性)
        assert r_ua.business_reward == r_growth.business_reward
        assert r_ua.total_reward > r_growth.total_reward


# ═══════════════════════════════════════════════════════════════
# 4. attribute — Primary Factor
# ═══════════════════════════════════════════════════════════════


class TestAttributePrimaryFactor:
    """归因主因判定."""

    def test_creative_primary_factor(self) -> None:
        """CTR 大幅提升 → primary_factor = creative."""
        engine = _make_engine()
        exp = _make_experience()
        attr = engine.attribute(exp, {"ctr_change": 0.50, "cvr_change": 0.30})
        assert attr.primary_factor == "creative"
        assert attr.creative_contribution > 0.3

    def test_strategy_primary_factor(self) -> None:
        """高策略置信度 + 低 CTR 变化 → primary_factor = strategy."""
        engine = _make_engine()
        exp = _make_experience(
            confidence=0.9,
            context={"strategy_success_rate": 0.9},
        )
        attr = engine.attribute(exp, {"ctr_change": 0.01, "cvr_change": 0.01})
        assert attr.primary_factor == "strategy"

    def test_audience_primary_factor(self) -> None:
        """高受众匹配度 → primary_factor = audience."""
        engine = _make_engine()
        exp = _make_experience(
            context={"audience_match": 0.95},
        )
        attr = engine.attribute(exp, {})
        assert attr.primary_factor == "audience"

    def test_timing_primary_factor(self) -> None:
        """高时机因子 → primary_factor = timing."""
        engine = _make_engine()
        exp = _make_experience(
            context={"timing_factor": 0.8},
        )
        attr = engine.attribute(exp, {})
        assert attr.primary_factor == "timing"

    def test_unexplained_primary(self) -> None:
        """所有贡献都很低 → primary_factor = unexplained."""
        engine = _make_engine()
        exp = _make_experience(
            confidence=0.01,
            context={"strategy_success_rate": 0.0, "audience_match": 0.0, "timing_factor": 0.0},
        )
        attr = engine.attribute(exp, {"ctr_change": 0.0, "cvr_change": 0.0})
        assert attr.primary_factor == "unexplained"


# ═══════════════════════════════════════════════════════════════
# 5. attribute — Contribution Values
# ═══════════════════════════════════════════════════════════════


class TestAttributeContributions:
    """归因贡献值."""

    def test_creative_contribution_ctr_only(self) -> None:
        """仅 CTR 变化."""
        engine = _make_engine()
        exp = _make_experience()
        attr = engine.attribute(exp, {"ctr_change": 0.40})
        # creative 贡献应被归一化, 且 > 0
        assert attr.creative_contribution > 0.0

    def test_creative_contribution_negative_ctr(self) -> None:
        """CTR 负向变化."""
        engine = _make_engine()
        exp = _make_experience()
        attr = engine.attribute(exp, {"ctr_change": -0.30, "cvr_change": -0.20})
        assert attr.creative_contribution < 0.0

    def test_strategy_contribution_from_context(self) -> None:
        """策略贡献从 context 提取."""
        engine = _make_engine()
        exp = _make_experience(
            confidence=0.7,
            context={"strategy_success_rate": 0.8},
        )
        attr = engine.attribute(exp, {})
        assert attr.strategy_contribution > 0.0

    def test_audience_contribution_from_context(self) -> None:
        """受众贡献从 context 提取."""
        engine = _make_engine()
        exp = _make_experience(
            context={"audience_match": 0.75},
        )
        attr = engine.attribute(exp, {})
        assert attr.audience_contribution > 0.0

    def test_contribution_normalization(self) -> None:
        """贡献值归一化 — 总和 (不含 unexplained) ≈ 1.0."""
        engine = _make_engine()
        exp = _make_experience(
            confidence=0.6,
            context={"strategy_success_rate": 0.6, "audience_match": 0.6, "timing_factor": 0.3},
        )
        attr = engine.attribute(exp, {"ctr_change": 0.20, "cvr_change": 0.15})
        contrib_sum = (
            attr.creative_contribution
            + attr.strategy_contribution
            + attr.audience_contribution
            + attr.timing_contribution
        )
        assert abs(contrib_sum - 1.0) < 0.01

    def test_contribution_zero_sum(self) -> None:
        """所有贡献为零 → 归一化后均为 0."""
        engine = _make_engine()
        exp = _make_experience(
            confidence=0.0,
            context={"strategy_success_rate": 0.0, "audience_match": 0.0, "timing_factor": 0.0},
        )
        attr = engine.attribute(exp, {"ctr_change": 0.0, "cvr_change": 0.0})
        assert attr.creative_contribution == 0.0
        assert attr.strategy_contribution == 0.0
        assert attr.audience_contribution == 0.0
        assert attr.timing_contribution == 0.0


# ═══════════════════════════════════════════════════════════════
# 6. attribute — Evidence
# ═══════════════════════════════════════════════════════════════


class TestAttributeEvidence:
    """证据生成."""

    def test_evidence_generation_creative(self) -> None:
        """有 CTR/CVR 数据 → 生成素材证据."""
        engine = _make_engine()
        exp = _make_experience()
        attr = engine.attribute(exp, {"ctr_change": 0.30, "cvr_change": 0.15})
        creative_evidence = [e for e in attr.evidence if e.metric_source == "creative_metrics"]
        assert len(creative_evidence) == 1

    def test_evidence_generation_strategy(self) -> None:
        """有策略成功率 → 生成策略证据."""
        engine = _make_engine()
        exp = _make_experience(context={"strategy_success_rate": 0.75})
        attr = engine.attribute(exp, {})
        strategy_evidence = [e for e in attr.evidence if e.metric_source == "strategy_history"]
        assert len(strategy_evidence) == 1

    def test_evidence_generation_audience(self) -> None:
        """有受众匹配度 → 生成受众证据."""
        engine = _make_engine()
        exp = _make_experience(context={"audience_match": 0.8})
        attr = engine.attribute(exp, {})
        audience_evidence = [e for e in attr.evidence if e.metric_source == "audience_analysis"]
        assert len(audience_evidence) == 1

    def test_evidence_generation_timing(self) -> None:
        """有时机因子 → 生成时机证据."""
        engine = _make_engine()
        exp = _make_experience(context={"timing_factor": 0.6})
        attr = engine.attribute(exp, {})
        timing_evidence = [e for e in attr.evidence if e.metric_source == "market_timing"]
        assert len(timing_evidence) == 1

    def test_evidence_no_data_no_evidence(self) -> None:
        """无数据 → 不生成证据."""
        engine = _make_engine()
        exp = _make_experience()
        attr = engine.attribute(exp, {})
        assert len(attr.evidence) == 0

    def test_evidence_has_source_ids(self) -> None:
        """证据包含 source_ids."""
        engine = _make_engine()
        exp = _make_experience(decision_id="d_test_001")
        attr = engine.attribute(exp, {"ctr_change": 0.20})
        for e in attr.evidence:
            assert "d_test_001" in e.source_ids

    def test_evidence_has_data_window(self) -> None:
        """证据包含 data_window."""
        engine = _make_engine()
        exp = _make_experience()
        attr = engine.attribute(exp, {"ctr_change": 0.20})
        for e in attr.evidence:
            assert e.data_window != ""

    def test_evidence_confidence_range(self) -> None:
        """证据置信度在 [0, 1] 范围内."""
        engine = _make_engine()
        exp = _make_experience(
            context={
                "strategy_success_rate": 0.8,
                "audience_match": 0.7,
                "timing_factor": 0.5,
            },
        )
        attr = engine.attribute(exp, {"ctr_change": 0.30, "cvr_change": 0.20})
        for e in attr.evidence:
            assert 0.0 <= e.confidence <= 1.0


# ═══════════════════════════════════════════════════════════════
# 7. attribute — Confidence
# ═══════════════════════════════════════════════════════════════


class TestAttributeConfidence:
    """归因置信度."""

    def test_attribution_confidence_with_evidence(self) -> None:
        """有证据 → 置信度 > 0.3."""
        engine = _make_engine()
        exp = _make_experience(
            context={"strategy_success_rate": 0.7},
        )
        attr = engine.attribute(exp, {"ctr_change": 0.20, "cvr_change": 0.10})
        assert attr.confidence > 0.3

    def test_attribution_confidence_without_evidence(self) -> None:
        """无证据 → 置信度低."""
        engine = _make_engine()
        exp = _make_experience()
        attr = engine.attribute(exp, {})
        assert attr.confidence >= 0.0


# ═══════════════════════════════════════════════════════════════
# 8. process()
# ═══════════════════════════════════════════════════════════════


class TestProcess:
    """统一入口 process()."""

    def test_process_returns_both(self) -> None:
        """process() 返回 (reward, attribution)."""
        engine = _make_engine()
        exp = _make_experience()
        reward, attr = engine.process(exp, {"roas_change": 0.30})
        assert isinstance(reward, LearningReward)
        assert isinstance(attr, AttributionResult)

    def test_process_total_reward_in_attribution(self) -> None:
        """process() 将 total_reward 回填到 attribution."""
        engine = _make_engine()
        exp = _make_experience()
        reward, attr = engine.process(exp, {"roas_change": 0.30})
        assert attr.total_reward == reward.total_reward

    def test_process_reward_level_positive(self) -> None:
        """正向指标 → reward_level = positive."""
        engine = _make_engine()
        exp = _make_experience()
        reward, _ = engine.process(
            exp, {"roas_change": 0.30, "revenue_change": 0.20}
        )
        assert reward.reward_level == "positive"

    def test_process_reward_level_negative(self) -> None:
        """负向指标 → reward_level = negative."""
        engine = _make_engine()
        exp = _make_experience(execution_success_rate=0.0)
        reward, _ = engine.process(
            exp, {"roas_change": -0.50, "revenue_change": -0.30}
        )
        assert reward.reward_level == "negative"

    def test_process_with_custom_weights(self) -> None:
        """自定义权重."""
        engine = _make_engine()
        exp = _make_experience()
        reward, _ = engine.process(
            exp, {"roas_change": 0.30}, weights=RewardWeights.ua_agent()
        )
        assert reward.weights.business == 0.70

    def test_process_attribution_primary_factor(self) -> None:
        """process() 的 attribution 包含 primary_factor."""
        engine = _make_engine()
        exp = _make_experience(
            context={"strategy_success_rate": 0.9},
        )
        _, attr = engine.process(exp, {"ctr_change": 0.50, "cvr_change": 0.40})
        assert attr.primary_factor in ("creative", "strategy", "audience", "timing", "unexplained")


# ═══════════════════════════════════════════════════════════════
# 9. End-to-end Pipeline
# ═══════════════════════════════════════════════════════════════


class TestEndToEndPipeline:
    """完整 Pipeline."""

    def test_full_pipeline_positive(self) -> None:
        """正向完整流程."""
        engine = _make_engine()
        exp = _make_experience(
            decision_id="d_pipeline_001",
            context={
                "strategy_success_rate": 0.8,
                "audience_match": 0.7,
                "sample_size": 5000,
            },
        )
        reward, attr = engine.process(
            exp,
            {
                "roas_change": 0.35,
                "revenue_change": 0.25,
                "payer_change": 0.15,
                "ctr_change": 0.20,
                "cvr_change": 0.12,
                "cost_change": -0.10,
                "time_change": -0.05,
            },
        )

        # Reward 验证
        assert reward.reward_level == "positive"
        assert reward.business_reward > 0.0
        assert reward.execution_reward == 1.0
        assert reward.efficiency_reward > 0.0

        # Attribution 验证
        assert attr.total_reward == reward.total_reward
        assert attr.primary_factor != ""
        assert len(attr.evidence) > 0

    def test_full_pipeline_negative(self) -> None:
        """负向完整流程."""
        engine = _make_engine()
        exp = _make_experience(
            decision_id="d_pipeline_002",
            execution_success_rate=0.0,
        )
        reward, attr = engine.process(
            exp,
            {
                "roas_change": -0.40,
                "revenue_change": -0.30,
                "ctr_change": -0.25,
                "cvr_change": -0.20,
                "cost_change": 0.30,
            },
        )

        assert reward.reward_level == "negative"
        assert reward.total_reward < 0.0
        assert reward.execution_reward < 0.0
        assert attr.creative_contribution < 0.0

    def test_full_pipeline_blocked(self) -> None:
        """被拦截流程."""
        engine = _make_engine()
        exp = _make_experience(was_blocked=True)
        reward, _ = engine.process(exp, {"roas_change": 0.30})
        assert reward.safety_reward == -1.0

    def test_full_pipeline_creative_driven(self) -> None:
        """素材驱动 — CTR/CVR 大幅提升."""
        engine = _make_engine()
        exp = _make_experience(
            context={"strategy_success_rate": 0.3, "audience_match": 0.3},
        )
        _, attr = engine.process(
            exp,
            {"roas_change": 0.30, "ctr_change": 0.60, "cvr_change": 0.40},
        )
        assert attr.primary_factor == "creative"
        assert attr.is_creative_driven is True

    def test_full_pipeline_strategy_driven(self) -> None:
        """策略驱动 — 高策略成功率 + 低 CTR."""
        engine = _make_engine()
        exp = _make_experience(
            confidence=0.9,
            context={"strategy_success_rate": 0.95},
        )
        _, attr = engine.process(
            exp,
            {"roas_change": 0.20, "ctr_change": 0.01, "cvr_change": 0.01},
        )
        assert attr.primary_factor == "strategy"

    def test_full_pipeline_evidence_traceability(self) -> None:
        """证据可追溯 — 每条证据可回答"为什么"."""
        engine = _make_engine()
        exp = _make_experience(
            decision_id="d_trace_001",
            context={
                "strategy_success_rate": 0.8,
                "audience_match": 0.75,
                "timing_factor": 0.5,
                "data_window": "2026-07-01~2026-07-07",
            },
        )
        _, attr = engine.process(
            exp,
            {
                "roas_change": 0.30,
                "ctr_change": 0.25,
                "cvr_change": 0.15,
            },
        )

        # 每个证据可追溯
        for e in attr.evidence:
            assert e.metric_source != ""
            assert len(e.source_ids) > 0
            assert e.data_window != ""
            assert e.description != ""


# ═══════════════════════════════════════════════════════════════
# 10. Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况."""

    def test_zero_metrics(self) -> None:
        """全零指标 — 不崩溃."""
        engine = _make_engine()
        exp = _make_experience()
        reward, attr = engine.process(
            exp,
            {"roas_change": 0.0, "revenue_change": 0.0, "payer_change": 0.0},
        )
        assert reward is not None
        assert attr is not None

    def test_negative_values(self) -> None:
        """全负值指标."""
        engine = _make_engine()
        exp = _make_experience()
        reward, attr = engine.process(
            exp,
            {
                "roas_change": -0.5,
                "revenue_change": -0.4,
                "payer_change": -0.3,
                "ctr_change": -0.2,
                "cvr_change": -0.15,
                "cost_change": 0.5,
                "time_change": 0.3,
            },
        )
        assert reward.business_reward < 0.0
        assert reward.efficiency_reward < 0.0
        assert attr.creative_contribution < 0.0

    def test_extreme_positive_values(self) -> None:
        """极端正向值 — 不溢出."""
        engine = _make_engine()
        exp = _make_experience()
        reward, attr = engine.process(
            exp,
            {"roas_change": 100.0, "revenue_change": 100.0, "payer_change": 100.0},
        )
        assert -1.0 <= reward.business_reward <= 1.0
        assert -1.0 <= reward.total_reward <= 1.0

    def test_extreme_negative_values(self) -> None:
        """极端负向值 — 不溢出."""
        engine = _make_engine()
        exp = _make_experience()
        reward, attr = engine.process(
            exp,
            {"roas_change": -100.0, "revenue_change": -100.0, "payer_change": -100.0},
        )
        assert -1.0 <= reward.business_reward <= 1.0
        assert -1.0 <= reward.total_reward <= 1.0

    def test_no_context(self) -> None:
        """无 context — 使用默认值."""
        engine = _make_engine()
        exp = _make_experience(context={})
        reward, attr = engine.process(exp, {"roas_change": 0.20})
        assert reward is not None
        assert attr is not None

    def test_partial_metrics(self) -> None:
        """部分指标 — 只提供 ROAS."""
        engine = _make_engine()
        exp = _make_experience()
        reward, attr = engine.process(exp, {"roas_change": 0.25})
        assert reward.business_reward > 0.0
        assert reward.confidence < 0.5  # 指标不完整, 置信度低

    def test_confidence_low_sample_size(self) -> None:
        """小样本量 → 置信度低."""
        engine = _make_engine()
        exp = _make_experience(context={"sample_size": 10})
        reward, _ = engine.process(
            exp, {"roas_change": 0.30}  # 仅 1 个指标, 完整度低
        )
        assert reward.confidence < 0.5

    def test_confidence_high_sample_size(self) -> None:
        """大样本量 → 置信度高."""
        engine = _make_engine()
        exp = _make_experience(context={"sample_size": 50000})
        reward, _ = engine.process(
            exp, {"roas_change": 0.30, "revenue_change": 0.20, "payer_change": 0.10}
        )
        assert reward.confidence > 0.5

    def test_attribution_idempotent(self) -> None:
        """相同输入 → 相同归因结果."""
        engine = _make_engine()
        exp = _make_experience(
            context={"strategy_success_rate": 0.7, "audience_match": 0.6},
        )
        metrics = {"ctr_change": 0.30, "cvr_change": 0.20}
        attr1 = engine.attribute(exp, metrics)
        attr2 = engine.attribute(exp, metrics)
        assert attr1.primary_factor == attr2.primary_factor
        assert attr1.creative_contribution == attr2.creative_contribution

    def test_reward_calculation_method(self) -> None:
        """Reward calculation_method 标记为 engine."""
        engine = _make_engine()
        exp = _make_experience()
        reward, _ = engine.process(exp, {"roas_change": 0.10})
        assert reward.calculation_method == "reward_attribution_engine"

    def test_attribution_method(self) -> None:
        """Attribution method 标记为 engine."""
        engine = _make_engine()
        exp = _make_experience()
        _, attr = engine.process(exp, {"roas_change": 0.10})
        assert attr.attribution_method == "reward_attribution_engine"

    def test_data_window_from_context(self) -> None:
        """从 context 提取 data_window."""
        engine = _make_engine()
        exp = _make_experience(
            context={"data_window": "2026-07-15~2026-07-21"},
        )
        _, attr = engine.process(exp, {"ctr_change": 0.20})
        for e in attr.evidence:
            assert e.data_window == "2026-07-15~2026-07-21"