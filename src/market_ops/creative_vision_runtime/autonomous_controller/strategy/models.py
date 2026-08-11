"""E11.8.1 — Strategy Planner Models。

StrategyType:         策略类型
MutationFocus:        进化目标（突变聚焦维度）
EvolutionObjective:   长期进化目标
EvolutionStrategy:    最终进化策略输出
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrategyType(str, Enum):
    """策略类型。"""
    EXPLOIT_WINNER = "exploit_winner"    # 利用赢家（小幅变体）
    EXPLORE_NEW = "explore_new"          # 探索新方向
    FIX_FAILURE = "fix_failure"          # 修复失败
    DIVERSIFY = "diversify"              # 多样化（种群塌缩时）
    SCALE_SUCCESS = "scale_success"      # 扩大成功（高ROI赢家）


class MutationFocus(str, Enum):
    """突变聚焦维度。"""
    HOOK = "hook"            # 钩子（开场）
    VISUAL = "visual"        # 视觉
    GAMEPLAY = "gameplay"    # 玩法展示
    REWARD = "reward"        # 奖励/激励
    PACING = "pacing"        # 节奏
    FULL = "full"            # 全维度


class Horizon(str, Enum):
    """目标时间范围。"""
    SHORT = "SHORT"      # 短期（1-3天）
    MEDIUM = "MEDIUM"    # 中期（1-2周）
    LONG = "LONG"        # 长期（1个月+）


class Intensity(str, Enum):
    """策略强度。"""
    SMALL = "small"      # 轻度（小幅调整）
    MEDIUM = "medium"    # 中度
    LARGE = "large"      # 重度
    RADICAL = "radical"  # 激进


@dataclass
class EvolutionObjective:
    """长期进化目标。

    描述系统应该朝哪个方向优化。

    Attributes:
        objective_id:  目标 ID
        metric:        目标指标（CTR / ROI / Retention / Diversity）
        current_value: 当前值
        target_value:  目标值
        priority:      优先级 (0-1)
        horizon:       时间范围
        reason:        原因说明
        metadata:      附加元数据
    """

    objective_id: str = ""
    metric: str = ""
    current_value: float = 0.0
    target_value: float = 0.0
    priority: float = 0.0
    horizon: Horizon = Horizon.MEDIUM
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.objective_id:
            self.objective_id = f"obj_{uuid.uuid4().hex[:12]}"

    @property
    def gap(self) -> float:
        """当前值与目标值之间的差距。"""
        return max(0.0, self.target_value - self.current_value)

    @property
    def gap_pct(self) -> float:
        """差距百分比。"""
        if self.target_value == 0:
            return 0.0
        return self.gap / self.target_value

    @property
    def is_urgent(self) -> bool:
        """是否紧急（高优先级 + 短期）。"""
        return self.priority >= 0.7 and self.horizon == Horizon.SHORT

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "metric": self.metric,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "gap": self.gap,
            "gap_pct": self.gap_pct,
            "priority": self.priority,
            "horizon": self.horizon.value,
            "reason": self.reason,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionObjective({self.metric}, "
            f"{self.current_value:.3f}→{self.target_value:.3f}, "
            f"priority={self.priority:.2f})"
        )


@dataclass
class EvolutionStrategy:
    """最终进化策略输出。

    Attributes:
        strategy_id:     策略 ID
        strategy_type:   策略类型
        objective:       进化目标
        target_genomes:  目标基因组 ID 列表
        mutation_focus:  突变聚焦维度
        intensity:       策略强度
        confidence:      置信度 (0-1)
        reason:          决策理由
        metadata:        附加元数据
        created_at:      创建时间
    """

    strategy_id: str = ""
    strategy_type: StrategyType = StrategyType.EXPLORE_NEW
    objective: EvolutionObjective | None = None
    target_genomes: list[str] = field(default_factory=list)
    mutation_focus: MutationFocus = MutationFocus.FULL
    intensity: Intensity = Intensity.MEDIUM
    confidence: float = 0.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.strategy_id:
            self.strategy_id = f"strat_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_high_confidence(self) -> bool:
        """是否高置信度策略。"""
        return self.confidence >= 0.7

    @property
    def is_exploit(self) -> bool:
        """是否利用型策略。"""
        return self.strategy_type in (StrategyType.EXPLOIT_WINNER, StrategyType.SCALE_SUCCESS)

    @property
    def is_explore(self) -> bool:
        """是否探索型策略。"""
        return self.strategy_type in (StrategyType.EXPLORE_NEW, StrategyType.DIVERSIFY)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type.value,
            "objective": self.objective.to_dict() if self.objective else None,
            "target_genomes": self.target_genomes,
            "mutation_focus": self.mutation_focus.value,
            "intensity": self.intensity.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionStrategy({self.strategy_type.value}, "
            f"focus={self.mutation_focus.value}, "
            f"intensity={self.intensity.value}, "
            f"confidence={self.confidence:.2f})"
        )