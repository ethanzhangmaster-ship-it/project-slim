"""E13.7.8 Learning Cycle Gate — 学习循环门控引擎.

Day 7.8 Step 5:
  独立控制学习循环的 继续/暂停/回滚/请求更多数据 决策，
  基于 Feedback 分类 + Effectiveness 评估 + 历史趋势。

核心流程:
  LearningFeedback + LearningEffectiveness
          |
          v
  CycleGate.evaluate()
          |
          +--> 按优先级评估规则
          |
          +--> 最早触发的规则决定最终决策
          |
          v
  CycleGateResult
          |
          +-- CONTINUE          → 正常进入 POLICY_DECISION
          +-- PAUSE             → 暂停，等待人工审查
          +-- ROLLBACK          → 回滚策略到上一版本
          +-- REQUEST_MORE_DATA → 跳过策略调整，仅积累数据

规则优先级 (从高到低):
  0. ROLLBACK    — 连续负学习增益
  1. PAUSE       — 重复负反馈
  2. REQUEST_MORE_DATA — 数据不足
  3. CONTINUE    — 默认

设计原则:
  - 确定性: 规则按优先级依次评估，相同输入 → 相同决策
  - 可扩展: 规则通过 add_rule() 动态注册
  - 可审计: 每次评估记录所有规则结果
  - 不侵入已有模块: 通过 CycleGateResult 数据模型桥接

用法:
  from growth_runtime.intelligence.learning.learning_cycle_gate import CycleGate

  gate = CycleGate()
  result = gate.evaluate(
      feedback=feedback,
      effectiveness=effectiveness,
      cycle_number=3,
      history=cycle_history,
  )
  if result.should_continue:
      # 继续下一周期
  elif result.should_pause:
      # 暂停
"""

from __future__ import annotations

from typing import Any

from .models.cycle_gate_models import (
    CycleGateResult,
    GateDecision,
    GateRule,
)


# ═══════════════════════════════════════════════════════════════
# Default Gate Rules
# ═══════════════════════════════════════════════════════════════


def _build_default_rules() -> list[GateRule]:
    """构建默认门控规则集.

    优先级: ROLLBACK > PAUSE > REQUEST_MORE_DATA > CONTINUE
    """

    def _has_negative_learning_gain(ctx: dict[str, Any]) -> bool:
        gain = ctx.get("learning_gain", 0.0)
        return gain < -0.3

    def _has_repeated_negative(ctx: dict[str, Any]) -> bool:
        negative_count = ctx.get("consecutive_negative_count", 0)
        return negative_count >= 3

    def _has_insufficient_data(ctx: dict[str, Any]) -> bool:
        classification = ctx.get("feedback_classification", "")
        return classification == "insufficient_data"

    def _has_stagnant_with_failures(ctx: dict[str, Any]) -> bool:
        classification = ctx.get("feedback_classification", "")
        success_delta = ctx.get("success_delta", 0.0)
        return classification == "stagnant" and success_delta < 0

    def _has_effectiveness_below_threshold(ctx: dict[str, Any]) -> bool:
        score = ctx.get("effectiveness_score")
        if score is None:
            return False
        threshold = ctx.get("min_effectiveness_threshold", 0.3)
        return score < threshold

    return [
        # ── Priority 0: ROLLBACK (最强) ──
        GateRule(
            name="strong_negative_learning",
            description="学习增益强负 (learning_gain < -0.3)",
            priority=0,
            condition=_has_negative_learning_gain,
            decision=GateDecision.ROLLBACK.value,
            reason_template="Strong negative learning gain ({learning_gain:.4f}) — rollback strategy",
        ),
        # ── Priority 1: PAUSE ──
        GateRule(
            name="repeated_negative_cycles",
            description="连续 {consecutive_negative_count} 个周期负反馈",
            priority=1,
            condition=_has_repeated_negative,
            decision=GateDecision.PAUSE.value,
            reason_template="Repeated negative cycles ({consecutive_negative_count}) — pause for review",
        ),
        GateRule(
            name="stagnant_with_failures",
            description="停滞且伴随执行失败",
            priority=2,
            condition=_has_stagnant_with_failures,
            decision=GateDecision.PAUSE.value,
            reason_template="Stagnant learning with execution failures — pause for investigation",
        ),
        GateRule(
            name="effectiveness_below_threshold",
            description="有效性评分低于阈值 {min_effectiveness_threshold}",
            priority=3,
            condition=_has_effectiveness_below_threshold,
            decision=GateDecision.PAUSE.value,
            reason_template="Effectiveness score ({effectiveness_score}) below threshold ({min_effectiveness_threshold}) — pause",
        ),
        # ── Priority 10: REQUEST_MORE_DATA ──
        GateRule(
            name="insufficient_data",
            description="数据不足，无法判断",
            priority=10,
            condition=_has_insufficient_data,
            decision=GateDecision.REQUEST_MORE_DATA.value,
            reason_template="Insufficient data — request more samples",
        ),
        # ── Priority 100: CONTINUE (默认) ──
        GateRule(
            name="default_continue",
            description="默认继续",
            priority=100,
            condition=lambda _: True,
            decision=GateDecision.CONTINUE.value,
            reason_template="All conditions passed — continue",
        ),
    ]


