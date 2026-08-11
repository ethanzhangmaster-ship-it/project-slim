"""E13.7.8 Policy Adjustment Models — 策略调整协议.

Day 7.8 Step 6:
  定义 Policy Adjustment 的 Contract 层，将 Feedback + Gate + Effectiveness
  转化为具体的策略参数调整建议。

核心模型:
  1. AdjustmentDirection  — 调整方向枚举
  2. PolicyAdjustment      — 单条策略调整 (target + delta + reason)
  3. PolicyAdjustmentSet   — 策略调整集合 (多条调整 + 统计)

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 每条调整包含 target/delta/reason/confidence 四要素
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块 (LearningFeedback, CycleGateResult, LearningEffectiveness)

用法:
  from growth_runtime.intelligence.learning.models.learning_policy_models import (
      AdjustmentDirection,
      PolicyAdjustment,
      PolicyAdjustmentSet,
  )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. AdjustmentDirection
# ═══════════════════════════════════════════════════════════════


class AdjustmentDirection(str, Enum):
    """调整方向 — 策略参数的变化方向.

    | 方向       | 含义        | 触发条件                  |
    |-----------|------------|--------------------------|
    | INCREASE  | 上调参数     | GOOD_LEARNING / SCALE_UP |
    | DECREASE  | 下调参数     | BAD_LEARNING / ROLLBACK  |
    | MAINTAIN  | 保持不变     | STAGNANT / INSUFFICIENT  |
    """

    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"


# ═══════════════════════════════════════════════════════════════
# 2. PolicyAdjustment
# ═══════════════════════════════════════════════════════════════


@dataclass
class PolicyAdjustment:
    """单条策略调整 — 具体的参数变更建议.

    Attributes:
        adjustment_id: 调整唯一标识
        cycle_number: 编排周期编号
        target_policy: 目标策略参数名 (e.g., "exploration_rate")
        current_value: 当前参数值
        recommended_value: 建议参数值
        adjustment_delta: 调整量 (recommended - current)
        direction: 调整方向
        reason: 调整原因
        confidence: 调整置信度 [0, 1]
        source: 触发来源 (feedback_classification / gate_decision)
        created_at: 创建时间
        metadata: 扩展元数据
    """

    adjustment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    target_policy: str = ""
    current_value: float = 0.0
    recommended_value: float = 0.0
    adjustment_delta: float = 0.0
    direction: str = AdjustmentDirection.MAINTAIN.value
    reason: str = ""
    confidence: float = 0.0
    source: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_significant(self) -> bool:
        """调整是否显著 (delta 绝对值 > 0.01)."""
        return abs(self.adjustment_delta) > 0.01

    @property
    def is_high_confidence(self) -> bool:
        """是否为高置信度调整."""
        return self.confidence >= 0.7

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def increase(
        cls,
        target_policy: str,
        current_value: float,
        delta: float,
        reason: str = "",
        confidence: float = 0.5,
        cycle_number: int = 0,
        source: str = "",
        **kwargs: Any,
    ) -> PolicyAdjustment:
        """创建上调建议."""
        recommended = round(current_value + delta, 4)
        return cls(
            cycle_number=cycle_number,
            target_policy=target_policy,
            current_value=current_value,
            recommended_value=recommended,
            adjustment_delta=round(delta, 4),
            direction=AdjustmentDirection.INCREASE.value,
            reason=reason,
            confidence=round(confidence, 4),
            source=source,
            **kwargs,
        )

    @classmethod
    def decrease(
        cls,
        target_policy: str,
        current_value: float,
        delta: float,
        reason: str = "",
        confidence: float = 0.5,
        cycle_number: int = 0,
        source: str = "",
        **kwargs: Any,
    ) -> PolicyAdjustment:
        """创建下调建议 (delta 应为正值，内部取负)."""
        abs_delta = abs(delta)
        recommended = round(max(0.0, current_value - abs_delta), 4)
        return cls(
            cycle_number=cycle_number,
            target_policy=target_policy,
            current_value=current_value,
            recommended_value=recommended,
            adjustment_delta=round(-abs_delta, 4),
            direction=AdjustmentDirection.DECREASE.value,
            reason=reason,
            confidence=round(confidence, 4),
            source=source,
            **kwargs,
        )

    @classmethod
    def maintain(
        cls,
        target_policy: str,
        current_value: float,
        reason: str = "",
        cycle_number: int = 0,
        source: str = "",
        **kwargs: Any,
    ) -> PolicyAdjustment:
        """创建保持建议."""
        return cls(
            cycle_number=cycle_number,
            target_policy=target_policy,
            current_value=current_value,
            recommended_value=current_value,
            adjustment_delta=0.0,
            direction=AdjustmentDirection.MAINTAIN.value,
            reason=reason,
            confidence=1.0,
            source=source,
            **kwargs,
        )

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjustment_id": self.adjustment_id,
            "cycle_number": self.cycle_number,
            "target_policy": self.target_policy,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "adjustment_delta": self.adjustment_delta,
            "direction": self.direction,
            "reason": self.reason,
            "confidence": self.confidence,
            "source": self.source,
            "is_significant": self.is_significant,
            "is_high_confidence": self.is_high_confidence,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 3. PolicyAdjustmentSet
# ═══════════════════════════════════════════════════════════════


@dataclass
class PolicyAdjustmentSet:
    """策略调整集合 — 一次评估产生的所有调整.

    Attributes:
        set_id: 集合唯一标识
        cycle_number: 编排周期编号
        adjustments: 调整列表
        source_feedback: 来源反馈分类
        source_gate: 来源门控决策
        total_adjustments: 调整总数
        significant_count: 显著调整数
        high_confidence_count: 高置信度调整数
        created_at: 创建时间
        metadata: 扩展元数据
    """

    set_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    adjustments: list[PolicyAdjustment] = field(default_factory=list)
    source_feedback: str = ""
    source_gate: str = ""
    total_adjustments: int = 0
    significant_count: int = 0
    high_confidence_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        return len(self.adjustments) == 0

    @property
    def has_significant_changes(self) -> bool:
        return self.significant_count > 0

    @property
    def summary(self) -> str:
        """生成调整摘要."""
        if self.is_empty:
            return "No policy adjustments"
        parts = [f"{adj.target_policy}: {adj.current_value} → {adj.recommended_value}"
                 for adj in self.adjustments if adj.is_significant]
        return "; ".join(parts) if parts else "Minor adjustments only"

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def from_adjustments(
        cls,
        adjustments: list[PolicyAdjustment],
        cycle_number: int = 0,
        source_feedback: str = "",
        source_gate: str = "",
        **kwargs: Any,
    ) -> PolicyAdjustmentSet:
        """从调整列表创建集合."""
        significant = sum(1 for a in adjustments if a.is_significant)
        high_conf = sum(1 for a in adjustments if a.is_high_confidence)
        return cls(
            cycle_number=cycle_number,
            adjustments=list(adjustments),
            source_feedback=source_feedback,
            source_gate=source_gate,
            total_adjustments=len(adjustments),
            significant_count=significant,
            high_confidence_count=high_conf,
            **kwargs,
        )

    @classmethod
    def empty(cls, cycle_number: int = 0) -> PolicyAdjustmentSet:
        """创建空集合."""
        return cls(cycle_number=cycle_number)

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_id": self.set_id,
            "cycle_number": self.cycle_number,
            "adjustments": [a.to_dict() for a in self.adjustments],
            "source_feedback": self.source_feedback,
            "source_gate": self.source_gate,
            "total_adjustments": self.total_adjustments,
            "significant_count": self.significant_count,
            "high_confidence_count": self.high_confidence_count,
            "is_empty": self.is_empty,
            "has_significant_changes": self.has_significant_changes,
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "AdjustmentDirection",
    "PolicyAdjustment",
    "PolicyAdjustmentSet",
]