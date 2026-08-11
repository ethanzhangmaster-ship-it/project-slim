"""E13.6.3 Execution Context — 执行运行时上下文.

封装执行所需的所有上下文信息，包括 GuardContext (安全)、决策来源、任务关联和
运行时配置。E13.6.3 基础版本，E13.6.4 Safety Layer 接入后扩展。

核心设计:
  - ExecutionContext: 执行上下文，包含 GuardContext + 决策/任务/运行时信息
  - GuardContext: 安全上下文 (定义在 base_executor.py)
  - E13.6.3: guard_context 预留 safety_check 接口
  - E13.6.4: Safety Controller 通过 safety_check 钩子注入

连接:
  E13.6.3 ExecutionEngine.execute(plan, context=ExecutionContext)
  E13.6.4 SafetyController → ExecutionContext.safety_check
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base_executor import GuardContext


# ═══════════════════════════════════════════════════════════════
# Execution Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionContext:
    """执行上下文 — 封装执行所需的所有上下文信息.

    Attributes:
        guard_context: 安全上下文 (E13.6.3 基础, E13.6.4 完整)
        decision_id: 关联的决策 ID
        opportunity_id: 关联的机会 ID
        strategy_id: 关联的策略 ID
        task_id: 关联的任务 ID
        user_confirmation: 用户确认状态 (E13.6.3 预留)
        risk_score: 风险评分 [0, 1] (E13.6.3 预留, E13.6.4 计算)
        safety_check: 安全校验函数 (E13.6.3 预留, E13.6.4 注入)
        approval_required: 是否需要审批
        reason: 执行原因
        dry_run: 是否为试运行模式
        timeout_seconds: 执行超时时间
        metadata: 扩展元数据
    """

    guard_context: GuardContext = field(default_factory=GuardContext)
    decision_id: str = ""
    opportunity_id: str = ""
    strategy_id: str = ""
    task_id: str = ""
    user_confirmation: str = "none"  # none | pending | approved | denied
    risk_score: float = 0.0
    safety_check: bool = True
    approval_required: bool = False
    reason: str = ""
    dry_run: bool = False
    timeout_seconds: int = 3600
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        """用户是否已确认."""
        return self.user_confirmation == "approved"

    @property
    def is_denied(self) -> bool:
        """用户是否已拒绝."""
        return self.user_confirmation == "denied"

    @property
    def is_pending_user(self) -> bool:
        """是否等待用户确认."""
        return self.user_confirmation == "pending"

    @property
    def is_high_risk(self) -> bool:
        """是否为高风险操作."""
        return self.guard_context.is_high_risk

    @property
    def needs_approval(self) -> bool:
        """是否需要审批 (安全层 + 用户确认)."""
        return self.approval_required or self.guard_context.requires_approval

    @property
    def can_execute(self) -> bool:
        """是否可以执行 (安全校验通过 + 非 dry_run 或已确认)."""
        if self.dry_run:
            return self.is_approved
        return self.safety_check and not self.is_denied

    def to_dict(self) -> dict[str, Any]:
        return {
            "guard_context": {
                "risk_level": self.guard_context.risk_level,
                "requires_approval": self.guard_context.requires_approval,
                "budget_impact": self.guard_context.budget_impact,
                "confidence": self.guard_context.confidence,
            },
            "decision_id": self.decision_id,
            "opportunity_id": self.opportunity_id,
            "strategy_id": self.strategy_id,
            "task_id": self.task_id,
            "user_confirmation": self.user_confirmation,
            "risk_score": self.risk_score,
            "safety_check": self.safety_check,
            "approval_required": self.approval_required,
            "reason": self.reason,
            "dry_run": self.dry_run,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_guard_context(
        cls,
        guard_context: GuardContext,
        **kwargs,
    ) -> ExecutionContext:
        """从 GuardContext 快速创建 ExecutionContext."""
        return cls(guard_context=guard_context, **kwargs)

    @classmethod
    def safe(cls, **kwargs) -> ExecutionContext:
        """创建安全级别 (低风险) 的上下文."""
        return cls(
            guard_context=GuardContext(risk_level="safe"),
            safety_check=True,
            approval_required=False,
            **kwargs,
        )

    @classmethod
    def medium_risk(cls, **kwargs) -> ExecutionContext:
        """创建中风险上下文."""
        return cls(
            guard_context=GuardContext(risk_level="medium"),
            safety_check=True,
            **kwargs,
        )

    @classmethod
    def high_risk(cls, **kwargs) -> ExecutionContext:
        """创建高风险上下文 (需要审批)."""
        return cls(
            guard_context=GuardContext(
                risk_level="high",
                requires_approval=True,
            ),
            safety_check=True,
            approval_required=True,
            **kwargs,
        )

    @classmethod
    def critical(cls, **kwargs) -> ExecutionContext:
        """创建关键风险上下文 (必须审批)."""
        return cls(
            guard_context=GuardContext(
                risk_level="critical",
                requires_approval=True,
            ),
            safety_check=True,
            approval_required=True,
            user_confirmation="pending",
            **kwargs,
        )