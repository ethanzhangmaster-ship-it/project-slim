"""Dashboard Aggregator — 数据聚合层.

将 DataProvider 的数据聚合为 Dashboard 需要的格式。
通过环境变量 WORKSPACE_DATA_PROVIDER 切换 mock/real 数据源。
"""

from __future__ import annotations

import os
from typing import Any

from .mock_provider import get_mock_provider
from .models import OrganizationNode


def _get_provider():
    """根据环境变量选择数据 provider.

    WORKSPACE_DATA_PROVIDER=real  → RealDataProvider (GrowthLoop + CEO JSONL)
    WORKSPACE_DATA_PROVIDER=mock  → MockDataProvider (默认)
    """
    mode = os.environ.get("WORKSPACE_DATA_PROVIDER", "mock").lower()
    if mode == "real":
        from .real_provider import get_real_provider
        return get_real_provider()
    return get_mock_provider()


class DashboardAggregator:
    """Dashboard 数据聚合器 — 薄层, 组合 DataProvider."""

    def __init__(self) -> None:
        self.provider = _get_provider()

    def get_dashboard(self) -> dict[str, Any]:
        """聚合 Dashboard 全量数据."""
        kpi = self.provider.get_kpi()
        briefing = self.provider.get_daily_briefing()
        games = [g.to_dict() for g in self.provider.get_games()]
        recent_events = [e.to_dict() for e in self.provider.get_events(limit=5)]
        active_tasks = [t.to_dict() for t in self.provider.get_tasks() if t.status == "running"]
        return {
            "kpi": kpi.to_dict(),
            "briefing": briefing.to_dict(),
            "games": games,
            "recent_events": recent_events,
            "active_tasks": active_tasks,
        }

    def get_organization(self) -> dict[str, Any]:
        """生成组织架构树."""
        agents = self.provider.get_agents()
        agent_map = {a.id: a for a in agents}

        # 按部门分组
        departments: dict[str, list] = {
            "Executive": [], "Product": [], "Growth": [],
            "Data": [], "Operation": [], "LiveOps": [],
        }
        for a in agents:
            if a.department in departments:
                departments[a.department].append(a)

        dept_labels = {
            "Executive": "CEO Office", "Product": "Product Department",
            "Growth": "Growth Department", "Data": "Data Department",
            "Operation": "Operation Department", "LiveOps": "LiveOps Department",
        }

        children = []
        for dept_key, dept_label in dept_labels.items():
            dept_agents = departments.get(dept_key, [])
            agent_nodes = [
                OrganizationNode(
                    id=f"agent-{a.id}", name=a.name, type="agent",
                    agent_id=a.id, status=a.status,
                ) for a in dept_agents
            ]
            children.append(OrganizationNode(
                id=f"dept-{dept_key.lower()}", name=dept_label, type="department",
                children=agent_nodes,
            ))

        root = OrganizationNode(
            id="company", name="AI Game Studio", type="company", children=children,
        )
        return root.to_dict()

    def get_agent_detail(self, agent_id: str) -> dict[str, Any] | None:
        """获取 Agent 详情 (含当前任务和最近决策)."""
        agent = self.provider.get_agent(agent_id)
        if not agent:
            return None
        tasks = [t.to_dict() for t in self.provider.get_tasks() if t.agent_id == agent_id]
        decisions = [d.to_dict() for d in self.provider.get_decisions() if d.agent_id == agent_id]
        result = agent.to_dict()
        result["tasks"] = tasks
        result["decisions"] = decisions
        return result

    def get_game_detail(self, game_id: str) -> dict[str, Any] | None:
        """获取游戏详情."""
        game = self.provider.get_game(game_id)
        if not game:
            return None
        events = [e.to_dict() for e in self.provider.get_events() if e.game_id == game_id]
        tasks = [t.to_dict() for t in self.provider.get_tasks() if t.game_id == game_id]
        result = game.to_dict()
        result["recent_events"] = events
        result["tasks"] = tasks
        result["ai_team"] = [
            {"id": "ceo", "name": "CEO Agent"},
            {"id": "ua", "name": "UA Agent"},
            {"id": "creative", "name": "Creative Agent"},
            {"id": "data", "name": "Data Agent"},
            {"id": "revenue", "name": "Revenue Agent"},
        ]
        return result


# 全局单例
_aggregator: DashboardAggregator | None = None


def get_aggregator() -> DashboardAggregator:
    global _aggregator
    if _aggregator is None:
        _aggregator = DashboardAggregator()
    return _aggregator
