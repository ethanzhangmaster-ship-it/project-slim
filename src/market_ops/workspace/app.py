"""AI Game Studio OS Workspace — FastAPI 应用.

启动 (Mock 数据):
  uvicorn market_ops.workspace.app:app --reload --port 8080

启动 (真实数据 — 读取 GrowthLoop + CEO JSONL):
  WORKSPACE_DATA_PROVIDER=real uvicorn market_ops.workspace.app:app --reload --port 8080

端点:
  GET  /api/dashboard              — Dashboard 全量数据
  GET  /api/organization           — 组织架构树
  GET  /api/agents                 — Agent 列表
  GET  /api/agents/{id}            — Agent 详情
  GET  /api/tasks                  — 任务列表
  GET  /api/tasks/{id}             — 任务详情
  GET  /api/events                 — 事件流
  GET  /api/events/stream          — SSE 实时事件推送
  GET  /api/decisions              — 决策列表
  POST /api/decisions/{id}/approve — 批准决策 (执行层)
  POST /api/decisions/{id}/reject  — 驳回决策 (执行层)
  GET  /api/games                  — 游戏列表
  GET  /api/games/{id}             — 游戏详情
  GET  /api/kpi                    — KPI 卡片数据
  GET  /api/briefing               — 今日 AI 简报
  GET  /api/memory                 — 记忆系统
  POST /api/loop/trigger           — 触发 GrowthLoop cycle (执行层)
  POST /api/loop/scheduler/start   — 启动定时调度器 (无人值守)
  POST /api/loop/scheduler/stop    — 停止定时调度器
  GET  /api/loop/scheduler/status  — 调度器状态查询
  POST /api/loop/scheduler/trigger — 立即触发一次 cycle
  POST /api/product/prd           — 生成 PRD（产品需求文档）
  POST /api/product/gdd/{id}      — 生成 GDD（游戏设计文档）
  POST /api/product/features/{id} — Feature 优先级排序
  POST /api/product/roadmap/{id}  — 生成产品路线图
  GET  /api/product/prds          — PRD 列表
  GET  /api/product/stats         — 产品统计
  GET  /api/ceo/dashboard         — CEO 决策中心仪表盘
  GET  /api/ceo/company-report    — 公司日报
  GET  /api/ceo/portfolio         — 投资组合俯瞰
  GET  /api/ceo/decisions/pending — 待审批决策
  GET  /api/ceo/cross-department  — 跨部门协同视图
  POST /api/designer/levels/{gdd_id}       — 关卡设计
  POST /api/designer/economy/{gdd_id}      — 经济数值平衡
  POST /api/designer/systems/{gdd_id}      — 系统规格
  POST /api/designer/difficulty/{gdd_id}   — 难度曲线
  POST /api/designer/document/{gdd_id}     — 完整设计文档
  GET  /api/designer/documents             — 设计文档列表
  GET  /api/designer/documents/{doc_id}    — 设计文档详情
  GET  /api/designer/stats                 — 设计统计
  POST /api/numerical/model                — 数值建模 (LTV/CAC/ROI)
  POST /api/numerical/retention            — 留存曲线建模
  POST /api/numerical/pay-conversion       — 付费转化漏斗分析
  POST /api/numerical/tuning               — 数值调优建议
  POST /api/numerical/ab-test              — A/B 测试方案设计
  POST /api/numerical/inflation            — 通胀监控
  POST /api/numerical/report               — 完整数值报告
  GET  /api/numerical/reports              — 数值报告列表
  GET  /api/numerical/reports/{report_id}  — 数值报告详情
  GET  /api/numerical/stats                — 数值统计
  POST /api/data-analyst/behavior          — 玩家行为分析
  POST /api/data-analyst/funnel            — 漏斗归因分析
  POST /api/data-analyst/retention-predict — 留存预测
  POST /api/data-analyst/segmentation      — 玩家分群
  POST /api/data-analyst/bi-report         — BI 报表
  POST /api/data-analyst/anomalies         — 异常检测
  GET  /api/data-analyst/bi-reports        — BI 报表列表
  GET  /api/data-analyst/bi-reports/{id}   — BI 报表详情
  GET  /api/data-analyst/stats             — 数据分析统计
  POST /api/player-support/ticket          — 工单处理
  POST /api/player-support/faq             — FAQ 管理
  POST /api/player-support/sentiment       — 舆情监控
  POST /api/player-support/vip             — VIP 服务
  POST /api/player-support/satisfaction    — 满意度分析
  GET  /api/player-support/tickets         — 工单列表
  GET  /api/player-support/stats           — 玩家服务统计
  POST /api/collaboration/analysis-loop              — Data Analyst→Numerical Designer 分析闭环
  GET  /api/collaboration/data-numerical             — 协同记录列表
  GET  /api/collaboration/data-numerical/{id}        — 协同记录详情
  GET  /api/collaboration/data-numerical/stats       — 协同统计
  POST /api/collaboration/reverse-loop               — Numerical→Data Analyst 反向分析闭环 (M3.1)
  GET  /api/collaboration/numerical-data             — 反向协同记录列表
  GET  /api/collaboration/numerical-data/{id}        — 反向协同记录详情
  GET  /api/collaboration/numerical-data/stats       — 反向协同统计
  GET  /api/collaboration/conflicts                  — 冲突记录列表 (M3.2)
  GET  /api/collaboration/conflicts/{id}             — 冲突记录详情
  GET  /api/collaboration/conflicts/stats            — 冲突检测统计
  GET  /api/collaboration/conflicts/versions         — 游戏数值版本表
  POST /api/collaboration/conflicts/check            — 修改前冲突预检
  POST /api/collaboration/conflicts/register         — 注册数值变更 (推进版本号)
  POST /api/maintenance/alerts/notify                — 检测告警并推送通知 (邮件/企微/飞书)
  GET  /api/maintenance/alerts/channels              — 查询通知渠道配置状态
  GET  /api/p4/readiness                             — P4 启动就绪检查
  GET  /api/p4/agent/status                          — P4 Agent 状态 (含熔断器)
  POST /api/p4/agent/run                             — P4 Agent 运行 (dry_run/production)
  POST /api/p4/agent/circuit/reset                   — P4 熔断器重置 (需授权)
  POST /api/p4/fleet/run                             — P4.1 Fleet 分片编排运行
  GET  /api/p4/cycle/{cycle_id}                      — P4.2 Cycle 状态查询
  POST /api/p4/cycle/run                             — P4.2 Cycle 运行 (可恢复)
  POST /api/p4/product/advance                       — P4.3 产品生命周期推进
  POST /api/p4/governance/arbitrate                  — P4.4 多 Agent 仲裁
  POST /api/p4/governance/takeover                   — P4.4 人工接管 (需授权)
  POST /api/p4/governance/release                    — P4.4 释放接管 (需授权)
  GET  /api/p4/governance/permissions                — P4.4 权限矩阵查询
  GET  /api/p4/slo/evaluate                          — P4.5 SLO 评估
  POST /api/p4/queue/enqueue                         — P4.5 DurableQueue 入队
  GET  /api/p4/queue/pending                         — P4.5 查询 pending
  POST /api/p4/queue/ack/{job_id}                    — P4.5 DurableQueue ack
  POST /api/p4/queue/fail/{job_id}                   — P4.5 DurableQueue fail
  GET  /api/p4/queue/dead-letters                    — P4.5 死信队列
  POST /api/p4/canary/run                            — P4.5 Canary 灰度运行
  POST /api/reports/generate                          — 生成周期报告 (daily/weekly/monthly)
  GET  /api/reports                                   — 列出报告 (可按 period / report_type 过滤)
  GET  /api/reports/stats                             — 报告统计
  GET  /api/reports/{report_id}                       — 获取报告详情
  POST /api/retirement/evaluate                       — 评估游戏退役条件
  POST /api/retirement/plan                           — 创建退役计划
  POST /api/retirement/execute                        — 执行退役流程 (dry_run 默认 true)
  GET  /api/retirement/plans                          — 列出退役计划 (可按 status 过滤)
  GET  /api/retirement/plans/{plan_id}                — 获取退役计划详情
  POST /api/retirement/cancel/{plan_id}               — 取消退役
  GET  /api/retirement/stats                          — 退役统计
  GET  /healthz                    — 健康检查
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .aggregator import get_aggregator

logger = logging.getLogger(__name__)

# 记忆系统数据源路径
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_EXECUTION_MEMORY = _PROJECT_ROOT / "data" / "ceo" / "execution_memory.jsonl"
_EXECUTION_EXPERIENCE = _PROJECT_ROOT / "data" / "ceo" / "execution_experience.jsonl"
_OPERATOR_MEMORY = _PROJECT_ROOT / "data" / "ceo" / "operator_memory.jsonl"
_GROWTH_LOOP_HISTORY = _PROJECT_ROOT / "data" / "growth_loop" / "cycle_history.jsonl"

app = FastAPI(
    title="AI Game Studio OS Workspace",
    description="AI 游戏公司管理工作台 API",
    version="0.1.0",
)

# CORS — 允许前端 (Next.js dev server) 跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict:
    """健康检查 — 含子系统状态和告警计数.

    status:
      - healthy: 无告警
      - degraded: 有 warning 告警
      - critical: 有 critical 告警
    """
    from .system_monitor import SystemMonitor
    monitor = SystemMonitor(data_dir=str(_PROJECT_ROOT / "data"))
    health = monitor.get_system_health()
    return {
        "status": health["status"],
        "service": "ai-game-studio-workspace",
        "timestamp": health["timestamp"],
        "alerts_count": health["alerts_count"],
        "critical_alerts": health["critical_alerts"],
        "warning_alerts": health["warning_alerts"],
    }


@app.get("/readyz")
async def readyz() -> dict:
    """就绪检查 — critical 状态时返回 503."""
    from .system_monitor import SystemMonitor
    monitor = SystemMonitor(data_dir=str(_PROJECT_ROOT / "data"))
    health = monitor.get_system_health()
    if health["status"] == "critical":
        raise HTTPException(status_code=503, detail={
            "status": "critical",
            "message": "系统存在 critical 告警, 暂不可用",
            "alerts_count": health["alerts_count"],
        })
    return {"status": "ready", "timestamp": health["timestamp"]}


@app.get("/api/dashboard")
async def get_dashboard() -> dict:
    """Dashboard 全量数据 (含 LiveOps 执行概览)."""
    data = get_aggregator().get_dashboard()
    # LiveOps 执行结果回流
    try:
        from .liveops_executor import LiveOpsStatsAggregator
        stats = LiveOpsStatsAggregator(data_dir=str(_PROJECT_ROOT / "data"))
        data["liveops_overview"] = stats.aggregate(recent_limit=5)
    except Exception as exc:
        logger.warning("LiveOps stats aggregate failed: %s", exc)
        data["liveops_overview"] = {"total_executions": 0, "recent_executions": []}
    return data


@app.get("/api/kpi")
async def get_kpi() -> dict:
    """KPI 卡片数据."""
    return get_aggregator().provider.get_kpi().to_dict()


@app.get("/api/briefing")
async def get_briefing() -> dict:
    """今日 AI 简报."""
    return get_aggregator().provider.get_daily_briefing().to_dict()


@app.get("/api/organization")
async def get_organization() -> dict:
    """组织架构树."""
    return get_aggregator().get_organization()


@app.get("/api/agents")
async def get_agents() -> list[dict]:
    """Agent 列表."""
    return [a.to_dict() for a in get_aggregator().provider.get_agents()]


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    """Agent 详情."""
    detail = get_aggregator().get_agent_detail(agent_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return detail


@app.get("/api/tasks")
async def get_tasks() -> list[dict]:
    """任务列表."""
    return [t.to_dict() for t in get_aggregator().provider.get_tasks()]


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    """任务详情."""
    task = get_aggregator().provider.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task.to_dict()


@app.get("/api/events")
async def get_events(limit: int = 50) -> list[dict]:
    """事件流."""
    return [e.to_dict() for e in get_aggregator().provider.get_events(limit=limit)]


@app.get("/api/decisions")
async def get_decisions() -> list[dict]:
    """决策列表."""
    return [d.to_dict() for d in get_aggregator().provider.get_decisions()]


@app.get("/api/games")
async def get_games() -> list[dict]:
    """游戏列表."""
    return [g.to_dict() for g in get_aggregator().provider.get_games()]


@app.get("/api/games/{game_id}")
async def get_game(game_id: str) -> dict:
    """游戏详情."""
    detail = get_aggregator().get_game_detail(game_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    return detail


def _read_jsonl_tail(path: Path, limit: int = 50) -> list[dict]:
    """读取 JSONL 文件最后 N 条记录."""
    if not path.exists():
        return []
    records: list[dict] = []
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
    return records


@app.get("/api/memory")
async def get_memory(limit: int = 50) -> dict:
    """记忆系统 — 执行记忆 + 经验学习 + 操作员日志."""
    execution_memory = _read_jsonl_tail(_EXECUTION_MEMORY, limit)
    execution_experience = _read_jsonl_tail(_EXECUTION_EXPERIENCE, limit)
    operator_memory = _read_jsonl_tail(_OPERATOR_MEMORY, limit)

    # 统计摘要
    total_executions = len(execution_memory)
    successful = sum(1 for r in execution_memory if r.get("success"))
    total_experiences = len(execution_experience)
    positive_rewards = sum(1 for r in execution_experience if r.get("reward", 0) > 0)

    return {
        "execution_memory": execution_memory,
        "execution_experience": execution_experience,
        "operator_memory": operator_memory,
        "summary": {
            "total_executions": total_executions,
            "successful_executions": successful,
            "success_rate": round(successful / max(total_executions, 1), 2),
            "total_experiences": total_experiences,
            "positive_rewards": positive_rewards,
            "positive_rate": round(positive_rewards / max(total_experiences, 1), 2),
            "operator_logs": len(operator_memory),
        },
    }


# ── 执行层: 决策审批 ─────────────────────────────────────────


class ApprovalRequest(BaseModel):
    """审批请求体."""
    approver: str = "workspace_admin"
    reason: str = ""


@app.post("/api/decisions/{decision_id}/approve")
async def approve_decision(decision_id: str, req: ApprovalRequest) -> dict:
    """批准一个待审批决策.

    调用 DecisionValidator.approve, 写入 approval_queue.jsonl (append resolution)
    和 audit 审计记录.
    """
    try:
        from src.ceo_intelligence.decision_engine.validator import DecisionValidator
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"DecisionValidator module not available: {exc}",
        ) from exc

    # 使用基于 _PROJECT_ROOT 的绝对路径 (便于测试 monkeypatch)
    approval_path = str(_PROJECT_ROOT / "data" / "ceo" / "approval_queue.jsonl")
    audit_dir = str(_PROJECT_ROOT / "data" / "ceo" / "audit")
    validator = DecisionValidator(
        approval_queue_path=approval_path,
        audit_dir=audit_dir,
    )
    try:
        ok = validator.approve(decision_id, approver=req.approver)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Approval failed: {exc}",
        ) from exc

    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"Decision {decision_id} not found or already resolved",
        )

    logger.info("Decision %s approved by %s", decision_id, req.approver)
    return {
        "decision_id": decision_id,
        "status": "approved",
        "approver": req.approver,
        "message": "决策已批准",
    }


@app.post("/api/decisions/{decision_id}/reject")
async def reject_decision(decision_id: str, req: ApprovalRequest) -> dict:
    """驳回一个待审批决策."""
    try:
        from src.ceo_intelligence.decision_engine.validator import DecisionValidator
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"DecisionValidator module not available: {exc}",
        ) from exc

    approval_path = str(_PROJECT_ROOT / "data" / "ceo" / "approval_queue.jsonl")
    audit_dir = str(_PROJECT_ROOT / "data" / "ceo" / "audit")
    validator = DecisionValidator(
        approval_queue_path=approval_path,
        audit_dir=audit_dir,
    )
    try:
        ok = validator.reject(decision_id, approver=req.approver)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Rejection failed: {exc}",
        ) from exc

    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"Decision {decision_id} not found or already resolved",
        )

    logger.info("Decision %s rejected by %s", decision_id, req.approver)
    return {
        "decision_id": decision_id,
        "status": "rejected",
        "approver": req.approver,
        "reason": req.reason,
        "message": "决策已驳回",
    }


# ── 执行层: GrowthLoop 历史 ─────────────────────────────────


@app.get("/api/loop/history")
async def get_loop_history(limit: int = 10) -> list[dict]:
    """GrowthLoop 历史 cycle 摘要列表 (从 cycle_history.jsonl 读取).

    返回最近 N 个 cycle 的摘要信息, 用于 Dashboard 展示执行历史.
    """
    records = _read_jsonl_tail(_GROWTH_LOOP_HISTORY, limit)
    # 倒序: 最新的在前
    records.reverse()

    summaries: list[dict] = []
    for r in records:
        actions = r.get("actions", []) or []
        execution_results = r.get("execution_results", []) or []
        success_count = sum(
            1 for e in execution_results if isinstance(e, dict) and e.get("success")
        )
        # 动作类型分布
        action_types: dict[str, int] = {}
        for a in actions:
            if isinstance(a, dict):
                at = str(a.get("action_type", "unknown"))
                action_types[at] = action_types.get(at, 0) + 1

        summaries.append({
            "cycle_number": r.get("cycle_number", 0),
            "loop_id": r.get("loop_id", ""),
            "started_at": r.get("started_at", ""),
            "completed_at": r.get("completed_at", ""),
            "duration_ms": r.get("duration_ms", 0),
            "signal_count": len(r.get("signal_ids", []) or []),
            "actions_planned": r.get("actions_planned", len(actions)),
            "actions_executed": r.get("actions_executed", len(execution_results)),
            "actions_skipped": r.get("actions_skipped", 0),
            "actions_rolled_back": r.get("actions_rolled_back", 0),
            "success_count": success_count,
            "success_rate": round(success_count / max(len(execution_results), 1), 2),
            "action_types": action_types,
            "dry_run": any(
                isinstance(e, dict) and e.get("dry_run") for e in execution_results
            ),
        })

    return summaries


@app.get("/api/loop/cycle/{cycle_number}")
async def get_loop_cycle_detail(cycle_number: int) -> dict:
    """获取单个 cycle 的完整详情 (含动作链路)."""
    records = _read_jsonl_tail(_GROWTH_LOOP_HISTORY, 200)
    for r in records:
        if r.get("cycle_number") == cycle_number:
            return r
    raise HTTPException(
        status_code=404,
        detail=f"Cycle {cycle_number} not found",
    )


# ── 执行层: GrowthLoop 定时调度器 (7×24 无人值守) ────────────


def _get_scheduler() -> "GrowthLoopScheduler":
    """获取全局调度器单例 (懒加载)."""
    if not hasattr(_get_scheduler, "_instance"):
        from .growth_loop_scheduler import GrowthLoopScheduler
        _get_scheduler._instance = GrowthLoopScheduler(
            data_dir=str(_PROJECT_ROOT / "data" / "growth_loop"),
            project_root=str(_PROJECT_ROOT),
        )
    return _get_scheduler._instance


class SchedulerStartRequest(BaseModel):
    """调度器启动请求体."""
    interval_hours: float = 6.0       # 调度间隔 (小时)
    dry_run: bool = True              # dry-run 模式
    fetch_meta_ads: bool = False      # 是否拉取真实 Meta Ads 数据
    run_immediately: bool = True      # 是否立即执行首次 cycle


@app.post("/api/loop/scheduler/start")
async def start_scheduler(req: SchedulerStartRequest) -> dict:
    """启动 GrowthLoop 定时调度器.

    启动后台线程, 按 interval_hours 间隔自动触发 GrowthLoop cycle。
    首次执行可选立即触发 (run_immediately=true) 或等待一个间隔。

    Returns:
        调度器状态 (running, interval_hours, next_cycle_at, ...)
    """
    scheduler = _get_scheduler()
    try:
        result = scheduler.start(
            interval_hours=req.interval_hours,
            dry_run=req.dry_run,
            fetch_meta_ads=req.fetch_meta_ads,
            run_immediately=req.run_immediately,
        )
        logger.info(
            "Scheduler start requested: interval=%.2fh dry_run=%s fetch_meta_ads=%s",
            req.interval_hours, req.dry_run, req.fetch_meta_ads,
        )
        return result
    except Exception as exc:
        logger.exception("Scheduler start failed")
        raise HTTPException(
            status_code=500,
            detail=f"Scheduler start failed: {exc}",
        ) from exc


@app.post("/api/loop/scheduler/stop")
async def stop_scheduler(timeout: float = 30.0) -> dict:
    """停止 GrowthLoop 定时调度器.

    优雅停止: 等待当前 cycle 完成后退出后台线程。

    Args:
        timeout: 等待线程结束的超时时间 (秒, query param)

    Returns:
        调度器最终状态
    """
    scheduler = _get_scheduler()
    try:
        result = scheduler.stop(timeout=timeout)
        logger.info("Scheduler stop requested")
        return result
    except Exception as exc:
        logger.exception("Scheduler stop failed")
        raise HTTPException(
            status_code=500,
            detail=f"Scheduler stop failed: {exc}",
        ) from exc


@app.get("/api/loop/scheduler/status")
async def get_scheduler_status() -> dict:
    """获取调度器当前状态.

    Returns:
        {
            "running": bool,
            "cycle_in_progress": bool,
            "interval_hours": float,
            "dry_run": bool,
            "started_at": ISO8601,
            "last_cycle_at": ISO8601,
            "next_cycle_at": ISO8601,
            "total_scheduled_cycles": int,
            "total_successful_cycles": int,
            "total_failed_cycles": int,
            "last_error": str,
            "last_cycle_result": {...} | null,
        }
    """
    scheduler = _get_scheduler()
    return scheduler.get_status()


@app.post("/api/loop/scheduler/trigger")
async def trigger_scheduler_now() -> dict:
    """立即触发一次 cycle (不影响调度节奏).

    如果调度器未运行或当前有 cycle 在执行中, 返回 skipped。
    """
    scheduler = _get_scheduler()
    try:
        result = scheduler.trigger_now()
        logger.info("Scheduler trigger_now: status=%s", result.get("status"))
        return result
    except Exception as exc:
        logger.exception("Scheduler trigger_now failed")
        raise HTTPException(
            status_code=500,
            detail=f"Scheduler trigger failed: {exc}",
        ) from exc


# ── Product Manager Agent: PRD/GDD/Roadmap 生成 ──────────────


def _get_product_agent() -> "ProductManagerAgent":
    """获取 Product Agent 单例（懒加载）."""
    if not hasattr(_get_product_agent, "_instance"):
        from .product_agent import ProductManagerAgent
        _get_product_agent._instance = ProductManagerAgent(
            data_dir=str(_PROJECT_ROOT / "data"),
        )
    return _get_product_agent._instance


class ProductOpportunityRequest(BaseModel):
    """市场机会请求体 — 用于生成 PRD."""
    genre: str = "Merge"             # Merge / Match3 / Simulation
    target_audience: str = ""        # 目标用户
    target_market: str = "Global"    # 目标市场
    budget_usd: float = 300000.0     # 开发预算
    timeline_months: int = 6         # 开发周期
    opportunity_id: str = ""         # 关联机会 ID
    competitor_analysis: str = ""    # 竞品分析
    market_size: str = ""            # 市场规模


@app.post("/api/product/prd")
async def generate_prd(req: ProductOpportunityRequest) -> dict:
    """从市场机会生成 PRD（产品需求文档）.

    输入品类/受众/市场/预算，自动生成完整 PRD，含 KPI 目标、风险评估、Go/No-Go 决策。
    """
    from .product_agent import MarketOpportunity
    agent = _get_product_agent()
    try:
        opportunity = MarketOpportunity(
            genre=req.genre,
            target_audience=req.target_audience,
            target_market=req.target_market,
            budget_usd=req.budget_usd,
            timeline_months=req.timeline_months,
            opportunity_id=req.opportunity_id,
            competitor_analysis=req.competitor_analysis,
            market_size=req.market_size,
        )
        prd = agent.generate_prd(opportunity)
        return prd.to_dict()
    except Exception as exc:
        logger.exception("PRD generation failed")
        raise HTTPException(
            status_code=500,
            detail=f"PRD generation failed: {exc}",
        ) from exc


@app.post("/api/product/gdd/{prd_id}")
async def generate_gdd(prd_id: str) -> dict:
    """从 PRD 生成 GDD（游戏设计文档）."""
    agent = _get_product_agent()
    try:
        gdd = agent.generate_gdd(prd_id)
        return gdd.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("GDD generation failed")
        raise HTTPException(
            status_code=500,
            detail=f"GDD generation failed: {exc}",
        ) from exc


@app.post("/api/product/features/{prd_id}")
async def prioritize_features(prd_id: str) -> dict:
    """从 PRD 生成并排序 Feature 列表."""
    agent = _get_product_agent()
    try:
        features = agent.prioritize_features(prd_id)
        return {
            "prd_id": prd_id,
            "feature_count": len(features),
            "features": [f.to_dict() for f in features],
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Feature prioritization failed")
        raise HTTPException(
            status_code=500,
            detail=f"Feature prioritization failed: {exc}",
        ) from exc


@app.post("/api/product/roadmap/{prd_id}")
async def create_roadmap(prd_id: str) -> dict:
    """从 PRD 生成产品路线图."""
    agent = _get_product_agent()
    try:
        roadmap = agent.create_roadmap(prd_id)
        return roadmap.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Roadmap creation failed")
        raise HTTPException(
            status_code=500,
            detail=f"Roadmap creation failed: {exc}",
        ) from exc


@app.get("/api/product/prds")
async def list_prds(limit: int = 50) -> list[dict]:
    """列出所有 PRD."""
    agent = _get_product_agent()
    return agent.list_prds(limit=limit)


@app.get("/api/product/prds/{prd_id}")
async def get_prd(prd_id: str) -> dict:
    """获取单个 PRD."""
    agent = _get_product_agent()
    prd = agent.get_prd(prd_id)
    if not prd:
        raise HTTPException(status_code=404, detail=f"PRD {prd_id} not found")
    return prd


@app.get("/api/product/gdds")
async def list_gdds(limit: int = 50) -> list[dict]:
    """列出所有 GDD."""
    agent = _get_product_agent()
    return agent.list_gdds(limit=limit)


@app.get("/api/product/gdds/{gdd_id}")
async def get_gdd(gdd_id: str) -> dict:
    """获取单个 GDD."""
    agent = _get_product_agent()
    gdd = agent.get_gdd(gdd_id)
    if not gdd:
        raise HTTPException(status_code=404, detail=f"GDD {gdd_id} not found")
    return gdd


@app.get("/api/product/roadmaps")
async def list_roadmaps(limit: int = 50) -> list[dict]:
    """列出所有路线图."""
    agent = _get_product_agent()
    return agent.list_roadmaps(limit=limit)


@app.get("/api/product/stats")
async def get_product_stats() -> dict:
    """产品统计概览."""
    agent = _get_product_agent()
    return agent.get_stats()


# ── CEO Decision Center: 统一决策中心 ─────────────────────────


def _get_ceo_decision_center() -> "CEODecisionCenter":
    """获取 CEO Decision Center 单例（懒加载）."""
    if not hasattr(_get_ceo_decision_center, "_instance"):
        from .ceo_decision_center import CEODecisionCenter
        _get_ceo_decision_center._instance = CEODecisionCenter(
            data_dir=str(_PROJECT_ROOT / "data"),
        )
    return _get_ceo_decision_center._instance


@app.get("/api/ceo/dashboard")
async def get_ceo_dashboard() -> dict:
    """CEO 决策中心仪表盘 — 一页全览公司状态.

    返回公司状态、各部门统计、待处理事项、告警、最近决策、KPI 卡片。
    """
    center = _get_ceo_decision_center()
    return center.get_dashboard()


@app.get("/api/ceo/company-report")
async def get_ceo_company_report() -> dict:
    """公司日报 — CEO 每日决策参考.

    整合各子系统数据，生成结构化的公司运营日报，含执行摘要、部门报告、
    投资组合、资源分配建议、下一步行动。
    """
    center = _get_ceo_decision_center()
    return center.get_company_report()


@app.get("/api/ceo/portfolio")
async def get_ceo_portfolio() -> dict:
    """投资组合俯瞰 — 所有游戏的健康度和表现."""
    center = _get_ceo_decision_center()
    return center.get_portfolio_overview()


@app.get("/api/ceo/decisions/pending")
async def get_ceo_pending_decisions(limit: int = 50) -> list[dict]:
    """获取待审批决策列表."""
    center = _get_ceo_decision_center()
    return center.get_pending_decisions(limit=limit)


@app.get("/api/ceo/decisions/history")
async def get_ceo_decision_history(limit: int = 50) -> list[dict]:
    """获取已审批决策历史."""
    center = _get_ceo_decision_center()
    return center.get_decision_history(limit=limit)


@app.get("/api/ceo/execution-timeline")
async def get_ceo_execution_timeline(limit: int = 50) -> dict:
    """获取执行时间线 — 跨所有域的执行记录."""
    center = _get_ceo_decision_center()
    return center.get_execution_timeline(limit=limit)


@app.get("/api/ceo/cross-department")
async def get_ceo_cross_department() -> dict:
    """跨部门协同视图 — 各域当前状态和待办."""
    center = _get_ceo_decision_center()
    return center.get_cross_department_view()


# ── Game Designer Agent: 关卡/数值/系统/难度设计 ─────────────


def _get_designer_agent() -> "GameDesignerAgent":
    if not hasattr(_get_designer_agent, "_instance"):
        from .game_designer_agent import GameDesignerAgent
        bus = _get_shared_message_bus()
        registry = getattr(_get_shared_message_bus, "_registry", None)
        identity = None
        if registry is not None:
            try:
                from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                    AgentRole,
                )
                records = registry.find_by_role(AgentRole.DESIGNER)
                identity = records[0].identity if records else None
            except Exception:
                pass
        _get_designer_agent._instance = GameDesignerAgent(
            data_dir=str(_PROJECT_ROOT / "data"),
            message_bus=bus,
            agent_identity=identity,
        )
    return _get_designer_agent._instance


@app.post("/api/designer/levels/{gdd_id}")
async def design_levels(gdd_id: str) -> dict:
    """从 GDD 生成关卡设计（关卡列表 + 章节结构）."""
    agent = _get_designer_agent()
    try:
        design = agent.design_levels(gdd_id)
        return design.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/designer/economy/{gdd_id}")
async def balance_economy(gdd_id: str) -> dict:
    """从 GDD 生成经济数值平衡（货币/产出/消耗/定价）."""
    agent = _get_designer_agent()
    try:
        balance = agent.balance_economy(gdd_id)
        return balance.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/designer/systems/{gdd_id}")
async def specify_systems(gdd_id: str) -> dict:
    """从 GDD 生成系统规格列表."""
    agent = _get_designer_agent()
    try:
        systems = agent.specify_systems(gdd_id)
        return {
            "gdd_id": gdd_id,
            "system_count": len(systems),
            "systems": [s.to_dict() for s in systems],
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/designer/difficulty/{gdd_id}")
async def generate_difficulty_curve(gdd_id: str) -> dict:
    """从 GDD 生成难度曲线（分阶段难度配置）."""
    agent = _get_designer_agent()
    try:
        curve = agent.generate_difficulty_curve(gdd_id)
        return curve.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/designer/document/{gdd_id}")
async def create_design_document(gdd_id: str) -> dict:
    """从 GDD 生成完整设计文档（聚合关卡/数值/系统/难度）."""
    agent = _get_designer_agent()
    try:
        doc = agent.create_design_document(gdd_id)
        return doc.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/designer/documents")
async def list_design_documents(limit: int = 50) -> list[dict]:
    """设计文档列表."""
    return _get_designer_agent().list_design_documents(limit=limit)


@app.get("/api/designer/documents/{document_id}")
async def get_design_document(document_id: str) -> dict:
    """设计文档详情."""
    doc = _get_designer_agent().get_design_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Design document {document_id} not found")
    return doc


@app.get("/api/designer/stats")
async def get_designer_stats() -> dict:
    """设计统计概览."""
    return _get_designer_agent().get_stats()


# ── Numerical Designer Agent: 数值建模/调优/A/B测试 ─────────


def _get_numerical_agent() -> "NumericalDesignerAgent":
    if not hasattr(_get_numerical_agent, "_instance"):
        from .numerical_designer_agent import NumericalDesignerAgent
        bus = _get_shared_message_bus()
        registry = getattr(_get_shared_message_bus, "_registry", None)
        identity = None
        if registry is not None:
            try:
                from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                    AgentRole,
                )
                records = registry.find_by_role(AgentRole.NUMERICAL)
                identity = records[0].identity if records else None
            except Exception:
                pass
        _get_numerical_agent._instance = NumericalDesignerAgent(
            data_dir=str(_PROJECT_ROOT / "data"),
            message_bus=bus,
            agent_identity=identity,
        )
    return _get_numerical_agent._instance


class NumericalMetricsRequest(BaseModel):
    """数值建模请求体 — 运营指标输入."""

    game_id: str
    genre: str = "Merge"
    dau: int = 10000
    total_users: int = 100000
    revenue_total: float = 5000.0
    spend: float = 3000.0
    arpu: float = 0.15
    arppu: float = 8.0
    retention_d1: float = 0.42
    retention_d7: float = 0.18
    retention_d30: float = 0.10
    payer_rate: float = 0.06
    first_pay_rate: float = 0.05
    avg_first_pay_days: float = 3.5
    avg_first_pay_amount: float = 4.99


class ABTestRequest(BaseModel):
    """A/B 测试设计请求体."""

    game_id: str
    hypothesis: str
    genre: str = "Merge"
    target_metric: str = "retention_d1"
    dau: int = 10000
    total_users: int = 100000
    arpu: float = 0.15
    arppu: float = 8.0
    retention_d1: float = 0.42
    retention_d7: float = 0.18
    retention_d30: float = 0.10
    payer_rate: float = 0.06
    first_pay_rate: float = 0.05
    avg_first_pay_days: float = 3.5
    avg_first_pay_amount: float = 4.99
    revenue_total: float = 5000.0
    spend: float = 3000.0


def _req_to_metrics(req: "NumericalMetricsRequest | ABTestRequest") -> "GameMetrics":
    """请求体转 GameMetrics."""
    from .numerical_designer_agent import GameMetrics
    return GameMetrics(
        game_id=req.game_id,
        genre=req.genre,
        dau=req.dau,
        total_users=req.total_users,
        revenue_total=req.revenue_total,
        spend=req.spend,
        arpu=req.arpu,
        arppu=req.arppu,
        retention_d1=req.retention_d1,
        retention_d7=req.retention_d7,
        retention_d30=req.retention_d30,
        payer_rate=req.payer_rate,
        first_pay_rate=req.first_pay_rate,
        avg_first_pay_days=req.avg_first_pay_days,
        avg_first_pay_amount=req.avg_first_pay_amount,
    )


@app.post("/api/numerical/model")
async def model_numerical(req: NumericalMetricsRequest) -> dict:
    """数值建模 — LTV/CAC/ROI/回本周期预测."""
    agent = _get_numerical_agent()
    metrics = _req_to_metrics(req)
    model = agent.model_numerical(req.game_id, metrics)
    return model.to_dict()


@app.post("/api/numerical/retention")
async def model_retention(req: NumericalMetricsRequest) -> dict:
    """留存曲线建模 — D1/D7/D30 拟合与预测."""
    agent = _get_numerical_agent()
    metrics = _req_to_metrics(req)
    curve = agent.model_retention(req.game_id, metrics)
    return curve.to_dict()


@app.post("/api/numerical/pay-conversion")
async def analyze_pay_conversion(req: NumericalMetricsRequest) -> dict:
    """付费转化漏斗分析."""
    agent = _get_numerical_agent()
    metrics = _req_to_metrics(req)
    funnel = agent.analyze_pay_conversion(req.game_id, metrics)
    return funnel.to_dict()


@app.post("/api/numerical/tuning")
async def recommend_tuning(req: NumericalMetricsRequest) -> dict:
    """数值调优建议 — 基于 KPI 偏差."""
    agent = _get_numerical_agent()
    metrics = _req_to_metrics(req)
    recs = agent.recommend_tuning(req.game_id, metrics)
    return {
        "game_id": req.game_id,
        "recommendation_count": len(recs),
        "high_priority_count": sum(1 for r in recs if r.priority == "HIGH"),
        "recommendations": [r.to_dict() for r in recs],
    }


@app.post("/api/numerical/ab-test")
async def design_ab_test(req: ABTestRequest) -> dict:
    """A/B 测试方案设计."""
    agent = _get_numerical_agent()
    metrics = _req_to_metrics(req)
    test = agent.design_ab_test(req.game_id, req.hypothesis, metrics, req.target_metric)
    return test.to_dict()


@app.post("/api/numerical/inflation")
async def monitor_inflation(game_id: str) -> dict:
    """通胀监控 — 货币产出/消耗监控."""
    agent = _get_numerical_agent()
    report = agent.monitor_inflation(game_id)
    return report.to_dict()


@app.post("/api/numerical/report")
async def create_numerical_report(req: NumericalMetricsRequest) -> dict:
    """完整数值报告（聚合所有数值产物）."""
    agent = _get_numerical_agent()
    metrics = _req_to_metrics(req)
    report = agent.create_numerical_report(req.game_id, metrics)
    return report.to_dict()


@app.get("/api/numerical/reports")
async def list_numerical_reports(limit: int = 50) -> list[dict]:
    """数值报告列表."""
    return _get_numerical_agent().list_numerical_reports(limit=limit)


@app.get("/api/numerical/reports/{report_id}")
async def get_numerical_report(report_id: str) -> dict:
    """数值报告详情."""
    report = _get_numerical_agent().get_numerical_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Numerical report {report_id} not found")
    return report


@app.get("/api/numerical/stats")
async def get_numerical_stats() -> dict:
    """数值统计概览."""
    return _get_numerical_agent().get_stats()


# ── Data Analyst Agent: 玩家行为分析/漏斗/BI 报表 ─────────


def _get_data_analyst_agent() -> "DataAnalystAgent":
    if not hasattr(_get_data_analyst_agent, "_instance"):
        from .data_analyst_agent import DataAnalystAgent
        bus = _get_shared_message_bus()
        registry = getattr(_get_shared_message_bus, "_registry", None)
        identity = None
        if registry is not None:
            try:
                from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                    AgentRole,
                )
                records = registry.find_by_role(AgentRole.DATA_ANALYST)
                identity = records[0].identity if records else None
            except Exception:
                pass
        _get_data_analyst_agent._instance = DataAnalystAgent(
            data_dir=str(_PROJECT_ROOT / "data"),
            message_bus=bus,
            agent_identity=identity,
        )
    return _get_data_analyst_agent._instance


class BehaviorDataRequest(BaseModel):
    """行为数据请求体."""

    game_id: str
    genre: str = "Merge"
    dau: int = 10000
    mau: int = 80000
    new_users_today: int = 800
    avg_session_duration: float = 420.0
    avg_sessions_per_user: float = 4.0
    retention_d1: float = 0.42
    retention_d7: float = 0.18
    retention_d30: float = 0.10
    revenue_total: float = 5000.0
    payer_count: int = 600


def _req_to_behavior_data(req: "BehaviorDataRequest") -> "BehaviorData":
    from .data_analyst_agent import BehaviorData
    return BehaviorData(
        game_id=req.game_id,
        genre=req.genre,
        dau=req.dau,
        mau=req.mau,
        new_users_today=req.new_users_today,
        avg_session_duration=req.avg_session_duration,
        avg_sessions_per_user=req.avg_sessions_per_user,
        retention_d1=req.retention_d1,
        retention_d7=req.retention_d7,
        retention_d30=req.retention_d30,
        revenue_total=req.revenue_total,
        payer_count=req.payer_count,
    )


@app.post("/api/data-analyst/behavior")
async def analyze_behavior(req: BehaviorDataRequest) -> dict:
    """玩家行为分析 — 活跃/会话/参与度."""
    agent = _get_data_analyst_agent()
    data = _req_to_behavior_data(req)
    report = agent.analyze_behavior(req.game_id, data)
    return report.to_dict()


@app.post("/api/data-analyst/funnel")
async def analyze_funnel(req: BehaviorDataRequest) -> dict:
    """漏斗归因分析 — 识别转化瓶颈."""
    agent = _get_data_analyst_agent()
    data = _req_to_behavior_data(req)
    funnel = agent.analyze_funnel(req.game_id, data)
    return funnel.to_dict()


@app.post("/api/data-analyst/retention-predict")
async def predict_retention(req: BehaviorDataRequest) -> dict:
    """留存预测 — 基于历史数据预测未来留存."""
    agent = _get_data_analyst_agent()
    data = _req_to_behavior_data(req)
    prediction = agent.predict_retention(req.game_id, data)
    return prediction.to_dict()


@app.post("/api/data-analyst/segmentation")
async def segment_players(req: BehaviorDataRequest) -> dict:
    """玩家分群 — RFM 分群."""
    agent = _get_data_analyst_agent()
    data = _req_to_behavior_data(req)
    segmentation = agent.segment_players(req.game_id, data)
    return segmentation.to_dict()


@app.post("/api/data-analyst/bi-report")
async def generate_bi_report(req: BehaviorDataRequest) -> dict:
    """生成 BI 报表."""
    agent = _get_data_analyst_agent()
    data = _req_to_behavior_data(req)
    report = agent.generate_bi_report(req.game_id, data)
    return report.to_dict()


@app.post("/api/data-analyst/anomalies")
async def detect_anomalies(req: BehaviorDataRequest) -> dict:
    """异常检测 — 指标异常波动."""
    agent = _get_data_analyst_agent()
    data = _req_to_behavior_data(req)
    alerts = agent.detect_anomalies(req.game_id, data)
    return {"game_id": req.game_id, "alert_count": len(alerts),
            "alerts": [a.to_dict() for a in alerts]}


@app.get("/api/data-analyst/bi-reports")
async def list_bi_reports(limit: int = 50) -> list[dict]:
    """BI 报表列表."""
    return _get_data_analyst_agent().list_bi_reports(limit=limit)


@app.get("/api/data-analyst/bi-reports/{report_id}")
async def get_bi_report(report_id: str) -> dict:
    """BI 报表详情."""
    report = _get_data_analyst_agent().get_bi_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"BI report {report_id} not found")
    return report


@app.get("/api/data-analyst/stats")
async def get_data_analyst_stats() -> dict:
    """数据分析统计概览."""
    return _get_data_analyst_agent().get_stats()


# ── Player Support Agent: 工单/FAQ/舆情/VIP ───────────────


def _get_player_support_agent() -> "PlayerSupportAgent":
    if not hasattr(_get_player_support_agent, "_instance"):
        from .player_support_agent import PlayerSupportAgent
        _get_player_support_agent._instance = PlayerSupportAgent(
            data_dir=str(_PROJECT_ROOT / "data"),
        )
    return _get_player_support_agent._instance


class TicketRequest(BaseModel):
    """工单请求体."""

    game_id: str
    player_id: str
    category: str = "other"        # payment/bug/account/gameplay/other
    subject: str
    description: str
    priority: str = "medium"       # low/medium/high/critical


class FAQRequest(BaseModel):
    """FAQ 管理请求体."""

    game_id: str
    action: str = "list"           # list/create/update/search
    question: str = ""
    answer: str = ""
    category: str = "other"
    faq_id: str = ""


class SentimentRequest(BaseModel):
    """舆情监控请求体."""

    game_id: str
    total_tickets: int = 120
    avg_rating: float = 4.2
    total_reviews: int = 8500
    positive_reviews: int = 6120
    negative_reviews: int = 1530
    neutral_reviews: int = 850
    vip_players: int = 45
    csat_score: float = 82.0
    nps_responses: int = 320
    promoters: int = 180
    passives: int = 90
    detractors: int = 50


class VIPRequest(BaseModel):
    """VIP 服务请求体."""

    game_id: str
    player_id: str
    vip_level: str = "gold"        # gold/platinum/diamond
    request: str


class SatisfactionRequest(BaseModel):
    """满意度分析请求体."""

    game_id: str
    csat_score: float = 82.0
    nps_responses: int = 320
    promoters: int = 180
    passives: int = 90
    detractors: int = 50


def _req_to_feedback(req: "SentimentRequest | SatisfactionRequest", game_id: str) -> "PlayerFeedback":
    from .player_support_agent import PlayerFeedback
    return PlayerFeedback(
        game_id=game_id,
        csat_score=getattr(req, "csat_score", 82.0),
        nps_responses=getattr(req, "nps_responses", 320),
        promoters=getattr(req, "promoters", 180),
        passives=getattr(req, "passives", 90),
        detractors=getattr(req, "detractors", 50),
        avg_rating=getattr(req, "avg_rating", 4.2) if hasattr(req, "avg_rating") else 4.2,
        total_reviews=getattr(req, "total_reviews", 8500) if hasattr(req, "total_reviews") else 8500,
        positive_reviews=getattr(req, "positive_reviews", 6120) if hasattr(req, "positive_reviews") else 6120,
        negative_reviews=getattr(req, "negative_reviews", 1530) if hasattr(req, "negative_reviews") else 1530,
        neutral_reviews=getattr(req, "neutral_reviews", 850) if hasattr(req, "neutral_reviews") else 850,
    )


@app.post("/api/player-support/ticket")
async def process_ticket(req: TicketRequest) -> dict:
    """工单处理 — 自动分类/路由/回复."""
    agent = _get_player_support_agent()
    ticket = agent.process_ticket(
        req.game_id, req.player_id, req.category,
        req.subject, req.description, req.priority
    )
    return ticket.to_dict()


@app.post("/api/player-support/faq")
async def manage_faq(req: FAQRequest) -> dict:
    """FAQ 知识库管理."""
    agent = _get_player_support_agent()
    return agent.manage_faq(
        req.game_id, req.action, req.question, req.answer, req.category, req.faq_id
    )


@app.post("/api/player-support/sentiment")
async def monitor_sentiment(req: SentimentRequest) -> dict:
    """舆情监控 — 评分/评论/社媒情绪."""
    agent = _get_player_support_agent()
    feedback = _req_to_feedback(req, req.game_id)
    report = agent.monitor_sentiment(req.game_id, feedback)
    return report.to_dict()


@app.post("/api/player-support/vip")
async def serve_vip(req: VIPRequest) -> dict:
    """VIP 服务."""
    agent = _get_player_support_agent()
    record = agent.serve_vip(req.game_id, req.player_id, req.vip_level, req.request)
    return record.to_dict()


@app.post("/api/player-support/satisfaction")
async def analyze_satisfaction(req: SatisfactionRequest) -> dict:
    """满意度分析 — CSAT/NPS."""
    agent = _get_player_support_agent()
    feedback = _req_to_feedback(req, req.game_id)
    report = agent.analyze_satisfaction(req.game_id, feedback)
    return report.to_dict()


@app.get("/api/player-support/tickets")
async def list_tickets(limit: int = 50) -> list[dict]:
    """工单列表."""
    return _get_player_support_agent().list_tickets(limit=limit)


@app.get("/api/player-support/stats")
async def get_player_support_stats() -> dict:
    """玩家服务统计概览."""
    return _get_player_support_agent().get_stats()


# ── 跨 Agent 协同: Data Analyst → Numerical Designer 分析闭环 ───


class AnalysisClosedLoopRequest(BaseModel):
    """分析闭环请求体 — Data Analyst 行为数据触发 Numerical Designer 建模."""

    game_id: str
    genre: str = "Merge"
    dau: int = 10000
    mau: int = 80000
    revenue_total: float = 5000.0
    payer_count: int = 600
    retention_d1: float = 0.42
    retention_d7: float = 0.18
    retention_d30: float = 0.10
    anomalies: list[dict[str, Any]] = []


@app.post("/api/collaboration/analysis-loop")
async def trigger_analysis_closed_loop(req: AnalysisClosedLoopRequest) -> dict:
    """触发完整分析闭环: Data Analyst → Numerical Designer.

    4 步协同链路:
      1. behavior_analyzed → model_numerical (LTV/CAC 建模)
      2. retention_predicted → model_retention (留存曲线建模)
      3. players_segmented → analyze_pay_conversion (付费转化分析)
      4. anomalies_detected → recommend_tuning (+design_ab_test if critical)
    """
    bridge = _get_data_numerical_bridge()
    behavior_data = {
        "genre": req.genre,
        "dau": req.dau,
        "mau": req.mau,
        "revenue_total": req.revenue_total,
        "payer_count": req.payer_count,
        "retention_d1": req.retention_d1,
        "retention_d7": req.retention_d7,
        "retention_d30": req.retention_d30,
        "anomalies": req.anomalies,
    }
    result = bridge.run_analysis_closed_loop(req.game_id, behavior_data)
    return result


@app.get("/api/collaboration/data-numerical")
async def list_data_numerical_collaborations(
    game_id: str = "", limit: int = 50
) -> list[dict]:
    """查询 Data Analyst → Numerical Designer 协同记录列表."""
    bridge = _get_data_numerical_bridge()
    return bridge.list_collaborations(
        game_id=game_id or None, limit=limit
    )


@app.get("/api/collaboration/data-numerical/stats")
async def get_data_numerical_collaboration_stats() -> dict:
    """协同统计概览."""
    bridge = _get_data_numerical_bridge()
    return bridge.get_stats()


@app.get("/api/collaboration/data-numerical/{collaboration_id}")
async def get_data_numerical_collaboration(collaboration_id: str) -> dict:
    """查询单条协同记录详情."""
    bridge = _get_data_numerical_bridge()
    record = bridge.get_collaboration(collaboration_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Collaboration {collaboration_id} not found",
        )
    return record


# ── 协同层: Numerical Designer → Data Analyst 反向闭环 (M3.1) ──


@app.post("/api/collaboration/reverse-loop")
async def trigger_reverse_analysis_loop(req: dict) -> dict:
    """Numerical Designer → Data Analyst 反向分析闭环.

    流程: 调优建议 → 异常检测 → 留存预测 → 行为基线
    (3 步反向协同, 验证调优效果)

    Request body:
        game_id: 游戏 ID
        tuning_payload: 调优建议 (含 target_metric, parameter, adjustment_pct 等)
    """
    game_id = req.get("game_id", "unknown")
    tuning_payload = req.get("tuning_payload", req)  # 允许扁平化传入
    bridge = _get_numerical_data_bridge()
    result = bridge.run_reverse_closed_loop(game_id, tuning_payload)
    return result


@app.get("/api/collaboration/numerical-data")
async def list_numerical_data_collaborations(
    game_id: str | None = None, limit: int = 50
) -> list[dict]:
    """反向协同记录列表 (Numerical → Data Analyst)."""
    bridge = _get_numerical_data_bridge()
    return bridge.list_collaborations(game_id=game_id, limit=limit)


@app.get("/api/collaboration/numerical-data/stats")
async def get_numerical_data_collaboration_stats() -> dict:
    """反向协同统计."""
    bridge = _get_numerical_data_bridge()
    return bridge.get_stats()


@app.get("/api/collaboration/numerical-data/{collaboration_id}")
async def get_numerical_data_collaboration(collaboration_id: str) -> dict:
    """查询单条反向协同记录详情."""
    bridge = _get_numerical_data_bridge()
    record = bridge.get_collaboration(collaboration_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Reverse collaboration {collaboration_id} not found",
        )
    return record


# ── 执行层: CEO 每日例会 (DailyOperatorPipeline HTTP 暴露) ───


class CEODailyRunRequest(BaseModel):
    """CEO 每日例会请求体."""
    business_date: str = ""        # 默认今天
    force: bool = False            # 越过幂等门重跑
    use_real_data: bool = False    # 生产模式（四真实源），默认 demo


@app.post("/api/ceo/daily-run")
async def trigger_ceo_daily_run(req: CEODailyRunRequest) -> dict:
    """触发 CEO 每日例会（DailyOperatorPipeline 13 阶段全公司经营闭环）.

    模式:
      1. demo (默认): 确定性 SIM 舰队，离线可跑，不依赖真实 API
      2. prod (use_real_data=true): GameRegistry + 四真实源（仍 DRY_RUN）

    幂等: 同日已跑过返回 SKIPPED，force=true 可重跑.

    Returns:
        OperatorRunResult 摘要（含 13 阶段结果、决策/执行统计）.
    """
    import sys
    from datetime import date as _date

    # 确保 scripts 和 src 在 path 中
    scripts_dir = str(_PROJECT_ROOT / "scripts")
    src_dir = str(_PROJECT_ROOT / "src")
    for d in [scripts_dir, src_dir]:
        if d not in sys.path:
            sys.path.insert(0, d)

    business_date = req.business_date or _date.today().isoformat()

    try:
        from src.operator import build_growth_operator
        from src.operator.state import OperatorRunStore
        from src.ceo_intelligence.daily_operator.memory import JsonlOperatorMemory
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"DailyOperator modules not available: {exc}",
        ) from exc

    start_time = time.time()

    try:
        # 跨 Agent 协同：注入 LiveOpsAgent 到 CEO Daily Run
        liveops_agent = _get_liveops_agent()

        if req.use_real_data:
            # 生产模式：GameRegistry + 四真实源
            from scripts.run_daily_operator import build_prod_scheduler
            scheduler = build_prod_scheduler(business_date)
        else:
            # demo 模式：确定性 SIM 舰队
            from scripts.run_daily_operator import build_demo_scheduler
            scheduler = build_demo_scheduler(business_date)

        # 注入 LiveOpsAgent (跨 Agent 协同: CEO → LiveOps)
        if liveops_agent is not None and hasattr(scheduler, "pipeline") and hasattr(scheduler.pipeline, "ctx"):
            scheduler.pipeline.ctx.liveops_agent = liveops_agent

        result = scheduler.run_daily_cycle(business_date, force=req.force)
        duration = round(time.time() - start_time, 2)

        result_dict = result.to_dict()
        result_dict["duration_seconds"] = duration

        if result.real_api_called:
            logger.warning(
                "CEO daily-run %s: real_api_called=True (should be False in DRY_RUN)",
                business_date,
            )

        logger.info(
            "CEO daily-run completed: date=%s status=%s stages=%d duration=%ss",
            business_date,
            result.status.value,
            len(result.stages),
            duration,
        )
        return result_dict

    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        logger.exception("CEO daily-run failed after %ss", duration)
        raise HTTPException(
            status_code=500,
            detail=f"CEO daily-run failed: {exc}",
        ) from exc


# ── 执行层: 触发 GrowthLoop Cycle ────────────────────────────


class LoopTriggerRequest(BaseModel):
    """触发 GrowthLoop 请求体."""
    dry_run: bool = True
    days: int = 7
    fetch_meta_ads: bool = False  # 是否拉取真实 Meta Ads 数据


@app.post("/api/loop/trigger")
async def trigger_growth_loop(req: LoopTriggerRequest) -> dict:
    """触发一次 GrowthLoop cycle.

    模式:
      1. 轻量触发 (默认): dry_run=true, fetch_meta_ads=false
         不调真实 Meta API, 只执行 Phase A (到期评估)
      2. 真实数据触发: fetch_meta_ads=true
         拉取 Meta Ads 数据, 生成 signals, 执行完整 Phase A+B+C
         (需要 META_ACCESS_TOKEN 和 META_AD_ACCOUNT_ID)
      3. Live 执行: dry_run=false + fetch_meta_ads=true
         拉取真实数据 + 真实执行动作 (调用 Meta Ads API 写操作)

    Returns:
        cycle 执行结果摘要.
    """
    import sys

    # 确保 scripts 目录在 path 中
    scripts_dir = str(_PROJECT_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    try:
        from scripts.growth_loop_orchestrator import GrowthLoopOrchestrator
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"GrowthLoopOrchestrator not available: {exc}",
        ) from exc

    # 可选: 拉取真实 Meta Ads 数据
    meta_data_info: dict = {}
    loop_input = None

    if req.fetch_meta_ads:
        from .meta_ads_fetcher import MetaAdsDataFetcher

        fetcher = MetaAdsDataFetcher()
        if not fetcher.is_configured():
            raise HTTPException(
                status_code=400,
                detail="fetch_meta_ads=true 但 META_ACCESS_TOKEN 或 META_AD_ACCOUNT_ID 未配置",
            )
        loop_input = fetcher.fetch(days=req.days)

        if loop_input.fetch_error:
            meta_data_info = {
                "fetch_error": loop_input.fetch_error,
                "creatives_fetched": 0,
                "signals_generated": 0,
            }
            logger.warning("Meta Ads fetch failed: %s", loop_input.fetch_error)
        else:
            meta_data_info = {
                "creatives_fetched": loop_input.creative_count,
                "signals_generated": len(loop_input.signals),
                "predictions_generated": loop_input.prediction_count,
            }
            logger.info("Meta Ads data fetched: %d creatives, %d signals",
                        loop_input.creative_count, len(loop_input.signals))

    try:
        # 构建 Orchestrator
        kwargs: dict = {
            "data_dir": str(_PROJECT_ROOT / "data" / "growth_loop"),
            "dry_run": req.dry_run,
        }

        # 注入真实数据和 RealityGate
        if loop_input and not loop_input.fetch_error:
            if loop_input.reality_scores:
                kwargs["reality_scores"] = loop_input.reality_scores
            if loop_input.game_id_resolver:
                kwargs["game_id_resolver"] = loop_input.game_id_resolver

        # Live 模式注入 MetaAdsPlatformAdapter
        if not req.dry_run and loop_input and not loop_input.fetch_error:
            try:
                from scripts.meta_ads_adapter import MetaAdsPlatformAdapter
                from market_ops.execution_runtime.adapters.facebook import FacebookClient
                client = FacebookClient()
                kwargs["adapter"] = MetaAdsPlatformAdapter(client)
                logger.info("Injected MetaAdsPlatformAdapter (live mode)")
            except Exception as exc:
                logger.warning("Failed to create MetaAdsPlatformAdapter: %s", exc)

        orchestrator = GrowthLoopOrchestrator(**kwargs)
        start_time = time.time()

        # 构造 run_cycle 参数
        cycle_kwargs: dict = {}
        if loop_input and not loop_input.fetch_error:
            cycle_kwargs["signals"] = loop_input.signals if loop_input.signals else None
            cycle_kwargs["current_metrics"] = loop_input.current_metrics
            cycle_kwargs["previous_metrics"] = loop_input.previous_metrics
            cycle_kwargs["creative_to_adset_map"] = loop_input.creative_to_adset_map
            cycle_kwargs["current_budgets"] = loop_input.current_budgets

            # post_metrics_provider: 从 current_metrics 中取对应 creative 的指标
            def post_metrics_provider(pending: Any) -> dict[str, float]:
                cid = getattr(pending, "creative_id", "")
                return loop_input.current_metrics.get(cid, {})

            cycle_kwargs["post_metrics_provider"] = post_metrics_provider

        result = orchestrator.run_cycle(**cycle_kwargs)
        duration = round(time.time() - start_time, 2)

        # CycleResult 转 dict
        actions = getattr(result, "actions", [])
        execution_results = getattr(result, "execution_results", [])
        success_count = sum(
            1 for e in execution_results
            if isinstance(e, dict) and e.get("success")
            or (not isinstance(e, dict) and getattr(e, "success", False))
        )

        response = {
            "status": "completed",
            "cycle_number": getattr(result, "cycle_number", 0),
            "dry_run": req.dry_run,
            "fetch_meta_ads": req.fetch_meta_ads,
            "duration_seconds": duration,
            "actions_planned": len(actions),
            "actions_executed": len(execution_results),
            "actions_succeeded": success_count,
            "success_rate": round(success_count / max(len(execution_results), 1), 2),
            "evaluated_count": getattr(result, "evaluated_count", 0),
            "pending_created": getattr(result, "pending_created", 0),
            "message": f"Cycle #{getattr(result, 'cycle_number', 0)} 完成, "
                       f"规划 {len(actions)} 个动作, 执行 {len(execution_results)} 个",
        }

        # 附加 Meta Ads 数据信息
        if meta_data_info:
            response["meta_ads_data"] = meta_data_info

        # 附加 RealityScore (如果拉取了真实数据)
        if loop_input and not loop_input.fetch_error and loop_input.reality_scores:
            response["reality_scores"] = [
                {
                    "game_id": gid,
                    "composite": getattr(score, "composite", 0.0),
                    "decision_level": getattr(score, "decision_level", ""),
                    "coverage": getattr(score, "coverage", 0.0),
                    "freshness": getattr(score, "freshness", 0.0),
                    "consistency": getattr(score, "consistency", 0.0),
                }
                for gid, score in loop_input.reality_scores.items()
            ]

        # 附加诊断摘要 (取首个诊断作为代表)
        diagnosis = getattr(result, "diagnosis", None)
        if diagnosis and isinstance(diagnosis, dict):
            response["diagnosis_summary"] = {
                "root_cause": diagnosis.get("root_cause", ""),
                "confidence": diagnosis.get("confidence", 0.0),
                "creative_id": diagnosis.get("creative_id", ""),
                "evidence": diagnosis.get("evidence", [])[:3],
            }

        # 附加策略摘要 (取首个策略作为代表)
        strategy = getattr(result, "strategy", None)
        if strategy and isinstance(strategy, dict):
            response["strategy_summary"] = {
                "strategy_type": strategy.get("strategy_type", ""),
                "intensity": strategy.get("intensity", 0.0),
                "target_creative_id": strategy.get("target_creative_id", ""),
                "time_horizon_days": strategy.get("time_horizon_days", 0),
            }

        # 附加动作详情 (含完整链路信息)
        if actions:
            response["action_details"] = [
                {
                    "action_id": getattr(a, "action_id", ""),
                    "action_type": str(getattr(a, "action_type", "")),
                    "creative_id": getattr(a, "creative_id", ""),
                    "adset_id": getattr(a, "adset_id", ""),
                    "risk_level": getattr(a, "risk_level", ""),
                    "approval_level": getattr(a, "approval_level", 0),
                    "confidence": getattr(a, "confidence", 0.0),
                    "budget_impact": getattr(a, "budget_impact", 0.0),
                    "status": getattr(a, "status", ""),
                    "reason": getattr(a, "reason", ""),
                }
                for a in actions[:10]  # 最多返回 10 个
            ]

        return response
    except Exception as exc:
        logger.exception("GrowthLoop trigger failed")
        raise HTTPException(
            status_code=500,
            detail=f"GrowthLoop cycle failed: {exc}",
        ) from exc


# ── 执行层: SSE 实时事件推送 ─────────────────────────────────


def _collect_sse_events(limit: int = 20) -> list[dict[str, Any]]:
    """收集多事件源, 合并为统一事件列表 (按时间倒序).

    事件源:
      1. WorkspaceEvent (provider.get_events) — 基础事件流
      2. DataNumericalBridge 协同记录 — 跨 Agent 协同事件
      3. CEO Memory 最近记录 — 执行记忆回流

    每条事件统一格式:
      {
        "id": str, "timestamp": str, "source": str,
        "agent_id": str, "agent_name": str, "event_type": str,
        "message": str, "game_id": str, "game_name": str,
        "data": dict (原始记录)
      }
    """
    events: list[dict[str, Any]] = []

    # 1. 基础事件流
    try:
        workspace_events = get_aggregator().provider.get_events(limit=limit)
        for ev in workspace_events:
            d = ev.to_dict()
            events.append({
                "id": d["id"],
                "timestamp": d["timestamp"],
                "source": "workspace",
                "agent_id": d.get("agent_id", ""),
                "agent_name": d.get("agent_name", ""),
                "event_type": d.get("event_type", "info"),
                "message": d.get("message", ""),
                "game_id": d.get("game_id", ""),
                "game_name": d.get("game_name", ""),
                "data": d,
            })
    except Exception:
        pass

    # 2. 跨 Agent 协同记录
    try:
        bridge = _get_data_numerical_bridge()
        collabs = bridge.list_collaborations(limit=limit)
        for rec in collabs:
            events.append({
                "id": rec.get("collaboration_id", ""),
                "timestamp": rec.get("created_at", ""),
                "source": "collaboration",
                "agent_id": "data_numerical_bridge",
                "agent_name": "Data→Numerical Bridge",
                "event_type": "success" if rec.get("status") == "success" else "warning",
                "message": f"协同: {rec.get('trigger_event', '')} → {rec.get('target_method', '')} ({rec.get('game_id', '')})",
                "game_id": rec.get("game_id", ""),
                "game_name": "",
                "data": rec,
            })
    except Exception:
        pass

    # 3. CEO Memory 最近记录
    try:
        ceo_records = _read_jsonl_tail(_EXECUTION_MEMORY, limit)
        for rec in ceo_records:
            domain = rec.get("domain", "unknown")
            action = rec.get("action_type", "")
            events.append({
                "id": rec.get("execution_id", ""),
                "timestamp": rec.get("created_at", ""),
                "source": "ceo_memory",
                "agent_id": rec.get("agent_id", domain),
                "agent_name": domain.replace("_", " ").title(),
                "event_type": "success" if rec.get("success") else "error",
                "message": f"[{domain}] {action}",
                "game_id": rec.get("game_id", ""),
                "game_name": "",
                "data": rec,
            })
    except Exception:
        pass

    # 按时间倒序排序 (兼容 ISO 字符串比较)
    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return events[:limit]


@app.get("/api/events/stream")
async def event_stream(limit: int = 20) -> StreamingResponse:
    """SSE 实时事件流 — 多事件源轮询, 推送新事件.

    事件源:
      1. WorkspaceEvent (基础事件流)
      2. DataNumericalBridge 协同记录 (跨 Agent 协同)
      3. CEO Memory 执行记忆 (回流审计)

    SSE 消息格式:
      id: <event_id>
      event: <source>
      data: {json}

    心跳: 每 15 秒发送 `: ping` 注释行, 防止代理超时.
    轮询间隔: 3 秒.
    """
    async def generate() -> str:
        seen_ids: set[str] = set()
        tick = 0
        while True:
            events = _collect_sse_events(limit=limit)
            for ev in events:
                eid = ev.get("id", "")
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    # 限制 seen_ids 大小防止内存泄漏
                    if len(seen_ids) > 500:
                        seen_ids = set(list(seen_ids)[-250:])
                    payload = json.dumps(ev, ensure_ascii=False)
                    yield f"id: {eid}\nevent: {ev['source']}\ndata: {payload}\n\n"

            # 每 15 秒发送心跳 (5 个 tick × 3 秒)
            tick += 1
            if tick % 5 == 0:
                yield ": ping\n\n"

            await asyncio.sleep(3)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── LiveOps Agent: 流失分析 + 回流活动 ───────────────────────


def _get_shared_message_bus():
    """获取共享 MessageBus 单例 — LiveOps ↔ Growth 跨 Agent 通信.

    懒加载: 首次调用时创建, 同时初始化 ChurnAlertBridge 并注册.
    """
    if not hasattr(_get_shared_message_bus, "_instance"):
        try:
            from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                MessageBus,
                create_default_organization,
                create_agent_registry,
            )
            bus = MessageBus()
            # 创建默认组织 (含 LiveOps identity)
            registry = create_agent_registry()
            create_default_organization(registry)
            _get_shared_message_bus._instance = bus
            _get_shared_message_bus._registry = registry
            # 初始化 ChurnAlertBridge 并注册到 bus
            _get_churn_alert_bridge(bus, registry)
        except ImportError:
            _get_shared_message_bus._instance = None
            _get_shared_message_bus._registry = None
    return _get_shared_message_bus._instance


def _get_liveops_identity(registry):
    """从注册中心获取 LiveOps Agent identity."""
    if registry is None:
        return None
    try:
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            AgentRole,
        )
        records = registry.find_by_role(AgentRole.LIVEOPS)
        return records[0].identity if records else None
    except Exception:
        return None


def _get_liveops_agent():
    """获取 LiveOpsAgent 单例 (注入共享 MessageBus + identity)."""
    from .liveops_agent import LiveOpsAgent
    bus = _get_shared_message_bus()
    registry = getattr(_get_shared_message_bus, "_registry", None)
    identity = _get_liveops_identity(registry)
    return LiveOpsAgent(
        data_dir=str(_PROJECT_ROOT / "data"),
        message_bus=bus,
        agent_identity=identity,
    )


def _get_churn_alert_bridge(bus=None, registry=None):
    """获取 ChurnAlertBridge 单例 — LiveOps → Growth 桥接.

    首次调用时创建并注册到 MessageBus.
    """
    if not hasattr(_get_churn_alert_bridge, "_instance"):
        if bus is None:
            bus = _get_shared_message_bus()
        if registry is None:
            registry = getattr(_get_shared_message_bus, "_registry", None)
        # 获取 UA Agent identity 作为 Growth 侧接收方
        ua_identity = None
        if registry is not None:
            try:
                from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                    AgentRole,
                )
                records = registry.find_by_role(AgentRole.UA)
                ua_identity = records[0].identity if records else None
            except Exception:
                pass
        from .churn_alert_bridge import ChurnAlertBridge
        bridge = ChurnAlertBridge(
            data_dir=str(_PROJECT_ROOT / "data"),
            message_bus=bus,
            agent_identity=ua_identity,
        )
        bridge.register()
        _get_churn_alert_bridge._instance = bridge
    return _get_churn_alert_bridge._instance


def _get_data_numerical_bridge():
    """获取 DataNumericalBridge 单例 — Data Analyst → Numerical Designer 桥接.

    首次调用时创建并注册到 MessageBus.
    """
    if not hasattr(_get_data_numerical_bridge, "_instance"):
        bus = _get_shared_message_bus()
        registry = getattr(_get_shared_message_bus, "_registry", None)
        numerical_identity = None
        if registry is not None:
            try:
                from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                    AgentRole,
                )
                records = registry.find_by_role(AgentRole.NUMERICAL)
                numerical_identity = records[0].identity if records else None
            except Exception:
                pass
        from .data_numerical_bridge import DataNumericalBridge
        bridge = DataNumericalBridge(
            data_dir=str(_PROJECT_ROOT / "data"),
            message_bus=bus,
            agent_identity=numerical_identity,
            numerical_agent=_get_numerical_agent(),
        )
        bridge.register()
        _get_data_numerical_bridge._instance = bridge
    return _get_data_numerical_bridge._instance


def _get_numerical_data_bridge():
    """获取 NumericalDataBridge 单例 — Numerical Designer → Data Analyst 反向桥接.

    首次调用时创建并注册到 MessageBus.
    """
    if not hasattr(_get_numerical_data_bridge, "_instance"):
        bus = _get_shared_message_bus()
        registry = getattr(_get_shared_message_bus, "_registry", None)
        data_analyst_identity = None
        if registry is not None:
            try:
                from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                    AgentRole,
                )
                records = registry.find_by_role(AgentRole.DATA_ANALYST)
                data_analyst_identity = records[0].identity if records else None
            except Exception:
                pass
        from .numerical_data_bridge import NumericalDataBridge
        bridge = NumericalDataBridge(
            data_dir=str(_PROJECT_ROOT / "data"),
            message_bus=bus,
            agent_identity=data_analyst_identity,
            data_analyst_agent=_get_data_analyst_agent(),
        )
        bridge.register()
        _get_numerical_data_bridge._instance = bridge
    return _get_numerical_data_bridge._instance


class WinbackCampaignRequest(BaseModel):
    """设计回流活动请求体."""

    game_id: str
    # 可选: 直接传入流失分析结果; 不传则自动调用 analyze_churn_risk
    analysis: dict | None = None


@app.get("/api/liveops/churn-analysis/{game_id}")
async def get_churn_analysis(game_id: str) -> dict:
    """获取指定游戏的流失风险分析.

    复用 player_monetization 的 LifecycleDetector/PlayerSegmenter,
    返回 ChurnAnalysis (分群分布、生命周期阶段、高价值流失用户数).
    """
    agent = _get_liveops_agent()
    try:
        analysis = agent.analyze_churn_risk(game_id)
        return analysis.to_dict()
    except Exception as exc:
        logger.exception("LiveOps churn-analysis failed for %s", game_id)
        raise HTTPException(
            status_code=500,
            detail=f"Churn analysis failed: {exc}",
        ) from exc


@app.post("/api/liveops/winback-campaign")
async def design_winback_campaign(req: WinbackCampaignRequest) -> dict:
    """基于流失分析设计回流活动方案 (默认 dry_run, 只生成不执行).

    若请求体带 analysis, 则直接使用; 否则自动调用 analyze_churn_risk.
    根据流失分群自动选择活动类型:
      - lapsed → push_re-engagement
      - churning → special_offer
      - at_risk_churn → login_bonus
    """
    agent = _get_liveops_agent()
    try:
        if req.analysis is not None:
            from .liveops_agent import ChurnAnalysis
            analysis = ChurnAnalysis(
                game_id=req.analysis.get("game_id", req.game_id),
                analysis_date=req.analysis.get("analysis_date", ""),
                total_players=int(req.analysis.get("total_players", 0)),
                at_risk_count=int(req.analysis.get("at_risk_count", 0)),
                lapsed_count=int(req.analysis.get("lapsed_count", 0)),
                churning_count=int(req.analysis.get("churning_count", 0)),
                avg_churn_risk=float(req.analysis.get("avg_churn_risk", 0.0)),
                segments=req.analysis.get("segments", {}) or {},
                lifecycle_stages=req.analysis.get("lifecycle_stages", {}) or {},
                high_value_at_risk=int(req.analysis.get("high_value_at_risk", 0)),
            )
        else:
            analysis = agent.analyze_churn_risk(req.game_id)

        campaign = agent.design_winback_campaign(req.game_id, analysis)
        return campaign.to_dict()
    except Exception as exc:
        logger.exception("LiveOps winback-campaign design failed for %s", req.game_id)
        raise HTTPException(
            status_code=500,
            detail=f"Winback campaign design failed: {exc}",
        ) from exc


@app.get("/api/liveops/campaigns")
async def list_liveops_campaigns(game_id: str | None = None) -> list[dict]:
    """列出回流活动方案 (可按 game_id 过滤)."""
    agent = _get_liveops_agent()
    return [c.to_dict() for c in agent.list_campaigns(game_id=game_id)]


@app.get("/api/liveops/campaigns/{campaign_id}")
async def get_liveops_campaign(campaign_id: str) -> dict:
    """获取单个回流活动方案详情."""
    agent = _get_liveops_agent()
    campaign = agent.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found",
        )
    return campaign.to_dict()


@app.post("/api/liveops/campaigns/{campaign_id}/evaluate")
async def evaluate_liveops_campaign(campaign_id: str) -> dict:
    """评估回流活动效果 (基于活动方案的确定性估算)."""
    agent = _get_liveops_agent()
    campaign = agent.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found",
        )
    try:
        evaluation = agent.evaluate_campaign(campaign_id)
        result = evaluation.to_dict()
        result["campaign"] = campaign.to_dict()
        return result
    except Exception as exc:
        logger.exception("LiveOps campaign evaluate failed for %s", campaign_id)
        raise HTTPException(
            status_code=500,
            detail=f"Campaign evaluation failed: {exc}",
        ) from exc


# ── LiveOps 活动执行层 API (接入 ApprovalGate + 执行引擎) ────


class CampaignExecuteRequest(BaseModel):
    """活动执行请求体."""

    dry_run: bool = True


class CampaignApprovalRequest(BaseModel):
    """活动审批请求体."""

    approver: str = "workspace_admin"
    reason: str = ""


@app.post("/api/liveops/campaigns/{campaign_id}/execute")
async def execute_liveops_campaign(
    campaign_id: str,
    req: CampaignExecuteRequest,
) -> dict:
    """执行回流活动方案 — 接入 ApprovalGate 与执行引擎.

    根据活动 rewards_pool 和动作类型自动分级:
      - Level 0: 低风险动作 (push/email) + 小额奖励 (<$50) → 自动执行
      - Level 1: 中额奖励 ($50-$500) → dry_run 验证后执行
      - Level 2: 大额奖励 (≥$500) → 阻塞等人工审批

    Args:
        campaign_id: 活动方案 ID
        req.dry_run: True=只生成执行计划不真实下发; False=走完整审批+执行流程
    """
    agent = _get_liveops_agent()
    campaign = agent.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found",
        )
    try:
        result = agent.execute_campaign(campaign_id, dry_run=req.dry_run)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "LiveOps campaign execute failed for %s", campaign_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"Campaign execution failed: {exc}",
        ) from exc


@app.get("/api/liveops/executions")
async def list_liveops_executions(
    campaign_id: str | None = None,
) -> list[dict]:
    """列出活动执行记录 (可按 campaign_id 过滤)."""
    agent = _get_liveops_agent()
    return [r.to_dict() for r in agent.list_executions(campaign_id=campaign_id)]


@app.get("/api/liveops/executions/{execution_id}")
async def get_liveops_execution(execution_id: str) -> dict:
    """查询单个活动执行状态."""
    agent = _get_liveops_agent()
    result = agent.get_execution(execution_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Execution {execution_id} not found",
        )
    return result.to_dict()


@app.get("/api/liveops/pending-approvals")
async def list_liveops_pending_approvals() -> list[dict]:
    """列出待人工审批的活动执行 (Level 2 阻塞)."""
    agent = _get_liveops_agent()
    return [r.to_dict() for r in agent.list_pending_approvals()]


@app.post("/api/liveops/executions/{execution_id}/approve")
async def approve_liveops_execution(
    execution_id: str,
    req: CampaignApprovalRequest,
) -> dict:
    """人工审批通过 — 执行阻塞的活动."""
    agent = _get_liveops_agent()
    result = agent.get_execution(execution_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Execution {execution_id} not found",
        )
    if result.status not in ("blocked", "dry_run", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Execution {execution_id} status is {result.status}, cannot approve",
        )
    try:
        approved = agent.approve_campaign(
            execution_id, approver=req.approver
        )
        return approved.to_dict()
    except Exception as exc:
        logger.exception(
            "LiveOps execution approve failed for %s", execution_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"Approval failed: {exc}",
        ) from exc


@app.post("/api/liveops/executions/{execution_id}/reject")
async def reject_liveops_execution(
    execution_id: str,
    req: CampaignApprovalRequest,
) -> dict:
    """人工审批拒绝."""
    agent = _get_liveops_agent()
    result = agent.get_execution(execution_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Execution {execution_id} not found",
        )
    try:
        rejected = agent.reject_campaign(
            execution_id, approver=req.approver, reason=req.reason
        )
        return rejected.to_dict()
    except Exception as exc:
        logger.exception(
            "LiveOps execution reject failed for %s", execution_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"Rejection failed: {exc}",
        ) from exc


@app.get("/api/liveops/stats")
async def get_liveops_stats(recent_limit: int = 10) -> dict:
    """LiveOps 执行结果统计概览 — Dashboard 回流数据源.

    返回:
      - 执行总数 / 各状态分布 / 成功率
      - 累计下发奖励金额 (仅 live completed)
      - 推送/奖励/邮件送达总数
      - 按游戏分组统计
      - 最近 N 条执行记录摘要
    """
    from .liveops_executor import LiveOpsStatsAggregator
    stats = LiveOpsStatsAggregator(data_dir=str(_PROJECT_ROOT / "data"))
    return stats.aggregate(recent_limit=recent_limit)


@app.get("/api/liveops/cross-agent")
async def get_cross_agent_overview() -> dict:
    """跨 Agent 协同概览 — 可视化数据源.

    返回:
      - agent_topology: Agent 协同拓扑 (CEO ↔ LiveOps ↔ Growth)
      - recent_events: 最近 LiveOps 广播事件 (从 CEO memory 提取)
      - ceo_liveops_stage: CEO Daily Run 最近一次 STAGE_LIVEOPS 阶段结果
      - collaboration_flow: 协同链路图数据 (节点 + 边)
    """
    # 1. Agent 协同拓扑 — 全部 10 个 Agent + 完整协同链路
    topology = {
        "nodes": [
            # 管理层
            {"id": "ceo", "name": "CEO Office", "role": "supervisor", "department": "管理", "color": "#8b5cf6"},
            {"id": "memory", "name": "CEO Memory", "role": "memory", "department": "管理", "color": "#10b981"},
            # 研发部
            {"id": "product", "name": "Product Agent", "role": "product", "department": "研发", "color": "#0ea5e9"},
            {"id": "designer", "name": "Game Designer", "role": "designer", "department": "研发", "color": "#0ea5e9"},
            # 增长部
            {"id": "ua", "name": "Growth Loop", "role": "ua", "department": "增长", "color": "#3b82f6"},
            {"id": "creative", "name": "Creative Agent", "role": "creative", "department": "增长", "color": "#3b82f6"},
            # 运营部
            {"id": "liveops", "name": "LiveOps Agent", "role": "liveops", "department": "运营", "color": "#d946ef"},
            {"id": "numerical", "name": "Numerical Designer", "role": "numerical", "department": "运营", "color": "#d946ef"},
            {"id": "data_analyst", "name": "Data Analyst", "role": "data_analyst", "department": "运营", "color": "#d946ef"},
            {"id": "player_support", "name": "Player Support", "role": "player_support", "department": "运营", "color": "#d946ef"},
        ],
        "edges": [
            # CEO → 各部门 Agent (决策下发)
            {"from": "ceo", "to": "liveops", "label": "STAGE_LIVEOPS", "type": "trigger"},
            {"from": "ceo", "to": "ua", "label": "GrowthLoop 触发", "type": "trigger"},
            {"from": "ceo", "to": "product", "label": "立项指令", "type": "trigger"},
            # 研发链路: Product → Designer
            {"from": "product", "to": "designer", "label": "GDD 传递", "type": "data_flow"},
            # Designer → Numerical (设计数值 → 运营建模)
            {"from": "designer", "to": "numerical", "label": "EconomyBalance", "type": "data_flow"},
            # Data Analyst → Numerical (行为分析 → 数值建模闭环)
            {"from": "data_analyst", "to": "numerical", "label": "behavior_analyzed", "type": "collaboration"},
            # LiveOps → Growth (churn_alert → UA 响应)
            {"from": "liveops", "to": "ua", "label": "churn_alert", "type": "alert"},
            # LiveOps → Growth (winback campaign 执行)
            {"from": "liveops", "to": "creative", "label": "素材需求", "type": "collaboration"},
            # 各 Agent → CEO Memory (执行结果回流)
            {"from": "liveops", "to": "memory", "label": "执行结果回流", "type": "feedback"},
            {"from": "numerical", "to": "memory", "label": "数值报告回流", "type": "feedback"},
            {"from": "designer", "to": "memory", "label": "设计文档回流", "type": "feedback"},
            {"from": "data_analyst", "to": "memory", "label": "分析报告回流", "type": "feedback"},
            # MessageBus 广播
            {"from": "liveops", "to": "ceo", "label": "MessageBus 广播", "type": "broadcast"},
            {"from": "data_analyst", "to": "ceo", "label": "异常告警广播", "type": "broadcast"},
            # Player Support → LiveOps (玩家反馈驱动运营)
            {"from": "player_support", "to": "liveops", "label": "VIP 反馈", "type": "collaboration"},
        ],
        "departments": [
            {"id": "管理", "color": "#8b5cf6", "agents": ["ceo", "memory"]},
            {"id": "研发", "color": "#0ea5e9", "agents": ["product", "designer"]},
            {"id": "增长", "color": "#3b82f6", "agents": ["ua", "creative"]},
            {"id": "运营", "color": "#d946ef", "agents": ["liveops", "numerical", "data_analyst", "player_support"]},
        ],
    }

    # 2. 从 CEO execution_memory 提取最近 LiveOps 事件
    recent_events: list[dict] = []
    exec_memory_path = _PROJECT_ROOT / "data" / "ceo" / "execution_memory.jsonl"
    if exec_memory_path.exists():
        try:
            lines = exec_memory_path.read_text(encoding="utf-8").strip().split("\n")
            # 取最近 20 条 liveops 域记录
            liveops_lines = [
                json.loads(l) for l in lines
                if l.strip() and json.loads(l).get("domain") == "liveops"
            ]
            recent_events = liveops_lines[-20:]
        except (OSError, json.JSONDecodeError):
            pass

    # 3. CEO Daily Run 最近一次 STAGE_LIVEOPS 阶段结果
    ceo_liveops_stage: dict | None = None
    runs_path = _PROJECT_ROOT / "data" / "operator_demo" / "runs.jsonl"
    if not runs_path.exists():
        runs_path = _PROJECT_ROOT / "data" / "operator" / "runs.jsonl"
    if runs_path.exists():
        try:
            lines = runs_path.read_text(encoding="utf-8").strip().split("\n")
            # 从后往前找最近一次含 liveops 阶段的 run
            for line in reversed(lines):
                if not line.strip():
                    continue
                run = json.loads(line)
                stages = run.get("stages", [])
                for st in stages:
                    if st.get("stage") == "liveops":
                        ceo_liveops_stage = st
                        ceo_liveops_stage["run_id"] = run.get("run_id", "")
                        ceo_liveops_stage["business_date"] = run.get("business_date", "")
                        break
                if ceo_liveops_stage:
                    break
        except (OSError, json.JSONDecodeError):
            pass

    # 4. 协同链路统计
    collaboration_stats = {
        "total_liveops_events": len(recent_events),
        "ceo_liveops_triggered": ceo_liveops_stage is not None,
        "broadcast_types": ["churn_alert", "campaign_executed", "campaign_approved", "campaign_rejected", "behavior_analyzed", "anomalies_detected"],
        "feedback_channels": ["ceo_memory", "message_bus"],
        "collaboration_links": [
            {"name": "Data→Numerical", "endpoint": "/api/collaboration/analysis-loop", "active": True},
            {"name": "Product→Designer", "endpoint": "/api/designer/document", "active": True},
            {"name": "Designer→Numerical", "endpoint": "/api/numerical/inflation", "active": True},
            {"name": "LiveOps→Growth", "endpoint": "/api/growth/churn-responses", "active": True},
        ],
        "topology_summary": {
            "total_agents": len(topology["nodes"]),
            "total_edges": len(topology["edges"]),
            "total_departments": len(topology["departments"]),
        },
    }

    return {
        "topology": topology,
        "recent_events": recent_events,
        "ceo_liveops_stage": ceo_liveops_stage,
        "collaboration_stats": collaboration_stats,
    }


# ── LiveOps → Growth 双向协同: ChurnAlertBridge API ──────────


@app.get("/api/growth/churn-responses")
async def list_churn_responses(
    game_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Growth 响应 LiveOps churn_alert 的动作建议列表.

    Query:
        game_id: 过滤指定游戏 (不传=全部)
        limit: 返回最近 N 条 (默认 50, 最新在前)
    """
    bridge = _get_churn_alert_bridge()
    return bridge.list_responses(game_id=game_id, limit=limit)


