"""E13.3.1 GrowthSignalEngine — 增长信号引擎.

核心职责:
  将 E13.2 的"事实数据" (CreativeFitnessVector, AttributionEdge, KnowledgeGraph)
  转换成可决策的 GrowthSignal 列表.

输入:
  - CreativeFitnessVector: 创意表现多维向量
  - AttributionEdge: 归因链路
  - KnowledgeGraph: 知识图谱

输出:
  - list[GrowthSignal]: 分类信号列表
  - SignalBatch: 批量信号结果 (含统计)

信号类型:
  - CREATIVE_WINNER: 赢家素材
  - CREATIVE_FATIGUE: 素材疲劳
  - CREATIVE_UNDERPERFORM: 低效素材
  - ROAS_DROP: ROAS 下降
  - LTV_UPSIDE: LTV 上升潜力
  - SCALE_OPPORTUNITY: 放量机会
  - BUDGET_WASTE: 预算浪费
  - MONETIZATION_ISSUE: 变现问题
"""

from __future__ import annotations

import time
from typing import Any

from .models import (
    GrowthSignal,
    SignalBatch,
    SignalCategory,
    SignalContext,
    SignalSeverity,
    SignalType,
    SIGNAL_CATEGORY_MAP,
)
from .rules import (
    BudgetWasteDetector,
    CreativeFatigueDetector,
    CreativeUnderperformDetector,
    CreativeWinnerDetector,
    LTVUpsideDetector,
    MonetizationIssueDetector,
    ROASDropDetector,
    ScaleOpportunityDetector,
)


# ═══════════════════════════════════════════════════════════════
# Default Thresholds
# ═══════════════════════════════════════════════════════════════

DEFAULT_THRESHOLDS = {
    # Creative
    "fatigue_ctr_drop_pct": 0.25,
    "fatigue_roas_drop_pct": 0.25,
    "fatigue_frequency_min": 3.0,
    "fatigue_score_threshold": 0.75,
    "winner_roas_multiplier": 1.3,
    "winner_roas_absolute": 1.5,
    "winner_ltv_min": 5.0,
    "winner_fitness_min": 0.8,
    "winner_sample_min": 5000,
    "underperform_roas_max": 0.5,
    "underperform_ctr_max": 0.005,
    "underperform_spend_min": 100,
    # Revenue
    "roas_drop_pct": 0.30,
    "roas_drop_absolute": 0.3,
    "ltv_upside_pct": 0.20,
    "ltv_upside_absolute": 2.0,
    # UA
    "scale_roas_multiplier": 1.3,
    "scale_roas_absolute": 1.5,
    "scale_spend_max_ratio": 0.5,
    "waste_roas_max": 0.5,
    "waste_spend_min": 200,
    "waste_spend_increase": 0.3,
    # Monetization
    "monetization_iap_conversion_min": 0.01,
    "monetization_ad_arpdau_min": 0.01,
}


# ═══════════════════════════════════════════════════════════════
# GrowthSignalEngine
# ═══════════════════════════════════════════════════════════════


