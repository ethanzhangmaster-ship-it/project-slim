"""E13.7.4.2 Agent Policy System — 安全边界层.

Agent Policy 在 Agent Decision 和 Execution Engine 之间建立安全边界:
    Agent Decision → PolicyEngine → ALLOW/WARN/BLOCK/REQUIRE_APPROVAL → Execution Engine

模块:
  - policy_models: 核心数据模型 (PolicyDecision, PolicyContext, RiskRule, etc.)
  - policy_engine: 策略引擎 (PolicyEngine, 规则聚合与决策)
  - risk_rules: 风险规则集 (12 条默认规则)
  - approval_manager: 审批管理器 (ApprovalManager, 审批生命周期)
  - policy_templates: 预设模板 (Conservative/Balanced/Aggressive)

与 E13.6.4 Safety Controller 的关系:
  Agent Policy (本层) → 决定 Agent 能不能提出/执行这个动作
  Safety Controller (E13.6.4) → 决定这个动作执行时是否安全
"""

from .policy_models import (
    # Enums
    PolicyDecision,
    PolicyActionType,
    RuleSeverity,
    ApprovalStatus,
    # Data
    PolicyContext,
    PolicyResult,
    RuleResult,
    RiskRule,
    ApprovalRequest,
    # Helpers
    SEVERITY_TO_DECISION,
    DECISION_SEVERITY,
    most_severe_decision,
)

from .risk_rules import (
    build_default_rules,
    build_custom_budget_rule,
)

from .policy_engine import (
    PolicyEngine,
    EngineStats,
    create_policy_engine,
)

from .approval_manager import (
    ApprovalManager,
    ApprovalRecord,
    create_approval_manager,
)

from .policy_templates import (
    PolicyTemplate,
    CONSERVATIVE,
    BALANCED,
    AGGRESSIVE,
    TEMPLATES,
    get_template,
    list_templates,
)

__all__ = [
    # Enums
    "PolicyDecision",
    "PolicyActionType",
    "RuleSeverity",
    "ApprovalStatus",
    # Models
    "PolicyContext",
    "PolicyResult",
    "RuleResult",
    "RiskRule",
    "ApprovalRequest",
    # Helpers
    "SEVERITY_TO_DECISION",
    "DECISION_SEVERITY",
    "most_severe_decision",
    # Rules
    "build_default_rules",
    "build_custom_budget_rule",
    # Engine
    "PolicyEngine",
    "EngineStats",
    "create_policy_engine",
    # Approval
    "ApprovalManager",
    "ApprovalRecord",
    "create_approval_manager",
    # Templates
    "PolicyTemplate",
    "CONSERVATIVE",
    "BALANCED",
    "AGGRESSIVE",
    "TEMPLATES",
    "get_template",
    "list_templates",
]