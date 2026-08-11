"""P2.6.7 Recovery Escalation — 升级人工。

接 P2.3 Approval Workflow：HIGH/CRITICAL 故障不再自动处理，
生成 EscalationTicket 并（可选）向 P2.3 提交 manual approval 请求。

四级升级（用户契约）：
    LOW      -> 自动 retry 即可（通常不产生工单）
    MEDIUM   -> 自动恢复（reconcile 等；恢复失败才升级）
    HIGH     -> 需要人工介入（产生工单 + 可选 P2.3 审批单）
    CRITICAL -> 停止所有自动执行（halt_automation=True）

CRITICAL halt 语义：JsonlEscalationStore.automation_halted() 为 True 时，
上层（P3 Autonomous Operator / RecoveryEngine）必须暂停一切自动执行，
直到人工 resolve 该工单（resolve 追加 latest-wins 行，与 P2.3 store 同纪律）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.execution.recovery.models import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    EscalationTicket,
    RecoveryIncident,
    _as_str,
    _now_iso,
    severity_rank,
)

# 等级 -> 处理方式说明（供报表/测试引用）
ESCALATION_LEVELS = {
    "LOW": "auto_retry",           # 自动重试即可
    "MEDIUM": "auto_recover",      # 自动恢复
    "HIGH": "manual_intervention", # 人工介入
    "CRITICAL": "halt_automation", # 停止所有自动执行
}


# ---------------------------------------------------------------------------
# Store（Jsonl / InMemory 同契约）
# ---------------------------------------------------------------------------


class JsonlEscalationStore:
    """append-only 工单库（data/execution/escalations.jsonl）。

    resolve = 追加新行（status=resolved），读取时 latest-wins——
    与 P2.3 JsonlApprovalStore 相同纪律。
    """

    def __init__(self, path: str = "data/execution/escalations.jsonl"):
        self.path = Path(path)

    def add(self, ticket: EscalationTicket) -> None:
        record = ticket.to_dict()
        record["record_status"] = "open"
        record["recorded_at"] = _now_iso()
        self._append(record)

    def resolve(self, ticket_id: str, resolved_by: str, note: str = "") -> None:
        self._append(
            {
                "ticket_id": ticket_id,
                "record_status": "resolved",
                "resolved_by": resolved_by,
                "note": note,
                "recorded_at": _now_iso(),
            }
        )

    def all(self) -> List[Dict[str, Any]]:
        """全部工单，latest-wins 合并。"""
        merged: Dict[str, Dict[str, Any]] = {}
        for record in self._read():
            ticket_id = record.get("ticket_id", "")
            if not ticket_id:
                continue
            base = merged.get(ticket_id, {})
            base.update(record)
            merged[ticket_id] = base
        return list(merged.values())

    def open_tickets(self) -> List[Dict[str, Any]]:
        return [t for t in self.all() if t.get("record_status") == "open"]

    def automation_halted(self) -> bool:
        """存在未 resolve 的 CRITICAL 工单 -> 停止所有自动执行。"""
        return any(
            bool(t.get("halt_automation"))
            for t in self.open_tickets()
        )

    # -- I/O ---------------------------------------------------------------

    def _append(self, record: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records


class InMemoryEscalationStore(JsonlEscalationStore):
    """同契约内存版（测试 / 双跑 fixture 用）。"""

    def __init__(self):  # noqa: D107 - 不调 super，避免建路径
        self._records: List[Dict[str, Any]] = []

    def _append(self, record: Dict[str, Any]) -> None:
        self._records.append(dict(record))

    def _read(self) -> List[Dict[str, Any]]:
        return list(self._records)


# ---------------------------------------------------------------------------
# EscalationManager
# ---------------------------------------------------------------------------


class EscalationManager:
    """升级管理器：产工单 + 接 P2.3 manual approval。

    Args:
        store             : 工单库（默认 JsonlEscalationStore）
        approval_workflow : 可选 P2.3 ApprovalWorkflow/ApprovalService；
                            注入后 HIGH+ 工单会同步提交 manual approval，
                            approval_id 回填到工单。
    """

    def __init__(
        self,
        store: Optional[JsonlEscalationStore] = None,
        approval_workflow: Any = None,
    ):
        self.store = store or JsonlEscalationStore()
        self.approval_workflow = approval_workflow

    def escalate(
        self,
        incident: RecoveryIncident,
        severity: str,
        reason: str,
        recommended_action: str = "",
        request: Any = None,
    ) -> EscalationTicket:
        """生成工单、落库、推进状态机、（可选）提交 P2.3 审批。

        Returns:
            EscalationTicket（CRITICAL 自动 halt_automation=True）
        """
        severity = _as_str(severity)
        ticket = EscalationTicket(
            incident_id=incident.incident_id,
            severity=severity,
            reason=reason,
            recommended_action=recommended_action
            or self._default_recommendation(incident, severity),
            metadata={
                "execution_id": incident.execution_id,
                "action": incident.action,
                "provider": incident.provider,
                "failure_type": incident.failure_type,
            },
        )

        # 接 P2.3：HIGH+ 且注入了审批工作流 -> 提交 manual approval
        if (
            self.approval_workflow is not None
            and request is not None
            and severity_rank(severity) >= severity_rank(SEVERITY_HIGH)
        ):
            try:
                submitted = self.approval_workflow.submit(request)
                approval = getattr(submitted, "request", submitted)
                ticket.approval_id = str(
                    getattr(approval, "approval_id", "") or ""
                )
            except Exception as exc:  # 审批提交失败不阻断升级本身
                ticket.metadata["approval_submit_error"] = str(exc)

        self.store.add(ticket)

        # 推进事件状态机 -> ESCALATED
        if incident.status in ("CLASSIFIED", "PLANNED", "RECOVERING"):
            incident.transition("ESCALATED", reason=reason)

        return ticket

    def resolve(self, ticket_id: str, resolved_by: str, note: str = "") -> None:
        self.store.resolve(ticket_id, resolved_by, note)

    def automation_halted(self) -> bool:
        return self.store.automation_halted()

    # ------------------------------------------------------------------

    @staticmethod
    def _default_recommendation(
        incident: RecoveryIncident, severity: str
    ) -> str:
        if _as_str(severity) == SEVERITY_CRITICAL:
            return (
                f"HALT all automation. Manually verify {incident.provider} "
                f"state for target and reconcile {incident.action}."
            )
        return (
            f"Manually inspect {incident.provider} ({incident.failure_type}) "
            f"and re-run {incident.action} after fixing root cause."
        )


__all__ = [
    "ESCALATION_LEVELS",
    "JsonlEscalationStore",
    "InMemoryEscalationStore",
    "EscalationManager",
]