@app.get("/api/growth/churn-responses/stats")
async def get_churn_response_stats() -> dict:
    """Growth 响应统计 — 供 Dashboard 概览卡片."""
    bridge = _get_churn_alert_bridge()
    return bridge.get_stats()


@app.get("/api/growth/churn-responses/{response_id}")
async def get_churn_response(response_id: str) -> dict:
    """查询单条 Growth 响应详情."""
    bridge = _get_churn_alert_bridge()
    result = bridge.get_response(response_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Churn response {response_id} not found",
        )
    return result


@app.post("/api/growth/churn-responses/{response_id}/rollback")
async def rollback_churn_response(response_id: str) -> dict:
    """回滚已执行的 Growth 响应 — 恢复 UA 状态.

    安全机制: 仅 executed / partial_executed 状态可回滚.
    回滚后状态变为 rolled_back, 写入审计日志.
    """
    bridge = _get_churn_alert_bridge()
    result = bridge.rollback_response(response_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Churn response {response_id} not found",
        )
    logger.info("Churn response %s rolled back", response_id)
    return {
        "response_id": response_id,
        "status": result.get("status", "rolled_back"),
        "message": "响应已回滚, UA 状态已恢复",
    }


@app.get("/api/growth/churn-responses/audit/logs")
async def list_churn_response_audit_logs(limit: int = 50) -> list[dict]:
    """查询 Growth 响应审计日志 (执行/回滚记录)."""
    bridge = _get_churn_alert_bridge()
    return bridge.list_audit_logs(limit=limit)


