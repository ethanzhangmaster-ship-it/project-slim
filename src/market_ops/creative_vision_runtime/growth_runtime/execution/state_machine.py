"""E13.6.3 Execution State Machine — 动作执行生命周期状态机.

管理每个 ActionNode 从创建到完成的全生命周期，包括正常路径和异常回滚路径。

状态转移图:

正常路径:
  CREATED → VALIDATING → READY → EXECUTING → SUCCESS → VERIFYING → COMPLETED

异常路径:
  EXECUTING → FAILED → ROLLBACK_PENDING → ROLLBACK_EXECUTING → ROLLED_BACK

跳过路径:
  VALIDATING → SKIPPED

审批路径:
  EXECUTING → PENDING_APPROVAL → READY

连接:
  E13.6.3 ExecutionEngine → StateMachine → ActionNode
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ExecutionPhase(str, Enum):
    """执行阶段 — 动作生命周期状态."""

    CREATED = "created"                      # 初始创建
    VALIDATING = "validating"                # 前置校验中
    READY = "ready"                          # 校验通过，等待执行
    EXECUTING = "executing"                  # 执行中
    SUCCESS = "success"                      # 执行成功
    VERIFYING = "verifying"                  # 结果验证中
    COMPLETED = "completed"                  # 完整完成

    # 异常路径
    FAILED = "failed"                        # 执行失败
    ROLLBACK_PENDING = "rollback_pending"    # 等待回滚
    ROLLBACK_EXECUTING = "rollback_executing" # 回滚执行中
    ROLLED_BACK = "rolled_back"              # 已回滚

    # 其他
    SKIPPED = "skipped"                      # 跳过
    PENDING_APPROVAL = "pending_approval"    # 等待审批
    TIMED_OUT = "timed_out"                  # 超时


# ── 状态转移规则 ──────────────────────────────────────────────

# 合法状态转移映射
_TRANSITIONS: dict[ExecutionPhase, set[ExecutionPhase]] = {
    ExecutionPhase.CREATED: {
        ExecutionPhase.VALIDATING,
        ExecutionPhase.SKIPPED,
    },
    ExecutionPhase.VALIDATING: {
        ExecutionPhase.READY,
        ExecutionPhase.SKIPPED,
        ExecutionPhase.FAILED,
    },
    ExecutionPhase.READY: {
        ExecutionPhase.EXECUTING,
        ExecutionPhase.SKIPPED,
    },
    ExecutionPhase.EXECUTING: {
        ExecutionPhase.SUCCESS,
        ExecutionPhase.FAILED,
        ExecutionPhase.PENDING_APPROVAL,
        ExecutionPhase.TIMED_OUT,
    },
    ExecutionPhase.SUCCESS: {
        ExecutionPhase.VERIFYING,
        ExecutionPhase.COMPLETED,
    },
    ExecutionPhase.VERIFYING: {
        ExecutionPhase.COMPLETED,
        ExecutionPhase.FAILED,
    },
    ExecutionPhase.COMPLETED: set(),  # 终态

    # 异常路径
    ExecutionPhase.FAILED: {
        ExecutionPhase.ROLLBACK_PENDING,
        ExecutionPhase.COMPLETED,  # 不可回滚动作直接标记完成
    },
    ExecutionPhase.ROLLBACK_PENDING: {
        ExecutionPhase.ROLLBACK_EXECUTING,
    },
    ExecutionPhase.ROLLBACK_EXECUTING: {
        ExecutionPhase.ROLLED_BACK,
        ExecutionPhase.FAILED,
    },
    ExecutionPhase.ROLLED_BACK: set(),  # 终态

    # 审批路径
    ExecutionPhase.PENDING_APPROVAL: {
        ExecutionPhase.READY,       # 审批通过
        ExecutionPhase.SKIPPED,    # 审批拒绝
        ExecutionPhase.FAILED,
    },

    ExecutionPhase.SKIPPED: set(),      # 终态
    ExecutionPhase.TIMED_OUT: {
        ExecutionPhase.FAILED,
        ExecutionPhase.ROLLBACK_PENDING,
    },
}

# 终态集合
_TERMINAL_PHASES = {
    ExecutionPhase.COMPLETED,
    ExecutionPhase.ROLLED_BACK,
    ExecutionPhase.SKIPPED,
}


# ═══════════════════════════════════════════════════════════════
# Transition Record
# ═══════════════════════════════════════════════════════════════


@dataclass
class TransitionRecord:
    """状态转移记录."""
    from_phase: ExecutionPhase
    to_phase: ExecutionPhase
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# Execution State Machine
# ═══════════════════════════════════════════════════════════════


class ExecutionStateMachine:
    """执行状态机 — 管理单个 ActionNode 的执行生命周期.

    用法:
        sm = ExecutionStateMachine()
        sm.transition(ExecutionPhase.VALIDATING, reason="开始校验")
        sm.transition(ExecutionPhase.READY, reason="校验通过")
        sm.transition(ExecutionPhase.EXECUTING, reason="开始执行")
        sm.transition(ExecutionPhase.SUCCESS, reason="执行成功")
        sm.transition(ExecutionPhase.COMPLETED, reason="完成")

        # 查看历史
        for record in sm.history:
            print(f"{record.from_phase} → {record.to_phase}: {record.reason}")
    """

    def __init__(self, node_id: str = ""):
        self._node_id = node_id
        self._current: ExecutionPhase = ExecutionPhase.CREATED
        self._history: list[TransitionRecord] = []
        self._initial_created_at = datetime.now(timezone.utc).isoformat()
        self._last_transition_at = self._initial_created_at

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def current_phase(self) -> ExecutionPhase:
        return self._current

    @property
    def history(self) -> list[TransitionRecord]:
        return list(self._history)

    @property
    def is_terminal(self) -> bool:
        return self._current in _TERMINAL_PHASES

    @property
    def is_running(self) -> bool:
        return self._current == ExecutionPhase.EXECUTING

    @property
    def is_failed(self) -> bool:
        return self._current in {
            ExecutionPhase.FAILED,
            ExecutionPhase.ROLLBACK_PENDING,
            ExecutionPhase.ROLLBACK_EXECUTING,
        }

    @property
    def is_success(self) -> bool:
        return self._current in {
            ExecutionPhase.COMPLETED,
            ExecutionPhase.SUCCESS,
        }

    @property
    def is_rolled_back(self) -> bool:
        return self._current == ExecutionPhase.ROLLED_BACK

    @property
    def transition_count(self) -> int:
        return len(self._history)

    @property
    def created_at(self) -> str:
        return self._initial_created_at

    @property
    def last_transition_at(self) -> str:
        return self._last_transition_at

    # ── 状态转移 ──────────────────────────────────────────────

    def can_transition(self, to_phase: ExecutionPhase) -> bool:
        """检查是否可以转移到目标状态."""
        return to_phase in _TRANSITIONS.get(self._current, set())

    def transition(
        self,
        to_phase: ExecutionPhase,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """执行状态转移.

        Args:
            to_phase: 目标状态
            reason: 转移原因
            metadata: 附加元数据

        Returns:
            bool: 转移是否成功

        Raises:
            ValueError: 非法状态转移
        """
        if not self.can_transition(to_phase):
            raise ValueError(
                f"非法状态转移: {self._current.value} → {to_phase.value}"
            )

        record = TransitionRecord(
            from_phase=self._current,
            to_phase=to_phase,
            reason=reason,
            metadata=metadata or {},
        )
        self._history.append(record)
        self._current = to_phase
        self._last_transition_at = record.timestamp
        return True

    def try_transition(
        self,
        to_phase: ExecutionPhase,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """尝试状态转移，失败时不抛异常.

        Returns:
            bool: 转移是否成功
        """
        try:
            return self.transition(to_phase, reason, metadata)
        except ValueError:
            return False

    # ── 便捷方法 ──────────────────────────────────────────────

    def mark_validating(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.VALIDATING, reason)

    def mark_ready(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.READY, reason)

    def mark_executing(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.EXECUTING, reason)

    def mark_success(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.SUCCESS, reason)

    def mark_verifying(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.VERIFYING, reason)

    def mark_completed(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.COMPLETED, reason)

    def mark_failed(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.FAILED, reason)

    def mark_rollback_pending(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.ROLLBACK_PENDING, reason)

    def mark_rollback_executing(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.ROLLBACK_EXECUTING, reason)

    def mark_rolled_back(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.ROLLED_BACK, reason)

    def mark_skipped(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.SKIPPED, reason)

    def mark_pending_approval(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.PENDING_APPROVAL, reason)

    def mark_timed_out(self, reason: str = "") -> bool:
        return self.transition(ExecutionPhase.TIMED_OUT, reason)

    # ── 完整执行流程 ──────────────────────────────────────────

    def execute_full_cycle(
        self,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> list[TransitionRecord]:
        """执行完整成功路径: CREATED → VALIDATING → READY → EXECUTING → SUCCESS → COMPLETED.

        Returns:
            list[TransitionRecord]: 所有转移记录
        """
        self.mark_validating(reason or "开始校验")
        self.mark_ready(reason or "校验通过")
        self.mark_executing(reason or "开始执行")
        self.mark_success(reason or "执行成功")
        self.mark_completed(reason or "完成")
        return list(self._history)

    def execute_failure_rollback(
        self,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> list[TransitionRecord]:
        """执行异常回滚路径: EXECUTING → FAILED → ROLLBACK_PENDING → ROLLBACK_EXECUTING → ROLLED_BACK.

        Returns:
            list[TransitionRecord]: 所有转移记录
        """
        self.mark_failed(reason or "执行失败")
        self.mark_rollback_pending(reason or "准备回滚")
        self.mark_rollback_executing(reason or "执行回滚")
        self.mark_rolled_back(reason or "回滚完成")
        return list(self._history)

    # ── 序列化 ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self._node_id,
            "current_phase": self._current.value,
            "is_terminal": self.is_terminal,
            "transition_count": self.transition_count,
            "created_at": self._initial_created_at,
            "last_transition_at": self._last_transition_at,
            "history": [
                {
                    "from": r.from_phase.value,
                    "to": r.to_phase.value,
                    "timestamp": r.timestamp,
                    "reason": r.reason,
                }
                for r in self._history
            ],
        }

    @classmethod
    def get_valid_transitions(cls, from_phase: ExecutionPhase) -> set[ExecutionPhase]:
        """获取某状态的所有合法转移目标."""
        return _TRANSITIONS.get(from_phase, set())

    @classmethod
    def get_terminal_phases(cls) -> set[ExecutionPhase]:
        """获取所有终态."""
        return _TERMINAL_PHASES.copy()