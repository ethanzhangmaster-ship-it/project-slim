"""E11.2 Mutation Schema — 创意基因变异数据模型。

定义 Mutation Engine 的稳定契约：

  MutationType    — 变异类型枚举 (REPLACE/COMBINE/ENHANCE/REMOVE)
  MutationTarget  — 单次变异目标 (基因名 + 旧值 + 新值)
  MutationRule    — 变异规则 (目标基因 + 策略 + 优先级)
  MutationResult  — 变异结果 (父代 → 子代 + 变更列表)
  MutationHistory — 进化链记录 (谱系追踪)

数据流：
  CreativeGenome → MutationRule → MutationTarget → MutationResult → MutationHistory
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# MutationType — 变异类型枚举
# ═══════════════════════════════════════════════════════════

class MutationType(Enum):
    """变异操作类型。

    REPLACE — 替换基因值（如 hook A → hook B）
    COMBINE — 组合两个基因维度（如 emotion + reward）
    ENHANCE — 强化已有基因值（如 increase curiosity strength）
    REMOVE  — 删除弱基因值
    """
    REPLACE = "replace"
    COMBINE = "combine"
    ENHANCE = "enhance"
    REMOVE = "remove"


# ═══════════════════════════════════════════════════════════
# MutationTarget — 单次变异目标
# ═══════════════════════════════════════════════════════════

@dataclass
class MutationTarget:
    """描述一次基因变异的具体目标。

    例如：
        MutationTarget(
            gene_name="hook",
            old_value="rescue",
            new_value="discovery",
            confidence=0.85,
        )
    """
    gene_name: str
    old_value: Any = None
    new_value: Any = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_name": self.gene_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MutationTarget:
        return cls(
            gene_name=data["gene_name"],
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            confidence=data.get("confidence", 0.0),
        )


# ═══════════════════════════════════════════════════════════
# MutationRule — 变异规则
# ═══════════════════════════════════════════════════════════

@dataclass
class MutationRule:
    """描述一条变异规则。

    规则定义了：
      - 对哪个基因槽位进行操作
      - 使用什么变异类型
      - 基于什么策略（如 winner_pattern, random, targeted）
      - 规则优先级

    例如：
        MutationRule(
            target_gene="hook",
            mutation_type=MutationType.REPLACE,
            strategy="winner_pattern",
            priority=0.8,
        )
    """
    target_gene: str
    mutation_type: MutationType
    strategy: str
    priority: float = 0.5
    rule_id: str = field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "target_gene": self.target_gene,
            "mutation_type": self.mutation_type.value,
            "strategy": self.strategy,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MutationRule:
        return cls(
            rule_id=data.get("rule_id", ""),
            target_gene=data["target_gene"],
            mutation_type=MutationType(data["mutation_type"]),
            strategy=data["strategy"],
            priority=data.get("priority", 0.5),
        )


# ═══════════════════════════════════════════════════════════
# MutationResult — 变异结果
# ═══════════════════════════════════════════════════════════

@dataclass
class MutationResult:
    """描述一次变异操作的输出。

    记录了父代 → 子代的关系和所有变更。

    例如：
        MutationResult(
            parent_genome_id="genome_001",
            child_genome_id="genome_002",
            changes=[MutationTarget(...)],
            success=True,
        )
    """
    parent_genome_id: str
    child_genome_id: str
    changes: list[MutationTarget] = field(default_factory=list)
    mutation_id: str = field(default_factory=lambda: f"mutation_{uuid.uuid4().hex[:8]}")
    success: bool = True

    def add_change(self, target: MutationTarget) -> None:
        """添加一个变更记录。"""
        self.changes.append(target)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "parent_genome_id": self.parent_genome_id,
            "child_genome_id": self.child_genome_id,
            "changes": [c.to_dict() for c in self.changes],
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MutationResult:
        changes = [MutationTarget.from_dict(c) for c in data.get("changes", [])]
        return cls(
            mutation_id=data.get("mutation_id", ""),
            parent_genome_id=data["parent_genome_id"],
            child_genome_id=data["child_genome_id"],
            changes=changes,
            success=data.get("success", True),
        )


# ═══════════════════════════════════════════════════════════
# MutationHistory — 进化链记录
# ═══════════════════════════════════════════════════════════

@dataclass
class MutationHistory:
    """记录一次变异操作的完整历史。

    用于追踪进化链：
        winner genome → mutation #001 → child → mutation #002 → new candidate

    例如：
        MutationHistory(
            mutation_id="mutation_001",
            parent_id="genome_001",
            child_id="genome_002",
            rule_id="rule_abc123",
        )
    """
    mutation_id: str
    parent_id: str
    child_id: str
    rule_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "parent_id": self.parent_id,
            "child_id": self.child_id,
            "rule_id": self.rule_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MutationHistory:
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            mutation_id=data["mutation_id"],
            parent_id=data["parent_id"],
            child_id=data["child_id"],
            rule_id=data.get("rule_id"),
            created_at=created_at or datetime.now(timezone.utc),
        )