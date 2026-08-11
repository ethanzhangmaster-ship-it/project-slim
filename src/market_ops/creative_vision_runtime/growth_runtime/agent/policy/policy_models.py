"""E13.7.4.2 Policy Models — 策略系统核心数据模型.

定义 Agent Policy System 的完整数据模型:
  - PolicyDecision: 四级策略决策 (ALLOW / WARN / BLOCK / REQUIRE_APPROVAL)
  - PolicyActionType: Agent 可执行的动作类型
  - PolicyContext: 策略评估上下文 (从 Runtime 传入)
  - PolicyResult: 单次策略评估结果
  - RuleResult: 单条规则评估结果
  - RiskRule: 风险规则基类

与 E13.6.4 Safety Controller 的关系:
  Agent Policy (本层) → 决定 Agent 能不能提出/执行这个动作
  Safety Controller (E13.6.4) → 决定这个动作执行时是否安全
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class PolicyDecision(str, Enum):
    """策略决策结果.

    ALLOW: 允许执行，无需额外检查
    WARN: 允许执行，但记录警告 (如: 置信度偏低)
    BLOCK: 禁止执行，直接拒绝 (如: 超出日预算上限)
    REQUIRE_APPROVAL: 需要人工审批 (如: 预算增加 > 30%)
    """
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


class PolicyActionType(str, Enum):
    """Agent 可执行的动作类型."""
    CREATE_CAMPAIGN = "create_campaign"
    UPDATE_BUDGET = "update_budget"
    PAUSE_CAMPAIGN = "pause_campaign"
    RESUME_CAMPAIGN = "resume_campaign"
    CREATE_CREATIVE = "create_creative"
    MUTATE_CREATIVE = "mutate_creative"
    CHANGE_TARGETING = "change_targeting"
    CHANGE_BIDDING = "change_bidding"
    SCALE_BUDGET = "scale_budget"
    BATCH_CREATE = "batch_create"
    ROLLBACK = "rollback"


class RuleSeverity(str, Enum):
    """规则严重程度."""
    CRITICAL = "critical"  # 违反即 BLOCK
    HIGH = "high"          # 违反即 REQUIRE_APPROVAL
    MEDIUM = "medium"      # 违反即 WARN
    LOW = "low"            # 仅记录


class ApprovalStatus(str, Enum):
    """审批状态."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════════════════
# Severity → Decision 映射
# ═══════════════════════════════════════════════════════════════

SEVERITY_TO_DECISION: dict[RuleSeverity, PolicyDecision] = {
    RuleSeverity.CRITICAL: PolicyDecision.BLOCK,
    RuleSeverity.HIGH: PolicyDecision.REQUIRE_APPROVAL,
    RuleSeverity.MEDIUM: PolicyDecision.WARN,
    RuleSeverity.LOW: PolicyDecision.ALLOW,
}

# 决策严格度排序 (用于取最严格决策)
DECISION_SEVERITY: dict[PolicyDecision, int] = {
    PolicyDecision.ALLOW: 0,
    PolicyDecision.WARN: 1,
    PolicyDecision.REQUIRE_APPROVAL: 2,
    PolicyDecision.BLOCK: 3,
}


# ═══════════════════════════════════════════════════════════════
# Policy Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class PolicyContext:
    """策略评估上下文 — 从 Runtime 传入的完整决策信息.

    Attributes:
        action_type: 动作类型
        campaign_id: 目标 Campaign ID
        budget_change: 预算变动金额
        budget_change_ratio: 预算变动比例
        current_budget: 当前预算
        current_spend: 当前累计花费
        daily_spend_limit: 日预算上限
        daily_spend: 当日已花费
        confidence: Agent 置信度 [0, 1]
        risk_score: 风险评分 [0, 1]
        agent_cycle: Agent 当前循环数
        agent_consecutive_errors: Agent 连续错误数
        campaign_age_hours: Campaign 创建时长 (小时)
        creative_count: 当日已创建素材数
        max_creative_per_day: 每日最大素材数
        max_campaign_per_day: 每日最大 Campaign 数
        user_confirmation: 用户是否已确认
        metadata: 扩展元数据
    """
    action_type: str = ""
    campaign_id: str = ""
    budget_change: float = 0.0
    budget_change_ratio: float = 0.0
    current_budget: float = 0.0
    current_spend: float = 0.0
    daily_spend_limit: float = 10000.0
    daily_spend: float = 0.0
    confidence: float = 0.5
    risk_score: float = 0.0
    agent_cycle: int = 0
    agent_consecutive_errors: int = 0
    campaign_age_hours: float = 0.0
    creative_count: int = 0
    max_creative_per_day: int = 20
    max_campaign_per_day: int = 5
    user_confirmation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "campaign_id": self.campaign_id,
            "budget_change": self.budget_change,
            "budget_change_ratio": self.budget_change_ratio,
            "current_budget": self.current_budget,
            "current_spend": self.current_spend,
            "daily_spend_limit": self.daily_spend_limit,
            "daily_spend": self.daily_spend,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "agent_cycle": self.agent_cycle,
            "agent_consecutive_errors": self.agent_consecutive_errors,
            "campaign_age_hours": self.campaign_age_hours,
            "creative_count": self.creative_count,
            "max_creative_per_day": self.max_creative_per_day,
            "max_campaign_per_day": self.max_campaign_per_day,
            "user_confirmation": self.user_confirmation,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Rule Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class RuleResult:
    """单条规则评估结果.

    Attributes:
        rule_id: 规则 ID
        rule_name: 规则名称
        triggered: 是否触发
        decision: 触发后的决策
        reason: 触发原因
        severity: 严重程度
    """
    rule_id: str = ""
    rule_name: str = ""
    triggered: bool = False
    decision: PolicyDecision = PolicyDecision.ALLOW
    reason: str = ""
    severity: RuleSeverity = RuleSeverity.LOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "triggered": self.triggered,
            "decision": self.decision.value,
            "reason": self.reason,
            "severity": self.severity.value,
        }


