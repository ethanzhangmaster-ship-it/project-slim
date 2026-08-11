"""E12.2 — Creative Fatigue Detector。

检测创意疲劳，综合以下信号：
  - CTR 衰减率（当前 vs 峰值）
  - ROAS 衰减率（当前 vs 峰值）
  - 曝光频次（frequency）
  - 上线天数（days_since_launch）

输出 FatigueInsight + RealityInsight。

Usage:
    detector = FatigueDetector()
    fatigue = detector.detect(creative_reality, peak_ctr=0.05, peak_roas=2.0)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..intelligence.models import (
    FatigueInsight,
    InsightType,
    RealityInsight,
    SeverityLevel,
)

if TYPE_CHECKING:
    from ..models import CreativeReality, RealitySnapshot

logger = logging.getLogger(__name__)


class FatigueDetector:
    """创意疲劳检测器。

    综合 CTR 衰减、ROAS 衰减、频次、上线天数，
    计算疲劳评分并生成洞察。

    Attributes:
        total_detected:  累计检测次数
        total_fatigued:  累计疲劳创意数
    """

    # 阈值配置
    CTR_DECAY_THRESHOLD = 0.30       # CTR 衰减 30% → 疲劳信号
    ROAS_DECAY_THRESHOLD = 0.30      # ROAS 衰减 30% → 疲劳信号
    FREQUENCY_THRESHOLD = 5.0        # 频次 > 5 → 可能疲劳
    FREQUENCY_HIGH = 10.0            # 频次 > 10 → 严重疲劳
    DAYS_THRESHOLD = 7               # 上线 > 7 天 → 开始监测
    DAYS_HIGH = 30                   # 上线 > 30 天 → 高疲劳风险

    # 疲劳评分权重
    WEIGHT_CTR = 0.35
    WEIGHT_ROAS = 0.35
    WEIGHT_FREQUENCY = 0.20
    WEIGHT_DAYS = 0.10

    def __init__(self) -> None:
        self.total_detected: int = 0
        self.total_fatigued: int = 0

    # ── Public API ───────────────────────────────────────

    def detect(
        self,
        creative: CreativeReality,
        peak_ctr: float | None = None,
        peak_roas: float | None = None,
        frequency: float = 0.0,
        days_since_launch: int = 0,
    ) -> FatigueInsight:
        """检测单个 Creative 的疲劳程度。

        Args:
            creative:          Creative 现实数据
            peak_ctr:          历史峰值 CTR（None 时用当前值）
            peak_roas:         历史峰值 ROAS（None 时用当前值）
            frequency:         曝光频次
            days_since_launch: 上线天数

        Returns:
            FatigueInsight
        """
        evidence: list[str] = []

        # 1. CTR 衰减
        ctr_decay = self._compute_decay(creative.ctr, peak_ctr)
        ctr_score = self._decay_score(ctr_decay, self.CTR_DECAY_THRESHOLD)
        if ctr_decay >= self.CTR_DECAY_THRESHOLD:
            evidence.append(
                f"CTR decayed {ctr_decay:.0%}: "
                f"peak={peak_ctr:.4f}, current={creative.ctr:.4f}"
            )

        # 2. ROAS 衰减
        roas_decay = self._compute_decay(creative.roas_d30, peak_roas)
        roas_score = self._decay_score(roas_decay, self.ROAS_DECAY_THRESHOLD)
        if roas_decay >= self.ROAS_DECAY_THRESHOLD:
            evidence.append(
                f"ROAS decayed {roas_decay:.0%}: "
                f"peak={peak_roas:.4f}, current={creative.roas_d30:.4f}"
            )

        # 3. 频次
        freq_score = self._frequency_score(frequency)
        if frequency >= self.FREQUENCY_THRESHOLD:
            evidence.append(f"High frequency: {frequency:.1f}")

        # 4. 上线天数
        days_score = self._days_score(days_since_launch)
        if days_since_launch >= self.DAYS_THRESHOLD:
            evidence.append(f"Days since launch: {days_since_launch}")

        # 综合评分
        fatigue_score = (
            ctr_score * self.WEIGHT_CTR
            + roas_score * self.WEIGHT_ROAS
            + freq_score * self.WEIGHT_FREQUENCY
            + days_score * self.WEIGHT_DAYS
        )

        # 严重程度
        severity = self._fatigue_severity(fatigue_score)

        # 置信度：基于数据充分性
        confidence = self._confidence(
            creative=creative,
            has_peak_ctr=peak_ctr is not None,
            has_peak_roas=peak_roas is not None,
        )

        self.total_detected += 1
        if fatigue_score >= 0.6:
            self.total_fatigued += 1

        return FatigueInsight(
            creative_id=creative.creative_id,
            fatigue_score=round(fatigue_score, 4),
            ctr_decay=round(ctr_decay, 4),
            roas_decay=round(roas_decay, 4),
            frequency=round(frequency, 2),
            days_since_launch=days_since_launch,
            evidence=evidence,
            severity=severity,
            confidence=round(confidence, 4),
        )

    def detect_batch(
        self,
        snapshot: RealitySnapshot,
        peak_data: dict[str, dict] | None = None,
    ) -> list[FatigueInsight]:
        """批量检测快照中所有 Creative 的疲劳。

        Args:
            snapshot:  RealitySnapshot
            peak_data: {creative_id: {"peak_ctr": float, "peak_roas": float, "frequency": float, "days": int}}

        Returns:
            FatigueInsight 列表
        """
        results: list[FatigueInsight] = []
        peaks = peak_data or {}

        for creative in snapshot.creatives:
            peak = peaks.get(creative.creative_id, {})
            result = self.detect(
                creative=creative,
                peak_ctr=peak.get("peak_ctr"),
                peak_roas=peak.get("peak_roas"),
                frequency=peak.get("frequency", 0.0),
                days_since_launch=peak.get("days_since_launch", 0),
            )
            results.append(result)

        return results

    def to_insights(
        self,
        fatigue_results: list[FatigueInsight],
        snapshot_id: str = "",
    ) -> list[RealityInsight]:
        """将 FatigueInsight 转换为 RealityInsight。

        Args:
            fatigue_results: FatigueInsight 列表
            snapshot_id:     来源快照 ID

        Returns:
            RealityInsight 列表
        """
        insights: list[RealityInsight] = []

        for f in fatigue_results:
            if not f.is_fatigued:
                continue

            # 确定推荐行动
            if f.is_severely_fatigued:
                action = "MUTATE_HOOK_AND_VISUAL"
                priority = f.fatigue_score
            elif f.ctr_decay >= self.CTR_DECAY_THRESHOLD:
                action = "MUTATE_HOOK"
                priority = f.fatigue_score * 0.8
            elif f.roas_decay >= self.ROAS_DECAY_THRESHOLD:
                action = "MUTATE_MONETIZATION"
                priority = f.fatigue_score * 0.8
            else:
                action = "MONITOR"
                priority = f.fatigue_score * 0.5

            insights.append(RealityInsight(
                type=InsightType.CREATIVE_FATIGUE,
                severity=f.severity,
                confidence=f.confidence,
                target=f.creative_id,
                evidence=f.evidence,
                recommended_action=action,
                priority=priority,
                source_snapshot_id=snapshot_id,
                metadata={
                    "fatigue_score": f.fatigue_score,
                    "ctr_decay": f.ctr_decay,
                    "roas_decay": f.roas_decay,
                },
            ))

        return insights

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _compute_decay(current: float, peak: float | None) -> float:
        """计算衰减率。"""
        if peak is None or peak <= 0:
            return 0.0
        if current >= peak:
            return 0.0
        return (peak - current) / peak

    @staticmethod
    def _decay_score(decay: float, threshold: float) -> float:
        """衰减率 → 评分。"""
        if decay >= threshold * 2:
            return 1.0
        elif decay >= threshold:
            return 0.5 + (decay - threshold) / threshold * 0.5
        elif decay > 0:
            return decay / threshold * 0.5
        return 0.0

    @staticmethod
    def _frequency_score(frequency: float) -> float:
        """频次 → 评分。"""
        if frequency >= FatigueDetector.FREQUENCY_HIGH:
            return 1.0
        elif frequency >= FatigueDetector.FREQUENCY_THRESHOLD:
            return 0.5 + (frequency - FatigueDetector.FREQUENCY_THRESHOLD) / (
                FatigueDetector.FREQUENCY_HIGH - FatigueDetector.FREQUENCY_THRESHOLD
            ) * 0.5
        elif frequency > 0:
            return frequency / FatigueDetector.FREQUENCY_THRESHOLD * 0.5
        return 0.0

    @staticmethod
    def _days_score(days: int) -> float:
        """上线天数 → 评分。"""
        if days >= FatigueDetector.DAYS_HIGH:
            return 1.0
        elif days >= FatigueDetector.DAYS_THRESHOLD:
            return 0.5 + (days - FatigueDetector.DAYS_THRESHOLD) / (
                FatigueDetector.DAYS_HIGH - FatigueDetector.DAYS_THRESHOLD
            ) * 0.5
        elif days > 0:
            return days / FatigueDetector.DAYS_THRESHOLD * 0.5
        return 0.0

    @staticmethod
    def _fatigue_severity(score: float) -> SeverityLevel:
        if score >= 0.8:
            return SeverityLevel.CRITICAL
        elif score >= 0.6:
            return SeverityLevel.HIGH
        elif score >= 0.4:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    @staticmethod
    def _confidence(
        creative: CreativeReality,
        has_peak_ctr: bool,
        has_peak_roas: bool,
    ) -> float:
        """估算置信度。"""
        confidence = 0.5
        if creative.installs >= 5000:
            confidence += 0.2
        elif creative.installs >= 1000:
            confidence += 0.1
        if has_peak_ctr:
            confidence += 0.1
        if has_peak_roas:
            confidence += 0.1
        return min(confidence, 0.95)

    def __repr__(self) -> str:
        return (
            f"FatigueDetector(detected={self.total_detected}, "
            f"fatigued={self.total_fatigued})"
        )