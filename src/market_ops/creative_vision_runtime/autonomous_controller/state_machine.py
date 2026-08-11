"""E11.5.1 — Controller State Machine。

管理 AutonomousCreativeController 的状态转换。

合法转换：
  IDLE → ANALYZING
  ANALYZING → DECIDING | FAILED
  DECIDING → MUTATING | FAILED
  MUTATING → EXECUTING | FAILED
  EXECUTING → COMPLETED | FAILED
  COMPLETED → IDLE
  FAILED → IDLE
"""

from __future__ import annotations

import logging
from typing import Callable, Any

from .models import CycleStatus

logger = logging.getLogger(__name__)


class ControllerStateMachine:
    """控制器状态机。

    管理进化循环的状态转换，确保只有合法转换才能执行。

    Attributes:
        current_state: 当前状态
        transition_count: 转换次数
        history: 状态历史
    """

    # 合法转换表
    VALID_TRANSITIONS: dict[CycleStatus, list[CycleStatus]] = {
        CycleStatus.IDLE: [CycleStatus.ANALYZING],
        CycleStatus.ANALYZING: [CycleStatus.DECIDING, CycleStatus.FAILED],
        CycleStatus.DECIDING: [CycleStatus.MUTATING, CycleStatus.FAILED],
        CycleStatus.MUTATING: [CycleStatus.EXECUTING, CycleStatus.FAILED],
        CycleStatus.EXECUTING: [CycleStatus.COMPLETED, CycleStatus.FAILED],
        CycleStatus.COMPLETED: [CycleStatus.IDLE],
        CycleStatus.FAILED: [CycleStatus.IDLE],
    }

    def __init__(self, initial_state: CycleStatus = CycleStatus.IDLE) -> None:
        self._current_state = initial_state
        self._transition_count: int = 0
        self._history: list[CycleStatus] = [initial_state]
        self._handlers: dict[CycleStatus, list[Callable]] = {}

    # ── State Query ─────────────────────────────────────

    @property
    def current_state(self) -> CycleStatus:
        return self._current_state

    @property
    def transition_count(self) -> int:
        return self._transition_count

    @property
    def history(self) -> list[CycleStatus]:
        return list(self._history)

    @property
    def is_idle(self) -> bool:
        return self._current_state == CycleStatus.IDLE

    @property
    def is_running(self) -> bool:
        return self._current_state in (
            CycleStatus.ANALYZING,
            CycleStatus.DECIDING,
            CycleStatus.MUTATING,
            CycleStatus.EXECUTING,
        )

    @property
    def is_terminal(self) -> bool:
        return self._current_state in (
            CycleStatus.COMPLETED,
            CycleStatus.FAILED,
        )

    # ── Transition ──────────────────────────────────────

    def can_transition(self, to_state: CycleStatus) -> bool:
        """检查是否可以转换到目标状态。"""
        return to_state in self.VALID_TRANSITIONS.get(self._current_state, [])

    def transition(self, to_state: CycleStatus) -> CycleStatus:
        """执行状态转换。

        Args:
            to_state: 目标状态

        Returns:
            转换后的状态

        Raises:
            ValueError: 非法转换
        """
        if not self.can_transition(to_state):
            valid = self.VALID_TRANSITIONS.get(self._current_state, [])
            raise ValueError(
                f"Invalid transition: {self._current_state.value} → {to_state.value}. "
                f"Valid: {[s.value for s in valid]}"
            )

        old_state = self._current_state
        self._current_state = to_state
        self._history.append(to_state)
        self._transition_count += 1

        logger.debug(f"State: {old_state.value} → {to_state.value}")

        # 触发处理器
        self._trigger_handlers(to_state)

        return self._current_state

    def transition_to_analyzing(self) -> CycleStatus:
        return self.transition(CycleStatus.ANALYZING)

    def transition_to_deciding(self) -> CycleStatus:
        return self.transition(CycleStatus.DECIDING)

    def transition_to_mutating(self) -> CycleStatus:
        return self.transition(CycleStatus.MUTATING)

    def transition_to_executing(self) -> CycleStatus:
        return self.transition(CycleStatus.EXECUTING)

    def transition_to_completed(self) -> CycleStatus:
        return self.transition(CycleStatus.COMPLETED)

    def transition_to_failed(self) -> CycleStatus:
        return self.transition(CycleStatus.FAILED)

    def reset(self) -> CycleStatus:
        """重置到 IDLE 状态。"""
        self._current_state = CycleStatus.IDLE
        self._history = [CycleStatus.IDLE]
        return self._current_state

    # ── Event Handlers ──────────────────────────────────

    def on(self, state: CycleStatus, handler: Callable) -> None:
        """注册状态进入处理器。"""
        if state not in self._handlers:
            self._handlers[state] = []
        self._handlers[state].append(handler)

    def _trigger_handlers(self, state: CycleStatus) -> None:
        """触发状态进入处理器。"""
        handlers = self._handlers.get(state, [])
        for handler in handlers:
            try:
                handler(state, self._transition_count)
            except Exception as e:
                logger.error(f"Handler error for state {state.value}: {e}")

    # ── Stats ──────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "current_state": self._current_state.value,
            "transition_count": self._transition_count,
            "history": [s.value for s in self._history],
            "is_idle": self.is_idle,
            "is_running": self.is_running,
            "is_terminal": self.is_terminal,
        }

    def __repr__(self) -> str:
        return (
            f"ControllerStateMachine(state={self._current_state.value}, "
            f"transitions={self._transition_count})"
        )