"""P2.4.6 Execution Audit — 接 EP0 AuditTrail 的执行事件流。

新事件（用户契约）：
    execution.started   : 安全执行开始（过闸门后、动手前）
    provider.called     : 已实际调用 Provider（real_api_called 与否都记）
    execution.finished  : 执行终态（SUCCESS / FAILED / BLOCKED / ROLLED_BACK）
    rollback.finished   : 回滚终态（ROLLBACK_SUCCESS / ESCALATED）

完整审计链（跨层）：
    decision.created -> approval.submitted -> approval.approved
      -> execution.started -> provider.called -> execution.finished
      -> rollback.finished（仅失败回滚时）

实现：
- 自有事件流：{audit_dir}/execution_events.jsonl（append-only）
- 同时桥接 EP0 audit.trail.AuditTrail.record_execution（executions.jsonl），
  保持与 P2.2 Router 相同的 EP0 落点
- 审计失败绝不阻断主流程（与 Router 同纪律）
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

EVENT_EXECUTION_STARTED = "execution.started"
EVENT_PROVIDER_CALLED = "provider.called"
EVENT_EXECUTION_FINISHED = "execution.finished"
EVENT_ROLLBACK_FINISHED = "rollback.finished"

VALID_EVENTS = (
    EVENT_EXECUTION_STARTED,
    EVENT_PROVIDER_CALLED,
    EVENT_EXECUTION_FINISHED,
    EVENT_ROLLBACK_FINISHED,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ExecutionAuditLogger:
    """P2.4 执行事件审计器。

    Args:
        audit_dir  : 事件流目录（execution_events.jsonl）
        audit_trail: 可选 EP0 AuditTrail 实例（桥接 executions.jsonl）
    """

    def __init__(
        self,
        audit_dir: str = "data/execution/audit",
        audit_trail: Any = None,
    ) -> None:
        self.dir = Path(audit_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.dir / "execution_events.jsonl"
        self.audit_trail = audit_trail

    # ------------------------------------------------------------------
    # 事件记录
    # ------------------------------------------------------------------
    def emit(
        self,
        event: str,
        execution_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """写一条事件。审计失败绝不抛出。"""
        if event not in VALID_EVENTS:
            # 未知事件也记录（前向兼容），但打标
            payload = dict(payload or {})
            payload["_unknown_event"] = True
        record = {
            "event": event,
            "execution_id": execution_id,
            "ts": _now_iso(),
            "payload": payload or {},
        }
        try:
            with self.events_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception:  # noqa: BLE001 — 审计失败不阻断
            pass

    # -- 语义化入口 ----------------------------------------------------

    def execution_started(self, context: Any) -> None:
        self.emit(
            EVENT_EXECUTION_STARTED,
            getattr(context, "execution_id", ""),
            {
                "request_id": getattr(context, "request_id", ""),
                "action": getattr(context, "action", ""),
                "target": getattr(context, "target", ""),
                "mode": getattr(context, "mode", ""),
                "risk_score": getattr(context, "risk_score", 0.0),
                "authorization_id": getattr(context, "authorization_id", ""),
            },
        )

    def provider_called(self, context: Any, provider_id: str, real_api_called: bool) -> None:
        self.emit(
            EVENT_PROVIDER_CALLED,
            getattr(context, "execution_id", ""),
            {
                "provider": provider_id,
                "real_api_called": bool(real_api_called),
                "action": getattr(context, "action", ""),
            },
        )

    def execution_finished(self, context: Any, verdict: str, error: str = "") -> None:
        self.emit(
            EVENT_EXECUTION_FINISHED,
            getattr(context, "execution_id", ""),
            {
                "status": getattr(context, "status", ""),
                "verdict": verdict,
                "error": error,
                "started_at": getattr(context, "started_at", ""),
                "finished_at": getattr(context, "finished_at", ""),
            },
        )
        self._bridge_ep0(context, verdict, error)

    def rollback_finished(self, context: Any, rollback_result: Any) -> None:
        detail = (
            rollback_result.to_dict()
            if hasattr(rollback_result, "to_dict")
            else dict(rollback_result or {})
        )
        self.emit(
            EVENT_ROLLBACK_FINISHED,
            getattr(context, "execution_id", ""),
            detail,
        )

    # ------------------------------------------------------------------
    # 查询（验收 / 测试用）
    # ------------------------------------------------------------------
    def events_for(self, execution_id: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if not self.events_file.exists():
            return results
        for line in self.events_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("execution_id") == execution_id:
                results.append(record)
        return results

    # ------------------------------------------------------------------
    # EP0 桥接
    # ------------------------------------------------------------------
    def _bridge_ep0(self, context: Any, verdict: str, error: str) -> None:
        if self.audit_trail is None:
            return
        try:
            from audit.trail import ExecutionRecord

            self.audit_trail.record_execution(
                ExecutionRecord(
                    decision_id=getattr(context, "request_id", ""),
                    agent=f"safe_executor:{getattr(context, 'action', '')}",
                    action=getattr(context, "action", ""),
                    success=verdict in ("EXECUTED", "RETURN_EXISTING"),
                    duration_ms=0.0,
                    error=error,
                )
            )
        except Exception:  # noqa: BLE001 — 审计失败不阻断
            pass


__all__ = [
    "EVENT_EXECUTION_STARTED",
    "EVENT_PROVIDER_CALLED",
    "EVENT_EXECUTION_FINISHED",
    "EVENT_ROLLBACK_FINISHED",
    "VALID_EVENTS",
    "ExecutionAuditLogger",
]