# ── 系统监控 API ──────────────────────────────────────────────


def _get_system_monitor():
    """获取 SystemMonitor 实例."""
    from .system_monitor import SystemMonitor
    return SystemMonitor(data_dir=str(_PROJECT_ROOT / "data"))


# ── JSONL 轮转管理 API ────────────────────────────────────────


@app.get("/api/maintenance/jsonl/stats")
async def get_jsonl_rotation_stats() -> dict:
    """JSONL 文件轮转统计 — 扫描所有 .jsonl 文件及归档."""
    from .jsonl_rotator import get_default_rotator
    rotator = get_default_rotator(data_dir=str(_PROJECT_ROOT / "data"))
    return rotator.get_rotation_stats()


@app.get("/api/maintenance/jsonl/archives/{file_path:path}")
async def list_jsonl_archives(file_path: str) -> dict:
    """查询指定 JSONL 文件的归档列表.

    Args:
        file_path: JSONL 文件相对路径 (相对于 data_dir), 如 "ceo/execution_memory.jsonl"
    """
    from .jsonl_rotator import get_default_rotator
    rotator = get_default_rotator(data_dir=str(_PROJECT_ROOT / "data"))
    full_path = _PROJECT_ROOT / "data" / file_path
    archives = rotator.list_archives(full_path)
    return {
        "file_path": file_path,
        "exists": full_path.exists(),
        "archives": archives,
        "archive_count": len(archives),
    }


