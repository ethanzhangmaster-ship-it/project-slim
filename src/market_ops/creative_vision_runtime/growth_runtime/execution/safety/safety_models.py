"""E13.6.4 Safety Models — 安全层数据模型.

定义安全决策、风险类别、安全规则、评估结果和审批请求等核心模型。

核心模型:
  - SafetyDecision: 安全决策枚举 (ALLOW/WARN/BLOCK/REQUIRE_APPROVAL)
  - RiskCategory: 风险类别枚举 (BUDGET/CREATIVE/CAMPAIGN/ROLLBACK)
  - SafetyRule: 单条安全规则 (条件 + 动作)
  - SafetyEvaluation: 安全评估结果
  - ApprovalRequest: 审批请求 (状态 + 工作流)

连接:
  E13.6.4 SafetyEngine → SafetyRule → SafetyEvaluation → ExecutionContext
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


class SafetyDecision(str, Enum):
    """安全决策 — 安全评估后的四种结果.

    | ALLOW             | 允许执行, 无限制           |
    | WARN              | 允许执行, 但记录警告        |
    | BLOCK             | 禁止执行, 直接拒绝          |
    | REQUIRE_APPROVAL  | 需要人工审批后才能执行       |
    """
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


class RiskCategory(str, Enum):
    """风险类别 — 按动作类型和影响范围分类.

    | BUDGET_SCALE       | 预算放量操作           |
    | BUDGET_REDUCE      | 预算缩减操作           |
    | CREATIVE_MUTATION  | 素材变异操作           |
    | CAMPAIGN_PAUSE     | 暂停广告系列           |
    | CAMPAIGN_CREATE    | 创建新广告系列          |
    | CAMPAIGN_FREEZE    | 冻结广告系列           |
    | ROLLBACK           | 回滚操作              |
    | GENERAL            | 通用操作              |
    """
    BUDGET_SCALE = "budget_scale"
    BUDGET_REDUCE = "budget_reduce"
    CREATIVE_MUTATION = "creative_mutation"
    CAMPAIGN_PAUSE = "campaign_pause"
    CAMPAIGN_CREATE = "campaign_create"
    CAMPAIGN_FREEZE = "campaign_freeze"
    ROLLBACK = "rollback"
    GENERAL = "general"


class ApprovalStatus(str, Enum):
    """审批状态 — 审批请求的生命周期.

    | PENDING   | 等待审批   |
    | APPROVED  | 已批准     |
    | DENIED    | 已拒绝     |
    | EXPIRED   | 已过期     |
    | CANCELLED | 已取消     |
    """
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RuleSeverity(str, Enum):
    """规则严重程度 — 影响安全决策的优先级.

    | CRITICAL | 致命: 违反即 BLOCK         |
    | HIGH     | 高危: 违反即 REQUIRE_APPROVAL |
    | MEDIUM   | 中危: 违反即 WARN           |
    | LOW      | 低危: 违反仅记录             |
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ═══════════════════════════════════════════════════════════════
# Safety Rule
# ═══════════════════════════════════════════════════════════════


@dataclass
class SafetyRule:
    """安全规则 — 定义单条安全检查规则.

    Attributes:
        rule_id: 规则唯一标识
        name: 规则名称
        description: 规则描述
        category: 风险类别
        severity: 严重程度
        condition: 条件函数 (action, context) -> bool
        decision: 违反时的安全决策 (静态)
        decision_fn: 动态决策函数 (action, context) -> SafetyDecision (优先级高于 decision)
        reason_fn: 动态原因函数 (action, context) -> str (优先级高于 reason_template)
        reason_template: 违反时的原因模板
        enabled: 是否启用
        priority: 规则优先级 (数字越小越优先)
        metadata: 扩展元数据
    """
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: RiskCategory = RiskCategory.GENERAL
    severity: RuleSeverity = RuleSeverity.MEDIUM
    condition: Callable[..., bool] | None = None
    decision: SafetyDecision = SafetyDecision.WARN
    decision_fn: Callable[..., SafetyDecision] | None = None
    reason_fn: Callable[..., str] | None = None
    reason_template: str = ""
    enabled: bool = True
    priority: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)

    def evaluate(self, action: Any, context: Any) -> tuple[bool, str, SafetyDecision]:
        """评估规则条件.

        Returns:
            (triggered, reason, decision): 是否触发 + 原因描述 + 安全决策
        """
        if not self.enabled or self.condition is None:
            return False, "", SafetyDecision.ALLOW

        try:
            triggered = self.condition(action, context)
            if triggered:
                # 动态决策优先
                decision = self.decision
                if self.decision_fn is not None:
                    decision = self.decision_fn(action, context)
                # 动态原因优先
                reason = self.reason_template
                if self.reason_fn is not None:
                    reason = self.reason_fn(action, context)
                return True, reason, decision
            return False, "", SafetyDecision.ALLOW
        except Exception:
            return False, "", SafetyDecision.ALLOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "severity": self.severity.value,
            "decision": self.decision.value,
            "reason_template": self.reason_template,
            "enabled": self.enabled,
            "priority": self.priority,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Safety Evaluation
