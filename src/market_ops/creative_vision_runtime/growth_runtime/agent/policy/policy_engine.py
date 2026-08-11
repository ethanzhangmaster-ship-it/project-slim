"""E13.7.4.2 Policy Engine — 核心策略引擎.

PolicyEngine 是 Agent Policy System 的核心，负责:
  - 聚合所有风险规则并评估
  - 输出最终 PolicyResult (ALLOW / WARN / BLOCK / REQUIRE_APPROVAL)
  - 生成决策摘要和历史记录

处理流程:
    PolicyContext
          ↓
    PolicyEngine.evaluate()
          ↓
    for each RiskRule:
        RuleResult → triggered / not triggered
          ↓
    aggregate → most_severe_decision
          ↓
    PolicyResult

与 E13.6.4 Safety Controller 的边界:
    PolicyEngine → 决定 Agent 能不能提出/执行这个动作
    SafetyController → 决定动作执行时是否安全
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .policy_models import (
    DECISION_SEVERITY,
    PolicyContext,
    PolicyDecision,
    PolicyResult,
    RiskRule,
    RuleResult,
    most_severe_decision,
)
from .risk_rules import build_default_rules


# ═══════════════════════════════════════════════════════════════
# Engine Statistics
# ═══════════════════════════════════════════════════════════════


@dataclass
class EngineStats:
    """引擎统计信息.

    Attributes:
        total_evaluations: 总评估次数
        total_allowed: 允许次数
        total_warned: 警告次数
        total_blocked: 阻止次数
        total_approval_required: 审批次数
        total_rules_triggered: 规则触发总数
        rules_triggered_count: 各规则触发次数
        last_evaluation_at: 最近评估时间
    """
    total_evaluations: int = 0
    total_allowed: int = 0
    total_warned: int = 0
    total_blocked: int = 0
    total_approval_required: int = 0
    total_rules_triggered: int = 0
    rules_triggered_count: dict[str, int] = field(default_factory=dict)
    last_evaluation_at: str = ""

    def record(self, result: PolicyResult) -> None:
        """记录一次评估结果."""
        self.total_evaluations += 1
        self.last_evaluation_at = result.timestamp

        if result.decision == PolicyDecision.ALLOW:
            self.total_allowed += 1
        elif result.decision == PolicyDecision.WARN:
            self.total_warned += 1
        elif result.decision == PolicyDecision.BLOCK:
            self.total_blocked += 1
        elif result.decision == PolicyDecision.REQUIRE_APPROVAL:
            self.total_approval_required += 1

        for rule_name in result.triggered_rules:
            self.total_rules_triggered += 1
            self.rules_triggered_count[rule_name] = (
                self.rules_triggered_count.get(rule_name, 0) + 1
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_evaluations": self.total_evaluations,
            "total_allowed": self.total_allowed,
            "total_warned": self.total_warned,
            "total_blocked": self.total_blocked,
            "total_approval_required": self.total_approval_required,
            "total_rules_triggered": self.total_rules_triggered,
            "rules_triggered_count": self.rules_triggered_count,
            "last_evaluation_at": self.last_evaluation_at,
        }


# ═══════════════════════════════════════════════════════════════
# Policy Engine
# ═══════════════════════════════════════════════════════════════


class PolicyEngine:
    """策略引擎 — 聚合所有风险规则并做出最终决策.

    使用方式:
        >>> engine = PolicyEngine()
        >>> context = PolicyContext(action_type="update_budget", budget_change_ratio=0.5)
        >>> result = engine.evaluate(context)
        >>> print(result.decision)  # REQUIRE_APPROVAL

    Attributes:
        rules: 已注册的风险规则列表
        stats: 引擎统计信息
        strict_mode: 严格模式 (所有 HIGH 规则触发时升级为 BLOCK)
        auto_approve_rollback: 是否自动批准回滚操作
        evaluation_history: 评估历史记录
    """

    def __init__(
        self,
        rules: list[RiskRule] | None = None,
        strict_mode: bool = False,
        auto_approve_rollback: bool = True,
        max_history: int = 1000,
    ):
        self._rules: list[RiskRule] = rules if rules is not None else build_default_rules()
        self.strict_mode = strict_mode
        self.auto_approve_rollback = auto_approve_rollback
        self.max_history = max_history
        self.stats = EngineStats()
        self._evaluation_history: list[PolicyResult] = []

    # ── Properties ──────────────────────────────────────────

    @property
    def rules(self) -> list[RiskRule]:
        return list(self._rules)

    @property
    def enabled_rules(self) -> list[RiskRule]:
        return [r for r in self._rules if r.enabled]

    @property
    def evaluation_history(self) -> list[PolicyResult]:
        return list(self._evaluation_history)

    # ── Rule Management ─────────────────────────────────────

    def add_rule(self, rule: RiskRule) -> None:
        """添加规则."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def enable_rule(self, rule_id: str) -> bool:
        """启用规则."""
        for r in self._rules:
            if r.rule_id == rule_id:
                r.enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则."""
        for r in self._rules:
            if r.rule_id == rule_id:
                r.enabled = False
                return True
        return False

    def get_rule(self, rule_id: str) -> RiskRule | None:
        """获取规则."""
        for r in self._rules:
            if r.rule_id == rule_id:
                return r
        return None

    def get_rules_by_action(self, action_type: str) -> list[RiskRule]:
        """获取适用于特定动作类型的规则."""
        return [
            r for r in self._rules
            if not r.action_types or action_type in r.action_types
        ]

    # ── Core Evaluation ─────────────────────────────────────

    def evaluate(self, context: PolicyContext) -> PolicyResult:
        """评估策略上下文，返回最终决策.

        处理流程:
          1. 遍历所有启用规则，对匹配的 action_type 执行 evaluate()
          2. 收集所有 RuleResult
          3. 取最严格的决策作为最终决策
          4. 自动批准回滚操作 (如果配置了)
          5. 记录统计和歷史

        Args:
            context: 策略评估上下文

        Returns:
            PolicyResult: 最终策略评估结果
        """
        rule_results: list[RuleResult] = []
        triggered_rules: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []
        decisions: list[PolicyDecision] = []

        # 1. 遍历所有规则
        for rule in self._rules:
            if not rule.enabled:
                continue

            result = rule.evaluate(context)
            rule_results.append(result)

            if result.triggered:
                triggered_rules.append(result.rule_name)
                decisions.append(result.decision)

                if result.decision == PolicyDecision.WARN:
                    warnings.append(result.reason)
                elif result.decision == PolicyDecision.BLOCK:
                    errors.append(result.reason)
                elif result.decision == PolicyDecision.REQUIRE_APPROVAL:
                    warnings.append(result.reason)

        # 2. 取最严格的决策
        if not decisions:
            final_decision = PolicyDecision.ALLOW
            final_reason = "所有规则检查通过"
        else:
            final_decision = most_severe_decision(decisions)

            # 严格模式: 将 REQUIRE_APPROVAL 升级为 BLOCK
            if self.strict_mode and final_decision == PolicyDecision.REQUIRE_APPROVAL:
                final_decision = PolicyDecision.BLOCK

            # 构建最终原因
            triggered_reasons = []
            for r in rule_results:
                if r.triggered:
                    triggered_reasons.append(f"[{r.rule_name}] {r.reason}")
            final_reason = "; ".join(triggered_reasons) if triggered_reasons else "规则评估通过"

        # 3. 自动批准回滚操作
        if (
            self.auto_approve_rollback
            and final_decision == PolicyDecision.REQUIRE_APPROVAL
            and context.action_type == "rollback"
        ):
            final_decision = PolicyDecision.ALLOW
            final_reason = "回滚操作自动批准 (auto_approve_rollback=true)"

        # 4. 计算综合风险评分
        risk_score = self._compute_risk_score(rule_results, context)

        # 5. 构建结果
        result = PolicyResult(
            result_id=str(uuid.uuid4()),
            decision=final_decision,
            reason=final_reason,
            risk_score=risk_score,
            rule_results=rule_results,
            triggered_rules=triggered_rules,
            warnings=warnings,
            errors=errors,
            requires_approval=(final_decision == PolicyDecision.REQUIRE_APPROVAL),
            is_blocked=(final_decision == PolicyDecision.BLOCK),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # 6. 记录统计
        self.stats.record(result)
        self._record_history(result)

        return result

    def _compute_risk_score(
        self, rule_results: list[RuleResult], context: PolicyContext
    ) -> float:
        """计算综合风险评分 [0, 1].

        基于:
          - 已触发规则的严重程度
          - 上下文风险评分
          - 置信度
        """
        if not rule_results:
            return context.risk_score

        triggered = [r for r in rule_results if r.triggered]
        if not triggered:
            return context.risk_score * 0.5  # 无触发规则时降低风险

        # 严重程度权重
        severity_weights = {
            "critical": 1.0,
            "high": 0.7,
            "medium": 0.4,
            "low": 0.1,
        }

        rule_risk = 0.0
        for r in triggered:
            weight = severity_weights.get(r.severity.value, 0.4)
            rule_risk = max(rule_risk, weight)

        # 综合: 规则风险 60% + 上下文风险 30% + 置信度惩罚 10%
        confidence_penalty = (1.0 - context.confidence) * 0.1
        return min(1.0, rule_risk * 0.6 + context.risk_score * 0.3 + confidence_penalty)

    def _record_history(self, result: PolicyResult) -> None:
        """记录评估历史."""
        self._evaluation_history.append(result)
        if len(self._evaluation_history) > self.max_history:
            self._evaluation_history = self._evaluation_history[-self.max_history:]

    # ── Quick Check ─────────────────────────────────────────

    def quick_check(self, context: PolicyContext) -> bool:
        """快速检查 — 返回 True 表示允许执行 (ALLOW 或 WARN).

        Args:
            context: 策略上下文

        Returns:
            bool: 是否允许执行
        """
        result = self.evaluate(context)
        return result.decision in (PolicyDecision.ALLOW, PolicyDecision.WARN)

    def is_blocked(self, context: PolicyContext) -> bool:
        """检查是否被阻止."""
        result = self.evaluate(context)
        return result.is_blocked

    def needs_approval(self, context: PolicyContext) -> bool:
        """检查是否需要审批."""
        result = self.evaluate(context)
        return result.requires_approval

    # ── Summary ─────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """获取引擎摘要."""
        return {
            "rules_count": len(self._rules),
            "enabled_rules_count": len(self.enabled_rules),
            "strict_mode": self.strict_mode,
            "auto_approve_rollback": self.auto_approve_rollback,
            "stats": self.stats.to_dict(),
        }

    def get_rules_status(self) -> list[dict[str, Any]]:
        """获取所有规则状态."""
        return [r.to_dict() for r in self._rules]

    def reset_stats(self) -> None:
        """重置统计."""
        self.stats = EngineStats()
        self._evaluation_history = []


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_policy_engine(
    rules: list[RiskRule] | None = None,
    strict_mode: bool = False,
    auto_approve_rollback: bool = True,
) -> PolicyEngine:
    """创建策略引擎的工厂函数.

    Args:
        rules: 自定义规则集 (None = 使用默认规则)
        strict_mode: 严格模式
        auto_approve_rollback: 自动批准回滚

    Returns:
        PolicyEngine: 策略引擎实例
    """
    return PolicyEngine(
        rules=rules,
        strict_mode=strict_mode,
        auto_approve_rollback=auto_approve_rollback,
    )