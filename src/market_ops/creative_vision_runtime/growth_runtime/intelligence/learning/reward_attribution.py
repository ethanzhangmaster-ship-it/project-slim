"""E13.7.4 Reward Attribution Engine — 奖励计算与归因引擎.

Day 7.4.4:
  将 LearningExperience + Reality Metrics 转换为可学习的
  LearningReward + AttributionResult。

核心流程:
  Execution Result
        |
        v
  RewardAttributionEngine
        |
        +--> LearningReward      (business/execution/safety/efficiency)
        |
        +--> AttributionResult   (strategy/creative/audience/timing)
        |
        v
  Learning Memory

职责:
  1. Reward 计算: 多维度加权 (business/execution/safety/efficiency)
  2. Reward 权重选择: 支持 Growth/UA/Creative/Conservative
  3. Attribution 分解: creative/strategy/audience/timing 四维
  4. Confidence 计算: 基于样本量和指标完整度
  5. Evidence 记录: 可追溯的数据来源

设计原则:
  - 不修改 LearningExperience / LearningReward / AttributionResult 模型
  - 输入: LearningExperience + Reality Metrics (dict)
  - 输出: LearningReward + AttributionResult
  - process() 作为统一入口, 内部调用 calculate_reward + attribute
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .models.learning_models import (
    AttributionEvidence,
    AttributionResult,
    LearningExperience,
    LearningReward,
    RewardWeights,
)


# ═══════════════════════════════════════════════════════════════
# RewardAttributionEngine
# ═══════════════════════════════════════════════════════════════


class RewardAttributionEngine:
    """奖励归因引擎 — 将执行结果转换为可学习信号.

    用法:
        engine = RewardAttributionEngine()
        reward, attribution = engine.process(experience, metrics)

        # 或分步调用
        reward = engine.calculate_reward(experience, metrics)
        attribution = engine.attribute(experience, metrics)
    """

    def __init__(self) -> None:
        self._default_weights = RewardWeights.default()

    # ── Public API ──────────────────────────────────────────

    def calculate_reward(
        self,
        experience: LearningExperience,
        metrics: dict[str, float],
        weights: RewardWeights | None = None,
    ) -> LearningReward:
        """计算统一奖励.

        Args:
            experience: 学习经验 (含 outcome 信息)
            metrics: 现实指标 (roas_change, revenue_change, payer_change, etc.)
            weights: 奖励权重 (默认 Growth Agent)

        Returns:
            LearningReward: 统一奖励信号
        """
        w = weights or self._default_weights

        # ── 1. 业务奖励 ──
        business_reward = self._compute_business_reward(metrics)

        # ── 2. 执行奖励 ──
        execution_reward = self._compute_execution_reward(experience)

        # ── 3. 安全奖励 ──
        safety_reward = self._compute_safety_reward(experience)

        # ── 4. 效率奖励 ──
        efficiency_reward = self._compute_efficiency_reward(metrics)

        # ── 5. 加权总奖励 ──
        extra_reward = sum(
            w.extra.get(k, 0.0) * 0.0 for k in w.extra
        )
        total = (
            business_reward * w.business
            + execution_reward * w.execution
            + safety_reward * w.safety
            + efficiency_reward * w.efficiency
            + extra_reward
        )
        total_reward = round(max(-1.0, min(1.0, total)), 4)

        # ── 6. 置信度 ──
        confidence = self._compute_reward_confidence(metrics, experience)

        # ── 7. 等级判定 ──
        if total_reward > 0.15:
            level = "positive"
        elif total_reward < -0.15:
            level = "negative"
        else:
            level = "neutral"

        return LearningReward(
            total_reward=total_reward,
            business_reward=round(business_reward, 4),
            execution_reward=round(execution_reward, 4),
            safety_reward=round(safety_reward, 4),
            efficiency_reward=round(efficiency_reward, 4),
            confidence=round(confidence, 4),
            reward_level=level,
            weights=w,
            calculation_method="reward_attribution_engine",
            source_rewards={
                "decision_id": experience.decision_id,
                "execution_id": experience.execution_id,
            },
            components={
                "business_raw": round(business_reward, 4),
                "execution_raw": round(execution_reward, 4),
                "safety_raw": round(safety_reward, 4),
                "efficiency_raw": round(efficiency_reward, 4),
            },
        )

    def attribute(
        self,
        experience: LearningExperience,
        metrics: dict[str, float],
    ) -> AttributionResult:
        """归因分解 — 将 reward 分解为 Strategy/Creative/Audience/Timing.

        Args:
            experience: 学习经验 (含 context 信息)
            metrics: 现实指标

        Returns:
            AttributionResult: 归因结果 + 证据
        """
        # ── 1. 计算各维度贡献 ──
        creative = self._compute_creative_contribution(metrics)
        strategy = self._compute_strategy_contribution(experience)
        audience = self._compute_audience_contribution(experience)
        timing = self._compute_timing_contribution(experience)

        # ── 2. 归一化 ──
        total_abs = abs(creative) + abs(strategy) + abs(audience) + abs(timing)
        if total_abs > 0:
            creative_norm = round(creative / total_abs, 4)
            strategy_norm = round(strategy / total_abs, 4)
            audience_norm = round(audience / total_abs, 4)
            timing_norm = round(timing / total_abs, 4)
        else:
            creative_norm = strategy_norm = audience_norm = timing_norm = 0.0

        # ── 3. 主因判定 ──
        contributions = {
            "creative": creative_norm,
            "strategy": strategy_norm,
            "audience": audience_norm,
            "timing": timing_norm,
        }
        primary = max(contributions, key=lambda k: abs(contributions[k]))
        if abs(contributions[primary]) < 0.05:
            primary = "unexplained"

        # ── 4. 证据生成 ──
        evidence = self._generate_evidence(experience, metrics, primary)

        # ── 5. 置信度 ──
        confidence = self._compute_attribution_confidence(metrics, evidence)

        return AttributionResult(
            decision_id=experience.decision_id,
            total_reward=0.0,  # 由调用方在 process() 中填充
            strategy_contribution=strategy_norm,
            creative_contribution=creative_norm,
            audience_contribution=audience_norm,
            timing_contribution=timing_norm,
            unexplained=round(1.0 - (creative_norm + strategy_norm + audience_norm + timing_norm), 4),
            primary_factor=primary,
            confidence=round(confidence, 4),
            attribution_method="reward_attribution_engine",
            evidence=evidence,
        )

    def process(
        self,
        experience: LearningExperience,
        metrics: dict[str, float],
        weights: RewardWeights | None = None,
    ) -> tuple[LearningReward, AttributionResult]:
        """统一入口 — 计算 reward + attribution.

        Args:
            experience: 学习经验
            metrics: 现实指标
            weights: 奖励权重

        Returns:
            (LearningReward, AttributionResult)
        """
        reward = self.calculate_reward(experience, metrics, weights)
        attribution = self.attribute(experience, metrics)

        # 将 total_reward 回填到 attribution
        attribution.total_reward = reward.total_reward

        return reward, attribution

    # ── Private: Reward Computation ─────────────────────────

    def _compute_business_reward(self, metrics: dict[str, float]) -> float:
        """计算业务奖励.

        公式:
          business_reward = roas_score × 0.5 + revenue_score × 0.3 + payer_score × 0.2

        每项通过 tanh 归一化到 [-1, 1].
        """
        roas_change = metrics.get("roas_change", 0.0)
        revenue_change = metrics.get("revenue_change", 0.0)
        payer_change = metrics.get("payer_change", 0.0)

        roas_score = math.tanh(roas_change * 5.0)
        revenue_score = math.tanh(revenue_change * 5.0)
        payer_score = math.tanh(payer_change * 5.0)

        business = roas_score * 0.5 + revenue_score * 0.3 + payer_score * 0.2
        return round(max(-1.0, min(1.0, business)), 4)

    def _compute_execution_reward(self, experience: LearningExperience) -> float:
        """计算执行奖励.

        success → 1.0, failure → -1.0, 部分成功 → 线性插值.
        """
        rate = experience.outcome.execution_success_rate
        return round(2.0 * rate - 1.0, 4)

    def _compute_safety_reward(self, experience: LearningExperience) -> float:
        """计算安全奖励.

        blocked → -1.0, approval_required → -0.5, normal → 1.0.
        """
        if experience.outcome.was_blocked:
            return -1.0
        if experience.outcome.needed_approval:
            return -0.5
        return 1.0

    def _compute_efficiency_reward(self, metrics: dict[str, float]) -> float:
        """计算效率奖励.

        cost 下降 + time 下降 → 正向.
        """
        cost_change = metrics.get("cost_change", 0.0)
        time_change = metrics.get("time_change", 0.0)

        # cost 下降 = 正向, 上升 = 负向
        cost_score = math.tanh(-cost_change * 5.0)
        time_score = math.tanh(-time_change * 5.0)

        efficiency = cost_score * 0.5 + time_score * 0.5
        return round(max(-1.0, min(1.0, efficiency)), 4)

    # ── Private: Attribution Computation ────────────────────

    def _compute_creative_contribution(self, metrics: dict[str, float]) -> float:
        """计算素材贡献.

        公式:
          creative_score = tanh(ctr_change×5) × 0.5 + tanh(cvr_change×5) × 0.5
        """
        ctr_change = metrics.get("ctr_change", 0.0)
        cvr_change = metrics.get("cvr_change", 0.0)

        ctr_score = math.tanh(ctr_change * 5.0)
        cvr_score = math.tanh(cvr_change * 5.0)

        return ctr_score * 0.5 + cvr_score * 0.5

    def _compute_strategy_contribution(self, experience: LearningExperience) -> float:
        """计算策略贡献.

        基于策略置信度和历史成功率.
        """
        confidence = experience.confidence
        # 从 context 提取历史成功率
        success_rate = float(experience.context.get("strategy_success_rate", 0.5))
        return confidence * success_rate

    def _compute_audience_contribution(self, experience: LearningExperience) -> float:
        """计算受众贡献.

        基于受众匹配度 (从 context 提取).
        """
        audience_match = float(experience.context.get("audience_match", 0.5))
        return audience_match

    def _compute_timing_contribution(self, experience: LearningExperience) -> float:
        """计算时机贡献.

        基于市场窗口评分 (从 context 提取).
        """
        timing_factor = float(experience.context.get("timing_factor", 0.0))
        return timing_factor

    # ── Private: Confidence ─────────────────────────────────

    def _compute_reward_confidence(
        self, metrics: dict[str, float], experience: LearningExperience
    ) -> float:
        """计算奖励置信度.

        基于:
          - 指标完整度 (有多少个指标可用)
          - 样本量 (从 experience context 提取)
          - 决策置信度
        """
        # 指标完整度
        expected_metrics = {"roas_change", "revenue_change", "payer_change"}
        available = sum(1 for m in expected_metrics if metrics.get(m, 0.0) != 0.0)
        metric_completeness = available / max(len(expected_metrics), 1)

        # 样本量因子
        sample_size = float(experience.context.get("sample_size", 100))
        sample_factor = 1.0 - math.exp(-sample_size / 5000)

        # 综合
        confidence = (
            metric_completeness * 0.4
            + sample_factor * 0.3
            + experience.confidence * 0.3
        )
        return round(max(0.0, min(1.0, confidence)), 4)

    def _compute_attribution_confidence(
        self,
        metrics: dict[str, float],
        evidence: list[AttributionEvidence],
    ) -> float:
        """计算归因置信度.

        基于:
          - 证据数量
          - 指标可用性
          - 证据平均置信度
        """
        # 证据置信度
        if evidence:
            evidence_conf = sum(e.confidence for e in evidence) / len(evidence)
        else:
            evidence_conf = 0.3

        # 指标可用性
        has_ctr = abs(metrics.get("ctr_change", 0.0)) > 0.0
        has_cvr = abs(metrics.get("cvr_change", 0.0)) > 0.0
        metric_factor = (0.5 if has_ctr else 0.0) + (0.5 if has_cvr else 0.0)

        confidence = evidence_conf * 0.4 + metric_factor * 0.4 + 0.2
        return round(max(0.0, min(1.0, confidence)), 4)

    # ── Private: Evidence ───────────────────────────────────

    def _generate_evidence(
        self,
        experience: LearningExperience,
        metrics: dict[str, float],
        primary_factor: str,
    ) -> list[AttributionEvidence]:
        """生成归因证据列表.

        为每个有数据的维度生成可追溯证据.
        """
        evidence: list[AttributionEvidence] = []

        # 素材证据
        ctr_change = metrics.get("ctr_change", 0.0)
        cvr_change = metrics.get("cvr_change", 0.0)
        if abs(ctr_change) > 0.0 or abs(cvr_change) > 0.0:
            evidence.append(
                AttributionEvidence(
                    metric_source="creative_metrics",
                    source_ids=[experience.decision_id],
                    data_window=self._extract_data_window(experience),
                    confidence=round(0.5 + 0.3 * min(1.0, abs(ctr_change) + abs(cvr_change)), 4),
                    description=(
                        f"CTR {'+' if ctr_change >= 0 else ''}{ctr_change:.1%}, "
                        f"CVR {'+' if cvr_change >= 0 else ''}{cvr_change:.1%}"
                    ),
                )
            )

        # 策略证据
        strategy_rate = float(experience.context.get("strategy_success_rate", 0.0))
        if strategy_rate > 0.0:
            evidence.append(
                AttributionEvidence(
                    metric_source="strategy_history",
                    source_ids=[experience.decision_id],
                    data_window=self._extract_data_window(experience),
                    confidence=round(min(0.9, strategy_rate + 0.1), 4),
                    description=f"Strategy historical success rate: {strategy_rate:.1%}",
                )
            )

        # 受众证据
        audience_match = float(experience.context.get("audience_match", 0.0))
        if audience_match > 0.0:
            evidence.append(
                AttributionEvidence(
                    metric_source="audience_analysis",
                    source_ids=[experience.decision_id],
                    data_window=self._extract_data_window(experience),
                    confidence=round(min(0.9, audience_match + 0.1), 4),
                    description=f"Audience match score: {audience_match:.2f}",
                )
            )

        # 时机证据
        timing_factor = float(experience.context.get("timing_factor", 0.0))
        if abs(timing_factor) > 0.0:
            evidence.append(
                AttributionEvidence(
                    metric_source="market_timing",
                    source_ids=[experience.decision_id],
                    data_window=self._extract_data_window(experience),
                    confidence=round(min(0.9, abs(timing_factor) + 0.1), 4),
                    description=f"Timing factor: {timing_factor:+.2f}",
                )
            )

        return evidence

    def _extract_data_window(self, experience: LearningExperience) -> str:
        """从 experience 提取数据窗口."""
        window = experience.context.get("data_window", "")
        if window:
            return str(window)
        # 默认: 创建日期前后 7 天
        if experience.created_at:
            date = experience.created_at[:10]  # "2026-07-30"
            return f"{date}~D+7"
        return "unknown"


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════


__all__ = [
    "RewardAttributionEngine",
]