"""E13.6.4 Approval Manager — 审批工作流管理器.

管理审批请求的创建、处理、查询和过期管理。

核心功能:
  - 创建审批请求 (create_approval)
  - 批准/拒绝审批 (approve/deny)
  - 查询审批状态 (get_pending/get_by_action)
  - 自动过期处理 (expire_stale_requests)

连接:
  E13.6.4 SafetyEngine → ApprovalManager → ApprovalRequest → ExecutionContext
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from .safety_models import ApprovalRequest, ApprovalStatus, SafetyEvaluation


# ═══════════════════════════════════════════════════════════════
# Approval Manager
# ═══════════════════════════════════════════════════════════════


@dataclass
class ApprovalManager:
    """审批管理器 — 管理审批请求的生命周期.

    用法:
        manager = ApprovalManager()
        request = manager.create_approval(evaluation)
        manager.approve(request.request_id, "admin")
    """

    requests: dict[str, ApprovalRequest] = field(default_factory=dict)
    default_expiry_hours: int = 24
    history: list[dict[str, Any]] = field(default_factory=list)

    # ── 创建审批 ──────────────────────────────────────────────

    def create_approval(
        self,
        evaluation: SafetyEvaluation,
        reason: str = "",
        expires_in_hours: int | None = None,
    ) -> ApprovalRequest:
        """创建审批请求.

        Args:
            evaluation: 安全评估结果
            reason: 审批原因
            expires_in_hours: 过期时间 (小时), None 使用默认值

        Returns:
            ApprovalRequest: 审批请求
        """
        expiry_hours = expires_in_hours if expires_in_hours is not None else self.default_expiry_hours
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=expiry_hours)).isoformat()

        request = ApprovalRequest(
            action_id=evaluation.action_id,
            action_type=evaluation.action_type,
            risk_score=evaluation.risk_score,
            reason=reason or "; ".join(evaluation.reasons),
            expires_at=expires_at,
            metadata={"evaluation_id": evaluation.evaluation_id},
        )

        self.requests[request.request_id] = request
        self._log_history(request, "created")
        return request

    def create_approval_for_action(
        self,
        action_id: str,
        action_type: str,
        risk_score: float = 0.0,
        reason: str = "",
        expires_in_hours: int | None = None,
    ) -> ApprovalRequest:
        """为指定动作创建审批请求 (无需 SafetyEvaluation).

        Args:
            action_id: 动作 ID
            action_type: 动作类型
            risk_score: 风险评分
            reason: 审批原因
            expires_in_hours: 过期时间

        Returns:
            ApprovalRequest: 审批请求
        """
        expiry_hours = expires_in_hours if expires_in_hours is not None else self.default_expiry_hours
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=expiry_hours)).isoformat()

        request = ApprovalRequest(
            action_id=action_id,
            action_type=action_type,
            risk_score=risk_score,
            reason=reason,
            expires_at=expires_at,
        )

        self.requests[request.request_id] = request
        self._log_history(request, "created")
        return request

    # ── 审批操作 ──────────────────────────────────────────────

    def approve(
        self,
        request_id: str,
        approved_by: str = "system",
        notes: str = "",
    ) -> ApprovalRequest | None:
        """批准审批请求.

        Args:
            request_id: 请求 ID
            approved_by: 审批人
            notes: 备注

        Returns:
            更新后的 ApprovalRequest, 不存在返回 None
        """
        request = self.requests.get(request_id)
        if request is None:
            return None
        if not request.is_pending:
            return request

        request.approve(approved_by, notes)
        self._log_history(request, "approved")
        return request

    def deny(
        self,
        request_id: str,
        approved_by: str = "system",
        notes: str = "",
    ) -> ApprovalRequest | None:
        """拒绝审批请求.

        Args:
            request_id: 请求 ID
            approved_by: 审批人
            notes: 备注

        Returns:
            更新后的 ApprovalRequest, 不存在返回 None
        """
        request = self.requests.get(request_id)
        if request is None:
            return None
        if not request.is_pending:
            return request

        request.deny(approved_by, notes)
        self._log_history(request, "denied")
        return request

    def cancel(self, request_id: str) -> ApprovalRequest | None:
        """取消审批请求."""
        request = self.requests.get(request_id)
        if request is None:
            return None
        request.cancel()
        self._log_history(request, "cancelled")
        return request

    # ── 查询 ──────────────────────────────────────────────────

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """获取审批请求."""
        return self.requests.get(request_id)

    def get_pending(self) -> list[ApprovalRequest]:
        """获取所有待审批的请求."""
        self._expire_stale()
        return [r for r in self.requests.values() if r.is_pending]

    def get_by_action(self, action_id: str) -> list[ApprovalRequest]:
        """按动作 ID 获取审批请求."""
        return [r for r in self.requests.values() if r.action_id == action_id]

    def get_approved(self) -> list[ApprovalRequest]:
        """获取已批准的请求."""
        return [r for r in self.requests.values() if r.is_approved]

    def get_denied(self) -> list[ApprovalRequest]:
        """获取已拒绝的请求."""
        return [r for r in self.requests.values() if r.is_denied]

    def is_action_approved(self, action_id: str) -> bool:
        """检查动作是否已被批准."""
        for r in self.requests.values():
            if r.action_id == action_id and r.is_approved:
                return True
        return False

    def is_action_denied(self, action_id: str) -> bool:
        """检查动作是否已被拒绝."""
        for r in self.requests.values():
            if r.action_id == action_id and r.is_denied:
                return True
        return False

    def has_pending_approval(self, action_id: str) -> bool:
        """检查动作是否有待审批的请求."""
        for r in self.requests.values():
            if r.action_id == action_id and r.is_pending:
                return True
        return False

    # ── 过期处理 ──────────────────────────────────────────────

    def _expire_stale(self) -> int:
        """自动过期处理 — 将过期的待审批请求标记为 EXPIRED."""
        count = 0
        for request in self.requests.values():
            if request.is_pending and request.is_expired:
                request.expire()
                self._log_history(request, "expired")
                count += 1
        return count

    def expire_stale_requests(self) -> int:
        """公开的过期处理方法."""
        return self._expire_stale()

    # ── 统计与日志 ────────────────────────────────────────────

    def _log_history(self, request: ApprovalRequest, event: str) -> None:
        """记录审批历史."""
        self.history.append({
            "request_id": request.request_id,
            "action_id": request.action_id,
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def stats(self) -> dict[str, Any]:
        """获取审批统计."""
        self._expire_stale()
        all_requests = list(self.requests.values())
        pending = [r for r in all_requests if r.is_pending]
        approved = [r for r in all_requests if r.is_approved]
        denied = [r for r in all_requests if r.is_denied]
        expired = [r for r in all_requests if r.is_expired]

        return {
            "total": len(all_requests),
            "pending": len(pending),
            "approved": len(approved),
            "denied": len(denied),
            "expired": len(expired),
            "approval_rate": (
                len(approved) / max(len(approved) + len(denied), 1)
            ),
        }

    def clear(self) -> None:
        """清空所有审批请求."""
        self.requests.clear()
        self.history.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests": {k: v.to_dict() for k, v in self.requests.items()},
            "stats": self.stats(),
            "history_count": len(self.history),
        }