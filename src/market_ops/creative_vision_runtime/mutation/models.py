"""E11.4.2 — Mutation Mapping Models。

MutationGeneChange:  单个基因突变
VisionMutationPlan:  视觉驱动的突变计划（连接 V5 Mutation Engine）
MutationConstraint:  突变约束
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MutationGeneChange:
    """单个基因突变。

    Attributes:
        gene_name:   基因组基因名
        old_value:   突变前值
        new_value:   突变后值
        operator:    操作符 (increase/decrease/set)
        confidence:  置信度 (0-1)
        delta:       变化量 (new - old)
        reason:      突变原因
        source_pattern: 来源视觉模式
    """

    gene_name: str = ""
    old_value: float = 0.0
    new_value: float = 0.0
    operator: str = "increase"
    confidence: float = 0.0
    delta: float = 0.0
    reason: str = ""
    source_pattern: str = ""

    def __post_init__(self) -> None:
        self.delta = round(self.new_value - self.old_value, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_name": self.gene_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "operator": self.operator,
            "confidence": self.confidence,
            "delta": self.delta,
            "reason": self.reason,
            "source_pattern": self.source_pattern,
        }

    def __repr__(self) -> str:
        return (
            f"MutationGeneChange({self.gene_name}: "
            f"{self.old_value:.2f}→{self.new_value:.2f}, "
            f"Δ={self.delta:+.2f})"
        )


@dataclass
class MutationConstraint:
    """基因突变约束。

    Attributes:
        gene_name:    基因名
        min_value:    最小值
        max_value:    最大值
        max_delta:    单次最大变化量
        min_delta:    单次最小变化量
        direction:    允许方向 (increase/decrease/both)
    """

    gene_name: str
    min_value: float = 0.0
    max_value: float = 1.0
    max_delta: float = 0.25
    min_delta: float = 0.05
    direction: str = "both"  # increase / decrease / both

    def clamp(self, value: float) -> float:
        """将值限制在 [min_value, max_value] 范围内。"""
        return max(self.min_value, min(self.max_value, value))

    def clamp_delta(self, delta: float, direction: str) -> float:
        """限制变化量。

        Args:
            delta:     原始变化量
            direction: 变化方向 (increase/decrease)

        Returns:
            限制后的变化量
        """
        abs_delta = abs(delta)
        if abs_delta < self.min_delta:
            abs_delta = 0.0
        abs_delta = min(abs_delta, self.max_delta)

        if direction == "decrease":
            return -abs_delta
        return abs_delta

    def is_valid(self, old_value: float, new_value: float) -> bool:
        """检查突变是否合法。"""
        if new_value < self.min_value or new_value > self.max_value:
            return False
        if self.direction == "increase" and new_value <= old_value:
            return False
        if self.direction == "decrease" and new_value >= old_value:
            return False
        return abs(new_value - old_value) <= self.max_delta

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_name": self.gene_name,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "max_delta": self.max_delta,
            "min_delta": self.min_delta,
            "direction": self.direction,
        }

    def __repr__(self) -> str:
        return (
            f"MutationConstraint({self.gene_name}: "
            f"[{self.min_value}, {self.max_value}], "
            f"max_delta={self.max_delta})"
        )


@dataclass
class VisionMutationPlan:
    """视觉驱动的突变计划 — 连接 V5 Mutation Engine。

    Attributes:
        plan_id:             计划 ID
        asset_id:            素材 ID
        source_decision_id:  来源 VisionDecision ID
        changes:             基因突变列表
        priority:            优先级 (high/medium/low)
        expected_impact:     预期影响描述
        total_confidence:    总体置信度
        summary:             计划总结
        created_at:          创建时间
    """

    plan_id: str = ""
    asset_id: str = ""
    source_decision_id: str = ""

    changes: list[MutationGeneChange] = field(default_factory=list)
    priority: str = "medium"
    expected_impact: str = ""
    total_confidence: float = 0.0
    summary: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = f"vmp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def change_count(self) -> int:
        return len(self.changes)

    @property
    def genes_touched(self) -> list[str]:
        return [c.gene_name for c in self.changes]

    @property
    def max_delta(self) -> float:
        if not self.changes:
            return 0.0
        return max(abs(c.delta) for c in self.changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "asset_id": self.asset_id,
            "source_decision_id": self.source_decision_id,
            "changes": [c.to_dict() for c in self.changes],
            "priority": self.priority,
            "expected_impact": self.expected_impact,
            "total_confidence": self.total_confidence,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"VisionMutationPlan(asset={self.asset_id}, "
            f"changes={self.change_count}, "
            f"priority={self.priority})"
        )