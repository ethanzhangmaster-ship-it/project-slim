"""E11.5.2 — Trigger Models。

OpportunitySignal:  市场机会信号
TriggerDecision:    触发决策（Gate before Controller）
TriggerAction:      触发动作类型枚举
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TriggerAction(str, Enum):
    """触发动作类型。"""
    START_EVOLUTION = "start_evolution"  # 启动进化循环
    QUEUE = "queue"                      # 排队等待
    MERGE = "merge"                      # 合并到已有机会
    IGNORE = "ignore"                    # 忽略
    DEFER = "defer"                      # 推迟（等待更多数据）


@dataclass
class OpportunitySignal:
    """市场机会信号。

    描述一个被检测到的创意进化机会。

    Attributes:
        signal_id:          信号 ID
        source:             信号来源 (market/competitor/performance/category)
        category:           品类 (merge_puzzle/simulation/...)
        patterns:           涉及的模式列表
        confidence:         置信度 (0-1)
        priority:           优先级 (high/medium/low)
        recommended_action: 推荐动作
        reason:             检测理由
        metadata:           附加元数据
        created_at:         创建时间
    """

    signal_id: str = ""
    source: str = "market"
    category: str = ""
    patterns: list[str] = field(default_factory=list)
    confidence: float = 0.0
    priority: str = "medium"
    recommended_action: str = "start_evolution"
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.signal_id:
            self.signal_id = f"os_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()
        if self.priority not in ("high", "medium", "low"):
            raise ValueError(f"Invalid priority: {self.priority}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Invalid confidence: {self.confidence}")

    @property
    def pattern_count(self) -> int:
        return len(self.patterns)

    @property
    def is_high_priority(self) -> bool:
        return self.priority == "high"

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "source": self.source,
            "category": self.category,
            "patterns": self.patterns,
            "confidence": self.confidence,
            "priority": self.priority,
            "recommended_action": self.recommended_action,
            "reason": self.reason,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpportunitySignal:
        return cls(
            signal_id=data.get("signal_id", ""),
            source=data.get("source", "market"),
            category=data.get("category", ""),
            patterns=data.get("patterns", []),
            confidence=float(data.get("confidence", 0.0)),
            priority=data.get("priority", "medium"),
            recommended_action=data.get("recommended_action", "start_evolution"),
            reason=data.get("reason", ""),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"OpportunitySignal({self.source}/{self.category}, "
            f"conf={self.confidence:.2f}, "
            f"pri={self.priority}, "
            f"patterns={self.pattern_count})"
        )


@dataclass
class TriggerDecision:
    """触发决策。

    OpportunitySignal 经过 TriggerEngine 评估后的决策结果。

    Attributes:
        decision_id:    决策 ID
        signal_id:      来源信号 ID
        should_trigger: 是否触发进化
        action:         执行动作
        reason:         决策理由
        confidence:     决策置信度
        created_at:     创建时间
    """

    decision_id: str = ""
    signal_id: str = ""
    should_trigger: bool = False
    action: TriggerAction = TriggerAction.IGNORE
    reason: str = ""
    confidence: float = 0.0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = f"td_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_positive(self) -> bool:
        return self.should_trigger and self.action == TriggerAction.START_EVOLUTION

    @property
    def is_deferred(self) -> bool:
        return self.action == TriggerAction.DEFER

    @property
    def is_ignored(self) -> bool:
        return self.action == TriggerAction.IGNORE

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "signal_id": self.signal_id,
            "should_trigger": self.should_trigger,
            "action": self.action.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TriggerDecision:
        action_raw = data.get("action", "ignore")
        if isinstance(action_raw, str):
            action = TriggerAction(action_raw)
        else:
            action = action_raw
        return cls(
            decision_id=data.get("decision_id", ""),
            signal_id=data.get("signal_id", ""),
            should_trigger=bool(data.get("should_trigger", False)),
            action=action,
            reason=data.get("reason", ""),
            confidence=float(data.get("confidence", 0.0)),
        )

    def __repr__(self) -> str:
        return (
            f"TriggerDecision({self.action.value}, "
            f"trigger={self.should_trigger}, "
            f"conf={self.confidence:.2f})"
        )