"""E12.7.7 Dashboard Models — GrowthDashboardState, ProductDashboard, DecisionView, etc."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── Enums ────────────────────────────────────────────────────


class SystemStatus(str, Enum):
    """系统状态."""
    IDLE = "idle"
    RUNNING = "running"
    OPTIMIZING = "optimizing"
    DEGRADED = "degraded"
    ERROR = "error"
    PAUSED = "paused"


class RiskLevel(str, Enum):
    """风险等级."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrendDirection(str, Enum):
    """趋势方向."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class LifecycleStage(str, Enum):
    """产品生命周期."""
    INCUBATION = "incubation"
    GROWTH = "growth"
    MATURITY = "maturity"
    DECLINE = "decline"
    REVIVAL = "revival"


class DashboardEventType(str, Enum):
    """仪表盘事件类型."""
    CYCLE_STARTED = "cycle_started"
    DECISION_CREATED = "decision_created"
    TASK_COMPLETED = "task_completed"
    EXPERIMENT_FINISHED = "experiment_finished"
    PATTERN_LEARNED = "pattern_learned"
    RISK_ALERT = "risk_alert"
    SYSTEM_STATUS_CHANGED = "system_status_changed"
    PRODUCT_UPDATED = "product_updated"


# ── DashboardEvent ───────────────────────────────────────────


@dataclass
class DashboardEvent:
    """仪表盘事件."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: DashboardEventType = DashboardEventType.SYSTEM_STATUS_CHANGED
    product_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "product_id": self.product_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# ── GrowthDashboardState ─────────────────────────────────────


@dataclass
class GrowthDashboardState:
    """系统总览状态."""
    system_status: SystemStatus = SystemStatus.IDLE
    active_products: int = 0
    active_cycles: int = 0
    running_tasks: int = 0
    pending_decisions: int = 0
    health_score: float = 1.0
    last_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_status": self.system_status.value,
            "active_products": self.active_products,
            "active_cycles": self.active_cycles,
            "running_tasks": self.running_tasks,
            "pending_decisions": self.pending_decisions,
            "health_score": round(self.health_score, 2),
            "last_update": self.last_update,
        }


# ── ProductDashboard ─────────────────────────────────────────


@dataclass
class ProductDashboard:
    """单产品仪表盘状态."""
    product_id: str = ""
    lifecycle_stage: LifecycleStage = LifecycleStage.GROWTH
    current_roas: float = 0.0
    trend: TrendDirection = TrendDirection.STABLE
    risk_level: RiskLevel = RiskLevel.LOW
    growth_score: float = 0.0
    active_strategy: str = ""
    budget_allocation: float = 0.0
    active_experiments: int = 0
    completed_cycles: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "lifecycle_stage": self.lifecycle_stage.value,
            "current_roas": round(self.current_roas, 4),
            "trend": self.trend.value,
            "risk_level": self.risk_level.value,
            "growth_score": round(self.growth_score, 2),
            "active_strategy": self.active_strategy,
            "budget_allocation": round(self.budget_allocation, 2),
            "active_experiments": self.active_experiments,
            "completed_cycles": self.completed_cycles,
            "last_updated": self.last_updated,
        }


# ── DecisionView ─────────────────────────────────────────────


@dataclass
class DecisionView:
    """AI 决策展示."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    action: str = ""
    reason: str = ""
    confidence: float = 0.0
    priority: int = 0
    impact: str = ""
    source_module: str = ""
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "product_id": self.product_id,
            "action": self.action,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "priority": self.priority,
            "impact": self.impact,
            "source_module": self.source_module,
            "status": self.status,
            "created_at": self.created_at,
        }


# ── TaskView ─────────────────────────────────────────────────


@dataclass
class TaskView:
    """执行任务展示."""
    task_id: str = ""
    task_type: str = ""
    product_id: str = ""
    status: str = "pending"
    progress: float = 0.0
    target_module: str = ""
    strategy_id: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "product_id": self.product_id,
            "status": self.status,
            "progress": round(self.progress, 2),
            "target_module": self.target_module,
            "strategy_id": self.strategy_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ── PatternView ──────────────────────────────────────────────


@dataclass
class PatternView:
    """学习模式展示."""
    pattern_id: str = ""
    name: str = ""
    description: str = ""
    usage_count: int = 0
    success_rate: float = 0.0
    avg_roas: float = 0.0
    confidence: float = 0.0
    reliability: float = 0.0
    gene_tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "usage_count": self.usage_count,
            "success_rate": round(self.success_rate, 2),
            "avg_roas": round(self.avg_roas, 4),
            "confidence": round(self.confidence, 2),
            "reliability": round(self.reliability, 2),
            "gene_tags": self.gene_tags,
            "created_at": self.created_at,
        }


# ── PortfolioMetrics ─────────────────────────────────────────


@dataclass
class PortfolioMetrics:
    """组合指标."""
    total_spend: float = 0.0
    total_revenue: float = 0.0
    portfolio_roas: float = 0.0
    portfolio_ltv: float = 0.0
    portfolio_fitness: float = 0.0
    product_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_spend": round(self.total_spend, 2),
            "total_revenue": round(self.total_revenue, 2),
            "portfolio_roas": round(self.portfolio_roas, 4),
            "portfolio_ltv": round(self.portfolio_ltv, 2),
            "portfolio_fitness": round(self.portfolio_fitness, 2),
            "product_count": self.product_count,
        }


# ── GrowthCycleView ──────────────────────────────────────────


@dataclass
class GrowthCycleView:
    """增长循环视图."""
    cycle_number: int = 0
    state: str = ""
    outcome: str = ""
    strategy_id: str = ""
    execution_id: str = ""
    has_errors: bool = False
    patterns_learned: int = 0
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_number": self.cycle_number,
            "state": self.state,
            "outcome": self.outcome,
            "strategy_id": self.strategy_id,
            "execution_id": self.execution_id,
            "has_errors": self.has_errors,
            "patterns_learned": self.patterns_learned,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ── DashboardOverview ────────────────────────────────────────


@dataclass
class DashboardOverview:
    """仪表盘总览."""
    system: GrowthDashboardState = field(default_factory=GrowthDashboardState)
    portfolio: PortfolioMetrics = field(default_factory=PortfolioMetrics)
    products: list[ProductDashboard] = field(default_factory=list)
    recent_decisions: list[DecisionView] = field(default_factory=list)
    active_tasks: list[TaskView] = field(default_factory=list)
    top_patterns: list[PatternView] = field(default_factory=list)
    system_events: list[DashboardEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system.to_dict(),
            "portfolio": self.portfolio.to_dict(),
            "products": [p.to_dict() for p in self.products],
            "recent_decisions": [d.to_dict() for d in self.recent_decisions],
            "active_tasks": [t.to_dict() for t in self.active_tasks],
            "top_patterns": [p.to_dict() for p in self.top_patterns],
            "system_events": [e.to_dict() for e in self.system_events],
        }