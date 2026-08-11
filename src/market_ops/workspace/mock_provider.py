"""Mock Data Provider — 内置 Mock 数据生成器.

基于现有 GamePortfolioEntry / PerformanceSnapshot 结构生成 mock KPI 数据。
代码即数据, 无独立 JSON 文件。

设计原则:
  - 单例模式, 全局共享一份 mock 数据
  - 数据真实合理 (参考海外手游真实指标范围)
  - 可被 DashboardAggregator 消费
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from .models import (
    DailyBriefing,
    DashboardKPI,
    WorkspaceAgent,
    WorkspaceDecision,
    WorkspaceEvent,
    WorkspaceGame,
    WorkspaceTask,
)


class MockDataProvider:
    """内置 Mock 数据提供者 — 生成 AI Game Studio OS 全量 mock 数据."""

    def __init__(self) -> None:
        self._agents: list[WorkspaceAgent] = []
        self._tasks: list[WorkspaceTask] = []
        self._events: list[WorkspaceEvent] = []
        self._decisions: list[WorkspaceDecision] = []
        self._games: list[WorkspaceGame] = []
        self._seed()

    def _seed(self) -> None:
        """初始化 mock 数据."""
        self._seed_games()
        self._seed_agents()
        self._seed_tasks()
        self._seed_events()
        self._seed_decisions()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _seed_games(self) -> None:
        games_data = [
            {"id": "p04", "name": "Witch Merge", "genre": "Merge", "status": "growing",
             "health": 86, "dau": 120000, "rev": 50000, "spend": 28000, "roas": 1.8,
             "ltv": 4.2, "r1": 0.42, "r7": 0.18, "r30": 0.08, "market": "US", "trend": "up"},
            {"id": "p07", "name": "Seaside Town", "genre": "Simulation", "status": "stable",
             "health": 72, "dau": 85000, "rev": 32000, "spend": 18000, "roas": 1.5,
             "ltv": 3.1, "r1": 0.38, "r7": 0.15, "r30": 0.06, "market": "US", "trend": "flat"},
            {"id": "p12", "name": "Dragon Puzzle", "genre": "Puzzle", "status": "growing",
             "health": 81, "dau": 95000, "rev": 38000, "spend": 22000, "roas": 1.7,
             "ltv": 3.8, "r1": 0.40, "r7": 0.16, "r30": 0.07, "market": "JP", "trend": "up"},
            {"id": "p19", "name": "Zombie Defense", "genre": "Action", "status": "declining",
             "health": 58, "dau": 42000, "rev": 15000, "spend": 12000, "roas": 1.2,
             "ltv": 2.5, "r1": 0.30, "r7": 0.10, "r30": 0.04, "market": "US", "trend": "down"},
            {"id": "p23", "name": "Cozy Garden", "genre": "Casual", "status": "launching",
             "health": 65, "dau": 28000, "rev": 8000, "spend": 15000, "roas": 0.5,
             "ltv": 1.8, "r1": 0.35, "r7": 0.12, "r30": 0.05, "market": "US", "trend": "up"},
        ]
        for g in games_data:
            self._games.append(WorkspaceGame(
                id=g["id"], name=g["name"], genre=g["genre"], status=g["status"],
                health_score=g["health"], dau=g["dau"], revenue=g["rev"], spend=g["spend"],
                roas=g["roas"], ltv=g["ltv"], retention_d1=g["r1"], retention_d7=g["r7"],
                retention_d30=g["r30"], ai_manager="UA Agent", market=g["market"], trend=g["trend"],
            ))

    def _seed_agents(self) -> None:
        agents_data = [
            {"id": "ceo", "name": "CEO Agent", "dept": "Executive", "status": "running",
             "conf": 0.92, "caps": ["Portfolio Strategy", "Budget Allocation", "Risk Assessment"],
             "color": "#ef4444"},
            {"id": "ua", "name": "UA Agent", "dept": "Growth", "status": "running",
             "conf": 0.89, "caps": ["Campaign Analysis", "Budget Optimization", "Creative Evaluation",
                                    "ROAS Prediction", "Memory Learning"],
             "color": "#3b82f6"},
            {"id": "creative", "name": "Creative Agent", "dept": "Growth", "status": "running",
             "conf": 0.94, "caps": ["Creative Generation", "Winner DNA Analysis", "A/B Testing",
                                    "Video Production", "Asset Management"],
             "color": "#8b5cf6"},
            {"id": "data", "name": "Data Agent", "dept": "Data", "status": "running",
             "conf": 0.96, "caps": ["Data Sync", "User Analytics", "Funnel Analysis",
                                   "Retention Analysis", "Revenue Reporting"],
             "color": "#10b981"},
            {"id": "revenue", "name": "Revenue Agent", "dept": "Data", "status": "idle",
             "conf": 0.87, "caps": ["IAP Optimization", "Ad Revenue", "LTV Modeling",
                                   "Paywall Design", "Pricing Strategy"],
             "color": "#f59e0b"},
            {"id": "aso", "name": "ASO Agent", "dept": "Growth", "status": "running",
             "conf": 0.85, "caps": ["Keyword Research", "Screenshot Optimization",
                                   "Store Listing", "Competitor Analysis"],
             "color": "#06b6d4"},
            {"id": "publish", "name": "Publishing Agent", "dept": "Operation", "status": "idle",
             "conf": 0.82, "caps": ["App Store Upload", "Metadata Management",
                                   "Localization", "Review Submission"],
             "color": "#ec4899"},
            {"id": "product", "name": "Product Agent", "dept": "Product", "status": "idle",
             "conf": 0.71, "caps": ["Market Research", "Game Design", "Roadmap Planning"],
             "color": "#14b8a6"},
            {"id": "liveops", "name": "LiveOps Agent", "dept": "LiveOps", "status": "running",
             "conf": 0.88, "caps": ["Churn Analysis", "Winback Campaign Design",
                                    "Lifecycle Segmentation", "Retention Uplift",
                                    "Player Re-engagement"],
             "color": "#d946ef"},
        ]
        for a in agents_data:
            self._agents.append(WorkspaceAgent(
                id=a["id"], name=a["name"], department=a["dept"], status=a["status"],
                confidence=a["conf"], capabilities=a["caps"], last_active=self._now(),
                avatar_color=a["color"],
            ))

    def _seed_tasks(self) -> None:
        tasks_data = [
            {"id": "t1", "title": "优化 P04 美国市场预算", "agent": "ua", "aname": "UA Agent",
             "game": "p04", "gname": "Witch Merge", "status": "running", "pri": "high", "prog": 70,
             "steps": [{"name": "获取数据", "done": True}, {"name": "分析原因", "done": True},
                       {"name": "生成策略", "done": True}, {"name": "执行调整", "done": True},
                       {"name": "评估结果", "done": False}]},
            {"id": "t2", "title": "生成 20 个 Creative 变体", "agent": "creative", "aname": "Creative Agent",
             "game": "p04", "gname": "Witch Merge", "status": "running", "pri": "high", "prog": 45,
             "steps": [{"name": "分析 Winner DNA", "done": True}, {"name": "生成变体", "done": True},
                       {"name": "A/B 测试", "done": False}, {"name": "评估结果", "done": False}]},
            {"id": "t3", "title": "分析 D7 留存下降原因", "agent": "data", "aname": "Data Agent",
             "game": "p07", "gname": "Seaside Town", "status": "running", "pri": "high", "prog": 60,
             "steps": [{"name": "数据同步", "done": True}, {"name": "留存分析", "done": True},
                       {"name": "Funnel 分析", "done": True}, {"name": "生成报告", "done": False}]},
            {"id": "t4", "title": "调整 IAP 价格策略", "agent": "revenue", "aname": "Revenue Agent",
             "game": "p12", "gname": "Dragon Puzzle", "status": "waiting_approval", "pri": "critical", "prog": 30,
             "steps": [{"name": "LTV 建模", "done": True}, {"name": "竞品分析", "done": True},
                       {"name": "方案设计", "done": False}, {"name": "等待审批", "done": False}]},
            {"id": "t5", "title": "优化 ASO 关键词", "agent": "aso", "aname": "ASO Agent",
             "game": "p04", "gname": "Witch Merge", "status": "completed", "pri": "medium", "prog": 100,
             "steps": [{"name": "关键词研究", "done": True}, {"name": "竞品分析", "done": True},
                       {"name": "更新关键词", "done": True}, {"name": "验证效果", "done": True}]},
            {"id": "t6", "title": "提交 P23 App Store 审核", "agent": "publish", "aname": "Publishing Agent",
             "game": "p23", "gname": "Cozy Garden", "status": "pending", "pri": "medium", "prog": 0,
             "steps": [{"name": "准备 Metadata", "done": False}, {"name": "上传 Build", "done": False},
                       {"name": "提交审核", "done": False}]},
        ]
        for t in tasks_data:
            self._tasks.append(WorkspaceTask(
                id=t["id"], title=t["title"], agent_id=t["agent"], agent_name=t["aname"],
                game_id=t["game"], game_name=t["gname"], status=t["status"], priority=t["pri"],
                progress=t["prog"], steps=t["steps"], created_at=self._now(),
            ))

    def _seed_events(self) -> None:
        events_data = [
            ("e1", "09:01", "data", "Data Agent", "info", "完成数据同步 (ThinkingData + Adjust)", "p04", "Witch Merge"),
            ("e2", "09:05", "ua", "UA Agent", "warning", "发现 ROAS 下降 12%, Creative 疲劳信号", "p07", "Seaside Town"),
            ("e3", "09:10", "creative", "Creative Agent", "info", "生成 20 个新素材变体", "p04", "Witch Merge"),
            ("e4", "09:20", "ceo", "CEO Agent", "decision", "批准 P04 预算调整 +30%", "p04", "Witch Merge"),
            ("e5", "09:25", "ua", "UA Agent", "success", "启动 A/B 测试 (5 组 Creative)", "p04", "Witch Merge"),
            ("e6", "09:30", "revenue", "Revenue Agent", "info", "检测到 IAP 转化率下降 8%", "p12", "Dragon Puzzle"),
            ("e7", "09:35", "data", "Data Agent", "warning", "D7 留存下降至 15% (阈值 18%)", "p07", "Seaside Town"),
            ("e8", "09:40", "aso", "ASO Agent", "success", "ASO 关键词优化完成, 排名提升 +3", "p04", "Witch Merge"),
            ("e9", "09:45", "creative", "Creative Agent", "info", "Winner DNA 分析完成", "p04", "Witch Merge"),
            ("e10", "09:50", "ceo", "CEO Agent", "info", "生成今日经营报告", "", ""),
        ]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for eid, time_str, aid, aname, etype, msg, gid, gname in events_data:
            self._events.append(WorkspaceEvent(
                id=eid, timestamp=f"{today}T{time_str}:00Z", agent_id=aid, agent_name=aname,
                event_type=etype, message=msg, game_id=gid, game_name=gname,
            ))

    def _seed_decisions(self) -> None:
        decisions_data = [
            {"id": "d1", "agent": "ua", "aname": "UA Agent", "game": "p04", "gname": "Witch Merge",
             "action": "增加美国市场预算 30%", "reason": "D7 ROAS 1.8, 超过目标 1.5, Creative B CTR 提升",
             "conf": 0.87, "impact": "+$5000/day revenue", "status": "executed"},
            {"id": "d2", "agent": "ceo", "aname": "CEO Agent", "game": "p19", "gname": "Zombie Defense",
             "action": "暂停日本市场投放", "reason": "D7 留存下降, CPI 上涨 25%, ROAS 低于 1.0",
             "conf": 0.92, "impact": "节省 $3000/day spend", "status": "executed"},
            {"id": "d3", "agent": "revenue", "aname": "Revenue Agent", "game": "p12", "gname": "Dragon Puzzle",
             "action": "调整礼包价格 $4.99 -> $3.99", "reason": "LTV 模型预测降价后总收入提升 15%",
             "conf": 0.78, "impact": "+15% IAP revenue (预测)", "status": "waiting_approval"},
            {"id": "d4", "agent": "creative", "aname": "Creative Agent", "game": "p04", "gname": "Witch Merge",
             "action": "主推 Character + Surprise 素材方向", "reason": "Winner DNA 分析: 此类素材 ROAS +22%",
             "conf": 0.91, "impact": "+22% ROAS (历史数据)", "status": "executed"},
            {"id": "d5", "agent": "ua", "aname": "UA Agent", "game": "p07", "gname": "Seaside Town",
             "action": "降低 Meta Campaign 出价 15%", "reason": "CPI 上涨, Creative 疲劳, 等待新素材",
             "conf": 0.83, "impact": "-$2000/day spend", "status": "executed"},
        ]
        for d in decisions_data:
            self._decisions.append(WorkspaceDecision(
                id=d["id"], agent_id=d["agent"], agent_name=d["aname"], game_id=d["game"],
                game_name=d["gname"], action=d["action"], reason=d["reason"], confidence=d["conf"],
                impact=d["impact"], status=d["status"], created_at=self._now(),
            ))

    # ── 查询接口 ──────────────────────────────────────────────

    def get_agents(self) -> list[WorkspaceAgent]:
        return self._agents

    def get_agent(self, agent_id: str) -> WorkspaceAgent | None:
        for a in self._agents:
            if a.id == agent_id:
                return a
        return None

    def get_tasks(self) -> list[WorkspaceTask]:
        return self._tasks

    def get_task(self, task_id: str) -> WorkspaceTask | None:
        for t in self._tasks:
            if t.id == task_id:
                return t
        return None

    def get_events(self, limit: int = 50) -> list[WorkspaceEvent]:
        return sorted(self._events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_decisions(self) -> list[WorkspaceDecision]:
        return self._decisions

    def get_games(self) -> list[WorkspaceGame]:
        return self._games

    def get_game(self, game_id: str) -> WorkspaceGame | None:
        for g in self._games:
            if g.id == game_id:
                return g
        return None

    def get_kpi(self) -> DashboardKPI:
        total_dau = sum(g.dau for g in self._games)
        total_rev = sum(g.revenue for g in self._games)
        total_spend = sum(g.spend for g in self._games)
        avg_roas = sum(g.roas for g in self._games) / max(len(self._games), 1)
        avg_ltv = sum(g.ltv for g in self._games) / max(len(self._games), 1)
        ai_tasks = len(self._tasks)
        auto_tasks = sum(1 for t in self._tasks if t.status in ("running", "completed"))
        auto_rate = auto_tasks / max(ai_tasks, 1)
        return DashboardKPI(
            games=len(self._games), total_dau=total_dau, total_revenue=total_rev,
            total_spend=total_spend, avg_roas=round(avg_roas, 2), avg_ltv=round(avg_ltv, 2),
            ai_tasks=ai_tasks, automation_rate=round(auto_rate, 2),
        )

    def get_daily_briefing(self) -> DailyBriefing:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        hour = datetime.now(timezone.utc).hour
        if hour < 12:
            greeting = "Good Morning"
        elif hour < 18:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"
        return DailyBriefing(
            date=today, greeting=greeting,
            highlights=[
                {"type": "success", "title": "P04 Witch Merge 美国市场 ROAS 提升 18%",
                 "detail": "原因: Creative B CTR 提升", "suggestion": "建议: 增加预算 30%"},
                {"type": "warning", "title": "P07 Seaside D7 Retention 下降 12%",
                 "detail": "原因: Level 5 流失严重", "suggestion": "建议: 优化新手流程"},
                {"type": "info", "title": "P12 Dragon Puzzle IAP 转化率下降 8%",
                 "detail": "原因: 礼包定价偏高", "suggestion": "建议: 测试 $3.99 价格点"},
            ],
            alerts=[
                {"type": "warning", "title": "Creative 疲劳", "detail": "P07 Meta Campaign CTR 下降 15%"},
                {"type": "info", "title": "新素材已就绪", "detail": "20 个 Creative 变体可投放"},
            ],
        )


# 全局单例
_mock_provider: MockDataProvider | None = None


def get_mock_provider() -> MockDataProvider:
    global _mock_provider
    if _mock_provider is None:
        _mock_provider = MockDataProvider()
    return _mock_provider
