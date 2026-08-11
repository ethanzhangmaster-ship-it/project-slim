"""E15.3.2 Cycle State Machine — 决策周期状态机.

管理 DecisionCycle 的状态转换，保证合法状态流转。

合法转换:
  CREATED    → OBSERVING
  OBSERVING  → ANALYZING, FAILED, PAUSED
  ANALYZING  → PLANNING, FAILED, PAUSED
  PLANNING   → DECIDING, FAILED, PAUSED
  DECIDING   → EXECUTING, FAILED, PAUSED
  EXECUTING  → EVALUATING, FAILED, PAUSED
  EVALUATING → LEARNING, FAILED, PAUSED
  LEARNING   → COMPLETED, FAILED, PAUSED
  COMPLETED  → OBSERVING (next cycle)
  FAILED     → OBSERVING (recovery)
  PAUSED     → OBSERVING (resume)
"""

from __future__ import annotations

from .models import CycleState, DecisionCycle


# ═══════════════════════════════════════════════════════════════
# Valid Transitions
# ═══════════════════════════════════════════════════════════════

VALID_TRANSITIONS: dict[CycleState, set[CycleState]] = {
    CycleState.CREATED:    {CycleState.OBSERVING},
    CycleState.OBSERVING:  {CycleState.ANALYZING, CycleState.FAILED, CycleState.PAUSED},
    CycleState.ANALYZING:  {CycleState.PLANNING, CycleState.FAILED, CycleState.PAUSED},
    CycleState.PLANNING:   {CycleState.DECIDING, CycleState.FAILED, CycleState.PAUSED},
    CycleState.DECIDING:   {CycleState.EXECUTING, CycleState.FAILED, CycleState.PAUSED},
    CycleState.EXECUTING:  {CycleState.EVALUATING, CycleState.FAILED, CycleState.PAUSED},
    CycleState.EVALUATING: {CycleState.LEARNING, CycleState.FAILED, CycleState.PAUSED},
    CycleState.LEARNING:   {CycleState.COMPLETED, CycleState.FAILED, CycleState.PAUSED},
    CycleState.COMPLETED:  {CycleState.OBSERVING},
    CycleState.FAILED:     {CycleState.OBSERVING, CycleState.CREATED},
    CycleState.PAUSED:     {CycleState.OBSERVING, CycleState.FAILED},
}

# 禁止的转换 (用于验证)
FORBIDDEN_TRANSITIONS: set[tuple[CycleState, CycleState]] = {
    # 不允许跳过核心阶段
    (CycleState.OBSERVING, CycleState.EXECUTING),
    (CycleState.OBSERVING, CycleState.COMPLETED),
    (CycleState.ANALYZING, CycleState.EXECUTING),
    (CycleState.ANALYZING, CycleState.COMPLETED),
    (CycleState.PLANNING, CycleState.COMPLETED),
    (CycleState.DECIDING, CycleState.COMPLETED),
    # 不允许回退
    (CycleState.EXECUTING, CycleState.OBSERVING),
    (CycleState.EXECUTING, CycleState.ANALYZING),
    (CycleState.EVALUATING, CycleState.OBSERVING),
    (CycleState.EVALUATING, CycleState.ANALYZING),
    (CycleState.EVALUATING, CycleState.PLANNING),
    (CycleState.LEARNING, CycleState.OBSERVING),
    (CycleState.LEARNING, CycleState.ANALYZING),
    (CycleState.LEARNING, CycleState.PLANNING),
    (CycleState.LEARNING, CycleState.DECIDING),
    (CycleState.COMPLETED, CycleState.ANALYZING),
    (CycleState.COMPLETED, CycleState.PLANNING),
    (CycleState.COMPLETED, CycleState.DECIDING),
    (CycleState.COMPLETED, CycleState.EXECUTING),
    (CycleState.COMPLETED, CycleState.EVALUATING),
    (CycleState.COMPLETED, CycleState.LEARNING),
    # 不允许从终态到终态 (除了 FAILED→CREATED)
    (CycleState.COMPLETED, CycleState.FAILED),
    (CycleState.COMPLETED, CycleState.PAUSED),
    (CycleState.PAUSED, CycleState.COMPLETED),
}


# ═══════════════════════════════════════════════════════════════
# Cycle State Machine
# ═══════════════════════════════════════════════════════════════


