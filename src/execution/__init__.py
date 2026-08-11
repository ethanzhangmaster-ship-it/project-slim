"""P2.1 Execution Contract Layer（AI CEO 的「手部接口」）。

把 E17.3 GrowthDecision 的「决策语言」转成 P2 Execution Layer 的「动作合同」。
本层不执行任何真实 API；真实执行由 P2.2 Provider Layer 承接。
"""
from __future__ import annotations

from .contracts import ExecutionContract, build_contract
from .intent import (
    LOW_RISK_THRESHOLD,
    MID_RISK_THRESHOLD,
    build_intent,
    describe,
    intent_summary_dict,
    risk_band,
)
from .mapper import (
    DecisionToIntentMapper,
    UnmappedDecisionAction,
    normalize_action,
)
from .models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    ExecutionMode,
    ExecutionRequest,
    action_label,
    domain_label,
)
from .registry import Capability, CapabilityRegistry, Permission
from .validator import (
    ExecutionContractValidator,
    ValidationResult,
    ValidationStatus,
)

__all__ = [
    # models
    "ExecutionDomain",
    "ExecutionAction",
    "ExecutionMode",
    "ExecutionIntent",
    "ExecutionRequest",
    "action_label",
    "domain_label",
    # intent
    "LOW_RISK_THRESHOLD",
    "MID_RISK_THRESHOLD",
    "risk_band",
    "build_intent",
    "describe",
    "intent_summary_dict",
    # mapper
    "DecisionToIntentMapper",
    "UnmappedDecisionAction",
    "normalize_action",
    # registry
    "Permission",
    "Capability",
    "CapabilityRegistry",
    # validator
    "ValidationStatus",
    "ValidationResult",
    "ExecutionContractValidator",
    # contracts
    "ExecutionContract",
    "build_contract",
]
