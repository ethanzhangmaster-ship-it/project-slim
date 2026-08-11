"""E11.5.2 — Trigger Engine。

OpportunitySignal → TriggerDecision → AutonomousCreativeController。

核心职责：
  1. 对 OpportunitySignal 集合进行规则评估
  2. 生成 TriggerDecision（start_evolution/queue/merge/ignore/defer）
  3. 去重和优先级排序
  4. 连接 AutonomousCreativeController

流程：
  Raw Signals
    → OpportunityDetector.detect()
    → OpportunitySignal[]
    → TriggerEngine.evaluate()
    → TriggerDecision[]
    → if should_trigger → controller.run_cycle()
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .models import (
    OpportunitySignal,
    TriggerDecision,
    TriggerAction,
)
from .rules import Rule, build_default_rules
from .opportunity_detector import OpportunityDetector

logger = logging.getLogger(__name__)


class TriggerEngine:
    """触发引擎。

    对检测到的机会信号进行规则评估，决定是否触发进化循环。

    Attributes:
        detector:       OpportunityDetector（信号解析）
        rules:          规则列表
        context:        评估上下文
        evaluate_count: 已评估次数
        trigger_count:  已触发次数
    """

    def __init__(
        self,
        rules: list[Rule] | None = None,
        detector: OpportunityDetector | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self._detector = detector or OpportunityDetector()
        self._rules = rules or build_default_rules()
        self._context = context or {}
        self._evaluate_count: int = 0
        self._trigger_count: int = 0
        self._decision_history: list[TriggerDecision] = []

    # ── 核心接口：evaluate ──────────────────────────────

    def evaluate(
        self,
        opportunities: list[OpportunitySignal],
    ) -> list[TriggerDecision]:
        """对机会信号进行规则评估。

        Args:
            opportunities: 机会信号列表

        Returns:
            TriggerDecision 列表（按优先级排序）
        """
        decisions: list[TriggerDecision] = []
        seen_signals: set[str] = set()

        for signal in opportunities:
            # 去重：同一 signal_id 只评估一次
            if signal.signal_id in seen_signals:
                logger.debug(f"Skipping duplicate signal: {signal.signal_id}")
                continue
            seen_signals.add(signal.signal_id)

            decision = self._evaluate_single(signal)
            if decision is not None:
                decisions.append(decision)
                self._decision_history.append(decision)

                if decision.should_trigger:
                    self._trigger_count += 1

        self._evaluate_count += 1

        # 按优先级排序
        return self._sort_decisions(decisions)

    def evaluate_batch(
        self,
        opportunity_batches: list[list[OpportunitySignal]],
    ) -> list[list[TriggerDecision]]:
        """批量评估多组机会信号。"""
        return [self.evaluate(batch) for batch in opportunity_batches]

    # ── 便捷接口：process ───────────────────────────────

    def process(
        self,
        raw_signals: list[dict[str, Any]],
    ) -> list[TriggerDecision]:
        """一站式处理：原始信号 → 检测 → 评估。

        Args:
            raw_signals: 原始信号列表

        Returns:
            TriggerDecision 列表
        """
        opportunities = self._detector.detect(raw_signals)
        return self.evaluate(opportunities)

    # ── 连接 Controller ─────────────────────────────────

    def get_trigger_signals(
        self,
        decisions: list[TriggerDecision],
    ) -> list[TriggerDecision]:
        """获取所有 should_trigger 的决策。"""
        return [d for d in decisions if d.should_trigger]

    def get_positive_decisions(
        self,
        decisions: list[TriggerDecision],
    ) -> list[TriggerDecision]:
        """获取所有 START_EVOLUTION 的决策。"""
        return [d for d in decisions if d.is_positive]

    def on_trigger(
        self,
        handler: Callable[[TriggerDecision], None],
    ) -> None:
        """注册触发回调。"""
        self._trigger_handler = handler

    def _notify_trigger(self, decision: TriggerDecision) -> None:
        """通知触发回调。"""
        handler = getattr(self, "_trigger_handler", None)
        if handler:
            try:
                handler(decision)
            except Exception as e:
                logger.error(f"Trigger handler error: {e}")

    # ── 内部 ──────────────────────────────────────────

    def _evaluate_single(
        self,
        signal: OpportunitySignal,
    ) -> TriggerDecision | None:
        """对单个信号进行规则评估。

        规则按优先级排序，匹配到的第一条规则生效。
        """
        sorted_rules = sorted(
            [r for r in self._rules if r.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )

        for rule in sorted_rules:
            decision = rule.evaluate(signal, self._context)
            if decision is not None:
                logger.debug(
                    f"Signal {signal.signal_id} matched rule "
                    f"'{rule.name}' → {decision.action.value}"
                )
                return decision

        # 无规则匹配：默认 DEFER
        logger.debug(
            f"Signal {signal.signal_id} matched no rule, defaulting to DEFER"
        )
        return TriggerDecision(
            signal_id=signal.signal_id,
            should_trigger=False,
            action=TriggerAction.DEFER,
            reason="No rule matched, default defer",
            confidence=signal.confidence,
        )

    @staticmethod
    def _sort_decisions(
        decisions: list[TriggerDecision],
    ) -> list[TriggerDecision]:
        """按优先级排序决策。

        START_EVOLUTION 优先，然后按 confidence 降序。
        """
        def sort_key(d: TriggerDecision) -> tuple[int, float]:
            action_order = {
                TriggerAction.START_EVOLUTION: 0,
                TriggerAction.QUEUE: 1,
                TriggerAction.MERGE: 2,
                TriggerAction.DEFER: 3,
                TriggerAction.IGNORE: 4,
            }
            return (action_order.get(d.action, 99), -d.confidence)

        return sorted(decisions, key=sort_key)

    # ── 配置 ──────────────────────────────────────────

    def add_rule(self, rule: Rule) -> None:
        """添加自定义规则。"""
        self._rules.append(rule)
        logger.info(f"Rule added: {rule.name}")

    def remove_rule(self, rule_name: str) -> bool:
        """移除规则。"""
        for i, rule in enumerate(self._rules):
            if rule.name == rule_name:
                self._rules.pop(i)
                logger.info(f"Rule removed: {rule_name}")
                return True
        return False

    def set_context(self, key: str, value: Any) -> None:
        """设置评估上下文。"""
        self._context[key] = value

    def update_context(self, context: dict[str, Any]) -> None:
        """批量更新评估上下文。"""
        self._context.update(context)

    # ── Stats ──────────────────────────────────────────

    @property
    def evaluate_count(self) -> int:
        return self._evaluate_count

    @property
    def trigger_count(self) -> int:
        return self._trigger_count

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def get_stats(self) -> dict[str, Any]:
        return {
            "evaluate_count": self._evaluate_count,
            "trigger_count": self._trigger_count,
            "rule_count": self.rule_count,
            "detector": self._detector.get_stats(),
            "recent_decisions": [
                d.to_dict() for d in self._decision_history[-5:]
            ],
        }

    def reset(self) -> None:
        """重置统计和去重。"""
        self._evaluate_count = 0
        self._trigger_count = 0
        self._decision_history.clear()
        self._detector.reset()

    def __repr__(self) -> str:
        return (
            f"TriggerEngine(evaluated={self._evaluate_count}, "
            f"triggered={self._trigger_count}, "
            f"rules={self.rule_count})"
        )