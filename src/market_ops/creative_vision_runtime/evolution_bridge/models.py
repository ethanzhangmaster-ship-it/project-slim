"""E11.4.3 — Evolution Bridge Models。

GenomeMutationTask:  VisionMutationPlan → Genome 的桥梁数据模型
GeneMutation:       单个基因突变（子结构）
BridgeStatus:       任务状态枚举
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GeneMutation:
    """单个基因突变 — 从 VisionMutationPlan 提取。

    Attributes:
        gene_name:      Genome 基因名 (hook_contrast/color_brightness/...)
        old_value:      突变前值
        new_value:      突变后值
        operator:       操作符 (increase/decrease/set)
        confidence:     置信度 (0-1)
        delta:          变化量 (new - old)
        reason:         突变原因
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeneMutation:
        return cls(
            gene_name=data.get("gene_name", ""),
            old_value=data.get("old_value", 0.0),
            new_value=data.get("new_value", 0.0),
            operator=data.get("operator", "increase"),
            confidence=data.get("confidence", 0.0),
            reason=data.get("reason", ""),
            source_pattern=data.get("source_pattern", ""),
        )

    def __repr__(self) -> str:
        return (
            f"GeneMutation({self.gene_name}: "
            f"{self.old_value:.2f}→{self.new_value:.2f}, "
            f"Δ={self.delta:+.2f})"
        )


@dataclass
class GenomeMutationTask:
    """VisionMutationPlan → Genome 突变任务。

    连接 E11.4.2 VisionMutationPlan 与 V5 Mutation Engine 的桥梁。

    Attributes:
        task_id:             任务 ID
        genome_id:           目标 Genome ID
        asset_id:            素材 ID
        source_plan_id:      来源 VisionMutationPlan ID
        gene_mutations:      基因突变列表
        priority:            优先级 (high/medium/low)
        total_confidence:    总体置信度
        summary:             任务总结
        created_at:          创建时间
        status:              任务状态 (pending/applied/failed)
        applied_at:          应用时间
        error_message:       错误信息
    """

    task_id: str = ""
    genome_id: str = ""
    asset_id: str = ""
    source_plan_id: str = ""

    gene_mutations: list[GeneMutation] = field(default_factory=list)
    priority: str = "medium"
    total_confidence: float = 0.0
    summary: str = ""
    created_at: str = ""

    status: str = "pending"  # pending / applied / failed
    applied_at: str = ""
    error_message: str = ""

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = f"gmt_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def mutation_count(self) -> int:
        return len(self.gene_mutations)

    @property
    def genes_touched(self) -> list[str]:
        return [m.gene_name for m in self.gene_mutations]

    @property
    def max_delta(self) -> float:
        if not self.gene_mutations:
            return 0.0
        return max(abs(m.delta) for m in self.gene_mutations)

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    @property
    def is_applied(self) -> bool:
        return self.status == "applied"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    def mark_applied(self) -> None:
        self.status = "applied"
        self.applied_at = _now()

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.error_message = error
        self.applied_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "genome_id": self.genome_id,
            "asset_id": self.asset_id,
            "source_plan_id": self.source_plan_id,
            "gene_mutations": [m.to_dict() for m in self.gene_mutations],
            "priority": self.priority,
            "total_confidence": self.total_confidence,
            "summary": self.summary,
            "created_at": self.created_at,
            "status": self.status,
            "applied_at": self.applied_at,
            "error_message": self.error_message,
        }

    def __repr__(self) -> str:
        return (
            f"GenomeMutationTask({self.task_id}, "
            f"genome={self.genome_id}, "
            f"mutations={self.mutation_count}, "
            f"status={self.status})"
        )