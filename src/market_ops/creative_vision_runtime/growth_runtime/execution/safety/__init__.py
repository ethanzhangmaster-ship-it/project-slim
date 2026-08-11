"""E13.6.4 Safety Controller — 安全控制层.

在 Execution Engine 之前注入安全校验，实现 ALLOW/WARN/BLOCK/REQUIRE_APPROVAL
四级决策，为 Autonomous Growth Runtime 提供可控、可审计的安全保障。

模块结构:
  - safety_models: 安全模型 (SafetyDecision, SafetyRule, SafetyEvaluation, etc.)
  - safety_rules: 内置安全规则 (预算、素材、暂停、回滚)
  - safety_policy: 策略管理 (SafetyPolicy, Default/Conservative/Aggressive)
  - approval_manager: 审批工作流管理
  - safety_engine: 安全评估引擎核心

连接:
  E13.6.4 SafetyEngine → ExecutionContext → E13.6.3 ExecutionEngine
"""

from .safety_models import (
    ApprovalRequest,
    ApprovalStatus,
    RiskCategory,
    RuleResult,
    RuleSeverity,
    SafetyDecision,
    SafetyEvaluation,
    SafetyRule,
)
from .safety_rules import (
    budget_reduce_rule,
    budget_scale_rule,
    campaign_create_rule,
    campaign_freeze_rule,
    campaign_pause_rule,
    creative_mutation_safety_rule,
    daily_budget_cap_rule,
    get_rules_for_action_type,
    rollback_protection_rule,
)
from .safety_policy import (
    SafetyPolicy,
    create_aggressive_policy,
    create_conservative_policy,
    create_default_policy,
)
from .approval_manager import ApprovalManager
from .safety_engine import SafetyEngine

__all__ = [
    # ── Models ──
    "SafetyDecision",
    "RiskCategory",
    "ApprovalStatus",
    "RuleSeverity",
    "SafetyRule",
    "RuleResult",
    "SafetyEvaluation",
    "ApprovalRequest",
    # ── Rules ──
    "budget_scale_rule",
    "budget_reduce_rule",
    "daily_budget_cap_rule",
    "creative_mutation_safety_rule",
    "campaign_pause_rule",
    "campaign_freeze_rule",
    "campaign_create_rule",
    "rollback_protection_rule",
    "get_rules_for_action_type",
    # ── Policy ──
    "SafetyPolicy",
    "create_default_policy",
    "create_aggressive_policy",
    "create_conservative_policy",
    # ── Approval ──
    "ApprovalManager",
    # ── Engine ──
    "SafetyEngine",
]