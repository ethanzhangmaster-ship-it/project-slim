"""E17.6 — Adapter 统一接口。

Adapter 是 Router 与真实执行系统之间唯一的接触面：
- Router 只调 `adapter.execute(action)`，绝不直接调 API。
- 默认全部 SIM（real_api_called=False）；接真实系统时由具体 Adapter
  负责把 real_api_called 置 True 并遵守各自的门控（如 PlayConnector）。
- `rollback(action)` 供状态机 FAILED → ROLLBACK 使用，默认无操作。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import AdapterOutcome, ExecutionAction


@runtime_checkable
class ExecutionAdapter(Protocol):
    """统一执行适配器契约。"""

    name: str
    domain: str

    def execute(self, action: ExecutionAction) -> AdapterOutcome:
        ...

    def rollback(self, action: ExecutionAction) -> AdapterOutcome:
        ...


class BaseSimAdapter:
    """SIM 基类：确定性、无真实 API、可回滚。"""

    name = "sim_adapter"
    domain = ""

    def execute(self, action: ExecutionAction) -> AdapterOutcome:  # pragma: no cover
        raise NotImplementedError

    def rollback(self, action: ExecutionAction) -> AdapterOutcome:
        return AdapterOutcome(
            ok=True,
            detail=f"simulated rollback of {action.action_type} on {action.target or action.game_id}",
            real_api_called=False,
        )


__all__ = ["ExecutionAdapter", "BaseSimAdapter"]
