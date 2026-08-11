"""E13.5.3 Strategy Selector — 策略选择引擎.

将 GrowthOpportunity 连接到 StrategyMemory + FailureMemory，选择历史最优增长打法。

核心流程:
  GrowthOpportunity
      ↓
  StrategyMemory.recommend()    → 候选策略
      ↓
  StrategyMatcher.match()       → 多维度匹配评分
      ↓
  FailureMemory.check_strategy() → 风险评分
      ↓
  StrategyRanker.rank()         → 综合排序
      ↓
  StrategySelection             → 最终选择

连接:
  E13.5.2 Opportunity → E13.5.3 Selector → E13.4.3 StrategyMemory
                                         → E13.4.4 FailureMemory
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .intelligence_models import (
    GrowthOpportunity,
    StrategyCandidate,
    StrategySelection,
)
from .strategy_matcher import StrategyMatcher
from .strategy_ranker import StrategyRanker

if TYPE_CHECKING:
    from ..memory.failure_memory import FailureMemory
    from ..memory.strategy_memory import StrategyMemory
    from ..memory.strategy_models import GrowthStrategyPattern


class StrategySelector:
    """策略选择器 — 为机会选择最佳历史增长方案.

    连接 StrategyMemory 和 FailureMemory，实现端到端的策略选择。

    用法:
        selector = StrategySelector(strategy_memory, failure_memory)
        selection = selector.select(opportunity)
        if selection.has_selection:
            print(f"Selected: {selection.selected_strategy_id}")
    """

    def __init__(
        self,
        strategy_memory: StrategyMemory | None = None,
        failure_memory: FailureMemory | None = None,
    ):
        """初始化策略选择器.

        Args:
            strategy_memory: StrategyMemory 实例 (必需)
            failure_memory: FailureMemory 实例 (可选，用于风险检查)
        """
        self._strategy_memory = strategy_memory
        self._failure_memory = failure_memory
        self._matcher = StrategyMatcher()
        self._ranker = StrategyRanker()
        self._selection_count: int = 0

    # ═══════════════════════════════════════════════════════════
    # Selection
    # ═══════════════════════════════════════════════════════════

    def select(
        self,
        opportunity: GrowthOpportunity,
        top_n: int = 5,
        viable_only: bool = True,
        min_confidence: float = 0.3,
    ) -> StrategySelection:
        """为机会选择最佳策略.

        完整流程:
          1. StrategyMemory.recommend() → 候选策略
          2. StrategyMatcher.match() → 多维度匹配
          3. FailureMemory.check_strategy() → 风险检查
          4. StrategyRanker.rank() → 综合排序
          5. 构建 StrategySelection

        Args:
            opportunity: 增长机会
            top_n: 返回前 N 个候选
            viable_only: 是否仅返回可行策略 (排除风险拦截)
            min_confidence: 最低决策置信度

        Returns:
            StrategySelection: 策略选择结果
        """
        self._selection_count += 1

        selection = StrategySelection(opportunity_id=opportunity.opportunity_id)

        # Step 1: 从 StrategyMemory 获取候选策略
        if self._strategy_memory is None:
            return selection

        strategies = self._get_candidate_strategies(opportunity)
        if not strategies:
            return selection

        # Step 2: 多维度匹配
        matched = self._matcher.match(opportunity, strategies)

        # Step 3: 风险检查
        risk_data = self._check_risks(strategies, opportunity)

        # Step 4: 综合排序
        candidates = self._ranker.rank(matched, risk_data=risk_data, top_n=top_n)

        # Step 5: 过滤
        if viable_only:
            candidates = self._ranker.get_viable(candidates)

        if not candidates:
            return selection

        # Step 6: 构建选择结果
        best = candidates[0]
        alternatives = candidates[1:] if len(candidates) > 1 else []

        selection.selected_strategy_id = best.strategy_id
        selection.selected_strategy = best.strategy
        selection.alternatives = alternatives
        selection.decision_confidence = self._compute_decision_confidence(best, candidates)
        selection.selection_reason = best.reason
        selection.risk_warnings = best.failure_warnings
        selection.requires_approval = self._determine_approval(best, opportunity)
        selection._best_candidate = best

        return selection

    def select_best(
        self,
        opportunity: GrowthOpportunity,
    ) -> StrategyCandidate | None:
        """选择最佳策略 (仅返回候选，不包装为 Selection).

        Args:
            opportunity: 增长机会

        Returns:
            StrategyCandidate | None: 最佳候选
        """
        selection = self.select(opportunity, top_n=1, viable_only=True)
        return selection._best_candidate

    def select_with_alternatives(
        self,
        opportunity: GrowthOpportunity,
        top_n: int = 3,
    ) -> StrategySelection:
        """选择并返回多个备选策略."""
        return self.select(opportunity, top_n=top_n, viable_only=True)

    # ═══════════════════════════════════════════════════════════
    # Internal Steps
    # ═══════════════════════════════════════════════════════════

    def _get_candidate_strategies(
        self,
        opportunity: GrowthOpportunity,
    ) -> list[GrowthStrategyPattern]:
        """从 StrategyMemory 获取候选策略."""
        if self._strategy_memory is None:
            return []

        return self._strategy_memory.recommend(
            opportunity_type=opportunity.opportunity_type.value,
            signal_types=self._extract_opportunity_signals(opportunity),
            audience_segment=opportunity.metadata.get("audience_segment", "") if opportunity.metadata else "",
            product_category=opportunity.product_id,
            actionable_only=True,
            top_n=10,
        )

    def _check_risks(
        self,
        strategies: list[GrowthStrategyPattern],
        opportunity: GrowthOpportunity,
    ) -> dict[str, Any]:
        """通过 FailureMemory 检查策略风险."""
        if self._failure_memory is None:
            return {}

        risk_data: dict[str, Any] = {}
        opp_type = opportunity.opportunity_type.value
        audience = opportunity.metadata.get("audience_segment", "") if opportunity.metadata else ""

        for strategy in strategies:
            warnings = self._failure_memory.check_strategy(
                strategy=strategy,
                opportunity_type=opp_type,
                audience_segment=audience,
                product_category=opportunity.product_id,
            )

            if warnings:
                # 扁平化所有步骤的警告
                all_warnings: list[dict[str, Any]] = []
                for step_key, step_warnings in warnings.items():
                    for w in step_warnings:
                        all_warnings.append({
                            "pattern_name": w.pattern_name,
                            "risk_score": w.risk_score,
                            "failure_rate": w.failure_rate,
                            "expected_loss": w.expected_loss,
                            "suggestion": w.suggestion,
                            "requires_approval": w.requires_approval,
                        })

                risk_data[strategy.strategy_id] = {
                    "warnings": all_warnings,
                    "total_warnings": len(all_warnings),
                    "max_risk": max((w["risk_score"] for w in all_warnings), default=0.0),
                }

        return risk_data

    def _compute_decision_confidence(
        self,
        best: StrategyCandidate,
        all_candidates: list[StrategyCandidate],
    ) -> float:
        """计算决策置信度.

        基于最佳候选的 final_score 和候选间的差距。
        """
        if not all_candidates or len(all_candidates) == 1:
            return best.final_score

        # 显著差距增强置信度
        second_score = all_candidates[1].final_score if len(all_candidates) > 1 else 0.0
        gap = best.final_score - second_score
        gap_bonus = min(gap * 0.3, 0.15)  # 差距越大，置信度越高

        return round(min(best.final_score + gap_bonus, 1.0), 4)

    def _determine_approval(
        self,
        candidate: StrategyCandidate,
        opportunity: GrowthOpportunity,
    ) -> bool:
        """判断是否需要人工审批."""
        # 高风险需要审批
        if candidate.risk_score >= 0.6:
            return True
        # 高影响机会 + 低置信度需要审批
        if opportunity.is_high_priority and candidate.final_score < 0.6:
            return True
        # 有失败警告需要审批
        if candidate.failure_warnings:
            return True
        return False

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _extract_opportunity_signals(opportunity: GrowthOpportunity) -> list[str]:
        """从机会中提取信号类型."""
        signals: list[str] = []

        opp_type = opportunity.opportunity_type.value
        signals.append(opp_type)

        # 从 reason 中提取
        reason = opportunity.reason.lower()
        signal_keywords = {
            "fatigue": "creative_fatigue",
            "ctr": "ctr_drop",
            "frequency": "frequency_spike",
            "roas": "roas_drop",
            "crash": "roas_crash",
            "spike": "spend_spike",
            "scale": "scale_opportunity",
            "audience": "audience_expansion",
            "payer": "payer_increase",
            "ltv": "ltv_increase",
            "budget": "budget_optimization",
        }
        for keyword, signal_name in signal_keywords.items():
            if keyword in reason:
                signals.append(signal_name)

        return list(set(signals))

    # ═══════════════════════════════════════════════════════════
    # Properties
    # ═══════════════════════════════════════════════════════════

    @property
    def matcher(self) -> StrategyMatcher:
        return self._matcher

    @property
    def ranker(self) -> StrategyRanker:
        return self._ranker

    @property
    def selection_count(self) -> int:
        return self._selection_count