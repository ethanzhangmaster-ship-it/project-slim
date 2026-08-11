"""E17.6 — ExecutionRouter：路由 + 权限门 + 状态机 + 审计 + 记忆。

route(action)：
  CREATED → VALIDATING
    ├─ 无 adapter                → FAILED（不回滚，配置错误）
    ├─ CRITICAL                  → WAITING_APPROVAL（进 outbox，标 manual_only，
    │                              审批也不自动执行——只能人工后台操作）
    ├─ CONTROLLED                → WAITING_APPROVAL（进 outbox，approve() 后执行）
    └─ SAFE → EXECUTING
         ├─ ok  → SUCCESS → LEARNING（写 ExecutionMemory）
         └─ 失败 → FAILED → adapter.rollback → ROLLBACK

所有终态（含 WAITING_APPROVAL / SKIPPED）都写 EP0 AuditTrail.record_execution，
所有终态都写 ExecutionMemory（供 E17.7 沉淀）。

Approval Outbox：轻量 JSONL 审批信箱（E16 JsonlApprovalQueue 强绑定 GrowthDecision，
此处动作粒度不同故自建；沿用其教训——pending 必须过滤 resolution）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from audit.trail import ApprovalRecord, AuditTrail, ExecutionRecord

from .memory import ExecutionMemory
from .models import (
    AdapterOutcome,
    ExecutionAction,
    ExecutionExperience,
    ExecutionResult,
    ExecutionStatus,
)
from .permissions import PermissionChecker, PermissionTier
from .registry import AdapterRegistry, build_default_registry

_S = ExecutionStatus


class ApprovalOutbox:
    """执行动作级审批信箱（JSONL，request/resolution 双记录）。"""

    def __init__(self, path: str = "data/ceo/execution_approvals.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def enqueue(self, action: ExecutionAction, tier: PermissionTier,
                execution_id: str = "") -> None:
        self._append({
            "kind": "request",
            "action_id": action.action_id,
            "execution_id": execution_id,
            "tier": tier.value,
            "manual_only": tier == PermissionTier.CRITICAL,
            "action": action.to_dict(),
        })

    def resolve(self, action_id: str, *, approved: bool,
                approver: str = "human", reason: str = "") -> None:
        self._append({
            "kind": "resolution",
            "action_id": action_id,
            "approved": approved,
            "approver": approver,
            "reason": reason,
        })

    def get_request(self, action_id: str) -> Optional[Dict[str, Any]]:
        for row in self._read():
            if row.get("kind") == "request" and row.get("action_id") == action_id:
                return row
        return None

    def pending(self) -> List[Dict[str, Any]]:
        """未被 resolve 的 request（教训：必须过滤 resolution）。"""
        resolved = {
            row["action_id"] for row in self._read() if row.get("kind") == "resolution"
        }
        return [
            row for row in self._read()
            if row.get("kind") == "request" and row["action_id"] not in resolved
        ]

    def _append(self, data: Dict[str, Any]) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _read(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out


class ExecutionRouter:
    """路由器：registry.find(domain) → permission gate → adapter.execute。"""

    def __init__(
        self,
        registry: Optional[AdapterRegistry] = None,
        permission: Optional[PermissionChecker] = None,
        audit: Optional[AuditTrail] = None,
        memory: Optional[ExecutionMemory] = None,
        outbox: Optional[ApprovalOutbox] = None,
        agent_name: str = "execution_router",
    ):
        self.registry = registry or build_default_registry()
        self.permission = permission or PermissionChecker(agent=agent_name)
        self.audit = audit or AuditTrail(audit_dir="data/ceo/audit")
        self.memory = memory or ExecutionMemory()
        self.outbox = outbox or ApprovalOutbox()
        self.agent_name = agent_name

    # ------------------------------------------------------------------ #
    def route(self, action: ExecutionAction, *, execution_id: str = "") -> ExecutionResult:
        start = time.perf_counter()
        history = [_S.CREATED.value, _S.VALIDATING.value]

        adapter = self.registry.find(action.domain)
        if adapter is None:
            history.append(_S.FAILED.value)
            result = ExecutionResult(
                action_id=action.action_id, system="none",
                status=_S.FAILED, error=f"no adapter for domain '{action.domain}'",
                state_history=history,
            )
            return self._finalize(action, result, execution_id, start)

        tier = self.permission.check(action)
        if tier != PermissionTier.SAFE:
            history.append(_S.WAITING_APPROVAL.value)
            self.outbox.enqueue(action, tier, execution_id)
            detail = (
                "critical: manual console operation only"
                if tier == PermissionTier.CRITICAL
                else "queued for human approval"
            )
            result = ExecutionResult(
                action_id=action.action_id, system=adapter.name,
                status=_S.WAITING_APPROVAL, detail=detail,
                permission_tier=tier.value, state_history=history,
            )
            return self._finalize(action, result, execution_id, start)

        result = self._execute(adapter, action, history, tier)
        return self._finalize(action, result, execution_id, start)

    # ------------------------------------------------------------------ #
    def approve(self, action_id: str, *, approver: str = "human",
                reason: str = "", execution_id: str = "") -> ExecutionResult:
        """人工批准后执行（CRITICAL 除外——批准也不自动执行）。"""
        req = self.outbox.get_request(action_id)
        if req is None:
            raise KeyError(f"no approval request for action '{action_id}'")
        action = ExecutionAction.from_dict(req["action"])
        self.audit.record_approval(ApprovalRecord(
            decision_id=action.decision_id or action.action_id,
            approver=approver, approved=True, reason=reason,
        ))
        self.outbox.resolve(action_id, approved=True, approver=approver, reason=reason)

        if req.get("manual_only"):
            result = ExecutionResult(
                action_id=action.action_id, system="manual",
                status=_S.SKIPPED,
                detail="approved but CRITICAL: execute manually in console",
                permission_tier=PermissionTier.CRITICAL.value,
                state_history=[_S.WAITING_APPROVAL.value, _S.SKIPPED.value],
            )
            return self._finalize(action, result, execution_id or req.get("execution_id", ""),
                                  time.perf_counter())

        adapter = self.registry.find(action.domain)
        if adapter is None:
            result = ExecutionResult(
                action_id=action.action_id, system="none", status=_S.FAILED,
                error=f"no adapter for domain '{action.domain}'",
                state_history=[_S.WAITING_APPROVAL.value, _S.FAILED.value],
            )
            return self._finalize(action, result, execution_id or req.get("execution_id", ""),
                                  time.perf_counter())

        start = time.perf_counter()
        history = [_S.WAITING_APPROVAL.value]
        result = self._execute(adapter, action, history, PermissionTier.CONTROLLED)
        return self._finalize(action, result, execution_id or req.get("execution_id", ""), start)

    def reject(self, action_id: str, *, approver: str = "human", reason: str = "") -> None:
        req = self.outbox.get_request(action_id)
        if req is None:
            raise KeyError(f"no approval request for action '{action_id}'")
        action = ExecutionAction.from_dict(req["action"])
        self.audit.record_approval(ApprovalRecord(
            decision_id=action.decision_id or action.action_id,
            approver=approver, approved=False, reason=reason,
        ))
        self.outbox.resolve(action_id, approved=False, approver=approver, reason=reason)

    def record_skip(self, action: ExecutionAction, reason: str,
                    *, execution_id: str = "") -> ExecutionResult:
        """依赖失败等原因跳过（仍写审计 + 记忆，保证每动作有 AuditRecord）。"""
        result = ExecutionResult(
            action_id=action.action_id, system="none", status=_S.SKIPPED,
            detail=reason, state_history=[_S.CREATED.value, _S.SKIPPED.value],
        )
        return self._finalize(action, result, execution_id, time.perf_counter())

    def pending_approvals(self) -> List[Dict[str, Any]]:
        return self.outbox.pending()

    # ------------------------------------------------------------------ #
    def _execute(self, adapter, action: ExecutionAction,
                 history: List[str], tier: PermissionTier) -> ExecutionResult:
        history.append(_S.EXECUTING.value)
        outcome: AdapterOutcome = adapter.execute(action)
        if outcome.ok:
            history.extend([_S.SUCCESS.value, _S.LEARNING.value])
            return ExecutionResult(
                action_id=action.action_id, system=adapter.name,
                status=_S.SUCCESS, detail=outcome.detail,
                real_api_called=outcome.real_api_called,
                permission_tier=tier.value, state_history=history,
                data=dict(outcome.data),
            )
        # 失败 → FAILED → ROLLBACK
        history.append(_S.FAILED.value)
        rb = adapter.rollback(action)
        history.append(_S.ROLLBACK.value)
        return ExecutionResult(
            action_id=action.action_id, system=adapter.name,
            status=_S.ROLLBACK, detail=rb.detail,
            real_api_called=outcome.real_api_called or rb.real_api_called,
            rolled_back=rb.ok, error=outcome.error or "execution failed",
            permission_tier=tier.value, state_history=history,
            data=dict(outcome.data),
        )

    def _finalize(self, action: ExecutionAction, result: ExecutionResult,
                  execution_id: str, start: float) -> ExecutionResult:
        result.duration_ms = round((time.perf_counter() - start) * 1000.0, 3)
        # EP0 审计：每个动作一条 ExecutionRecord（append-only）
        self.audit.record_execution(ExecutionRecord(
            decision_id=action.decision_id or execution_id or action.action_id,
            agent=self.agent_name,
            action=f"{action.domain}:{action.action_type}:{result.status.value}",
            success=result.status in (_S.SUCCESS, _S.WAITING_APPROVAL),
            duration_ms=result.duration_ms,
            error=result.error,
        ))
        # 执行记忆：Decision → Strategy → Execution → Result 闭环
        self.memory.record(ExecutionExperience(
            execution_id=execution_id,
            action_id=action.action_id,
            decision_id=action.decision_id,
            game_id=action.game_id,
            strategy_type=action.plan_strategy_type,
            domain=action.domain,
            action_type=action.action_type,
            status=result.status.value,
            success=result.status == _S.SUCCESS,
            real_api_called=result.real_api_called,
            rolled_back=result.rolled_back,
            detail=result.detail or result.error,
        ))
        return result


__all__ = ["ApprovalOutbox", "ExecutionRouter"]
