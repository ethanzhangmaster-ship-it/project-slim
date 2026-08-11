"""E12.6.5 — Meta Portfolio Optimizer Models。

产品组合级增长优化的核心数据模型。

核心模型:
  PortfolioSnapshot:     产品组合状态快照
  ProductLifecycleStage: 产品生命周期阶段
  PortfolioAction:       组合操作动作
  ProductFitness:        产品适应度评分
  BudgetAllocation:      预算分配结果
  ExperimentAllocation:  实验槽位分配结果
  PortfolioDecision:     组合决策
  PortfolioResult:       组合优化结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ──────────────────────────────────────────────────


class ProductLifecycleStage(str, Enum):
    """产品生命周期阶段。

    按产品成熟度从早期到晚期排列。
    """

    LAUNCH = "launch"
    GROWTH = "growth"
    PEAK = "peak"
    PLATEAU = "plateau"
    FATIGUE = "fatigue"
    DECAY = "decay"
    DEATH = "death"


class PortfolioAction(str, Enum):
    """组合操作动作。

    对一个产品在组合中的策略。
    """

    INCREASE_INVESTMENT = "increase_investment"
    DECREASE_INVESTMENT = "decrease_investment"
    MAINTAIN = "maintain"
    EXPLORE = "explore"
    HARVEST = "harvest"
    SUNSET = "sunset"


# 生命周期默认策略映射
_LIFECYCLE_DEFAULT_ACTION: dict[ProductLifecycleStage, PortfolioAction] = {
    ProductLifecycleStage.LAUNCH: PortfolioAction.EXPLORE,
    ProductLifecycleStage.GROWTH: PortfolioAction.INCREASE_INVESTMENT,
    ProductLifecycleStage.PEAK: PortfolioAction.MAINTAIN,
    ProductLifecycleStage.PLATEAU: PortfolioAction.EXPLORE,
    ProductLifecycleStage.FATIGUE: PortfolioAction.DECREASE_INVESTMENT,
    ProductLifecycleStage.DECAY: PortfolioAction.HARVEST,
    ProductLifecycleStage.DEATH: PortfolioAction.SUNSET,
}


def get_default_action(stage: ProductLifecycleStage) -> PortfolioAction:
    """获取生命周期阶段的默认组合动作。"""
    return _LIFECYCLE_DEFAULT_ACTION.get(stage, PortfolioAction.MAINTAIN)


# ── PortfolioSnapshot ──────────────────────────────────────


@dataclass
class PortfolioSnapshot:
    """产品组合状态快照。

    描述整个产品矩阵在某一时刻的聚合状态。

    Attributes:
        timestamp:       快照时间
        products:        产品 ID 列表
        total_spend:     总花费
        total_revenue:   总收入
        total_roas:      总 ROAS
        risk_score:      组合风险评分 [0, 1]
        growth_score:    组合增长评分 [0, 1]
        diversity_score: 组合多样性评分 [0, 1]
        metadata:        附加元数据
    """

    timestamp: datetime = field(default_factory=_now)
    products: list[str] = field(default_factory=list)
    total_spend: float = 0.0
    total_revenue: float = 0.0
    total_roas: float = 0.0
    risk_score: float = 0.0
    growth_score: float = 0.0
    diversity_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def product_count(self) -> int:
        return len(self.products)

    @property
    def is_profitable(self) -> bool:
        return self.total_roas >= 1.0

    @property
    def is_healthy(self) -> bool:
        return (
            self.total_roas >= 1.0
            and self.risk_score < 0.50
            and self.growth_score >= 0.30
        )

    @property
    def avg_revenue_per_product(self) -> float:
        if self.product_count <= 0:
            return 0.0
        return self.total_revenue / self.product_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "products": self.products,
            "product_count": self.product_count,
            "total_spend": round(self.total_spend, 2),
            "total_revenue": round(self.total_revenue, 2),
            "total_roas": round(self.total_roas, 4),
            "risk_score": round(self.risk_score, 4),
            "growth_score": round(self.growth_score, 4),
            "diversity_score": round(self.diversity_score, 4),
            "is_profitable": self.is_profitable,
            "is_healthy": self.is_healthy,
        }

    def __repr__(self) -> str:
        return (
            f"PortfolioSnapshot(products={self.product_count}, "
            f"roas={self.total_roas:.2f}, "
            f"growth={self.growth_score:.2f})"
        )


# ── ProductFitness ─────────────────────────────────────────


@dataclass
class ProductFitness:
    """产品适应度评分。

    用于产品组合内的排名和资源分配。

    公式:
      total_fitness = revenue_potential × 0.30
                    + growth_velocity × 0.25
                    + creative_scalability × 0.20
                    + market_opportunity × 0.15
                    + risk × 0.10

    Attributes:
        product_id:            产品 ID
        revenue_potential:     收入潜力 [0, 1]
        growth_velocity:       增长速度 [0, 1]
        creative_scalability:  创意可扩展性 [0, 1]
        market_opportunity:    市场机会 [0, 1]
        risk:                  风险评分 [0, 1]（越低越好）
        total_fitness:         总适应度 [0, 1]
        rank:                  排名（1-based）
        lifecycle_stage:       生命周期阶段
        metadata:              附加元数据
    """

    product_id: str = ""
    revenue_potential: float = 0.5
    growth_velocity: float = 0.5
    creative_scalability: float = 0.5
    market_opportunity: float = 0.5
    risk: float = 0.5
    total_fitness: float = 0.0
    rank: int = 0
    lifecycle_stage: ProductLifecycleStage = ProductLifecycleStage.PEAK
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def risk_adjusted_fitness(self) -> float:
        """风险调整后适应度。"""
        return self.total_fitness * (1.0 - self.risk * 0.5)

    @property
    def is_high_potential(self) -> bool:
        return self.total_fitness >= 0.70

    @property
    def is_low_potential(self) -> bool:
        return self.total_fitness < 0.30

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "revenue_potential": round(self.revenue_potential, 4),
            "growth_velocity": round(self.growth_velocity, 4),
            "creative_scalability": round(self.creative_scalability, 4),
            "market_opportunity": round(self.market_opportunity, 4),
            "risk": round(self.risk, 4),
            "total_fitness": round(self.total_fitness, 4),
            "risk_adjusted_fitness": round(self.risk_adjusted_fitness, 4),
            "rank": self.rank,
            "lifecycle_stage": self.lifecycle_stage.value,
            "is_high_potential": self.is_high_potential,
        }

    def __repr__(self) -> str:
        return (
            f"ProductFitness(product={self.product_id}, "
            f"fitness={self.total_fitness:.2f}, "
            f"rank=#{self.rank})"
        )


# ── BudgetAllocation ───────────────────────────────────────


@dataclass
class BudgetAllocation:
    """预算分配结果。

    Attributes:
        product_id:        产品 ID
        allocated_budget:  分配预算金额
        allocation_pct:    分配占比 [0, 1]
        previous_budget:   之前预算
        change_pct:        变化百分比
        reason:            分配理由
    """

    product_id: str = ""
    allocated_budget: float = 0.0
    allocation_pct: float = 0.0
    previous_budget: float = 0.0
    change_pct: float = 0.0
    reason: str = ""

    @property
    def is_increased(self) -> bool:
        return self.change_pct > 0.01

    @property
    def is_decreased(self) -> bool:
        return self.change_pct < -0.01

    @property
    def is_maintained(self) -> bool:
        return -0.01 <= self.change_pct <= 0.01

    @property
    def is_zero(self) -> bool:
        return self.allocated_budget <= 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "allocated_budget": round(self.allocated_budget, 2),
            "allocation_pct": round(self.allocation_pct, 4),
            "previous_budget": round(self.previous_budget, 2),
            "change_pct": round(self.change_pct, 4),
            "reason": self.reason,
            "is_increased": self.is_increased,
            "is_decreased": self.is_decreased,
            "is_zero": self.is_zero,
        }

    def __repr__(self) -> str:
        direction = "+" if self.is_increased else ("-" if self.is_decreased else "=")
        return (
            f"BudgetAllocation(product={self.product_id}, "
            f"amount={self.allocated_budget:.0f}, "
            f"{direction}{abs(self.change_pct):.0%})"
        )


# ── ExperimentAllocation ───────────────────────────────────


@dataclass
class ExperimentAllocation:
    """实验槽位分配结果。

    Attributes:
        product_id:         产品 ID
        allocated_slots:    分配实验槽位数
        allocation_pct:     分配占比 [0, 1]
        previous_slots:     之前槽位数
        change_pct:         变化百分比
        reason:             分配理由
    """

    product_id: str = ""
    allocated_slots: int = 0
    allocation_pct: float = 0.0
    previous_slots: int = 0
    change_pct: float = 0.0
    reason: str = ""

    @property
    def is_increased(self) -> bool:
        return self.change_pct > 0.01

    @property
    def is_decreased(self) -> bool:
        return self.change_pct < -0.01

    @property
    def is_maintained(self) -> bool:
        return -0.01 <= self.change_pct <= 0.01

    @property
    def is_zero(self) -> bool:
        return self.allocated_slots <= 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "allocated_slots": self.allocated_slots,
            "allocation_pct": round(self.allocation_pct, 4),
            "previous_slots": self.previous_slots,
            "change_pct": round(self.change_pct, 4),
            "reason": self.reason,
            "is_increased": self.is_increased,
            "is_decreased": self.is_decreased,
            "is_zero": self.is_zero,
        }

    def __repr__(self) -> str:
        direction = "+" if self.is_increased else ("-" if self.is_decreased else "=")
        return (
            f"ExperimentAllocation(product={self.product_id}, "
            f"slots={self.allocated_slots}, "
            f"{direction}{abs(self.change_pct):.0%})"
        )


# ── PortfolioDecision ──────────────────────────────────────


@dataclass
class PortfolioDecision:
    """产品组合决策。

    针对单个产品的组合级操作建议。

    Attributes:
        decision_id:       决策 ID
        product_id:        产品 ID
        action:            组合动作
        budget_change:     预算变化比例
        experiment_change: 实验槽位变化数
        confidence:        决策置信度 [0, 1]
        reasons:           决策理由列表
        fitness:           产品适应度
        lifecycle_stage:   生命周期阶段
        created_at:        创建时间
    """

    decision_id: str = ""
    product_id: str = ""
    action: PortfolioAction = PortfolioAction.MAINTAIN
    budget_change: float = 0.0
    experiment_change: int = 0
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    fitness: float = 0.0
    lifecycle_stage: ProductLifecycleStage = ProductLifecycleStage.PEAK
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = _gen_id("PD")

    @property
    def is_actionable(self) -> bool:
        return self.action != PortfolioAction.MAINTAIN and self.confidence >= 0.50

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.80

    @property
    def is_expansion(self) -> bool:
        return self.action in (
            PortfolioAction.INCREASE_INVESTMENT,
            PortfolioAction.EXPLORE,
        )

    @property
    def is_contraction(self) -> bool:
        return self.action in (
            PortfolioAction.DECREASE_INVESTMENT,
            PortfolioAction.HARVEST,
            PortfolioAction.SUNSET,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "product_id": self.product_id,
            "action": self.action.value,
            "budget_change": round(self.budget_change, 4),
            "experiment_change": self.experiment_change,
            "confidence": round(self.confidence, 4),
            "reasons": self.reasons,
            "fitness": round(self.fitness, 4),
            "lifecycle_stage": self.lifecycle_stage.value,
            "is_actionable": self.is_actionable,
            "is_high_confidence": self.is_high_confidence,
            "is_expansion": self.is_expansion,
            "is_contraction": self.is_contraction,
        }

    def __repr__(self) -> str:
        return (
            f"PortfolioDecision(product={self.product_id}, "
            f"action={self.action.value}, "
            f"conf={self.confidence:.2f})"
        )


# ── PortfolioResult ────────────────────────────────────────


@dataclass
class PortfolioResult:
    """产品组合优化结果。

    E12.6.5 核心输出。

    Attributes:
        result_id:              结果 ID
        total_budget:           总预算
        total_experiments:      总实验槽位
        budget_allocations:     预算分配列表
        experiment_allocations: 实验分配列表
        decisions:              组合决策列表
        fitness_scores:         适应度评分列表
        snapshot:               组合状态快照
        summary:                结果摘要
        created_at:             创建时间
    """

    result_id: str = ""
    total_budget: float = 0.0
    total_experiments: int = 0
    budget_allocations: list[BudgetAllocation] = field(default_factory=list)
    experiment_allocations: list[ExperimentAllocation] = field(default_factory=list)
    decisions: list[PortfolioDecision] = field(default_factory=list)
    fitness_scores: list[ProductFitness] = field(default_factory=list)
    snapshot: PortfolioSnapshot | None = None
    summary: str = ""
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.result_id:
            self.result_id = _gen_id("PR")

    @property
    def total_allocated_budget(self) -> float:
        return sum(a.allocated_budget for a in self.budget_allocations)

    @property
    def total_allocated_experiments(self) -> int:
        return sum(a.allocated_slots for a in self.experiment_allocations)

    @property
    def budget_utilization(self) -> float:
        if self.total_budget <= 0:
            return 0.0
        return min(1.0, self.total_allocated_budget / self.total_budget)

    @property
    def expansion_count(self) -> int:
        return sum(1 for d in self.decisions if d.is_expansion)

    @property
    def contraction_count(self) -> int:
        return sum(1 for d in self.decisions if d.is_contraction)

    @property
    def top_product(self) -> str:
        if not self.fitness_scores:
            return ""
        return max(self.fitness_scores, key=lambda f: f.total_fitness).product_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "total_budget": round(self.total_budget, 2),
            "total_experiments": self.total_experiments,
            "total_allocated_budget": round(self.total_allocated_budget, 2),
            "total_allocated_experiments": self.total_allocated_experiments,
            "budget_utilization": round(self.budget_utilization, 4),
            "expansion_count": self.expansion_count,
            "contraction_count": self.contraction_count,
            "top_product": self.top_product,
            "budget_allocations": [a.to_dict() for a in self.budget_allocations],
            "experiment_allocations": [a.to_dict() for a in self.experiment_allocations],
            "decisions": [d.to_dict() for d in self.decisions],
            "fitness_scores": [f.to_dict() for f in self.fitness_scores],
            "summary": self.summary,
        }

    def __repr__(self) -> str:
        return (
            f"PortfolioResult(products={len(self.fitness_scores)}, "
            f"budget={self.total_budget:.0f}, "
            f"expansion={self.expansion_count}, "
            f"contraction={self.contraction_count})"
        )