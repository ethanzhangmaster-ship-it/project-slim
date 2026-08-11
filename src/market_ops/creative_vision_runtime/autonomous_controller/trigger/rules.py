"""E11.5.2 — Rule Engine。

确定性规则系统，用于判断信号是否构成可执行的机会。

规则类型：
  - high_confidence_market_shift:  confidence > 0.8 → trigger
  - winner_pattern_emerging:       pattern_count > threshold → trigger
  - multi_source_convergence:      multiple sources agree → trigger
  - category_momentum:             category has rising signals → trigger
  - low_confidence_filter:         confidence < 0.3 → ignore
  - stale_signal:                  signal too old → defer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from .models import OpportunitySignal, TriggerAction, TriggerDecision


@dataclass
class Rule:
    """单条检测规则。

    Attributes:
        name:        规则名称
        description: 规则描述
        condition:    条件函数 (signal, context) → bool
        action:       匹配后的动作
        reason:       匹配后的理由
        priority:     规则优先级
        enabled:      是否启用
    """

    name: str = ""
    description: str = ""
    condition: Callable[[OpportunitySignal, dict[str, Any]], bool] = field(
        default=lambda s, ctx: False
    )
    action: TriggerAction = TriggerAction.IGNORE
    reason: str = ""
    priority: int = 0
    enabled: bool = True

    def evaluate(
        self,
        signal: OpportunitySignal,
        context: dict[str, Any] | None = None,
    ) -> TriggerDecision | None:
        """评估规则。

        Args:
            signal:  机会信号
            context: 评估上下文

        Returns:
            TriggerDecision 或 None（规则不匹配）
        """
        if not self.enabled:
            return None

        ctx = context or {}
        if not self.condition(signal, ctx):
            return None

        return TriggerDecision(
            signal_id=signal.signal_id,
            should_trigger=self.action == TriggerAction.START_EVOLUTION,
            action=self.action,
            reason=self.reason,
            confidence=signal.confidence,
        )

    def __repr__(self) -> str:
        return f"Rule({self.name}, action={self.action.value})"


# ═══════════════════════════════════════════════════════════
# Built-in Rules
# ═══════════════════════════════════════════════════════════

def _high_confidence_condition(signal: OpportunitySignal, ctx: dict) -> bool:
    return signal.confidence >= 0.8


def _winner_pattern_emerging_condition(signal: OpportunitySignal, ctx: dict) -> bool:
    threshold = ctx.get("pattern_threshold", 3)
    return signal.pattern_count >= threshold and signal.confidence >= 0.6


def _multi_source_convergence_condition(signal: OpportunitySignal, ctx: dict) -> bool:
    sources = ctx.get("recent_sources", [])
    unique_sources = set(sources)
    return len(unique_sources) >= 2 and signal.confidence >= 0.5


def _category_momentum_condition(signal: OpportunitySignal, ctx: dict) -> bool:
    momentum = ctx.get("category_momentum", 0.0)
    return momentum >= 0.6 and signal.confidence >= 0.5


def _low_confidence_condition(signal: OpportunitySignal, ctx: dict) -> bool:
    return signal.confidence < 0.3


def _stale_signal_condition(signal: OpportunitySignal, ctx: dict) -> bool:
    max_age_hours = ctx.get("max_age_hours", 24)
    if "signal_age_hours" not in ctx:
        return False
    return ctx["signal_age_hours"] > max_age_hours


def _medium_confidence_condition(signal: OpportunitySignal, ctx: dict) -> bool:
    return 0.5 <= signal.confidence < 0.8


def _high_priority_condition(signal: OpportunitySignal, ctx: dict) -> bool:
    return signal.is_high_priority and signal.confidence >= 0.6


def build_default_rules() -> list[Rule]:
    """构建默认规则集。

    规则按优先级排序：
      1. high_confidence_market_shift（最高优）
      2. winner_pattern_emerging
      3. high_priority_signal
      4. multi_source_convergence
      5. category_momentum
      6. medium_confidence_queue
      7. low_confidence_filter
      8. stale_signal_defer
    """
    return [
        Rule(
            name="high_confidence_market_shift",
            description="Confidence >= 0.8: immediately trigger evolution",
            condition=_high_confidence_condition,
            action=TriggerAction.START_EVOLUTION,
            reason="High confidence signal detected",
            priority=100,
        ),
        Rule(
            name="winner_pattern_emerging",
            description="Multiple patterns detected with sufficient confidence",
            condition=_winner_pattern_emerging_condition,
            action=TriggerAction.START_EVOLUTION,
            reason="Winner pattern emerging",
            priority=90,
        ),
        Rule(
            name="high_priority_signal",
            description="High priority signal with sufficient confidence",
            condition=_high_priority_condition,
            action=TriggerAction.START_EVOLUTION,
            reason="High priority signal detected",
            priority=85,
        ),
        Rule(
            name="multi_source_convergence",
            description="Multiple data sources agree on the same opportunity",
            condition=_multi_source_convergence_condition,
            action=TriggerAction.START_EVOLUTION,
            reason="Multi-source convergence detected",
            priority=80,
        ),
        Rule(
            name="category_momentum",
            description="Category has rising signal momentum",
            condition=_category_momentum_condition,
            action=TriggerAction.START_EVOLUTION,
            reason="Category momentum detected",
            priority=70,
        ),
        Rule(
            name="medium_confidence_queue",
            description="Confidence 0.5-0.8: queue for further evaluation",
            condition=_medium_confidence_condition,
            action=TriggerAction.QUEUE,
            reason="Medium confidence, queue for evaluation",
            priority=50,
        ),
        Rule(
            name="low_confidence_filter",
            description="Confidence < 0.3: ignore",
            condition=_low_confidence_condition,
            action=TriggerAction.IGNORE,
            reason="Low confidence signal, ignored",
            priority=30,
        ),
        Rule(
            name="stale_signal_defer",
            description="Signal too old: defer",
            condition=_stale_signal_condition,
            action=TriggerAction.DEFER,
            reason="Stale signal, deferred",
            priority=20,
        ),
    ]