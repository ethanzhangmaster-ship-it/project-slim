"""E13.6.3 Base Executor — 执行器基类.

所有 Executor 的抽象基类，定义统一的执行接口和 guard_context 安全钩子。

核心设计:
  - execute(): 统一入口，接收 GuardContext 进行安全校验
  - _do_execute(): 子类实现具体执行逻辑
  - _rollback(): 子类实现回滚逻辑
  - GuardContext: 安全上下文，E13.6.3 预留，E13.6.4 完整实现

连接:
  E13.6.3 ExecutionEngine → BaseExecutor → ConcreteExecutor
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from .models import ExecutionAction, ExecutionActionType, ExecutionDomain


# ═══════════════════════════════════════════════════════════════
# Execution Result
# ═══════════════════════════════════════════════════════════════


class ExecutionResultStatus(str, Enum):
    """执行结果状态."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING_APPROVAL = "pending_approval"  # 需要人工确认
    ROLLED_BACK = "rolled_back"
    TIMED_OUT = "timed_out"


@dataclass
class ExecutionResult:
    """执行结果 — 单次动作执行的结果.

    Attributes:
        result_id: 结果唯一标识
        action_id: 关联的动作 ID
        action_type: 动作类型
        status: 执行结果状态
        executor: 执行器名称
        before: 执行前状态 (用于审计)
        after: 执行后状态 (用于审计)
        reason: 执行原因
        confidence: 置信度
        started_at: 开始时间
        completed_at: 完成时间
        error_message: 错误信息
        metadata: 扩展元数据
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: ExecutionActionType = ExecutionActionType.MONITOR
    status: ExecutionResultStatus = ExecutionResultStatus.SUCCESS
    executor: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    confidence: float = 0.0
    started_at: str = ""
    completed_at: str = ""
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionResultStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == ExecutionResultStatus.FAILED

    @property
    def needs_approval(self) -> bool:
        return self.status == ExecutionResultStatus.PENDING_APPROVAL

    @property
    def duration_ms(self) -> float:
        """计算执行耗时 (毫秒)."""
        if not self.started_at or not self.completed_at:
            return 0.0
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            return (end - start).total_seconds() * 1000
        except (ValueError, TypeError):
            return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "status": self.status.value,
            "executor": self.executor,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
            "confidence": self.confidence,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Guard Context (E13.6.3 预留, E13.6.4 完整实现)
# ═══════════════════════════════════════════════════════════════


@dataclass
class GuardContext:
    """安全上下文 — 执行前的安全校验上下文.

    E13.6.3: 基础字段，用于 Executor 内部的简单校验
    E13.6.4: 完整 Safety Layer 实现，包含 cooldown / historical failure 等

    Attributes:
        risk_level: 风险等级
        requires_approval: 是否需要审批
        budget_impact: 预算影响 (金额)
        confidence: 决策置信度
        cooldown_minutes: 冷却时间 (分钟)
        max_retries: 最大重试次数
        allowed_domains: 允许执行的领域
        metadata: 扩展元数据
    """
    risk_level: str = "safe"
    requires_approval: bool = False
    budget_impact: float = 0.0
    confidence: float = 0.0
    cooldown_minutes: int = 0
    max_retries: int = 3
    allowed_domains: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_risk(self) -> bool:
        return self.risk_level in {"high", "critical"}


# ═══════════════════════════════════════════════════════════════
# Base Executor
# ═══════════════════════════════════════════════════════════════


class BaseExecutor(ABC):
    """执行器基类 — 所有 Executor 的抽象基类.

    子类必须实现:
      - _do_execute(action, guard_context) -> ExecutionResult
      - _rollback(action) -> ExecutionResult (可选)

    用法:
        class CreativeExecutor(BaseExecutor):
            def _do_execute(self, action, guard_context):
                # 执行素材生成逻辑
                return ExecutionResult(...)

            def _rollback(self, action):
                # 回滚素材
                return ExecutionResult(...)
    """

    def __init__(self, name: str = ""):
        self._name = name or self.__class__.__name__
        self._execution_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0

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

    # ── 主执行入口 ────────────────────────────────────────────

    def execute(
        self,
        action: ExecutionAction,
        guard_context: GuardContext | None = None,
    ) -> ExecutionResult:
        """执行动作 — 统一入口.

        Args:
            action: 要执行的 ExecutionAction
            guard_context: 安全上下文 (E13.6.3 预留, E13.6.4 完整使用)

        Returns:
            ExecutionResult: 执行结果
        """
        guard_context = guard_context or GuardContext()

        # 1. 前置校验
        if not self._pre_validate(action, guard_context):
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ExecutionResultStatus.SKIPPED,
                executor=self._name,
                reason="pre_validation_failed",
                confidence=guard_context.confidence,
            )

        # 2. 安全检查
        if guard_context.requires_approval:
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ExecutionResultStatus.PENDING_APPROVAL,
                executor=self._name,
                reason="approval_required",
                confidence=guard_context.confidence,
            )

        self._execution_count += 1
        started_at = datetime.now(timezone.utc).isoformat()

        try:
            # 3. 执行
            result = self._do_execute(action, guard_context)
            result.started_at = started_at
            result.completed_at = datetime.now(timezone.utc).isoformat()
            result.executor = self._name
            result.confidence = guard_context.confidence

            if result.is_success:
                self._success_count += 1
            else:
                self._failure_count += 1

            return result

        except Exception as e:
            self._failure_count += 1
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ExecutionResultStatus.FAILED,
                executor=self._name,
                reason=str(e),
                error_message=str(e),
                confidence=guard_context.confidence,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

    # ── 回滚入口 ──────────────────────────────────────────────

    def rollback(self, action: ExecutionAction) -> ExecutionResult:
        """回滚动作.

        Args:
            action: 要回滚的 ExecutionAction

        Returns:
            ExecutionResult: 回滚结果
        """
        try:
            result = self._rollback(action)
            result.executor = self._name
            result.status = ExecutionResultStatus.ROLLED_BACK
            return result
        except NotImplementedError:
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ExecutionResultStatus.ROLLED_BACK,
                executor=self._name,
                reason="rollback_not_implemented",
            )
        except Exception as e:
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ExecutionResultStatus.FAILED,
                executor=self._name,
                reason=f"rollback_failed: {e}",
                error_message=str(e),
            )

    # ── 子类实现 ──────────────────────────────────────────────

    @abstractmethod
    def _do_execute(
        self,
        action: ExecutionAction,
        guard_context: GuardContext,
    ) -> ExecutionResult:
        """子类实现具体执行逻辑."""
        ...

    def _rollback(self, action: ExecutionAction) -> ExecutionResult:
        """子类实现回滚逻辑 (可选)."""
        raise NotImplementedError(
            f"{self._name} does not implement rollback"
        )

    def _pre_validate(
        self,
        action: ExecutionAction,
        guard_context: GuardContext,
    ) -> bool:
        """前置校验 (子类可覆盖)."""
        return True

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "execution_count": self._execution_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": round(self.success_rate, 4),
        }