"""E13.7.4.2 Approval Manager — 人工审批管理.

管理审批请求的完整生命周期:
  - PENDING → APPROVED → EXECUTING → COMPLETED
  - PENDING → REJECTED
  - PENDING → EXPIRED (超时未处理)
  - PENDING → CANCELLED

与 PolicyEngine 的关系:
  - PolicyEngine 输出 REQUIRE_APPROVAL 时
  - ApprovalManager 创建审批请求并管理其生命周期
  - 审批通过后，Agent 继续执行动作
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .policy_models import (
    ApprovalRequest,
    ApprovalStatus,
    PolicyContext,
    PolicyDecision,
    PolicyResult,
)


# ═══════════════════════════════════════════════════════════════
# Approval Record
# ═══════════════════════════════════════════════════════════════


@dataclass
class ApprovalRecord:
    """审批记录 — 包含请求和完整生命周期信息.

    Attributes:
        request: 审批请求
        policy_result: 触发审批的策略结果
        execution_result: 执行结果 (审批通过后执行)
        notes: 审批备注
    """
    request: ApprovalRequest
    policy_result: PolicyResult | None = None
    execution_result: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "policy_result": self.policy_result.to_dict() if self.policy_result else None,
            "execution_result": self.execution_result,
            "notes": self.notes,
        }


# ═══════════════════════════════════════════════════════════════
# Approval Manager
# ═══════════════════════════════════════════════════════════════


class ApprovalManager:
    """审批管理器.

    管理审批请求的完整生命周期:
      - 创建审批请求
      - 批准 / 拒绝 / 取消
      - 自动过期处理
      - 查询和统计

    使用方式:
        >>> manager = ApprovalManager()
        >>> request = manager.create_approval(
        ...     action_type="update_budget",
        ...     action_params={"campaign_id": "123", "new_budget": 500},
        ...     reason="预算增加超过30%",
        ...     policy_result=result,
        ... )
        >>> manager.approve(request.request_id)
        >>> manager.is_approved(request.request_id)  # True
    """

    def __init__(
        self,
        default_ttl_hours: int = 24,
        max_pending: int = 100,
        max_history: int = 1000,
    ):
        self._default_ttl_hours = default_ttl_hours
        self._max_pending = max_pending
        self._max_history = max_history
        self._records: dict[str, ApprovalRecord] = {}
        self._history: list[ApprovalRecord] = []

    # ── Properties ──────────────────────────────────────────

    @property
    def pending_count(self) -> int:
        return len(self._pending())

    @property
    def total_count(self) -> int:
        return len(self._records) + len(self._history)

    # ── Create ──────────────────────────────────────────────

    def create_approval(
        self,
        action_type: str,
        action_params: dict[str, Any] | None = None,
        reason: str = "",
        policy_result: PolicyResult | None = None,
        context: PolicyContext | None = None,
        ttl_hours: int | None = None,
    ) -> ApprovalRequest:
        """创建审批请求.

        Args:
            action_type: 动作类型
            action_params: 动作参数
            reason: 审批原因
            policy_result: 触发审批的策略结果
            context: 策略上下文
            ttl_hours: 审批有效期 (小时)

        Returns:
            ApprovalRequest: 审批请求

        Raises:
            ValueError: 如果待审批队列已满
        """
        # 清理过期请求
        self._cleanup_expired()

        # 检查队列容量
        if self.pending_count >= self._max_pending:
            raise ValueError(
                f"待审批队列已满 ({self._max_pending}), 请先处理现有请求"
            )

        ttl = ttl_hours if ttl_hours is not None else self._default_ttl_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)

        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            action_type=action_type,
            action_params=action_params or {},
            reason=reason,
            context=context,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=expires_at.isoformat(),
        )

        record = ApprovalRecord(
            request=request,
            policy_result=policy_result,
        )

        self._records[request.request_id] = record
        return request

    def create_approval_from_result(
        self,
        policy_result: PolicyResult,
        action_params: dict[str, Any] | None = None,
        ttl_hours: int | None = None,
    ) -> ApprovalRequest | None:
        """从 PolicyResult 创建审批请求.

        仅当 PolicyResult.requires_approval == True 时创建。

        Args:
            policy_result: 策略评估结果
            action_params: 动作参数
            ttl_hours: 审批有效期

        Returns:
            ApprovalRequest 或 None
        """
        if not policy_result.requires_approval:
            return None

        return self.create_approval(
            action_type="unknown",
            action_params=action_params or {},
            reason=policy_result.reason,
            policy_result=policy_result,
            ttl_hours=ttl_hours,
        )

    # ── Approve / Reject / Cancel ───────────────────────────

    def approve(
        self, request_id: str, resolver: str = "", note: str = ""
    ) -> ApprovalRequest | None:
        """批准审批请求."""
        record = self._records.get(request_id)
        if record is None:
            return None

        if record.request.status != ApprovalStatus.PENDING:
            return None

        record.request.approve(resolver, note)
        if note:
            record.notes.append(f"[APPROVED] {resolver}: {note}")

        return record.request

    def reject(
        self, request_id: str, resolver: str = "", note: str = ""
    ) -> ApprovalRequest | None:
        """拒绝审批请求."""
        record = self._records.get(request_id)
        if record is None:
            return None

        if record.request.status != ApprovalStatus.PENDING:
            return None

        record.request.reject(resolver, note)
        if note:
            record.notes.append(f"[REJECTED] {resolver}: {note}")

        self._archive(record)
        return record.request

    def cancel(self, request_id: str, note: str = "") -> ApprovalRequest | None:
        """取消审批请求."""
        record = self._records.get(request_id)
        if record is None:
            return None

        if record.request.status != ApprovalStatus.PENDING:
            return None

        record.request.cancel()
        if note:
            record.notes.append(f"[CANCELLED] {note}")

        self._archive(record)
        return record.request

    def expire(self, request_id: str) -> ApprovalRequest | None:
        """手动过期审批请求."""
        record = self._records.get(request_id)
        if record is None:
            return None

        if record.request.status != ApprovalStatus.PENDING:
            return None

        record.request.expire()
        record.notes.append("[EXPIRED] 审批超时自动过期")
        self._archive(record)
        return record.request

    # ── Query ───────────────────────────────────────────────

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """获取审批请求."""
        record = self._records.get(request_id)
        return record.request if record else None

    def get_record(self, request_id: str) -> ApprovalRecord | None:
        """获取审批记录."""
        return self._records.get(request_id)

    def is_approved(self, request_id: str) -> bool:
        """检查是否已批准."""
        request = self.get_request(request_id)
        return request is not None and request.status == ApprovalStatus.APPROVED

    def is_pending(self, request_id: str) -> bool:
        """检查是否待审批."""
        request = self.get_request(request_id)
        return request is not None and request.status == ApprovalStatus.PENDING

    def get_pending(self) -> list[ApprovalRequest]:
        """获取所有待审批请求."""
        self._cleanup_expired()
        return [r.request for r in self._pending()]

    def get_all_active(self) -> list[ApprovalRequest]:
        """获取所有活跃请求 (PENDING + APPROVED)."""
        self._cleanup_expired()
        return [
            r.request for r in self._records.values()
            if r.request.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED)
        ]

    def get_history(
        self, limit: int = 50, offset: int = 0
    ) -> list[ApprovalRecord]:
        """获取历史记录."""
        return self._history[offset : offset + limit]

    # ── Stats ───────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取审批统计."""
        self._cleanup_expired()

        status_counts = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "expired": 0,
            "cancelled": 0,
        }

        for record in self._records.values():
            status = record.request.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        for record in self._history:
            status = record.request.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total": self.total_count,
            "active": len(self._records),
            "history": len(self._history),
            "status_counts": status_counts,
            "pending_requests": status_counts["pending"],
        }

    # ── Internal ────────────────────────────────────────────

    def _pending(self) -> list[ApprovalRecord]:
        """获取所有待审批记录."""
        return [
            r for r in self._records.values()
            if r.request.status == ApprovalStatus.PENDING
        ]

    def _cleanup_expired(self) -> None:
        """清理过期请求."""
        expired_ids = []
        for request_id, record in self._records.items():
            if record.request.status == ApprovalStatus.PENDING and record.request.is_expired:
                record.request.expire()
                record.notes.append("[EXPIRED] 审批超时自动过期")
                expired_ids.append(request_id)

        for rid in expired_ids:
            self._archive(self._records[rid])

    def _archive(self, record: ApprovalRecord) -> None:
        """归档记录."""
        if record.request.request_id in self._records:
            del self._records[record.request.request_id]
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def reset(self) -> None:
        """重置管理器."""
        self._records = {}
        self._history = []


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_approval_manager(
    default_ttl_hours: int = 24,
    max_pending: int = 100,
) -> ApprovalManager:
    """创建审批管理器的工厂函数."""
    return ApprovalManager(
        default_ttl_hours=default_ttl_hours,
        max_pending=max_pending,
    )