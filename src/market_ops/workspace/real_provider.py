"""Real Data Provider — 接入真实持久化数据.

从 GrowthLoop cycle_history.jsonl、CEO decisions.jsonl、game_reality/*.jsonl
和 company_snapshot.jsonl 读取真实数据.

设计原则:
  - 直接读取 JSONL 文件, 不依赖业务模块导入 (轻量稳健)
  - 实现与 MockDataProvider 相同接口, 可无缝替换
  - 数据源缺失或解析失败时优雅降级到空列表
  - 单例模式, 每次调用读取最新数据 (无缓存, 保证实时性)

数据源:
  - data/growth_loop/cycle_history.jsonl  → tasks, events
  - data/ceo/audit/decisions.jsonl        → decisions (CEO 决策)
  - data/ceo/approval_queue.jsonl         → decisions (等待审批)
  - data/ceo/game_reality/*.jsonl         → games (每游戏真实 KPI)
  - data/ceo/company_snapshot.jsonl       → KPI 公司级聚合
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    DailyBriefing,
    DashboardKPI,
    WorkspaceAgent,
    WorkspaceDecision,
    WorkspaceEvent,
    WorkspaceGame,
    WorkspaceTask,
)
from .mock_provider import MockDataProvider
from .agent_registry_store import get_agents_data

logger = logging.getLogger(__name__)

# 项目根目录 (workspace/real_provider.py → project_slim/)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 真实数据源路径
GROWTH_LOOP_HISTORY = _PROJECT_ROOT / "data" / "growth_loop" / "cycle_history.jsonl"
CEO_DECISIONS_AUDIT = _PROJECT_ROOT / "data" / "ceo" / "audit" / "decisions.jsonl"
CEO_APPROVAL_QUEUE = _PROJECT_ROOT / "data" / "ceo" / "approval_queue.jsonl"
GAME_REALITY_DIR = _PROJECT_ROOT / "data" / "ceo" / "game_reality"
COMPANY_SNAPSHOT = _PROJECT_ROOT / "data" / "ceo" / "company_snapshot.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL 文件, 返回 dict 列表. 文件不存在或解析失败返回空列表."""
    if not path.exists():
        logger.debug("JSONL file not found: %s", path)
        return []
    records: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to read %s: %s", path, exc)
        return []
    for line_num, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            logger.warning("JSONL parse error at %s:%d: %s", path.name, line_num, exc)
    return records


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_jsonl_last(path: Path) -> dict[str, Any] | None:
    """读取 JSONL 文件的最后一行 (最新快照). 文件不存在返回 None."""
    records = _read_jsonl(path)
    return records[-1] if records else None


def _read_company_snapshot() -> dict[str, Any] | None:
    """读取公司快照 (JSONL, 取最后一行最新快照)."""
    return _read_jsonl_last(COMPANY_SNAPSHOT)


def _game_id_to_name(game_id: str) -> str:
    """将 game_id 转换为可读名称. 如 cooking_fever_x → Cooking Fever X."""
    return game_id.replace("_", " ").title()


def _infer_genre(game_id: str) -> str:
    """基于 game_id 关键词推断游戏类型."""
    gid = game_id.lower()
    if "merge" in gid:
        return "Merge"
    if "cooking" in gid or "chef" in gid:
        return "Cooking"
    if "quiz" in gid or "trivia" in gid:
        return "Trivia"
    if "vampire" in gid or "horror" in gid or "mansion" in gid:
        return "Adventure"
    if "travel" in gid or "word" in gid:
        return "Puzzle"
    if "hospital" in gid or "drama" in gid:
        return "Simulation"
    if "bible" in gid:
        return "Religious"
    return "Casual"