@app.post("/api/maintenance/jsonl/rotate")
async def trigger_jsonl_rotation(file_path: str) -> dict:
    """手动触发指定 JSONL 文件的轮转.

    Query:
        file_path: JSONL 文件相对路径 (相对于 data_dir)
    """
    from .jsonl_rotator import get_default_rotator
    rotator = get_default_rotator(data_dir=str(_PROJECT_ROOT / "data"))
    full_path = _PROJECT_ROOT / "data" / file_path
    rotated = rotator.maybe_rotate(full_path)
    return {
        "file_path": file_path,
        "rotated": rotated,
        "message": "轮转已完成" if rotated else "文件未超阈值, 无需轮转",
    }


@app.post("/api/maintenance/jsonl/rotate-all")
async def trigger_jsonl_rotation_all() -> dict:
    """批量轮转所有超阈值的 JSONL 文件.

    非侵入式运维操作: 扫描 data_dir 下所有 .jsonl 文件,
    对超阈值 (10MB / 50000 行) 的文件执行 gzip 归档 + 截断.
    适用于定期清理 append-only 文件, 防止无限膨胀.
    """
    from .jsonl_rotator import get_default_rotator
    rotator = get_default_rotator(data_dir=str(_PROJECT_ROOT / "data"))
    return rotator.rotate_all()


