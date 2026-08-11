"""E15.0.9 Execution Adapter Base — 统一适配器接口.

定义所有平台适配器的抽象基类 ExecutionAdapter 和统一执行结果
AdapterExecutionResult。

与 E13.6 BaseExecutor 的关系:
  - ExecutionAdapter: E15.0.9 高层适配器接口 (输入 GrowthAction)
  - BaseExecutor:     E13.6 底层执行器接口 (输入 ExecutionAction)
  - Adapter 内部调用 BaseExecutor 完成实际平台 API 调用

设计原则:
  - execute():  统一执行入口
  - validate(): 前置校验
  - rollback(): 回滚操作 (每个 Adapter 必须实现)
  - stats():    执行统计
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .growth_action import ActionType, GrowthAction


# ═══════════════════════════════════════════════════════════════
# Adapter Result Status
# ═══════════════════════════════════════════════════════════════


class AdapterResultStatus(str, Enum):
    """适配器执行结果状态."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING_APPROVAL = "pending_approval"
    ROLLED_BACK = "rolled_back"
    TIMED_OUT = "timed_out"
    DEGRADED = "degraded"  # 降级到 MOCK 模式
    BLOCKED = "blocked"    # 安全策略阻止


# ═══════════════════════════════════════════════════════════════
# Adapter Execution Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class AdapterExecutionResult:
    """E15.0.9 统一执行结果 — 所有 Adapter 的标准输出.

    与 E13.6 ExecutionResult 的关系:
      AdapterExecutionResult 是面向 Agent 的高层结果，
      ExecutionResult 是底层执行器的详细结果。
      Adapter 将 ExecutionResult 转换为 AdapterExecutionResult。

    Attributes:
        execution_id:      执行唯一标识 (UUID)
        action_id:         关联的动作 ID
        action_type:       动作类型
        success:           是否成功 (便捷属性)
        status:            详细状态
        external_id:       外部平台返回的实体 ID (campaign_id / release_id)
        error:             错误信息
        rollback_available: 是否支持回滚
        timestamp:         执行时间戳
        adapter_name:      适配器名称
        confidence:        执行置信度
        metadata:          扩展元数据 (平台特定信息)
    """

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: ActionType = ActionType.NOOP
    success: bool = False
    status: AdapterResultStatus = AdapterResultStatus.SUCCESS
    external_id: str = ""
    error: str = ""
    rollback_available: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    adapter_name: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Serialization ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "success": self.success,
            "status": self.status.value,
            "external_id": self.external_id,
            "error": self.error,
            "rollback_available": self.rollback_available,
            "timestamp": self.timestamp,
            "adapter_name": self.adapter_name,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdapterExecutionResult":
        return cls(
            execution_id=data.get("execution_id", str(uuid.uuid4())),
            action_id=data.get("action_id", ""),
            action_type=ActionType(data.get("action_type", "noop")),
            success=data.get("success", False),
            status=AdapterResultStatus(data.get("status", "success")),
            external_id=data.get("external_id", ""),
            error=data.get("error", ""),
            rollback_available=data.get("rollback_available", False),
            timestamp=data.get("timestamp", ""),
            adapter_name=data.get("adapter_name", ""),
            confidence=data.get("confidence", 0.0),
            metadata=data.get("metadata", {}),
        )

    # ── Factory Methods ──────────────────────────────────────

    @classmethod
    def success_result(
        cls,
        action: GrowthAction,
        external_id: str = "",
        adapter_name: str = "",
        **metadata: Any,
    ) -> "AdapterExecutionResult":
        """创建成功结果."""
        return cls(
            action_id=action.action_id,
            action_type=action.action_type,
            success=True,
            status=AdapterResultStatus.SUCCESS,
            external_id=external_id,
            rollback_available=True,
            adapter_name=adapter_name,
            metadata=metadata,
        )

    @classmethod
    def failure_result(
        cls,
        action: GrowthAction,
        error: str,
        adapter_name: str = "",
        **metadata: Any,
    ) -> "AdapterExecutionResult":
        """创建失败结果."""
        return cls(
            action_id=action.action_id,
            action_type=action.action_type,
            success=False,
            status=AdapterResultStatus.FAILED,
            error=error,
            rollback_available=False,
            adapter_name=adapter_name,
            metadata=metadata,
        )

    @classmethod
    def skipped_result(
        cls,
        action: GrowthAction,
        reason: str,
        adapter_name: str = "",
    ) -> "AdapterExecutionResult":
        """创建跳过结果."""
        return cls(
            action_id=action.action_id,
            action_type=action.action_type,
            success=False,
            status=AdapterResultStatus.SKIPPED,
            error=reason,
            rollback_available=False,
            adapter_name=adapter_name,
        )

    @classmethod
    def blocked_result(
        cls,
        action: GrowthAction,
        reason: str,
        adapter_name: str = "",
    ) -> "AdapterExecutionResult":
        """创建安全阻止结果."""
        return cls(
            action_id=action.action_id,
            action_type=action.action_type,
            success=False,
            status=AdapterResultStatus.BLOCKED,
            error=reason,
            rollback_available=False,
            adapter_name=adapter_name,
        )

    # ── Properties ───────────────────────────────────────────

    @property
    def is_success(self) -> bool:
        return self.status == AdapterResultStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == AdapterResultStatus.FAILED

    @property
    def is_blocked(self) -> bool:
        return self.status == AdapterResultStatus.BLOCKED

    @property
    def needs_rollback(self) -> bool:
        return self.is_failed and self.rollback_available

    def __repr__(self) -> str:
        return (
            f"AdapterResult(id={self.execution_id[:8]}..., "
            f"status={self.status.value}, "
            f"adapter={self.adapter_name})"
        )


