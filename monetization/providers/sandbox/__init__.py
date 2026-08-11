"""
E14.3.4 — Provider Sandbox (public surface)
============================================

Upgrades simulation / shadow / production from "interface exists" into a
complete operating strategy:

    SandboxManager     — per game+provider policy, promotion ladder, demotion
    ShadowTracker      — prediction vs reality for shadow proposals
    CanaryController   — staged production rollout with per-stage gates
    RollbackGate       — auto rollback on post-execution metric breach
    HealthScorer       — rolling 0-100 provider health scoring
"""
from monetization.providers.sandbox.canary import CanaryController
from monetization.providers.sandbox.health_score import (
    DEGRADED_MIN, HEALTHY_MIN, HealthScorer, HealthSnapshot,
    STATUS_DEGRADED, STATUS_HEALTHY, STATUS_UNHEALTHY, status_for,
)
from monetization.providers.sandbox.rollback_gate import GuardedChange, RollbackGate
from monetization.providers.sandbox.sandbox_manager import SandboxManager
from monetization.providers.sandbox.sandbox_models import (
    CANARY_FAILED, CANARY_PASSED, CANARY_PENDING, CANARY_ROLLED_BACK,
    CANARY_RUNNING, CanaryRun, CanaryStage, DEFAULT_CANARY_STAGES,
    GATE_HOLD, GATE_ROLLBACK, GateDecision, PROMOTION_LADDER,
    SandboxPolicy, SHADOW_CLOSED, SHADOW_OPEN, ShadowRecord,
)
from monetization.providers.sandbox.shadow_tracker import ShadowTracker

__all__ = [
    "SandboxManager", "ShadowTracker", "CanaryController",
    "RollbackGate", "GuardedChange", "HealthScorer", "HealthSnapshot",
    "status_for", "STATUS_HEALTHY", "STATUS_DEGRADED", "STATUS_UNHEALTHY",
    "HEALTHY_MIN", "DEGRADED_MIN",
    "ShadowRecord", "SHADOW_OPEN", "SHADOW_CLOSED",
    "CanaryRun", "CanaryStage", "DEFAULT_CANARY_STAGES",
    "CANARY_PENDING", "CANARY_RUNNING", "CANARY_PASSED",
    "CANARY_FAILED", "CANARY_ROLLED_BACK",
    "GateDecision", "GATE_HOLD", "GATE_ROLLBACK",
    "SandboxPolicy", "PROMOTION_LADDER",
]
