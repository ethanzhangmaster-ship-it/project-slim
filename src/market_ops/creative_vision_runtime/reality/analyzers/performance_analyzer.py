"""E12.2 — Performance Analyzer。

分析 RealitySnapshot 中的 Campaign/Creative 性能变化，
检测 CTR、CVR、ROAS、CPI、LTV 等关键指标的变化。

检测规则：
  - ROAS 下降 > 30% → PERFORMANCE_DROP
  - CTR 下降 > 20% → CREATIVE_FATIGUE 信号
  - CPI 上升 > 30% → 效率下降

Usage:
    analyzer = PerformanceAnalyzer()
    insights = analyzer.analyze(snapshot, previous_snapshot)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..intelligence.models import (
    InsightType,
    PerformanceInsight,
    RealityInsight,
    SeverityLevel,
)

if TYPE_CHECKING:
    from ..models import CampaignReality, CreativeReality, RealitySnapshot

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """性能分析器 —— 检测 Campaign/Creative 性能变化。

    对比当前快照与历史快照，检测关键指标变化，
    输出 PerformanceInsight 和 RealityInsight。

    Attributes:
        total_analyzed:  累计分析次数
    """

    # 阈值配置
    ROAS_DROP_THRESHOLD = 0.30       # ROAS 下降 30% → PERFORMANCE_DROP
    CTR_DROP_THRESHOLD = 0.20        # CTR 下降 20% → 疲劳信号
    CPI_RISE_THRESHOLD = 0.30        # CPI 上升 30% → 效率下降
    ROAS_IMPROVE_THRESHOLD = 0.30    # ROAS 改善 30% → WINNING_PATTERN
    CTR_IMPROVE_THRESHOLD = 0.20     # CTR 改善 20% → 赢家信号

    def __init__(self) -> None:
        self.total_analyzed: int = 0

    # ── Public API ───────────────────────────────────────

    def analyze(
        self,
        current: RealitySnapshot,
        previous: RealitySnapshot | None = None,
    ) -> list[RealityInsight]:
        """分析性能变化。

        Args:
            current:   当前快照
            previous:  历史快照（None 时只做当前值评估）

        Returns:
            RealityInsight 列表
        """
        insights: list[RealityInsight] = []

        # 按 Campaign 分析
        for campaign in current.campaigns:
            prev_campaign = self._find_previous(campaign.campaign_id, previous)
            campaign_insights = self._analyze_campaign(campaign, prev_campaign, current)
            insights.extend(campaign_insights)

        # 按 Creative 分析
        for creative in current.creatives:
            prev_creative = self._find_previous_creative(creative.creative_id, previous)
            creative_insights = self._analyze_creative(creative, prev_creative, current)
            insights.extend(creative_insights)

        self.total_analyzed += 1
        logger.info(
            f"PerformanceAnalyzer: {len(insights)} insights "
            f"from {len(current.campaigns)} campaigns, "
            f"{len(current.creatives)} creatives"
        )
        return insights

    def analyze_single(
        self,
        current: CampaignReality,
        previous: CampaignReality | None = None,
    ) -> list[PerformanceInsight]:
        """分析单个 Campaign 的性能变化。

        Args:
            current:  当前 Campaign
            previous: 历史 Campaign

        Returns:
            PerformanceInsight 列表
        """
        perf_insights: list[PerformanceInsight] = []

        # ROAS
        if previous and previous.roas_d7 > 0:
            change = self._compute_change(current.roas_d7, previous.roas_d7)
            direction = self._direction(change)
            perf_insights.append(PerformanceInsight(
                creative_id=current.campaign_id,
                metric="ROAS",
                current_value=current.roas_d7,
                previous_value=previous.roas_d7,
                change_pct=change,
                direction=direction,
                severity=self._roas_severity(change),
                confidence=self._confidence_from_data(current),
                evidence=[f"ROAS changed {change:+.0%}: {previous.roas_d7:.4f} → {current.roas_d7:.4f}"],
            ))

        # CTR
        if previous and previous.ctr > 0:
            change = self._compute_change(current.ctr, previous.ctr)
            direction = self._direction(change)
            perf_insights.append(PerformanceInsight(
                creative_id=current.campaign_id,
                metric="CTR",
                current_value=current.ctr,
                previous_value=previous.ctr,
                change_pct=change,
                direction=direction,
                severity=self._ctr_severity(change),
                confidence=self._confidence_from_data(current),
                evidence=[f"CTR changed {change:+.0%}: {previous.ctr:.4f} → {current.ctr:.4f}"],
            ))

        # CPI (CPI 上升是坏的)
        if previous and previous.cpi > 0:
            change = self._compute_change(current.cpi, previous.cpi)
            direction = -self._direction(change)  # CPI 上升 = 恶化
            perf_insights.append(PerformanceInsight(
                creative_id=current.campaign_id,
                metric="CPI",
                current_value=current.cpi,
                previous_value=previous.cpi,
                change_pct=change,
                direction=direction,
                severity=self._cpi_severity(change),
                confidence=self._confidence_from_data(current),
                evidence=[f"CPI changed {change:+.0%}: ${previous.cpi:.2f} → ${current.cpi:.2f}"],
            ))

        return perf_insights

    # ── Internal ────────────────────────────────────────

    def _analyze_campaign(
        self,
        campaign: CampaignReality,
        previous: CampaignReality | None,
        snapshot: RealitySnapshot,
    ) -> list[RealityInsight]:
        """分析单个 Campaign 并生成 RealityInsight。"""
        perf = self.analyze_single(campaign, previous)
        insights: list[RealityInsight] = []

        for p in perf:
            insight = self._perf_to_insight(p, snapshot)
            if insight:
                insights.append(insight)

        return insights

    def _analyze_creative(
        self,
        creative: CreativeReality,
        previous: CreativeReality | None,
        snapshot: RealitySnapshot,
    ) -> list[RealityInsight]:
        """分析单个 Creative 并生成 RealityInsight。"""
        insights: list[RealityInsight] = []

        if not previous:
            return insights

        # ROAS 变化
        if previous.roas_d30 > 0:
            change = self._compute_change(creative.roas_d30, previous.roas_d30)
            if change < -self.ROAS_DROP_THRESHOLD:
                insights.append(RealityInsight(
                    type=InsightType.PERFORMANCE_DROP,
                    severity=SeverityLevel.HIGH,
                    confidence=min(abs(change) * 2, 0.95),
                    target=creative.creative_id,
                    evidence=[
                        f"ROAS dropped {change:+.0%}: "
                        f"{previous.roas_d30:.4f} → {creative.roas_d30:.4f}",
                    ],
                    recommended_action="EVALUATE_CREATIVE",
                    priority=min(abs(change), 1.0),
                    source_snapshot_id=snapshot.snapshot_id,
                ))

        # CTR 变化
        if previous.ctr > 0:
            change = self._compute_change(creative.ctr, previous.ctr)
            if change < -self.CTR_DROP_THRESHOLD:
                insights.append(RealityInsight(
                    type=InsightType.CREATIVE_FATIGUE,
                    severity=SeverityLevel.MEDIUM,
                    confidence=min(abs(change) * 1.5, 0.85),
                    target=creative.creative_id,
                    evidence=[
                        f"CTR dropped {change:+.0%}: "
                        f"{previous.ctr:.4f} → {creative.ctr:.4f}",
                    ],
                    recommended_action="CHECK_FATIGUE",
                    priority=min(abs(change) * 0.8, 0.8),
                    source_snapshot_id=snapshot.snapshot_id,
                ))

        return insights

    def _perf_to_insight(
        self,
        perf: PerformanceInsight,
        snapshot: RealitySnapshot,
    ) -> RealityInsight | None:
        """PerformanceInsight → RealityInsight。"""
        # 只有显著恶化才生成 RealityInsight
        if perf.direction >= 0:
            return None

        if perf.metric == "ROAS" and perf.change_pct < -self.ROAS_DROP_THRESHOLD:
            return RealityInsight(
                type=InsightType.PERFORMANCE_DROP,
                severity=SeverityLevel.HIGH,
                confidence=min(abs(perf.change_pct) * 2, 0.95),
                target=perf.creative_id,
                evidence=perf.evidence,
                recommended_action="EVALUATE_CAMPAIGN",
                priority=min(abs(perf.change_pct), 1.0),
                source_snapshot_id=snapshot.snapshot_id,
            )

        if perf.metric == "CTR" and perf.change_pct < -self.CTR_DROP_THRESHOLD:
            return RealityInsight(
                type=InsightType.CREATIVE_FATIGUE,
                severity=SeverityLevel.MEDIUM,
                confidence=min(abs(perf.change_pct) * 1.5, 0.85),
                target=perf.creative_id,
                evidence=perf.evidence,
                recommended_action="CHECK_FATIGUE",
                priority=min(abs(perf.change_pct) * 0.8, 0.8),
                source_snapshot_id=snapshot.snapshot_id,
            )

        return None

    # ── Helpers ────────────────────────────────────────

    @staticmethod
    def _compute_change(current: float, previous: float) -> float:
        """计算变化率。"""
        if previous == 0:
            return 0.0 if current == 0 else float("inf")
        return (current - previous) / abs(previous)

    @staticmethod
    def _direction(change: float) -> int:
        if change > 0.05:
            return 1
        elif change < -0.05:
            return -1
        return 0

    @staticmethod
    def _roas_severity(change: float) -> SeverityLevel:
        if change < -0.5:
            return SeverityLevel.CRITICAL
        elif change < -0.3:
            return SeverityLevel.HIGH
        elif change < -0.15:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    @staticmethod
    def _ctr_severity(change: float) -> SeverityLevel:
        if change < -0.4:
            return SeverityLevel.CRITICAL
        elif change < -0.2:
            return SeverityLevel.HIGH
        elif change < -0.1:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    @staticmethod
    def _cpi_severity(change: float) -> SeverityLevel:
        if change > 0.5:
            return SeverityLevel.CRITICAL
        elif change > 0.3:
            return SeverityLevel.HIGH
        elif change > 0.15:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    @staticmethod
    def _confidence_from_data(obj: Any) -> float:
        """根据数据量估算置信度。"""
        installs = getattr(obj, "installs", 0)
        if installs >= 5000:
            return 0.9
        elif installs >= 1000:
            return 0.7
        elif installs >= 100:
            return 0.5
        return 0.2

    @staticmethod
    def _find_previous(
        campaign_id: str,
        previous: RealitySnapshot | None,
    ) -> CampaignReality | None:
        if not previous:
            return None
        for c in previous.campaigns:
            if c.campaign_id == campaign_id:
                return c
        return None

    @staticmethod
    def _find_previous_creative(
        creative_id: str,
        previous: RealitySnapshot | None,
    ) -> CreativeReality | None:
        if not previous:
            return None
        for c in previous.creatives:
            if c.creative_id == creative_id:
                return c
        return None

    def __repr__(self) -> str:
        return f"PerformanceAnalyzer(analyzed={self.total_analyzed})"