# ═══════════════════════════════════════════════════════════════
# Execution Adapter (ABC)
# ═══════════════════════════════════════════════════════════════


class ExecutionAdapter(ABC):
    """E15.0.9 统一执行适配器基类 — 所有平台适配器的抽象基类.

    子类必须实现:
      - execute(action) -> AdapterExecutionResult
      - validate(action) -> bool

    子类可选覆盖:
      - rollback(action, result) -> AdapterExecutionResult

    与 E13.6 BaseExecutor 的关系:
      ExecutionAdapter 是高层抽象，面向 Agent 的 GrowthAction。
      BaseExecutor 是底层抽象，面向平台 API 的 ExecutionAction。
      平台 Adapter 内部将 GrowthAction 转换为 ExecutionAction，
      然后委托给 BaseExecutor 执行。

    用法:
        class MetaAdsAdapter(ExecutionAdapter):
            def execute(self, action):
                # 1. 转换 GrowthAction → ExecutionAction
                # 2. 调用 MetaExecutor.execute()
                # 3. 转换 ExecutionResult → AdapterExecutionResult
                ...

            def validate(self, action):
                return action.action_type in SUPPORTED_ACTIONS
    """

    def __init__(self, name: str = ""):
        self._name = name or self.__class__.__name__
        self._execution_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0
        self._rollback_count: int = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def execution_count(self) -> int:
        return self._execution_count

    @property
    def success_rate(self) -> float:
        if self._execution_count == 0:
            return 1.0
        return self._success_count / self._execution_count

    # ── Abstract Interface ───────────────────────────────────

    @abstractmethod
    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        """执行动作.

        Args:
            action: GrowthAction 高层动作

        Returns:
            AdapterExecutionResult: 统一执行结果
        """
        ...

    @abstractmethod
    def validate(self, action: GrowthAction) -> bool:
        """前置校验 — 检查动作是否可执行.

        Args:
            action: GrowthAction 高层动作

        Returns:
            bool: True 如果动作有效
        """
        ...

    # ── Rollback ─────────────────────────────────────────────

    def rollback(
        self,
        action: GrowthAction,
        result: AdapterExecutionResult,
    ) -> AdapterExecutionResult:
        """回滚动作 — 将执行结果恢复到执行前状态.

        默认实现返回 "rollback_not_implemented"。
        子类应覆盖此方法以实现平台特定的回滚逻辑。

        Args:
            action: 原始 GrowthAction
            result: 原始执行结果

        Returns:
            AdapterExecutionResult: 回滚结果
        """
        self._rollback_count += 1
        return AdapterExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            success=False,
            status=AdapterResultStatus.ROLLED_BACK,
            error=f"rollback_not_implemented for {self._name}",
            rollback_available=False,
            adapter_name=self._name,
        )

    # ── Internal Helpers ─────────────────────────────────────

    def _record_success(self) -> None:
        self._execution_count += 1
        self._success_count += 1

    def _record_failure(self) -> None:
        self._execution_count += 1
        self._failure_count += 1

    def _record_rollback(self) -> None:
        self._rollback_count += 1

    # ── Stats ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "execution_count": self._execution_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "rollback_count": self._rollback_count,
            "success_rate": round(self.success_rate, 4),
        }

    def __repr__(self) -> str:
        return f"{self._name}(executions={self._execution_count}, rate={self.success_rate:.2%})"


__all__ = [
    "AdapterResultStatus",
    "AdapterExecutionResult",
    "ExecutionAdapter",
]