"""E13.5.2 Opportunity Rules — 机会检测规则引擎.

将 Reality Signal + Metrics + Prediction 转换为 GrowthOpportunity 候选。

核心规则:
  - CreativeFatigueRule: 素材疲劳检测 → CREATIVE_REFRESH
  - ScalingOpportunityRule: 放量机会检测 → CREATIVE_SCALE
  - BudgetOptimizationRule: 预算优化检测 → BUDGET_OPTIMIZATION
  - MonetizationOptimizationRule: 变现优化检测 → MONETIZATION_OPTIMIZATION
  - AudienceExpansionRule: 受众扩展检测 → AUDIENCE_EXPANSION
  - RiskMitigationRule: 风险缓解检测 → RISK_MITIGATION

连接:
  E13.3 Signal → E13.5.2 Rules → GrowthOpportunity
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .intelligence_models import (
    CurrentMetrics,
    DecisionPriority,
    ExpectedImpact,
    GrowthOpportunity,
    OpportunitySource,
    OpportunityType,
    SignalSummary,
)


# ═══════════════════════════════════════════════════════════════
# Abstract Base
# ═══════════════════════════════════════════════════════════════


class OpportunityRule(ABC):
    """机会检测规则基类.

    每个规则接收 signals + metrics + predictions，返回检测到的 GrowthOpportunity 列表。
    """

    # 规则名称，子类必须覆盖
    name: str = "base"
    # 规则描述
    description: str = ""

    @abstractmethod
    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        """检测机会.

        Args:
            signals: 信号摘要 (含 fatigue, anomaly, trend 等)
            metrics: 当前指标快照
            predictions: 预测结果 (如 fatigue_probability, roas_forecast 等)

        Returns:
            list[GrowthOpportunity]: 匹配的机会列表
        """
        ...

    def _create_opportunity(
        self,
        opportunity_type: OpportunityType,
        impact_score: float,
        confidence: float,
        urgency: float,
        reason: str,
        recommended_action: str,
        expected_impact: ExpectedImpact | None = None,
        source: OpportunitySource = OpportunitySource.SIGNAL_ENGINE,
    ) -> GrowthOpportunity:
        """创建机会对象并自动计算优先级."""
        opp = GrowthOpportunity(
            opportunity_type=opportunity_type,
            source=source,
            impact_score=impact_score,
            confidence=confidence,
            urgency=urgency,
            reason=reason,
            recommended_action=recommended_action,
            expected_impact=expected_impact or ExpectedImpact(),
        )
        opp.compute_priority()
        return opp

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, value))


# ═══════════════════════════════════════════════════════════════
# Rule Implementations
# ═══════════════════════════════════════════════════════════════


class CreativeFatigueRule(OpportunityRule):
    """素材疲劳检测规则.

    条件:
      - CTR 下降 > 20% (相对于 baseline)
      - Frequency > 3.0 (曝光频次过高)
      - ROAS 下降趋势

    输出: CREATIVE_REFRESH
    """

    name = "creative_fatigue"
    description = "Detect creative fatigue from CTR decay, frequency spike, and ROAS decline"

    def __init__(
        self,
        ctr_decay_threshold: float = 0.20,
        frequency_threshold: float = 3.0,
        roas_decay_threshold: float = 0.10,
    ):
        self.ctr_decay_threshold = ctr_decay_threshold
        self.frequency_threshold = frequency_threshold
        self.roas_decay_threshold = roas_decay_threshold

    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        if not signals.fatigue_detected:
            return []

        # CTR 下降检查
        ctr_decay = predictions.get("ctr_decay", 0.0) if predictions else 0.0
        # Frequency 检查
        freq = metrics.frequency
        # ROAS 下降
        roas_decay = abs(predictions.get("roas_decay", 0.0)) if predictions else 0.0

        conditions_met = 0
        reasons: list[str] = []

        if ctr_decay >= self.ctr_decay_threshold:
            conditions_met += 1
            reasons.append(f"CTR decay {ctr_decay:.0%} >= {self.ctr_decay_threshold:.0%}")

        if freq >= self.frequency_threshold:
            conditions_met += 1
            reasons.append(f"Frequency {freq:.1f} >= {self.frequency_threshold}")

        if roas_decay >= self.roas_decay_threshold:
            conditions_met += 1
            reasons.append(f"ROAS decay {roas_decay:.0%} >= {self.roas_decay_threshold:.0%}")

        if conditions_met < 2:
            return []

        # 置信度 = 条件匹配数 / 3 + 预测概率加权
        fatigue_prob = predictions.get("fatigue_probability", 0.5) if predictions else 0.5
        confidence = self._clamp(conditions_met / 3 * 0.6 + fatigue_prob * 0.4)

        # 影响评分 = CTR 衰减 + 频次过高
        impact = self._clamp(ctr_decay * 0.5 + min(freq / 10.0, 0.5))

        # 紧急度 = 频次越高越紧急
        urgency = self._clamp(min(freq / 8.0, 1.0))

        reason = "Creative fatigue detected: " + "; ".join(reasons)
        recommended_action = "generate_dna_variants"

        expected = ExpectedImpact(
            roas_change=0.20,  # 预期 ROAS +20%
            ctr_change=0.15,   # 预期 CTR +15%
            confidence=confidence,
            timeframe_days=5,
        )

        return [self._create_opportunity(
            opportunity_type=OpportunityType.CREATIVE_REFRESH,
            impact_score=round(impact, 4),
            confidence=round(confidence, 4),
            urgency=round(urgency, 4),
            reason=reason,
            recommended_action=recommended_action,
            expected_impact=expected,
        )]


class ScalingOpportunityRule(OpportunityRule):
    """放量机会检测规则.

    条件:
      - ROAS > target_roas (默认 1.2)
      - spend 稳定 (未剧烈波动)
      - conversion 稳定 (CTR 或 IPM 未下降)

    输出: CREATIVE_SCALE
    """

    name = "scaling_opportunity"
    description = "Detect scaling opportunities when ROAS exceeds target with stable metrics"

    def __init__(
        self,
        target_roas: float = 1.2,
        ctr_min: float = 0.01,
        ipm_min: float = 1.0,
        spend_min: float = 50.0,
    ):
        self.target_roas = target_roas
        self.ctr_min = ctr_min
        self.ipm_min = ipm_min
        self.spend_min = spend_min

    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        if metrics.roas < self.target_roas:
            return []

        if metrics.spend < self.spend_min:
            return []

        if metrics.ctr < self.ctr_min:
            return []

        if signals.trend == "declining":
            return []

        # ROAS 超出目标越多，机会越大
        roas_surplus = (metrics.roas - self.target_roas) / self.target_roas
        impact = self._clamp(roas_surplus * 0.5 + 0.3)

        # 置信度基于 ROAS 和指标稳定性
        roas_confidence = self._clamp((metrics.roas - self.target_roas) / self.target_roas * 0.5 + 0.5)
        trend_confidence = 0.7 if signals.trend == "improving" else 0.5
        confidence = self._clamp(roas_confidence * 0.6 + trend_confidence * 0.4)

        # 紧急度：ROAS 越高越有价值立即行动(但不过度)
        urgency = self._clamp(roas_surplus * 0.4 + 0.3)

        reason = (
            f"Scaling opportunity: ROAS {metrics.roas:.2f} > target {self.target_roas}, "
            f"CTR stable at {metrics.ctr:.4f}, trend: {signals.trend}"
        )
        recommended_action = "scale_budget"

        expected = ExpectedImpact(
            spend_change=metrics.spend * 0.3,  # 预期 +30% spend
            revenue_change=metrics.revenue * 0.3,
            roas_change=-0.05,  # 放量后 ROAS 可能略有下降
            confidence=confidence,
            timeframe_days=3,
        )

        return [self._create_opportunity(
            opportunity_type=OpportunityType.CREATIVE_SCALE,
            impact_score=round(impact, 4),
            confidence=round(confidence, 4),
            urgency=round(urgency, 4),
            reason=reason,
            recommended_action=recommended_action,
            expected_impact=expected,
        )]


class BudgetOptimizationRule(OpportunityRule):
    """预算优化检测规则.

    条件:
      - 检测到 winner (ROAS > 1.5 且 spend 稳定)
      - 有其他 campaign 预算未充分利用
      - 或有闲置预算

    输出: BUDGET_OPTIMIZATION 或 BUDGET_REDISTRIBUTION
    """

    name = "budget_optimization"
    description = "Detect budget optimization opportunities from winner campaigns and idle budget"

    def __init__(
        self,
        winner_roas: float = 1.5,
        idle_budget_ratio: float = 0.15,
    ):
        self.winner_roas = winner_roas
        self.idle_budget_ratio = idle_budget_ratio

    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        opportunities: list[GrowthOpportunity] = []

        # 预算再分配: winner + 闲置预算
        has_winner = metrics.roas >= self.winner_roas
        has_idle_budget = predictions.get("idle_budget_ratio", 0.0) >= self.idle_budget_ratio if predictions else False

        if has_winner and has_idle_budget:
            idle_ratio = predictions.get("idle_budget_ratio", 0.0) if predictions else 0.0
            impact = self._clamp(idle_ratio * 0.6 + 0.3)
            confidence = self._clamp((metrics.roas - 1.0) / self.winner_roas)
            urgency = self._clamp(idle_ratio)

            reason = (
                f"Budget redistribution: winner ROAS {metrics.roas:.2f} with "
                f"{idle_ratio:.0%} idle budget available"
            )

            expected = ExpectedImpact(
                roas_change=0.10,
                revenue_change=metrics.revenue * idle_ratio * 0.5,
                confidence=confidence,
                timeframe_days=3,
            )

            opportunities.append(self._create_opportunity(
                opportunity_type=OpportunityType.BUDGET_REDISTRIBUTION,
                impact_score=round(impact, 4),
                confidence=round(confidence, 4),
                urgency=round(urgency, 4),
                reason=reason,
                recommended_action="redistribute_budget",
                expected_impact=expected,
            ))

        return opportunities


class MonetizationOptimizationRule(OpportunityRule):
    """变现优化检测规则.

    条件:
      - payer_rate 上升
      - ARPPU (平均每付费用户收入) 上升
      - LTV 预测上升

    输出: MONETIZATION_OPTIMIZATION
    """

    name = "monetization_optimization"
    description = "Detect monetization opportunities from payer rate, ARPPU, and LTV improvements"

    def __init__(
        self,
        payer_rate_increase: float = 0.05,
        ltv_increase: float = 0.10,
    ):
        self.payer_rate_increase = payer_rate_increase
        self.ltv_increase = ltv_increase

    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        if not predictions:
            return []

        payer_rate_change = predictions.get("payer_rate_change", 0.0)
        ltv_change = predictions.get("ltv_change", 0.0)
        arppu_change = predictions.get("arppu_change", 0.0)

        conditions_met = 0
        reasons: list[str] = []

        if payer_rate_change >= self.payer_rate_increase:
            conditions_met += 1
            reasons.append(f"Payer rate +{payer_rate_change:.0%}")

        if ltv_change >= self.ltv_increase:
            conditions_met += 1
            reasons.append(f"LTV +{ltv_change:.0%}")

        if arppu_change >= self.ltv_increase:
            conditions_met += 1
            reasons.append(f"ARPPU +{arppu_change:.0%}")

        if conditions_met < 2:
            return []

        # 影响 = 变现改善幅度
        impact = self._clamp((payer_rate_change + ltv_change + arppu_change) / 3 * 1.5)
        confidence = self._clamp(conditions_met / 3 * 0.7 + 0.3)
        urgency = self._clamp(impact * 0.6)

        reason = "Monetization optimization: " + "; ".join(reasons)
        recommended_action = "optimize_monetization"

        expected = ExpectedImpact(
            revenue_change=metrics.revenue * 0.15,
            roas_change=0.10,
            confidence=confidence,
            timeframe_days=14,
        )

        return [self._create_opportunity(
            opportunity_type=OpportunityType.MONETIZATION_OPTIMIZATION,
            impact_score=round(impact, 4),
            confidence=round(confidence, 4),
            urgency=round(urgency, 4),
            reason=reason,
            recommended_action=recommended_action,
            expected_impact=expected,
        )]


class AudienceExpansionRule(OpportunityRule):
    """受众扩展检测规则.

    条件:
      - 当前受众表现稳定 (ROAS > 1.0)
      - 未检测到疲劳信号
      - 有 lookalike 或兴趣扩展机会

    输出: AUDIENCE_EXPANSION
    """

    name = "audience_expansion"
    description = "Detect audience expansion opportunities when current audience is stable"

    def __init__(
        self,
        min_roas: float = 1.0,
        min_spend: float = 100.0,
    ):
        self.min_roas = min_roas
        self.min_spend = min_spend

    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        if metrics.roas < self.min_roas:
            return []

        if metrics.spend < self.min_spend:
            return []

        if signals.fatigue_detected:
            return []

        if signals.trend == "declining":
            return []

        # 有 lookalike 机会
        has_lookalike = predictions.get("lookalike_ready", False) if predictions else False

        impact = self._clamp(0.3 + (metrics.roas - self.min_roas) * 0.3)
        confidence = 0.6 if has_lookalike else 0.4
        urgency = 0.3  # 受众扩展不紧急

        reason = (
            f"Audience expansion: current ROAS {metrics.roas:.2f} stable, "
            f"trend {signals.trend}"
        )
        if has_lookalike:
            reason += ", lookalike audience ready"
        recommended_action = "expand_audience"

        expected = ExpectedImpact(
            spend_change=metrics.spend * 0.5,
            revenue_change=metrics.revenue * 0.4,
            roas_change=-0.05,  # 扩展初期 ROAS 可能略降
            confidence=confidence,
            timeframe_days=7,
        )

        return [self._create_opportunity(
            opportunity_type=OpportunityType.AUDIENCE_EXPANSION,
            impact_score=round(impact, 4),
            confidence=round(confidence, 4),
            urgency=round(urgency, 4),
            reason=reason,
            recommended_action=recommended_action,
            expected_impact=expected,
        )]


class RiskMitigationRule(OpportunityRule):
    """风险缓解检测规则.

    条件:
      - 检测到异常信号 (anomaly)
      - ROAS 骤降 > 30%
      - 或花费异常激增

    输出: RISK_MITIGATION
    """

    name = "risk_mitigation"
    description = "Detect risk mitigation needs from anomaly signals and sharp metric declines"

    def __init__(
        self,
        roas_crash_threshold: float = 0.30,
        spend_spike_ratio: float = 2.0,
    ):
        self.roas_crash_threshold = roas_crash_threshold
        self.spend_spike_ratio = spend_spike_ratio

    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        if not signals.anomaly_detected:
            return []

        roas_crash = predictions.get("roas_crash", 0.0) if predictions else 0.0
        spend_spike = predictions.get("spend_spike_ratio", 1.0) if predictions else 1.0

        if roas_crash < self.roas_crash_threshold and spend_spike < self.spend_spike_ratio:
            return []

        impact = self._clamp(roas_crash * 0.6 + min(spend_spike / 5.0, 0.4))
        confidence = self._clamp(0.6 + roas_crash * 0.4)
        urgency = self._clamp(roas_crash * 0.7 + min(spend_spike / 4.0, 0.3))

        reasons: list[str] = []
        if roas_crash >= self.roas_crash_threshold:
            reasons.append(f"ROAS crashed {roas_crash:.0%}")
        if spend_spike >= self.spend_spike_ratio:
            reasons.append(f"Spend spiked {spend_spike:.1f}x")

        reason = "Risk mitigation required: " + "; ".join(reasons)
        recommended_action = "pause_underperforming"

        expected = ExpectedImpact(
            roas_change=roas_crash * 0.5,  # 止损后预期恢复一半
            spend_change=-metrics.spend * 0.2,
            confidence=confidence,
            timeframe_days=1,
        )

        return [self._create_opportunity(
            opportunity_type=OpportunityType.RISK_MITIGATION,
            impact_score=round(impact, 4),
            confidence=round(confidence, 4),
            urgency=round(urgency, 4),
            reason=reason,
            recommended_action=recommended_action,
            expected_impact=expected,
        )]


class ExperimentLaunchRule(OpportunityRule):
    """实验启动检测规则.

    条件:
      - 当前所有 campaign 表现稳定
      - 无活跃实验
      - 有可用的新创意 DNA 或新受众

    输出: EXPERIMENT_LAUNCH
    """

    name = "experiment_launch"
    description = "Detect experiment launch opportunities when system is stable with unused capacity"

    def __init__(self, min_roas: float = 0.8):
        self.min_roas = min_roas

    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        has_new_dna = predictions.get("new_dna_available", False) if predictions else False
        has_new_audience = predictions.get("new_audience_available", False) if predictions else False

        if not has_new_dna and not has_new_audience:
            return []

        if signals.trend == "declining":
            return []

        impact = 0.25
        confidence = 0.5
        urgency = 0.2

        reason_parts: list[str] = []
        if has_new_dna:
            reason_parts.append("new DNA variants available")
        if has_new_audience:
            reason_parts.append("new audience segments available")

        reason = "Experiment launch: " + "; ".join(reason_parts)
        recommended_action = "launch_experiment"

        expected = ExpectedImpact(
            roas_change=0.05,
            confidence=0.5,
            timeframe_days=7,
        )

        return [self._create_opportunity(
            opportunity_type=OpportunityType.EXPERIMENT_LAUNCH,
            impact_score=round(impact, 4),
            confidence=round(confidence, 4),
            urgency=round(urgency, 4),
            reason=reason,
            recommended_action=recommended_action,
            expected_impact=expected,
        )]


# ═══════════════════════════════════════════════════════════════
# Rule Engine (Composite)
# ═══════════════════════════════════════════════════════════════


class RuleEngine:
    """规则引擎 — 组合所有检测规则，批量检测机会.

    用法:
        engine = RuleEngine()
        engine.register(CreativeFatigueRule())
        opportunities = engine.detect(signals, metrics, predictions)
    """

    def __init__(self):
        self._rules: list[OpportunityRule] = []

    def register(self, rule: OpportunityRule) -> None:
        """注册一条检测规则."""
        self._rules.append(rule)

    def register_defaults(self) -> None:
        """注册所有默认规则."""
        self.register(CreativeFatigueRule())
        self.register(ScalingOpportunityRule())
        self.register(BudgetOptimizationRule())
        self.register(MonetizationOptimizationRule())
        self.register(AudienceExpansionRule())
        self.register(RiskMitigationRule())
        self.register(ExperimentLaunchRule())

    def detect(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
    ) -> list[GrowthOpportunity]:
        """运行所有规则，汇总检测结果.

        Args:
            signals: 信号摘要
            metrics: 当前指标
            predictions: 预测数据

        Returns:
            list[GrowthOpportunity]: 所有检测到的机会
        """
        opportunities: list[GrowthOpportunity] = []
        for rule in self._rules:
            try:
                results = rule.detect(signals, metrics, predictions)
                opportunities.extend(results)
            except Exception:
                # 单个规则失败不影响其他规则
                continue
        return opportunities

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def get_rule_names(self) -> list[str]:
        return [r.name for r in self._rules]

    def clear(self) -> None:
        self._rules.clear()