# ═══════════════════════════════════════════════════════════════
# CycleGate
# ═══════════════════════════════════════════════════════════════


class CycleGate:
    """学习循环门控引擎 — 控制继续/暂停/回滚/请求更多数据.

    用法:
        gate = CycleGate()
        result = gate.evaluate(
            feedback=feedback,
            effectiveness=effectiveness,
            cycle_number=3,
            cycle_history=history,
        )
    """

    def __init__(self) -> None:
        self._rules: list[GateRule] = _build_default_rules()
        self._evaluate_count: int = 0
        self._result_history: list[CycleGateResult] = []

    @property
    def evaluate_count(self) -> int:
        return self._evaluate_count

    @property
    def rules(self) -> list[GateRule]:
        return list(self._rules)

    # ── Public API ───────────────────────────────────────────────

    def evaluate(
        self,
        feedback: Any = None,  # LearningFeedback
        effectiveness: Any = None,  # LearningEffectiveness
        cycle_number: int = 0,
        cycle_history: list[Any] | None = None,
        config: Any = None,  # OrchestratorConfig
    ) -> CycleGateResult:
        """评估门控 — 主入口.

        Args:
            feedback: LearningFeedback 实例
            effectiveness: LearningEffectiveness 实例
            cycle_number: 当前周期编号
            cycle_history: 历史周期结果列表
            config: OrchestratorConfig 实例

        Returns:
            CycleGateResult
        """
        self._evaluate_count += 1

        # 构建评估上下文
        context = self._build_context(
            feedback=feedback,
            effectiveness=effectiveness,
            cycle_number=cycle_number,
            cycle_history=cycle_history,
            config=config,
        )

        # 按优先级排序规则
        sorted_rules = sorted(self._rules, key=lambda r: r.priority)

        rule_results: list[dict[str, Any]] = []
        triggered_rule: str = ""
        final_decision: str = GateDecision.CONTINUE.value
        final_reason: str = ""

        for rule in sorted_rules:
            triggered, reason = rule.evaluate(context)
            rule_results.append({
                "name": rule.name,
                "priority": rule.priority,
                "decision": rule.decision,
                "triggered": triggered,
                "reason": reason,
            })

            if triggered:
                triggered_rule = rule.name
                final_decision = rule.decision
                final_reason = reason
                break

        result = CycleGateResult(
            cycle_number=cycle_number,
            decision=final_decision,
            decision_reason=final_reason,
            triggered_rule=triggered_rule,
            rules_evaluated=len(rule_results),
            rule_results=rule_results,
            feedback_classification=context.get("feedback_classification", ""),
            effectiveness_score=context.get("effectiveness_score"),
            learning_gain=context.get("learning_gain", 0.0),
        )

        self._result_history.append(result)
        return result

    # ── Rule Management ─────────────────────────────────────────

    def add_rule(self, rule: GateRule) -> None:
        """添加自定义规则."""
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """按名称移除规则."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def clear_rules(self) -> None:
        """清空所有规则."""
        self._rules = []

    # ── Query ────────────────────────────────────────────────────

    def get_history(self) -> list[CycleGateResult]:
        return list(self._result_history)

    def get_latest(self) -> CycleGateResult | None:
        if not self._result_history:
            return None
        return self._result_history[-1]

    def get_stats(self) -> dict[str, Any]:
        if not self._result_history:
            return {
                "evaluate_count": self._evaluate_count,
                "continue_count": 0,
                "pause_count": 0,
                "rollback_count": 0,
                "request_data_count": 0,
                "blocking_rate": 0.0,
            }

        continue_count = sum(1 for r in self._result_history if r.should_continue)
        pause_count = sum(1 for r in self._result_history if r.should_pause)
        rollback_count = sum(1 for r in self._result_history if r.should_rollback)
        request_count = sum(1 for r in self._result_history if r.should_request_data)
        blocking = sum(1 for r in self._result_history if r.is_blocking)

        return {
            "evaluate_count": self._evaluate_count,
            "continue_count": continue_count,
            "pause_count": pause_count,
            "rollback_count": rollback_count,
            "request_data_count": request_count,
            "blocking_rate": round(blocking / len(self._result_history), 4),
        }

    def reset(self) -> None:
        self._evaluate_count = 0
        self._result_history = []
        self._rules = _build_default_rules()

    # ── Internal ─────────────────────────────────────────────────

    def _build_context(
        self,
        feedback: Any,
        effectiveness: Any,
        cycle_number: int,
        cycle_history: list[Any] | None,
        config: Any,
    ) -> dict[str, Any]:
        """构建评估上下文."""
        ctx: dict[str, Any] = {
            "cycle_number": cycle_number,
        }

        # ── 从 feedback 提取 ──
        if feedback is not None:
            ctx["feedback_classification"] = getattr(feedback, "classification", "")
            ctx["learning_gain"] = getattr(
                getattr(feedback, "outcome_measurement", None),
                "learning_gain",
                0.0,
            ) or 0.0
            ctx["success_delta"] = getattr(
                getattr(feedback, "outcome_measurement", None),
                "success_delta",
                0.0,
            ) or 0.0

        # ── 从 effectiveness 提取 ──
        if effectiveness is not None:
            ctx["effectiveness_score"] = getattr(effectiveness, "effectiveness_score", None)
            if ctx["learning_gain"] == 0.0:
                ctx["learning_gain"] = getattr(effectiveness, "learning_gain", 0.0) or 0.0

        # ── 从 config 提取 ──
        if config is not None:
            ctx["min_effectiveness_threshold"] = getattr(
                config, "min_effectiveness_threshold", 0.3
            )

        # ── 从 history 计算连续负反馈 ──
        ctx["consecutive_negative_count"] = self._count_consecutive_negative(
            cycle_history or []
        )

        return ctx

    @staticmethod
    def _count_consecutive_negative(history: list[Any]) -> int:
        """从最近的周期历史中计算连续负反馈次数."""
        count = 0
        for item in reversed(history):
            # 检查 OrchestrationCycleResult
            if hasattr(item, "effectiveness"):
                eff = item.effectiveness
                if eff is not None and hasattr(eff, "learning_gain"):
                    if eff.learning_gain < 0:
                        count += 1
                    else:
                        break
            # 检查 CycleGateResult
            elif hasattr(item, "learning_gain"):
                if item.learning_gain < 0:
                    count += 1
                else:
                    break
            else:
                break
        return count

    def __repr__(self) -> str:
        return (
            f"CycleGate("
            f"rules={len(self._rules)}, "
            f"evaluations={self._evaluate_count})"
        )


__all__ = [
    "CycleGate",
]