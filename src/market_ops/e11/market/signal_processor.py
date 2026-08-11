"""E11.5.2 Signal Processor — 市场信号处理器。

将 PerformanceFeedback 转换为 MarketSignal，提炼出可驱动
Genome 进化的学习信号。

流程：
  PerformanceFeedback
      → Metric Extraction
      → Normalization
      → Signal Generation
      → MarketSignal

核心逻辑：
  - 评估各维度信号（付费/LTV/留存/获客）
  - 映射到 Creative DNA 基因槽位
  - 计算置信度
  - 输出 MarketSignal

数据流：
  PerformanceFeedback → MarketSignalProcessor.process() → MarketSignal
"""

from __future__ import annotations

from .feedback_schema import PerformanceFeedback
from .market_signal_schema import (
    MarketSignal,
    SignalType,
    SignalStrength,
)
from .signal_rules import (
    evaluate_monetization_signal,
    evaluate_ltv_signal,
    evaluate_retention_signal,
    evaluate_acquisition_signal,
    evaluate_overall_quality,
    evaluate_cpi_signal,
    evaluate_install_cvr_signal,
    evaluate_d1_retention_signal,
    evaluate_engagement_signal,
    evaluate_arpu_signal,
    evaluate_d7_ltv_signal,
    map_to_creative_genes,
    compute_confidence,
)


class MarketSignalProcessor:
    """市场信号处理器。

    将 PerformanceFeedback 中的原始数据提炼为 MarketSignal。

    Usage:
        processor = MarketSignalProcessor()
        signal = processor.process(feedback, genome_id="genome_001")
        # signal.quality_score, signal.signals, signal.confidence
    """

    def __init__(self) -> None:
        pass

    # ── 主入口 ────────────────────────────────────────

    def process(
        self,
        feedback: PerformanceFeedback,
        genome_id: str = "",
    ) -> MarketSignal:
        """处理 PerformanceFeedback 生成 MarketSignal。

        Args:
            feedback: PerformanceFeedback 实例
            genome_id: 关联的 Genome ID

        Returns:
            MarketSignal
        """
        # 1. 综合质量评分
        quality_score = evaluate_overall_quality(feedback)

        # 2. DNA 信号映射
        signals = map_to_creative_genes(feedback)

        # 3. 信号组成
        signal_composition = self._build_composition(feedback)

        # 4. 置信度
        confidence, sample_size = compute_confidence(feedback)

        return MarketSignal(
            creative_id=feedback.creative_id,
            genome_id=genome_id,
            quality_score=quality_score,
            signals=signals,
            signal_composition=signal_composition,
            confidence=confidence,
            sample_size=sample_size,
        )

    # ── 信号组成 ──────────────────────────────────────

    def _build_composition(
        self,
        feedback: PerformanceFeedback,
    ) -> dict[str, str]:
        """构建信号组成摘要。

        Returns:
            {
                "acquisition": "strong" | "medium" | "weak" | "none",
                "engagement": "strong" | "medium" | "weak" | "none",
                "monetization": "very_strong" | "strong" | "medium" | "weak" | "none",
            }
        """
        composition: dict[str, str] = {}

        # 获客信号
        acq_score = evaluate_acquisition_signal(feedback.ua_metrics)
        composition["acquisition"] = SignalStrength.from_score(acq_score).value

        # 留存信号
        eng_score = evaluate_retention_signal(feedback.engagement_metrics)
        composition["engagement"] = SignalStrength.from_score(eng_score).value

        # 付费信号
        mon_score = evaluate_monetization_signal(feedback.monetization_metrics)
        composition["monetization"] = SignalStrength.from_score(mon_score).value

        return composition

    # ── 便捷方法 ──────────────────────────────────────

    def process_batch(
        self,
        feedbacks: list[PerformanceFeedback],
        genome_id: str = "",
    ) -> list[MarketSignal]:
        """批量处理反馈。

        Args:
            feedbacks: PerformanceFeedback 列表
            genome_id: 关联的 Genome ID

        Returns:
            MarketSignal 列表
        """
        return [self.process(fb, genome_id=genome_id) for fb in feedbacks]

    def __repr__(self) -> str:
        return "MarketSignalProcessor()"