class GrowthSignalEngine:
    """增长信号引擎 — 从事实数据中提取可决策的增长信号.

    用法:
        engine = GrowthSignalEngine()
        signals = engine.analyze(vectors, attribution_edges, knowledge_graph)
        batch = engine.analyze_batch(context)
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        """初始化引擎.

        Args:
            thresholds: 自定义阈值，覆盖默认值
        """
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

        # 初始化所有检测器
        self._fatigue_detector = CreativeFatigueDetector(thresholds)
        self._winner_detector = CreativeWinnerDetector(thresholds)
        self._underperform_detector = CreativeUnderperformDetector(thresholds)
        self._roas_drop_detector = ROASDropDetector(thresholds)
        self._ltv_upside_detector = LTVUpsideDetector(thresholds)
        self._scale_detector = ScaleOpportunityDetector(thresholds)
        self._waste_detector = BudgetWasteDetector(thresholds)
        self._monetization_detector = MonetizationIssueDetector(thresholds)

    def analyze(
        self,
        vectors: list[Any],
        attribution_edges: list[Any] | None = None,
        knowledge_graph: Any = None,
        product_id: str = "",
    ) -> list[GrowthSignal]:
        """分析输入数据，生成增长信号列表.

        Args:
            vectors: CreativeFitnessVector 列表
            attribution_edges: AttributionEdge 列表 (可选)
            knowledge_graph: KnowledgeGraph 实例 (可选)
            product_id: 产品ID

        Returns:
            list[GrowthSignal]: 检测到的所有增长信号
        """
        if not vectors:
            return []

        benchmarks = self._compute_benchmarks(vectors)
        all_signals: list[GrowthSignal] = []

        for vector in vectors:
            signals = self._analyze_vector(vector, benchmarks)
            all_signals.extend(signals)

        # 按严重度和置信度排序: CRITICAL > HIGH > MEDIUM > LOW, 然后按置信度降序
        severity_order = {
            SignalSeverity.CRITICAL: 0,
            SignalSeverity.HIGH: 1,
            SignalSeverity.MEDIUM: 2,
            SignalSeverity.LOW: 3,
        }
        all_signals.sort(key=lambda s: (severity_order.get(s.severity, 99), -s.confidence))

        return all_signals

    def analyze_batch(self, context: SignalContext) -> SignalBatch:
        """批量分析，返回 SignalBatch (含统计).

        Args:
            context: SignalContext 包含 vectors, edges, graph 等

        Returns:
            SignalBatch: 含完整信号列表和分类统计
        """
        start = time.perf_counter()

        signals = self.analyze(
            vectors=context.vectors,
            attribution_edges=context.attribution_edges,
            knowledge_graph=context.knowledge_graph,
            product_id=context.product_id,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        # 计算分类统计
        summary: dict[str, int] = {}
        for sig in signals:
            key = sig.signal_type.value
            summary[key] = summary.get(key, 0) + 1

        return SignalBatch(
            product_id=context.product_id,
            date=context.date,
            signals=signals,
            total_vectors=len(context.vectors),
            total_signals=len(signals),
            summary=summary,
            elapsed_ms=round(elapsed_ms, 2),
        )

    # ═══════════════════════════════════════════════════════════
    # Internal Methods
    # ═══════════════════════════════════════════════════════════

    def _analyze_vector(self, vector: Any, benchmarks: dict[str, float]) -> list[GrowthSignal]:
        """对单个向量运行所有检测器."""
        signals: list[GrowthSignal] = []

        # Creative signals
        winner = self._winner_detector.detect(vector, benchmarks)
        if winner:
            signals.append(winner)

        fatigue = self._fatigue_detector.detect(vector, benchmarks)
        if fatigue:
            signals.append(fatigue)

        underperform = self._underperform_detector.detect(vector, benchmarks)
        if underperform:
            signals.append(underperform)

        # Revenue signals
        roas_drop = self._roas_drop_detector.detect(vector, benchmarks)
        if roas_drop:
            signals.append(roas_drop)

        ltv_upside = self._ltv_upside_detector.detect(vector, benchmarks)
        if ltv_upside:
            signals.append(ltv_upside)

        # UA signals
        scale = self._scale_detector.detect(vector, benchmarks)
        if scale:
            signals.append(scale)

        waste = self._waste_detector.detect(vector, benchmarks)
        if waste:
            signals.append(waste)

        # Monetization signals
        monetization = self._monetization_detector.detect(vector, benchmarks)
        if monetization:
            signals.append(monetization)

        return signals

    def _compute_benchmarks(self, vectors: list[Any]) -> dict[str, float]:
        """计算分类基准数据."""
        if not vectors:
            return {}

        n = len(vectors)
        total_ctr = 0.0
        total_d7_roas = 0.0
        total_d30_roas = 0.0
        total_d7_ltv = 0.0
        total_d30_ltv = 0.0
        total_spend = 0.0
        total_fitness = 0.0

        for v in vectors:
            total_ctr += v.ctr
            total_d7_roas += v.d7_roas
            total_d30_roas += v.d30_roas
            total_d7_ltv += v.d7_ltv
            total_d30_ltv += v.d30_ltv
            total_spend += v.spend
            total_fitness += v.fitness_score

        return {
            "avg_ctr": round(total_ctr / n, 6),
            "avg_d7_roas": round(total_d7_roas / n, 4),
            "avg_d30_roas": round(total_d30_roas / n, 4),
            "avg_d7_ltv": round(total_d7_ltv / n, 4),
            "avg_d30_ltv": round(total_d30_ltv / n, 4),
            "avg_spend": round(total_spend / n, 2),
            "avg_fitness": round(total_fitness / n, 4),
            "total_vectors": float(n),
        }

    # ═══════════════════════════════════════════════════════════
    # Convenience filters
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def filter_by_severity(
        signals: list[GrowthSignal],
        min_severity: SignalSeverity = SignalSeverity.HIGH,
    ) -> list[GrowthSignal]:
        """按最低严重度过滤信号."""
        severity_order = {
            SignalSeverity.CRITICAL: 0,
            SignalSeverity.HIGH: 1,
            SignalSeverity.MEDIUM: 2,
            SignalSeverity.LOW: 3,
        }
        threshold = severity_order.get(min_severity, 99)
        return [s for s in signals if severity_order.get(s.severity, 99) <= threshold]

    @staticmethod
    def filter_by_category(
        signals: list[GrowthSignal],
        category: SignalCategory,
    ) -> list[GrowthSignal]:
        """按分类过滤信号."""
        return [s for s in signals if s.category == category]

    @staticmethod
    def filter_by_type(
        signals: list[GrowthSignal],
        signal_type: SignalType,
    ) -> list[GrowthSignal]:
        """按信号类型过滤."""
        return [s for s in signals if s.signal_type == signal_type]

    @staticmethod
    def get_winners(signals: list[GrowthSignal]) -> list[GrowthSignal]:
        """获取所有 Winner 信号."""
        return [s for s in signals if s.signal_type == SignalType.CREATIVE_WINNER]

    @staticmethod
    def get_fatigued(signals: list[GrowthSignal]) -> list[GrowthSignal]:
        """获取所有 Fatigue 信号."""
        return [s for s in signals if s.signal_type == SignalType.CREATIVE_FATIGUE]

    @staticmethod
    def get_scale_opportunities(signals: list[GrowthSignal]) -> list[GrowthSignal]:
        """获取所有放量机会."""
        return [s for s in signals if s.signal_type == SignalType.SCALE_OPPORTUNITY]

    @staticmethod
    def get_critical_signals(signals: list[GrowthSignal]) -> list[GrowthSignal]:
        """获取所有 CRITICAL 级别信号."""
        return [s for s in signals if s.severity == SignalSeverity.CRITICAL]