"""E11.3.1 Fitness Schema — Genome 价值评估数据模型。

定义 Fitness Evaluation 的稳定契约：

  FitnessDirection  — 指标优化方向 (MAXIMIZE / MINIMIZE)
  FitnessMetric     — 单个评估指标 (name, value, weight, direction)
  FitnessScore      — 综合评分 (genome_id, score, metrics, rank)
  FitnessSnapshot   — 评估快照 (时间序列追踪)
  EvaluationResult  — 评估输出 (passed, reason)

数据流：
  CreativeGenome → FitnessMetric[] → FitnessScore → EvaluationResult → Selection
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# FitnessDirection — 优化方向
# ═══════════════════════════════════════════════════════════

class FitnessDirection(Enum):
    """指标优化方向。

    MAXIMIZE — 越高越好（如 ROAS, CTR, Retention）
    MINIMIZE — 越低越好（如 CPI, Crash Rate）
    """
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


# ═══════════════════════════════════════════════════════════
# FitnessMetric — 单个评估指标
# ═══════════════════════════════════════════════════════════

@dataclass
class FitnessMetric:
    """单个 Fitness 评估指标。

    例如：
        FitnessMetric(name="roas_d7", value=0.42, weight=0.5, direction=FitnessDirection.MAXIMIZE)
    """
    name: str
    value: float
    weight: float = 1.0
    direction: FitnessDirection = FitnessDirection.MAXIMIZE

    @property
    def weighted_value(self) -> float:
        """加权值 = value * weight。"""
        return self.value * self.weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "weight": self.weight,
            "direction": self.direction.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitnessMetric:
        return cls(
            name=data["name"],
            value=data["value"],
            weight=data.get("weight", 1.0),
            direction=FitnessDirection(data.get("direction", "maximize")),
        )


# ═══════════════════════════════════════════════════════════
# FitnessScore — 综合评分
# ═══════════════════════════════════════════════════════════

@dataclass
class FitnessScore:
    """Genome 综合 Fitness 评分。

    计算规则：
      - 对每个指标计算加权贡献
      - MAXIMIZE 指标: contribution = weighted_value
      - MINIMIZE 指标: contribution = (1 - normalized_value) * weight
      - score = sum(contributions) / sum(weights)

    例如：
        FitnessScore(
            genome_id="genome_001",
            metrics=[FitnessMetric("roas_d7", 0.42, 0.5, MAXIMIZE)],
        )
    """
    genome_id: str
    metrics: list[FitnessMetric] = field(default_factory=list)
    rank: int = 0

    def __post_init__(self) -> None:
        if not self.metrics:
            self._score = 0.0
        else:
            self._score = self._calculate_score()

    def _calculate_score(self) -> float:
        """计算综合评分。

        对每个指标：
          - MAXIMIZE: contribution = value * weight
          - MINIMIZE: contribution = (1 - value) * weight
        总分 = sum(contributions) / sum(weights)
        """
        total_contribution = 0.0
        total_weight = 0.0

        for metric in self.metrics:
            if metric.direction == FitnessDirection.MAXIMIZE:
                contribution = metric.value * metric.weight
            else:
                # MINIMIZE: 反转值，低值 → 高贡献
                contribution = (1.0 - metric.value) * metric.weight

            total_contribution += contribution
            total_weight += metric.weight

        if total_weight == 0:
            return 0.0

        return round(total_contribution / total_weight, 4)

    @property
    def score(self) -> float:
        """综合评分 (0.0 ~ 1.0)。"""
        return self._score

    @property
    def is_healthy(self) -> bool:
        """评分是否健康（>= 0.5）。"""
        return self._score >= 0.5

    def add_metric(self, metric: FitnessMetric) -> None:
        """添加指标并重新计算评分。"""
        self.metrics.append(metric)
        self._score = self._calculate_score()

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "score": self._score,
            "rank": self.rank,
            "metrics": [m.to_dict() for m in self.metrics],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitnessScore:
        metrics = [FitnessMetric.from_dict(m) for m in data.get("metrics", [])]
        score = cls(
            genome_id=data["genome_id"],
            metrics=metrics,
            rank=data.get("rank", 0),
        )
        return score

    def __repr__(self) -> str:
        return (
            f"FitnessScore(genome={self.genome_id!r}, "
            f"score={self._score}, rank={self.rank})"
        )


# ═══════════════════════════════════════════════════════════
# FitnessSnapshot — 评估快照
# ═══════════════════════════════════════════════════════════

@dataclass
class FitnessSnapshot:
    """Genome 评估的时间快照。

    用于追踪 Genome 在不同时间点的 fitness 变化。

    例如：
        Day 1: genome_001 score=0.60
        Day 30: genome_001 score=0.85

    通过快照链可以分析 Genome 的进化趋势。
    """
    snapshot_id: str = field(default_factory=lambda: f"snap_{uuid.uuid4().hex[:8]}")
    genome_id: str = ""
    fitness_score: FitnessScore | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def score(self) -> float:
        """快照中的评分值。"""
        return self.fitness_score.score if self.fitness_score else 0.0

    @property
    def rank(self) -> int:
        """快照中的排名。"""
        return self.fitness_score.rank if self.fitness_score else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "genome_id": self.genome_id,
            "fitness_score": self.fitness_score.to_dict() if self.fitness_score else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitnessSnapshot:
        fs_data = data.get("fitness_score")
        fitness_score = FitnessScore.from_dict(fs_data) if fs_data else None
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            genome_id=data["genome_id"],
            fitness_score=fitness_score,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"FitnessSnapshot(id={self.snapshot_id!r}, "
            f"genome={self.genome_id!r}, score={self.score})"
        )


# ═══════════════════════════════════════════════════════════
# EvaluationResult — 评估输出
# ═══════════════════════════════════════════════════════════

@dataclass
class EvaluationResult:
    """Fitness 评估的最终输出。

    用于 Selection 层决策：
      - passed=True → 保留/晋级
      - passed=False → 淘汰/重新变异

    例如：
        EvaluationResult(
            genome_id="genome_001",
            fitness=FitnessScore(...),
            passed=True,
            reason="ROAS 0.42 > threshold 0.30",
        )
    """
    genome_id: str
    fitness: FitnessScore | None = None
    passed: bool = False
    reason: str = ""

    @property
    def score(self) -> float:
        """评估中的评分值。"""
        return self.fitness.score if self.fitness else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "fitness": self.fitness.to_dict() if self.fitness else None,
            "passed": self.passed,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationResult:
        fitness_data = data.get("fitness")
        fitness = FitnessScore.from_dict(fitness_data) if fitness_data else None
        return cls(
            genome_id=data["genome_id"],
            fitness=fitness,
            passed=data.get("passed", False),
            reason=data.get("reason", ""),
        )

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"EvaluationResult(genome={self.genome_id!r}, "
            f"{status}, reason={self.reason!r})"
        )