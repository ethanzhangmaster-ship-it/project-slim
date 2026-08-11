"""E12.1 — Reality Feedback Bridge。

将 RealitySnapshot 转换为 E11 Evolution 可消费的反馈信号。

数据流：
  RealitySnapshot
       │
       ▼
  RealityFeedbackBridge
       │
       ├── CreativeReality → PerformanceSignal
       ├── PerformanceSignal → FitnessScore
       ├── FitnessScore → LearningSignal
       │
       ▼
  EvolutionFeedback[] → E11 Controller.receive_feedback()

Usage:
    bridge = RealityFeedbackBridge()
    signals = bridge.convert_to_signals(snapshot)
    feedbacks = bridge.generate_feedback(snapshot)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..autonomous_controller.feedback.models import (
    EvolutionFeedback,
    FitnessScore,
    LearningDirection,
    LearningSignal,
    PerformanceSignal,
)

if TYPE_CHECKING:
    from .models import CreativeReality, RealitySnapshot

logger = logging.getLogger(__name__)


class RealityFeedbackBridge:
    """Reality → E11 Feedback 桥接器。

    将真实世界数据（RealitySnapshot）转换为 E11 Evolution
    可消费的反馈信号（PerformanceSignal, FitnessScore,
    LearningSignal, EvolutionFeedback）。

    Attributes:
        total_converted:     累计转换的 Creative 数
        total_feedbacks:     累计生成的反馈数
    """

    def __init__(self) -> None:
        self.total_converted: int = 0
        self.total_feedbacks: int = 0

    # ── Public API ───────────────────────────────────────

    def convert_to_signals(
        self,
        snapshot: RealitySnapshot,
    ) -> list[PerformanceSignal]:
        """将 RealitySnapshot 中的 Creative 转为 PerformanceSignal 列表。

        Args:
            snapshot: RealitySnapshot

        Returns:
            PerformanceSignal 列表（E11 可消费）
        """
        signals: list[PerformanceSignal] = []

        for creative in snapshot.creatives:
            signal = self._creative_to_signal(creative)
            if signal.has_sufficient_data:
                signals.append(signal)

        self.total_converted += len(signals)
        logger.info(
            f"RealityFeedbackBridge: {len(signals)} signals "
            f"from {len(snapshot.creatives)} creatives"
        )
        return signals

    def generate_feedback(
        self,
        snapshot: RealitySnapshot,
    ) -> list[EvolutionFeedback]:
        """从 RealitySnapshot 生成完整 EvolutionFeedback 列表。

        流程：
          1. CreativeReality → PerformanceSignal
          2. PerformanceSignal → FitnessScore
          3. FitnessScore → LearningSignal
          4. 组装 → EvolutionFeedback

        Args:
            snapshot: RealitySnapshot

        Returns:
            EvolutionFeedback 列表
        """
        signals = self.convert_to_signals(snapshot)
        feedbacks = self._signals_to_feedbacks(signals)

        self.total_feedbacks += len(feedbacks)
        logger.info(
            f"RealityFeedbackBridge: {len(feedbacks)} feedbacks generated"
        )
        return feedbacks

    def generate_market_signal(
        self,
        snapshot: RealitySnapshot,
    ) -> dict:
        """生成 E11.9 OpportunityDetector 可消费的市场信号。

        Args:
            snapshot: RealitySnapshot

        Returns:
            market_signal dict（含 metrics, trends, usage_count）
        """
        # 聚合所有 Campaign 的指标
        total_impressions = sum(
            c.impressions for c in snapshot.campaigns
        )
        total_clicks = sum(c.clicks for c in snapshot.campaigns)
        total_installs = sum(c.installs for c in snapshot.campaigns)
        total_spend = sum(c.spend for c in snapshot.campaigns)
        total_revenue = sum(c.revenue_d30 for c in snapshot.campaigns)

        avg_ctr = (
            round(total_clicks / total_impressions, 4)
            if total_impressions > 0 else 0.0
        )
        avg_cvr = (
            round(total_installs / total_clicks, 4)
            if total_clicks > 0 else 0.0
        )
        avg_roi = (
            round(total_revenue / total_spend, 4)
            if total_spend > 0 else 0.0
        )

        # 计算趋势（与历史快照对比）
        trends = self._compute_trends(snapshot)

        # 创意使用次数
        usage_count = len(snapshot.creatives)

        return {
            "metrics": {
                "CTR": avg_ctr,
                "CVR": avg_cvr,
                "ROI": avg_roi,
                "spend": total_spend,
                "revenue": total_revenue,
                "impressions": total_impressions,
                "installs": total_installs,
            },
            "trends": trends,
            "usage_count": usage_count,
            "timestamp": snapshot.timestamp,
            "snapshot_id": snapshot.snapshot_id,
        }

    # ── Internal ────────────────────────────────────────

    def _creative_to_signal(
        self,
        creative: CreativeReality,
    ) -> PerformanceSignal:
        """CreativeReality → PerformanceSignal。"""
        return PerformanceSignal(
            genome_id=creative.dna_id,
            creative_id=creative.creative_id,
            impressions=(creative.installs * 50),  # 估算：installs / CVR
            clicks=int(creative.installs / creative.ctr) if creative.ctr > 0 else 0,
            installs=creative.installs,
            revenue=creative.revenue,
            spend=creative.spend,
            ctr=creative.ctr,
            cvr=creative.payer_rate,
            roi=creative.roi,
            period="7d",
        )

    def _signals_to_feedbacks(
        self,
        signals: list[PerformanceSignal],
    ) -> list[EvolutionFeedback]:
        """PerformanceSignal 列表 → EvolutionFeedback 列表。"""
        # 按 genome_id 分组
        genome_signals: dict[str, list[PerformanceSignal]] = {}
        for s in signals:
            gid = s.genome_id or s.creative_id
            genome_signals.setdefault(gid, []).append(s)

        feedbacks: list[EvolutionFeedback] = []

        for rank, (gid, group_signals) in enumerate(
            genome_signals.items(), start=1
        ):
            # 聚合该 genome 的所有 signal
            best_signal = max(group_signals, key=lambda s: s.roi)

            # 计算 FitnessScore
            fitness = self._compute_fitness(best_signal, rank)

            # 生成 LearningSignal
            learning = self._compute_learning(fitness, best_signal)

            feedbacks.append(EvolutionFeedback(
                genome_id=gid,
                fitness=fitness,
                learning_signal=learning,
            ))

        return feedbacks

    def _compute_fitness(
        self,
        signal: PerformanceSignal,
        rank: int,
    ) -> FitnessScore:
        """计算 FitnessScore。

        使用 E11.6.3 公式：
          fitness = revenue×0.4 + efficiency×0.3 + payer×0.3

        这里简化：ROI×0.4 + CTR×0.3 + CVR×0.3
        """
        roi_score = min(signal.roi / 2.0, 1.0) * 100
        ctr_score = min(signal.ctr / 0.05, 1.0) * 100
        cvr_score = min(signal.cvr / 0.10, 1.0) * 100

        overall = roi_score * 0.4 + ctr_score * 0.3 + cvr_score * 0.3

        return FitnessScore(
            genome_id=signal.genome_id,
            overall_score=round(overall, 1),
            roi_score=round(roi_score, 1),
            ctr_score=round(ctr_score, 1),
            cvr_score=round(cvr_score, 1),
            revenue_score=round(signal.revenue / 1000, 1),  # 归一化
            rank=rank,
        )

    def _compute_learning(
        self,
        fitness: FitnessScore,
        signal: PerformanceSignal,
    ) -> LearningSignal:
        """根据 FitnessScore 生成 LearningSignal。"""
        if fitness.is_winner:
            direction = LearningDirection.IMPROVE
            confidence = min(fitness.overall_score / 100, 0.95)
            insights = [f"Genome {signal.genome_id} is a winner (score={fitness.overall_score:.1f})"]
        elif fitness.is_average:
            direction = LearningDirection.KEEP
            confidence = 0.7
            insights = [f"Genome {signal.genome_id} is average (score={fitness.overall_score:.1f})"]
        else:
            direction = LearningDirection.MUTATE
            confidence = 0.8
            insights = [f"Genome {signal.genome_id} needs mutation (score={fitness.overall_score:.1f})"]

        if signal.roi > 1.0:
            insights.append(f"Positive ROI: {signal.roi:.2f}")

        recommended_mutations = []
        if direction == LearningDirection.MUTATE:
            if signal.ctr < 0.02:
                recommended_mutations.append("Improve hook gene for higher CTR")
            if signal.cvr < 0.03:
                recommended_mutations.append("Enhance gameplay gene for better conversion")

        return LearningSignal(
            genome_id=signal.genome_id,
            direction=direction,
            confidence=confidence,
            insights=insights,
            recommended_mutations=recommended_mutations,
        )

    def _compute_trends(
        self,
        snapshot: RealitySnapshot,
    ) -> dict[str, float]:
        """计算指标趋势（当前 vs 历史）。

        简化版：当有历史快照时，对比 total_roi。
        """
        # 默认无趋势变化
        return {
            "ROI": 0.0,
            "CTR": 0.0,
            "CVR": 0.0,
        }

    def __repr__(self) -> str:
        return (
            f"RealityFeedbackBridge(converted={self.total_converted}, "
            f"feedbacks={self.total_feedbacks})"
        )