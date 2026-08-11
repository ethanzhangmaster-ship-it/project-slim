"""E13.5.2 Opportunity Intelligence Engine — 机会智能引擎.

将 Reality Signal + Metrics + Prediction + Memory Knowledge 融合为可执行的
GrowthOpportunity 列表。

完整流程:
  Reality Snapshot
      ↓
  Signal Detection (E13.3)
      ↓
  Rule-Based Detection (opportunity_rules.py)
      ↓
  Memory Matching (Strategy + Pattern + Failure)
      ↓
  Opportunity Ranking (opportunity_ranker.py)
      ↓
  GrowthOpportunity[]

连接:
  E12 Reality → E13.3 Signal → E13.5.2 Intelligence → E13.5.5 Decision Engine
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .intelligence_models import (
    CurrentMetrics,
    GrowthOpportunity,
    MemoryContext,
    SignalSummary,
)
from .opportunity_ranker import OpportunityRanker
from .opportunity_rules import RuleEngine

if TYPE_CHECKING:
    from ..memory.failure_memory import FailureMemory
    from ..memory.pattern_store import PatternStore
    from ..memory.strategy_memory import StrategyMemory


class OpportunityIntelligenceEngine:
    """机会智能引擎 — 核心推理层.

    将 E12 现实数据 + E13.4 记忆知识转换为可执行的增长机会。

    用法:
        engine = OpportunityIntelligenceEngine()
        # 可选: 连接 Memory
        engine.set_strategy_memory(sm)
        engine.set_pattern_store(ps)
        engine.set_failure_memory(fm)

        # 分析
        opportunities = engine.analyze(
            signals=signal_summary,
            metrics=current_metrics,
            predictions={"fatigue_probability": 0.87, "ctr_decay": 0.35},
            memory_context=memory_context,
        )

        # 获取 Top-N
        top = engine.get_top_opportunities(opportunities, n=3)
    """

    def __init__(self):
        self._rule_engine = RuleEngine()
        self._rule_engine.register_defaults()
        self._ranker = OpportunityRanker()
        self._analysis_count: int = 0

    # ═══════════════════════════════════════════════════════════
    # Memory Connection
    # ═══════════════════════════════════════════════════════════

    def set_strategy_memory(self, sm: StrategyMemory) -> None:
        """连接策略记忆."""
        self._ranker.set_strategy_memory(sm)

    def set_pattern_store(self, ps: PatternStore) -> None:
        """连接模式存储."""
        self._ranker.set_pattern_store(ps)

    def set_failure_memory(self, fm: FailureMemory) -> None:
        """连接失败记忆."""
        self._ranker.set_failure_memory(fm)

    # ═══════════════════════════════════════════════════════════
    # Analysis
    # ═══════════════════════════════════════════════════════════

    def analyze(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
        memory_context: MemoryContext | None = None,
        top_n: int = 10,
        use_real_memory: bool = False,
    ) -> list[GrowthOpportunity]:
        """分析现实数据，发现增长机会.

        完整流程:
          1. Rule-Based Detection: 信号 + 指标 → 候选机会
          2. Memory Matching: 查询 Memory 增强置信度
          3. Ranking: 综合评分排序
          4. Top-N Selection

        Args:
            signals: 信号摘要 (含 fatigue, anomaly, trend 等)
            metrics: 当前指标快照
            predictions: 预测数据 (fatigue_probability, ctr_decay, roas_forecast 等)
            memory_context: 预检索的记忆上下文 (可选)
            top_n: 返回前 N 个机会
            use_real_memory: 是否使用实时 Memory 查询 (需要先 set_*_memory)

        Returns:
            list[GrowthOpportunity]: 按综合得分降序排列的机会列表
        """
        self._analysis_count += 1

        # Step 1: Rule-Based Detection
        opportunities = self._rule_engine.detect(signals, metrics, predictions)

        if not opportunities:
            return []

        # Step 2: Memory Boost & Ranking
        if use_real_memory:
            opportunities = self._ranker.rank_with_memory(opportunities, top_n=top_n)
        else:
            opportunities = self._ranker.rank(opportunities, memory_context=memory_context, top_n=top_n)

        return opportunities

    def analyze_with_memory(
        self,
        signals: SignalSummary,
        metrics: CurrentMetrics,
        predictions: dict[str, Any] | None = None,
        top_n: int = 10,
    ) -> list[GrowthOpportunity]:
        """使用实时 Memory 查询进行分析.

        需要先通过 set_strategy_memory / set_pattern_store / set_failure_memory
        连接 Memory 模块。

        Args:
            signals: 信号摘要
            metrics: 当前指标
            predictions: 预测数据
            top_n: 返回前 N 个

        Returns:
            list[GrowthOpportunity]: 增强排序后的机会列表
        """
        return self.analyze(
            signals=signals,
            metrics=metrics,
            predictions=predictions,
            use_real_memory=True,
            top_n=top_n,
        )

    def analyze_quick(
        self,
        fatigue_detected: bool = False,
        anomaly_detected: bool = False,
        trend: str = "stable",
        roas: float = 0.0,
        ctr: float = 0.0,
        frequency: float = 0.0,
        spend: float = 0.0,
        revenue: float = 0.0,
        predictions: dict[str, Any] | None = None,
        top_n: int = 5,
    ) -> list[GrowthOpportunity]:
        """快速分析 (使用简化参数).

        无需构造完整的 SignalSummary 和 CurrentMetrics，直接传入关键参数。

        Args:
            fatigue_detected: 是否检测到疲劳
            anomaly_detected: 是否检测到异常
            trend: 趋势方向 (improving / stable / declining)
            roas: 当前 ROAS
            ctr: 当前 CTR
            frequency: 当前频次
            spend: 当前花费
            revenue: 当前收入
            predictions: 预测数据
            top_n: 返回前 N 个

        Returns:
            list[GrowthOpportunity]: 排序后的机会列表
        """
        signals = SignalSummary(
            fatigue_detected=fatigue_detected,
            anomaly_detected=anomaly_detected,
            trend=trend,
        )
        metrics = CurrentMetrics(
            roas=roas,
            ctr=ctr,
            frequency=frequency,
            spend=spend,
            revenue=revenue,
        )
        return self.analyze(signals=signals, metrics=metrics, predictions=predictions, top_n=top_n)

    # ═══════════════════════════════════════════════════════════
    # Top-N Helpers
    # ═══════════════════════════════════════════════════════════

    def get_top_opportunities(
        self,
        opportunities: list[GrowthOpportunity],
        n: int = 3,
    ) -> list[GrowthOpportunity]:
        """获取 Top-N 机会."""
        return self._ranker.get_top(opportunities, n=n)

    def get_critical_opportunities(
        self,
        opportunities: list[GrowthOpportunity],
    ) -> list[GrowthOpportunity]:
        """获取紧急/高优先级机会."""
        return self._ranker.get_critical_only(opportunities)

    def get_actionable_opportunities(
        self,
        opportunities: list[GrowthOpportunity],
    ) -> list[GrowthOpportunity]:
        """获取可执行机会."""
        return self._ranker.get_actionable_only(opportunities)

    # ═══════════════════════════════════════════════════════════
    # Rule Management
    # ═══════════════════════════════════════════════════════════

    @property
    def rule_engine(self) -> RuleEngine:
        """获取规则引擎 (用于自定义规则)."""
        return self._rule_engine

    @property
    def ranker(self) -> OpportunityRanker:
        """获取排序器 (用于自定义排序)."""
        return self._ranker

    @property
    def analysis_count(self) -> int:
        """获取分析次数."""
        return self._analysis_count