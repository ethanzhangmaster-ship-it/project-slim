"""E13.7.8 Cycle Gate Models — 学习循环门控协议.

Day 7.8 Step 5:
  定义 Cycle Gate 的 Contract 层，独立控制学习循环的
  继续/暂停/回滚/请求更多数据 决策。

核心模型:
  1. GateDecision          — 门控决策枚举
  2. GateRule              — 门控规则 (条件 → 决策)
  3. CycleGateResult       — 门控结果 (含决策、原因、条件评估)

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 规则可组合，按优先级评估
  - 确定性: 相同输入 → 相同决策
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块

用法:
  from growth_runtime.intelligence.learning.models.cycle_gate_models import (
      GateDecision,
      CycleGateResult,
  )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════
# 1. GateDecision
# ═══════════════════════════════════════════════════════════════


class GateDecision(str, Enum):
    """门控决策 — 学习循环是否继续/暂停/回滚.

    | 决策                 | 含义                          | 后续行为                  |
    |---------------------|------------------------------|--------------------------|
    | CONTINUE             | 继续执行下一周期               | 正常进入 POLICY_DECISION |
    | PAUSE               | 暂停学习循环                   | 等待人工审查或条件改善     |
    | ROLLBACK            | 回滚策略到上一版本              | 恢复 previous_state       |
    | REQUEST_MORE_DATA   | 数据不足，继续采样              | 跳过策略调整，仅积累数据    |
    """

    CONTINUE = "continue"
    PAUSE = "pause"
    ROLLBACK = "rollback"
    REQUEST_MORE_DATA = "request_more_data"


# ═══════════════════════════════════════════════════════════════
# 2. GateRule
# ═══════════════════════════════════════════════════════════════


@dataclass
class GateRule:
    """门控规则 — 单个条件 → 决策 映射.

    Attributes:
        name: 规则名称 (用于审计)
        description: 规则描述
        priority: 优先级 (越小越优先，0 = 最高)
        condition: 条件函数 (context) -> bool
        decision: 满足条件时的决策
        reason_template: 原因模板 (str.format)
    """

    name: str = ""
    description: str = ""
    priority: int = 100
    condition: Callable[[dict[str, Any]], bool] = field(default=lambda _: False)
    decision: str = GateDecision.CONTINUE.value
    reason_template: str = ""

    def evaluate(self, context: dict[str, Any]) -> tuple[bool, str]:
        """评估规则.

        Args:
            context: 评估上下文 (含 feedback, effectiveness, cycle_number, ...)

        Returns:
            (triggered, reason)
        """
        try:
            triggered = self.condition(context)
        except Exception:
            triggered = False

        reason = self.reason_template.format(**context) if triggered else ""
        return triggered, reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "decision": self.decision,
        }


# ═══════════════════════════════════════════════════════════════
# 3. CycleGateResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class CycleGateResult:
    """门控结果 — 一次门控评估的完整输出.

    Attributes:
        gate_id: 门控唯一标识
        cycle_number: 编排周期编号
        decision: 最终决策
        decision_reason: 决策原因
        triggered_rule: 触发的规则名称
        rules_evaluated: 评估的规则数量
        rule_results: 各规则评估结果
        feedback_classification: 反馈分类 (来自 LearningFeedback)
        effectiveness_score: 有效性评分 (来自 LearningEffectiveness)
        learning_gain: 学习增益
        created_at: 创建时间
        metadata: 扩展元数据
    """

    gate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    decision: str = GateDecision.CONTINUE.value
    decision_reason: str = ""
    triggered_rule: str = ""
    rules_evaluated: int = 0
    rule_results: list[dict[str, Any]] = field(default_factory=list)
    feedback_classification: str = ""
    effectiveness_score: float | None = None
    learning_gain: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def should_continue(self) -> bool:
        return self.decision == GateDecision.CONTINUE.value

    @property
    def should_pause(self) -> bool:
        return self.decision == GateDecision.PAUSE.value

    @property
    def should_rollback(self) -> bool:
        return self.decision == GateDecision.ROLLBACK.value

    @property
    def should_request_data(self) -> bool:
        return self.decision == GateDecision.REQUEST_MORE_DATA.value

    @property
    def is_blocking(self) -> bool:
        """是否阻止继续执行."""
        return self.decision != GateDecision.CONTINUE.value

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def continue_result(
        cls,
        cycle_number: int = 0,
        reason: str = "",
        **kwargs: Any,
    ) -> CycleGateResult:
        return cls(
            cycle_number=cycle_number,
            decision=GateDecision.CONTINUE.value,
            decision_reason=reason or "All conditions passed — continue",
            **kwargs,
        )

    @classmethod
    def pause_result(
        cls,
        cycle_number: int = 0,
        reason: str = "",
        triggered_rule: str = "",
        **kwargs: Any,
    ) -> CycleGateResult:
        return cls(
            cycle_number=cycle_number,
            decision=GateDecision.PAUSE.value,
            decision_reason=reason,
            triggered_rule=triggered_rule,
            **kwargs,
        )

    @classmethod
    def rollback_result(
        cls,
        cycle_number: int = 0,
        reason: str = "",
        triggered_rule: str = "",
        **kwargs: Any,
    ) -> CycleGateResult:
        return cls(
            cycle_number=cycle_number,
            decision=GateDecision.ROLLBACK.value,
            decision_reason=reason,
            triggered_rule=triggered_rule,
            **kwargs,
        )

    @classmethod
    def request_data_result(
        cls,
        cycle_number: int = 0,
        reason: str = "",
        **kwargs: Any,
    ) -> CycleGateResult:
        return cls(
            cycle_number=cycle_number,
            decision=GateDecision.REQUEST_MORE_DATA.value,
            decision_reason=reason or "Insufficient data — continue sampling",
            **kwargs,
        )

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "cycle_number": self.cycle_number,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "triggered_rule": self.triggered_rule,
            "rules_evaluated": self.rules_evaluated,
            "rule_results": self.rule_results,
            "feedback_classification": self.feedback_classification,
            "effectiveness_score": self.effectiveness_score,
            "learning_gain": self.learning_gain,
            "should_continue": self.should_continue,
            "should_pause": self.should_pause,
            "should_rollback": self.should_rollback,
            "should_request_data": self.should_request_data,
            "is_blocking": self.is_blocking,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "GateDecision",
    "GateRule",
    "CycleGateResult",
]