# ═══════════════════════════════════════════════════════════════


@dataclass
class RuleResult:
    """单条规则评估结果.

    Attributes:
        rule_id: 规则 ID
        rule_name: 规则名称
        triggered: 是否触发
        decision: 安全决策
        reason: 触发原因
    """
    rule_id: str = ""
    rule_name: str = ""
    triggered: bool = False
    decision: SafetyDecision = SafetyDecision.ALLOW
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "triggered": self.triggered,
            "decision": self.decision.value,
            "reason": self.reason,
        }


@dataclass
class SafetyEvaluation:
    """安全评估结果 — 对单个动作的综合安全评估.

    Attributes:
        evaluation_id: 评估唯一标识
        action_id: 关联的动作 ID
        action_type: 动作类型
        decision: 最终安全决策 (取最严格的规则结果)
        risk_score: 综合风险评分 [0, 1]
        rule_results: 各规则评估结果
        triggered_rules: 触发的规则名称列表
        reasons: 触发原因列表
        requires_approval: 是否需要审批
        is_blocked: 是否被阻止
        warnings: 警告信息列表
        evaluated_at: 评估时间
        metadata: 扩展元数据
    """
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: str = ""
    decision: SafetyDecision = SafetyDecision.ALLOW
    risk_score: float = 0.0
    rule_results: list[RuleResult] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    requires_approval: bool = False
    is_blocked: bool = False
    warnings: list[str] = field(default_factory=list)
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.decision == SafetyDecision.ALLOW

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def triggered_count(self) -> int:
        return len(self.triggered_rules)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "decision": self.decision.value,
            "risk_score": self.risk_score,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "triggered_rules": self.triggered_rules,
            "reasons": self.reasons,
            "requires_approval": self.requires_approval,
            "is_blocked": self.is_blocked,
            "warnings": self.warnings,
            "evaluated_at": self.evaluated_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Approval Request
# ═══════════════════════════════════════════════════════════════


@dataclass
class ApprovalRequest:
    """审批请求 — 需要人工审批的操作请求.

    Attributes:
        request_id: 请求唯一标识
        action_id: 关联的动作 ID
        action_type: 动作类型
        risk_score: 风险评分
        reason: 审批原因
        status: 审批状态
        approved_by: 审批人
        approved_at: 审批时间
        expires_at: 过期时间
        notes: 审批备注
        metadata: 扩展元数据
    """
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: str = ""
    risk_score: float = 0.0
    reason: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str = ""
    approved_at: str = ""
    expires_at: str = ""
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pending(self) -> bool:
        return self.status == ApprovalStatus.PENDING

    @property
    def is_approved(self) -> bool:
        return self.status == ApprovalStatus.APPROVED

    @property
    def is_denied(self) -> bool:
        return self.status == ApprovalStatus.DENIED

    @property
    def is_expired(self) -> bool:
        if self.status == ApprovalStatus.EXPIRED:
            return True
        if self.expires_at and self.status == ApprovalStatus.PENDING:
            try:
                expire_time = datetime.fromisoformat(self.expires_at)
                return datetime.now(timezone.utc) > expire_time
            except (ValueError, TypeError):
                return False
        return False

    def approve(self, approved_by: str = "", notes: str = "") -> None:
        self.status = ApprovalStatus.APPROVED
        self.approved_by = approved_by
        self.approved_at = datetime.now(timezone.utc).isoformat()
        if notes:
            self.notes = notes

    def deny(self, approved_by: str = "", notes: str = "") -> None:
        self.status = ApprovalStatus.DENIED
        self.approved_by = approved_by
        self.approved_at = datetime.now(timezone.utc).isoformat()
        if notes:
            self.notes = notes

    def cancel(self) -> None:
        self.status = ApprovalStatus.CANCELLED

    def expire(self) -> None:
        self.status = ApprovalStatus.EXPIRED

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "risk_score": self.risk_score,
            "reason": self.reason,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "expires_at": self.expires_at,
            "notes": self.notes,
            "metadata": self.metadata,
        }