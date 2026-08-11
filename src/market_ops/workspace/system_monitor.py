"""系统监控模块 — 统一聚合所有子系统监控指标.

聚合数据源:
  1. GrowthLoop cycle_history.jsonl — 执行成功率/动作统计
  2. LiveOps campaign_executions.jsonl — 活动执行状态分布
  3. ChurnAlertBridge churn_responses.jsonl — Growth 响应统计
  4. CEO approval_queue.jsonl — 审批队列监控
  5. JSONL 文件系统 — 数据量/增长率监控
  6. API 端点可用性 — 健康检查

输出:
  - SystemHealth: 系统整体健康概览
  - AlertList: 告警列表 (阈值检测)
  - 各子系统统计指标

用法:
    monitor = SystemMonitor(data_dir="data")
    health = monitor.get_system_health()
    alerts = monitor.get_alerts()
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 告警阈值 ──────────────────────────────────────────────────
ALERT_PENDING_APPROVAL_THRESHOLD = 10       # pending 审批超过 10 条告警
ALERT_SUCCESS_RATE_THRESHOLD = 0.8          # 成功率低于 80% 告警
ALERT_JSONL_SIZE_MB_THRESHOLD = 50          # JSONL 文件超过 50MB 告警
ALERT_STALE_HOURS_THRESHOLD = 24            # JSONL 超过 24 小时未更新告警


class SystemMonitor:
    """系统监控器 — 聚合所有子系统监控指标.

    职责:
      1. 聚合 GrowthLoop / LiveOps / ChurnAlert / CEO 审批的执行统计
      2. 监控 JSONL 数据文件 (大小/记录数/最近更新时间)
      3. 检测告警 (阈值检测)
      4. 提供系统健康概览 (healthy/degraded/critical)

    不职责:
      - 不直接修改任何数据 (只读)
      - 不发送通知 (告警仅返回列表, 由调用方决定通知方式)
    """

    # 监控的 JSONL 文件清单 (相对 data_dir 的路径)
    MONITORED_FILES = {
        "growth_loop_history": "growth_loop/cycle_history.jsonl",
        "liveops_executions": "liveops/campaign_executions.jsonl",
        "churn_responses": "growth/churn_responses.jsonl",
        "churn_audit": "growth/churn_response_audit.jsonl",
        "ceo_approval_queue": "ceo/approval_queue.jsonl",
        "ceo_execution_memory": "ceo/execution_memory.jsonl",
        "ceo_execution_experience": "ceo/execution_experience.jsonl",
        "operator_runs": "operator_demo/runs.jsonl",
    }

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)

    # ── 系统健康概览 ─────────────────────────────────────────

    def get_system_health(self) -> dict[str, Any]:
        """系统整体健康概览 — 供 /healthz 和 Dashboard.

        Returns:
            {
                "status": "healthy" | "degraded" | "critical",
                "timestamp": ISO8601,
                "uptime_info": {...},
                "subsystems": {...},
                "alerts_count": N,
            }
        """
        alerts = self.get_alerts()
        critical_count = sum(1 for a in alerts if a["severity"] == "critical")
        warning_count = sum(1 for a in alerts if a["severity"] == "warning")

        if critical_count > 0:
            status = "critical"
        elif warning_count > 0:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subsystems": {
                "growth_loop": self._get_growth_loop_stats(),
                "liveops": self._get_liveops_stats(),
                "churn_alert": self._get_churn_alert_stats(),
                "approval_queue": self._get_approval_queue_stats(),
            },
            "data_files": self._get_file_stats(),
            "alerts_count": len(alerts),
            "critical_alerts": critical_count,
            "warning_alerts": warning_count,
        }

    # ── 告警检测 ─────────────────────────────────────────────

    def get_alerts(self) -> list[dict[str, Any]]:
        """检测所有告警 — 阈值检测.

        Returns:
            告警列表, 每条含:
              - alert_id: 唯一标识
              - severity: critical | warning | info
              - category: growth_loop | liveops | churn_alert | approval | data_file
              - message: 告警描述
              - current_value: 当前值
              - threshold: 阈值
              - suggestion: 修复建议
        """
        alerts: list[dict[str, Any]] = []

        # 1. GrowthLoop 成功率告警
        gl_stats = self._get_growth_loop_stats()
        if gl_stats["total_cycles"] > 0:
            success_rate = gl_stats["success_rate"]
            if success_rate < ALERT_SUCCESS_RATE_THRESHOLD:
                alerts.append({
                    "alert_id": "gl_low_success_rate",
                    "severity": "critical" if success_rate < 0.5 else "warning",
                    "category": "growth_loop",
                    "message": f"GrowthLoop 成功率 {success_rate:.1%} 低于阈值 {ALERT_SUCCESS_RATE_THRESHOLD:.0%}",
                    "current_value": success_rate,
                    "threshold": ALERT_SUCCESS_RATE_THRESHOLD,
                    "suggestion": "检查最近的 cycle 执行结果, 定位失败动作",
                })

        # 2. LiveOps 成功率告警
        lo_stats = self._get_liveops_stats()
        if lo_stats["total_executions"] > 0:
            lo_success_rate = lo_stats["success_rate"]
            if lo_success_rate < ALERT_SUCCESS_RATE_THRESHOLD:
                alerts.append({
                    "alert_id": "lo_low_success_rate",
                    "severity": "warning",
                    "category": "liveops",
                    "message": f"LiveOps 活动成功率 {lo_success_rate:.1%} 低于阈值",
                    "current_value": lo_success_rate,
                    "threshold": ALERT_SUCCESS_RATE_THRESHOLD,
                    "suggestion": "检查 campaign_executions.jsonl 中的 failed 记录",
                })

        # 3. 审批队列积压告警
        aq_stats = self._get_approval_queue_stats()
        pending_total = aq_stats["ceo_pending"] + aq_stats["liveops_pending"]
        if pending_total >= ALERT_PENDING_APPROVAL_THRESHOLD:
            alerts.append({
                "alert_id": "approval_backlog",
                "severity": "warning",
                "category": "approval",
                "message": f"待审批积压 {pending_total} 条 (CEO {aq_stats['ceo_pending']} + LiveOps {aq_stats['liveops_pending']})",
                "current_value": pending_total,
                "threshold": ALERT_PENDING_APPROVAL_THRESHOLD,
                "suggestion": "及时处理 pending 审批, 避免 UA 动作阻塞",
            })

        # 4. JSONL 文件大小告警
        for name, stats in self._get_file_stats().items():
            if stats["exists"] and stats["size_mb"] > ALERT_JSONL_SIZE_MB_THRESHOLD:
                alerts.append({
                    "alert_id": f"file_size_{name}",
                    "severity": "warning",
                    "category": "data_file",
                    "message": f"{name} 文件 {stats['size_mb']:.1f}MB 超过阈值 {ALERT_JSONL_SIZE_MB_THRESHOLD}MB",
                    "current_value": stats["size_mb"],
                    "threshold": ALERT_JSONL_SIZE_MB_THRESHOLD,
                    "suggestion": "考虑归档历史数据或轮转 JSONL 文件",
                })

        # 5. JSONL 文件过期告警
        for name, stats in self._get_file_stats().items():
            if stats["exists"] and stats["hours_since_update"] > ALERT_STALE_HOURS_THRESHOLD:
                alerts.append({
                    "alert_id": f"file_stale_{name}",
                    "severity": "info",
                    "category": "data_file",
                    "message": f"{name} 已 {stats['hours_since_update']:.0f} 小时未更新",
                    "current_value": stats["hours_since_update"],
                    "threshold": ALERT_STALE_HOURS_THRESHOLD,
                    "suggestion": "检查相关子系统是否正常运行",
                })

        return alerts

    # ── 子系统统计 ───────────────────────────────────────────

    def _get_growth_loop_stats(self) -> dict[str, Any]:
        """GrowthLoop 执行统计."""
        path = self.data_dir / self.MONITORED_FILES["growth_loop_history"]
        if not path.exists():
            return self._empty_gl_stats()

        records = self._read_jsonl(path)
        if not records:
            return self._empty_gl_stats()

        total_cycles = len(records)
        total_actions_planned = sum(r.get("actions_planned", 0) for r in records)
        total_actions_executed = sum(r.get("actions_executed", 0) for r in records)
        total_actions_rolled_back = sum(r.get("actions_rolled_back", 0) for r in records)

        # 成功率: 从 execution_results 计算
        total_success = 0
        total_results = 0
        for r in records:
            for er in r.get("execution_results", []) or []:
                if isinstance(er, dict):
                    total_results += 1
                    if er.get("success"):
                        total_success += 1

        success_rate = total_success / max(total_results, 1)

        # 最近一次 cycle
        latest = records[-1] if records else {}
        latest_cycle = {
            "cycle_number": latest.get("cycle_number", 0),
            "completed_at": latest.get("completed_at", ""),
            "actions_planned": latest.get("actions_planned", 0),
            "actions_executed": latest.get("actions_executed", 0),
            "duration_ms": latest.get("duration_ms", 0),
        }

        return {
            "total_cycles": total_cycles,
            "total_actions_planned": total_actions_planned,
            "total_actions_executed": total_actions_executed,
            "total_actions_rolled_back": total_actions_rolled_back,
            "success_rate": round(success_rate, 4),
            "latest_cycle": latest_cycle,
        }

    def _empty_gl_stats(self) -> dict[str, Any]:
        return {
            "total_cycles": 0,
            "total_actions_planned": 0,
            "total_actions_executed": 0,
            "total_actions_rolled_back": 0,
            "success_rate": 0.0,
            "latest_cycle": {},
        }

    def _get_liveops_stats(self) -> dict[str, Any]:
        """LiveOps 执行统计 (从 campaign_executions.jsonl 聚合)."""
        path = self.data_dir / self.MONITORED_FILES["liveops_executions"]
        if not path.exists():
            return {
                "total_executions": 0,
                "completed": 0,
                "blocked": 0,
                "dry_run": 0,
                "failed": 0,
                "success_rate": 0.0,
            }

        records = self._read_jsonl(path)
        # 按 execution_id 去重 (保留最新)
        latest: dict[str, dict] = {}
        for r in records:
            exec_id = r.get("execution_id", "")
            latest[exec_id] = r

        total = len(latest)
        status_counts: dict[str, int] = {}
        for r in latest.values():
            status = r.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        completed = status_counts.get("completed", 0)
        success_rate = completed / max(total, 1)

        return {
            "total_executions": total,
            "completed": completed,
            "blocked": status_counts.get("blocked", 0),
            "dry_run": status_counts.get("dry_run", 0),
            "failed": status_counts.get("failed", 0),
            "success_rate": round(success_rate, 4),
        }

    def _get_churn_alert_stats(self) -> dict[str, Any]:
        """ChurnAlertBridge 响应统计."""
        path = self.data_dir / self.MONITORED_FILES["churn_responses"]
        if not path.exists():
            return {
                "total_responses": 0,
                "executed": 0,
                "rolled_back": 0,
                "suggested": 0,
            }

        records = self._read_jsonl(path)
        # 按 response_id 去重 (保留最新)
        latest: dict[str, dict] = {}
        for r in records:
            rid = r.get("response_id", "")
            latest[rid] = r

        status_counts: dict[str, int] = {}
        for r in latest.values():
            status = r.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_responses": len(latest),
            "executed": status_counts.get("executed", 0),
            "rolled_back": status_counts.get("rolled_back", 0),
            "suggested": status_counts.get("suggested", 0),
            "partial_executed": status_counts.get("partial_executed", 0),
        }

    def _get_approval_queue_stats(self) -> dict[str, Any]:
        """审批队列统计 (CEO + LiveOps)."""
        # CEO 决策审批
        ceo_path = self.data_dir / self.MONITORED_FILES["ceo_approval_queue"]
        ceo_pending = 0
        oldest_ceo_pending_hours = 0.0
        if ceo_path.exists():
            records = self._read_jsonl(ceo_path)
            now = datetime.now(timezone.utc)
            # 先收集已有 resolution 的 audit_id (approve/reject 时 append 的记录)
            resolved_ids = {
                r.get("audit_id") for r in records
                if r.get("kind") == "resolution"
            }
            for r in records:
                if (r.get("status") == "pending"
                        and not r.get("executed")
                        and r.get("audit_id") not in resolved_ids):
                    ceo_pending += 1
                    created = r.get("created_at", "")
                    if created:
                        try:
                            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                            hours = (now - created_dt).total_seconds() / 3600
                            if hours > oldest_ceo_pending_hours:
                                oldest_ceo_pending_hours = hours
                        except (ValueError, TypeError):
                            pass

        # LiveOps 活动审批
        liveops_path = self.data_dir / self.MONITORED_FILES["liveops_executions"]
        liveops_pending = 0
        if liveops_path.exists():
            records = self._read_jsonl(liveops_path)
            latest: dict[str, dict] = {}
            for r in records:
                exec_id = r.get("execution_id", "")
                latest[exec_id] = r
            for r in latest.values():
                if r.get("status") == "blocked":
                    liveops_pending += 1

        return {
            "ceo_pending": ceo_pending,
            "liveops_pending": liveops_pending,
            "total_pending": ceo_pending + liveops_pending,
            "oldest_ceo_pending_hours": round(oldest_ceo_pending_hours, 1),
        }

    # ── 文件监控 ─────────────────────────────────────────────

    def _get_file_stats(self) -> dict[str, dict[str, Any]]:
        """监控所有 JSONL 文件的大小/记录数/最近更新时间."""
        stats: dict[str, dict[str, Any]] = {}
        now = datetime.now(timezone.utc).timestamp()

        for name, rel_path in self.MONITORED_FILES.items():
            path = self.data_dir / rel_path
            if not path.exists():
                stats[name] = {
                    "exists": False,
                    "path": rel_path,
                    "size_mb": 0.0,
                    "record_count": 0,
                    "last_modified": "",
                    "hours_since_update": 0.0,
                }
                continue

            stat = path.stat()
            size_mb = stat.st_size / (1024 * 1024)
            mtime = stat.st_mtime
            hours_since_update = (now - mtime) / 3600

            # 估算记录数 (按行数)
            record_count = 0
            try:
                with path.open("r", encoding="utf-8") as f:
                    for _ in f:
                        record_count += 1
            except (OSError, UnicodeDecodeError):
                pass

            stats[name] = {
                "exists": True,
                "path": rel_path,
                "size_mb": round(size_mb, 2),
                "record_count": record_count,
                "last_modified": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                "hours_since_update": round(hours_since_update, 1),
            }

        return stats

    # ── 工具方法 ─────────────────────────────────────────────

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        """读取 JSONL 文件 (返回所有记录)."""
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    # ── Dashboard 概览 ───────────────────────────────────────

    def get_dashboard_overview(self) -> dict[str, Any]:
        """Dashboard 监控概览 — 聚合所有指标为单一响应.

        Returns:
            {
                "health": {...},
                "alerts": [...],
                "subsystems": {...},
                "data_files": {...},
            }
        """
        return {
            "health": self.get_system_health(),
            "alerts": self.get_alerts(),
            "growth_loop": self._get_growth_loop_stats(),
            "liveops": self._get_liveops_stats(),
            "churn_alert": self._get_churn_alert_stats(),
            "approval_queue": self._get_approval_queue_stats(),
            "data_files": self._get_file_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
