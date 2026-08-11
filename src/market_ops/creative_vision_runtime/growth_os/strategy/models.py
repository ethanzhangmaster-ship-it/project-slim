"""E12.7.3 — Growth Strategy Planner Models。

战略规划层核心数据模型。

核心模型:
  StrategyObjective:  增长目标
  StrategyAction:     策略动作
  StrategyTemplate:   策略模板类型
  GrowthStrategy:     完整增长策略
  ConstraintCheck:    约束检查结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ──────────────────────────────────────────────────


class StrategyTemplateType(str, Enum):
    """策略模板类型。"""

    SCALE = "scale"
    RECOVERY = "recovery"
    EXPLORATION = "exploration"
    MAINTAIN = "maintain"
    SUNSET = "sunset"
    CUSTOM = "custom"


class StrategyStatus(str, Enum):
    """策略状态。"""

    DRAFT = "draft"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    """风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class ActionType(str, Enum):
    """策略动作类型。"""

    # 创意
    CREATE_CREATIVE = "create_creative"
    MUTATE_DNA = "mutate_dna"
    REFRESH_CREATIVE = "refresh_creative"

    # 预算
    INCREASE_BUDGET = "increase_budget"
    DECREASE_BUDGET = "decrease_budget"
    REALLOCATE_BUDGET = "reallocate_budget"

    # 实验
    LAUNCH_EXPERIMENT = "launch_experiment"
    EVALUATE_EXPERIMENT = "evaluate_experiment"
    STOP_EXPERIMENT = "stop_experiment"

    # 受众
    EXPAND_AUDIENCE = "expand_audience"
    REFINE_TARGETING = "refine_targeting"

    # 产品
    SCALE_PRODUCT = "scale_product"
    SUNSET_PRODUCT = "sunset_product"

    # 自定义
    CUSTOM = "custom"


# ── StrategyObjective ──────────────────────────────────────


@dataclass
class StrategyObjective:
    """增长目标。

    Attributes:
        objective_id:  目标 ID
        product_id:    产品 ID
        metric:        目标指标
        current_value: 当前值
        target_value:  目标值
        priority:      优先级 [0, 1]
        urgency:       紧急度 [0, 1]
        impact:        预计影响 [0, 1]
        description:   目标描述
        metadata:      附加元数据
    """

    objective_id: str = ""
    product_id: str = ""
    metric: str = ""
    current_value: float = 0.0
    target_value: float = 0.0
    priority: float = 0.0
    urgency: float = 0.0
    impact: float = 0.0
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.objective_id:
            self.objective_id = _gen_id("OBJ")

    @property
    def gap(self) -> float:
        return max(0.0, self.target_value - self.current_value)

    @property
    def gap_pct(self) -> float:
        if self.current_value <= 0:
            return 1.0
        return self.gap / self.current_value

    @property
    def is_improvement(self) -> bool:
        return self.target_value > self.current_value

    @property
    def composite_score(self) -> float:
        return self.priority * 0.4 + self.urgency * 0.35 + self.impact * 0.25

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "product_id": self.product_id,
            "metric": self.metric,
            "current_value": round(self.current_value, 4),
            "target_value": round(self.target_value, 4),
            "gap": round(self.gap, 4),
            "gap_pct": round(self.gap_pct, 4),
            "priority": round(self.priority, 4),
            "urgency": round(self.urgency, 4),
            "impact": round(self.impact, 4),
            "composite_score": round(self.composite_score, 4),
            "description": self.description,
        }

    def __repr__(self) -> str:
        return (
            f"StrategyObjective(metric={self.metric}, "
            f"{self.current_value:.2f}→{self.target_value:.2f}, "
            f"priority={self.priority:.2f})"
        )


# ── StrategyAction ─────────────────────────────────────────


@dataclass
class StrategyAction:
    """策略动作。

    Attributes:
        action_id:       动作 ID
        action_type:     动作类型
        target_module:   目标模块
        parameters:      动作参数
        priority:        优先级 [0, 100]
        expected_result: 预期结果描述
        expected_impact: 预期影响 [0, 1]
        dependencies:    依赖动作 ID 列表
        duration_days:   预计耗时（天）
        status:          动作状态
        metadata:        附加元数据
    """

    action_id: str = ""
    action_type: ActionType = ActionType.CUSTOM
    target_module: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: int = 50
    expected_result: str = ""
    expected_impact: float = 0.0
    dependencies: list[str] = field(default_factory=list)
    duration_days: int = 1
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action_id:
            self.action_id = _gen_id("SA")

    @property
    def is_high_priority(self) -> bool:
        return self.priority >= 80

    @property
    def has_dependencies(self) -> bool:
        return len(self.dependencies) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "target_module": self.target_module,
            "parameters": self.parameters,
            "priority": self.priority,
            "expected_result": self.expected_result,
            "expected_impact": round(self.expected_impact, 4),
            "dependencies": self.dependencies,
            "duration_days": self.duration_days,
            "is_high_priority": self.is_high_priority,
        }

    def __repr__(self) -> str:
        return (
            f"StrategyAction(type={self.action_type.value}, "
            f"priority={self.priority})"
        )


# ── GrowthStrategy ─────────────────────────────────────────


