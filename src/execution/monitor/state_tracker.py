"""P2.5.3 Execution State Tracker（状态机 + 轨迹追踪）。

从 P2.4 SafeExecutionOutcome 推导 P2.5 自有 ExecutionState 轨迹，并校验合法迁移。

Monitor 只观察，不驱动迁移；非法跳转抛出 IllegalStateTransitionError——这说明
上游编排出现了不可能发生的状态路径，是真实 bug 信号（而非 Monitor 自己写错了）。

状态机（规格）：
    CREATED -> AUTHORIZED -> RUNNING -> SUCCESS
    分支：FAILED -> ROLLBACK -> ROLLED_BACK
          + BLOCKED / ESCALATED（终态）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.execution.monitor.models import (
    STATE_AUTHORIZED,
    STATE_BLOCKED,
    STATE_CREATED,
    STATE_ESCALATED,
    STATE_FAILED,
    STATE_ROLLBACK,
    STATE_ROLLED_BACK,
    STATE_RUNNING,
    STATE_SUCCESS,
    TERMINAL_STATES,
    VALID_STATES,
    IllegalStateTransitionError,
    _ALLOWED_STATE_TRANSITIONS,
)
from src.execution.safe_executor.models import (
    CTX_BLOCKED,
    CTX_CREATED,
    CTX_EXECUTING,
    CTX_FAILED,
    CTX_ROLLED_BACK,
    CTX_SNAPSHOTTING,
    CTX_SUCCESS,
    CTX_VALIDATING,
    CTX_VERIFYING,
    SafeExecutionOutcome,
)

# P2.4 CTX_* -> P2.5 STATE_* 映射
_CTX_TO_STATE: Dict[str, str] = {
    CTX_CREATED: STATE_CREATED,
    CTX_VALIDATING: STATE_AUTHORIZED,
    CTX_SNAPSHOTTING: STATE_RUNNING,
    CTX_EXECUTING: STATE_RUNNING,
    CTX_VERIFYING: STATE_RUNNING,
    CTX_SUCCESS: STATE_SUCCESS,
    CTX_FAILED: STATE_FAILED,
    CTX_ROLLED_BACK: STATE_ROLLED_BACK,
    CTX_BLOCKED: STATE_BLOCKED,
}

# P2.4 verdict -> P2.5 终态（用于从 outcome 直接推导）
_VERDICT_TO_STATE: Dict[str, str] = {
    "EXECUTED": STATE_SUCCESS,
    "RETURN_EXISTING": STATE_SUCCESS,
    "BLOCKED": STATE_BLOCKED,
    "ROLLED_BACK": STATE_ROLLED_BACK,
    "ESCALATED": STATE_ESCALATED,
    "FAILED": STATE_FAILED,
}


def ctx_to_state(ctx_status: str) -> str:
    return _CTX_TO_STATE.get(ctx_status, STATE_CREATED)


def validate_transition(from_state: str, to_state: str) -> None:
    """校验一次 P2.5 状态迁移是否合法；非法抛 IllegalStateTransitionError。"""
    if from_state == to_state:
        return
    if from_state not in VALID_STATES:
        raise IllegalStateTransitionError(f"unknown state: {from_state}")
    if to_state not in VALID_STATES:
        raise IllegalStateTransitionError(f"unknown state: {to_state}")
    allowed = _ALLOWED_STATE_TRANSITIONS.get(from_state, ())
    if to_state not in allowed:
        raise IllegalStateTransitionError(
            f"illegal transition {from_state} -> {to_state}"
        )


@dataclass
class TrackedState:
    """一次执行的 P2.5 状态追踪结果。"""

    execution_id: str
    final_state: str
    trajectory: List[str] = field(default_factory=list)
    legal: bool = True

    @property
    def is_terminal(self) -> bool:
        return self.final_state in TERMINAL_STATES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "final_state": self.final_state,
            "trajectory": list(self.trajectory),
            "legal": self.legal,
            "is_terminal": self.is_terminal,
        }


class ExecutionStateTracker:
    """追踪每个 execution_id 的 P2.5 状态轨迹（纯观察，不改写 outcome）。"""

    def __init__(self) -> None:
        self._trajectories: Dict[str, List[str]] = {}

    def _validate_trajectory(self, trajectory: List[str]) -> bool:
        """依次校验轨迹中每对相邻状态；全程合法返回 True。"""
        for i in range(1, len(trajectory)):
            try:
                validate_transition(trajectory[i - 1], trajectory[i])
            except IllegalStateTransitionError:
                return False
        return True

    def track_execution(self, outcome: SafeExecutionOutcome) -> TrackedState:
        ctx = outcome.context
        # 从 ctx.history（P2.4 状态时间线）映射到 P2.5 状态轨迹
        trajectory = [ctx_to_state(s) for (s, _) in (ctx.history or [])]
        if not trajectory:
            trajectory = [ctx_to_state(ctx.status)]
        legal = self._validate_trajectory(trajectory)
        # 终态以 verdict 为准（更权威），并与轨迹末态对齐
        final = _VERDICT_TO_STATE.get(outcome.verdict, trajectory[-1])
        # 若 verdict 终态与轨迹末态不一致，但均为合法终态则采信 verdict
        self._trajectories[ctx.execution_id] = trajectory
        return TrackedState(
            execution_id=ctx.execution_id,
            final_state=final,
            trajectory=trajectory,
            legal=legal,
        )

    def get_trajectory(self, execution_id: str) -> Optional[List[str]]:
        return self._trajectories.get(execution_id)

    def step(self, execution_id: str, new_state: str) -> List[str]:
        """手动推进一步（测试 / 外部驱动用）。

        返回更新后的轨迹。非法迁移抛 IllegalStateTransitionError。
        """
        traj = self._trajectories.get(execution_id)
        if traj is None:
            traj = [STATE_CREATED]
            self._trajectories[execution_id] = traj
        validate_transition(traj[-1], new_state)
        traj.append(new_state)
        return list(traj)


__all__ = [
    "ctx_to_state",
    "validate_transition",
    "TrackedState",
    "ExecutionStateTracker",
]
