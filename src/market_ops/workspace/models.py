"""Workspace DTO — 适配 PRD 字段需求, 不侵入现有 dataclass.

字段映射策略:
  - 现有 AgentRecord.identity.agent_id  ->  WorkspaceAgent.id
  - 现有 AgentRecord.identity.name      ->  WorkspaceAgent.name
  - 现有 AgentRecord.identity.role      ->  WorkspaceAgent.department (映射)
  - 现有 AgentRecord.status             ->  WorkspaceAgent.status
  - 现有 AgentRecord.identity.capabilities -> WorkspaceAgent.capabilities
  - 新增: confidence, last_active, current_tasks, recent_decisions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkspaceAgent:
    """AI 员工 (适配 PRD Agent Detail 页面)."""
    id: str
    name: str
    department: str
    status: str  # running | idle | offline | degraded
    confidence: float  # 0.0 - 1.0
    capabilities: list[str] = field(default_factory=list)
    last_active: str = ""
    current_task_ids: list[str] = field(default_factory=list)
    recent_decision_ids: list[str] = field(default_factory=list)
    avatar_color: str = "#6366f1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "department": self.department,
            "status": self.status,
            "confidence": self.confidence,
            "capabilities": self.capabilities,
            "last_active": self.last_active,
            "current_task_ids": self.current_task_ids,
            "recent_decision_ids": self.recent_decision_ids,
            "avatar_color": self.avatar_color,
        }


@dataclass
class WorkspaceTask:
    """任务 (适配 PRD Task Center)."""
    id: str
    title: str
    agent_id: str
    agent_name: str
    game_id: str = ""
    game_name: str = ""
    status: str = "pending"  # pending | running | waiting_approval | completed | failed
    priority: str = "medium"  # low | medium | high | critical
    progress: int = 0  # 0 - 100
    steps: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "game_id": self.game_id,
            "game_name": self.game_name,
            "status": self.status,
            "priority": self.priority,
            "progress": self.progress,
            "steps": self.steps,
            "created_at": self.created_at,
        }


@dataclass
class WorkspaceEvent:
    """事件流 (适配 PRD Activity Stream)."""
    id: str
    timestamp: str
    agent_id: str
    agent_name: str
    event_type: str  # info | success | warning | error | decision
    message: str
    game_id: str = ""
    game_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "event_type": self.event_type,
            "message": self.message,
            "game_id": self.game_id,
            "game_name": self.game_name,
        }


@dataclass
class WorkspaceDecision:
    """决策 (适配 PRD Decision Center)."""
    id: str
    agent_id: str
    agent_name: str
    game_id: str
    game_name: str
    action: str
    reason: str
    confidence: float
    impact: str
    status: str = "executed"  # proposed | approved | executed | rejected
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "game_id": self.game_id,
            "game_name": self.game_name,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "impact": self.impact,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class WorkspaceGame:
    """游戏 (适配 PRD Game Portfolio)."""
    id: str
    name: str
    genre: str
    status: str  # growing | stable | declining | launching
    health_score: int  # 0 - 100
    dau: int
    revenue: float  # daily USD
    spend: float  # daily USD
    roas: float
    ltv: float
    retention_d1: float
    retention_d7: float
    retention_d30: float
    ai_manager: str = ""
    market: str = "US"
    trend: str = "up"  # up | flat | down

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "genre": self.genre,
            "status": self.status,
            "health_score": self.health_score,
            "dau": self.dau,
            "revenue": self.revenue,
            "spend": self.spend,
            "roas": self.roas,
            "ltv": self.ltv,
            "retention_d1": self.retention_d1,
            "retention_d7": self.retention_d7,
            "retention_d30": self.retention_d30,
            "ai_manager": self.ai_manager,
            "market": self.market,
            "trend": self.trend,
        }


@dataclass
class DashboardKPI:
    """Dashboard 顶部 KPI 卡片."""
    games: int
    total_dau: int
    total_revenue: float
    total_spend: float
    avg_roas: float
    avg_ltv: float
    ai_tasks: int
    automation_rate: float  # 0.0 - 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "games": self.games,
            "total_dau": self.total_dau,
            "total_revenue": self.total_revenue,
            "total_spend": self.total_spend,
            "avg_roas": self.avg_roas,
            "avg_ltv": self.avg_ltv,
            "ai_tasks": self.ai_tasks,
            "automation_rate": self.automation_rate,
        }


@dataclass
class DailyBriefing:
    """今日 AI 简报."""
    date: str
    greeting: str
    highlights: list[dict[str, Any]]  # {type, title, detail, suggestion}
    alerts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "greeting": self.greeting,
            "highlights": self.highlights,
            "alerts": self.alerts,
        }


@dataclass
class OrganizationNode:
    """组织架构树节点."""
    id: str
    name: str
    type: str  # company | department | agent
    children: list["OrganizationNode"] = field(default_factory=list)
    agent_id: str = ""
    status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "children": [c.to_dict() for c in self.children],
            "agent_id": self.agent_id,
            "status": self.status,
        }
