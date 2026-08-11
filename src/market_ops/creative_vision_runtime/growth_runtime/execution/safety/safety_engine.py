"""E13.6.4 Safety Engine — 安全评估引擎核心.

消费 ActionPlan 中的每个 ActionNode，通过 SafetyPolicy 中的规则进行评估，返回
SafetyEvaluation 决策。与 ExecutionContext 集成，为 E13.6.3 ExecutionEngine 提供
安全校验。

核心流程:
  ActionNode
      ↓
  SafetyEngine.evaluate(action, context)
      ↓
  遍历 SafetyPolicy.rules (按 priority 排序)
      ↓
  每个规则: condition(action, context) → triggered?
      ↓
  聚合: 取最严格的 decision
      ↓
  SafetyEvaluation (ALLOW | WARN | BLOCK | REQUIRE_APPROVAL)
      ↓
  更新 ExecutionContext (risk_score, safety_check, approval_required)

连接:
  E13.6.4 SafetyEngine → ExecutionContext → E13.6.3 ExecutionEngine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .safety_models import (
    RiskCategory,
    RuleResult,
    SafetyDecision,
    SafetyEvaluation,
    SafetyRule,
)
from .safety_policy import SafetyPolicy, create_default_policy
from .safety_rules import get_rules_for_action_type


# ═══════════════════════════════════════════════════════════════
# Decision Priority — 决策严格度排序
# ═══════════════════════════════════════════════════════════════

_DECISION_SEVERITY: dict[SafetyDecision, int] = {
    SafetyDecision.ALLOW: 0,
    SafetyDecision.WARN: 1,
    SafetyDecision.REQUIRE_APPROVAL: 2,
    SafetyDecision.BLOCK: 3,
}


def _most_severe(a: SafetyDecision, b: SafetyDecision) -> SafetyDecision:
    """返回两个决策中更严格的."""
    return a if _DECISION_SEVERITY[a] >= _DECISION_SEVERITY[b] else b


# ── Action Type → Risk Category 映射 ──────────────────────────

_ACTION_TYPE_TO_CATEGORIES: dict[str, list[RiskCategory]] = {
    "scale_budget": [RiskCategory.BUDGET_SCALE, RiskCategory.ROLLBACK],
    "update_budget": [RiskCategory.BUDGET_SCALE, RiskCategory.ROLLBACK],
    "reduce_budget": [RiskCategory.BUDGET_REDUCE, RiskCategory.ROLLBACK],
    "mutate_creative": [RiskCategory.CREATIVE_MUTATION, RiskCategory.ROLLBACK],
    "create_creative": [RiskCategory.CREATIVE_MUTATION, RiskCategory.ROLLBACK],
    "pause_campaign": [RiskCategory.CAMPAIGN_PAUSE, RiskCategory.ROLLBACK],
    "freeze_campaign": [RiskCategory.CAMPAIGN_FREEZE, RiskCategory.ROLLBACK],
    "create_campaign": [RiskCategory.CAMPAIGN_CREATE, RiskCategory.ROLLBACK],
    "pause_creative": [RiskCategory.ROLLBACK],
    "upload_creative": [RiskCategory.ROLLBACK],
    "monitor": [RiskCategory.ROLLBACK],
    "collect_result": [RiskCategory.ROLLBACK],
}


def _is_rule_applicable(rule: SafetyRule, action_type: str) -> bool:
    """检查规则是否适用于给定的动作类型."""
    applicable_categories = _ACTION_TYPE_TO_CATEGORIES.get(
        action_type, [RiskCategory.GENERAL, RiskCategory.ROLLBACK]
    )
    return rule.category in applicable_categories


# ═══════════════════════════════════════════════════════════════
# Safety Engine
# ═══════════════════════════════════════════════════════════════


@dataclass
class SafetyEngine:
    """安全评估引擎 — 对动作进行安全评估.

    用法:
        policy = create_default_policy()
        engine = SafetyEngine(policy)
        evaluation = engine.evaluate(action, context)

        if evaluation.is_blocked:
            return  # 阻止执行
        if evaluation.requires_approval:
            # 创建审批请求
            ...
    """

    policy: SafetyPolicy = field(default_factory=create_default_policy)
    enable_auto_rules: bool = True
    evaluation_count: int = 0
    block_count: int = 0
    approval_count: int = 0
    warn_count: int = 0

    # ── 主入口 ────────────────────────────────────────────────

    def evaluate(
        self,
        action: Any,
        context: Any,
        action_type: str = "",
    ) -> SafetyEvaluation:
        """评估单个动作的安全性.

        Args:
            action: 要评估的动作 (ExecutionAction 或 ActionNode)
            context: 执行上下文 (ExecutionContext 或任何带 metadata 的对象)
            action_type: 动作类型字符串 (如果 action 没有 action_type 属性)

        Returns:
            SafetyEvaluation: 安全评估结果
        """
        self.evaluation_count += 1

        # 提取 action_type
        resolved_action_type = action_type
        if not resolved_action_type:
            resolved_action_type = self._resolve_action_type(action)

        # 提取 action_id
        action_id = self._resolve_action_id(action)

        evaluation = SafetyEvaluation(
            action_id=action_id,
            action_type=resolved_action_type,
        )

        # 收集规则
        rules = self._collect_rules(resolved_action_type)

        # 按优先级排序
        rules.sort(key=lambda r: r.priority)

        # 评估每条规则
        final_decision = SafetyDecision.ALLOW
        total_risk = 0.0
        triggered_count = 0

        for rule in rules:
            triggered, reason, decision = rule.evaluate(action, context)

            rule_result = RuleResult(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                triggered=triggered,
                decision=decision if triggered else SafetyDecision.ALLOW,
                reason=reason if triggered else "",
            )
            evaluation.rule_results.append(rule_result)

            if triggered:
                evaluation.triggered_rules.append(rule.name)
                evaluation.reasons.append(reason)

                # 按严重程度加权风险评分
                severity_weight = self._severity_weight(rule)
                total_risk += severity_weight
                triggered_count += 1

                # 取最严格的决策
                final_decision = _most_severe(final_decision, decision)

                # 警告信息
                if decision == SafetyDecision.WARN:
                    evaluation.warnings.append(f"[{rule.name}] {reason}")
                    self.warn_count += 1

        # 计算综合风险评分 (sigmoid 归一化)
        if triggered_count > 0:
            # 使用 sigmoid 将触发规则的风险权重映射到 [0, 1]
            import math
            evaluation.risk_score = 1.0 / (1.0 + math.exp(-total_risk + 2.0))
        else:
            evaluation.risk_score = 0.0

        # 设置最终决策
        evaluation.decision = final_decision
        evaluation.is_blocked = final_decision == SafetyDecision.BLOCK
        evaluation.requires_approval = final_decision == SafetyDecision.REQUIRE_APPROVAL

        if evaluation.is_blocked:
            self.block_count += 1
        elif evaluation.requires_approval:
            self.approval_count += 1

        return evaluation

    def evaluate_node(
        self,
        node: Any,
        context: Any,
    ) -> SafetyEvaluation:
        """评估 ActionNode (从 node.action 中提取动作).

        Args:
            node: ActionNode 实例
            context: 执行上下文

        Returns:
            SafetyEvaluation: 安全评估结果
        """
        action = node.action if hasattr(node, "action") else node
        action_type = ""
        if hasattr(action, "action_type") and hasattr(action.action_type, "value"):
            action_type = action.action_type.value
        return self.evaluate(action, context, action_type)

    def evaluate_plan(
        self,
        plan: Any,
        context: Any,
    ) -> list[SafetyEvaluation]:
        """评估整个 ActionPlan 中的所有节点.

        Args:
            plan: ActionPlan 实例
            context: 执行上下文

        Returns:
            SafetyEvaluation 列表 (按执行顺序)
        """
        evaluations: list[SafetyEvaluation] = []

        if hasattr(plan, "get_ordered_nodes"):
            nodes = plan.get_ordered_nodes()
        elif hasattr(plan, "nodes"):
            nodes = plan.nodes
        else:
            return evaluations

        for node in nodes:
            evaluation = self.evaluate_node(node, context)
            evaluations.append(evaluation)

            # 如果被阻止，停止评估后续节点
            if evaluation.is_blocked:
                break

        return evaluations

    # ── 集成方法 ──────────────────────────────────────────────

    def apply_to_context(
        self,
        evaluation: SafetyEvaluation,
        context: Any,
    ) -> Any:
        """将安全评估结果应用到 ExecutionContext.

        更新 context 的 risk_score, safety_check, approval_required 等字段。

        Args:
            evaluation: 安全评估结果
            context: ExecutionContext 实例

        Returns:
            更新后的 context
        """
        if hasattr(context, "risk_score"):
            context.risk_score = evaluation.risk_score

        if evaluation.is_blocked:
            if hasattr(context, "safety_check"):
                context.safety_check = False
            if hasattr(context, "approval_required"):
                context.approval_required = False
        elif evaluation.requires_approval:
            if hasattr(context, "safety_check"):
                context.safety_check = True
            if hasattr(context, "approval_required"):
                context.approval_required = True
            if hasattr(context, "user_confirmation"):
                context.user_confirmation = "pending"
        else:
            if hasattr(context, "safety_check"):
                context.safety_check = True
            if hasattr(context, "approval_required"):
                context.approval_required = False

        # 存储评估结果到 metadata
        if hasattr(context, "metadata") and isinstance(context.metadata, dict):
            context.metadata["safety_evaluation"] = evaluation.to_dict()

        return context

    # ── 内部方法 ──────────────────────────────────────────────

    def _collect_rules(self, action_type: str) -> list[SafetyRule]:
        """收集适用的规则 — 策略规则 + 自动规则 (去重, 按 action_type 过滤).

        策略规则优先: 如果策略中已有同名规则, 跳过自动规则.
        """
        rules: list[SafetyRule] = []
        seen_ids: set[str] = set()
        seen_names: set[str] = set()

        # 1. 策略中的启用规则 (只添加适用于当前 action_type 的)
        for rule in self.policy.get_enabled_rules():
            if rule.rule_id not in seen_ids and _is_rule_applicable(rule, action_type):
                rules.append(rule)
                seen_ids.add(rule.rule_id)
                seen_names.add(rule.name)

        # 2. 自动规则 (根据 action_type 生成, 策略中已有的同名规则跳过)
        if self.enable_auto_rules:
            auto_rules = get_rules_for_action_type(action_type)
            for rule in auto_rules:
                if rule.rule_id not in seen_ids and rule.name not in seen_names:
                    rules.append(rule)
                    seen_ids.add(rule.rule_id)
                    seen_names.add(rule.name)

        return rules

    def _resolve_action_type(self, action: Any) -> str:
        """从 action 中解析动作类型."""
        if hasattr(action, "action_type"):
            at = action.action_type
            if hasattr(at, "value"):
                return at.value
            return str(at)
        return "unknown"

    def _resolve_action_id(self, action: Any) -> str:
        """从 action 中解析动作 ID."""
        if hasattr(action, "action_id"):
            return str(action.action_id)
        if hasattr(action, "node_id"):
            return str(action.node_id)
        return ""

    def _severity_weight(self, rule: SafetyRule) -> float:
        """根据规则严重程度返回风险权重."""
        weights = {
            "critical": 1.0,
            "high": 0.7,
            "medium": 0.4,
            "low": 0.15,
        }
        return weights.get(rule.severity.value, 0.4)

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "evaluation_count": self.evaluation_count,
            "block_count": self.block_count,
            "approval_count": self.approval_count,
            "warn_count": self.warn_count,
            "policy_name": self.policy.name,
            "policy_rules": self.policy.enabled_rule_count,
            "auto_rules_enabled": self.enable_auto_rules,
        }

    def reset_stats(self) -> None:
        """重置统计."""
        self.evaluation_count = 0
        self.block_count = 0
        self.approval_count = 0
        self.warn_count = 0