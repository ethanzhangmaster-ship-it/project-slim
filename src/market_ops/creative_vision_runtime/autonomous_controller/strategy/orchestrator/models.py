"""E11.9 — Autonomous Evolution Orchestrator Models。

EvolutionCycleStatus:  进化周期状态
EvolutionOpportunity:  进化机会
EvolutionDecision:     进化决策
EvolutionCycle:        一次完整进化周期
EvolutionCycleResult:  周期执行结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvolutionCycleStatus(str, Enum):
    """进化周期状态。"""
    IDLE = "idle"              # 等待检测
    DETECTING = "detecting"    # 检测机会
    PLANNING = "planning"      # 生成策略
    EXECUTING = "executing"    # 执行突变
    EVALUATING = "evaluating"  # 评估结果
    LEARNING = "learning"      # 写入记忆/知识
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 取消


class OpportunityType(str, Enum):
    """进化机会类型。"""
    CREATIVE_FATIGUE = "creative_fatigue"      # 创意疲劳
    PERFORMANCE_DROP = "performance_drop"       # 性能下降
    MARKET_SHIFT = "market_shift"              # 市场变化
    NEW_WINNER_PATTERN = "new_winner_pattern"   # 发现新赢家模式
    UNDEREXPLOITED_DNA = "underexploited_dna"   # 未充分探索的 DNA
    KNOWLEDGE_GAP = "knowledge_gap"             # 知识空白
    DIVERSITY_COLLAPSE = "diversity_collapse"   # 多样性塌缩
    SCHEDULED = "scheduled"                     # 按计划执行


class EvolutionAction(str, Enum):
    """进化决策动作。"""
    START_EVOLUTION = "start_evolution"   # 启动进化
    OBSERVE = "observe"                   # 观察等待
    HOLD = "hold"                         # 暂停
    ABORT = "abort"                       # 中止


@dataclass
class EvolutionOpportunity:
    """进化机会。

    Attributes:
        opportunity_id: 机会 ID
        type:           机会类型
        score:          机会评分 (0-1)
        evidence:       证据列表
        metrics:        相关指标
        created_at:     创建时间
        metadata:       附加元数据
    """

    opportunity_id: str = ""
    type: OpportunityType = OpportunityType.PERFORMANCE_DROP
    score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.opportunity_id:
            self.opportunity_id = f"opp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_high_priority(self) -> bool:
        return self.score >= 0.8

    @property
    def is_medium_priority(self) -> bool:
        return 0.5 <= self.score < 0.8

    @property
    def is_low_priority(self) -> bool:
        return self.score < 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "type": self.type.value,
            "score": self.score,
            "evidence": self.evidence,
            "metrics": self.metrics,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionOpportunity({self.type.value}, "
            f"score={self.score:.2f})"
        )


@dataclass
class EvolutionDecision:
    """进化决策。

    Attributes:
        decision_id: 决策 ID
        action:      决策动作
        reason:      决策理由
        confidence:  置信度 (0-1)
        opportunity: 关联机会
        created_at:  创建时间
        metadata:    附加元数据
    """

    decision_id: str = ""
    action: EvolutionAction = EvolutionAction.HOLD
    reason: str = ""
    confidence: float = 0.0
    opportunity: EvolutionOpportunity | None = None
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def should_evolve(self) -> bool:
        return self.action == EvolutionAction.START_EVOLUTION

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action": self.action.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "opportunity": self.opportunity.to_dict() if self.opportunity else None,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionDecision({self.action.value}, "
            f"confidence={self.confidence:.2f})"
        )


@dataclass
class EvolutionCycle:
    """一次完整进化周期。

    Attributes:
        cycle_id:          周期 ID
        status:            周期状态
        trigger_reason:    触发原因
        opportunity_score: 机会评分
        strategy_id:       策略 ID
        execution_id:      执行结果 ID
        evaluation_id:     评估 ID
        decision:          决策记录
        created_at:        创建时间
        completed_at:      完成时间
        metadata:          附加元数据
    """

    cycle_id: str = ""
    status: EvolutionCycleStatus = EvolutionCycleStatus.IDLE
    trigger_reason: str = ""
    opportunity_score: float = 0.0
    strategy_id: str | None = None
    execution_id: str | None = None
    evaluation_id: str | None = None
    decision: EvolutionDecision | None = None
    created_at: str = ""
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cycle_id:
            self.cycle_id = f"cycle_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_active(self) -> bool:
        return self.status in (
            EvolutionCycleStatus.DETECTING,
            EvolutionCycleStatus.PLANNING,
            EvolutionCycleStatus.EXECUTING,
            EvolutionCycleStatus.EVALUATING,
            EvolutionCycleStatus.LEARNING,
        )

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            EvolutionCycleStatus.COMPLETED,
            EvolutionCycleStatus.FAILED,
            EvolutionCycleStatus.CANCELLED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "status": self.status.value,
            "trigger_reason": self.trigger_reason,
            "opportunity_score": self.opportunity_score,
            "strategy_id": self.strategy_id,
            "execution_id": self.execution_id,
            "evaluation_id": self.evaluation_id,
            "decision": self.decision.to_dict() if self.decision else None,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionCycle({self.cycle_id}, "
            f"status={self.status.value}, "
            f"score={self.opportunity_score:.2f})"
        )


@dataclass
class EvolutionCycleResult:
    """周期执行结果。

    Attributes:
        cycle:          进化周期
        success:        是否成功
        strategies:     生成的策略列表
        execution:      执行结果
        evaluation:     评估结果
        summary:        摘要
        created_at:     创建时间
    """

    cycle: EvolutionCycle | None = None
    success: bool = False
    strategies: list[Any] = field(default_factory=list)
    execution: Any = None
    evaluation: Any = None
    summary: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle.to_dict() if self.cycle else None,
            "success": self.success,
            "strategies_count": len(self.strategies),
            "summary": self.summary,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionCycleResult(success={self.success}, "
            f"strategies={len(self.strategies)})"
        )