@app.post("/api/maintenance/alerts/notify")
async def notify_alerts(
    channels: str | None = None,
    min_severity: str = "warning",
) -> dict:
    """检测当前告警并推送到通知渠道.

    流程:
      1. 调用 SystemMonitor.get_alerts() 获取当前告警
      2. 按 min_severity 过滤 (critical/warning/info)
      3. 按 channels 推送到指定渠道 (逗号分隔; 留空则自动检测)
      4. 幂等去重: 同一 alert_id 在 5 分钟窗口内只推送一次

    Args:
        channels: 渠道列表 (逗号分隔), 如 "wecom,feishu"; None 则自动检测已配置渠道
        min_severity: 最低推送级别 ("critical" | "warning" | "info"), 默认 "warning"

    Returns:
        推送结果: alerts_count, results (各渠道结果), deduplicated_count
    """
    from .alert_notifier import get_alert_notifier, SEVERITY_PUSH_MAP
    monitor = _get_system_monitor()
    all_alerts = monitor.get_alerts()

    # 按最低级别过滤
    severity_order = {"info": 0, "warning": 1, "critical": 2}
    min_level = severity_order.get(min_severity, 1)
    filtered_alerts = [
        a for a in all_alerts
        if severity_order.get(a.get("severity", "info"), 0) >= min_level
    ]

    # 解析渠道参数
    channel_list = None
    if channels:
        channel_list = [c.strip() for c in channels.split(",") if c.strip()]

    notifier = get_alert_notifier()
    results = notifier.notify_alerts(filtered_alerts, channels=channel_list)

    return {
        "alerts_total": len(all_alerts),
        "alerts_to_push": len(filtered_alerts),
        "deduplicated_count": len(all_alerts) - len(filtered_alerts),
        "min_severity": min_severity,
        "channels_requested": channel_list or "auto",
        "results": [
            {
                "channel": r.channel,
                "success": r.success,
                "sent": r.sent,
                "error": r.error,
            }
            for r in results
        ],
    }


@app.get("/api/maintenance/alerts/channels")
async def get_alert_channels_status() -> dict:
    """查询告警通知渠道配置状态 (不暴露凭证值)."""
    from .alert_notifier import get_alert_notifier
    notifier = get_alert_notifier()
    cfg = notifier.config
    return {
        "email": {
            "configured": cfg.has_email_config(),
            "smtp_host": cfg.smtp_host or "(未配置)",
            "smtp_port": cfg.smtp_port,
            "recipients_count": len(cfg.email_to),
        },
        "wecom": {
            "configured": cfg.has_wecom_config(),
            "webhook_set": bool(cfg.wecom_webhook),
        },
        "feishu": {
            "configured": cfg.has_feishu_config(),
            "webhook_set": bool(cfg.feishu_webhook),
        },
        "dedup_window_seconds": cfg.dedup_window_seconds,
        "active_channels": notifier._get_active_channels(),
    }


# ── 协同层: 冲突检测 (M3.2) ─────────────────────────────────


