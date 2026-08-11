"""E15.2.3 Action Selection Models — 动作选择数据模型.

定义:
  - ActionCandidate: 候选动作 (来自 Planner)
  - SelectionStatus: 选择状态
  - SelectedAction:  最终选中的动作
  - SelectionResult: 选择结果 (含所有候选评分)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class SelectionStatus(str, Enum):
    """E15.2.3 选择状态."""
    SELECTED = "selected"
    REJECTED = "rejected"
    BLOCKED = "blocked"       # 被安全规则阻止
    PENDING = "pending"


# ═══════════════════════════════════════════════════════════════
# Action Candidate
# ═══════════════════════════════════════════════════════════════


@dataclass
class ActionCandidate:
    """E15.2.3 候选动作 — 来自 Planner 的候选执行动作.

    Attributes:
        action_id:       动作唯一标识
        action_type:     动作类型
        target:          目标描述 (campaign_id, creative_id 等)
        expected_reward: 预期收益 (0.0-1.0)
        confidence:      置信度 (0.0-1.0)
        execution_cost:  执行成本 (0.0-1.0)
        risk_score:      风险评估分 (0.0-1.0, 来自 RiskEngine)
        risk_level:      风险等级 (来自 RiskEngine)
        memory_boost:    记忆增强因子 (0.0-1.0)
        metadata:        扩展元数据
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""
    target: dict[str, Any] = field(default_factory=dict)
    expected_reward: float = 0.0
    confidence: float = 0.0
    execution_cost: float = 0.0
    risk_score: float = 0.0
    risk_level: str = ""
    memory_boost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "expected_reward": self.expected_reward,
            "confidence": self.confidence,
            "execution_cost": self.execution_cost,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "memory_boost": self.memory_boost,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Scored Candidate
# ═══════════════════════════════════════════════════════════════


@dataclass
class ScoredCandidate:
    """E15.2.3 评分后的候选 — 包含各维度分解得分.

    Attributes:
        candidate:        原始候选
        total_score:      综合得分
        reward_component: 收益维度得分
        confidence_component: 置信度维度得分
        memory_component: 记忆维度得分
        risk_penalty:     风险惩罚
        cost_penalty:     执行成本惩罚
        status:           选择状态
        block_reason:     阻止原因 (仅 BLOCKED)
    """
    candidate: ActionCandidate
    total_score: float = 0.0
    reward_component: float = 0.0
    confidence_component: float = 0.0
    memory_component: float = 0.0
    risk_penalty: float = 0.0
    cost_penalty: float = 0.0
    status: SelectionStatus = SelectionStatus.PENDING
    block_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "total_score": self.total_score,
            "reward_component": self.reward_component,
            "confidence_component": self.confidence_component,
            "memory_component": self.memory_component,
            "risk_penalty": self.risk_penalty,
            "cost_penalty": self.cost_penalty,
            "status": self.status.value,
            "block_reason": self.block_reason,
        }


# ═══════════════════════════════════════════════════════════════
# Selected Action
# ═══════════════════════════════════════════════════════════════


@dataclass
class SelectedAction:
    """E15.2.3 最终选中动作.

    Attributes:
        action_id:     选中的动作 ID
        action_type:   动作类型
        score:         综合得分
        confidence:    置信度
        reasoning:     选择理由
        alternatives:  备选方案
        trace:         决策追踪信息
    """
    action_id: str = ""
    action_type: str = ""
    score: float = 0.0
    confidence: float = 0.0
    reasoning: str = ""
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "score": self.score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "alternatives": self.alternatives,
            "trace": self.trace,
        }


# ═══════════════════════════════════════════════════════════════
# Selection Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class SelectionResult:
    """E15.2.3 选择结果 — 包含所有候选的评分和最终选择.

    Attributes:
        result_id:    结果 ID
        selected:     最终选中
        candidates:   所有评分后的候选 (含 rejected)
        created_at:   创建时间
        metadata:     扩展元数据
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    selected: SelectedAction | None = None
    candidates: list[ScoredCandidate] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_selected(self) -> ScoredCandidate | None:
        """获取选中的评分候选."""
        if self.selected is None:
            return None
        for c in self.candidates:
            if c.candidate.action_id == self.selected.action_id:
                return c
        return None

    def get_rejected(self) -> list[ScoredCandidate]:
        """获取所有被拒绝的候选."""
        return [c for c in self.candidates if c.status == SelectionStatus.REJECTED]

    def get_blocked(self) -> list[ScoredCandidate]:
        """获取所有被阻止的候选."""
        return [c for c in self.candidates if c.status == SelectionStatus.BLOCKED]

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "selected": self.selected.to_dict() if self.selected else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


__all__ = [
    "SelectionStatus",
    "ActionCandidate",
    "ScoredCandidate",
    "SelectedAction",
    "SelectionResult",
]