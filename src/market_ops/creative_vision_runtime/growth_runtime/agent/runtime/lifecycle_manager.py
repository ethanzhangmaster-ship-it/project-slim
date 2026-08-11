"""E13.7.4.1 Lifecycle Manager — Agent 生命周期管理.

LifecycleManager 负责 ProductionGrowthRuntime 的启停控制:

状态流:
  CREATED → INITIALIZING → LOADING_MEMORY → CONNECTING_TOOLS → RUNNING
  RUNNING → PAUSED → RUNNING
  RUNNING → SAFE_MODE → RUNNING
  RUNNING → STOPPING → STOPPED
  RUNNING → FAILED → SAFE_MODE

特性:
  - 分阶段初始化 (记忆加载 → 工具连接)
  - 优雅暂停/恢复
  - 安全模式进入/退出
  - 初始化失败回滚
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from .runtime_events import EventBus, RuntimeEventType
from .runtime_state import RuntimeState, RuntimeStatus


class LifecycleError(Exception):
    """生命周期错误."""
    pass


class LifecycleManager:
    """Agent 生命周期管理器.

    用法:
        lm = LifecycleManager(state, event_bus)
        lm.on_initialize(lambda: load_memory())
        lm.on_connect_tools(lambda: connect_adapters())
        lm.start()
        lm.stop()
    """

    def __init__(
        self,
        state: RuntimeState | None = None,
        event_bus: EventBus | None = None,
    ):
        self._state = state or RuntimeState()
        self._event_bus = event_bus or EventBus()

        # 初始化钩子
        self._init_hooks: list[Callable[[], None]] = []
        self._memory_load_hooks: list[Callable[[], None]] = []
        self._tool_connect_hooks: list[Callable[[], None]] = []
        self._shutdown_hooks: list[Callable[[], None]] = []

        # 控制锁
        self._lock = threading.Lock()

    # ── Properties ────────────────────────────────────────────

    @property
    def status(self) -> RuntimeStatus:
        return self._state.status

    @property
    def is_running(self) -> bool:
        return self._state.status == RuntimeStatus.RUNNING

    @property
    def is_paused(self) -> bool:
        return self._state.status == RuntimeStatus.PAUSED

    @property
    def is_safe_mode(self) -> bool:
        return self._state.status == RuntimeStatus.SAFE_MODE

    # ── 钩子注册 ──────────────────────────────────────────────

    def on_initialize(self, hook: Callable[[], None]) -> None:
        """注册初始化钩子."""
        self._init_hooks.append(hook)

    def on_load_memory(self, hook: Callable[[], None]) -> None:
        """注册记忆加载钩子."""
        self._memory_load_hooks.append(hook)

    def on_connect_tools(self, hook: Callable[[], None]) -> None:
        """注册工具连接钩子."""
        self._tool_connect_hooks.append(hook)

    def on_shutdown(self, hook: Callable[[], None]) -> None:
        """注册关闭钩子."""
        self._shutdown_hooks.append(hook)

    # ── 生命周期操作 ──────────────────────────────────────────

    def initialize(self) -> bool:
        """初始化 Agent.

        CREATED → INITIALIZING

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if not self._state.transition(RuntimeStatus.INITIALIZING):
                return False

        self._event_bus.emit(
            RuntimeEventType.AGENT_STARTED,
            source="lifecycle",
            data={"phase": "initialize"},
        )

        try:
            for hook in self._init_hooks:
                hook()
            return True
        except Exception as e:
            self._state.transition(RuntimeStatus.FAILED)
            self._event_bus.emit(
                RuntimeEventType.ERROR_OCCURRED,
                source="lifecycle",
                error=str(e),
            )
            return False

    def load_memory(self) -> bool:
        """加载记忆.

        INITIALIZING → LOADING_MEMORY

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if not self._state.transition(RuntimeStatus.LOADING_MEMORY):
                return False

        try:
            for hook in self._memory_load_hooks:
                hook()
            return True
        except Exception as e:
            self._state.transition(RuntimeStatus.FAILED)
            self._event_bus.emit(
                RuntimeEventType.ERROR_OCCURRED,
                source="lifecycle",
                error=f"Memory load failed: {e}",
            )
            return False

    def connect_tools(self) -> bool:
        """连接工具.

        LOADING_MEMORY → CONNECTING_TOOLS

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if not self._state.transition(RuntimeStatus.CONNECTING_TOOLS):
                return False

        try:
            for hook in self._tool_connect_hooks:
                hook()
            return True
        except Exception as e:
            self._state.transition(RuntimeStatus.FAILED)
            self._event_bus.emit(
                RuntimeEventType.ERROR_OCCURRED,
                source="lifecycle",
                error=f"Tool connection failed: {e}",
            )
            return False

    def start(self) -> bool:
        """启动 Agent (完整初始化流程).

        CREATED → INITIALIZING → LOADING_MEMORY → CONNECTING_TOOLS → RUNNING

        Returns:
            bool: 是否成功
        """
        if not self.initialize():
            return False
        if not self.load_memory():
            return False
        if not self.connect_tools():
            return False

        with self._lock:
            self._state.started_at = datetime.now(timezone.utc).isoformat()
            self._state.transition(RuntimeStatus.RUNNING)

        self._event_bus.emit(
            RuntimeEventType.AGENT_STARTED,
            source="lifecycle",
            data={"status": "running"},
        )

        return True

    def pause(self) -> bool:
        """暂停 Agent.

        RUNNING → PAUSED

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if not self._state.transition(RuntimeStatus.PAUSED):
                return False

        self._event_bus.emit(
            RuntimeEventType.AGENT_PAUSED,
            source="lifecycle",
        )
        return True

    def resume(self) -> bool:
        """恢复 Agent.

        PAUSED → RUNNING

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if not self._state.transition(RuntimeStatus.RUNNING):
                return False

        self._event_bus.emit(
            RuntimeEventType.AGENT_RESUMED,
            source="lifecycle",
        )
        return True

    def enter_safe_mode(self, reason: str = "") -> bool:
        """进入安全模式.

        RUNNING/FAILED → SAFE_MODE

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if not self._state.transition(RuntimeStatus.SAFE_MODE):
                return False

        self._event_bus.emit(
            RuntimeEventType.SAFE_MODE_ENTERED,
            source="lifecycle",
            data={"reason": reason},
        )
        return True

    def exit_safe_mode(self) -> bool:
        """退出安全模式.

        SAFE_MODE → RUNNING

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if not self._state.transition(RuntimeStatus.RUNNING):
                return False

        self._event_bus.emit(
            RuntimeEventType.SAFE_MODE_EXITED,
            source="lifecycle",
        )
        return True

    def stop(self) -> bool:
        """停止 Agent.

        RUNNING/PAUSED/SAFE_MODE → STOPPING → STOPPED

        Returns:
            bool: 是否成功
        """
        with self._lock:
            self._state.transition(RuntimeStatus.STOPPING)

        self._event_bus.emit(
            RuntimeEventType.AGENT_STOPPED,
            source="lifecycle",
            data={"phase": "shutdown"},
        )

        try:
            for hook in self._shutdown_hooks:
                hook()
        except Exception:
            pass

        self._state.transition(RuntimeStatus.STOPPED)
        return True

    def fail(self, error: str = "") -> None:
        """标记为失败状态."""
        self._state.transition(RuntimeStatus.FAILED)
        self._event_bus.emit(
            RuntimeEventType.ERROR_OCCURRED,
            source="lifecycle",
            error=error,
        )

    def reset(self) -> None:
        """重置生命周期."""
        self._state.reset()
        self._init_hooks.clear()
        self._memory_load_hooks.clear()
        self._tool_connect_hooks.clear()
        self._shutdown_hooks.clear()


def create_lifecycle_manager(
    state: RuntimeState | None = None,
    event_bus: EventBus | None = None,
) -> LifecycleManager:
    """创建默认生命周期管理器."""
    return LifecycleManager(state=state, event_bus=event_bus)