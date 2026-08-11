"""E15.2.1 Planning Rules — 安全规则与验证.

安全规则确保 Planner 生成的计划不会超出安全边界。

核心组件:
  - PlanningRule: 单条安全规则 (action_type → 约束)
  - SafetyValidator: 规则验证器 (检查计划是否符合规则)

规则类型:
  - max_budget_change: 最大预算变化比例
  - require_approval:  强制审批
  - min_confidence:    最低置信度阈值
  - forbidden_actions: 禁止执行的动作
  - max_daily_actions: 每日最大执行次数
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import ExecutionPlan, RiskLevel


# ═══════════════════════════════════════════════════════════════
# Planning Rule
# ═══════════════════════════════════════════════════════════════


@dataclass
class PlanningRule:
    """E15.2.1 安全规则 — 对特定 Action 类型的约束.

    Attributes:
        rule_id:            规则唯一标识
        action_type:        适用的 Action 类型
        max_budget_change:  最大预算变化比例 (0 = 无限制, 0.3 = 30%)
        require_approval:   是否强制审批
        min_confidence:     最低置信度阈值
        forbidden:          是否禁止此 Action
        max_daily_actions:  每日最大执行次数 (0 = 无限制)
        required_adapters:  必须使用的适配器
        check_params:       参数校验表达式
        metadata:           扩展元数据
    """
    rule_id: str = ""
    action_type: str = ""
    max_budget_change: float = 0.0
    require_approval: bool = False
    min_confidence: float = 0.5
    forbidden: bool = False
    max_daily_actions: int = 0
    required_adapters: list[str] = field(default_factory=list)
    check_params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self, plan: ExecutionPlan) -> list[str]:
        """验证计划是否符合此规则.

        Args:
            plan: ExecutionPlan

        Returns:
            list[str]: 违规错误列表 (空列表 = 合规)
        """
        errors: list[str] = []

        # 1. 禁止执行
        if self.forbidden:
            errors.append(f"Action '{self.action_type}' is forbidden")
            return errors

        # 2. 置信度检查
        if plan.confidence < self.min_confidence:
            errors.append(
                f"Confidence {plan.confidence} < minimum {self.min_confidence} "
                f"for action '{self.action_type}'"
            )

        # 3. 预算变化检查
        if self.max_budget_change > 0:
            budget_multiplier = plan.context.get("budget_multiplier", 0)
            if budget_multiplier > 1 + self.max_budget_change:
                errors.append(
                    f"Budget change {budget_multiplier - 1:.0%} exceeds "
                    f"maximum {self.max_budget_change:.0%} for '{self.action_type}'"
                )

        # 4. 强制审批
        if self.require_approval and not plan.required_approval:
            errors.append(
                f"Action '{self.action_type}' requires approval but none specified"
            )

        # 5. 适配器检查
        if self.required_adapters:
            plan_adapters = {t.adapter for t in plan.tasks}
            missing = set(self.required_adapters) - plan_adapters
            if missing:
                errors.append(
                    f"Missing required adapters: {missing} for action '{self.action_type}'"
                )

        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "action_type": self.action_type,
            "max_budget_change": self.max_budget_change,
            "require_approval": self.require_approval,
            "min_confidence": self.min_confidence,
            "forbidden": self.forbidden,
            "max_daily_actions": self.max_daily_actions,
            "required_adapters": self.required_adapters,
            "check_params": self.check_params,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Safety Validator
# ═══════════════════════════════════════════════════════════════


class SafetyValidator:
    """E15.2.1 安全验证器 — 规则集合 + 验证计划.

    用法:
        validator = SafetyValidator()
        validator.add_rule(rule)
        errors = validator.validate(plan)
    """

    def __init__(self):
        self._rules: dict[str, PlanningRule] = {}
        self._register_default_rules()

    # ── Rule Management ───────────────────────────────────────

    def add_rule(self, rule: PlanningRule) -> None:
        """添加规则."""
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则."""
        return self._rules.pop(rule_id, None) is not None

    def get_rule(self, rule_id: str) -> PlanningRule | None:
        """获取规则."""
        return self._rules.get(rule_id)

    def get_rules_by_action(self, action_type: str) -> list[PlanningRule]:
        """按 Action 类型获取规则."""
        return [r for r in self._rules.values() if r.action_type == action_type]

    def get_all_rules(self) -> list[PlanningRule]:
        """获取所有规则."""
        return list(self._rules.values())

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    # ── Validation ────────────────────────────────────────────

    def validate(self, plan: ExecutionPlan) -> list[str]:
        """验证计划是否符合所有安全规则.

        Args:
            plan: ExecutionPlan

        Returns:
            list[str]: 所有违规错误列表 (空列表 = 完全合规)
        """
        errors: list[str] = []

        # 检查是否有针对此 action_type 的规则
        matching_rules = self.get_rules_by_action(plan.action_type)

        if not matching_rules:
            # 无特定规则: 检查通用规则
            for rule in self._rules.values():
                if rule.action_type == "*":
                    errors.extend(rule.validate(plan))
            return errors

        # 逐条验证
        for rule in matching_rules:
            errors.extend(rule.validate(plan))

        return errors

    def is_safe(self, plan: ExecutionPlan) -> bool:
        """检查计划是否安全 (无违规)."""
        return len(self.validate(plan)) == 0

    def validate_with_warnings(self, plan: ExecutionPlan) -> tuple[list[str], list[str]]:
        """验证计划并返回错误和警告.

        Returns:
            (errors, warnings): 错误列表和警告列表
        """
        errors = self.validate(plan)
        warnings: list[str] = []

        # 高风险计划警告
        if plan.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            warnings.append(
                f"Plan has {plan.risk_level.value} risk level — manual review recommended"
            )

        # 低置信度警告
        if plan.confidence < 0.6:
            warnings.append(
                f"Low confidence ({plan.confidence}) — consider gathering more data"
            )

        # 无模板警告
        if plan.workflow_type.value == "custom":
            warnings.append(
                "Using custom workflow — no template guardrails applied"
            )

        return errors, warnings

    # ── Default Rules ─────────────────────────────────────────

    def _register_default_rules(self) -> None:
        """注册默认安全规则."""
        # 预算增加: 最多 30%
        self.add_rule(PlanningRule(
            rule_id="budget_increase_limit",
            action_type="increase_budget",
            max_budget_change=0.3,
            require_approval=True,
            min_confidence=0.7,
        ))

        # 放量: 最多 50%
        self.add_rule(PlanningRule(
            rule_id="scale_budget_limit",
            action_type="scale",
            max_budget_change=0.5,
            require_approval=True,
            min_confidence=0.8,
        ))

        # 暂停止损: 不需要审批 (快速止损)
        self.add_rule(PlanningRule(
            rule_id="pause_campaign_rule",
            action_type="pause_campaign",
            require_approval=False,
            min_confidence=0.6,
        ))

        # 素材刷新: 低风险
        self.add_rule(PlanningRule(
            rule_id="creative_refresh_rule",
            action_type="replace_creative",
            max_budget_change=0.0,
            require_approval=False,
            min_confidence=0.5,
        ))

        # 收入优化: 需审批
        self.add_rule(PlanningRule(
            rule_id="revenue_optimize_rule",
            action_type="optimize_pricing",
            require_approval=True,
            min_confidence=0.7,
        ))


__all__ = [
    "PlanningRule",
    "SafetyValidator",
]