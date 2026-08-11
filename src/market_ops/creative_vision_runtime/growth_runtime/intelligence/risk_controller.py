"""E13.5.4 Risk Controller — 风险控制器.

将 Failure Memory 从"记住失败"升级为"实时阻止错误决策"。

核心流程:
  Strategy
      ↓
  Failure Memory Check  → failure_risk (40%)
      ↓
  Risk Rules Engine     → aggression_risk (25%)
                          uncertainty_risk (20%)
                          impact_risk (15%)
      ↓
  Risk Score Calculation
      ↓
  ALLOW / WARNING / BLOCK

连接:
  E13.4.4 FailureMemory → E13.5.4 RiskController → E13.5.5 DecisionEngine
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .risk_models import (
    RiskAssessment,
    RiskContext,
    RiskDecision,
    RiskLevel,
    RiskPolicy,
)
from .risk_rules import RiskRuleEngine, RiskRuleResult

if TYPE_CHECKING:
    from ..memory.failure_memory import FailureMemory


# ═══════════════════════════════════════════════════════════════
# Risk Calculator
# ═══════════════════════════════════════════════════════════════


class RiskCalculator:
    """风险计算器 — 加权融合四个风险维度.

    公式:
      risk_score = failure_risk×0.40 + aggression_risk×0.25
                 + uncertainty_risk×0.20 + impact_risk×0.15
    """

    # 权重
    FAILURE_WEIGHT = 0.40
    AGGRESSION_WEIGHT = 0.25
    UNCERTAINTY_WEIGHT = 0.20
    IMPACT_WEIGHT = 0.15

    def calculate(
        self,
        failure_risk: float,
        aggression_risk: float,
        uncertainty_risk: float,
        impact_risk: float,
    ) -> float:
        """计算综合风险评分.

        Args:
            failure_risk: 历史失败风险 [0, 1]
            aggression_risk: 策略激进程度 [0, 1]
            uncertainty_risk: 不确定性风险 [0, 1]
            impact_risk: 影响程度风险 [0, 1]

        Returns:
            float: 综合风险评分 [0, 1]
        """
        score = (
            failure_risk * self.FAILURE_WEIGHT
            + aggression_risk * self.AGGRESSION_WEIGHT
            + uncertainty_risk * self.UNCERTAINTY_WEIGHT
            + impact_risk * self.IMPACT_WEIGHT
        )
        return round(min(max(score, 0.0), 1.0), 4)

    def get_risk_breakdown(
        self,
        failure_risk: float,
        aggression_risk: float,
        uncertainty_risk: float,
        impact_risk: float,
    ) -> dict[str, float]:
        """获取风险分解详情."""
        return {
            "failure_risk_weighted": round(failure_risk * self.FAILURE_WEIGHT, 4),
            "aggression_risk_weighted": round(aggression_risk * self.AGGRESSION_WEIGHT, 4),
            "uncertainty_risk_weighted": round(uncertainty_risk * self.UNCERTAINTY_WEIGHT, 4),
            "impact_risk_weighted": round(impact_risk * self.IMPACT_WEIGHT, 4),
        }


# ═══════════════════════════════════════════════════════════════
# Risk Controller
# ═══════════════════════════════════════════════════════════════


class RiskController:
    """风险控制器 — 整合 Failure Memory + Risk Rules 进行综合风险评估.

    将 E13.4.4 Failure Memory 从被动记录升级为主动拦截。

    用法:
        controller = RiskController(failure_memory, policy)
        assessment = controller.evaluate(strategy, context)
        if assessment.is_blocked:
            print("Cannot execute:", assessment.reasons)
        elif assessment.is_warning:
            print("Warning:", assessment.recommendations)
    """

    # 风险构成权重
    FAILURE_WEIGHT = 0.40
    AGGRESSION_WEIGHT = 0.25
    UNCERTAINTY_WEIGHT = 0.20
    IMPACT_WEIGHT = 0.15

    def __init__(
        self,
        failure_memory: FailureMemory | None = None,
        policy: RiskPolicy | None = None,
    ):
        """初始化风险控制器.

        Args:
            failure_memory: FailureMemory 实例 (可选，用于历史失败检查)
            policy: 风险策略配置 (默认使用 RiskPolicy())
        """
        self._failure_memory = failure_memory
        self._policy = policy or RiskPolicy()
        self._rule_engine = RiskRuleEngine(self._policy)
        self._calculator = RiskCalculator()
        self._evaluation_count: int = 0

    # ═══════════════════════════════════════════════════════════
    # Core: Evaluate
    # ═══════════════════════════════════════════════════════════

    def evaluate(
        self,
        strategy: Any,
        context: RiskContext,
        strategy_name: str = "",
    ) -> RiskAssessment:
        """评估策略的综合风险.

        完整流程:
          1. Failure Memory Check → failure_risk
          2. Risk Rules Engine → aggression/uncertainty/impact
          3. Weighted Score → risk_score
          4. Map → RiskLevel + RiskDecision
          5. Return RiskAssessment

        Args:
            strategy: 策略对象 (StrategyCandidate / GrowthStrategyPattern / dict)
            context: 风险评估上下文
            strategy_name: 策略名称 (可选)

        Returns:
            RiskAssessment: 综合风险评估结果
        """
        self._evaluation_count += 1

        # 提取策略 ID 和名称
        strategy_id = self._extract_strategy_id(strategy)
        if not strategy_name:
            strategy_name = self._extract_strategy_name(strategy)

        # 创建评估对象
        assessment = RiskAssessment(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
        )

        # Step 1: Failure Memory Check
        failure_risk, failure_warnings, failure_patterns = self._check_failure_memory(
            strategy, context
        )
        assessment.failure_risk = failure_risk
        assessment.failure_warnings = failure_warnings
        assessment.failure_patterns = failure_patterns

        # Step 2: Risk Rules Engine
        rule_result = self._rule_engine.evaluate(strategy, context)
        assessment.aggression_risk = rule_result.aggression_risk
        assessment.uncertainty_risk = rule_result.uncertainty_risk
        assessment.impact_risk = rule_result.impact_risk
        assessment.rule_violations = rule_result.violations
        assessment.reasons = rule_result.reasons
        assessment.recommendations = rule_result.recommendations

        # Step 3: Weighted Score
        assessment.risk_score = self._calculator.calculate(
            failure_risk=failure_risk,
            aggression_risk=rule_result.aggression_risk,
            uncertainty_risk=rule_result.uncertainty_risk,
            impact_risk=rule_result.impact_risk,
        )

        # Step 4: Map to RiskLevel
        assessment.risk_level = self._map_to_risk_level(assessment.risk_score)

        # Step 5: Determine Decision + Approval
        assessment.decision = self._determine_decision(
            assessment.risk_score,
            assessment.risk_level,
            failure_risk,
            failure_warnings,
            context,
        )
        assessment.requires_approval = self._determine_approval(
            assessment.risk_score,
            assessment.risk_level,
            failure_warnings,
            context,
        )

        # 如果规则或失败记忆推荐审批，则强制要求
        if assessment.requires_approval and assessment.decision == RiskDecision.ALLOW:
            assessment.decision = RiskDecision.WARNING

        return assessment

    def evaluate_batch(
        self,
        strategies: list[Any],
        context: RiskContext,
    ) -> list[RiskAssessment]:
        """批量评估多个策略.

        Args:
            strategies: 策略列表
            context: 风险评估上下文

        Returns:
            list[RiskAssessment]: 每个策略的评估结果
        """
        return [self.evaluate(s, context) for s in strategies]

    def is_safe(
        self,
        strategy: Any,
        context: RiskContext,
    ) -> bool:
        """快速检查策略是否安全 (可直接执行).

        Args:
            strategy: 策略对象
            context: 风险评估上下文

        Returns:
            bool: 是否安全
        """
        assessment = self.evaluate(strategy, context)
        return assessment.is_safe

    def is_blocked(
        self,
        strategy: Any,
        context: RiskContext,
    ) -> bool:
        """快速检查策略是否被阻止.

        Args:
            strategy: 策略对象
            context: 风险评估上下文

        Returns:
            bool: 是否被阻止
        """
        assessment = self.evaluate(strategy, context)
        return assessment.is_blocked

    # ═══════════════════════════════════════════════════════════
    # Failure Memory Integration
    # ═══════════════════════════════════════════════════════════

    def _check_failure_memory(
        self,
        strategy: Any,
        context: RiskContext,
    ) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
        """通过 FailureMemory 检查历史失败.

        Returns:
            tuple: (failure_risk, failure_warnings, failure_patterns)
        """
        if self._failure_memory is None:
            return 0.0, [], []

        failure_warnings: list[dict[str, Any]] = []
        failure_patterns: list[dict[str, Any]] = []
        max_failure_risk = 0.0

        # 尝试获取策略动作类型
        action_type = self._extract_action_type(strategy)
        opp_type = context.opportunity_type
        audience = context.audience_segment
        product = context.product_id

        try:
            if action_type:
                # 使用 check_action 获取单个动作的警告
                warnings = self._failure_memory.check_action(
                    action_type=action_type,
                    opportunity_type=opp_type,
                    audience_segment=audience,
                    product_category=product,
                )
            else:
                # 尝试使用 check_strategy 获取策略所有步骤的警告
                if hasattr(strategy, "steps"):
                    warnings_dict = self._failure_memory.check_strategy(
                        strategy=strategy,
                        opportunity_type=opp_type,
                        audience_segment=audience,
                        product_category=product,
                    )
                    # 扁平化
                    warnings: list[Any] = []
                    for step_warnings in warnings_dict.values():
                        warnings.extend(step_warnings)
                else:
                    # 使用 compute_risk_score 直接计算
                    risk_score = self._failure_memory.compute_risk_score(
                        action_type=opp_type or "unknown",
                        opportunity_type=opp_type,
                        audience_segment=audience,
                        product_category=product,
                    )
                    return risk_score, [], []

            for w in warnings:
                failure_warnings.append({
                    "pattern_name": w.pattern_name,
                    "risk_score": w.risk_score,
                    "failure_rate": w.failure_rate,
                    "expected_loss": w.expected_loss,
                    "severity": w.severity.value if hasattr(w.severity, "value") else str(w.severity),
                    "suggestion": w.suggestion,
                    "requires_approval": w.requires_approval,
                    "context_summary": w.context_summary,
                })
                if w.risk_score > max_failure_risk:
                    max_failure_risk = w.risk_score

            # 找到对应的 FailurePattern
            # 从 FailureMemory 获取所有模式，匹配
            if hasattr(self._failure_memory, "get_all"):
                all_patterns = self._failure_memory.get_all()
                for p in all_patterns:
                    if action_type and p.condition.action_type == action_type:
                        failure_patterns.append({
                            "failure_id": p.failure_id,
                            "name": p.name,
                            "category": p.category.value if hasattr(p.category, "value") else str(p.category),
                            "failure_rate": p.failure_rate,
                            "total_attempts": p.total_attempts,
                            "avg_loss": p.avg_loss,
                            "severity": p.severity.value if hasattr(p.severity, "value") else str(p.severity),
                            "suggestion": p.suggestion,
                        })

        except Exception:
            # FailureMemory 检查失败时降级
            pass

        return max_failure_risk, failure_warnings, failure_patterns

    # ═══════════════════════════════════════════════════════════
    # Decision Mapping
    # ═══════════════════════════════════════════════════════════

    def _map_to_risk_level(self, risk_score: float) -> RiskLevel:
        """将风险评分映射到风险等级.

        Args:
            risk_score: 综合风险评分 [0, 1]

        Returns:
            RiskLevel: 风险等级
        """
        if risk_score >= self._policy.block_threshold:
            return RiskLevel.CRITICAL
        if risk_score >= 0.75:
            return RiskLevel.HIGH
        if risk_score >= self._policy.warning_threshold:
            return RiskLevel.MEDIUM
        if risk_score >= self._policy.safe_threshold:
            return RiskLevel.LOW
        return RiskLevel.SAFE

    def _determine_decision(
        self,
        risk_score: float,
        risk_level: RiskLevel,
        failure_risk: float,
        failure_warnings: list[dict[str, Any]],
        context: RiskContext,
    ) -> RiskDecision:
        """确定风险决策.

        Decision logic:
          - risk_score >= block_threshold → BLOCK
          - 历史失败率 > 0.7 → BLOCK
          - risk_score >= warning_threshold → WARNING
          - 新产品 + 样本量 < 5 → WARNING
          - 否则 → ALLOW
        """
        # 硬阻断条件
        if risk_score >= self._policy.block_threshold:
            return RiskDecision.BLOCK

        # 历史失败率过高 → BLOCK
        if failure_risk >= 0.85:
            return RiskDecision.BLOCK

        # 历史失败率 > 0.7 → 检查是否有高严重性警告
        if failure_risk >= 0.7:
            for w in failure_warnings:
                if w.get("severity") in ("critical", "high"):
                    return RiskDecision.BLOCK
            return RiskDecision.WARNING

        # 新产品 + 样本量不足 → 不能自动执行
        if context.is_new_product and context.sample_size < 5:
            return RiskDecision.WARNING

        # 达到警告阈值
        if risk_score >= self._policy.warning_threshold:
            return RiskDecision.WARNING

        # 安全阈值以下
        if risk_score < self._policy.safe_threshold and self._policy.auto_allow_safe:
            return RiskDecision.ALLOW

        # 低风险也允许
        if risk_level == RiskLevel.LOW:
            return RiskDecision.ALLOW

        return RiskDecision.ALLOW

    def _determine_approval(
        self,
        risk_score: float,
        risk_level: RiskLevel,
        failure_warnings: list[dict[str, Any]],
        context: RiskContext,
    ) -> bool:
        """判断是否需要人工审批.

        Approval conditions:
          - CRITICAL → 需要审批
          - HIGH → 需要审批
          - 有高严重性失败警告 → 需要审批
          - 新产品 + 低样本量 → 需要审批
          - escalation_required → 需要审批
        """
        if risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            return True

        # 有高严重性失败警告
        for w in failure_warnings:
            if w.get("severity") in ("critical", "high"):
                return True
            if w.get("requires_approval"):
                return True

        # 新产品 + 低样本量
        if context.is_new_product and context.sample_size < self._policy.min_sample_size:
            return True

        # 策略要求升级
        if self._policy.escalation_required:
            return True

        return False

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _extract_strategy_id(strategy: Any) -> str:
        """从策略对象中提取 ID."""
        if hasattr(strategy, "strategy_id"):
            return str(strategy.strategy_id) if strategy.strategy_id else ""
        if isinstance(strategy, dict):
            return str(strategy.get("strategy_id", "") or "")
        return ""

    @staticmethod
    def _extract_strategy_name(strategy: Any) -> str:
        """从策略对象中提取名称."""
        if hasattr(strategy, "strategy_name"):
            return str(strategy.strategy_name) if strategy.strategy_name else ""
        if isinstance(strategy, dict):
            return str(strategy.get("strategy_name", "") or "")
        return ""

    @staticmethod
    def _extract_action_type(strategy: Any) -> str:
        """从策略中提取动作类型."""
        # StrategyCandidate
        if hasattr(strategy, "strategy") and strategy.strategy:
            s = strategy.strategy
            if isinstance(s, dict):
                trigger = s.get("trigger", {})
                if isinstance(trigger, dict):
                    return trigger.get("action_type", "")
        # GrowthStrategyPattern
        if hasattr(strategy, "trigger"):
            t = strategy.trigger
            if hasattr(t, "action_type"):
                return t.action_type
        # dict
        if isinstance(strategy, dict):
            trigger = strategy.get("trigger", {})
            if isinstance(trigger, dict):
                return trigger.get("action_type", "")
            return strategy.get("action_type", "")
        return ""

    # ═══════════════════════════════════════════════════════════
    # Properties
    # ═══════════════════════════════════════════════════════════

    @property
    def policy(self) -> RiskPolicy:
        return self._policy

    @property
    def rule_engine(self) -> RiskRuleEngine:
        return self._rule_engine

    @property
    def calculator(self) -> RiskCalculator:
        return self._calculator

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count

    @property
    def has_failure_memory(self) -> bool:
        return self._failure_memory is not None

    def update_policy(self, policy: RiskPolicy) -> None:
        """更新风险策略."""
        self._policy = policy
        self._rule_engine = RiskRuleEngine(policy)