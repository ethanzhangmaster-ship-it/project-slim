"""E12.6.2 — Resource Controller Models。

Resource Controller 的核心数据模型。

核心模型:
  ResourceType:          资源类型枚举
  ResourceRequest:       资源请求（输入）
  ResourceAllocation:    资源分配结果（输出）
  ProductResourceState:  产品资源状态
  BudgetAdjustment:      预算调整记录
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import exp
from typing import Any


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── ResourceType ────────────────────────────────────────────


class ResourceType(str, Enum):
    """资源类型。

    系统可以分配的五种资源。
    """

    EXPERIMENT_BUDGET = "experiment_budget"
    MUTATION_BUDGET = "mutation_budget"
    GENERATION_CAPACITY = "generation_capacity"
    ANALYSIS_COMPUTE = "analysis_compute"
    HUMAN_REVIEW = "human_review"


# 资源类型标签
_RESOURCE_LABELS: dict[ResourceType, str] = {
    ResourceType.EXPERIMENT_BUDGET: "实验预算",
    ResourceType.MUTATION_BUDGET: "突变预算",
    ResourceType.GENERATION_CAPACITY: "生成容量",
    ResourceType.ANALYSIS_COMPUTE: "分析算力",
    ResourceType.HUMAN_REVIEW: "人工审核",
}


def get_resource_label(resource_type: ResourceType) -> str:
    return _RESOURCE_LABELS.get(resource_type, resource_type.value)


# ── ResourceRequest ─────────────────────────────────────────


@dataclass
class ResourceRequest:
    """资源请求 —— 产品向 Resource Controller 申请资源。

    Attributes:
        request_id:       请求 ID
        product_id:       产品 ID
        resource_type:    资源类型
        requested_amount: 请求金额
        reason:           请求原因
        expected_return:  预期回报（ROI 倍数）
        urgency:          紧急程度 [0, 1]
        learning_value:   学习价值 [0, 1]
        priority_score:   优先级评分（由 Controller 计算）
        metadata:         附加元数据
    """

    request_id: str = ""
    product_id: str = ""
    resource_type: ResourceType = ResourceType.EXPERIMENT_BUDGET
    requested_amount: float = 0.0
    reason: str = ""
    expected_return: float = 1.0
    urgency: float = 0.5
    learning_value: float = 0.5
    priority_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id:
            self.request_id = _gen_id("RR")

    @property
    def is_urgent(self) -> bool:
        return self.urgency >= 0.70

    @property
    def is_high_value(self) -> bool:
        return self.expected_return >= 1.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "product_id": self.product_id,
            "resource_type": self.resource_type.value,
            "requested_amount": round(self.requested_amount, 2),
            "reason": self.reason,
            "expected_return": round(self.expected_return, 4),
            "urgency": round(self.urgency, 4),
            "learning_value": round(self.learning_value, 4),
            "priority_score": round(self.priority_score, 4),
        }

    def __repr__(self) -> str:
        return (
            f"ResourceRequest(product={self.product_id}, "
            f"type={self.resource_type.value}, "
            f"amount={self.requested_amount:.2f})"
        )


# ── ResourceAllocation ──────────────────────────────────────


@dataclass
class ResourceAllocation:
    """资源分配结果 —— Controller 输出。

    Attributes:
        allocation_id:    分配 ID
        product_id:       产品 ID
        resource_type:    资源类型
        allocated_amount: 分配金额
        allocation_score: 分配评分
        priority:         优先级
        reasons:          分配理由
        created_at:       创建时间
        request_id:       关联的请求 ID
        expected_roi:     预期 ROI
        confidence:       分配置信度
    """

    allocation_id: str = ""
    product_id: str = ""
    resource_type: ResourceType = ResourceType.EXPERIMENT_BUDGET
    allocated_amount: float = 0.0
    allocation_score: float = 0.0
    priority: int = 0
    reasons: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)
    request_id: str = ""
    expected_roi: float = 0.0
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.allocation_id:
            self.allocation_id = _gen_id("RA")

    @property
    def is_funded(self) -> bool:
        return self.allocated_amount > 0

    @property
    def is_fully_funded(self) -> bool:
        return self.allocated_amount >= self.allocation_score * 0.90

    def to_dict(self) -> dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "product_id": self.product_id,
            "resource_type": self.resource_type.value,
            "allocated_amount": round(self.allocated_amount, 2),
            "allocation_score": round(self.allocation_score, 4),
            "priority": self.priority,
            "reasons": self.reasons,
            "created_at": self.created_at.isoformat(),
            "request_id": self.request_id,
            "expected_roi": round(self.expected_roi, 4),
            "confidence": round(self.confidence, 4),
            "is_funded": self.is_funded,
        }

    def __repr__(self) -> str:
        return (
            f"ResourceAllocation(product={self.product_id}, "
            f"amount={self.allocated_amount:.2f}, "
            f"score={self.allocation_score:.2f})"
        )


# ── ProductResourceState ────────────────────────────────────


@dataclass
class ProductResourceState:
    """产品资源状态 —— 追踪产品当前资源使用情况。

    Attributes:
        product_id:              产品 ID
        total_budget:            总预算
        allocated_budget:        已分配预算
        spent_budget:            已消耗预算
        active_experiments:      活跃实验数
        active_mutations:        活跃突变数
        generation_queue_size:   生成队列大小
        recent_roas:             最近 ROAS
        fatigue_score:           疲劳度
        prediction_confidence:   预测置信度
        population_diversity:    种群多样性
        last_allocation_time:    上次分配时间
        updated_at:              更新时间
    """

    product_id: str = ""
    total_budget: float = 0.0
    allocated_budget: float = 0.0
    spent_budget: float = 0.0
    active_experiments: int = 0
    active_mutations: int = 0
    generation_queue_size: int = 0
    recent_roas: float = 1.0
    fatigue_score: float = 0.0
    prediction_confidence: float = 0.5
    population_diversity: float = 0.5
    last_allocation_time: datetime | None = None
    updated_at: datetime = field(default_factory=_now)

    @property
    def budget_remaining(self) -> float:
        return max(0.0, self.total_budget - self.allocated_budget)

    @property
    def budget_utilization(self) -> float:
        if self.total_budget <= 0:
            return 0.0
        return min(1.0, self.allocated_budget / self.total_budget)

    @property
    def spend_efficiency(self) -> float:
        if self.spent_budget <= 0:
            return 0.0
        return self.recent_roas

    @property
    def is_healthy(self) -> bool:
        return (
            self.fatigue_score < 0.50
            and self.prediction_confidence >= 0.60
            and self.population_diversity >= 0.30
        )

    @property
    def needs_attention(self) -> bool:
        return (
            self.fatigue_score >= 0.80
            or self.recent_roas < 0.50
            or self.population_diversity < 0.20
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "total_budget": round(self.total_budget, 2),
            "allocated_budget": round(self.allocated_budget, 2),
            "spent_budget": round(self.spent_budget, 2),
            "budget_remaining": round(self.budget_remaining, 2),
            "budget_utilization": round(self.budget_utilization, 4),
            "active_experiments": self.active_experiments,
            "active_mutations": self.active_mutations,
            "recent_roas": round(self.recent_roas, 4),
            "fatigue_score": round(self.fatigue_score, 4),
            "prediction_confidence": round(self.prediction_confidence, 4),
            "population_diversity": round(self.population_diversity, 4),
            "is_healthy": self.is_healthy,
            "needs_attention": self.needs_attention,
        }

    def __repr__(self) -> str:
        return (
            f"ProductResourceState(product={self.product_id}, "
            f"roas={self.recent_roas:.2f}, "
            f"budget={self.allocated_budget:.0f}/{self.total_budget:.0f})"
        )


# ── BudgetAdjustment ────────────────────────────────────────


@dataclass
class BudgetAdjustment:
    """预算调整记录。

    Attributes:
        adjustment_id:    调整 ID
        product_id:       产品 ID
        resource_type:    资源类型
        previous_amount:  调整前金额
        new_amount:       调整后金额
        change_pct:       变化百分比
        reason:           调整原因
        adjusted_at:      调整时间
    """

    adjustment_id: str = ""
    product_id: str = ""
    resource_type: ResourceType = ResourceType.EXPERIMENT_BUDGET
    previous_amount: float = 0.0
    new_amount: float = 0.0
    change_pct: float = 0.0
    reason: str = ""
    adjusted_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.adjustment_id:
            self.adjustment_id = _gen_id("BA")
        if self.change_pct == 0.0 and self.previous_amount > 0:
            self.change_pct = (self.new_amount - self.previous_amount) / self.previous_amount

    @property
    def is_increase(self) -> bool:
        return self.change_pct > 0

    @property
    def is_decrease(self) -> bool:
        return self.change_pct < 0

    @property
    def is_frozen(self) -> bool:
        return self.new_amount == 0 and self.previous_amount > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjustment_id": self.adjustment_id,
            "product_id": self.product_id,
            "resource_type": self.resource_type.value,
            "previous_amount": round(self.previous_amount, 2),
            "new_amount": round(self.new_amount, 2),
            "change_pct": round(self.change_pct, 4),
            "reason": self.reason,
            "adjusted_at": self.adjusted_at.isoformat(),
            "is_increase": self.is_increase,
            "is_decrease": self.is_decrease,
            "is_frozen": self.is_frozen,
        }

    def __repr__(self) -> str:
        direction = "+" if self.is_increase else ""
        return (
            f"BudgetAdjustment(product={self.product_id}, "
            f"{direction}{self.change_pct:.0%}, "
            f"reason={self.reason[:30]})"
        )


# ── Priority Score Calculation ──────────────────────────────


def calculate_priority_score(
    expected_roi: float,
    learning_value: float,
    urgency: float,
    confidence: float,
) -> float:
    """计算资源优先级评分。

    公式:
      priority_score = normalized_roi × learning_value × urgency × confidence

    其中 normalized_roi = min(1.0, max(0.0, expected_roi / 3.0))
    确保每个因子在 [0, 1] 范围内。

    Returns:
        float: 优先级评分 [0, 1]
    """
    normalized_roi = max(0.0, min(1.0, expected_roi / 3.0))
    learning_value = max(0.0, min(1.0, learning_value))
    urgency = max(0.0, min(1.0, urgency))
    confidence = max(0.0, min(1.0, confidence))

    return round(normalized_roi * learning_value * urgency * confidence, 6)


def softmax_allocate(
    scores: list[tuple[str, float]],
    total_budget: float,
    min_allocation: float = 0.0,
) -> list[tuple[str, float]]:
    """Softmax 资源分配。

    使用 softmax 将总预算按优先级评分比例分配给多个产品。

    Args:
        scores:         [(product_id, priority_score), ...]
        total_budget:   总预算
        min_allocation: 最小分配金额（低于此值的产品将获得 0）

    Returns:
        [(product_id, allocated_amount), ...]
    """
    if not scores or total_budget <= 0:
        return [(pid, 0.0) for pid, _ in scores]

    # 处理负分数：将所有分数平移到非负范围
    raw_scores = [s for _, s in scores]
    min_score = min(raw_scores)
    if min_score < 0:
        raw_scores = [s - min_score for s in raw_scores]

    # 计算 softmax
    exp_scores = [exp(s) for s in raw_scores]
    sum_exp = sum(exp_scores)

    if sum_exp <= 0:
        return [(pid, 0.0) for pid, _ in scores]

    allocations: list[tuple[str, float]] = []
    for (pid, _), es in zip(scores, exp_scores):
        share = es / sum_exp
        amount = round(share * total_budget, 2)
        if amount < min_allocation:
            amount = 0.0
        allocations.append((pid, amount))

    # 由于四舍五入可能导致总和偏差，调整最大的分配
    total_allocated = sum(a for _, a in allocations)
    if total_allocated > 0 and abs(total_allocated - total_budget) > 0.01:
        diff = round(total_budget - total_allocated, 2)
        # 加到分配最多的产品上
        max_idx = max(range(len(allocations)), key=lambda i: allocations[i][1])
        pid, amount = allocations[max_idx]
        allocations[max_idx] = (pid, round(amount + diff, 2))

    return allocations