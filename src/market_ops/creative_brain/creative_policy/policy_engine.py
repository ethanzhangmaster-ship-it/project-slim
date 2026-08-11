"""V4.3 Policy Engine — the autonomous decision brain.

This is the final output of the entire Creative Brain pipeline.

Input:
  - Reasoning (V4.2): confidence, evidence, predicted decisions
  - Validation (V4.2.1): accuracy, calibration, error analysis
  - Trend data: growing/stable/declining/dead
  - Budget: available per country/platform
  - Country/Platform context

Output:
  - GENERATE / DONT_GENERATE / RETEST / ADAPT / KILL

Dependency injection: Reasoning and Validation engines are injected,
not imported directly. This enables:
  - Loose coupling
  - Easy testing with mock engines
  - Policy versioning and A/B comparison
  - Rollback to previous policy versions
"""

from __future__ import annotations

from typing import Any

from .schemas import (
    DecisionPolicy, PolicyAction, CreativeTask, RiskScore,
    DailyProductionPlan, Portfolio, BudgetAllocation, DecisionLog,
    PortfolioCategory,
)
from .policy_rules import PolicyRules
from .risk_controller import RiskController
from .creative_priority import CreativePriority
from .decision_logger import DecisionLogger


class PolicyEngine:
    """Autonomous decision engine for creative production.

    Architecture:
      Reasoning → Rules → Risk Override → Priority → Decision

    All external dependencies are injected:
      - reasoning_engine: V4.2 Creative Reasoning Engine
      - validation_engine: V4.2.1 Validation Engine
    """

    def __init__(self, reasoning_engine=None,
                 validation_engine=None,
                 policy: DecisionPolicy | None = None) -> None:
        # Injected dependencies
        self._reasoning = reasoning_engine
        self._validation = validation_engine

        # Policy configuration
        self._policy = policy or DecisionPolicy()

        # Internal components
        self._rules = PolicyRules()
        self._risk = RiskController()
        self._priority = CreativePriority()
        self._logger = DecisionLogger()

        # Policy version history (for rollback)
        self._policy_history: list[DecisionPolicy] = [self._policy]
        self._current_version_idx: int = 0

    # ── Main Decision Pipeline ──

    def decide(self, creative_data: dict[str, Any]) -> CreativeTask:
        """Make a decision for a single creative.

        Pipeline:
          1. Evaluate rules → PolicyAction
          2. Assess risk → RiskScore
          3. Risk override → final action
          4. Compute priority → PriorityScore
          5. Log decision
          6. Return CreativeTask

        Args:
            creative_data: Dict with keys:
                creative_id, dna, reasoning_confidence, validation_accuracy,
                trend_status, roi_prediction, budget, country, platform.

        Returns:
            CreativeTask with action, priority, risk, and evidence.
        """
        creative_id = creative_data.get("creative_id", "unknown")
        country = creative_data.get("country", "")
        trend = creative_data.get("trend_status", "stable")
        budget = creative_data.get("budget", 100.0)

        # 1. Evaluate rules
        action, evidence = self._rules.evaluate(creative_data, self._policy)

        # 2. Assess risk
        risk = self._risk.assess_risk(
            creative_id=creative_id,
            country=country,
            trend=trend,
            budget=budget,
            policy=self._policy,
        )

        # 3. Risk override
        final_action, overridden, override_reason = \
            self._risk.override_decision(action, risk)

        # 4. Compute priority
        priority = self._priority.compute(
            creative_id=creative_id,
            dna=creative_data.get("dna", {}),
            roi_prediction=creative_data.get("roi_prediction", 0.5),
            trend_status=trend,
            reasoning_confidence=creative_data.get("reasoning_confidence", 0.5),
            budget=budget,
            country=country,
            platform=creative_data.get("platform", "facebook"),
        )

        # 5. Log decision
        self._logger.log(
            creative_id=creative_id,
            action=final_action,
            reason=evidence.get("reason", ""),
            evidence=evidence,
            policy_version=self._policy.version,
            overridden_by_risk=overridden,
            overridden_reason=override_reason,
        )

        # 6. Build task
        return CreativeTask(
            creative_id=creative_id,
            dna=creative_data.get("dna", {}),
            priority=priority,
            action=final_action,
            country=country,
            platform=creative_data.get("platform", "facebook"),
            budget=budget,
            reasoning_confidence=creative_data.get("reasoning_confidence", 0.5),
            validation_accuracy=creative_data.get("validation_accuracy", 0.5),
            trend_status=trend,
            roi_prediction=creative_data.get("roi_prediction", 0.5),
            risk=risk,
            status="queued",
        )

    def decide_batch(self, creatives: list[dict[str, Any]]) -> list[CreativeTask]:
        """Decide for a batch of creatives.

        Returns tasks sorted by priority (highest first).
        """
        tasks = [self.decide(c) for c in creatives]
        # Sort by priority descending
        tasks.sort(key=lambda t: -t.priority.total_score)
        return tasks

    # ── Policy Management ──

    def update_policy(self, new_policy: DecisionPolicy) -> None:
        """Update to a new policy version (with history tracking)."""
        new_policy.previous_version = self._policy.version
        self._policy_history.append(new_policy)
        self._current_version_idx = len(self._policy_history) - 1
        self._policy = new_policy

    def rollback_policy(self) -> DecisionPolicy | None:
        """Rollback to the previous policy version.

        Returns:
            The restored policy, or None if no previous version.
        """
        if self._current_version_idx > 0:
            self._current_version_idx -= 1
            self._policy = self._policy_history[self._current_version_idx]
            return self._policy
        return None

    def compare_policies(self, version_a: str,
                         version_b: str) -> dict[str, Any]:
        """Compare two policy versions."""
        pol_a = None
        pol_b = None
        for p in self._policy_history:
            if p.version == version_a:
                pol_a = p
            if p.version == version_b:
                pol_b = p

        if not pol_a or not pol_b:
            return {"error": "Policy version not found"}

        return {
            "version_a": version_a,
            "version_b": version_b,
            "threshold_diff": {
                "confidence_go": pol_b.confidence_threshold_go - pol_a.confidence_threshold_go,
                "roi_go": pol_b.roi_threshold_go - pol_a.roi_threshold_go,
                "trend_growing_bonus": pol_b.trend_growing_bonus - pol_a.trend_growing_bonus,
            },
            "explore_ratio_diff": pol_b.default_explore_ratio - pol_a.default_explore_ratio,
        }

    # ── Accessors ──

    @property
    def policy(self) -> DecisionPolicy:
        return self._policy

    @property
    def risk_controller(self) -> RiskController:
        return self._risk

    @property
    def logger(self) -> DecisionLogger:
        return self._logger

    @property
    def policy_history(self) -> list[DecisionPolicy]:
        return list(self._policy_history)

    # ── Reporting ──

    def get_daily_summary(self) -> dict[str, Any]:
        """Get today's decision summary."""
        log_summary = self._logger.get_daily_summary()
        risk_summary = self._risk.get_risk_summary()
        return {
            "policy_version": self._policy.version,
            "decisions": log_summary,
            "risk": risk_summary,
        }