"""E11.8.2 — Strategy Executor Models。

MutationOperation:  突变操作类型
MutationParameter:  一次突变参数描述
MutationPlan:       Strategy 转换后的执行计划
ExecutionResult:    执行结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MutationOperation(str, Enum):
    """突变操作类型。"""
    MODIFY = "modify"        # 修改现有基因
    CREATE = "create"        # 创建全新基因组
    CROSSOVER = "crossover"  # 交叉组合多个基因
    RETIRE = "retire"        # 退役基因组
    CLONE = "clone"          # 克隆赢家（小幅变体）


@dataclass
class MutationParameter:
    """一次突变参数描述。

    Attributes:
        focus:       突变聚焦维度
        intensity:   突变强度 (0.0-1.0)
        target_gene: 目标基因名称
        description: 突变描述
        metadata:    附加参数
    """

    focus: str = ""
    intensity: float = 0.0
    target_gene: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "focus": self.focus,
            "intensity": self.intensity,
            "target_gene": self.target_gene,
            "description": self.description,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"MutationParameter(focus={self.focus}, "
            f"gene={self.target_gene}, "
            f"intensity={self.intensity:.2f})"
        )


@dataclass
class MutationPlan:
    """Strategy 转换后的执行计划。

    Attributes:
        plan_id:         计划 ID
        strategy_id:     关联的 Strategy ID
        genome_ids:      目标基因组 ID 列表
        operations:      操作列表
        mutations:       突变参数列表
        estimated_cost:  预估资源消耗
        priority:        优先级 (0-100)
        created_at:      创建时间
        metadata:        附加元数据
    """

    plan_id: str = ""
    strategy_id: str = ""
    genome_ids: list[str] = field(default_factory=list)
    operations: list[MutationOperation] = field(default_factory=list)
    mutations: list[MutationParameter] = field(default_factory=list)
    estimated_cost: float = 0.0
    priority: int = 0
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def operation_count(self) -> int:
        return len(self.operations)

    @property
    def mutation_count(self) -> int:
        return len(self.mutations)

    @property
    def total_genomes(self) -> int:
        return len(self.genome_ids)

    @property
    def is_create(self) -> bool:
        return MutationOperation.CREATE in self.operations

    @property
    def is_modify(self) -> bool:
        return MutationOperation.MODIFY in self.operations

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "strategy_id": self.strategy_id,
            "genome_ids": self.genome_ids,
            "operations": [op.value for op in self.operations],
            "mutations": [m.to_dict() for m in self.mutations],
            "estimated_cost": self.estimated_cost,
            "priority": self.priority,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"MutationPlan({self.plan_id}, "
            f"ops={self.operation_count}, "
            f"mutations={self.mutation_count}, "
            f"genomes={self.total_genomes})"
        )


@dataclass
class ExecutionResult:
    """执行结果。

    Attributes:
        plan_id:       计划 ID
        strategy_id:   策略 ID
        tasks_created: 创建的任务数
        task_ids:      任务 ID 列表
        success:       是否全部成功
        reason:        结果说明
        created_at:    创建时间
        metadata:      附加元数据
    """

    plan_id: str = ""
    strategy_id: str = ""
    tasks_created: int = 0
    task_ids: list[str] = field(default_factory=list)
    success: bool = False
    reason: str = ""
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now()

    @property
    def has_tasks(self) -> bool:
        return self.tasks_created > 0

    @property
    def is_partial(self) -> bool:
        """是否部分成功（有任务创建但非全部）。"""
        return self.tasks_created > 0 and not self.success

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "strategy_id": self.strategy_id,
            "tasks_created": self.tasks_created,
            "task_ids": self.task_ids,
            "success": self.success,
            "reason": self.reason,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"ExecutionResult({self.plan_id}, "
            f"tasks={self.tasks_created}, "
            f"success={self.success})"
        )