"""E12.6.3 — Safety Governor。

Governance Layer — AI Growth System 的安全驾驶员。

模块:
  - models:             SafetyAction, RiskLevel, SafetyContext, SafetyDecision, RollbackRecord
  - risk_detector:      风险评估引擎（5 维风险 + 总评分）
  - safety_policy:      5 条安全治理规则
  - rollback_manager:   创意/预算/策略回滚管理
  - safety_governor:    核心安全控制器
"""

from .models import (
    RiskLevel,
    RiskReport,
    RollbackRecord,
    SafetyAction,
    SafetyContext,
    SafetyDecision,
    get_risk_threshold,
    get_safety_action_priority,
    risk_level_from_score,
)
from .risk_detector import RiskDetector
from .safety_policy import (
    DEFAULT_SAFETY_POLICIES,
    HighMutationPolicy,
    InsufficientDataPolicy,
    LargeSpendPolicy,
    PopulationCollapsePolicy,
    SafetyPolicy,
    WinnerProtectionPolicy,
)
from .rollback_manager import RollbackManager
from .safety_governor import SafetyGovernor

__all__ = [
    # Models
    "SafetyAction",
    "RiskLevel",
    "SafetyContext",
    "SafetyDecision",
    "RiskReport",
    "RollbackRecord",
    "get_safety_action_priority",
    "risk_level_from_score",
    "get_risk_threshold",
    # Risk Detector
    "RiskDetector",
    # Policies
    "SafetyPolicy",
    "HighMutationPolicy",
    "LargeSpendPolicy",
    "InsufficientDataPolicy",
    "WinnerProtectionPolicy",
    "PopulationCollapsePolicy",
    "DEFAULT_SAFETY_POLICIES",
    # Rollback
    "RollbackManager",
    # Governor
    "SafetyGovernor",
]