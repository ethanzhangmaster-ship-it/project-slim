"""E12.2 — Insight Engine。

多分析器融合引擎：将 PerformanceAnalyzer、FatigueDetector、
AnomalyDetector 的输出融合为统一的 CombinedInsight。

核心职责：
  1. 运行所有分析器
  2. 合并相同类型的洞察
  3. 去重（同 target 同 type 只保留最高置信度）
  4. 按优先级排序
  5. 输出 CombinedInsight

Usage:
    engine = InsightEngine(
        performance_analyzer=PerformanceAnalyzer(),
        fatigue_detector=FatigueDetector(),
        anomaly_detector=AnomalyDetector(),
    )
    combined = engine.analyze(snapshot, previous_snapshot)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import CombinedInsight, InsightType, RealityInsight, SeverityLevel
from .confidence_engine import ConfidenceEngine
from .recommendation_engine import RecommendationEngine

if TYPE_CHECKING:
    from ..analyzers.performance_analyzer import PerformanceAnalyzer
    from ..analyzers.fatigue_detector import FatigueDetector
    from ..analyzers.anomaly_detector import AnomalyDetector
    from ..models import RealitySnapshot

logger = logging.getLogger(__name__)


class InsightEngine:
    """多分析器融合引擎。

    E12.2 核心运算引擎：运行所有分析器，融合结果，
    输出统一的 CombinedInsight。

    Attributes:
        performance_analyzer: 性能分析器
        fatigue_detector:     疲劳检测器
        anomaly_detector:     异常检测器
        confidence_engine:    置信度引擎
        recommendation_engine: 推荐引擎
        total_analyzed:       累计分析次数
    """

    def __init__(
        self,
        performance_analyzer: PerformanceAnalyzer | None = None,
        fatigue_detector: FatigueDetector | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        confidence_engine: ConfidenceEngine | None = None,
        recommendation_engine: RecommendationEngine | None = None,
    ) -> None:
        from ..analyzers.performance_analyzer import PerformanceAnalyzer
        from ..analyzers.fatigue_detector import FatigueDetector
        from ..analyzers.anomaly_detector import AnomalyDetector

        self.performance_analyzer = performance_analyzer or PerformanceAnalyzer()
        self.fatigue_detector = fatigue_detector or FatigueDetector()
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.confidence_engine = confidence_engine or ConfidenceEngine()
        self.recommendation_engine = recommendation_engine or RecommendationEngine()

        self.total_analyzed: int = 0

    # ── Public API ───────────────────────────────────────

    def analyze(
        self,
        current: RealitySnapshot,
        previous: RealitySnapshot | None = None,
        peak_data: dict[str, dict] | None = None,
        expected_map: dict[str, dict[str, float]] | None = None,
    ) -> CombinedInsight:
        """运行所有分析器并融合结果。

        Args:
            current:      当前 RealitySnapshot
            previous:     历史 RealitySnapshot
            peak_data:    FatigueDetector 的峰值数据
            expected_map: AnomalyDetector 的期望值

        Returns:
            CombinedInsight
        """
        all_insights: list[RealityInsight] = []

        # 1. 性能分析
        perf_insights = self.performance_analyzer.analyze(current, previous)
        all_insights.extend(perf_insights)

        # 2. 疲劳检测
        fatigue_results = self.fatigue_detector.detect_batch(current, peak_data)
        fatigue_insights = self.fatigue_detector.to_insights(
            fatigue_results, current.snapshot_id,
        )
        all_insights.extend(fatigue_insights)

        # 3. 异常检测
        anomaly_results = self.anomaly_detector.detect_batch(current, expected_map)
        anomaly_insights = self.anomaly_detector.to_insights(
            anomaly_results, current.snapshot_id,
        )
        all_insights.extend(anomaly_insights)

        # 4. 去重
        deduped = self._deduplicate(all_insights)

        # 5. 重新计算置信度（只覆盖未设置或低置信度的）
        for insight in deduped:
            if insight.confidence < 0.5:
                insight.confidence = self.confidence_engine.compute(insight)

        # 6. 按优先级排序
        deduped.sort(key=lambda i: i.priority, reverse=True)

        # 7. 融合
        combined = self._combine(deduped)

        self.total_analyzed += 1
        logger.info(
            f"InsightEngine: {len(deduped)} insights "
            f"(from {len(all_insights)} raw) → {combined.primary_type.value}"
        )
        return combined

    def get_actionable_insights(
        self,
        combined: CombinedInsight,
    ) -> list[RealityInsight]:
        """筛选可执行的洞察。"""
        return [i for i in combined.insights if i.is_actionable]

    def get_top_insights(
        self,
        combined: CombinedInsight,
        n: int = 5,
    ) -> list[RealityInsight]:
        """获取前 N 个洞察。"""
        return sorted(
            combined.insights,
            key=lambda i: i.priority,
            reverse=True,
        )[:n]

    # ── Internal ────────────────────────────────────────

    def _deduplicate(
        self,
        insights: list[RealityInsight],
    ) -> list[RealityInsight]:
        """去重：同 target + 同 type 只保留最高 confidence 的。"""
        key_to_insight: dict[str, RealityInsight] = {}

        for insight in insights:
            key = f"{insight.target}|{insight.type.value}"
            if key not in key_to_insight:
                key_to_insight[key] = insight
            else:
                existing = key_to_insight[key]
                if insight.confidence > existing.confidence:
                    key_to_insight[key] = insight

        return list(key_to_insight.values())

    def _combine(
        self,
        insights: list[RealityInsight],
    ) -> CombinedInsight:
        """融合多个洞察为 CombinedInsight。"""
        if not insights:
            return CombinedInsight(
                primary_type=InsightType.PERFORMANCE_DROP,
                aggregated_confidence=0.0,
                aggregated_priority=0.0,
                severity=SeverityLevel.LOW,
                recommended_action="NO_ACTION",
                evidence=["No insights detected"],
            )

        # 主要类型：最高优先级洞察的类型
        primary = insights[0]

        # 聚合置信度：加权平均
        total_priority = sum(i.priority for i in insights)
        aggregated_confidence = (
            sum(i.confidence * i.priority for i in insights) / total_priority
            if total_priority > 0
            else 0.0
        )

        # 聚合优先级：top N 的加权平均
        top_n = insights[:3]
        agg_priority = (
            sum(i.priority * (1.0 - 0.1 * idx) for idx, i in enumerate(top_n))
            / sum(1.0 - 0.1 * idx for idx in range(len(top_n)))
        )

        # 严重程度：取最高
        severity_order = {SeverityLevel.CRITICAL: 0, SeverityLevel.HIGH: 1,
                          SeverityLevel.MEDIUM: 2, SeverityLevel.LOW: 3}
        worst_severity = min(insights, key=lambda i: severity_order[i.severity])

        # 推荐行动
        action = primary.recommended_action or self.recommendation_engine._default_action(
            primary.type,
        )

        # 所有证据
        all_evidence: list[str] = []
        for i in insights:
            all_evidence.extend(i.evidence)

        return CombinedInsight(
            insights=insights,
            primary_type=primary.type,
            aggregated_confidence=round(aggregated_confidence, 4),
            aggregated_priority=round(agg_priority, 4),
            severity=worst_severity.severity,
            recommended_action=action,
            evidence=all_evidence,
        )

    def __repr__(self) -> str:
        return f"InsightEngine(analyzed={self.total_analyzed})"