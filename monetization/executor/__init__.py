"""
E13.3.3 — Autonomous Monetization Executor (Controlled Execution Layer)
=======================================================================

The ONLY component in the E13.3 chain permitted to turn a simulated Decision
into a concrete config change — and it is gated, reversible, and (in v1)
fully mocked:

    StrategyDecision (simulated)
          |  (1) Decision Validation
          v
    Approval Gate            -> rejected | manual_review | approved
          |  (2) Config Mutator  (dry Change records, no side effects)
          v
    Provider.apply()  x N    -> MOCK: MAX / LevelPlay / RemoteConfig
          |  (3) on any failure -> rollback all applied
          v
    ExecutionResult          -> executed | rolled_back | failed | rejected | pending

Hard constraints:
  * NO real ad-platform API call in v1. Every provider response certifies
    `real_api_called: false`.
  * A Decision is NEVER executed directly from an Opportunity. The Approval
    Gate is mandatory:  Opportunity -> MAX API  is forbidden.
  * Rollback is mandatory on the first provider failure.

Usage:
    from monetization.executor import ExecutionOrchestrator
    orch = ExecutionOrchestrator()
    result = orch.execute_decision(strategy_decision_dict)   # from E13.3.2
"""
from monetization.executor.models import (
    EXEC_APPROVED, EXEC_EXECUTED, EXEC_FAILED, EXEC_PENDING, EXEC_REJECTED,
    EXEC_ROLLED_BACK, GATE_APPROVED, GATE_MANUAL_REVIEW, GATE_REJECTED,
    Change, ExecutionRequest, ExecutionResult, RollbackOperation,
)
from monetization.executor.approval_gate import ApprovalGate
from monetization.executor.config_mutator import ConfigMutator
from monetization.executor.executor import ExecutionOrchestrator
from monetization.executor.providers import (
    LevelPlayProvider, MaxProvider, MonetizationProvider, RemoteConfigProvider,
)

__all__ = [
    # statuses / verdicts
    "EXEC_APPROVED", "EXEC_EXECUTED", "EXEC_FAILED", "EXEC_PENDING",
    "EXEC_REJECTED", "EXEC_ROLLED_BACK",
    "GATE_APPROVED", "GATE_MANUAL_REVIEW", "GATE_REJECTED",
    # models
    "Change", "ExecutionRequest", "ExecutionResult", "RollbackOperation",
    # engines
    "ApprovalGate", "ConfigMutator", "ExecutionOrchestrator",
    # providers
    "MonetizationProvider", "MaxProvider", "LevelPlayProvider", "RemoteConfigProvider",
]