# ═══════════════════════════════════════════════════════════════
# Policy Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class PolicyResult:
    """策略评估结果 — PolicyEngine.evaluate() 的返回值.

    Attributes:
        result_id: 结果 ID
        decision: 最终决策
        reason: 决策原因
        risk_score: 综合风险评分 [0, 1]
        rule_results: 所有规则的评估结果
        triggered_rules: 已触发的规则
        warnings: 警告消息
        errors: 错误消息
        requires_approval: 是否需要审批
        is_blocked: 是否被阻止
        timestamp: 评估时间
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision: PolicyDecision = PolicyDecision.ALLOW
    reason: str = ""
    risk_score: float = 0.0
    rule_results: list[RuleResult] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires_approval: bool = False
    is_blocked: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "decision": self.decision.value,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "triggered_rules": self.triggered_rules,
            "warnings": self.warnings,
            "errors": self.errors,
            "requires_approval": self.requires_approval,
            "is_blocked": self.is_blocked,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════
# Risk Rule Base
# ═══════════════════════════════════════════════════════════════


@dataclass
class RiskRule:
    """风险规则基类.

    每条规则定义:
      - 触发条件 (condition)
      - 违反时的决策 (decision)
      - 违反原因 (reason_template)

    Attributes:
        rule_id: 规则 ID
        name: 规则名称
        description: 规则描述
        severity: 严重程度
        priority: 优先级 (数字越小越优先)
        enabled: 是否启用
        condition: 条件函数 (PolicyContext) -> bool
        reason_template: 触发原因模板
        action_types: 适用的动作类型 (空 = 全部)
    """
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    severity: RuleSeverity = RuleSeverity.MEDIUM
    priority: int = 50
    enabled: bool = True
    condition: Callable[[PolicyContext], bool] | None = None
    reason_template: str = ""
    action_types: list[str] = field(default_factory=list)

    def evaluate(self, context: PolicyContext) -> RuleResult:
        """评估规则.

        Args:
            context: 策略上下文

        Returns:
            RuleResult: 评估结果
        """
        if not self.enabled:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                triggered=False,
                decision=PolicyDecision.ALLOW,
                severity=self.severity,
            )

        # 检查动作类型
        if self.action_types and context.action_type not in self.action_types:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                triggered=False,
                decision=PolicyDecision.ALLOW,
                severity=self.severity,
            )

        # 检查条件
        triggered = False
        if self.condition:
            try:
                triggered = self.condition(context)
            except Exception:
                triggered = False

        if not triggered:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                triggered=False,
                decision=PolicyDecision.ALLOW,
                severity=self.severity,
            )

        decision = SEVERITY_TO_DECISION.get(self.severity, PolicyDecision.WARN)
        reason = self.reason_template
        # 支持简单模板替换
        for key in ["budget_change_ratio", "daily_spend_limit", "confidence", "max_creative_per_day"]:
            placeholder = "{" + key + "}"
            if placeholder in reason:
                value = getattr(context, key, "")
                if isinstance(value, float):
                    value = f"{value:.1%}" if key.endswith("ratio") else f"{value:.1f}"
                reason = reason.replace(placeholder, str(value))

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            triggered=True,
            decision=decision,
            reason=reason,
            severity=self.severity,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "priority": self.priority,
            "enabled": self.enabled,
            "action_types": self.action_types,
        }


# ═══════════════════════════════════════════════════════════════
# Approval Request
# ═══════════════════════════════════════════════════════════════


@dataclass
class ApprovalRequest:
    """审批请求.

    Attributes:
        request_id: 请求 ID
        action_type: 动作类型
        action_params: 动作参数
        reason: 审批原因
        context: 策略上下文
        status: 审批状态
        created_at: 创建时间
        expires_at: 过期时间
        resolved_at: 决议时间
        resolver: 审批人
        resolution_note: 审批备注
    """
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""
    action_params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    context: PolicyContext | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""
    resolved_at: str = ""
    resolver: str = ""
    resolution_note: str = ""

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc).isoformat() > self.expires_at

    def approve(self, resolver: str = "", note: str = "") -> None:
        """批准."""
        self.status = ApprovalStatus.APPROVED
        self.resolved_at = datetime.now(timezone.utc).isoformat()
        self.resolver = resolver
        self.resolution_note = note

    def reject(self, resolver: str = "", note: str = "") -> None:
        """拒绝."""
        self.status = ApprovalStatus.REJECTED
        self.resolved_at = datetime.now(timezone.utc).isoformat()
        self.resolver = resolver
        self.resolution_note = note

    def cancel(self) -> None:
        """取消."""
        self.status = ApprovalStatus.CANCELLED
        self.resolved_at = datetime.now(timezone.utc).isoformat()

    def expire(self) -> None:
        """过期."""
        self.status = ApprovalStatus.EXPIRED
        self.resolved_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "reason": self.reason,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "resolved_at": self.resolved_at,
            "resolver": self.resolver,
            "resolution_note": self.resolution_note,
            "is_expired": self.is_expired,
        }


def most_severe_decision(decisions: list[PolicyDecision]) -> PolicyDecision:
    """取最严格的决策."""
    if not decisions:
        return PolicyDecision.ALLOW
    return max(decisions, key=lambda d: DECISION_SEVERITY.get(d, 0))