def _infer_game_status(snapshot: dict[str, Any]) -> str:
    """根据 metrics 和 release_state 推断游戏状态."""
    metrics = snapshot.get("metrics", {}) or {}
    revenue = _safe_float(metrics.get("revenue_total"))
    dau = _safe_float(metrics.get("dau"))

    # 检查 release_state signal
    signals = snapshot.get("signals", []) or []
    release_signal = next(
        (s for s in signals if s.get("signal_type") == "release_state"),
        None,
    )
    raw_status = (release_signal or {}).get("raw", {}) or {}
    is_published = raw_status.get("status") == "published"

    if not is_published and revenue == 0 and dau == 0:
        return "launching"
    if revenue > 0 and dau > 0:
        # 有真实数据, 根据 health_score 判断
        health = _safe_float(snapshot.get("health_score"))
        if health >= 0.5:
            return "growing"
        if health >= 0.3:
            return "stable"
        return "declining"
    return "launching"


# ── Agent 角色到 Workspace 部门的映射 ──────────────────────

_ROLE_TO_DEPARTMENT: dict[str, str] = {
    "supervisor": "Executive",
    "ua": "Growth",
    "creative": "Growth",
    "monetization": "Data",
    "product": "Product",
    "observer": "Operation",
    "executor": "Operation",
    "memory": "Data",
    "liveops": "LiveOps",
    "designer": "Design",
    "numerical": "Design",
}

_ROLE_TO_AVATAR_COLOR: dict[str, str] = {
    "supervisor": "#ef4444",
    "ua": "#3b82f6",
    "creative": "#8b5cf6",
    "monetization": "#f59e0b",
    "product": "#10b981",
    "observer": "#06b6d4",
    "executor": "#6366f1",
    "memory": "#ec4899",
    "liveops": "#d946ef",
    "designer": "#0ea5e9",
    "numerical": "#14b8a6",
}


def _agent_status_to_workspace(status: str) -> str:
    """AgentStatus (online/idle/busy/degraded/offline) → Workspace status (running/idle/offline/degraded)."""
    mapping = {
        "online": "running",
        "idle": "idle",
        "busy": "running",
        "degraded": "degraded",
        "offline": "offline",
        "unknown": "idle",
    }
    return mapping.get(status, "idle")


def _agent_record_to_workspace(record: dict[str, Any]) -> WorkspaceAgent:
    """将 AgentRecord dict 转换为 WorkspaceAgent."""
    identity = record.get("identity", {}) or {}
    agent_id = identity.get("agent_id", "unknown")
    role = identity.get("role", "unknown")
    name = identity.get("name", "") or f"{role}_agent"
    capabilities = identity.get("capabilities", []) or []
    status_raw = record.get("status", "online")
    last_heartbeat = record.get("last_heartbeat", "")

    return WorkspaceAgent(
        id=agent_id,
        name=name,
        department=_ROLE_TO_DEPARTMENT.get(role, "Operation"),
        status=_agent_status_to_workspace(status_raw),
        confidence=0.9,  # 默认置信度, 后续可从 metrics 接入
        capabilities=capabilities,
        last_active=last_heartbeat,
        current_task_ids=[],
        recent_decision_ids=[],
        avatar_color=_ROLE_TO_AVATAR_COLOR.get(role, "#6366f1"),
    )