class CycleStateMachine:
    """E15.3.2 决策周期状态机.

    管理 DecisionCycle 的状态转换，保证:
      - 只能按合法路径转换
      - 禁止跳过核心阶段
      - 禁止非法回退

    用法:
        sm = CycleStateMachine()
        sm.transition(cycle, CycleState.ANALYZING)
        assert sm.current_state == CycleState.ANALYZING
    """

    def __init__(self) -> None:
        self._current_state: CycleState = CycleState.CREATED
        self._history: list[CycleState] = [CycleState.CREATED]
        self._transition_count: int = 0
        self._error_count: int = 0

    # ── Properties ──────────────────────────────────────────────

    @property
    def current_state(self) -> CycleState:
        return self._current_state

    @property
    def history(self) -> list[CycleState]:
        return list(self._history)

    @property
    def transition_count(self) -> int:
        return self._transition_count

    @property
    def error_count(self) -> int:
        return self._error_count

    # ── Core: Transition ─────────────────────────────────────────

    def transition(self, cycle: DecisionCycle, target: CycleState) -> bool:
        """执行状态转换.

        Args:
            cycle:  当前决策周期
            target: 目标状态

        Returns:
            bool: 是否成功
        """
        if not self.can_transition(cycle.state, target):
            self._error_count += 1
            return False

        self._current_state = target
        cycle.state = target
        self._history.append(target)
        self._transition_count += 1
        return True

    def can_transition(self, current: CycleState, target: CycleState) -> bool:
        """检查是否可以转换.

        Args:
            current: 当前状态
            target:  目标状态

        Returns:
            bool: 是否可以转换
        """
        if current == target:
            return True
        allowed = VALID_TRANSITIONS.get(current, set())
        return target in allowed

    def is_valid_transition(self, current: CycleState, target: CycleState) -> bool:
        """检查是否为合法转换 (语义别名)."""
        return self.can_transition(current, target)

    def is_forbidden(self, current: CycleState, target: CycleState) -> bool:
        """检查是否为禁止转换."""
        return (current, target) in FORBIDDEN_TRANSITIONS

    # ── Lifecycle ───────────────────────────────────────────────

    def reset(self) -> None:
        """重置状态机."""
        self._current_state = CycleState.CREATED
        self._history = [CycleState.CREATED]
        self._transition_count = 0
        self._error_count = 0

    def get_allowed_targets(self) -> set[CycleState]:
        """获取当前状态允许的目标状态."""
        return VALID_TRANSITIONS.get(self._current_state, set())

    def get_state_sequence(self) -> list[CycleState]:
        """获取状态历史序列."""
        return list(self._history)

    # ── Bulk Operations ─────────────────────────────────────────

    def run_sequence(
        self, cycle: DecisionCycle, sequence: list[CycleState]
    ) -> tuple[bool, str | None]:
        """执行一系列状态转换.

        Args:
            cycle:    决策周期
            sequence: 目标状态序列

        Returns:
            (success, error_message)
        """
        for target in sequence:
            if not self.transition(cycle, target):
                return False, (
                    f"Failed to transition from {self._current_state.value} "
                    f"to {target.value}"
                )
        return True, None

    # ── Full Cycle Runner ───────────────────────────────────────

    def run_full_cycle(self, cycle: DecisionCycle) -> tuple[bool, str | None]:
        """执行完整的标准决策周期.

        标准序列: CREATED → OBSERVING → ANALYZING → PLANNING
                  → DECIDING → EXECUTING → EVALUATING
                  → LEARNING → COMPLETED

        Args:
            cycle: 决策周期

        Returns:
            (success, error_message)
        """
        standard_sequence = [
            CycleState.OBSERVING,
            CycleState.ANALYZING,
            CycleState.PLANNING,
            CycleState.DECIDING,
            CycleState.EXECUTING,
            CycleState.EVALUATING,
            CycleState.LEARNING,
            CycleState.COMPLETED,
        ]
        return self.run_sequence(cycle, standard_sequence)

    def to_dict(self) -> dict:
        return {
            "current_state": self._current_state.value,
            "transition_count": self._transition_count,
            "error_count": self._error_count,
            "history": [s.value for s in self._history],
        }


__all__ = [
    "VALID_TRANSITIONS",
    "FORBIDDEN_TRANSITIONS",
    "CycleStateMachine",
]