"""E13.5.4 Risk Models — 风险控制数据模型.

将 Failure Memory 从"记住失败"升级为"实时阻止错误决策"。

核心模型:
  - RiskLevel: 风险等级枚举 (SAFE/LOW/MEDIUM/HIGH/CRITICAL)
  - RiskDecision: 风险决策枚举 (ALLOW/WARNING/BLOCK)
  - RiskAssessment: 风险评估结果
  - RiskPolicy: 风险策略配置
  - RiskContext: 风险评估上下文

连接:
  E13.4.4 FailureMemory → E13.5.4 RiskController → E13.5.5 DecisionEngine
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class RiskLevel(str, Enum):
    """风险等级 — E13.5.4 风险控制专用."""
    SAFE = "safe"           # 安全: 风险极低，可自动执行
    LOW = "low"             # 低风险: 可自动执行，需监控
    MEDIUM = "medium"       # 中风险: 建议人工审核
    HIGH = "high"           # 高风险: 需要人工审批
    CRITICAL = "critical"   # 致命风险: 禁止执行


class RiskDecision(str, Enum):
    """风险决策 — 对该策略的执行建议."""
    ALLOW = "allow"         # 允许自动执行
    WARNING = "warning"     # 警告但允许 (需监控)
    BLOCK = "block"         # 禁止执行


# ═══════════════════════════════════════════════════════════════
# Risk Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class RiskContext:
    """风险评估上下文 — 评估策略风险所需的环境信息.

    Attributes:
        product_id: 产品 ID
        campaign_id: 广告系列 ID
        audience_segment: 受众分群
        platform: 投放平台
        budget_current: 当前预算
        budget_proposed: 拟调整预算
        sample_size: 相关样本量
        days_since_first_launch: 产品上线天数
        opportunity_type: 机会类型
        signal_types: 当前信号类型
        metadata: 扩展元数据
    """
    product_id: str = ""
    campaign_id: str = ""
    audience_segment: str = ""
    platform: str = "meta_ads"
    budget_current: float = 0.0
    budget_proposed: float = 0.0
    sample_size: int = 0
    days_since_first_launch: int = 30
    opportunity_type: str = ""
    signal_types: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "campaign_id": self.campaign_id,
            "audience_segment": self.audience_segment,
            "platform": self.platform,
            "budget_current": self.budget_current,
            "budget_proposed": self.budget_proposed,
            "sample_size": self.sample_size,
            "days_since_first_launch": self.days_since_first_launch,
            "opportunity_type": self.opportunity_type,
            "signal_types": self.signal_types,
            "metadata": self.metadata,
        }

    @property
    def budget_change_ratio(self) -> float:
        """预算变化比例."""
        if self.budget_current <= 0:
            return 1.0  # 从零开始 = 100% 变化
        return abs(self.budget_proposed - self.budget_current) / self.budget_current

    @property
    def is_new_product(self) -> bool:
        """是否新产品 (上线 < 30 天)."""
        return self.days_since_first_launch < 30

    @property
    def is_low_sample(self) -> bool:
        """是否样本量不足."""
        return self.sample_size < 10


# ═══════════════════════════════════════════════════════════════
# Risk Assessment
# ═══════════════════════════════════════════════════════════════


@dataclass
class RiskAssessment:
    """风险评估结果 — 对策略的综合风险评估.

    Attributes:
        assessment_id: 评估唯一标识
        strategy_id: 被评估的策略 ID
        strategy_name: 策略名称
        risk_score: 综合风险评分 [0, 1] (越高越危险)
        risk_level: 风险等级
        decision: 风险决策 (ALLOW/WARNING/BLOCK)
        failure_risk: 来自 Failure Memory 的历史风险
        aggression_risk: 策略激进程度风险
        uncertainty_risk: 不确定性风险
        impact_risk: 影响程度风险
        failure_patterns: 匹配到的失败模式
        failure_warnings: 失败警告详情
        rule_violations: 触发的风险规则
        reasons: 风险原因列表
        recommendations: 建议列表
        requires_approval: 是否需要人工审批
        created_at: 评估时间
    """
    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    strategy_name: str = ""
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.SAFE
    decision: RiskDecision = RiskDecision.ALLOW
    failure_risk: float = 0.0
    aggression_risk: float = 0.0
    uncertainty_risk: float = 0.0
    impact_risk: float = 0.0
    failure_patterns: list[dict[str, Any]] = field(default_factory=list)
    failure_warnings: list[dict[str, Any]] = field(default_factory=list)
    rule_violations: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    requires_approval: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level.value,
            "decision": self.decision.value,
            "failure_risk": round(self.failure_risk, 4),
            "aggression_risk": round(self.aggression_risk, 4),
            "uncertainty_risk": round(self.uncertainty_risk, 4),
            "impact_risk": round(self.impact_risk, 4),
            "failure_patterns": self.failure_patterns,
            "failure_warnings": self.failure_warnings,
            "rule_violations": self.rule_violations,
            "reasons": self.reasons,
            "recommendations": self.recommendations,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
        }

    @property
    def is_safe(self) -> bool:
        """是否安全可执行."""
        return self.decision == RiskDecision.ALLOW

    @property
    def is_blocked(self) -> bool:
        """是否被阻止."""
        return self.decision == RiskDecision.BLOCK

    @property
    def is_warning(self) -> bool:
        """是否需要警告."""
        return self.decision == RiskDecision.WARNING

    def add_reason(self, reason: str) -> None:
        """添加风险原因."""
        self.reasons.append(reason)

    def add_recommendation(self, rec: str) -> None:
        """添加建议."""
        self.recommendations.append(rec)

    def add_rule_violation(self, rule: str) -> None:
        """添加规则违规."""
        self.rule_violations.append(rule)

    def add_failure_pattern(self, pattern: dict[str, Any]) -> None:
        """添加匹配到的失败模式."""
        self.failure_patterns.append(pattern)

    def add_failure_warning(self, warning: dict[str, Any]) -> None:
        """添加失败警告."""
        self.failure_warnings.append(warning)


# ═══════════════════════════════════════════════════════════════
# Risk Policy
# ═══════════════════════════════════════════════════════════════


@dataclass
class RiskPolicy:
    """风险策略 — 风险控制的阈值和参数配置.

    Attributes:
        block_threshold: 综合风险 >= 此值直接 BLOCK [默认 0.85]
        warning_threshold: 综合风险 >= 此值触发 WARNING [默认 0.50]
        safe_threshold: 综合风险 < 此值为 SAFE [默认 0.30]
        max_budget_increase: 最大允许预算增幅 (比例) [默认 0.30]
        max_budget_increase_new_product: 新产品最大预算增幅 [默认 0.10]
        min_sample_size: 最低样本量阈值 [默认 10]
        min_confidence: 最低置信度阈值 [默认 0.5]
        require_validation: 是否需要验证
        auto_allow_safe: 安全级别是否自动允许
        escalation_required: 是否需要升级到人工
    """
    block_threshold: float = 0.85
    warning_threshold: float = 0.50
    safe_threshold: float = 0.30
    max_budget_increase: float = 0.30
    max_budget_increase_new_product: float = 0.10
    min_sample_size: int = 10
    min_confidence: float = 0.5
    require_validation: bool = True
    auto_allow_safe: bool = True
    escalation_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_threshold": self.block_threshold,
            "warning_threshold": self.warning_threshold,
            "safe_threshold": self.safe_threshold,
            "max_budget_increase": self.max_budget_increase,
            "max_budget_increase_new_product": self.max_budget_increase_new_product,
            "min_sample_size": self.min_sample_size,
            "min_confidence": self.min_confidence,
            "require_validation": self.require_validation,
            "auto_allow_safe": self.auto_allow_safe,
            "escalation_required": self.escalation_required,
        }

    @classmethod
    def conservative(cls) -> RiskPolicy:
        """保守策略 — 更严格的阈值."""
        return cls(
            block_threshold=0.70,
            warning_threshold=0.35,
            safe_threshold=0.20,
            max_budget_increase=0.15,
            max_budget_increase_new_product=0.05,
            min_sample_size=20,
            min_confidence=0.6,
            require_validation=True,
            escalation_required=True,
        )

    @classmethod
    def aggressive(cls) -> RiskPolicy:
        """激进策略 — 更宽松的阈值."""
        return cls(
            block_threshold=0.95,
            warning_threshold=0.65,
            safe_threshold=0.40,
            max_budget_increase=0.50,
            max_budget_increase_new_product=0.20,
            min_sample_size=5,
            min_confidence=0.4,
            require_validation=False,
            escalation_required=False,
        )