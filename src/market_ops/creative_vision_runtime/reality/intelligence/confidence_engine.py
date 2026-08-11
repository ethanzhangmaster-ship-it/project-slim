"""E12.2 — Confidence Engine。

计算洞察的可信度，确保 E12 不会因数据不足而误触发 E11。

置信度公式：
  confidence = data_quality × signal_strength × historical_accuracy

其中：
  - data_quality:      数据质量（样本量、数据完整性）
  - signal_strength:   信号强度（变化幅度、持续性）
  - historical_accuracy: 历史准确率（可选）

Usage:
    ce = ConfidenceEngine()
    confidence = ce.compute(insight, data_quality=0.8, signal_strength=0.9)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RealityInsight

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """置信度计算引擎。

    综合数据质量、信号强度、历史准确率计算最终置信度。

    Attributes:
        total_computed:  累计计算次数
        historical_accuracy: 历史准确率（可为 None）
    """

    # 默认权重
    WEIGHT_DATA_QUALITY = 0.35
    WEIGHT_SIGNAL_STRENGTH = 0.45
    WEIGHT_HISTORICAL = 0.20

    def __init__(self, historical_accuracy: float | None = None) -> None:
        self.total_computed: int = 0
        self.historical_accuracy = historical_accuracy

    # ── Public API ───────────────────────────────────────

    def compute(
        self,
        insight: RealityInsight,
        data_quality: float | None = None,
        signal_strength: float | None = None,
    ) -> float:
        """计算洞察的置信度。

        Args:
            insight:         待评估的洞察
            data_quality:    数据质量（0-1），None 时自动估算
            signal_strength: 信号强度（0-1），None 时自动估算

        Returns:
            置信度（0-1）
        """
        # 自动估算
        if data_quality is None:
            data_quality = self._estimate_data_quality(insight)

        if signal_strength is None:
            signal_strength = self._estimate_signal_strength(insight)

        # 历史准确率
        historical = self.historical_accuracy or 0.0

        # 加权计算
        confidence = (
            data_quality * self.WEIGHT_DATA_QUALITY
            + signal_strength * self.WEIGHT_SIGNAL_STRENGTH
            + historical * self.WEIGHT_HISTORICAL
        )

        self.total_computed += 1
        return round(min(confidence, 1.0), 4)

    def compute_batch(
        self,
        insights: list[RealityInsight],
        data_quality: float | None = None,
        signal_strength: float | None = None,
    ) -> list[float]:
        """批量计算置信度。"""
        return [
            self.compute(i, data_quality, signal_strength)
            for i in insights
        ]

    def is_reliable(self, confidence: float) -> bool:
        """置信度是否足够可靠。"""
        return confidence >= 0.7

    def is_highly_reliable(self, confidence: float) -> bool:
        """置信度是否高度可靠。"""
        return confidence >= 0.85

    # ── Internal ────────────────────────────────────────

    def _estimate_data_quality(self, insight: RealityInsight) -> float:
        """根据洞察估算数据质量。

        证据越多 → 数据质量越高。
        """
        evidence_count = len(insight.evidence)

        if evidence_count >= 3:
            return 0.9
        elif evidence_count >= 2:
            return 0.75
        elif evidence_count >= 1:
            return 0.5
        return 0.2

    def _estimate_signal_strength(self, insight: RealityInsight) -> float:
        """根据严重程度和优先级估算信号强度。"""
        severity_score = {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.5,
            "low": 0.2,
        }
        sev = severity_score.get(insight.severity.value, 0.3)

        # 综合严重程度和优先级
        return (sev * 0.6 + insight.priority * 0.4)

    def __repr__(self) -> str:
        return f"ConfidenceEngine(computed={self.total_computed})"