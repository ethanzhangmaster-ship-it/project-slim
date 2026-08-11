"""E12.2 — Anomaly Detector。

检测数据异常：
  - 花费突变（Spend Spike）
  - 收入异常（Revenue Drop）
  - 安装量突变（Installs Spike/Drop）
  - 指标异常偏离

Usage:
    detector = AnomalyDetector()
    anomalies = detector.detect(snapshot, expected_values)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..intelligence.models import (
    AnomalyInsight,
    InsightType,
    RealityInsight,
    SeverityLevel,
)

if TYPE_CHECKING:
    from ..models import CampaignReality, RealitySnapshot

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """异常检测器。

    检测 Campaign 级别数据异常，包括花费突变、收入异常、
    安装量突变等。

    Attributes:
        total_detected:  累计检测次数
        total_anomalies: 累计异常数
    """

    # 阈值配置
    SPEND_SPIKE_THRESHOLD = 0.50       # 花费突变 > 50%
    SPEND_SURGE_THRESHOLD = 1.0        # 花费激增 > 100%
    REVENUE_DROP_THRESHOLD = 0.30      # 收入下降 > 30%
    INSTALLS_SPIKE_THRESHOLD = 0.50    # 安装量突变 > 50%
    SPEND_MIN = 100.0                  # 最小花费才检测（$100）

    def __init__(self) -> None:
        self.total_detected: int = 0
        self.total_anomalies: int = 0

    # ── Public API ───────────────────────────────────────

    def detect(
        self,
        current: CampaignReality,
        expected: dict[str, float] | None = None,
    ) -> list[AnomalyInsight]:
        """检测单个 Campaign 的异常。

        Args:
            current:  当前 Campaign 数据
            expected: 期望值 {"spend": float, "revenue": float, "installs": int}

        Returns:
            AnomalyInsight 列表
        """
        anomalies: list[AnomalyInsight] = []
        exp = expected or {}

        # 花费太小不检测
        if current.spend < self.SPEND_MIN:
            return anomalies

        # 1. 花费突变
        expected_spend = exp.get("spend")
        if expected_spend and expected_spend > 0:
            deviation = self._compute_deviation(current.spend, expected_spend)
            if abs(deviation) >= self.SPEND_SPIKE_THRESHOLD:
                anomaly_type = "SPEND_SURGE" if deviation > 0 else "SPEND_DROP"
                severity = (
                    SeverityLevel.CRITICAL
                    if abs(deviation) >= self.SPEND_SURGE_THRESHOLD
                    else SeverityLevel.HIGH
                )
                anomalies.append(AnomalyInsight(
                    campaign_id=current.campaign_id,
                    anomaly_type=anomaly_type,
                    metric="spend",
                    expected_value=expected_spend,
                    actual_value=current.spend,
                    deviation_pct=deviation,
                    severity=severity,
                    confidence=0.85,
                    evidence=[
                        f"Spend {deviation:+.0%}: "
                        f"expected ${expected_spend:.2f}, actual ${current.spend:.2f}",
                    ],
                ))

        # 2. 收入异常
        expected_revenue = exp.get("revenue")
        if expected_revenue and expected_revenue > 0:
            deviation = self._compute_deviation(
                current.revenue_d30, expected_revenue,
            )
            if deviation < -self.REVENUE_DROP_THRESHOLD:
                anomalies.append(AnomalyInsight(
                    campaign_id=current.campaign_id,
                    anomaly_type="REVENUE_DROP",
                    metric="revenue_d30",
                    expected_value=expected_revenue,
                    actual_value=current.revenue_d30,
                    deviation_pct=deviation,
                    severity=SeverityLevel.HIGH,
                    confidence=0.80,
                    evidence=[
                        f"Revenue dropped {deviation:+.0%}: "
                        f"expected ${expected_revenue:.2f}, actual ${current.revenue_d30:.2f}",
                    ],
                ))

        # 3. 安装量突变
        expected_installs = exp.get("installs")
        if expected_installs and expected_installs > 0:
            deviation = self._compute_deviation(
                current.installs, expected_installs,
            )
            if abs(deviation) >= self.INSTALLS_SPIKE_THRESHOLD:
                anomaly_type = "INSTALLS_SURGE" if deviation > 0 else "INSTALLS_DROP"
                anomalies.append(AnomalyInsight(
                    campaign_id=current.campaign_id,
                    anomaly_type=anomaly_type,
                    metric="installs",
                    expected_value=expected_installs,
                    actual_value=current.installs,
                    deviation_pct=deviation,
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.75,
                    evidence=[
                        f"Installs {deviation:+.0%}: "
                        f"expected {expected_installs:.0f}, actual {current.installs}",
                    ],
                ))

        self.total_detected += 1
        if anomalies:
            self.total_anomalies += 1

        return anomalies

    def detect_batch(
        self,
        snapshot: RealitySnapshot,
        expected_map: dict[str, dict[str, float]] | None = None,
    ) -> list[AnomalyInsight]:
        """批量检测快照中所有 Campaign 的异常。

        Args:
            snapshot:     RealitySnapshot
            expected_map: {campaign_id: {"spend": float, "revenue": float, "installs": int}}

        Returns:
            AnomalyInsight 列表
        """
        all_anomalies: list[AnomalyInsight] = []
        exp_map = expected_map or {}

        for campaign in snapshot.campaigns:
            expected = exp_map.get(campaign.campaign_id)
            anomalies = self.detect(campaign, expected)
            all_anomalies.extend(anomalies)

        return all_anomalies

    def to_insights(
        self,
        anomalies: list[AnomalyInsight],
        snapshot_id: str = "",
    ) -> list[RealityInsight]:
        """将 AnomalyInsight 转换为 RealityInsight。

        Args:
            anomalies:    AnomalyInsight 列表
            snapshot_id:  来源快照 ID

        Returns:
            RealityInsight 列表
        """
        insights: list[RealityInsight] = []

        for a in anomalies:
            if not a.is_significant:
                continue

            # 确定推荐行动
            if a.anomaly_type == "SPEND_SURGE":
                action = "VERIFY_SPEND"
                priority = min(abs(a.deviation_pct) * 0.8, 1.0)
            elif a.anomaly_type == "SPEND_DROP":
                action = "CHECK_BUDGET"
                priority = min(abs(a.deviation_pct) * 0.7, 0.9)
            elif a.anomaly_type == "REVENUE_DROP":
                action = "INVESTIGATE_REVENUE"
                priority = min(abs(a.deviation_pct) * 0.9, 1.0)
            elif a.anomaly_type == "INSTALLS_DROP":
                action = "CHECK_TARGETING"
                priority = min(abs(a.deviation_pct) * 0.6, 0.8)
            else:
                action = "MONITOR"
                priority = 0.5

            insights.append(RealityInsight(
                type=InsightType.DATA_ANOMALY,
                severity=a.severity,
                confidence=a.confidence,
                target=a.campaign_id,
                evidence=a.evidence,
                recommended_action=action,
                priority=priority,
                source_snapshot_id=snapshot_id,
                metadata={
                    "anomaly_type": a.anomaly_type,
                    "metric": a.metric,
                    "deviation_pct": a.deviation_pct,
                },
            ))

        return insights

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _compute_deviation(actual: float, expected: float) -> float:
        """计算偏离率。"""
        if expected == 0:
            return 0.0 if actual == 0 else float("inf")
        return (actual - expected) / expected

    def __repr__(self) -> str:
        return (
            f"AnomalyDetector(detected={self.total_detected}, "
            f"anomalies={self.total_anomalies})"
        )