@app.get("/api/collaboration/conflicts")
async def list_conflicts(
    game_id: str | None = None,
    conflict_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """查询跨 Agent 冲突记录列表."""
    from .conflict_detector import get_conflict_detector
    detector = get_conflict_detector(data_dir=str(_PROJECT_ROOT / "data"))
    return detector.list_conflicts(
        game_id=game_id, conflict_type=conflict_type, limit=limit
    )


@app.get("/api/collaboration/conflicts/stats")
async def get_conflict_stats() -> dict:
    """冲突检测统计."""
    from .conflict_detector import get_conflict_detector
    detector = get_conflict_detector(data_dir=str(_PROJECT_ROOT / "data"))
    return detector.get_stats()


@app.get("/api/collaboration/conflicts/versions")
async def get_version_table(game_id: str | None = None) -> dict:
    """查询游戏数值版本表 (用于调试冲突检测)."""
    from .conflict_detector import get_conflict_detector
    detector = get_conflict_detector(data_dir=str(_PROJECT_ROOT / "data"))
    return detector.get_all_versions(game_id=game_id)


# ── iOS App Store 上架 (Spec ios_upload_spec.md) ──────────────


@app.get("/api/ios/credentials/status")
async def get_ios_credentials_status() -> dict:
    """查询 App Store Connect 凭证配置状态 (不暴露凭证值)."""
    from operation.providers.live import store_keys
    cred = store_keys.get_appstore()
    return {
        "configured": cred is not None,
        "mode": "PRODUCTION" if cred else "SIMULATION",
        "has_key_id": bool(cred and cred.get("key_id")),
        "has_issuer_id": bool(cred and cred.get("issuer_id")),
        "has_private_key": bool(cred and cred.get("private_key_p8")),
        "setup_guide": "见 credentials/store_keys.json.example",
    }


@app.post("/api/ios/release/start")
async def start_ios_release(
    game_id: str,
    bundle_id: str,
    ipa_path: str,
    version: str,
    build_number: int,
    version_id: str | None = None,
    stop_step: str | None = None,
) -> dict:
    """启动 iOS 发布流程 (7 步编排).

    默认执行到 submit_review (等待人工审核).
    可指定 stop_step 控制执行范围.
    """
    from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator
    orch = IOSReleaseOrchestrator(
        game_id=game_id,
        bundle_id=bundle_id,
        ipa_path=ipa_path,
        version=version,
        build_number=build_number,
        version_id=version_id,
        data_dir=str(_PROJECT_ROOT / "data" / "ios_release"),
    )
    return orch.run(stop_step=stop_step)


@app.get("/api/ios/release/{release_id}/status")
async def get_ios_release_status(release_id: str) -> dict:
    """查询发布流程状态."""
    from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator
    try:
        orch = IOSReleaseOrchestrator.load_release(
            release_id, data_dir=str(_PROJECT_ROOT / "data" / "ios_release"))
        return orch.get_status()
    except FileNotFoundError:
        return {"error": f"release not found: {release_id}"}


@app.post("/api/ios/release/{release_id}/resume")
async def resume_ios_release(
    release_id: str,
    start_step: str | None = None,
    stop_step: str | None = None,
) -> dict:
    """恢复/继续发布流程 (断点续跑)."""
    from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator
    try:
        orch = IOSReleaseOrchestrator.load_release(
            release_id, data_dir=str(_PROJECT_ROOT / "data" / "ios_release"))
        return orch.run(start_step=start_step, stop_step=stop_step)
    except FileNotFoundError:
        return {"error": f"release not found: {release_id}"}


@app.get("/api/ios/releases")
async def list_ios_releases() -> dict:
    """列出所有发布流程."""
    import json
    from pathlib import Path
    release_dir = _PROJECT_ROOT / "data" / "ios_release"
    if not release_dir.exists():
        return {"releases": []}
    releases = []
    for f in release_dir.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                state = json.load(fh)
            releases.append({
                "release_id": state.get("release_id", f.stem),
                "game_id": state.get("game_id", ""),
                "version": state.get("version", ""),
                "status": state.get("status", ""),
                "current_step": state.get("current_step", ""),
                "completed_steps": state.get("completed_steps", []),
                "started_at": state.get("started_at", ""),
            })
        except Exception:
            continue
    return {"releases": releases}


# ── Google Play 上架 (Spec google_play_upload_spec.md) ─────────


@app.get("/api/googleplay/credentials/status")
async def get_googleplay_credentials_status() -> dict:
    """查询 Google Play 凭证配置状态 (不暴露凭证值)."""
    from operation.providers.live import store_keys
    cred = store_keys.get_googleplay()
    return {
        "configured": cred is not None,
        "mode": "PRODUCTION" if cred else "SIMULATION",
        "has_service_account": bool(
            cred and (cred.get("service_account_json") or cred.get("service_account_json_path"))
        ),
        "has_package_name": bool(cred and cred.get("package_name")),
        "setup_guide": "见 credentials/store_keys.json.example",
    }


@app.post("/api/googleplay/release/start")
async def start_googleplay_release(
    game_id: str,
    package_name: str,
    aab_path: str,
    version: str,
    build_number: int,
    track: str = "internal",
    rollout_fraction: float = 0.05,
    stop_step: str | None = None,
) -> dict:
    """启动 Google Play 发布流程 (7 步编排).

    默认执行到 submit_review (等待人工审核).
    可指定 stop_step 控制执行范围.
    """
    from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
    orch = GooglePlayReleaseOrchestrator(
        game_id=game_id,
        package_name=package_name,
        aab_path=aab_path,
        version=version,
        build_number=build_number,
        track=track,
        rollout_fraction=rollout_fraction,
        data_dir=str(_PROJECT_ROOT / "data" / "google_play_release"),
    )
    return orch.run(stop_step=stop_step)


@app.get("/api/googleplay/release/{release_id}/status")
async def get_googleplay_release_status(release_id: str) -> dict:
    """查询 Google Play 发布流程状态."""
    from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
    try:
        orch = GooglePlayReleaseOrchestrator.load_release(
            release_id, data_dir=str(_PROJECT_ROOT / "data" / "google_play_release"))
        return orch.get_status()
    except FileNotFoundError:
        return {"error": f"release not found: {release_id}"}


@app.post("/api/googleplay/release/{release_id}/resume")
async def resume_googleplay_release(
    release_id: str,
    start_step: str | None = None,
    stop_step: str | None = None,
) -> dict:
    """恢复/继续 Google Play 发布流程 (断点续跑)."""
    from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
    try:
        orch = GooglePlayReleaseOrchestrator.load_release(
            release_id, data_dir=str(_PROJECT_ROOT / "data" / "google_play_release"))
        return orch.run(start_step=start_step, stop_step=stop_step)
    except FileNotFoundError:
        return {"error": f"release not found: {release_id}"}


@app.get("/api/googleplay/releases")
async def list_googleplay_releases() -> dict:
    """列出所有 Google Play 发布流程."""
    import json
    from pathlib import Path
    release_dir = _PROJECT_ROOT / "data" / "google_play_release"
    if not release_dir.exists():
        return {"releases": []}
    releases = []
    for f in release_dir.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                state = json.load(fh)
            releases.append({
                "release_id": state.get("release_id", f.stem),
                "game_id": state.get("game_id", ""),
                "package_name": state.get("package_name", ""),
                "version": state.get("version", ""),
                "track": state.get("track", ""),
                "status": state.get("status", ""),
                "current_step": state.get("current_step", ""),
                "completed_steps": state.get("completed_steps", []),
                "started_at": state.get("started_at", ""),
            })
        except Exception:
            continue
    return {"releases": releases}


@app.post("/api/googleplay/release/{release_id}/halt")
async def halt_googleplay_release(release_id: str) -> dict:
    """暂停/回滚 staged rollout (用户主动暂停)."""
    from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
    try:
        orch = GooglePlayReleaseOrchestrator.load_release(
            release_id, data_dir=str(_PROJECT_ROOT / "data" / "google_play_release"))
        return orch.halt_rollout()
    except FileNotFoundError:
        return {"error": f"release not found: {release_id}"}


@app.post("/api/googleplay/release/{release_id}/advance")
async def advance_googleplay_release(
    release_id: str,
    next_fraction: float = 0.10,
) -> dict:
    """推进 staged rollout 到下一百分比."""
    from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
    try:
        orch = GooglePlayReleaseOrchestrator.load_release(
            release_id, data_dir=str(_PROJECT_ROOT / "data" / "google_play_release"))
        return orch.advance_rollout(next_fraction=next_fraction)
    except FileNotFoundError:
        return {"error": f"release not found: {release_id}"}


# ── Token 过期监控 (Spec production_roadmap.md O5) ─────────────


@app.get("/api/token-monitor/status")
async def get_token_monitor_status() -> dict:
    """查询所有 Token 的过期监控状态摘要."""
    from .token_monitor import get_token_monitor
    monitor = get_token_monitor(data_dir=str(_PROJECT_ROOT / "data" / "token_monitor"))
    return monitor.get_status()


@app.get("/api/token-monitor/alerts")
async def get_token_monitor_alerts() -> dict:
    """查询 Token 过期告警列表 (兼容 SystemMonitor.get_alerts() 格式)."""
    from .token_monitor import get_token_monitor
    monitor = get_token_monitor(data_dir=str(_PROJECT_ROOT / "data" / "token_monitor"))
    return {"alerts": monitor.get_alerts()}


@app.post("/api/token-monitor/register")
async def register_token_for_monitor(req: dict) -> dict:
    """手动注册一个 Token 的过期时间 (用于 OAuth/JWT 等无法实时查询的 token).

    Request body:
        token_id: 唯一标识
        expires_at: 过期 Unix timestamp (0 = 永不过期)
        token_type: token 类型 (可选, 默认 custom)
        is_valid: 是否有效 (可选, 默认 true)
        token_preview: token 预览 (可选)
    """
    from .token_monitor import get_token_monitor
    monitor = get_token_monitor(data_dir=str(_PROJECT_ROOT / "data" / "token_monitor"))
    status = monitor.register_token(
        token_id=req.get("token_id", ""),
        expires_at=float(req.get("expires_at", 0)),
        token_type=req.get("token_type", "custom"),
        is_valid=bool(req.get("is_valid", True)),
        source="api_register",
        token_preview=req.get("token_preview", ""),
    )
    return status.to_dict()


@app.delete("/api/token-monitor/tokens/{token_id}")
async def unregister_token_from_monitor(token_id: str) -> dict:
    """移除已注册的 Token."""
    from .token_monitor import get_token_monitor
    monitor = get_token_monitor(data_dir=str(_PROJECT_ROOT / "data" / "token_monitor"))
    success = monitor.unregister_token(token_id)
    return {"success": success, "token_id": token_id}


@app.post("/api/token-monitor/check/meta")
async def check_meta_token_now() -> dict:
    """触发 Meta Access Token 实时检查 (从环境变量读取).

    需要 META_ACCESS_TOKEN 环境变量. 可选 META_APP_ID / META_APP_SECRET.
    """
    from .token_monitor import get_token_monitor
    monitor = get_token_monitor(data_dir=str(_PROJECT_ROOT / "data" / "token_monitor"))
    import os
    if not os.getenv("META_ACCESS_TOKEN", ""):
        return {
            "skipped": True,
            "reason": "META_ACCESS_TOKEN not configured",
        }
    status = monitor.check_meta_token_from_env()
    if status is None:
        return {"skipped": True, "reason": "META_ACCESS_TOKEN not configured"}
    return status.to_dict()


@app.post("/api/token-monitor/check/all")
async def check_all_auto_tokens() -> dict:
    """检查所有可自动检查的 token (目前仅 Meta)."""
    from .token_monitor import get_token_monitor
    monitor = get_token_monitor(data_dir=str(_PROJECT_ROOT / "data" / "token_monitor"))
    import os
    if not os.getenv("META_ACCESS_TOKEN", ""):
        return {
            "skipped": True,
            "reason": "META_ACCESS_TOKEN not configured",
            "checked": [],
        }
    results = monitor.check_all_auto_tokens()
    return {
        "checked": [s.to_dict() for s in results],
        "count": len(results),
    }


@app.post("/api/collaboration/conflicts/check")
async def check_conflict(req: dict) -> dict:
    """检查指定修改是否会产生冲突 (Agent 修改前预检).

    Request body:
        game_id: 游戏 ID
        metric: 目标指标
        agent_id: 发起修改的 Agent ID
        proposed_value: 建议的新值
        base_version: Agent 基于的版本号
    """
    from .conflict_detector import get_conflict_detector
    detector = get_conflict_detector(data_dir=str(_PROJECT_ROOT / "data"))
    conflict = detector.check_before_modify(
        game_id=req.get("game_id", "unknown"),
        metric=req.get("metric", ""),
        agent_id=req.get("agent_id", ""),
        proposed_value=float(req.get("proposed_value", 0.0)),
        base_version=int(req.get("base_version", 1)),
        source_event=req.get("source_event", ""),
    )
    if conflict is None:
        return {"has_conflict": False, "conflict": None}
    return {"has_conflict": True, "conflict": conflict.to_dict()}


@app.post("/api/collaboration/conflicts/register")
async def register_change(req: dict) -> dict:
    """注册数值变更 (Agent 完成修改后推进版本号).

    Request body:
        game_id: 游戏 ID
        metric: 目标指标
        agent_id: 完成修改的 Agent ID
        new_value: 修改后的新值
        base_version: Agent 基于的版本号
    """
    from .conflict_detector import get_conflict_detector
    detector = get_conflict_detector(data_dir=str(_PROJECT_ROOT / "data"))
    version = detector.register_change(
        game_id=req.get("game_id", "unknown"),
        metric=req.get("metric", ""),
        agent_id=req.get("agent_id", ""),
        new_value=float(req.get("new_value", 0.0)),
        base_version=int(req.get("base_version", 1)),
        source_event=req.get("source_event", ""),
    )
    return version.to_dict()


@app.get("/api/collaboration/conflicts/{conflict_id}")
async def get_conflict(conflict_id: str) -> dict:
    """查询单条冲突记录详情."""
    from .conflict_detector import get_conflict_detector
    detector = get_conflict_detector(data_dir=str(_PROJECT_ROOT / "data"))
    record = detector.get_conflict(conflict_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")
    return record


@app.get("/api/monitor/overview")
async def get_monitor_overview() -> dict:
    """系统监控概览 — 聚合所有子系统指标 + 告警 + 文件监控.

    返回:
      - health: 系统健康状态 (healthy/degraded/critical)
      - alerts: 告警列表
      - growth_loop: GrowthLoop 执行统计
      - liveops: LiveOps 执行统计
      - churn_alert: ChurnAlert 响应统计
      - approval_queue: 审批队列统计
      - data_files: JSONL 文件监控
    """
    return _get_system_monitor().get_dashboard_overview()


@app.get("/api/monitor/health")
async def get_monitor_health() -> dict:
    """系统健康详情 — 含子系统状态和告警计数."""
    return _get_system_monitor().get_system_health()


@app.get("/api/monitor/alerts")
async def get_monitor_alerts() -> list[dict]:
    """告警列表 — 阈值检测结果."""
    return _get_system_monitor().get_alerts()


@app.get("/api/monitor/files")
async def get_monitor_files() -> dict:
    """JSONL 文件监控 — 大小/记录数/最近更新时间."""
    return _get_system_monitor()._get_file_stats()


@app.get("/api/monitor/growth-loop")
async def get_monitor_growth_loop() -> dict:
    """GrowthLoop 执行统计."""
    return _get_system_monitor()._get_growth_loop_stats()


@app.get("/api/monitor/liveops")
async def get_monitor_liveops() -> dict:
    """LiveOps 执行统计."""
    return _get_system_monitor()._get_liveops_stats()


@app.get("/api/monitor/approval-queue")
async def get_monitor_approval_queue() -> dict:
    """审批队列统计 (CEO + LiveOps)."""
    return _get_system_monitor()._get_approval_queue_stats()


# ═══════════════════════════════════════════════════════════════
# P4 Autonomous Growth Agent — 安全封套 + Fleet + Cycle + 治理
# ═══════════════════════════════════════════════════════════════


def _get_p4_data_dir() -> Path:
    """P4 数据目录."""
    return _PROJECT_ROOT / "data" / "p4"


def _get_p4_operator():
    """获取 P4 operator (mock, 避免依赖完整 runtime)."""
    def _operator(**kwargs):
        return {"real_api_called": False, "shard_id": kwargs.get("run_id", "")}
    return _operator


def _get_p4_agent():
    """获取 P4 AutonomousGrowthAgent 单例 (dry_run 默认)."""
    from src.autonomous_growth import AutonomousGrowthAgent, AgentConfig, ProductionReadinessGate
    cache_key = "_p4_agent_instance"
    if not hasattr(app, cache_key):
        gate = ProductionReadinessGate(root=str(_PROJECT_ROOT))
        app.__dict__[cache_key] = AutonomousGrowthAgent(
            operator=_get_p4_operator(),
            config=AgentConfig(mode="dry_run"),
            readiness=gate,
        )
    return app.__dict__[cache_key]


def _get_p4_cycle_store():
    """获取 P4 CycleStore 单例."""
    from src.autonomous_growth import CycleStore
    return CycleStore(str(_get_p4_data_dir() / "cycle_state.jsonl"))


def _get_p4_durable_queue():
    """获取 P4 DurableQueue 单例."""
    from src.autonomous_growth import DurableQueue
    return DurableQueue(str(_get_p4_data_dir() / "durable_queue.jsonl"))


def _get_p4_governor():
    """获取 P4 MultiAgentGovernor 单例."""
    from src.autonomous_growth import MultiAgentGovernor
    cache_key = "_p4_governor_instance"
    if not hasattr(app, cache_key):
        app.__dict__[cache_key] = MultiAgentGovernor()
    return app.__dict__[cache_key]


@app.get("/api/p4/readiness")
async def p4_readiness() -> dict:
    """P4 启动就绪检查 — 验证配置/路径/凭证.

    遵循 frozen rule #8: 启动就绪验证配置、可写状态/日志路径和凭证.
    """
    from src.autonomous_growth import AgentConfig, ProductionReadinessGate
    gate = ProductionReadinessGate(root=str(_PROJECT_ROOT))
    config = AgentConfig(mode="dry_run")
    report = gate.check(config)
    return report.to_dict()


@app.get("/api/p4/agent/status")
async def p4_agent_status() -> dict:
    """P4 Agent 状态查询 — 含熔断器状态."""
    agent = _get_p4_agent()
    return {
        "mode": agent.config.mode,
        "circuit_open": agent.circuit_open,
        "consecutive_failures": agent.consecutive_failures,
        "max_consecutive_failures": agent.config.max_consecutive_failures,
        "max_games": agent.config.max_games,
        "max_actions": agent.config.max_actions,
        "max_daily_budget": agent.config.max_daily_budget,
        "min_confidence": agent.config.min_confidence,
    }


@app.post("/api/p4/agent/run")
async def p4_agent_run(req: dict) -> dict:
    """P4 Agent 运行 — dry_run 默认, production 需 approval.

    遵循 frozen rules:
      #1 默认 dry_run, production 需显式选择
      #2 production 需 approval gate
      #3 per-run limits: games, actions, budget, confidence
      #4 幂等: 同 date/game-set/mode 返回相同 run_id
      #6 simulation/dry_run 不报告执行动作
    """
    business_date = req.get("business_date", "")
    game_ids = req.get("game_ids", [])
    if not business_date or not game_ids:
        raise HTTPException(status_code=400, detail="business_date and game_ids required")

    mode = req.get("mode", "dry_run")
    if mode not in ("dry_run", "simulation", "production"):
        raise HTTPException(status_code=400, detail="mode must be dry_run, simulation or production")

    from src.autonomous_growth import AgentConfig, AutonomousGrowthAgent, ProductionReadinessGate
    config = AgentConfig(
        mode=mode,
        max_games=int(req.get("max_games", 25)),
        max_actions=int(req.get("max_actions", 20)),
        max_daily_budget=float(req.get("max_daily_budget", 1000.0)),
        min_confidence=float(req.get("min_confidence", 0.7)),
        require_approval_in_production=True,
        required_env=req.get("required_env", []) if mode == "production" else [],
    )
    gate = ProductionReadinessGate(root=str(_PROJECT_ROOT))
    agent = AutonomousGrowthAgent(operator=_get_p4_operator(), config=config, readiness=gate)

    run = agent.run(
        business_date=business_date,
        game_ids=game_ids,
        proposed_actions=int(req.get("proposed_actions", 0)),
        requested_budget=float(req.get("requested_budget", 0.0)),
        confidence=float(req.get("confidence", 1.0)),
        approval_present=bool(req.get("approval_present", False)),
    )
    return run.to_dict()


@app.post("/api/p4/agent/circuit/reset")
async def p4_agent_circuit_reset(req: dict) -> dict:
    """P4 熔断器重置 — 需授权.

    遵循 frozen rule #5: 连续失败打开熔断器, 重置需授权.
    """
    agent = _get_p4_agent()
    authorized = bool(req.get("authorized", False))
    success = agent.reset_circuit(authorized=authorized)
    return {
        "success": success,
        "circuit_open": agent.circuit_open,
        "authorized": authorized,
        "message": "熔断器已重置" if success else "重置失败: 需要授权",
    }


@app.post("/api/p4/fleet/run")
async def p4_fleet_run(req: dict) -> dict:
    """P4.1 Fleet 分片编排运行 — 确定性分片 + 失败隔离.

    遵循 frozen rule #3: per-run games 限制 (max 200).
    """
    from src.autonomous_growth import FleetConfig, FleetOrchestrator

    business_date = req.get("business_date", "")
    game_ids = req.get("game_ids", [])
    if not business_date or not game_ids:
        raise HTTPException(status_code=400, detail="business_date and game_ids required")

    config = FleetConfig(
        max_games=int(req.get("max_games", 200)),
        shard_size=int(req.get("shard_size", 12)),
        max_workers=int(req.get("max_workers", 8)),
    )
    errors = config.validate()
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    orchestrator = FleetOrchestrator(runner=_get_p4_operator(), config=config)
    result = orchestrator.run(business_date, game_ids)
    return {
        "business_date": result.business_date,
        "roles": result.roles,
        "total_games": result.total_games,
        "successful_shards": result.successful_shards,
        "failed_shards": result.failed_shards,
        "completed": result.completed,
        "real_api_called": result.real_api_called,
        "shards": [
            {
                "shard_id": s.shard_id,
                "game_ids": s.game_ids,
                "success": s.success,
                "error_type": s.error_type,
                "real_api_called": s.real_api_called,
            }
            for s in result.shards
        ],
    }


@app.get("/api/p4/cycle/{cycle_id}")
async def p4_cycle_get(cycle_id: str) -> dict:
    """P4.2 Cycle 状态查询 — 读取最新 revision."""
    store = _get_p4_cycle_store()
    state = store.load(cycle_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} not found")
    return state.to_dict()


@app.post("/api/p4/cycle/run")
async def p4_cycle_run(req: dict) -> dict:
    """P4.2 Cycle 运行 — 可恢复的 11 阶段循环.

    遵循 frozen rules:
      #2 production 需 approval
      #4 幂等: 同 cycle_id 可恢复
      #7 通过 SafeExecutor 执行
    """
    from src.autonomous_growth import AutonomousCycle, CycleStage
    from src.autonomous_growth.cycle import ORDER

    cycle_id = req.get("cycle_id", "")
    business_date = req.get("business_date", "")
    if not cycle_id or not business_date:
        raise HTTPException(status_code=400, detail="cycle_id and business_date required")

    production = bool(req.get("production", False))
    approval_present = bool(req.get("approval_present", False))

    # 提供 stub handlers (除 EXECUTE 外)
    handlers = {
        stage.value: lambda **kw: {"stage": kw["state"].stage.value, "stub": True}
        for stage in ORDER[:-1] if stage != CycleStage.EXECUTE
    }
    # EXECUTE handler
    def _execute_handler(**kw):
        return {"total_games": 0, "successful_shards": 0, "failed_shards": 0, "real_api_called": False}
    handlers[CycleStage.EXECUTE.value] = _execute_handler

    store = _get_p4_cycle_store()
    cycle = AutonomousCycle(store, handlers, production=production)
    state = cycle.run(cycle_id, business_date, approval_present=approval_present)
    return state.to_dict()


@app.post("/api/p4/product/advance")
async def p4_product_advance(req: dict) -> dict:
    """P4.3 产品生命周期推进 — 确定性 promotion gates.

    遵循 frozen rule: promotion 和 retirement 需冻结 KPI gates.
    """
    from src.autonomous_growth import ProductAsset, ProductFactory, ProductGate, ProductStage

    product_id = req.get("product_id", "")
    stage_str = req.get("stage", "idea")
    metrics = req.get("metrics", {})
    if not product_id:
        raise HTTPException(status_code=400, detail="product_id required")

    try:
        stage = ProductStage(stage_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid stage: {stage_str}")

    gate_config = req.get("gate", {})
    gate = ProductGate(
        max_cpi=float(gate_config.get("max_cpi", 1.0)),
        min_d1_retention=float(gate_config.get("min_d1_retention", 0.25)),
        min_roas=float(gate_config.get("min_roas", 0.8)),
        min_installs=int(gate_config.get("min_installs", 100)),
    )
    factory = ProductFactory(gate=gate)
    asset = ProductAsset(product_id=product_id, stage=stage, metrics=metrics)
    result = factory.advance(asset)
    return {
        "product_id": result.product_id,
        "stage": result.stage.value,
        "reason": result.reason,
        "history": result.history,
        "metrics": result.metrics,
    }


@app.post("/api/p4/governance/arbitrate")
async def p4_governance_arbitrate(req: dict) -> dict:
    """P4.4 多 Agent 仲裁 — 最小权限 + 预算约束.

    遵循 frozen rule #9: 不绕过治理.
    """
    from src.autonomous_growth import AgentProposal, AgentRole

    proposals_data = req.get("proposals", [])
    budget = float(req.get("budget", 0.0))
    if not proposals_data:
        return {"selected": [], "count": 0, "budget": budget}

    proposals = []
    for p in proposals_data:
        try:
            role = AgentRole(p["role"])
            proposals.append(AgentProposal(
                role=role,
                game_id=p["game_id"],
                resource=p["resource"],
                action=p["action"],
                priority=float(p["priority"]),
                confidence=float(p["confidence"]),
                requested_budget=float(p.get("requested_budget", 0.0)),
            ))
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"invalid proposal: {exc}")

    governor = _get_p4_governor()
    selected = governor.arbitrate(proposals, budget)
    return {
        "selected": [
            {
                "role": p.role.value,
                "game_id": p.game_id,
                "resource": p.resource,
                "action": p.action,
                "priority": p.priority,
                "confidence": p.confidence,
                "requested_budget": p.requested_budget,
            }
            for p in selected
        ],
        "count": len(selected),
        "budget": budget,
        "human_takeover": governor.human_takeover,
    }


@app.post("/api/p4/governance/takeover")
async def p4_governance_takeover(req: dict) -> dict:
    """P4.4 人工接管 — 需授权.

    遵循 frozen rule: 支持人工接管.
    """
    governor = _get_p4_governor()
    authorized = bool(req.get("authorized", False))
    success = governor.takeover(authorized=authorized)
    return {
        "success": success,
        "human_takeover": governor.human_takeover,
        "message": "已接管" if success else "接管失败: 需要授权",
    }


@app.post("/api/p4/governance/release")
async def p4_governance_release(req: dict) -> dict:
    """P4.4 释放人工接管 — 需授权."""
    governor = _get_p4_governor()
    authorized = bool(req.get("authorized", False))
    success = governor.release(authorized=authorized)
    return {
        "success": success,
        "human_takeover": governor.human_takeover,
        "message": "已释放接管" if success else "释放失败: 需要授权",
    }


@app.get("/api/p4/governance/permissions")
async def p4_governance_permissions() -> dict:
    """P4.4 查询权限矩阵."""
    from src.autonomous_growth import PERMISSIONS
    return {
        role.value: sorted(perms)
        for role, perms in PERMISSIONS.items()
    }


@app.get("/api/p4/slo/evaluate")
async def p4_slo_evaluate(
    success_rate: float,
    failed_shards: int,
    latency_ms: float,
    queue_depth: int,
) -> dict:
    """P4.5 SLO 评估 — 4 项检查 (成功率/失败分片/延迟/队列深度)."""
    from src.autonomous_growth import SLOEvaluator
    evaluator = SLOEvaluator()
    report = evaluator.evaluate(
        success_rate=success_rate,
        failed_shards=failed_shards,
        latency_ms=latency_ms,
        queue_depth=queue_depth,
    )
    return {
        "healthy": report.healthy,
        "checks": report.checks,
        "violations": report.violations,
    }


@app.post("/api/p4/queue/enqueue")
async def p4_queue_enqueue(req: dict) -> dict:
    """P4.5 DurableQueue 入队 — 幂等 (job_id 重复返回 False)."""
    job_id = req.get("job_id", "")
    payload = req.get("payload", {})
    max_attempts = int(req.get("max_attempts", 3))
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id required")

    queue = _get_p4_durable_queue()
    try:
        success = queue.enqueue(job_id, payload, max_attempts=max_attempts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"success": success, "job_id": job_id, "message": "已入队" if success else "已存在 (幂等)"}


@app.get("/api/p4/queue/pending")
async def p4_queue_pending() -> dict:
    """P4.5 DurableQueue 查询 pending."""
    queue = _get_p4_durable_queue()
    pending = queue.pending()
    return {
        "count": len(pending),
        "depth": queue.depth(),
        "jobs": [
            {
                "job_id": j.job_id,
                "payload": j.payload,
                "attempts": j.attempts,
                "max_attempts": j.max_attempts,
                "status": j.status,
            }
            for j in pending
        ],
    }


@app.post("/api/p4/queue/ack/{job_id}")
async def p4_queue_ack(job_id: str) -> dict:
    """P4.5 DurableQueue ack."""
    queue = _get_p4_durable_queue()
    success = queue.ack(job_id)
    return {"success": success, "job_id": job_id}


@app.post("/api/p4/queue/fail/{job_id}")
async def p4_queue_fail(job_id: str) -> dict:
    """P4.5 DurableQueue fail (递增 attempts, 达到 max 进入死信)."""
    queue = _get_p4_durable_queue()
    success = queue.fail(job_id)
    return {"success": success, "job_id": job_id}


@app.get("/api/p4/queue/dead-letters")
async def p4_queue_dead_letters() -> dict:
    """P4.5 DurableQueue 死信队列."""
    queue = _get_p4_durable_queue()
    dead = queue.dead_letters()
    return {
        "count": len(dead),
        "jobs": [
            {
                "job_id": j.job_id,
                "payload": j.payload,
                "attempts": j.attempts,
                "max_attempts": j.max_attempts,
                "status": j.status,
            }
            for j in dead
        ],
    }


@app.post("/api/p4/canary/run")
async def p4_canary_run(req: dict) -> dict:
    """P4.5 Canary 灰度运行 — 单动作生产灰度 + 监控 + 回滚.

    遵循 frozen rules:
      #2 production 需 approval
      #6 dry_run 不报告执行动作
      #7 通过 SafeExecutor 执行
    """
    from src.autonomous_growth import CanaryCoordinator

    canary_id = req.get("canary_id", "")
    game_id = req.get("game_id", "")
    action = req.get("action", {})
    approval_id = req.get("approval_id", "")
    if not canary_id or not game_id or not action or not approval_id:
        raise HTTPException(status_code=400,
                            detail="canary_id, game_id, action and approval_id required")

    # 使用 stub execute/monitor/rollback (生产环境注入真实实现)
    execute_fn = lambda **kw: {"success": True, "real_api_called": False, "evidence_ref": "stub-exec"}
    monitor_fn = lambda **kw: {"healthy": True, "evidence_ref": "stub-monitor"}
    rollback_fn = lambda **kw: {"success": True, "evidence_ref": "stub-rollback"}

    audit_path = str(_get_p4_data_dir() / "canary_audit.jsonl")
    canary = CanaryCoordinator(
        execute=execute_fn, monitor=monitor_fn,
        rollback=rollback_fn, audit_path=audit_path,
    )
    result = canary.run(canary_id, game_id, action, approval_id=approval_id)
    return result.__dict__


# ── Creative Mapping Engine ──────────────────────────────────


def _get_meta_access_token() -> str:
    """从环境变量获取 Meta access token。"""
    import os
    return (
        os.environ.get("META_ACCESS_TOKEN", "")
        or os.environ.get("FB_ACCESS_TOKEN", "")
    )


def _get_meta_ad_account_id() -> str:
    """从环境变量获取 Meta 广告账户 ID。"""
    import os
    return (
        os.environ.get("META_AD_ACCOUNT_ID", "")
        or os.environ.get("FACEBOOK_AD_ACCOUNT_ID", "")
    )


def _get_creative_mapping_engine():
    """获取 Creative Mapping Engine 单例。"""
    if not hasattr(_get_creative_mapping_engine, "_instance"):
        from src.market_ops.creative_mapping_engine import CreativeMappingEngine
        _get_creative_mapping_engine._instance = CreativeMappingEngine(
            data_dir=str(_PROJECT_ROOT / "data" / "creative_mapping"),
            eagle_index_path=str(_PROJECT_ROOT / "data" / "eagle_scan_index.json"),
        )
    return _get_creative_mapping_engine._instance


@app.post("/api/creative-mapping/match")
async def creative_mapping_match(req: dict) -> dict:
    """执行单条创意映射。"""
    engine = _get_creative_mapping_engine()
    if not req.get("facebook_creative_id"):
        raise HTTPException(status_code=400, detail="facebook_creative_id is required")
    record = engine.match(req)
    return record.to_dict()


@app.post("/api/creative-mapping/batch-match")
async def creative_mapping_batch_match(req: dict) -> dict:
    """批量创意映射。"""
    engine = _get_creative_mapping_engine()
    creatives = req.get("creatives", [])
    if not creatives:
        raise HTTPException(status_code=400, detail="creatives list is required")
    records = engine.batch_match(creatives)
    return {
        "total": len(records),
        "records": [r.to_dict() for r in records],
    }


@app.get("/api/creative-mapping/records")
async def creative_mapping_records(status: str = "", limit: int = 50) -> dict:
    """查询映射记录列表。"""
    engine = _get_creative_mapping_engine()
    records = engine.list_records(status=status, limit=limit)
    return {
        "total": len(records),
        "records": [r.to_dict() for r in records],
    }


@app.get("/api/creative-mapping/records/by-facebook/{fb_creative_id}")
async def creative_mapping_by_facebook(fb_creative_id: str) -> dict:
    """按 Facebook creative_id 查询映射。"""
    engine = _get_creative_mapping_engine()
    record = engine.get_by_facebook_id(fb_creative_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No mapping for facebook_creative_id: {fb_creative_id}")
    return record.to_dict()


@app.get("/api/creative-mapping/records/{mapping_id}")
async def creative_mapping_record_detail(mapping_id: str) -> dict:
    """查询单条映射记录详情。"""
    engine = _get_creative_mapping_engine()
    record = engine.get_record(mapping_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Mapping not found: {mapping_id}")
    return record.to_dict()


@app.get("/api/creative-mapping/review/queue")
async def creative_mapping_review_queue(limit: int = 50) -> dict:
    """获取待审核队列。"""
    engine = _get_creative_mapping_engine()
    tasks = engine.list_review_queue(limit=limit)
    return {"total": len(tasks), "tasks": tasks}


@app.post("/api/creative-mapping/review/{task_id}/approve")
async def creative_mapping_review_approve(task_id: str, req: dict) -> dict:
    """审核通过。"""
    engine = _get_creative_mapping_engine()
    eagle_filename = req.get("eagle_filename", "")
    if not eagle_filename:
        raise HTTPException(status_code=400, detail="eagle_filename is required")
    try:
        return engine.approve_review(
            task_id=task_id,
            eagle_filename=eagle_filename,
            eagle_path=req.get("eagle_path", ""),
            reviewer=req.get("reviewer", ""),
            note=req.get("note", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/creative-mapping/review/{task_id}/reject")
async def creative_mapping_review_reject(task_id: str, req: dict) -> dict:
    """审核驳回。"""
    engine = _get_creative_mapping_engine()
    reason = req.get("reason", "")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    try:
        return engine.reject_review(
            task_id=task_id, reason=reason, reviewer=req.get("reviewer", "")
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/creative-mapping/stats")
async def creative_mapping_stats() -> dict:
    """映射统计。"""
    engine = _get_creative_mapping_engine()
    return engine.get_stats()


# ── Eagle Scanner API ────────────────────────────────────────


def _get_eagle_scanner(eagle_root: str = "") -> Any:
    """获取 EagleScanner 实例。

    Args:
        eagle_root: Eagle 素材库根目录 (为空时使用默认路径)
    """
    from src.market_ops.creative_mapping_engine import EagleScanner
    root = eagle_root or str(_PROJECT_ROOT / "data" / "eagle_library")
    return EagleScanner(
        eagle_root=root,
        index_path=str(_PROJECT_ROOT / "data" / "eagle_scan_index.json"),
    )


@app.post("/api/creative-mapping/eagle/scan")
async def eagle_scan_full(req: dict) -> dict:
    """触发 Eagle 素材库全量扫描。

    请求体:
        eagle_root: Eagle 素材库根目录 (必填)
        extract_metadata: 是否使用 ffprobe 提取元数据 (默认 true)
    """
    eagle_root = req.get("eagle_root", "")
    if not eagle_root:
        raise HTTPException(status_code=400, detail="eagle_root is required")
    extract_metadata = req.get("extract_metadata", True)
    scanner = _get_eagle_scanner(eagle_root)
    scanner._extract_metadata = extract_metadata  # noqa: SLF001
    if not scanner.is_available:
        raise HTTPException(status_code=404, detail=f"Eagle root not found: {eagle_root}")
    report = scanner.scan_full()
    # 扫描后刷新 Creative Mapping Engine 缓存 (清空缓存，下次 match 时重新加载索引)
    engine = _get_creative_mapping_engine()
    engine._eagle_assets = None  # noqa: SLF001
    return report


@app.post("/api/creative-mapping/eagle/scan-incremental")
async def eagle_scan_incremental(req: dict) -> dict:
    """触发 Eagle 素材库增量扫描。

    请求体:
        eagle_root: Eagle 素材库根目录 (必填)
        extract_metadata: 是否使用 ffprobe 提取元数据 (默认 true)
    """
    eagle_root = req.get("eagle_root", "")
    if not eagle_root:
        raise HTTPException(status_code=400, detail="eagle_root is required")
    extract_metadata = req.get("extract_metadata", True)
    scanner = _get_eagle_scanner(eagle_root)
    scanner._extract_metadata = extract_metadata  # noqa: SLF001
    if not scanner.is_available:
        raise HTTPException(status_code=404, detail=f"Eagle root not found: {eagle_root}")
    report = scanner.scan_incremental()
    # 扫描后刷新 Creative Mapping Engine 缓存
    engine = _get_creative_mapping_engine()
    engine._eagle_assets = None  # noqa: SLF001 强制重新加载索引文件
    return report


@app.get("/api/creative-mapping/eagle/index")
async def eagle_index() -> dict:
    """查询当前 Eagle 素材索引。"""
    scanner = _get_eagle_scanner()
    return scanner.get_index()


@app.get("/api/creative-mapping/eagle/index/stats")
async def eagle_index_stats() -> dict:
    """查询 Eagle 素材索引统计摘要。"""
    scanner = _get_eagle_scanner()
    return scanner.get_stats()


@app.post("/api/creative-mapping/frame-similarity")
async def creative_mapping_frame_similarity(req: dict) -> dict:
    """手动计算两个素材的帧相似度。

    请求体:
        thumbnail_source: Facebook 缩略图 URL 或本地路径 (必填)
        eagle_path: Eagle 视频文件路径 (必填)
    """
    from src.market_ops.creative_mapping_engine import FrameSimilarityComputer

    thumbnail_source = req.get("thumbnail_source", "")
    eagle_path = req.get("eagle_path", "")
    if not thumbnail_source or not eagle_path:
        raise HTTPException(
            status_code=400,
            detail="thumbnail_source and eagle_path are required",
        )
    computer = FrameSimilarityComputer()
    score, method, cached = computer.compute(thumbnail_source, eagle_path)
    return {
        "score": score,
        "method": method,
        "cached": cached,
    }


@app.post("/api/creative-mapping/frame-similarity/batch")
async def creative_mapping_frame_similarity_batch(req: dict) -> dict:
    """批量计算帧相似度 (v1.3 性能优化)。

    请求体:
        pairs: [{"thumbnail_source": "...", "eagle_path": "..."}, ...]
    """
    import time as _time

    from src.market_ops.creative_mapping_engine import FrameSimilarityComputer

    pairs_raw = req.get("pairs", [])
    if not pairs_raw or not isinstance(pairs_raw, list):
        raise HTTPException(status_code=400, detail="pairs list is required")

    pairs: list[tuple[str, str]] = []
    for item in pairs_raw:
        thumb = item.get("thumbnail_source", "")
        eagle = item.get("eagle_path", "")
        pairs.append((thumb, eagle))

    computer = FrameSimilarityComputer()
    started = _time.time()
    results = computer.compute_batch(pairs)
    elapsed = round(_time.time() - started, 3)

    return {
        "results": [
            {"score": s, "method": m, "cached": c}
            for s, m, c in results
        ],
        "total": len(results),
        "elapsed_seconds": elapsed,
    }


@app.post("/api/creative-mapping/facebook/ingest")
async def creative_mapping_facebook_ingest(req: dict) -> dict:
    """拉取 Facebook 创意并自动映射 (v1.4)。

    请求体:
        ad_account_id: 广告账户 ID (可选，默认使用配置)
        lookback_days: 回溯天数 (默认 7)
        auto_map: 是否自动映射 (默认 true)
    """
    from src.market_ops.creative_mapping_engine import (
        FacebookCreativeIngester,
    )

    ad_account_id = req.get("ad_account_id", "")
    lookback_days = int(req.get("lookback_days", 7))
    auto_map = req.get("auto_map", True)

    engine = _get_creative_mapping_engine()

    # 尝试从环境变量构造 FacebookClient
    facebook_client = None
    try:
        from src.market_ops.facebook_ingestion.facebook_client import (
            FacebookClient,
        )

        token = _get_meta_access_token()
        account = ad_account_id or _get_meta_ad_account_id()
        if token and account:
            facebook_client = FacebookClient(
                access_token=token,
                ad_account_id=account,
            )
    except Exception:
        pass

    if facebook_client is None:
        raise HTTPException(
            status_code=503,
            detail="Facebook API credentials not configured (META_ACCESS_TOKEN/META_AD_ACCOUNT_ID)",
        )

    ingester = FacebookCreativeIngester(
        engine=engine,
        facebook_client=facebook_client,
    )
    result = ingester.ingest(
        ad_account_id=ad_account_id,
        lookback_days=lookback_days,
        auto_map=auto_map,
    )
    return result.to_dict()


@app.post("/api/creative-mapping/facebook/ingest-dry-run")
async def creative_mapping_facebook_ingest_dry_run(req: dict) -> dict:
    """dry_run 模式：使用提供的创意数据映射 (v1.4)。

    请求体:
        creatives: 创意数据列表
        auto_map: 是否自动映射 (默认 true)
    """
    from src.market_ops.creative_mapping_engine import (
        FacebookCreativeIngester,
    )

    creatives = req.get("creatives", [])
    if not creatives or not isinstance(creatives, list):
        raise HTTPException(
            status_code=400,
            detail="creatives list is required",
        )

    auto_map = req.get("auto_map", True)
    engine = _get_creative_mapping_engine()

    ingester = FacebookCreativeIngester(
        engine=engine,
        dry_run=True,
    )
    result = ingester.ingest_creatives(
        creatives=creatives,
        auto_map=auto_map,
    )
    return result.to_dict()


# ── v1.5 Delivery Bridge ─────────────────────────────────────


def _get_delivery_bridge():
    """获取 DeliveryBridge 单例 (绑定到 CreativeMappingEngine)。"""
    if not hasattr(_get_delivery_bridge, "_instance"):
        from src.market_ops.creative_mapping_engine import DeliveryBridge
        engine = _get_creative_mapping_engine()
        _get_delivery_bridge._instance = DeliveryBridge(
            engine=engine,
            data_dir=str(_PROJECT_ROOT / "data" / "creative_mapping"),
        )
    return _get_delivery_bridge._instance


def _get_insights_ingester():
    """获取 FacebookInsightsIngester 单例 (v1.7)。"""
    if not hasattr(_get_insights_ingester, "_instance"):
        from src.market_ops.creative_mapping_engine import FacebookInsightsIngester
        engine = _get_creative_mapping_engine()
        _get_insights_ingester._instance = FacebookInsightsIngester(
            engine=engine,
            data_dir=str(_PROJECT_ROOT / "data" / "creative_mapping"),
            dry_run=True,
        )
    return _get_insights_ingester._instance


def _get_strategy_optimizer():
    """获取 DeliveryStrategyOptimizer 单例 (v1.8)。"""
    if not hasattr(_get_strategy_optimizer, "_instance"):
        from src.market_ops.creative_mapping_engine import DeliveryStrategyOptimizer
        engine = _get_creative_mapping_engine()
        _get_strategy_optimizer._instance = DeliveryStrategyOptimizer(
            engine=engine,
            data_dir=str(_PROJECT_ROOT / "data" / "creative_mapping"),
        )
    return _get_strategy_optimizer._instance


@app.post("/api/creative-mapping/deliver")
async def creative_mapping_deliver(req: dict) -> dict:
    """单条投递：将映射记录的素材投递到 Facebook Ads (v1.5)。

    请求体:
        mapping_id: 映射记录 ID (必需)
        ad_account_id: Facebook 广告账户 ID (必需)
        campaign_id: 目标 Campaign ID (必需)
        adset_id: 目标 AdSet ID (必需)
        page_id: Facebook Page ID (必需)
        dry_run: True=模拟投递 (默认 true)
        creative_name: adcreative 标题 (可选)
        creative_body: adcreative 正文 (可选)
        access_token: Facebook API token (dry_run=false 时必需)
    """
    bridge = _get_delivery_bridge()
    mapping_id = req.get("mapping_id", "")
    if not mapping_id:
        raise HTTPException(status_code=400, detail="mapping_id is required")

    for field_name in ("ad_account_id", "campaign_id", "adset_id", "page_id"):
        if not req.get(field_name):
            raise HTTPException(
                status_code=400, detail=f"{field_name} is required"
            )

    result = bridge.dispatch(
        mapping_id=mapping_id,
        ad_account_id=req["ad_account_id"],
        campaign_id=req["campaign_id"],
        adset_id=req["adset_id"],
        page_id=req["page_id"],
        dry_run=req.get("dry_run", True),
        creative_name=req.get("creative_name", ""),
        creative_body=req.get("creative_body", ""),
        access_token=req.get("access_token", ""),
    )
    return result.to_dict()


@app.post("/api/creative-mapping/deliver-batch")
async def creative_mapping_deliver_batch(req: dict) -> dict:
    """批量投递：自动选取可投递记录批量推送 (v1.5)。

    请求体:
        ad_account_id / campaign_id / adset_id / page_id (必需)
        filter_status: 筛选 MappingStatus (可选)
        limit: 单次批量上限 (默认 5, 强制 ≤ 5)
        dry_run: 模拟投递 (默认 true)
        access_token: dry_run=false 时必需
    """
    bridge = _get_delivery_bridge()
    for field_name in ("ad_account_id", "campaign_id", "adset_id", "page_id"):
        if not req.get(field_name):
            raise HTTPException(
                status_code=400, detail=f"{field_name} is required"
            )

    filter_status_raw = req.get("filter_status")
    filter_status = None
    if filter_status_raw and isinstance(filter_status_raw, list):
        from src.market_ops.creative_mapping_engine import MappingStatus
        filter_status = [MappingStatus(s) for s in filter_status_raw]

    result = bridge.dispatch_batch(
        ad_account_id=req["ad_account_id"],
        campaign_id=req["campaign_id"],
        adset_id=req["adset_id"],
        page_id=req["page_id"],
        filter_status=filter_status,
        limit=req.get("limit", 5),
        dry_run=req.get("dry_run", True),
        access_token=req.get("access_token", ""),
    )
    return result.to_dict()


@app.get("/api/creative-mapping/deliverable")
async def creative_mapping_deliverable(limit: int = 50) -> dict:
    """查询可投递记录 (MATCHED/REVIEW_APPROVED + UNDISPATCHED/FAILED, v1.5)。"""
    bridge = _get_delivery_bridge()
    records = bridge.get_dispatchable(limit=limit)
    return {
        "records": [r.to_dict() for r in records],
        "count": len(records),
    }


@app.post("/api/creative-mapping/deliver-auto")
async def creative_mapping_deliver_auto(req: dict) -> dict:
    """自动创建投放结构并投递 (v1.6)。

    自动生成 Campaign + AdSet 配置 (CampaignStrategyBuilder)，
    可选真实创建结构 (FacebookPublisher) 并执行投递。

    请求体:
        mapping_id: 映射记录 ID (必需)
        ad_account_id: Facebook 广告账户 ID (必需)
        page_id: Facebook Page ID (必需)
        project_name: 项目名 (用于 Campaign/AdSet 命名, 必需)
        daily_budget: 日预算 USD (必需)
        countries: 投放国家列表 (必需, 非空)
        game_category: 游戏类别 (casual/hardcore/midcore, 默认 casual)
        adset_count: AdSet 数量 (默认 1)
        is_broad: 是否宽泛定向 (默认 false)
        target_cpi: 目标 CPI (可选)
        use_advantage_plus: 是否使用 ASC (默认 false)
        dry_run: 模拟模式 (默认 true)
        access_token: Facebook API token (dry_run=false 时必需)
        headlines: 广告标题列表 (可选)
        primary_texts: 广告正文列表 (可选)
    """
    bridge = _get_delivery_bridge()

    # 必需字段校验
    for field_name in ("mapping_id", "ad_account_id", "page_id", "project_name"):
        if not req.get(field_name):
            raise HTTPException(
                status_code=400, detail=f"{field_name} is required"
            )

    daily_budget = req.get("daily_budget")
    if daily_budget is None or float(daily_budget) <= 0:
        raise HTTPException(
            status_code=400, detail="daily_budget must be a positive number"
        )

    countries = req.get("countries")
    if not countries or not isinstance(countries, list):
        raise HTTPException(
            status_code=400, detail="countries must be a non-empty list"
        )

    result = bridge.dispatch_with_auto_structure(
        mapping_id=req["mapping_id"],
        ad_account_id=req["ad_account_id"],
        page_id=req["page_id"],
        project_name=req["project_name"],
        daily_budget=float(daily_budget),
        countries=countries,
        game_category=req.get("game_category", "casual"),
        adset_count=int(req.get("adset_count", 1)),
        is_broad=bool(req.get("is_broad", False)),
        target_cpi=req.get("target_cpi"),
        use_advantage_plus=bool(req.get("use_advantage_plus", False)),
        dry_run=req.get("dry_run", True),
        access_token=req.get("access_token", ""),
        headlines=req.get("headlines"),
        primary_texts=req.get("primary_texts"),
    )
    return result.to_dict()


# ── v1.7 成效反馈环 ────────────────────────────────────────────


@app.post("/api/creative-mapping/insights/ingest")
async def creative_mapping_insights_ingest(req: dict) -> dict:
    """拉取 Facebook insights 并回写成效数据 (v1.7)。

    请求体:
        start_date: 开始日期 YYYY-MM-DD (可选, 默认 lookback_days 天前)
        end_date: 结束日期 YYYY-MM-DD (可选, 默认今天)
        lookback_days: 回溯天数 (默认 7)
        dry_run: 模拟模式 (默认 true)
        access_token: Facebook API token (dry_run=false 时必需)
    """
    ingester = _get_insights_ingester()
    dry_run = req.get("dry_run", True)

    # 真实模式需要 facebook_client (需 access_token)
    if not dry_run:
        access_token = req.get("access_token", "")
        if not access_token:
            raise HTTPException(
                status_code=400, detail="access_token required for dry_run=false"
            )
        # 注入 facebook_client (生产环境)
        try:
            from src.market_ops.facebook_ingestion.facebook_client import FacebookClient
            ad_account_id = req.get("ad_account_id", "")
            if not ad_account_id:
                raise HTTPException(
                    status_code=400, detail="ad_account_id required for dry_run=false"
                )
            client = FacebookClient(
                access_token=access_token,
                ad_account_id=ad_account_id,
            )
            ingester._client = client
        except ImportError:
            raise HTTPException(
                status_code=500, detail="FacebookClient not available"
            )

    result = ingester.ingest_insights(
        start_date=req.get("start_date"),
        end_date=req.get("end_date"),
        lookback_days=int(req.get("lookback_days", 7)),
        dry_run=dry_run,
    )
    return result.to_dict()


@app.get("/api/creative-mapping/performance/{mapping_id}")
async def creative_mapping_performance(mapping_id: str) -> dict:
    """查询单条记录的成效数据 (v1.7)。"""
    ingester = _get_insights_ingester()
    result = ingester.get_performance(mapping_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "not found"))
    return result


@app.get("/api/creative-mapping/performance")
async def creative_mapping_performance_top(limit: int = 20) -> dict:
    """批量查询成效 (按 spend 降序 top N, v1.7)。"""
    ingester = _get_insights_ingester()
    performers = ingester.get_top_performers(limit=limit)
    return {
        "performers": performers,
        "count": len(performers),
    }


# ── v1.8 投放策略优化 ──────────────────────────────────────────


@app.post("/api/creative-mapping/strategy/evaluate")
async def creative_mapping_strategy_evaluate(req: dict) -> dict:
    """评估并自动归档低效素材 (v1.8)。

    请求体:
        dry_run: 模拟模式 (默认 true)
    """
    optimizer = _get_strategy_optimizer()
    dry_run = req.get("dry_run", True)
    result = optimizer.evaluate_and_archive(dry_run=dry_run)
    return result.to_dict()


@app.get("/api/creative-mapping/strategy/ranking")
async def creative_mapping_strategy_ranking(limit: int = 50) -> dict:
    """查询素材优先级排名 (v1.8)。"""
    optimizer = _get_strategy_optimizer()
    ranking = optimizer.rank_dispatchable(limit=limit)
    return {
        "ranking": ranking,
        "count": len(ranking),
    }


@app.get("/api/creative-mapping/strategy/summary")
async def creative_mapping_strategy_summary() -> dict:
    """查询策略优化摘要 (v1.8)。"""
    optimizer = _get_strategy_optimizer()
    return optimizer.get_strategy_summary()


@app.get("/api/creative-mapping/delivery/{mapping_id}")
async def creative_mapping_delivery_status(mapping_id: str) -> dict:
    """查询单条记录的投递状态 (v1.5)。"""
    bridge = _get_delivery_bridge()
    status = bridge.get_delivery_status(mapping_id)
    if not status.get("success"):
        raise HTTPException(status_code=404, detail=status.get("error", "not found"))
    return status


@app.post("/api/creative-mapping/delivery/{mapping_id}/retry")
async def creative_mapping_delivery_retry(mapping_id: str, req: dict) -> dict:
    """重试失败的投递 (v1.5)。

    请求体:
        ad_account_id / campaign_id / adset_id / page_id (必需)
        dry_run: 模拟投递 (默认 true)
        access_token: dry_run=false 时必需
    """
    bridge = _get_delivery_bridge()
    for field_name in ("ad_account_id", "campaign_id", "adset_id", "page_id"):
        if not req.get(field_name):
            raise HTTPException(
                status_code=400, detail=f"{field_name} is required"
            )

    result = bridge.redeliver(
        mapping_id=mapping_id,
        ad_account_id=req["ad_account_id"],
        campaign_id=req["campaign_id"],
        adset_id=req["adset_id"],
        page_id=req["page_id"],
        dry_run=req.get("dry_run", True),
        access_token=req.get("access_token", ""),
    )
    return result.to_dict()


# ── Market Intelligence Agent ─────────────────────────────────

def _get_market_intelligence_agent():
    """获取 MarketIntelligenceAgent 单例。"""
    if not hasattr(_get_market_intelligence_agent, "_instance"):
        from src.market_ops.workspace.market_intelligence_agent import (
            MarketIntelligenceAgent,
        )
        _get_market_intelligence_agent._instance = MarketIntelligenceAgent(
            data_dir=str(_PROJECT_ROOT / "data"),
        )
    return _get_market_intelligence_agent._instance


@app.get("/api/market-intelligence/analyze")
async def market_intelligence_analyze() -> dict:
    """综合市场分析。"""
    agent = _get_market_intelligence_agent()
    result = agent.analyze_market()
    return result.to_dict()


@app.get("/api/market-intelligence/trends")
async def market_intelligence_trends() -> dict:
    """趋势检测。"""
    agent = _get_market_intelligence_agent()
    trends = agent.detect_trends()
    return {"total": len(trends), "trends": trends}


@app.get("/api/market-intelligence/competitors")
async def market_intelligence_competitors() -> dict:
    """竞品追踪。"""
    agent = _get_market_intelligence_agent()
    competitors = agent.track_competitors()
    return {"total": len(competitors), "competitors": competitors}


@app.get("/api/market-intelligence/creative-signals")
async def market_intelligence_creative_signals() -> dict:
    """创意信号挖掘。"""
    agent = _get_market_intelligence_agent()
    signals = agent.mine_creative_signals()
    return {"total": len(signals), "creative_signals": signals}


@app.get("/api/market-intelligence/heatmap")
async def market_intelligence_heatmap() -> dict:
    """品类热度图。"""
    agent = _get_market_intelligence_agent()
    return agent.get_category_heatmap()


@app.get("/api/market-intelligence/opportunities")
async def market_intelligence_opportunities() -> dict:
    """机会生成。"""
    agent = _get_market_intelligence_agent()
    opportunities = agent.generate_opportunities()
    return {"total": len(opportunities), "opportunities": opportunities}


@app.get("/api/market-intelligence/report")
async def market_intelligence_report() -> dict:
    """市场报告。"""
    agent = _get_market_intelligence_agent()
    report = agent.get_market_report()
    return report.to_dict()


@app.get("/api/market-intelligence/stats")
async def market_intelligence_stats() -> dict:
    """统计信息。"""
    agent = _get_market_intelligence_agent()
    return agent.get_stats()


# ── 周期报告生成 ──────────────────────────────────────────────

def _get_period_report_generator():
    """获取 PeriodReportGenerator 单例（懒加载）.

    数据目录使用项目 data/ 目录。
    """
    if not hasattr(_get_period_report_generator, "_instance"):
        from src.market_ops.workspace.period_report_generator import PeriodReportGenerator
        _get_period_report_generator._instance = PeriodReportGenerator(
            data_dir=str(_PROJECT_ROOT / "data"),
        )
    return _get_period_report_generator._instance


@app.post("/api/reports/generate")
async def generate_report(req: dict) -> dict:
    """生成报告。

    请求体:
        report_type: executive|growth|monetization|ua|creative|portfolio
        period: daily|weekly|monthly
        end_date: YYYY-MM-DD (可选)
        game_ids: [game_id, ...] (可选)
    """
    from src.market_ops.workspace.period_report_generator import ReportPeriod, ReportType

    report_type = req.get("report_type", "")
    period = req.get("period", "")

    if not ReportType.is_valid(report_type):
        raise HTTPException(
            status_code=400,
            detail=f"无效的 report_type: {report_type}, 可选: {ReportType.all()}",
        )
    if not ReportPeriod.is_valid(period):
        raise HTTPException(
            status_code=400,
            detail=f"无效的 period: {period}, 可选: {ReportPeriod.all()}",
        )

    end_date = req.get("end_date") or None
    game_ids = req.get("game_ids") or None

    generator = _get_period_report_generator()
    try:
        report = generator.generate_report(
            report_type=report_type,
            period=period,
            end_date=end_date,
            game_ids=game_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return report.to_dict()


@app.get("/api/reports")
async def list_reports(
    period: str = "",
    report_type: str = "",
) -> dict:
    """列出报告。

    查询参数:
        period: daily|weekly|monthly (可选)
        report_type: executive|growth|monetization|ua|creative|portfolio (可选)
    """
    generator = _get_period_report_generator()
    period_arg = period or None
    type_arg = report_type or None
    reports = generator.list_reports(period=period_arg, report_type=type_arg)
    return {
        "total": len(reports),
        "reports": [r.to_dict() for r in reports],
    }


@app.get("/api/reports/stats")
async def reports_stats() -> dict:
    """报告统计。"""
    generator = _get_period_report_generator()
    return generator.get_stats()


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str) -> dict:
    """获取报告详情。"""
    generator = _get_period_report_generator()
    report = generator.get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"报告不存在: {report_id}",
        )
    return report.to_dict()


# ── 游戏退役编排 ──────────────────────────────────────────────

def _get_retirement_orchestrator():
    """获取 GameRetirementOrchestrator 单例 (绑定到项目 data 目录)."""
    if not hasattr(_get_retirement_orchestrator, "_instance"):
        from src.market_ops.workspace.retirement_orchestrator import (
            GameRetirementOrchestrator,
        )
        _get_retirement_orchestrator._instance = GameRetirementOrchestrator(
            data_dir=str(_PROJECT_ROOT / "data"),
        )
    return _get_retirement_orchestrator._instance


@app.post("/api/retirement/evaluate")
async def retirement_evaluate(req: dict) -> dict:
    """评估游戏退役条件.

    请求体:
        game_id: 游戏 ID (必需)
        metrics: {"roas_d30": 0.5, "ltv_d30": 0.3, "d1_retention": 0.25}
        thresholds: 可选, {"roas_d30_min": 0.8, ...} (默认使用 DEFAULT_THRESHOLDS)

    返回 RetirementDecision.
    """
    game_id = req.get("game_id", "")
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id is required")
    metrics = req.get("metrics", {})
    if not isinstance(metrics, dict) or not metrics:
        raise HTTPException(
            status_code=400, detail="metrics must be a non-empty dict"
        )
    thresholds = req.get("thresholds")
    orch = _get_retirement_orchestrator()
    decision = orch.evaluate_retirement(
        game_id=game_id,
        metrics=metrics,
        thresholds=thresholds if isinstance(thresholds, dict) else None,
    )
    return decision.to_dict()


@app.post("/api/retirement/plan")
async def retirement_create_plan(req: dict) -> dict:
    """创建退役计划.

    请求体:
        decision: RetirementDecision 字典 (必需, 来自 /evaluate)
            必须包含 game_id / trigger / metrics / threshold_values /
            decision / confidence / decided_at / decided_by
    """
    decision_data = req.get("decision")
    if not isinstance(decision_data, dict):
        raise HTTPException(
            status_code=400, detail="decision dict is required"
        )
    from src.market_ops.workspace.retirement_orchestrator import (
        RetirementDecision,
    )
    try:
        decision = RetirementDecision(
            game_id=decision_data.get("game_id", ""),
            trigger=decision_data.get("trigger", "manual_decision"),
            metrics=decision_data.get("metrics", {}),
            threshold_values=decision_data.get("threshold_values", {}),
            decision=decision_data.get("decision", "review"),
            confidence=float(decision_data.get("confidence", 0.0)),
            decided_at=decision_data.get("decided_at", ""),
            decided_by=decision_data.get("decided_by", "auto"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"invalid decision payload: {exc}"
        ) from exc
    orch = _get_retirement_orchestrator()
    plan = orch.create_plan(decision)
    return plan.to_dict()


@app.post("/api/retirement/execute")
async def retirement_execute(req: dict) -> dict:
    """执行退役流程.

    请求体:
        plan_id: 退役计划 ID (必需)
        dry_run: True=只编排不执行 (默认 true)
    """
    plan_id = req.get("plan_id", "")
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")
    orch = _get_retirement_orchestrator()
    plan = orch.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404, detail=f"Plan {plan_id} not found"
        )
    dry_run = req.get("dry_run", True)
    if not isinstance(dry_run, bool):
        dry_run = bool(dry_run)
    try:
        updated = orch.execute_retirement(plan, dry_run=dry_run)
        return updated.to_dict()
    except Exception as exc:
        logger.exception("Retirement execution failed for plan %s", plan_id)
        raise HTTPException(
            status_code=500,
            detail=f"Retirement execution failed: {exc}",
        ) from exc


@app.get("/api/retirement/plans")
async def retirement_list_plans(status: str = "") -> dict:
    """列出退役计划 (可按 current_stage 过滤)."""
    orch = _get_retirement_orchestrator()
    filter_status = status if status else None
    plans = orch.list_plans(status=filter_status)
    return {
        "plans": [p.to_dict() for p in plans],
        "count": len(plans),
    }


@app.get("/api/retirement/plans/{plan_id}")
async def retirement_get_plan(plan_id: str) -> dict:
    """获取退役计划详情."""
    orch = _get_retirement_orchestrator()
    plan = orch.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404, detail=f"Plan {plan_id} not found"
        )
    return plan.to_dict()


@app.post("/api/retirement/cancel/{plan_id}")
async def retirement_cancel(plan_id: str) -> dict:
    """取消退役.

    已 COMPLETED / FAILED / CANCELLED 的计划不可取消.
    """
    orch = _get_retirement_orchestrator()
    plan = orch.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404, detail=f"Plan {plan_id} not found"
        )
    success = orch.cancel_retirement(plan_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Plan {plan_id} cannot be cancelled (status={plan.current_stage})",
        )
    updated = orch.get_plan(plan_id)
    return updated.to_dict() if updated else {"plan_id": plan_id, "cancelled": True}


@app.get("/api/retirement/stats")
async def retirement_stats() -> dict:
    """退役统计."""
    orch = _get_retirement_orchestrator()
    return orch.get_stats()


# ── 截图自动渲染 ──────────────────────────────────────────────

def _get_screenshot_renderer():
    """获取 ScreenshotRenderer 单例 (输出到 data/screenshots/)."""
    if not hasattr(_get_screenshot_renderer, "_instance"):
        from .screenshot_renderer import ScreenshotRenderer
        _get_screenshot_renderer._instance = ScreenshotRenderer(
            output_dir=str(_PROJECT_ROOT / "data" / "screenshots")
        )
    return _get_screenshot_renderer._instance


@app.post("/api/screenshots/render")
async def render_screenshot(req: dict) -> dict:
    """渲染单个截图。

    请求体 (均可选, 除 game_id):
        game_id, device_type, headline, subheadline, cta,
        palette, layout, background_color, text_color, accent_color,
        image_path, dimensions (可选, [w, h])
    """
    game_id = req.get("game_id", "")
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id is required")

    renderer = _get_screenshot_renderer()
    # 若提供 palette/device_type 则走 create_spec (自动推导配色与尺寸)
    palette = req.get("palette", "vibrant")
    device_type = req.get("device_type", "iphone_6.7")
    try:
        spec = renderer.create_spec(
            game_id=game_id,
            device_type=device_type,
            headline=req.get("headline", ""),
            subheadline=req.get("subheadline", ""),
            cta=req.get("cta", ""),
            palette=palette,
            layout=req.get("layout", "top_text_bottom_image"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 显式覆盖 (高级用户自定义颜色/尺寸/背景图)
    if req.get("background_color"):
        spec.background_color = req["background_color"]
    if req.get("text_color"):
        spec.text_color = req["text_color"]
    if req.get("accent_color"):
        spec.accent_color = req["accent_color"]
    if req.get("image_path"):
        spec.image_path = req["image_path"]
    if req.get("dimensions") and isinstance(req["dimensions"], (list, tuple)) \
            and len(req["dimensions"]) == 2:
        spec.dimensions = (int(req["dimensions"][0]), int(req["dimensions"][1]))

    rendered = renderer.render(spec)
    return rendered.to_dict()


@app.post("/api/screenshots/render-batch")
async def render_screenshots_batch(req: dict) -> dict:
    """批量渲染截图。

    请求体:
        specs: [ {game_id, device_type, headline, ...}, ... ]
    """
    specs_payload = req.get("specs", [])
    if not specs_payload or not isinstance(specs_payload, list):
        raise HTTPException(
            status_code=400, detail="specs (non-empty list) is required"
        )

    renderer = _get_screenshot_renderer()
    specs: list = []
    for item in specs_payload:
        if not isinstance(item, dict) or not item.get("game_id"):
            raise HTTPException(
                status_code=400, detail="每个 spec 必须包含 game_id"
            )
        try:
            spec = renderer.create_spec(
                game_id=item["game_id"],
                device_type=item.get("device_type", "iphone_6.7"),
                headline=item.get("headline", ""),
                subheadline=item.get("subheadline", ""),
                cta=item.get("cta", ""),
                palette=item.get("palette", "vibrant"),
                layout=item.get("layout", "top_text_bottom_image"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if item.get("image_path"):
            spec.image_path = item["image_path"]
        specs.append(spec)

    rendered = renderer.render_batch(specs)
    return {
        "count": len(rendered),
        "results": [r.to_dict() for r in rendered],
    }


@app.get("/api/screenshots")
async def list_screenshots(game_id: str = "") -> dict:
    """列出已渲染的截图 (可按 game_id 过滤)."""
    renderer = _get_screenshot_renderer()
    rendered = renderer.list_rendered(game_id or None)
    return {
        "count": len(rendered),
        "items": [r.to_dict() for r in rendered],
    }


@app.get("/api/screenshots/stats")
async def screenshots_stats() -> dict:
    """截图统计."""
    renderer = _get_screenshot_renderer()
    return renderer.get_stats()


@app.get("/api/screenshots/devices")
async def list_devices() -> dict:
    """列出支持的设备尺寸预设."""
    renderer = _get_screenshot_renderer()
    return {
        name: list(dim) for name, dim in renderer.DEVICE_DIMENSIONS.items()
    }


@app.get("/api/screenshots/palettes")
async def list_palettes() -> dict:
    """列出支持的配色方案预设."""
    renderer = _get_screenshot_renderer()
    return renderer.PALETTES


# ── Eagle 素材自动打标签 (CME v1.9) ────────────────────────────

def _get_eagle_tagger():
    """获取 EagleAssetTagger 单例。"""
    if not hasattr(_get_eagle_tagger, "_instance"):
        from src.market_ops.creative_mapping_engine import EagleAssetTagger
        _get_eagle_tagger._instance = EagleAssetTagger()
    return _get_eagle_tagger._instance


def _get_eagle_tag_store():
    """获取 EagleTagStore 单例。"""
    if not hasattr(_get_eagle_tag_store, "_instance"):
        from src.market_ops.creative_mapping_engine import EagleTagStore
        _get_eagle_tag_store._instance = EagleTagStore()
    return _get_eagle_tag_store._instance


@app.post("/api/creative-mapping/eagle-tagger/tag")
async def eagle_tagger_tag(req: dict) -> dict:
    """对单个素材打标签 (CLIP 零样本分类)。

    请求体:
        asset_path: 素材文件路径 (必需, 图片或视频)
        top_k: 返回 top-K 标签 (可选, 默认 5)
        min_confidence: 置信度阈值 (可选, 默认 0.15)
        save: 是否持久化到 data/eagle_tags/ (可选, 默认 true)
    """
    asset_path = req.get("asset_path", "")
    if not asset_path:
        raise HTTPException(status_code=400, detail="asset_path is required")

    tagger = _get_eagle_tagger()
    result = tagger.tag_asset(
        asset_path=asset_path,
        top_k=req.get("top_k"),
        min_confidence=req.get("min_confidence"),
    )

    if req.get("save", True) and result.is_success:
        store = _get_eagle_tag_store()
        store.save(result)

    return result.to_dict()


@app.post("/api/creative-mapping/eagle-tagger/tag-batch")
async def eagle_tagger_tag_batch(req: dict) -> dict:
    """批量打标签。

    请求体:
        asset_paths: 素材路径列表 (必需)
        top_k: 返回 top-K 标签 (可选)
        min_confidence: 置信度阈值 (可选)
        save: 是否持久化 (可选, 默认 true)
    """
    asset_paths = req.get("asset_paths", [])
    if not asset_paths or not isinstance(asset_paths, list):
        raise HTTPException(
            status_code=400, detail="asset_paths (non-empty list) is required"
        )

    tagger = _get_eagle_tagger()
    results = tagger.tag_batch(
        asset_paths=asset_paths,
        top_k=req.get("top_k"),
        min_confidence=req.get("min_confidence"),
    )

    saved_count = 0
    if req.get("save", True):
        store = _get_eagle_tag_store()
        for r in results:
            if r.is_success:
                store.save(r)
                saved_count += 1

    return {
        "total": len(results),
        "success": sum(1 for r in results if r.is_success),
        "failed": sum(1 for r in results if not r.is_success),
        "saved": saved_count,
        "results": [r.to_dict() for r in results],
    }


@app.get("/api/creative-mapping/eagle-tagger/tags")
async def eagle_tagger_list_tags() -> dict:
    """查询所有已打标签的素材。"""
    store = _get_eagle_tag_store()
    all_results = store.load_all()
    return {
        "total": len(all_results),
        "tags": [r.to_dict() for r in all_results],
    }


@app.get("/api/creative-mapping/eagle-tagger/tags/{asset_id}")
async def eagle_tagger_get_tags(asset_id: str) -> dict:
    """查询单个素材的标签。"""
    store = _get_eagle_tag_store()
    result = store.load(asset_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"no tags found for asset_id: {asset_id}"
        )
    return result.to_dict()


@app.delete("/api/creative-mapping/eagle-tagger/tags/{asset_id}")
async def eagle_tagger_delete_tags(asset_id: str) -> dict:
    """删除单个素材的标签。"""
    store = _get_eagle_tag_store()
    deleted = store.delete(asset_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"no tags found for asset_id: {asset_id}"
        )
    return {"deleted": True, "asset_id": asset_id}


@app.get("/api/creative-mapping/eagle-tagger/stats")
async def eagle_tagger_stats() -> dict:
    """标签存储统计 + Tagger 状态。"""
    store = _get_eagle_tag_store()
    tagger = _get_eagle_tagger()
    return {
        "store": store.get_stats(),
        "tagger": {
            "clip_available": tagger.is_clip_available(),
            "backend": tagger.backend,
            "device": tagger.device,
            "vocabulary_size": tagger.total_tags_in_vocabulary,
            "categories": tagger.categories,
            "embedding_cache_size": tagger.embedding_cache_size,
        },
    }


@app.get("/api/creative-mapping/eagle-tagger/vocabulary")
async def eagle_tagger_vocabulary() -> dict:
    """查看标签词表。"""
    from src.market_ops.creative_mapping_engine.eagle_tagger import DEFAULT_TAG_VOCABULARY
    return {
        "categories": {
            category: tags
            for category, tags in DEFAULT_TAG_VOCABULARY.items()
        },
        "total_tags": sum(len(v) for v in DEFAULT_TAG_VOCABULARY.values()),
    }


# ── Credential Health Checker ─────────────────────────────────

@app.get("/api/credentials/health")
async def credential_health_summary() -> dict:
    """凭证健康检查摘要 (本地配置检查, 不含实时验证)."""
    from .credential_health_checker import get_credential_health_checker
    checker = get_credential_health_checker()
    report = checker.check_all(include_real_time=False)
    return report.to_dict()


@app.get("/api/credentials/health/detail")
async def credential_health_detail() -> dict:
    """凭证健康检查详情 (含每项检查的完整信息)."""
    from .credential_health_checker import get_credential_health_checker
    checker = get_credential_health_checker()
    report = checker.check_all(include_real_time=False)
    return report.to_dict()


@app.get("/api/credentials/canary-check")
async def credential_canary_check() -> dict:
    """金丝雀前置条件检查 (E1-E3 + Meta token 实时验证)."""
    from .credential_health_checker import get_credential_health_checker
    checker = get_credential_health_checker()
    report = checker.check_canary_prerequisites()
    return report.to_dict()


@app.post("/api/credentials/real-time-check")
async def credential_real_time_check() -> dict:
    """触发包含实时 Meta token 验证的完整凭证检查."""
    from .credential_health_checker import get_credential_health_checker
    checker = get_credential_health_checker()
    report = checker.check_all(include_real_time=True)
    return report.to_dict()


# ── ASO Keyword Research (aso-mcp) ────────────────────────────

@app.get("/api/aso/status")
async def aso_status() -> dict:
    """检查 aso-mcp 安装和认证状态."""
    from .aso_keyword_researcher import get_aso_keyword_researcher
    researcher = get_aso_keyword_researcher()
    return researcher.check_status()


@app.post("/api/aso/keywords/research")
async def aso_keywords_research(body: dict) -> dict:
    """关键词 ASO 指标研究 (热度/难度/品牌词).

    请求体:
        keywords: List[str]      关键词列表
        min_popularity: int      最小热度 (默认 6)
        max_difficulty: int      最大难度 (默认 70)
    """
    from .aso_keyword_researcher import get_aso_keyword_researcher
    researcher = get_aso_keyword_researcher()

    keywords = body.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    min_pop = body.get("min_popularity", 6)
    max_diff = body.get("max_difficulty", 70)

    result = researcher.research_keywords(
        keywords=keywords,
        min_popularity=min_pop,
        max_difficulty=max_diff,
    )
    return result.to_dict()


@app.post("/api/aso/keywords/research-single")
async def aso_keywords_research_single(body: dict) -> dict:
    """单个关键词 ASO 研究 (便捷接口)."""
    from .aso_keyword_researcher import get_aso_keyword_researcher
    researcher = get_aso_keyword_researcher()

    keyword = body.get("keyword", "")
    if not keyword:
        return {"error": "keyword 不能为空"}

    result = researcher.research_single(keyword)
    return result.to_dict()


def main() -> None:
    """CLI 入口: python -m market_ops.workspace.app"""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
