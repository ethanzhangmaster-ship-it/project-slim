"""E15.3.1 Lifecycle Manager — 生命周期管理.

管理 Operator 状态转换:

  IDLE → OBSERVING → THINKING → DECIDING → EXECUTING → LEARNING
    ↑        ↓            ↓           ↓           ↓          ↓
    └─ PAUSED ←───────────┴───────────┴───────────┴──────────┘
                                      ↓
                                   STOPPED
                                      ↓
                                    ERROR
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import OperatorState


# ═══════════════════════════════════════════════════════════════
# State Transition Map
# ═══════════════════════════════════════════════════════════════

# 定义合法状态转换
VALID_TRANSITIONS: dict[OperatorState, set[OperatorState]] = {
    OperatorState.IDLE: {
        OperatorState.OBSERVING,
        OperatorState.STOPPED,
    },
    OperatorState.OBSERVING: {
        OperatorState.THINKING,
        OperatorState.PAUSED,
        OperatorState.ERROR,
        OperatorState.STOPPED,
    },
    OperatorState.THINKING: {
        OperatorState.DECIDING,
        OperatorState.PAUSED,
        OperatorState.ERROR,
        OperatorState.STOPPED,
    },
    OperatorState.DECIDING: {
        OperatorState.EXECUTING,
        OperatorState.OBSERVING,  # 无动作时回到观察
        OperatorState.PAUSED,
        OperatorState.ERROR,
        OperatorState.STOPPED,
    },
    OperatorState.EXECUTING: {
        OperatorState.LEARNING,
        OperatorState.PAUSED,
        OperatorState.ERROR,
        OperatorState.STOPPED,
    },
    OperatorState.LEARNING: {
        OperatorState.OBSERVING,  # 学习完成后回到观察
        OperatorState.PAUSED,
        OperatorState.ERROR,
        OperatorState.STOPPED,
    },
    OperatorState.PAUSED: {
        OperatorState.OBSERVING,  # 恢复后进入观察
        OperatorState.STOPPED,
    },
    OperatorState.STOPPED: {
        OperatorState.IDLE,  # 可重新启动
    },
    OperatorState.ERROR: {
        OperatorState.IDLE,       # 恢复
        OperatorState.STOPPED,     # 停止
    },
}


# ═══════════════════════════════════════════════════════════════
# Lifecycle Manager
# ═══════════════════════════════════════════════════════════════


class LifecycleManager:
    """E15.3.1 生命周期管理器.

    管理 Operator 状态转换，确保合法转换。

    用法:
        lm = LifecycleManager()
        lm.start()           # IDLE → OBSERVING
        lm.transition(OperatorState.THINKING)
        lm.pause()
        lm.stop()
    """

    def __init__(self):
        self._state: OperatorState = OperatorState.IDLE
        self._history: list[dict[str, Any]] = []
        self._started_at: str | None = None
        self._paused_at: str | None = None
        self._stopped_at: str | None = None

    @property
    def state(self) -> OperatorState:
        """当前状态."""
        return self._state

    @property
    def started_at(self) -> str | None:
        return self._started_at

    @property
    def paused_at(self) -> str | None:
        return self._paused_at

    @property
    def stopped_at(self) -> str | None:
        return self._stopped_at

    # ── Core API ────────────────────────────────────────────────

    def transition(self, target: OperatorState) -> bool:
        """状态转换.

        Args:
            target: 目标状态

        Returns:
            bool: 转换是否成功
        """
        if not self.can_transition(target):
            return False

        old_state = self._state
        self._state = target
        self._record_transition(old_state, target, True)
        return True

    def can_transition(self, target: OperatorState) -> bool:
        """检查是否可以转换到目标状态."""
        allowed = VALID_TRANSITIONS.get(self._state, set())
        return target in allowed

    # ── Convenience Methods ─────────────────────────────────────

    def start(self) -> bool:
        """启动 Operator."""
        if self._state != OperatorState.IDLE:
            return False
        if self.transition(OperatorState.OBSERVING):
            self._started_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def pause(self) -> bool:
        """暂停."""
        if self.transition(OperatorState.PAUSED):
            self._paused_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def resume(self) -> bool:
        """恢复."""
        if self._state != OperatorState.PAUSED:
            return False
        if self.transition(OperatorState.OBSERVING):
            self._paused_at = None
            return True
        return False

    def stop(self) -> bool:
        """停止."""
        if self.transition(OperatorState.STOPPED):
            self._stopped_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def error(self) -> bool:
        """进入错误状态."""
        return self.transition(OperatorState.ERROR)

    def reset(self) -> None:
        """重置到 IDLE."""
        self._state = OperatorState.IDLE
        self._started_at = None
        self._paused_at = None
        self._stopped_at = None

    def is_running(self) -> bool:
        """是否在运行中."""
        return self._state in (
            OperatorState.OBSERVING,
            OperatorState.THINKING,
            OperatorState.DECIDING,
            OperatorState.EXECUTING,
            OperatorState.LEARNING,
        )

    def is_stopped(self) -> bool:
        """是否已停止."""
        return self._state == OperatorState.STOPPED

    def is_paused(self) -> bool:
        """是否已暂停."""
        return self._state == OperatorState.PAUSED

    def get_history(self) -> list[dict[str, Any]]:
        """获取状态转换历史."""
        return list(self._history)

    def get_state_summary(self) -> dict[str, Any]:
        """获取状态摘要."""
        return {
            "current_state": self._state.value,
            "is_running": self.is_running(),
            "is_paused": self.is_paused(),
            "is_stopped": self.is_stopped(),
            "started_at": self._started_at,
            "paused_at": self._paused_at,
            "stopped_at": self._stopped_at,
            "transitions": len(self._history),
        }

    # ── Internal ────────────────────────────────────────────────

    def _record_transition(
        self, from_state: OperatorState, to_state: OperatorState, success: bool
    ) -> None:
        self._history.append({
            "from": from_state.value,
            "to": to_state.value,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


__all__ = ["LifecycleManager", "VALID_TRANSITIONS"]