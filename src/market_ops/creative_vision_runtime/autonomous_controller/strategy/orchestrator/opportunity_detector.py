"""E11.9 — Opportunity Detector。

职责：回答"为什么现在需要进化？"

输入：
  - Market Signal (performance metrics)
  - Knowledge Graph (historical patterns)
  - Population State (diversity, etc.)

输出：
  - EvolutionOpportunity 列表

检测类型：
  - CREATIVE_FATIGUE:    CTR/CVR 持续下降
  - PERFORMANCE_DROP:    关键指标显著下降
  - DIVERSITY_COLLAPSE:  种群多样性塌缩
  - KNOWLEDGE_GAP:       知识图谱置信度低
  - NEW_WINNER_PATTERN:  发现新赢家模式
  - UNDEREXPLOITED_DNA:  高潜力但未充分探索
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionOpportunity,
    OpportunityType,
)

logger = logging.getLogger(__name__)

# 检测阈值
FATIGUE_CTR_DROP = -0.15       # CTR 下降 15%
FATIGUE_IMPRESSION_RISE = 0.3  # 曝光量上升 30%（频率增加）
PERFORMANCE_DROP_THRESHOLD = -0.20  # 关键指标下降 20%
DIVERSITY_COLLAPSE_THRESHOLD = 0.2  # 多样性 < 0.2
KNOWLEDGE_GAP_CONFIDENCE = 0.3      # 知识置信度 < 0.3


class OpportunityDetector:
    """机会检测器。

    从多源输入检测进化机会。

    Attributes:
        fatigue_ctr_drop:        创意疲劳 CTR 下降阈值
        fatigue_impression_rise: 创意疲劳曝光量上升阈值
        performance_drop:        性能下降阈值
        diversity_threshold:     多样性塌缩阈值
        knowledge_confidence:    知识空白置信度阈值
    """

    def __init__(
        self,
        fatigue_ctr_drop: float = FATIGUE_CTR_DROP,
        fatigue_impression_rise: float = FATIGUE_IMPRESSION_RISE,
        performance_drop: float = PERFORMANCE_DROP_THRESHOLD,
        diversity_threshold: float = DIVERSITY_COLLAPSE_THRESHOLD,
        knowledge_confidence: float = KNOWLEDGE_GAP_CONFIDENCE,
    ) -> None:
        self._fatigue_ctr_drop = fatigue_ctr_drop
        self._fatigue_impression_rise = fatigue_impression_rise
        self._performance_drop = performance_drop
        self._diversity_threshold = diversity_threshold
        self._knowledge_confidence = knowledge_confidence

    # ── 主入口 ──────────────────────────────────────────

    def detect(
        self,
        market_signal: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> list[EvolutionOpportunity]:
        """检测所有进化机会。

        Args:
            market_signal: 市场信号（含 metrics, trends）
            knowledge:     知识图谱数据
            population:    种群状态

        Returns:
            EvolutionOpportunity 列表（按 score 降序）
        """
        opportunities: list[EvolutionOpportunity] = []

        market_signal = market_signal or {}
        knowledge = knowledge or {}
        population = population or {}

        # 1. 创意疲劳检测
        opp = self._detect_fatigue(market_signal)
        if opp:
            opportunities.append(opp)

        # 2. 性能下降检测
        opp = self._detect_performance_drop(market_signal)
        if opp:
            opportunities.append(opp)

        # 3. 多样性塌缩检测
        opp = self._detect_diversity_collapse(population)
        if opp:
            opportunities.append(opp)

        # 4. 知识空白检测
        opp = self._detect_knowledge_gap(knowledge)
        if opp:
            opportunities.append(opp)

        # 5. 未充分探索检测
        opp = self._detect_underexploited(knowledge, population)
        if opp:
            opportunities.append(opp)

        # 按 score 降序
        opportunities.sort(key=lambda o: o.score, reverse=True)

        return opportunities

    def detect_top(
        self,
        market_signal: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> EvolutionOpportunity | None:
        """检测最高优先级机会。"""
        opportunities = self.detect(market_signal, knowledge, population)
        return opportunities[0] if opportunities else None

    # ── 检测逻辑 ─────────────────────────────────────────

    def _detect_fatigue(
        self, signal: dict[str, Any]
    ) -> EvolutionOpportunity | None:
        """检测创意疲劳。

        条件：
          - CTR 下降超过阈值
          - 曝光量上升（频率增加）
        """
        metrics = signal.get("metrics", {})
        trends = signal.get("trends", {})

        ctr_trend = trends.get("CTR", 0.0)
        impression_trend = trends.get("impressions", 0.0)
        ctr_current = metrics.get("CTR", 0.0)
        usage_count = signal.get("usage_count", 0)

        evidence: list[str] = []
        score = 0.0

        if ctr_trend < self._fatigue_ctr_drop:
            evidence.append(f"CTR trend {ctr_trend:.1%}")
            score += 0.4

        if impression_trend > self._fatigue_impression_rise:
            evidence.append(f"Impression trend {impression_trend:.1%}")
            score += 0.3

        if usage_count > 30:
            evidence.append(f"High usage count: {usage_count}")
            score += 0.2

        if ctr_current > 0 and ctr_current < 0.02:
            evidence.append(f"Low CTR: {ctr_current:.3f}")
            score += 0.1

        if evidence:
            score = min(1.0, score)
            return EvolutionOpportunity(
                type=OpportunityType.CREATIVE_FATIGUE,
                score=round(score, 3),
                evidence=evidence,
                metrics=metrics,
            )

        return None

    def _detect_performance_drop(
        self, signal: dict[str, Any]
    ) -> EvolutionOpportunity | None:
        """检测性能下降。

        条件：
          - ROI/CTR/CVR 任一指标下降超过阈值
        """
        metrics = signal.get("metrics", {})
        trends = signal.get("trends", {})

        evidence: list[str] = []
        score = 0.0

        for metric in ("ROI", "CTR", "CVR"):
            trend = trends.get(metric, 0.0)
            if trend < self._performance_drop:
                evidence.append(f"{metric} drop: {trend:.1%}")
                score += 0.3

        if evidence:
            score = min(1.0, score)
            return EvolutionOpportunity(
                type=OpportunityType.PERFORMANCE_DROP,
                score=round(score, 3),
                evidence=evidence,
                metrics=metrics,
            )

        return None

    def _detect_diversity_collapse(
        self, population: dict[str, Any]
    ) -> EvolutionOpportunity | None:
        """检测多样性塌缩。"""
        diversity = population.get("diversity_score", 0.5)

        if diversity < self._diversity_threshold:
            score = min(1.0, (self._diversity_threshold - diversity) * 5)
            return EvolutionOpportunity(
                type=OpportunityType.DIVERSITY_COLLAPSE,
                score=round(score, 3),
                evidence=[f"Diversity score: {diversity:.2f} (threshold: {self._diversity_threshold})"],
                metrics={"diversity": diversity},
            )

        return None

    def _detect_knowledge_gap(
        self, knowledge: dict[str, Any]
    ) -> EvolutionOpportunity | None:
        """检测知识空白。

        条件：
          - 整体知识置信度低
          - 某些 mutation 类型数据不足
        """
        overall = knowledge.get("overall_confidence", 0.5)
        perf = knowledge.get("mutation_performance", {})

        evidence: list[str] = []
        score = 0.0

        if overall < self._knowledge_confidence:
            evidence.append(f"Low overall confidence: {overall:.2f}")
            score += 0.5

        # 检查是否有数据不足的 mutation 类型
        for mt, data in perf.items():
            if data.get("sample_count", 0) < 5:
                evidence.append(f"Low samples for {mt}: {data.get('sample_count', 0)}")
                score += 0.2

        if evidence:
            score = min(1.0, score)
            return EvolutionOpportunity(
                type=OpportunityType.KNOWLEDGE_GAP,
                score=round(score, 3),
                evidence=evidence,
                metrics={"overall_confidence": overall},
            )

        return None

    def _detect_underexploited(
        self,
        knowledge: dict[str, Any],
        population: dict[str, Any],
    ) -> EvolutionOpportunity | None:
        """检测未充分探索的 DNA。

        条件：
          - 某些 mutation 类型成功率高中但探索次数少
        """
        perf = knowledge.get("mutation_performance", {})

        evidence: list[str] = []
        score = 0.0

        for mt, data in perf.items():
            success_rate = data.get("success_rate", 0.0)
            sample_count = data.get("sample_count", 0)

            # 高成功率但低样本量 → 未充分探索
            if success_rate > 0.6 and sample_count < 10:
                evidence.append(
                    f"{mt}: success_rate={success_rate:.0%}, "
                    f"samples={sample_count}"
                )
                score += 0.3

        if evidence:
            score = min(1.0, score)
            return EvolutionOpportunity(
                type=OpportunityType.UNDEREXPLOITED_DNA,
                score=round(score, 3),
                evidence=evidence,
            )

        return None

    def __repr__(self) -> str:
        return f"OpportunityDetector()"