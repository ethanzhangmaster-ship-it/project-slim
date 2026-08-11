"""EP0.11.4 — FlowAuditor: wire the central AuditTrail into real agent flows.

Three production flows are covered with semantic helpers:

  Release flow : decision -> approval -> release_action -> result
  Growth flow  : opportunity -> decision -> execution -> reward
  ASO flow     : insight -> plan -> approval -> experiment -> result

Design rules (Lean):
  * FlowAuditor wraps an ``AuditTrail``. When constructed with
    ``trail=None`` every method is a silent no-op, so agents can accept an
    optional auditor without changing any existing behaviour or test.
  * Deterministic, append-only JSONL via AuditTrail (data/audit/*.jsonl).
  * Agents never import each other through this module — it only depends
    on audit/trail.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from audit.trail import (
    ApprovalRecord,
    AuditTrail,
    DecisionRecord,
    ExecutionRecord,
)


class FlowAuditor:
    """Semantic audit helpers for the three production flows."""

    def __init__(self, trail: Optional[AuditTrail] = None):
        self.trail = trail

    @property
    def enabled(self) -> bool:
        return self.trail is not None

    # ------------------------------------------------------------------ #
    # generic primitives
    # ------------------------------------------------------------------ #
    def decision(
        self,
        agent: str,
        action: str,
        game_id: str,
        reason: str,
        confidence: float = 1.0,
        inputs: Optional[Dict[str, Any]] = None,
        decision_id: Optional[str] = None,
    ) -> str:
        """Record a decision; returns its decision_id (usable for follow-ups)."""
        did = decision_id or str(uuid4())
        if self.trail is not None:
            self.trail.record_decision(
                DecisionRecord(
                    agent=agent,
                    action=action,
                    game_id=game_id,
                    reason=reason,
                    confidence=float(confidence),
                    decision_id=did,
                    inputs=inputs or {},
                )
            )
        return did

    def approval(
        self,
        decision_id: str,
        approver: str,
        approved: bool,
        reason: str = "",
    ) -> None:
        if self.trail is not None:
            self.trail.record_approval(
                ApprovalRecord(
                    decision_id=decision_id,
                    approver=approver,
                    approved=approved,
                    reason=reason,
                )
            )

    def execution(
        self,
        decision_id: str,
        agent: str,
        action: str,
        success: bool,
        duration_ms: float = 0.0,
        error: str = "",
    ) -> None:
        if self.trail is not None:
            self.trail.record_execution(
                ExecutionRecord(
                    decision_id=decision_id,
                    agent=agent,
                    action=action,
                    success=success,
                    duration_ms=float(duration_ms),
                    error=error,
                )
            )

    # ------------------------------------------------------------------ #
    # Release flow: decision -> approval -> release_action -> result
    # ------------------------------------------------------------------ #
    def release_decision(
        self,
        package: str,
        recommendation: str,
        reason: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self.decision(
            agent="release_agent",
            action=f"release:{recommendation}",
            game_id=package,
            reason=reason,
            confidence=1.0,
            inputs=inputs,
        )

    def release_result(
        self,
        decision_id: str,
        package: str,
        op: str,
        ok: bool,
        real_api_called: bool,
        detail: str = "",
    ) -> None:
        self.execution(
            decision_id=decision_id,
            agent="release_agent",
            action=f"{op}({package}, real_api={real_api_called})",
            success=ok,
            error="" if ok else detail,
        )

    # ------------------------------------------------------------------ #
    # Growth flow: opportunity -> decision -> execution -> reward
    # ------------------------------------------------------------------ #
    def growth_opportunity(
        self,
        game_id: str,
        opportunity_type: str,
        priority: float,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self.decision(
            agent="growth_loop",
            action=f"opportunity:{opportunity_type}",
            game_id=game_id,
            reason=f"opportunity detected (priority={priority:.3f})",
            confidence=min(1.0, max(0.0, priority)),
            inputs=evidence,
        )

    def growth_plan_gated(
        self,
        decision_id: str,
        game_id: str,
        plan_title: str,
        approval_route: str,
        auto_approved: bool,
    ) -> None:
        self.approval(
            decision_id=decision_id,
            approver=f"policy_gate:{approval_route}",
            approved=auto_approved,
            reason=plan_title,
        )

    def growth_experiment(
        self,
        decision_id: str,
        game_id: str,
        plan_title: str,
        created: bool,
    ) -> None:
        self.execution(
            decision_id=decision_id,
            agent="growth_loop",
            action=f"experiment:{plan_title}",
            success=created,
            error="" if created else "experiment not created (gated/duplicate)",
        )

    def growth_reward(
        self,
        game_id: str,
        experiment_id: str,
        reward: float,
        detail: str = "",
    ) -> None:
        did = self.decision(
            agent="growth_loop",
            action="reward",
            game_id=game_id,
            reason=detail or f"revenue feedback for {experiment_id}",
            confidence=1.0,
            inputs={"experiment_id": experiment_id, "reward": reward},
        )
        self.execution(
            decision_id=did,
            agent="growth_loop",
            action=f"reward:{experiment_id}",
            success=True,
        )

    # ------------------------------------------------------------------ #
    # ASO flow: insight -> plan -> approval -> experiment -> result
    # ------------------------------------------------------------------ #
    def aso_insight(
        self,
        game_id: str,
        insight_type: str,
        description: str,
        impact_score: float,
    ) -> str:
        return self.decision(
            agent="aso_intelligence",
            action=f"insight:{insight_type}",
            game_id=game_id,
            reason=description,
            confidence=min(1.0, max(0.0, impact_score)),
        )

    def aso_gated_action(
        self,
        game_id: str,
        action: str,
        approval_route: str,
        executed: bool,
        queued: bool,
        reason: str = "",
        confidence: float = 1.0,
    ) -> str:
        """One DecisionValidator outcome: plan + approval + result in one go."""
        did = self.decision(
            agent="aso_intelligence",
            action=f"aso:{action}",
            game_id=game_id,
            reason=reason,
            confidence=confidence,
        )
        self.approval(
            decision_id=did,
            approver=f"decision_validator:{approval_route}",
            approved=executed or queued,
            reason=approval_route,
        )
        self.execution(
            decision_id=did,
            agent="aso_intelligence",
            action=f"aso:{action}",
            success=executed,
            error="" if executed else f"routed to {approval_route}",
        )
        return did


__all__ = ["FlowAuditor"]
