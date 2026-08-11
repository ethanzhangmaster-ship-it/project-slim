"""E12.6.2 — Resource Policy。

资源分配策略规则层。

策略:
  - WinnerScalingPolicy:    放大赢家（高 ROAS + 低疲劳）
  - FatigueRecoveryPolicy:  疲劳恢复（高疲劳 + 高置信度）
  - LowPotentialPolicy:     低潜力削减（低 ROAS + 持续下降）
  - ExplorationPolicy:      探索分配（高多样性 + 未知模式）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import (
    BudgetAdjustment,
    ProductResourceState,
    ResourceAllocation,
    ResourceRequest,
    ResourceType,
    calculate_priority_score,
)


# ── ResourcePolicy ──────────────────────────────────────────


class ResourcePolicy(ABC):
    """资源分配策略基类。

    每个策略评估产品状态，决定是否需要调整资源分配。
    """

    name: str = "base"

    def evaluate(
        self,
        state: ProductResourceState,
        request: ResourceRequest | None = None,
    ) -> BudgetAdjustment | None:
        """评估产品状态，返回预算调整建议。

        Returns:
            BudgetAdjustment 或 None（不调整）
        """
        result = self._evaluate(state, request)
        return result

    @abstractmethod
    def _evaluate(
        self,
        state: ProductResourceState,
        request: ResourceRequest | None = None,
    ) -> BudgetAdjustment | None:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


# ── WinnerScalingPolicy ─────────────────────────────────────


class WinnerScalingPolicy(ResourcePolicy):
    """放大赢家策略。

    条件:
      - ROAS > 1.5
      - fatigue < 0.3
      - prediction_confidence > 0.7

    动作:
      - 增加 50% 预算
    """

    name = "winner_scaling"

    ROAS_THRESHOLD = 1.5
    FATIGUE_THRESHOLD = 0.3
    CONFIDENCE_THRESHOLD = 0.7
    INCREASE_RATIO = 0.50  # +50%

    def _evaluate(
        self,
        state: ProductResourceState,
        request: ResourceRequest | None = None,
    ) -> BudgetAdjustment | None:
        if state.recent_roas < self.ROAS_THRESHOLD:
            return None
        if state.fatigue_score >= self.FATIGUE_THRESHOLD:
            return None
        if state.prediction_confidence < self.CONFIDENCE_THRESHOLD:
            return None

        previous = state.allocated_budget if state.allocated_budget > 0 else state.total_budget * 0.20
        new_amount = round(previous * (1.0 + self.INCREASE_RATIO), 2)

        return BudgetAdjustment(
            product_id=state.product_id,
            resource_type=ResourceType.EXPERIMENT_BUDGET,
            previous_amount=previous,
            new_amount=new_amount,
            reason=f"Winner scaling: ROAS={state.recent_roas:.2f}, "
            f"fatigue={state.fatigue_score:.2f}, "
            f"confidence={state.prediction_confidence:.2f}",
        )


# ── FatigueRecoveryPolicy ───────────────────────────────────


class FatigueRecoveryPolicy(ResourcePolicy):
    """疲劳恢复策略。

    条件:
      - fatigue > 0.8
      - prediction_confidence > 0.8

    动作:
      - 增加 30% 突变预算（用于生成新创意）
    """

    name = "fatigue_recovery"

    FATIGUE_THRESHOLD = 0.80
    CONFIDENCE_THRESHOLD = 0.80
    INCREASE_RATIO = 0.30  # +30%

    def _evaluate(
        self,
        state: ProductResourceState,
        request: ResourceRequest | None = None,
    ) -> BudgetAdjustment | None:
        if state.fatigue_score < self.FATIGUE_THRESHOLD:
            return None
        if state.prediction_confidence < self.CONFIDENCE_THRESHOLD:
            return None

        previous = state.allocated_budget if state.allocated_budget > 0 else state.total_budget * 0.15
        new_amount = round(previous * (1.0 + self.INCREASE_RATIO), 2)

        return BudgetAdjustment(
            product_id=state.product_id,
            resource_type=ResourceType.MUTATION_BUDGET,
            previous_amount=previous,
            new_amount=new_amount,
            reason=f"Fatigue recovery: fatigue={state.fatigue_score:.2f}, "
            f"confidence={state.prediction_confidence:.2f}",
        )


# ── LowPotentialPolicy ──────────────────────────────────────


class LowPotentialPolicy(ResourcePolicy):
    """低潜力削减策略。

    条件:
      - ROAS < 0.5
      - 且状态不健康

    动作:
      - 减少 50% 预算
    """

    name = "low_potential"

    ROAS_THRESHOLD = 0.50
    DECREASE_RATIO = 0.50  # -50%

    def _evaluate(
        self,
        state: ProductResourceState,
        request: ResourceRequest | None = None,
    ) -> BudgetAdjustment | None:
        if state.recent_roas >= self.ROAS_THRESHOLD:
            return None
        if not state.needs_attention:
            return None

        previous = state.allocated_budget if state.allocated_budget > 0 else state.total_budget * 0.10
        new_amount = round(previous * (1.0 - self.DECREASE_RATIO), 2)

        return BudgetAdjustment(
            product_id=state.product_id,
            resource_type=ResourceType.EXPERIMENT_BUDGET,
            previous_amount=previous,
            new_amount=new_amount,
            reason=f"Low potential: ROAS={state.recent_roas:.2f}, "
            f"needs_attention, reducing allocation",
        )


# ── ExplorationPolicy ───────────────────────────────────────


class ExplorationPolicy(ResourcePolicy):
    """探索分配策略。

    条件:
      - population_diversity > 0.7
      - prediction_confidence > 0.5

    动作:
      - 分配 20% 总预算用于探索
    """

    name = "exploration"

    DIVERSITY_THRESHOLD = 0.70
    CONFIDENCE_THRESHOLD = 0.50
    EXPLORE_RATIO = 0.20  # 探索预算占比

    def _evaluate(
        self,
        state: ProductResourceState,
        request: ResourceRequest | None = None,
    ) -> BudgetAdjustment | None:
        if state.population_diversity < self.DIVERSITY_THRESHOLD:
            return None
        if state.prediction_confidence < self.CONFIDENCE_THRESHOLD:
            return None

        explore_amount = round(state.total_budget * self.EXPLORE_RATIO, 2)

        return BudgetAdjustment(
            product_id=state.product_id,
            resource_type=ResourceType.GENERATION_CAPACITY,
            previous_amount=0.0,
            new_amount=explore_amount,
            reason=f"Exploration: diversity={state.population_diversity:.2f}, "
            f"allocating {self.EXPLORE_RATIO:.0%} for exploration",
        )


# ── Default Policies ────────────────────────────────────────


DEFAULT_RESOURCE_POLICIES: list[ResourcePolicy] = [
    WinnerScalingPolicy(),
    FatigueRecoveryPolicy(),
    LowPotentialPolicy(),
    ExplorationPolicy(),
]