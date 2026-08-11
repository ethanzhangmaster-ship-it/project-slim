"""E13.6.3 Audit Log — 执行审计日志.

记录每一次 AI 动作的完整上下文，包括原因、置信度、执行前后状态和结果。
这是 E13.6.5 Feedback Loop 和 E13.4 Memory 的数据来源。

核心设计:
  - AuditEntry: 单条审计记录
  - AuditLog: 审计日志存储与查询
  - 每条记录包含: action_id / reason / confidence / before / after / result

连接:
  E13.6.3 ExecutionEngine → AuditLog → E13.6.5 Feedback Loop → E13.4 Memory
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .base_executor import ExecutionResult, ExecutionResultStatus
from .models import ExecutionActionType


# ═══════════════════════════════════════════════════════════════
# Audit Entry
# ═══════════════════════════════════════════════════════════════


@dataclass
class AuditEntry:
    """审计条目 — 单次动作执行的完整记录.

    Attributes:
        entry_id: 条目唯一标识
        action_id: 关联的动作 ID
        action_type: 动作类型
        reason: 执行原因
        confidence: 决策置信度
        executor: 执行器名称
        before: 执行前状态
        after: 执行后状态
        result: 执行结果状态
        error_message: 错误信息
        node_id: 关联的 ActionNode ID
        plan_id: 关联的 ActionPlan ID
        task_id: 关联的 ExecutionTask ID
        decision_id: 关联的决策 ID
        timestamp: 记录时间
        metadata: 扩展元数据
    """
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: ExecutionActionType = ExecutionActionType.MONITOR
    reason: str = ""
    confidence: float = 0.0
    executor: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    result: ExecutionResultStatus = ExecutionResultStatus.SUCCESS
    error_message: str = ""
    node_id: str = ""
    plan_id: str = ""
    task_id: str = ""
    decision_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_execution_result(
        cls,
        result: ExecutionResult,
        reason: str = "",
        node_id: str = "",
        plan_id: str = "",
        task_id: str = "",
        decision_id: str = "",
    ) -> AuditEntry:
        """从 ExecutionResult 创建审计条目.

        Args:
            result: 执行结果
            reason: 执行原因
            node_id: 节点 ID
            plan_id: 计划 ID
            task_id: 任务 ID
            decision_id: 决策 ID

        Returns:
            AuditEntry: 审计条目
        """
        return cls(
            action_id=result.action_id,
            action_type=result.action_type,
            reason=reason or result.reason,
            confidence=result.confidence,
            executor=result.executor,
            before=result.before,
            after=result.after,
            result=result.status,
            error_message=result.error_message,
            node_id=node_id,
            plan_id=plan_id,
            task_id=task_id,
            decision_id=decision_id,
            metadata=result.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "executor": self.executor,
            "before": self.before,
            "after": self.after,
            "result": self.result.value,
            "error_message": self.error_message,
            "node_id": self.node_id,
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @property
    def is_success(self) -> bool:
        return self.result == ExecutionResultStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.result in {ExecutionResultStatus.FAILED, ExecutionResultStatus.TIMED_OUT}

    @property
    def needs_approval(self) -> bool:
        return self.result == ExecutionResultStatus.PENDING_APPROVAL


# ═══════════════════════════════════════════════════════════════
# Audit Log
# ═══════════════════════════════════════════════════════════════


class AuditLog:
    """审计日志 — 存储和查询执行记录.

    用法:
        log = AuditLog()
        log.record(result, reason="winner creative detected", task_id="task_001")
        log.record(result, reason="budget scale approved", task_id="task_001")

        # 查询
        entries = log.get_by_task("task_001")
        failed = log.get_failed()
        stats = log.stats()
    """

    def __init__(self):
        self._entries: list[AuditEntry] = []

    # ── 记录 ──────────────────────────────────────────────────

    def record(
        self,
        result: ExecutionResult,
        reason: str = "",
        node_id: str = "",
        plan_id: str = "",
        task_id: str = "",
        decision_id: str = "",
    ) -> AuditEntry:
        """记录一条执行审计.

        Args:
            result: 执行结果
            reason: 执行原因
            node_id: 节点 ID
            plan_id: 计划 ID
            task_id: 任务 ID
            decision_id: 决策 ID

        Returns:
            AuditEntry: 创建的审计条目
        """
        entry = AuditEntry.from_execution_result(
            result,
            reason=reason,
            node_id=node_id,
            plan_id=plan_id,
            task_id=task_id,
            decision_id=decision_id,
        )
        self._entries.append(entry)
        return entry

    def record_entry(self, entry: AuditEntry) -> None:
        """直接记录审计条目."""
        self._entries.append(entry)

    # ── 查询 ──────────────────────────────────────────────────

    def get_by_task(self, task_id: str) -> list[AuditEntry]:
        """按任务 ID 查询."""
        return [e for e in self._entries if e.task_id == task_id]

    def get_by_plan(self, plan_id: str) -> list[AuditEntry]:
        """按计划 ID 查询."""
        return [e for e in self._entries if e.plan_id == plan_id]

    def get_by_decision(self, decision_id: str) -> list[AuditEntry]:
        """按决策 ID 查询."""
        return [e for e in self._entries if e.decision_id == decision_id]

    def get_by_action_type(self, action_type: ExecutionActionType) -> list[AuditEntry]:
        """按动作类型查询."""
        return [e for e in self._entries if e.action_type == action_type]

    def get_successful(self) -> list[AuditEntry]:
        """获取所有成功的记录."""
        return [e for e in self._entries if e.is_success]

    def get_failed(self) -> list[AuditEntry]:
        """获取所有失败的记录."""
        return [e for e in self._entries if e.is_failed]

    def get_pending_approval(self) -> list[AuditEntry]:
        """获取所有待审批的记录."""
        return [e for e in self._entries if e.needs_approval]

    def get_recent(self, n: int = 10) -> list[AuditEntry]:
        """获取最近的 N 条记录."""
        return self._entries[-n:]

    def get_all(self) -> list[AuditEntry]:
        """获取所有记录."""
        return list(self._entries)

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取审计日志统计."""
        total = len(self._entries)
        if total == 0:
            return {
                "total": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "by_action_type": {},
                "by_executor": {},
            }

        success = len(self.get_successful())
        failed = len(self.get_failed())

        by_type: dict[str, int] = {}
        by_executor: dict[str, int] = {}
        for e in self._entries:
            by_type[e.action_type.value] = by_type.get(e.action_type.value, 0) + 1
            by_executor[e.executor] = by_executor.get(e.executor, 0) + 1

        return {
            "total": total,
            "success_count": success,
            "failure_count": failed,
            "success_rate": round(success / total, 4) if total else 0.0,
            "by_action_type": by_type,
            "by_executor": by_executor,
        }

    def to_memory_format(self) -> list[dict[str, Any]]:
        """转换为 E13.4 Memory 兼容格式.

        Returns:
            list[dict]: 可写入 PatternMemory 的记录列表
        """
        return [
            {
                "action_id": e.action_id,
                "action_type": e.action_type.value,
                "reason": e.reason,
                "confidence": e.confidence,
                "executor": e.executor,
                "result": e.result.value,
                "before": e.before,
                "after": e.after,
                "task_id": e.task_id,
                "decision_id": e.decision_id,
                "timestamp": e.timestamp,
            }
            for e in self._entries
        ]

    # ── 清理 ──────────────────────────────────────────────────

    def clear(self) -> None:
        """清空所有记录."""
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)