class RealDataProvider:
    """真实数据提供者 — 从持久化 JSONL 读取数据.

    接入:
      - GrowthLoop cycle_history → tasks (actions), events (cycle 事件)
      - CEO decisions audit → decisions (决策记录)
      - CEO approval_queue → decisions (待审批)

    暂时回退到 Mock (待后续 Phase 接入):
      - games (需 Revenue Intelligence)
      - agents (需 AgentRegistry 持久化)
      - kpi (需 Revenue Intelligence 聚合)
      - briefing (需 AI 简报生成)
    """

    def __init__(self) -> None:
        # Mock 作为回退数据源 (games/agents/kpi/briefing)
        self._fallback = MockDataProvider()
        logger.info(
            "RealDataProvider initialized: project_root=%s, "
            "growth_loop_history=%s (exists=%s), "
            "ceo_decisions=%s (exists=%s)",
            _PROJECT_ROOT,
            GROWTH_LOOP_HISTORY, GROWTH_LOOP_HISTORY.exists(),
            CEO_DECISIONS_AUDIT, CEO_DECISIONS_AUDIT.exists(),
        )

    # ── GrowthLoop 数据转换 ──────────────────────────────────

    @staticmethod
    def _action_to_task(
        action: dict[str, Any],
        cycle: dict[str, Any],
        index: int,
    ) -> WorkspaceTask:
        """将 GrowthLoop action 转换为 WorkspaceTask."""
        action_id = action.get("action_id", f"action-{index}")
        action_type = action.get("action_type", "unknown")
        strategy = action.get("expected_impact", {}) or {}
        strategy_type = strategy.get("strategy_type", "")
        reason = action.get("reason", "")

        # 执行状态映射
        status_raw = action.get("status", "pending")
        executed_at = action.get("executed_at")
        if executed_at:
            status = "completed"
        elif status_raw == "pending":
            status = "running"
        else:
            status = status_raw

        # 审批级别映射
        approval_level = action.get("approval_level", 0)
        if approval_level and int(approval_level) >= 2:
            status = "waiting_approval"

        # 风险级别映射
        risk_level = action.get("risk_level", "low")
        priority_map = {"low": "low", "medium": "medium", "high": "high"}
        priority = priority_map.get(risk_level, "medium")
        if strategy.get("intensity", 0) >= 1.0:
            priority = "high"

        # 步骤: 基于 action_type 推断
        steps = _build_action_steps(action_type, bool(executed_at))

        # 时间戳
        created_at = action.get("created_at") or cycle.get("started_at", "")

        return WorkspaceTask(
            id=action_id,
            title=f"{action_type}: {strategy_type}" if strategy_type else action_type,
            agent_id="growth_loop",
            agent_name="GrowthLoop Engine",
            game_id=strategy.get("metric", ""),
            game_name=cycle.get("loop_id", ""),
            status=status,
            priority=priority,
            progress=100 if status == "completed" else (50 if status == "running" else 0),
            steps=steps,
            created_at=created_at,
        )

    @staticmethod
    def _cycle_to_events(cycle: dict[str, Any]) -> list[WorkspaceEvent]:
        """将一个 CycleRecord 转换为多个 WorkspaceEvent."""
        events: list[WorkspaceEvent] = []
        cycle_num = cycle.get("cycle_number", 0)
        started_at = cycle.get("started_at", "")
        loop_id = cycle.get("loop_id", "")

        # Cycle 开始事件
        actions_planned = cycle.get("actions_planned", 0)
        if actions_planned:
            events.append(WorkspaceEvent(
                id=f"cycle-{cycle_num}-start",
                timestamp=started_at,
                agent_id="growth_loop",
                agent_name="GrowthLoop Engine",
                event_type="info",
                message=f"Cycle #{cycle_num} 启动, 规划 {actions_planned} 个动作",
                game_id=loop_id,
                game_name=loop_id,
            ))

        # 执行结果事件
        for result in cycle.get("execution_results", []):
            action_id = result.get("action_id", "")
            success = result.get("success", False)
            dry_run = result.get("dry_run", False)
            status = result.get("status", "")
            prefix = "[DRY-RUN] " if dry_run else ""
            event_type = "success" if success else "error"
            action = next(
                (a for a in cycle.get("actions", []) if a.get("action_id") == action_id),
                {},
            )
            action_type = action.get("action_type", "unknown")
            reason = action.get("reason", action_type)
            events.append(WorkspaceEvent(
                id=f"cycle-{cycle_num}-exec-{action_id}",
                timestamp=result.get("executed_at", started_at),
                agent_id="growth_loop",
                agent_name="GrowthLoop Engine",
                event_type=event_type,
                message=f"{prefix}{reason} → {status}",
                game_id=loop_id,
                game_name=loop_id,
            ))

        # Cycle 完成事件
        completed_at = cycle.get("completed_at", "")
        if completed_at:
            executed = cycle.get("actions_executed", 0)
            planned = cycle.get("actions_planned", 0)
            rolled_back = cycle.get("actions_rolled_back", 0)
            msg = f"Cycle #{cycle_num} 完成: {executed}/{planned} 执行"
            if rolled_back:
                msg += f", {rolled_back} 回滚"
            events.append(WorkspaceEvent(
                id=f"cycle-{cycle_num}-end",
                timestamp=completed_at,
                agent_id="growth_loop",
                agent_name="GrowthLoop Engine",
                event_type="success" if executed == planned else "warning",
                message=msg,
                game_id=loop_id,
                game_name=loop_id,
            ))

        return events

    # ── CEO Decision 数据转换 ─────────────────────────────────

    @staticmethod
    def _ceo_decision_to_workspace(
        record: dict[str, Any],
        index: int,
        source: str = "audit",
    ) -> WorkspaceDecision:
        """将 CEO 决策记录转换为 WorkspaceDecision."""
        decision_id = record.get("decision_id", f"ceo-dec-{index}")
        action = record.get("action", "unknown")
        game_id = record.get("game_id", "")
        reason = record.get("reason", "")
        confidence = _safe_float(record.get("confidence"), 0.5)
        timestamp = record.get("timestamp", "")

        # inputs 字段
        inputs = record.get("inputs", {}) or {}
        opportunity_type = inputs.get("opportunity_type", "")
        expected_value = _safe_float(inputs.get("expected_value"))
        simulation = inputs.get("simulation", {}) or {}
        rev_change = _safe_float(simulation.get("expected_revenue_change"))
        roas_change = _safe_float(simulation.get("expected_roas_change"))

        # 影响: 组合预期价值 + 模拟变化
        impact_parts: list[str] = []
        if expected_value:
            impact_parts.append(f"预期价值 {expected_value:.2f}")
        if rev_change:
            impact_parts.append(f"收入 {'+' if rev_change > 0 else ''}{rev_change*100:.0f}%")
        if roas_change:
            impact_parts.append(f"ROAS {'+' if roas_change > 0 else ''}{roas_change*100:.0f}%")
        impact = " · ".join(impact_parts) if impact_parts else "—"

        # 状态: audit 中的记录通常已处理, approval_queue 中是待审批
        if source == "queue":
            status = "waiting_approval" if record.get("status") in (None, "", "queued") else record.get("status", "waiting_approval")
        else:
            status = "executed"

        return WorkspaceDecision(
            id=decision_id,
            agent_id="ceo",
            agent_name="CEO Decision Engine",
            game_id=game_id,
            game_name=game_id,
            action=action,
            reason=reason or f"机会类型: {opportunity_type}",
            confidence=confidence,
            impact=impact,
            status=status,
            created_at=timestamp,
        )

    # ── 查询接口 (与 MockDataProvider 一致) ────────────────────

    def get_agents(self) -> list[WorkspaceAgent]:
        """Agent 列表 — 从 AgentRegistry 持久化快照读取.

        首次调用时自动创建默认组织 (5 个标准 Agent) 并持久化.
        """
        records = get_agents_data()
        if not records:
            logger.warning("No agents data available, falling back to mock")
            return self._fallback.get_agents()
        agents = [_agent_record_to_workspace(r) for r in records]
        logger.debug("RealDataProvider: loaded %d agents", len(agents))
        return agents

    def get_agent(self, agent_id: str) -> WorkspaceAgent | None:
        """Agent 详情 — 从持久化快照查找."""
        for agent in self.get_agents():
            if agent.id == agent_id:
                return agent
        return None

    def get_tasks(self) -> list[WorkspaceTask]:
        """任务列表 — 从 GrowthLoop cycle_history 读取真实 actions."""
        tasks: list[WorkspaceTask] = []
        cycles = _read_jsonl(GROWTH_LOOP_HISTORY)
        # 取最近 5 个 cycle 的 actions (避免任务过多)
        for cycle in cycles[-5:]:
            for i, action in enumerate(cycle.get("actions", [])):
                tasks.append(self._action_to_task(action, cycle, i))
        logger.debug("RealDataProvider: loaded %d tasks from %d cycles", len(tasks), len(cycles))
        return tasks

    def get_task(self, task_id: str) -> WorkspaceTask | None:
        for task in self.get_tasks():
            if task.id == task_id:
                return task
        return None

    def get_events(self, limit: int = 50) -> list[WorkspaceEvent]:
        """事件流 — 从 GrowthLoop cycle_history 读取真实 cycle 事件."""
        events: list[WorkspaceEvent] = []
        cycles = _read_jsonl(GROWTH_LOOP_HISTORY)
        for cycle in cycles[-10:]:  # 取最近 10 个 cycle
            events.extend(self._cycle_to_events(cycle))
        # 按时间倒序
        events.sort(key=lambda e: e.timestamp, reverse=True)
        result = events[:limit]
        logger.debug("RealDataProvider: loaded %d events from %d cycles", len(result), len(cycles))
        return result

    def get_decisions(self) -> list[WorkspaceDecision]:
        """决策列表 — 从 CEO audit/decisions 和 approval_queue 读取."""
        decisions: list[WorkspaceDecision] = []

        # CEO 决策审计 (已执行)
        audit_records = _read_jsonl(CEO_DECISIONS_AUDIT)
        for i, record in enumerate(audit_records):
            decisions.append(self._ceo_decision_to_workspace(record, i, source="audit"))

        # CEO 审批队列 (待审批)
        queue_records = _read_jsonl(CEO_APPROVAL_QUEUE)
        for i, record in enumerate(queue_records):
            decisions.append(self._ceo_decision_to_workspace(record, i + len(audit_records), source="queue"))

        # 去重 (同一 decision_id 可能同时出现在两个文件)
        seen_ids: set[str] = set()
        unique: list[WorkspaceDecision] = []
        for d in decisions:
            if d.id not in seen_ids:
                seen_ids.add(d.id)
                unique.append(d)

        # 按时间倒序
        unique.sort(key=lambda d: d.created_at, reverse=True)
        logger.debug(
            "RealDataProvider: loaded %d decisions (audit=%d, queue=%d, unique=%d)",
            len(unique), len(audit_records), len(queue_records), len(unique),
        )
        return unique

    def get_games(self) -> list[WorkspaceGame]:
        """游戏列表 — 从 game_reality/*.jsonl 读取真实 KPI.

        只返回有真实 metrics 的游戏 (revenue_total > 0 或 dau > 0).
        """
        games: list[WorkspaceGame] = []
        if not GAME_REALITY_DIR.exists():
            logger.warning("Game reality dir not found: %s", GAME_REALITY_DIR)
            return self._fallback.get_games()

        for jsonl_file in sorted(GAME_REALITY_DIR.glob("*.jsonl")):
            snapshot = _read_jsonl_last(jsonl_file)
            if not snapshot:
                continue
            metrics = snapshot.get("metrics", {}) or {}
            revenue = _safe_float(metrics.get("revenue_total"))
            dau = _safe_float(metrics.get("dau"))
            # 只返回有真实业务数据的游戏
            if revenue <= 0 and dau <= 0:
                continue
            games.append(self._snapshot_to_game(snapshot))

        # 按 DAU 倒序排列
        games.sort(key=lambda g: g.dau, reverse=True)
        logger.debug("RealDataProvider: loaded %d active games", len(games))
        return games

    def get_game(self, game_id: str) -> WorkspaceGame | None:
        """游戏详情 — 从 game_reality/{game_id}.jsonl 读取."""
        snapshot = _read_jsonl_last(GAME_REALITY_DIR / f"{game_id}.jsonl")
        if not snapshot:
            return None
        return self._snapshot_to_game(snapshot)

    @staticmethod
    def _snapshot_to_game(snapshot: dict[str, Any]) -> WorkspaceGame:
        """将 game_reality 快照转换为 WorkspaceGame."""
        game_id = snapshot.get("game_id", "unknown")
        metrics = snapshot.get("metrics", {}) or {}

        # 健康分 0.0-1.0 → 0-100
        health_raw = _safe_float(snapshot.get("health_score"))
        health_score = int(round(health_raw * 100))

        # LTV: 优先用 player_ltv, 无则用 ARPPU * 7 估算
        ltv = _safe_float(metrics.get("player_ltv"))
        if ltv <= 0:
            arppu = _safe_float(metrics.get("arppu"))
            ltv = arppu * 7 if arppu > 0 else 0.0

        return WorkspaceGame(
            id=game_id,
            name=_game_id_to_name(game_id),
            genre=_infer_genre(game_id),
            status=_infer_game_status(snapshot),
            health_score=health_score,
            dau=_safe_int(metrics.get("dau")),
            revenue=_safe_float(metrics.get("revenue_total")),
            spend=_safe_float(metrics.get("spend")),
            roas=_safe_float(metrics.get("roas")),
            ltv=round(ltv, 2),
            retention_d1=_safe_float(metrics.get("retention_d1")),
            retention_d7=_safe_float(metrics.get("retention_d7")),
            retention_d30=_safe_float(metrics.get("retention_d30")),
            ai_manager="Revenue Intelligence Agent",
            market="Global",
            trend="flat",
        )

    def get_kpi(self) -> DashboardKPI:
        """KPI — 从 company_snapshot 读取公司级聚合 + 真实 tasks 数量."""
        real_tasks = self.get_tasks()
        auto_tasks = sum(1 for t in real_tasks if t.status in ("running", "completed"))
        auto_rate = auto_tasks / max(len(real_tasks), 1)

        snapshot = _read_company_snapshot()
        if snapshot:
            # 真实公司级聚合
            games_count = _safe_int(snapshot.get("active_games", snapshot.get("total_games", 0)))
            total_dau = _safe_int(snapshot.get("total_dau"))
            total_revenue = _safe_float(snapshot.get("total_revenue"))
            # total_spend 需从 active games 聚合 (snapshot 中无此字段)
            active_games = self.get_games()
            total_spend = sum(g.spend for g in active_games)
            # avg_roas: 加权平均 (按 spend)
            total_spend_safe = max(total_spend, 1.0)
            avg_roas = sum(g.roas * g.spend for g in active_games) / total_spend_safe
            # avg_ltv: 简单平均
            avg_ltv = sum(g.ltv for g in active_games) / max(len(active_games), 1)
            return DashboardKPI(
                games=games_count,
                total_dau=total_dau,
                total_revenue=round(total_revenue, 2),
                total_spend=round(total_spend, 2),
                avg_roas=round(avg_roas, 3),
                avg_ltv=round(avg_ltv, 2),
                ai_tasks=len(real_tasks),
                automation_rate=round(auto_rate, 2),
            )

        # 回退: 从 active games 聚合
        active_games = self.get_games()
        if active_games:
            total_dau = sum(g.dau for g in active_games)
            total_revenue = sum(g.revenue for g in active_games)
            total_spend = sum(g.spend for g in active_games)
            total_spend_safe = max(total_spend, 1.0)
            avg_roas = sum(g.roas * g.spend for g in active_games) / total_spend_safe
            avg_ltv = sum(g.ltv for g in active_games) / len(active_games)
            return DashboardKPI(
                games=len(active_games),
                total_dau=total_dau,
                total_revenue=round(total_revenue, 2),
                total_spend=round(total_spend, 2),
                avg_roas=round(avg_roas, 3),
                avg_ltv=round(avg_ltv, 2),
                ai_tasks=len(real_tasks),
                automation_rate=round(auto_rate, 2),
            )

        # 最终回退到 Mock
        mock_kpi = self._fallback.get_kpi()
        return DashboardKPI(
            games=mock_kpi.games,
            total_dau=mock_kpi.total_dau,
            total_revenue=mock_kpi.total_revenue,
            total_spend=mock_kpi.total_spend,
            avg_roas=mock_kpi.avg_roas,
            avg_ltv=mock_kpi.avg_ltv,
            ai_tasks=len(real_tasks),
            automation_rate=round(auto_rate, 2),
        )

    def get_daily_briefing(self) -> DailyBriefing:
        """今日简报 — 基于真实数据生成."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        hour = datetime.now(timezone.utc).hour
        if hour < 12:
            greeting = "Good Morning"
        elif hour < 18:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"

        # 基于真实 decisions、events、games 生成 highlights
        highlights: list[dict[str, Any]] = []
        decisions = self.get_decisions()
        tasks = self.get_tasks()
        games = self.get_games()
        pending_decisions = [d for d in decisions if d.status == "waiting_approval"]
        running_tasks = [t for t in tasks if t.status == "running"]

        # 游戏组合概览
        if games:
            total_rev = sum(g.revenue for g in games)
            total_dau = sum(g.dau for g in games)
            highlights.append({
                "type": "success",
                "title": f"{len(games)} 款活跃游戏 · DAU {total_dau:,} · 日收入 ${total_rev:,.0f}",
                "detail": f"Top: {games[0].name} (ROAS {games[0].roas:.2f})",
                "suggestion": "建议: 在 Game Portfolio 查看详情",
            })
        if pending_decisions:
            highlights.append({
                "type": "warning",
                "title": f"{len(pending_decisions)} 个决策待审批",
                "detail": pending_decisions[0].action if pending_decisions else "",
                "suggestion": "建议: 在 Decision Center 处理待审批决策",
            })
        if running_tasks:
            highlights.append({
                "type": "info",
                "title": f"{len(running_tasks)} 个任务执行中",
                "detail": f"GrowthLoop 最近 {len(tasks)} 个动作",
                "suggestion": "建议: 在 Task Center 查看进度",
            })
        if not highlights:
            highlights.append({
                "type": "info",
                "title": "系统运行正常",
                "detail": "暂无紧急事项",
                "suggestion": "",
            })

        return DailyBriefing(
            date=today,
            greeting=greeting,
            highlights=highlights,
            alerts=[],
        )


# ── 辅助函数 ──────────────────────────────────────────────

def _build_action_steps(action_type: str, executed: bool) -> list[dict[str, Any]]:
    """根据 action_type 构建任务步骤."""
    if action_type == "update_budget":
        steps = [
            {"name": "信号检测", "done": True},
            {"name": "诊断分析", "done": True},
            {"name": "策略生成", "done": True},
            {"name": "预算调整", "done": executed},
            {"name": "效果评估", "done": False},
        ]
    elif action_type == "pause_campaign":
        steps = [
            {"name": "信号检测", "done": True},
            {"name": "诊断分析", "done": True},
            {"name": "策略生成", "done": True},
            {"name": "暂停 AdSet", "done": executed},
            {"name": "效果评估", "done": False},
        ]
    else:
        steps = [
            {"name": "信号检测", "done": True},
            {"name": "诊断分析", "done": True},
            {"name": "执行", "done": executed},
        ]
    return steps


# 全局单例
_real_provider: RealDataProvider | None = None


def get_real_provider() -> RealDataProvider:
    global _real_provider
    if _real_provider is None:
        _real_provider = RealDataProvider()
    return _real_provider
