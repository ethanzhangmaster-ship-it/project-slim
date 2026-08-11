"""E15.2.4 Execution Reasoning Models — 推理上下文与数据模型.

定义:
  - Observation:      观测数据点
  - Constraint:       执行约束
  - ExecutionAttempt: 历史执行尝试
  - ReasoningContext: 推理上下文
  - Hypothesis:       生成假设
  - DiagnosisResult:  诊断结果
  - ReasoningStep:    推理步骤
  - ReasoningTrace:   推理追踪
  - ReasoningResult:  推理结论
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


class DiagnosisStatus(str, Enum):
    """诊断状态."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    INCONCLUSIVE = "inconclusive"


class ReasoningDecision(str, Enum):
    """推理决策."""
    CONTINUE = "continue"        # 继续执行
    STOP = "stop"                # 停止
    MODIFY = "modify"            # 修改参数
    MONITOR = "monitor"          # 观望
    ESCALATE = "escalate"        # 升级人工


class ObservationTrend(str, Enum):
    """观测趋势."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class ConstraintType(str, Enum):
    """约束类型."""
    HARD = "hard"    # 硬约束 (不可违反)
    SOFT = "soft"    # 软约束 (建议)


# ═══════════════════════════════════════════════════════════════
# Observation
# ═══════════════════════════════════════════════════════════════


@dataclass
class Observation:
    """观测数据点.

    Attributes:
        metric:    指标名称 (roas, ctr, cvr, fatigue, frequency, etc.)
        value:     当前值
        previous:  前值 (用于计算趋势)
        trend:     趋势方向
        threshold: 阈值 (可选)
        timestamp: 时间戳
    """
    metric: str = ""
    value: float = 0.0
    previous: float = 0.0
    trend: ObservationTrend = ObservationTrend.STABLE
    threshold: float | None = None
    timestamp: str = ""

    def delta_pct(self) -> float:
        """变化百分比."""
        if self.previous == 0:
            return 0.0
        return round((self.value - self.previous) / abs(self.previous) * 100, 2)

    def exceeds_threshold(self) -> bool:
        """是否超过阈值."""
        if self.threshold is None:
            return False
        return self.value > self.threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "value": self.value,
            "previous": self.previous,
            "trend": self.trend.value,
            "threshold": self.threshold,
            "delta_pct": self.delta_pct(),
        }


# ═══════════════════════════════════════════════════════════════
# Constraint
# ═══════════════════════════════════════════════════════════════


@dataclass
class Constraint:
    """执行约束.

    Attributes:
        name:  约束名称
        value: 约束值
        type:  约束类型
    """
    name: str = ""
    value: Any = None
    type: ConstraintType = ConstraintType.HARD

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type.value,
        }


# ═══════════════════════════════════════════════════════════════
# Execution Attempt
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionAttempt:
    """历史执行尝试.

    Attributes:
        attempt_id: 尝试 ID
        action:     执行的动作
        result:     执行结果
        outcome:    结果 (success/failure/partial)
        timestamp:  时间戳
    """
    attempt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "action": self.action,
            "result": self.result,
            "outcome": self.outcome,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════
# Reasoning Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReasoningContext:
    """推理上下文 — 整合所有推理所需信息.

    Attributes:
        execution_id:      执行 ID
        action:            当前动作 (ActionCandidate)
        observations:      观测数据
        constraints:       约束条件
        previous_attempts: 历史尝试
        risk_assessment:   风险评估 (来自 E15.2.2)
        selected_action:   选中动作 (来自 E15.2.3)
        metadata:          扩展元数据
    """
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: dict[str, Any] = field(default_factory=dict)
    observations: list[Observation] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    previous_attempts: list[ExecutionAttempt] = field(default_factory=list)
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    selected_action: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_observation(self, metric: str) -> Observation | None:
        """按指标名获取观测."""
        for obs in self.observations:
            if obs.metric == metric:
                return obs
        return None

    def get_constraint(self, name: str) -> Constraint | None:
        """按名称获取约束."""
        for c in self.constraints:
            if c.name == name:
                return c
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "action": self.action,
            "observations": [o.to_dict() for o in self.observations],
            "constraints": [c.to_dict() for c in self.constraints],
            "previous_attempts": [a.to_dict() for a in self.previous_attempts],
            "risk_assessment": self.risk_assessment,
            "selected_action": self.selected_action,
        }


# ═══════════════════════════════════════════════════════════════
# Hypothesis
# ═══════════════════════════════════════════════════════════════


@dataclass
class Hypothesis:
    """推理假设.

    Attributes:
        name:             假设名称
        description:      假设描述
        evidence:         支撑证据
        confidence:       置信度
        impact:           影响程度
        suggested_action: 建议动作
    """
    name: str = ""
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    impact: str = "medium"
    suggested_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "impact": self.impact,
            "suggested_action": self.suggested_action,
        }


# ═══════════════════════════════════════════════════════════════
# Diagnosis Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class DiagnosisResult:
    """诊断结果 — 执行结果分析.

    Attributes:
        status:              诊断状态
        summary:             诊断摘要
        root_causes:         根因列表
        lessons:             经验教训
        metrics_delta:       指标变化
        hypotheses_confirmed: 被确认的假设
        hypotheses_rejected:  被拒绝的假设
    """
    status: DiagnosisStatus = DiagnosisStatus.INCONCLUSIVE
    summary: str = ""
    root_causes: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    metrics_delta: dict[str, float] = field(default_factory=dict)
    hypotheses_confirmed: list[str] = field(default_factory=list)
    hypotheses_rejected: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "summary": self.summary,
            "root_causes": self.root_causes,
            "lessons": self.lessons,
            "metrics_delta": self.metrics_delta,
            "hypotheses_confirmed": self.hypotheses_confirmed,
            "hypotheses_rejected": self.hypotheses_rejected,
        }


# ═══════════════════════════════════════════════════════════════
# Reasoning Step
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReasoningStep:
    """推理步骤.

    Attributes:
        step_id:     步骤 ID
        step_type:   步骤类型 (observation/hypothesis/evaluation/decision)
        description: 步骤描述
        confidence:  此步骤置信度
        timestamp:   时间戳
        metadata:    扩展数据
    """
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_type: str = ""
    description: str = ""
    confidence: float = 0.0
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "description": self.description,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Reasoning Trace
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReasoningTrace:
    """推理追踪 — 记录完整推理链路.

    Attributes:
        trace_id:       追踪 ID
        steps:          推理步骤列表
        final_decision: 最终决策
        confidence:     总体置信度
        hypotheses:     生成的假设
        created_at:     创建时间
    """
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    steps: list[ReasoningStep] = field(default_factory=list)
    final_decision: str = ""
    confidence: float = 0.0
    hypotheses: list[Hypothesis] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "steps": [s.to_dict() for s in self.steps],
            "final_decision": self.final_decision,
            "confidence": self.confidence,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Reasoning Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReasoningResult:
    """推理结果 — 最终推理输出.

    Attributes:
        result_id:    结果 ID
        decision:     推理决策
        confidence:   总体置信度
        reasoning:    推理步骤描述
        next_action:  建议下一步动作
        hypotheses:   生成的假设
        diagnosis:    诊断结果
        trace:        推理追踪
        explanation:  人类可读解释
        created_at:   创建时间
        metadata:     扩展元数据
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision: ReasoningDecision = ReasoningDecision.MONITOR
    confidence: float = 0.0
    reasoning: list[str] = field(default_factory=list)
    next_action: str | None = None
    hypotheses: list[Hypothesis] = field(default_factory=list)
    diagnosis: DiagnosisResult | None = None
    trace: ReasoningTrace | None = None
    explanation: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "next_action": self.next_action,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "diagnosis": self.diagnosis.to_dict() if self.diagnosis else None,
            "trace": self.trace.to_dict() if self.trace else None,
            "explanation": self.explanation,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


__all__ = [
    # Enums
    "DiagnosisStatus",
    "ReasoningDecision",
    "ObservationTrend",
    "ConstraintType",
    # Models
    "Observation",
    "Constraint",
    "ExecutionAttempt",
    "ReasoningContext",
    "Hypothesis",
    "DiagnosisResult",
    "ReasoningStep",
    "ReasoningTrace",
    "ReasoningResult",
]