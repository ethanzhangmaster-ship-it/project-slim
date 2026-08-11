"""E11.3.3 Selection Schema — 自然选择数据模型。

定义 Selection 层的稳定契约：

  SelectionMode   — 选择模式 (ELITE / THRESHOLD / DIVERSITY)
  SelectionPolicy — 选择策略 (mode, top_k, min_score, diversity_limit)
  Survivor        — 存活者 (genome_id, score, rank, reason)
  SelectionResult — 选择结果 (population_id, survivors, eliminated)

数据流：
  Population → SelectionPolicy → Survivors[] → SelectionResult → Next Generation
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# SelectionMode — 选择模式
# ═══════════════════════════════════════════════════════════

class SelectionMode(Enum):
    """自然选择模式。

    ELITE     — 精英选择：保留排名前 top_k 的成员
    THRESHOLD — 阈值选择：保留 score >= min_score 的成员
    DIVERSITY — 多样性选择：按基因指纹去重，保留多样性
    """
    ELITE = "elite"
    THRESHOLD = "threshold"
    DIVERSITY = "diversity"


# ═══════════════════════════════════════════════════════════
# SelectionPolicy — 选择策略
# ═══════════════════════════════════════════════════════════

@dataclass
class SelectionPolicy:
    """描述一条选择规则。

    例如：
        # 精英选择
        SelectionPolicy(mode=SelectionMode.ELITE, top_k=5)

        # 阈值选择
        SelectionPolicy(mode=SelectionMode.THRESHOLD, min_score=0.75)

        # 多样性选择
        SelectionPolicy(mode=SelectionMode.DIVERSITY, diversity_limit=3)
    """
    mode: SelectionMode = SelectionMode.ELITE
    top_k: int = 5
    min_score: float = 0.5
    diversity_limit: int = 3  # 同一基因指纹最多保留的数量

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "top_k": self.top_k,
            "min_score": self.min_score,
            "diversity_limit": self.diversity_limit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelectionPolicy:
        return cls(
            mode=SelectionMode(data.get("mode", "elite")),
            top_k=data.get("top_k", 5),
            min_score=data.get("min_score", 0.5),
            diversity_limit=data.get("diversity_limit", 3),
        )

    def __repr__(self) -> str:
        if self.mode == SelectionMode.ELITE:
            return f"SelectionPolicy(ELITE, top_k={self.top_k})"
        elif self.mode == SelectionMode.THRESHOLD:
            return f"SelectionPolicy(THRESHOLD, min={self.min_score})"
        return f"SelectionPolicy(DIVERSITY, limit={self.diversity_limit})"


# ═══════════════════════════════════════════════════════════
# Survivor — 存活者
# ═══════════════════════════════════════════════════════════

@dataclass
class Survivor:
    """描述一次选择后存活的 Genome。

    例如：
        Survivor(genome_id="genome_001", score=0.91, rank=1, reason="elite_top_2")
    """
    genome_id: str
    score: float = 0.0
    rank: int = 0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "score": self.score,
            "rank": self.rank,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Survivor:
        return cls(
            genome_id=data["genome_id"],
            score=data.get("score", 0.0),
            rank=data.get("rank", 0),
            reason=data.get("reason", ""),
        )

    def __repr__(self) -> str:
        return f"Survivor({self.genome_id!r}, score={self.score}, rank={self.rank})"


# ═══════════════════════════════════════════════════════════
# SelectionResult — 选择结果
# ═══════════════════════════════════════════════════════════

@dataclass
class SelectionResult:
    """一次选择操作的完整结果。

    记录了存活者和淘汰者，以及选择的代际信息。

    例如：
        SelectionResult(
            population_id="pop_001",
            survivors=[Survivor("genome_001", 0.91, 1), Survivor("genome_002", 0.85, 2)],
            eliminated=["genome_003"],
            generation=1,
        )
    """
    population_id: str = ""
    survivors: list[Survivor] = field(default_factory=list)
    eliminated: list[str] = field(default_factory=list)
    generation: int = 1
    policy: SelectionPolicy | None = None
    selection_id: str = field(default_factory=lambda: f"sel_{uuid.uuid4().hex[:8]}")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 属性 ──────────────────────────────────────────

    @property
    def survivor_count(self) -> int:
        """存活数量。"""
        return len(self.survivors)

    @property
    def eliminated_count(self) -> int:
        """淘汰数量。"""
        return len(self.eliminated)

    @property
    def survival_rate(self) -> float:
        """存活率 = survivors / (survivors + eliminated)。"""
        total = self.survivor_count + self.eliminated_count
        if total == 0:
            return 0.0
        return round(self.survivor_count / total, 4)

    @property
    def survivor_ids(self) -> list[str]:
        """存活者 ID 列表。"""
        return [s.genome_id for s in self.survivors]

    def get_survivor(self, genome_id: str) -> Survivor | None:
        """按 genome_id 查找存活者。"""
        for s in self.survivors:
            if s.genome_id == genome_id:
                return s
        return None

    def is_survivor(self, genome_id: str) -> bool:
        """检查 genome_id 是否存活。"""
        return self.get_survivor(genome_id) is not None

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "population_id": self.population_id,
            "generation": self.generation,
            "survivors": [s.to_dict() for s in self.survivors],
            "eliminated": self.eliminated,
            "policy": self.policy.to_dict() if self.policy else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelectionResult:
        survivors = [Survivor.from_dict(s) for s in data.get("survivors", [])]
        policy_data = data.get("policy")
        policy = SelectionPolicy.from_dict(policy_data) if policy_data else None
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            selection_id=data.get("selection_id", ""),
            population_id=data.get("population_id", ""),
            generation=data.get("generation", 1),
            survivors=survivors,
            eliminated=data.get("eliminated", []),
            policy=policy,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"SelectionResult(pop={self.population_id!r}, "
            f"gen={self.generation}, "
            f"survivors={self.survivor_count}/{self.survivor_count + self.eliminated_count})"
        )