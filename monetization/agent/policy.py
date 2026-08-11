"""
E13.4.4 — Module 3: Policy Engine (the agent's brain)
======================================================

Turns the fused signals into one of four discrete moves:

    observe     — watch only, no change (mild / uncertain)
    experiment  — create an A/B test, do NOT execute (unknown strategy)
    execute     — apply the change via the Executor (known + safe + confident)
    block       — forbid the action (high risk / retention-harmful)

Decision precedence (highest first):
    1. high retention risk OR retention-damaging -> BLOCK
    2. introduced strategy on a *novel* (strategy, segment) -> EXPERIMENT
       (never execute something we have no history for, on a fresh segment)
    3. known inventory strategy on a novel segment
         - known-good + severe -> EXECUTE (trusted + urgent)
         - otherwise           -> OBSERVE
    4. established (strategy, segment): severe + confident + positive -> EXECUTE
    5. otherwise -> OBSERVE

This is the user's state machine:
    Analyze -> { Known Strategy -> Execute | Unknown -> Experiment }
with an overriding BLOCK branch for anything that would hurt retention.

Novelty is *segment-scoped*. A strategy is "introduced" if it had no records in
the memory the agent started with (captured once in `baseline_strategies`); such
strategies must be experimented on every fresh segment before the agent will
trust them — this is what keeps the agent from *executing* an unproven strategy
while still letting it *learn* one segment at a time. A strategy that already
existed in the starting memory is "known inventory" and may be executed on a
fresh segment when it is known-good and the opportunity is severe.

Note: the Policy is *optimistic*. The Guardrails layer then enforces hard
caps and may further restrict the returned action. The Policy never sees the
daily caps — that is the Guardrails' job.
"""
from __future__ import annotations

from typing import Dict, Optional, Set

from monetization.agent.guardrails import Guardrails
from monetization.agent.models import (
    ACTION_BLOCK, ACTION_EXECUTE, ACTION_EXPERIMENT, ACTION_OBSERVE, PolicyConfig,
)


class Policy:
    def __init__(self, config: Optional[PolicyConfig] = None,
                 baseline_strategies: Optional[Set[str]] = None):
        self.cfg = config or PolicyConfig()
        # Strategy types present in the agent's starting memory. Captured ONCE;
        # it is intentionally *not* updated as the agent learns, so an
        # introduced (formerly unknown) strategy stays gated behind experiments
        # for the whole run instead of flipping to "known" after one test.
        self.baseline_strategies: Set[str] = set(baseline_strategies or [])

    def decide(self, *, opportunity, strategy_type: str, prior: dict,
               confidence: float, risk: str,
               simulation_revenue_delta: float, retention_delta: float,
               severity: float, guardrails: Optional[Guardrails] = None,
               local_samples: int = 0) -> str:
        """Return the intended action (observe/experiment/execute/block)."""
        # 1) Hard retention / high-risk block (cannot be overruled)
        if risk == "high":
            return ACTION_BLOCK
        if guardrails is not None and guardrails.check_retention(retention_delta):
            return ACTION_BLOCK

        known_good = prior.get("mean", 0.0) >= self.cfg.execute_prior
        novel = local_samples <= 0                      # never acted on this (seg)
        introduced = strategy_type not in self.baseline_strategies

        # 2) Introduced (formerly-unknown) strategy on a fresh segment -> test it.
        if introduced and novel:
            return ACTION_EXPERIMENT

        # 3) Known inventory strategy on a fresh segment.
        if novel:
            if known_good and severity >= self.cfg.severe_severity:
                return ACTION_EXECUTE      # trusted + urgent -> act now
            return ACTION_OBSERVE           # known + mild -> just watch

        # 4) Established (strategy, segment): severe + confident + positive.
        if (severity >= self.cfg.severe_severity
                and known_good
                and confidence >= self.cfg.execute_conf
                and simulation_revenue_delta >= 0.0):
            return ACTION_EXECUTE

        # 5) Known but mild / not-yet-confident enough -> watch
        return ACTION_OBSERVE
