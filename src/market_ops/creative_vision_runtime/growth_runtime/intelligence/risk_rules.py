"""E13.5.4 Risk Rules — 风险规则引擎.

将策略与上下文输入规则引擎，评估策略激进程度、不确定性和影响程度。

核心规则:
  - BudgetAggressionRule: 预算暴涨检测
  - HistoricalFailureCheckRule: 历史失败率检查
  - LowConfidenceRule: 低置信度检测
  - NewProductRule: 新产品限制
  - HighImpactRule: 高影响操作检测

连接:
  RiskController → RiskRuleEngine → [Rules] → aggression/uncertainty/impact risk
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .risk_models import RiskContext, RiskPolicy


# ═══════════════════════════════════════════════════════════════
# Rule Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class RiskRuleResult:
    """风险规则评估聚合结果.

    Attributes:
        aggression_risk: 策略激进程度 [0, 1]
        uncertainty_risk: 不确定性风险 [0, 1]
        impact_risk: 影响程度风险 [0, 1]
        violations: 触发的规则违规列表
        reasons: 风险原因
        recommendations: 建议
    """
    aggression_risk: float = 0.0
    uncertainty_risk: float = 0.0
    impact_risk: float = 0.0
    violations: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggression_risk": round(self.aggression_risk, 4),
            "uncertainty_risk": round(self.uncertainty_risk, 4),
            "impact_risk": round(self.impact_risk, 4),
            "violations": self.violations,
            "reasons": self.reasons,
            "recommendations": self.recommendations,
        }

    def add_violation(self, rule_name: str, reason: str, recommendation: str = "") -> None:
        """添加规则违规."""
        self.violations.append(rule_name)
        if reason:
            self.reasons.append(reason)
        if recommendation:
            self.recommendations.append(recommendation)

    @property
    def total_risk(self) -> float:
        """综合规则风险 (不含 failure)."""
        return self.aggression_risk + self.uncertainty_risk + self.impact_risk

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0


# ═══════════════════════════════════════════════════════════════
# Base Rule
# ═══════════════════════════════════════════════════════════════


class BaseRiskRule:
    """风险规则基类."""

    name: str = "base_risk_rule"

    def evaluate(
        self,
        strategy: Any,
        context: RiskContext,
        policy: RiskPolicy,
        result: RiskRuleResult,
    ) -> None:
        """评估风险并更新结果.

        Args:
            strategy: 策略对象 (StrategyCandidate / dict / GrowthStrategyPattern)
            context: 风险评估上下文
            policy: 风险策略配置
            result: 输出结果 (会被修改)
        """
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════
# Rule 1: Budget Aggression
# ═══════════════════════════════════════════════════════════════


class BudgetAggressionRule(BaseRiskRule):
    """预算激进程度检测.

    规则:
      - 预算增幅 > 100%: aggression += 0.8
      - 预算增幅 > 50%:  aggression += 0.3
      - 预算增幅 > 30%:  aggression += 0.15
      - 新产品 (上线 < 30天) 预算增幅 > 10%: aggression += 0.5 (额外)
    """

    name = "BudgetAggressionRule"

    # 预算增幅阈值
    AGGRESSION_THRESHOLD_HIGH = 1.0     # > 100%
    AGGRESSION_THRESHOLD_MED = 0.5      # > 50%
    AGGRESSION_THRESHOLD_LOW = 0.3      # > 30%

    # 对应风险增量
    AGGRESSION_SCORE_HIGH = 0.8
    AGGRESSION_SCORE_MED = 0.3
    AGGRESSION_SCORE_LOW = 0.15

    # 新产品额外惩罚
    NEW_PRODUCT_BUDGET_THRESHOLD = 0.10  # > 10%
    NEW_PRODUCT_PENALTY = 0.5

    def evaluate(
        self,
        strategy: Any,
        context: RiskContext,
        policy: RiskPolicy,
        result: RiskRuleResult,
    ) -> None:
        change_ratio = context.budget_change_ratio

        if change_ratio <= 0:
            return

        # 检查预算增幅
        if change_ratio > self.AGGRESSION_THRESHOLD_HIGH:
            result.aggression_risk += self.AGGRESSION_SCORE_HIGH
            result.add_violation(
                self.name,
                f"Budget increase {change_ratio:.0%} exceeds 100% threshold",
                f"Consider phased rollout: start with {policy.max_budget_increase:.0%} increase",
            )
        elif change_ratio > self.AGGRESSION_THRESHOLD_MED:
            result.aggression_risk += self.AGGRESSION_SCORE_MED
            result.add_violation(
                self.name,
                f"Budget increase {change_ratio:.0%} exceeds 50% threshold",
                f"Recommend gradual increase: max {policy.max_budget_increase:.0%} per adjustment",
            )
        elif change_ratio > self.AGGRESSION_THRESHOLD_LOW:
            result.aggression_risk += self.AGGRESSION_SCORE_LOW

        # 新产品额外检查
        if context.is_new_product:
            if change_ratio > self.NEW_PRODUCT_BUDGET_THRESHOLD:
                result.aggression_risk += self.NEW_PRODUCT_PENALTY
                result.add_violation(
                    self.name,
                    f"New product ({context.days_since_first_launch}d) budget increase {change_ratio:.0%} exceeds {self.NEW_PRODUCT_BUDGET_THRESHOLD:.0%}",
                    f"New products should limit budget increase to {policy.max_budget_increase_new_product:.0%}",
                )

        # Cap at 1.0
        result.aggression_risk = min(result.aggression_risk, 1.0)


# ═══════════════════════════════════════════════════════════════
# Rule 2: Historical Failure Check
# ═══════════════════════════════════════════════════════════════


class HistoricalFailureCheckRule(BaseRiskRule):
    """历史失败率检查.

    规则:
      - 失败率 > 0.9: 直接 BLOCK
      - 失败率 > 0.7: 高风险
      - 失败率 > 0.5: 中风险
    """

    name = "HistoricalFailureCheckRule"

    FAILURE_BLOCK_THRESHOLD = 0.9
    FAILURE_HIGH_THRESHOLD = 0.7
    FAILURE_MEDIUM_THRESHOLD = 0.5

    def evaluate(
        self,
        strategy: Any,
        context: RiskContext,
        policy: RiskPolicy,
        result: RiskRuleResult,
    ) -> None:
        # 从 strategy 或 context 中提取失败率信息
        failure_rate = self._extract_failure_rate(strategy, context)

        if failure_rate <= 0:
            return

        if failure_rate >= self.FAILURE_BLOCK_THRESHOLD:
            result.add_violation(
                self.name,
                f"Historical failure rate {failure_rate:.0%} >= {self.FAILURE_BLOCK_THRESHOLD:.0%}: BLOCK",
                "This strategy has a near-certain failure rate. Consider a completely different approach.",
            )
        elif failure_rate >= self.FAILURE_HIGH_THRESHOLD:
            result.add_violation(
                self.name,
                f"Historical failure rate {failure_rate:.0%} >= {self.FAILURE_HIGH_THRESHOLD:.0%}: HIGH risk",
                f"Strategy has failed {failure_rate:.0%} of the time. Require manual approval.",
            )
        elif failure_rate >= self.FAILURE_MEDIUM_THRESHOLD:
            result.add_violation(
                self.name,
                f"Historical failure rate {failure_rate:.0%} >= {self.FAILURE_MEDIUM_THRESHOLD:.0%}: MEDIUM risk",
                "Consider smaller scale test before full execution.",
            )

    def _extract_failure_rate(self, strategy: Any, context: RiskContext) -> float:
        """从策略或上下文中提取失败率."""
        # 尝试从 strategy 的属性获取
        if hasattr(strategy, "risk_score"):
            return float(strategy.risk_score) if isinstance(strategy.risk_score, (int, float)) else 0.0

        # 尝试从 dict 获取
        if isinstance(strategy, dict):
            return float(strategy.get("risk_score", 0) or 0)

        return 0.0


# ═══════════════════════════════════════════════════════════════
# Rule 3: Low Confidence
# ═══════════════════════════════════════════════════════════════


class LowConfidenceRule(BaseRiskRule):
    """低置信度检测.

    规则:
      - 置信度 < 0.3: 高不确定性
      - 置信度 < 0.5: 中等不确定性
      - 样本量 < 10: 额外不确定性
      - 样本量 < 5: 高不确定性
    """

    name = "LowConfidenceRule"

    CONFIDENCE_VERY_LOW = 0.3
    CONFIDENCE_LOW = 0.5

    UNCERTAINTY_SCORE_VERY_LOW = 0.7
    UNCERTAINTY_SCORE_LOW = 0.3

    SAMPLE_VERY_LOW = 5
    SAMPLE_LOW = 10

    SAMPLE_UNCERTAINTY_HIGH = 0.6
    SAMPLE_UNCERTAINTY_MED = 0.25

    def evaluate(
        self,
        strategy: Any,
        context: RiskContext,
        policy: RiskPolicy,
        result: RiskRuleResult,
    ) -> None:
        confidence = self._extract_confidence(strategy)

        # 置信度检查 (跳过 confidence=0 表示未设置)
        if confidence > 0 and confidence < self.CONFIDENCE_VERY_LOW:
            result.uncertainty_risk += self.UNCERTAINTY_SCORE_VERY_LOW
            result.add_violation(
                self.name,
                f"Confidence {confidence:.0%} < {self.CONFIDENCE_VERY_LOW:.0%}: very low confidence",
                "Require additional validation before execution.",
            )
        elif 0 < confidence < self.CONFIDENCE_LOW:
            result.uncertainty_risk += self.UNCERTAINTY_SCORE_LOW
            result.add_violation(
                self.name,
                f"Confidence {confidence:.0%} < {self.CONFIDENCE_LOW:.0%}: low confidence",
                "Consider gathering more data before executing.",
            )

        # 样本量检查
        if context.sample_size < self.SAMPLE_VERY_LOW and context.sample_size >= 0:
            result.uncertainty_risk += self.SAMPLE_UNCERTAINTY_HIGH
            result.add_violation(
                self.name,
                f"Sample size {context.sample_size} < {self.SAMPLE_VERY_LOW}: cannot auto-execute",
                "Insufficient data for automated decision. Require manual review.",
            )
        elif context.sample_size < self.SAMPLE_LOW:
            result.uncertainty_risk += self.SAMPLE_UNCERTAINTY_MED
            result.add_violation(
                self.name,
                f"Sample size {context.sample_size} < {self.SAMPLE_LOW}: low sample",
                "Small sample size increases uncertainty. Monitor closely.",
            )

        # Cap at 1.0
        result.uncertainty_risk = min(result.uncertainty_risk, 1.0)

    def _extract_confidence(self, strategy: Any) -> float:
        """从策略中提取置信度."""
        if hasattr(strategy, "confidence_score"):
            val = strategy.confidence_score
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
        if hasattr(strategy, "final_score"):
            val = strategy.final_score
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
        if isinstance(strategy, dict):
            val = strategy.get("confidence_score", 0) or 0
            if val > 0:
                return float(val)
            val = strategy.get("final_score", 0) or 0
            if val > 0:
                return float(val)
        return 0.0


# ═══════════════════════════════════════════════════════════════
# Rule 4: New Product
# ═══════════════════════════════════════════════════════════════


class NewProductRule(BaseRiskRule):
    """新产品限制.

    规则:
      - 上线 < 14 天: 高不确定性 + 高影响
      - 上线 < 30 天: 中等不确定性
      - 样本量 < 5: 不能自动执行
    """

    name = "NewProductRule"

    DAYS_VERY_NEW = 14
    DAYS_NEW = 30

    IMPACT_SCORE_VERY_NEW = 0.6
    IMPACT_SCORE_NEW = 0.3
    UNCERTAINTY_SCORE_NEW = 0.4

    def evaluate(
        self,
        strategy: Any,
        context: RiskContext,
        policy: RiskPolicy,
        result: RiskRuleResult,
    ) -> None:
        if not context.is_new_product:
            return

        if context.days_since_first_launch < self.DAYS_VERY_NEW:
            result.impact_risk += self.IMPACT_SCORE_VERY_NEW
            result.uncertainty_risk += self.UNCERTAINTY_SCORE_NEW
            result.add_violation(
                self.name,
                f"Very new product ({context.days_since_first_launch}d < {self.DAYS_VERY_NEW}d): high risk",
                "Extremely limited data. Recommend manual operation only.",
            )
        else:
            result.impact_risk += self.IMPACT_SCORE_NEW
            result.uncertainty_risk += self.UNCERTAINTY_SCORE_NEW * 0.5
            result.add_violation(
                self.name,
                f"New product ({context.days_since_first_launch}d < {self.DAYS_NEW}d): elevated risk",
                "Limited historical data. Use conservative parameters.",
            )

        # 样本量不足的额外惩罚
        if context.sample_size < 5:
            result.add_violation(
                self.name,
                f"New product with sample_size {context.sample_size} < 5: cannot auto-execute",
                "Insufficient data for any automated decision. Manual review required.",
            )

        # Cap
        result.impact_risk = min(result.impact_risk, 1.0)
        result.uncertainty_risk = min(result.uncertainty_risk, 1.0)


# ═══════════════════════════════════════════════════════════════
# Rule 5: High Impact Operations
# ═══════════════════════════════════════════════════════════════


class HighImpactRule(BaseRiskRule):
    """高影响操作检测.

    规则:
      - 删除 Campaign: impact = 0.9
      - 大额预算调整 (> 50%): impact = 0.5
      - 修改定向: impact = 0.4
      - 出价大幅调整: impact = 0.3
    """

    name = "HighImpactRule"

    # 高影响操作类型及风险分数
    HIGH_IMPACT_ACTIONS: dict[str, float] = {
        "delete_campaign": 0.9,
        "delete_adset": 0.85,
        "delete_creative": 0.7,
        "pause_campaign": 0.5,
        "budget_increase_major": 0.5,
        "budget_decrease_major": 0.5,
        "targeting_change": 0.4,
        "bid_change_major": 0.3,
        "audience_expansion": 0.25,
        "campaign_restructure": 0.45,
        "budget_increase": 0.2,
        "budget_decrease": 0.2,
        "bid_change": 0.15,
    }

    def evaluate(
        self,
        strategy: Any,
        context: RiskContext,
        policy: RiskPolicy,
        result: RiskRuleResult,
    ) -> None:
        action_type = self._extract_action_type(strategy, context)

        if not action_type:
            return

        impact_score = self.HIGH_IMPACT_ACTIONS.get(action_type, 0.0)

        if impact_score >= 0.5:
            result.impact_risk += impact_score
            result.add_violation(
                self.name,
                f"High-impact action '{action_type}' detected (impact={impact_score:.1f})",
                "High-impact operations should require manual approval.",
            )
        elif impact_score >= 0.3:
            result.impact_risk += impact_score
            result.add_violation(
                self.name,
                f"Medium-impact action '{action_type}' detected (impact={impact_score:.1f})",
                "Consider staged rollout to reduce impact risk.",
            )
        elif impact_score > 0:
            result.impact_risk += impact_score

        # Cap at 1.0
        result.impact_risk = min(result.impact_risk, 1.0)

    def _extract_action_type(self, strategy: Any, context: RiskContext) -> str:
        """从策略或上下文中提取动作类型."""
        # 尝试从 strategy 获取
        if hasattr(strategy, "strategy_name"):
            name = strategy.strategy_name.lower()
            for action in self.HIGH_IMPACT_ACTIONS:
                if action in name:
                    return action

        # 尝试从 dict 获取
        if isinstance(strategy, dict):
            name = (strategy.get("strategy_name", "") or "").lower()
            for action in self.HIGH_IMPACT_ACTIONS:
                if action in name:
                    return action

            # 检查 strategy dict 中的 action_type
            action_type = strategy.get("action_type", "")
            if action_type and action_type in self.HIGH_IMPACT_ACTIONS:
                return action_type

        # 从上下文的机会类型推断
        if context.opportunity_type:
            opp = context.opportunity_type.lower()
            if "budget" in opp:
                return "budget_increase" if context.budget_change_ratio > 0 else "budget_decrease"
            if "audience" in opp:
                return "audience_expansion"
            if "campaign" in opp and "restructure" in opp:
                return "campaign_restructure"
            if "bid" in opp:
                return "bid_change"

        return ""


# ═══════════════════════════════════════════════════════════════
# Risk Rule Engine
# ═══════════════════════════════════════════════════════════════


class RiskRuleEngine:
    """风险规则引擎 — 评估策略的多维度风险.

    综合所有规则，输出 aggression_risk, uncertainty_risk, impact_risk。

    用法:
        engine = RiskRuleEngine(policy)
        result = engine.evaluate(strategy, context)
        print(f"Aggression: {result.aggression_risk}")
    """

    def __init__(self, policy: RiskPolicy | None = None):
        """初始化规则引擎.

        Args:
            policy: 风险策略配置 (默认使用 RiskPolicy())
        """
        self._policy = policy or RiskPolicy()
        self._rules: list[BaseRiskRule] = []
        self._register_default_rules()
        self._evaluation_count: int = 0

    def _register_default_rules(self) -> None:
        """注册默认规则."""
        self._rules = [
            BudgetAggressionRule(),
            HistoricalFailureCheckRule(),
            LowConfidenceRule(),
            NewProductRule(),
            HighImpactRule(),
        ]

    def evaluate(
        self,
        strategy: Any,
        context: RiskContext,
    ) -> RiskRuleResult:
        """评估策略的风险.

        Args:
            strategy: 策略对象 (StrategyCandidate / dict / GrowthStrategyPattern)
            context: 风险评估上下文

        Returns:
            RiskRuleResult: 聚合的风险评估结果
        """
        self._evaluation_count += 1

        result = RiskRuleResult()

        for rule in self._rules:
            try:
                rule.evaluate(strategy, context, self._policy, result)
            except Exception:
                # 单个规则失败不影响整体评估
                continue

        return result

    def evaluate_batch(
        self,
        strategies: list[Any],
        context: RiskContext,
    ) -> list[RiskRuleResult]:
        """批量评估多个策略.

        Args:
            strategies: 策略列表
            context: 风险评估上下文

        Returns:
            list[RiskRuleResult]: 每个策略的评估结果
        """
        return [self.evaluate(s, context) for s in strategies]

    # ═══════════════════════════════════════════════════════════
    # Properties
    # ═══════════════════════════════════════════════════════════

    @property
    def policy(self) -> RiskPolicy:
        return self._policy

    @property
    def rules(self) -> list[BaseRiskRule]:
        return list(self._rules)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count

    def add_rule(self, rule: BaseRiskRule) -> None:
        """添加自定义规则."""
        self._rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """按名称移除规则."""
        for i, rule in enumerate(self._rules):
            if rule.name == rule_name:
                self._rules.pop(i)
                return True
        return False