"""CEO Decision Center — 整合 CEO Intelligence 9 个子模块的统一决策中心.

提供公司级仪表盘、投资组合俯瞰、决策队列管理、跨部门资源分配视图。
不新增算法层，仅做聚合编排，复用 ceo_intelligence 现有能力。

设计原则:
  - 只读聚合：不修改 CEO Intelligence 数据，仅读取和编排
  - 统一入口：所有 CEO 决策通过 Decision Center 暴露
  - 跨部门视图：整合 GrowthLoop / LiveOps / Product / Creative 各域数据
  - 降级容错：子模块不可用时降级为空结果，不阻断整体

数据源:
  - data/ceo/approval_queue.jsonl     — 待审批决策
  - data/ceo/audit/decisions.jsonl    — 已审批决策
  - data/ceo/execution_memory.jsonl   — 执行记忆
  - data/ceo/execution_experience.jsonl — 经验学习
  - data/ceo/operator_memory.jsonl    — 操作员日志
  - data/ceo/company_snapshot.jsonl   — 公司快照
  - data/ceo/game_reality/            — 游戏现实数据
  - data/growth_loop/cycle_history.jsonl — GrowthLoop 历史
  - data/liveops/campaign_executions.jsonl — LiveOps 执行
  - data/product/prds.jsonl           — 产品 PRD
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CEODecisionCenter:
    """CEO Decision Center — 统一决策中心.

    用法:
        center = CEODecisionCenter(data_dir="data")
        dashboard = center.get_dashboard()
        report = center.get_company_report()
        portfolio = center.get_portfolio_overview()
    """

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)

    # ── 核心方法 ─────────────────────────────────────────────

    def get_dashboard(self) -> dict[str, Any]:
        """CEO 决策中心仪表盘 — 一页全览公司状态.

        Returns:
            {
                "company_status": HEALTHY/ATTENTION/CRITICAL,
                "summary": {游戏数/决策数/执行数/成功率/收入/ROAS},
                "departments": {growth/liveops/product/creative 各域统计},
                "pending_actions": [...],  # 待处理事项
                "alerts": [...],          # 告警
                "recent_decisions": [...], # 最近决策
                "kpi_cards": {...},       # KPI 卡片
            }
        """
        # 各域统计
        approval_stats = self._get_approval_stats()
        growth_stats = self._get_growth_loop_stats()
        liveops_stats = self._get_liveops_stats()
        product_stats = self._get_product_stats()
        exec_memory_stats = self._get_execution_memory_stats()

        # 公司状态判定
        pending_count = approval_stats["pending_count"]
        critical_alerts = approval_stats["critical_pending"]
        success_rate = growth_stats.get("success_rate", 0.0)
        has_growth_data = growth_stats.get("total_cycles", 0) > 0

        if critical_alerts > 0 or (has_growth_data and success_rate < 0.5):
            company_status = "CRITICAL"
        elif pending_count > 10 or (has_growth_data and success_rate < 0.8):
            company_status = "ATTENTION"
        else:
            company_status = "HEALTHY"

        # 待处理事项
        pending_actions = self._get_pending_actions()

        # 告警
        alerts = self._get_alerts(approval_stats, growth_stats, liveops_stats)

        # 最近决策
        recent_decisions = self._get_recent_decisions(limit=10)

        # KPI 卡片
        kpi_cards = self._get_kpi_cards(growth_stats, liveops_stats, product_stats)

        return {
            "company_status": company_status,
            "generated_at": _now_iso(),
            "summary": {
                "total_games": product_stats.get("total_games", 0),
                "pending_decisions": pending_count,
                "total_executions": exec_memory_stats["total_executions"],
                "success_rate": round(success_rate, 4),
                "growth_loop_cycles": growth_stats.get("total_cycles", 0),
                "liveops_campaigns": liveops_stats.get("total_executions", 0),
                "product_prds": product_stats.get("total_prds", 0),
            },
            "departments": {
                "growth": growth_stats,
                "liveops": liveops_stats,
                "product": product_stats,
                "approval": approval_stats,
            },
            "pending_actions": pending_actions,
            "alerts": alerts,
            "recent_decisions": recent_decisions,
            "kpi_cards": kpi_cards,
        }

    def get_company_report(self) -> dict[str, Any]:
        """公司日报 — CEO 每日决策参考.

        整合各子系统数据，生成结构化的公司运营日报。
        """
        dashboard = self.get_dashboard()

        # 部门报告
        dept_reports = self._get_department_reports()

        # 投资组合
        portfolio = self.get_portfolio_overview()

        # 资源分配建议
        resource_allocation = self._get_resource_allocation(dashboard, portfolio)

        # 下一步行动建议
        next_actions = self._get_next_actions(dashboard)

        return {
            "report_date": datetime.now(timezone.utc).date().isoformat(),
            "generated_at": _now_iso(),
            "company_status": dashboard["company_status"],
            "executive_summary": self._build_executive_summary(dashboard),
            "department_reports": dept_reports,
            "portfolio": portfolio,
            "resource_allocation": resource_allocation,
            "next_actions": next_actions,
            "kpi_summary": dashboard["kpi_cards"],
            "pending_decisions": dashboard["pending_actions"],
        }

    def get_portfolio_overview(self) -> dict[str, Any]:
        """投资组合俯瞰 — 所有游戏的健康度和表现.

        从 game_reality 数据聚合每款游戏的关键指标。
        """
        game_reality_dir = self.data_dir / "ceo" / "game_reality"
        games: list[dict[str, Any]] = []

        if game_reality_dir.exists():
            for jsonl_file in sorted(game_reality_dir.glob("*.jsonl")):
                records = _read_jsonl(jsonl_file, limit=1)
                if records:
                    game_data = records[0]
                    games.append(self._extract_game_summary(game_data))

        # 按收入排序
        games.sort(key=lambda g: g.get("revenue_daily", 0), reverse=True)

        # 组合统计
        total_revenue = sum(g.get("revenue_daily", 0) for g in games)
        total_dau = sum(g.get("dau", 0) for g in games)
        healthy_count = sum(1 for g in games if g.get("health") == "healthy")
        attention_count = sum(1 for g in games if g.get("health") == "attention")
        critical_count = sum(1 for g in games if g.get("health") == "critical")

        return {
            "total_games": len(games),
            "total_revenue_daily": round(total_revenue, 2),
            "total_dau": total_dau,
            "health_distribution": {
                "healthy": healthy_count,
                "attention": attention_count,
                "critical": critical_count,
            },
            "games": games[:20],  # Top 20
        }

    def get_pending_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取待审批决策列表."""
        path = self.data_dir / "ceo" / "approval_queue.jsonl"
        records = _read_jsonl(path, limit=500)

        # 收集已有 resolution 的 audit_id
        resolved_ids = {
            r.get("audit_id") for r in records
            if r.get("kind") == "resolution"
        }

        pending = [
            r for r in records
            if r.get("status") == "pending"
            and not r.get("executed")
            and r.get("audit_id") not in resolved_ids
        ]
        return pending[:limit]

    def get_decision_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取已审批决策历史."""
        path = self.data_dir / "ceo" / "audit" / "decisions.jsonl"
        return _read_jsonl(path, limit)

    def get_execution_timeline(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取执行时间线 — 跨所有域的执行记录."""
        path = self.data_dir / "ceo" / "execution_memory.jsonl"
        records = _read_jsonl(path, limit)

        # 按域分组统计
        domain_counts: dict[str, int] = {}
        for r in records:
            domain = r.get("domain", "unknown")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        return {
            "timeline": records,
            "domain_distribution": domain_counts,
            "total_records": len(records),
        }

    def get_cross_department_view(self) -> dict[str, Any]:
        """跨部门协同视图 — 各域当前状态和待办."""
        return {
            "growth_loop": self._get_growth_loop_stats(),
            "liveops": self._get_liveops_stats(),
            "product": self._get_product_stats(),
            "approval": self._get_approval_stats(),
            "execution": self._get_execution_memory_stats(),
            "agent_topology": self._get_agent_topology(),
        }

    # ── 内部统计方法 ─────────────────────────────────────────

    def _get_approval_stats(self) -> dict[str, Any]:
        """审批队列统计."""
        path = self.data_dir / "ceo" / "approval_queue.jsonl"
        records = _read_jsonl(path, limit=1000)

        resolved_ids = {
            r.get("audit_id") for r in records
            if r.get("kind") == "resolution"
        }

        pending = [
            r for r in records
            if r.get("status") == "pending"
            and not r.get("executed")
            and r.get("audit_id") not in resolved_ids
        ]

        # 按游戏分组
        pending_by_game: dict[str, int] = {}
        for r in pending:
            game = r.get("game_id", "unknown")
            pending_by_game[game] = pending_by_game.get(game, 0) + 1

        # 高风险待审批（risk > 0.7）
        critical = [r for r in pending if r.get("risk", 0) > 0.7]

        return {
            "pending_count": len(pending),
            "critical_pending": len(critical),
            "pending_by_game": pending_by_game,
            "total_resolved": len(resolved_ids),
        }

    def _get_growth_loop_stats(self) -> dict[str, Any]:
        """GrowthLoop 执行统计."""
        path = self.data_dir / "growth_loop" / "cycle_history.jsonl"
        records = _read_jsonl(path, limit=100)

        if not records:
            return {"total_cycles": 0, "success_rate": 0.0, "total_actions": 0}

        total_cycles = len(records)
        total_actions = sum(r.get("actions_executed", 0) for r in records)
        total_success = sum(
            1 for r in records
            for e in (r.get("execution_results") or [])
            if isinstance(e, dict) and e.get("success")
        )
        total_results = sum(
            1 for r in records
            for e in (r.get("execution_results") or [])
            if isinstance(e, dict)
        )
        success_rate = total_success / max(total_results, 1)

        latest = records[0] if records else {}
        return {
            "total_cycles": total_cycles,
            "success_rate": round(success_rate, 4),
            "total_actions": total_actions,
            "latest_cycle": latest.get("cycle_number", 0),
            "latest_cycle_at": latest.get("completed_at", ""),
        }

    def _get_liveops_stats(self) -> dict[str, Any]:
        """LiveOps 执行统计."""
        path = self.data_dir / "liveops" / "campaign_executions.jsonl"
        records = _read_jsonl(path, limit=500)

        if not records:
            return {"total_executions": 0, "completed": 0, "success_rate": 0.0}

        # 按 execution_id 去重
        latest: dict[str, dict] = {}
        for r in records:
            exec_id = r.get("execution_id", "")
            latest[exec_id] = r

        status_counts: dict[str, int] = Counter(
            r.get("status", "unknown") for r in latest.values()
        )
        completed = status_counts.get("completed", 0)
        success_rate = completed / max(len(latest), 1)

        return {
            "total_executions": len(latest),
            "completed": completed,
            "blocked": status_counts.get("blocked", 0),
            "dry_run": status_counts.get("dry_run", 0),
            "failed": status_counts.get("failed", 0),
            "success_rate": round(success_rate, 4),
        }

    def _get_product_stats(self) -> dict[str, Any]:
        """产品 PRD 统计."""
        prd_path = self.data_dir / "product" / "prds.jsonl"
        gdd_path = self.data_dir / "product" / "gdds.jsonl"
        roadmap_path = self.data_dir / "product" / "roadmaps.jsonl"

        prds = _read_jsonl(prd_path, limit=100)
        gdds = _read_jsonl(gdd_path, limit=100)
        roadmaps = _read_jsonl(roadmap_path, limit=100)

        genre_dist: dict[str, int] = Counter(p.get("genre", "unknown") for p in prds)
        go_no_go_dist: dict[str, int] = Counter(p.get("go_no_go", "unknown") for p in prds)

        # 游戏总数（从 game_reality 或 PRD）
        game_reality_dir = self.data_dir / "ceo" / "game_reality"
        total_games = len(list(game_reality_dir.glob("*.jsonl"))) if game_reality_dir.exists() else 0

        return {
            "total_prds": len(prds),
            "total_gdds": len(gdds),
            "total_roadmaps": len(roadmaps),
            "total_games": total_games,
            "genre_distribution": dict(genre_dist),
            "go_no_go_distribution": dict(go_no_go_dist),
        }

    def _get_execution_memory_stats(self) -> dict[str, Any]:
        """执行记忆统计."""
        path = self.data_dir / "ceo" / "execution_memory.jsonl"
        records = _read_jsonl(path, limit=500)

        if not records:
            return {"total_executions": 0, "domain_distribution": {}, "success_rate": 0.0}

        domain_counts: dict[str, int] = Counter(
            r.get("domain", "unknown") for r in records
        )
        success_count = sum(1 for r in records if r.get("success"))
        success_rate = success_count / max(len(records), 1)

        return {
            "total_executions": len(records),
            "domain_distribution": dict(domain_counts),
            "success_rate": round(success_rate, 4),
        }

    def _get_pending_actions(self) -> list[dict[str, Any]]:
        """获取待处理事项列表."""
        actions: list[dict[str, Any]] = []

        # 1. 待审批决策
        pending_decisions = self.get_pending_decisions(limit=10)
        for d in pending_decisions:
            actions.append({
                "type": "approval_pending",
                "priority": "HIGH" if d.get("risk", 0) > 0.7 else "NORMAL",
                "title": f"审批决策: {d.get('game_id', 'unknown')} - {d.get('opportunity_id', '')}",
                "detail": d.get("description", ""),
                "audit_id": d.get("audit_id", ""),
            })

        # 2. GrowthLoop 最近失败的 cycle
        gl_path = self.data_dir / "growth_loop" / "cycle_history.jsonl"
        gl_records = _read_jsonl(gl_path, limit=5)
        for r in gl_records:
            failed = [
                e for e in (r.get("execution_results") or [])
                if isinstance(e, dict) and not e.get("success")
            ]
            if failed:
                actions.append({
                    "type": "growth_loop_failed",
                    "priority": "HIGH",
                    "title": f"Cycle #{r.get('cycle_number', 0)} 有 {len(failed)} 个失败动作",
                    "detail": str(failed[0].get("error", "")) if failed else "",
                })

        # 3. LiveOps 待审批活动
        lo_path = self.data_dir / "liveops" / "campaign_executions.jsonl"
        lo_records = _read_jsonl(lo_path, limit=20)
        for r in lo_records:
            if r.get("status") == "blocked":
                actions.append({
                    "type": "liveops_approval",
                    "priority": "NORMAL",
                    "title": f"LiveOps 活动待审批: {r.get('campaign_id', '')}",
                    "detail": f"game={r.get('game_id', '')}, type={r.get('campaign_type', '')}",
                })

        return actions[:20]

    def _get_alerts(
        self, approval_stats: dict, growth_stats: dict, liveops_stats: dict
    ) -> list[dict[str, Any]]:
        """生成告警列表."""
        alerts: list[dict[str, Any]] = []

        # 审批积压
        if approval_stats["pending_count"] > 10:
            alerts.append({
                "severity": "warning",
                "category": "approval",
                "message": f"待审批积压 {approval_stats['pending_count']} 条",
                "suggestion": "及时处理 pending 审批",
            })

        # 高风险待审批
        if approval_stats["critical_pending"] > 0:
            alerts.append({
                "severity": "critical",
                "category": "approval",
                "message": f"{approval_stats['critical_pending']} 条高风险待审批",
                "suggestion": "优先处理 risk > 0.7 的审批",
            })

        # GrowthLoop 成功率
        gl_rate = growth_stats.get("success_rate", 1.0)
        if gl_rate < 0.8 and growth_stats.get("total_cycles", 0) > 0:
            alerts.append({
                "severity": "critical" if gl_rate < 0.5 else "warning",
                "category": "growth_loop",
                "message": f"GrowthLoop 成功率 {gl_rate:.1%}",
                "suggestion": "检查最近 cycle 的失败动作",
            })

        # LiveOps 成功率
        lo_rate = liveops_stats.get("success_rate", 1.0)
        if lo_rate < 0.8 and liveops_stats.get("total_executions", 0) > 0:
            alerts.append({
                "severity": "warning",
                "category": "liveops",
                "message": f"LiveOps 成功率 {lo_rate:.1%}",
                "suggestion": "检查 campaign_executions 中的 failed 记录",
            })

        return alerts

    def _get_recent_decisions(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取最近决策."""
        path = self.data_dir / "ceo" / "audit" / "decisions.jsonl"
        records = _read_jsonl(path, limit)
        return records

    def _get_kpi_cards(
        self, growth_stats: dict, liveops_stats: dict, product_stats: dict
    ) -> dict[str, Any]:
        """KPI 卡片数据."""
        return {
            "growth_loop": {
                "cycles": growth_stats.get("total_cycles", 0),
                "success_rate": growth_stats.get("success_rate", 0.0),
                "actions": growth_stats.get("total_actions", 0),
            },
            "liveops": {
                "campaigns": liveops_stats.get("total_executions", 0),
                "success_rate": liveops_stats.get("success_rate", 0.0),
                "completed": liveops_stats.get("completed", 0),
            },
            "product": {
                "prds": product_stats.get("total_prds", 0),
                "gdds": product_stats.get("total_gdds", 0),
                "games": product_stats.get("total_games", 0),
            },
        }

    def _get_department_reports(self) -> dict[str, Any]:
        """各部门报告."""
        return {
            "growth": {
                "status": "active",
                "stats": self._get_growth_loop_stats(),
                "recent_cycles": _read_jsonl(
                    self.data_dir / "growth_loop" / "cycle_history.jsonl", limit=5
                ),
            },
            "liveops": {
                "status": "active",
                "stats": self._get_liveops_stats(),
                "recent_executions": _read_jsonl(
                    self.data_dir / "liveops" / "campaign_executions.jsonl", limit=5
                ),
            },
            "product": {
                "status": "active",
                "stats": self._get_product_stats(),
                "recent_prds": _read_jsonl(
                    self.data_dir / "product" / "prds.jsonl", limit=5
                ),
            },
        }

    def _get_resource_allocation(
        self, dashboard: dict, portfolio: dict
    ) -> dict[str, Any]:
        """资源分配建议."""
        games = portfolio.get("games", [])
        total_revenue = portfolio.get("total_revenue_daily", 0)

        # 按收入占比分配建议
        allocation: list[dict[str, Any]] = []
        for g in games[:10]:
            revenue = g.get("revenue_daily", 0)
            share = revenue / max(total_revenue, 1)
            health = g.get("health", "unknown")
            if health == "healthy":
                action = "维持投入"
            elif health == "attention":
                action = "优化调整"
            else:
                action = "减少投入"
            allocation.append({
                "game_id": g.get("game_id", ""),
                "revenue_share": round(share, 4),
                "current_health": health,
                "suggested_action": action,
            })

        return {
            "total_revenue": round(total_revenue, 2),
            "allocation": allocation,
        }

    def _get_next_actions(self, dashboard: dict) -> list[dict[str, Any]]:
        """下一步行动建议."""
        actions: list[dict[str, Any]] = []
        pending = dashboard.get("pending_actions", [])

        # 高优先级待处理
        for p in pending[:5]:
            if p.get("priority") == "HIGH":
                actions.append({
                    "action": p.get("title", ""),
                    "type": p.get("type", ""),
                    "priority": "IMMEDIATE",
                    "detail": p.get("detail", ""),
                })

        # 公司状态建议
        status = dashboard.get("company_status", "HEALTHY")
        if status == "CRITICAL":
            actions.append({
                "action": "系统处于 CRITICAL 状态，需要立即介入",
                "type": "system",
                "priority": "IMMEDIATE",
            })
        elif status == "ATTENTION":
            actions.append({
                "action": "系统处于 ATTENTION 状态，建议检查告警",
                "type": "system",
                "priority": "HIGH",
            })

        return actions

    def _build_executive_summary(self, dashboard: dict) -> str:
        """构建执行摘要."""
        summary = dashboard.get("summary", {})
        status = dashboard.get("company_status", "UNKNOWN")
        pending = summary.get("pending_decisions", 0)
        cycles = summary.get("growth_loop_cycles", 0)
        success = summary.get("success_rate", 0.0)
        games = summary.get("total_games", 0)

        return (
            f"公司状态: {status} | "
            f"游戏数: {games} | "
            f"待审批: {pending} | "
            f"GrowthLoop: {cycles} cycles (成功率 {success:.1%}) | "
            f"生成于 {dashboard.get('generated_at', '')}"
        )

    def _extract_game_summary(self, game_data: dict) -> dict[str, Any]:
        """从游戏现实数据提取摘要."""
        revenue = 0.0
        dau = 0
        roas = 0.0

        # 尝试从不同字段提取
        for key in ("revenue_daily", "revenue", "iap_revenue", "ad_revenue"):
            val = game_data.get(key)
            if isinstance(val, (int, float)):
                revenue += val
        for key in ("dau", "daily_active_users"):
            val = game_data.get(key)
            if isinstance(val, int):
                dau = val
        for key in ("roas", "roas_d30", "roas_d60"):
            val = game_data.get(key)
            if isinstance(val, (int, float)):
                roas = val
                break

        # 健康度判定
        if roas > 1.0 and revenue > 100:
            health = "healthy"
        elif roas < 0.5 or revenue < 10:
            health = "critical"
        else:
            health = "attention"

        return {
            "game_id": game_data.get("game_id", game_data.get("id", "unknown")),
            "game_name": game_data.get("game_name", game_data.get("name", "unknown")),
            "revenue_daily": round(revenue, 2),
            "dau": dau,
            "roas": round(roas, 4),
            "health": health,
        }

    def _get_agent_topology(self) -> dict[str, Any]:
        """获取 Agent 拓扑."""
        path = self.data_dir / "workspace" / "agents.jsonl"
        agents = _read_jsonl(path, limit=50)

        nodes = []
        for a in agents:
            nodes.append({
                "agent_id": a.get("agent_id", ""),
                "name": a.get("name", ""),
                "role": a.get("role", ""),
                "status": a.get("status", "unknown"),
                "department": a.get("department", ""),
            })

        return {
            "total_agents": len(nodes),
            "agents": nodes,
        }


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 字符串."""
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    """读取 JSONL 文件最后 N 条记录（倒序返回，最新在前）."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.reverse()
    return records