@dataclass
class GrowthStrategy:
    """增长策略。

    完整的增长策略计划。

    Attributes:
        strategy_id:      策略 ID
        product_id:       产品 ID
        objective:        增长目标
        template_type:    策略模板类型
        hypothesis_id:    关联假设 ID
        actions:          策略动作列表
        expected_impact:  预期整体影响 [0, 1]
        confidence:       置信度 [0, 1]
        risk_level:       风险等级
        risk_score:       风险评分 [0, 1]
        duration_days:    预计周期（天）
        status:           策略状态
        description:      策略描述
        created_at:       创建时间
        metadata:         附加元数据
    """

    strategy_id: str = ""
    product_id: str = ""
    objective: StrategyObjective | None = None
    template_type: StrategyTemplateType = StrategyTemplateType.CUSTOM
    hypothesis_id: str = ""
    actions: list[StrategyAction] = field(default_factory=list)
    expected_impact: float = 0.0
    confidence: float = 0.0
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = 0.5
    duration_days: int = 7
    status: StrategyStatus = StrategyStatus.DRAFT
    description: str = ""
    created_at: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_id:
            self.strategy_id = _gen_id("STR")

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def total_duration_days(self) -> int:
        if not self.actions:
            return self.duration_days
        return sum(a.duration_days for a in self.actions)

    @property
    def risk_adjusted_impact(self) -> float:
        return self.expected_impact * self.confidence * (1.0 - self.risk_score * 0.5)

    @property
    def is_actionable(self) -> bool:
        return (
            self.status == StrategyStatus.VALIDATED
            and self.confidence >= 0.50
            and self.action_count > 0
        )

    @property
    def is_high_risk(self) -> bool:
        return self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @property
    def high_priority_action_count(self) -> int:
        return sum(1 for a in self.actions if a.is_high_priority)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "product_id": self.product_id,
            "template_type": self.template_type.value,
            "hypothesis_id": self.hypothesis_id,
            "expected_impact": round(self.expected_impact, 4),
            "confidence": round(self.confidence, 4),
            "risk_level": self.risk_level.value,
            "risk_score": round(self.risk_score, 4),
            "risk_adjusted_impact": round(self.risk_adjusted_impact, 4),
            "duration_days": self.duration_days,
            "total_duration_days": self.total_duration_days,
            "status": self.status.value,
            "action_count": self.action_count,
            "high_priority_action_count": self.high_priority_action_count,
            "is_actionable": self.is_actionable,
            "is_high_risk": self.is_high_risk,
            "description": self.description,
            "actions": [a.to_dict() for a in self.actions],
            "objective": self.objective.to_dict() if self.objective else None,
        }

    def __repr__(self) -> str:
        return (
            f"GrowthStrategy(product={self.product_id}, "
            f"template={self.template_type.value}, "
            f"actions={self.action_count}, "
            f"impact={self.expected_impact:.2f})"
        )


# ── ConstraintCheck ────────────────────────────────────────


@dataclass
class ConstraintCheck:
    """约束检查结果。

    Attributes:
        check_id:       检查 ID
        constraint_name: 约束名称
        passed:         是否通过
        current_value:  当前值
        max_value:      最大值
        message:        检查消息
        severity:       严重程度
    """

    check_id: str = ""
    constraint_name: str = ""
    passed: bool = True
    current_value: float = 0.0
    max_value: float = 0.0
    message: str = ""
    severity: RiskLevel = RiskLevel.LOW

    def __post_init__(self) -> None:
        if not self.check_id:
            self.check_id = _gen_id("CHK")

    @property
    def is_over_limit(self) -> bool:
        return self.current_value > self.max_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "constraint_name": self.constraint_name,
            "passed": self.passed,
            "current_value": round(self.current_value, 4),
            "max_value": round(self.max_value, 4),
            "message": self.message,
            "severity": self.severity.value,
        }

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"ConstraintCheck({self.constraint_name}: {status})"


# ── StrategyPlan ───────────────────────────────────────────


@dataclass
class StrategyPlan:
    """策略规划结果。

    Planner 的输出。

    Attributes:
        plan_id:        规划 ID
        product_id:     产品 ID
        strategies:     策略列表（已排名）
        top_strategy:   最优策略
        constraints:    约束检查结果
        summary:        规划摘要
        created_at:     创建时间
        metadata:       附加元数据
    """

    plan_id: str = ""
    product_id: str = ""
    strategies: list[GrowthStrategy] = field(default_factory=list)
    top_strategy: GrowthStrategy | None = None
    constraints: list[ConstraintCheck] = field(default_factory=list)
    summary: str = ""
    created_at: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = _gen_id("PLN")

    @property
    def strategy_count(self) -> int:
        return len(self.strategies)

    @property
    def all_constraints_passed(self) -> bool:
        return all(c.passed for c in self.constraints)

    @property
    def actionable_strategies(self) -> list[GrowthStrategy]:
        return [s for s in self.strategies if s.is_actionable]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "product_id": self.product_id,
            "strategy_count": self.strategy_count,
            "top_strategy": self.top_strategy.to_dict() if self.top_strategy else None,
            "all_constraints_passed": self.all_constraints_passed,
            "constraints": [c.to_dict() for c in self.constraints],
            "summary": self.summary,
            "actionable_strategies": len(self.actionable_strategies),
        }

    def __repr__(self) -> str:
        return (
            f"StrategyPlan(product={self.product_id}, "
            f"strategies={self.strategy_count}, "
            f"top={self.top_strategy.template_type.value if self.top_strategy else 'none'})"
        )