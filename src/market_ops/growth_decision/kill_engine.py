"""E9.9.5 Module 2: Kill Engine.

Determines if an experiment asset should be terminated.

Safety Gate: minimum spend and installs before kill decision.
Kill Rules:
  1. ROAS_DECAY:      variant_roas < control_roas * 0.7
  2. CPI_DEGRADATION:  variant_cpi > control_cpi * 1.4
  3. CTR_COLLAPSE:     variant_ctr < control_ctr * 0.7

Output: GrowthDecision with KILL action and triggered rules.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.growth_decision.schemas import (
    GrowthDecision, GrowthAction, WinnerLevel,
)

# ── Thresholds ─────────────────────────────────────────────

MIN_SPEND = 100.0
MIN_INSTALLS = 50

ROAS_DECAY_RATIO = 0.7
CPI_DEGRADATION_RATIO = 1.4
CTR_COLLAPSE_RATIO = 0.7


class KillEngine:
    """Evaluates kill rules and generates termination decisions.

    Usage:
        kill = KillEngine()
        kill_decisions = kill.evaluate("output/experiment_intelligence/experiment_results.json")
    """

    def __init__(self) -> None:
        self._control_performance: dict[str, dict[str, Any]] = {}

    def evaluate(
        self,
        results_path: str | Path,
    ) -> list[GrowthDecision]:
        """Load E9.9 results and evaluate kill rules.

        Args:
            results_path: Path to experiment_results.json

        Returns:
            GrowthDecision list (KILL or WATCH only)
        """
        raw = self._load_results(results_path)
        return self.evaluate_from_dicts(raw)

    def evaluate_from_dicts(
        self, results: list[dict[str, Any]]
    ) -> list[GrowthDecision]:
        """Evaluate kill rules on pre-loaded results."""
        decisions = []
        for entry in results:
            decision = self._evaluate_single(entry)
            decisions.append(decision)
        return decisions

    def evaluate_single(
        self, result: dict[str, Any]
    ) -> GrowthDecision:
        """Evaluate kill rules for a single experiment."""
        return self._evaluate_single(result)

    # ── Load ───────────────────────────────────────────────

    def _load_results(self, path: str | Path) -> list[dict[str, Any]]:
        """Load E9.9 experiment_results.json."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("results", []) if isinstance(data, dict) else data

    # ── Evaluation ─────────────────────────────────────────

    def _evaluate_single(self, result: dict[str, Any]) -> GrowthDecision:
        """Evaluate kill rules for a single experiment.

        Process:
        1. Check safety gate (MIN_SPEND, MIN_INSTALLS)
        2. Evaluate 3 kill rules
        3. Return KILL or WATCH
        """
        spend = result.get("spend", 0.0)
        installs = result.get("installs", 0)
        variant_roas = result.get("roas", 0.0)
        variant_cpi = result.get("cpi", 0.0)
        variant_ctr = result.get("ctr", 0.0)

        # Safety gate: must have minimum evidence
        if not self._safety_gate_passed(spend, installs):
            return GrowthDecision(
                decision_id=f"GD_{uuid.uuid4().hex[:8]}",
                experiment_id=result.get("experiment_id", ""),
                creative_id=result.get("control_creative_id", ""),
                decision=GrowthAction.WATCH.value,
                winner_level=WinnerLevel.INCONCLUSIVE.value,
                reason=(
                    f"Insufficient evidence for kill: "
                    f"spend=${spend:.0f}/{MIN_SPEND:.0f}, "
                    f"installs={installs}/{MIN_INSTALLS}"
                ),
                confidence=0.0,
                budget_before=spend,
                budget_after=0.0,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        # Evaluate kill rules
        triggered_rules = self._check_kill_rules(
            variant_roas=variant_roas,
            variant_cpi=variant_cpi,
            variant_ctr=variant_ctr,
            # Control metrics from E9.9 result (lift is relative to control)
            # Use lift to estimate control values
            lift=result.get("lift", 0.0),
        )

        if triggered_rules:
            return GrowthDecision(
                decision_id=f"GD_{uuid.uuid4().hex[:8]}",
                experiment_id=result.get("experiment_id", ""),
                creative_id=result.get("control_creative_id", ""),
                decision=GrowthAction.KILL.value,
                winner_level=WinnerLevel.FAILED.value,
                reason="; ".join(triggered_rules),
                confidence=result.get("confidence", 0.0),
                budget_before=spend,
                budget_after=0.0,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        # No kill rules triggered
        return GrowthDecision(
            decision_id=f"GD_{uuid.uuid4().hex[:8]}",
            experiment_id=result.get("experiment_id", ""),
            creative_id=result.get("control_creative_id", ""),
            decision=GrowthAction.WATCH.value,
            winner_level=WinnerLevel.PROMISING.value,
            reason="No kill rules triggered",
            confidence=result.get("confidence", 0.0),
            budget_before=spend,
            budget_after=0.0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── Safety Gate ────────────────────────────────────────

    def _safety_gate_passed(self, spend: float, installs: int) -> bool:
        """Check minimum evidence threshold before kill decision.

        Returns True if conditions are met (can proceed to evaluate).
        Returns False if insufficient evidence (should WATCH).
        """
        return spend >= MIN_SPEND and installs >= MIN_INSTALLS

    # ── Kill Rules ─────────────────────────────────────────

    def _check_kill_rules(
        self,
        variant_roas: float,
        variant_cpi: float,
        variant_ctr: float,
        lift: float,
    ) -> list[str]:
        """Evaluate all kill rules and return triggered rule names.

        Uses lift to estimate control values:
          control_roas = variant_roas / (1 + lift)
          control_cpi = variant_cpi * (1 + lift)   [higher lift → lower CPI]
          control_ctr = variant_ctr / (1 + lift)    [higher lift → lower CTR]
        """
        triggered: list[str] = []

        # Estimate control values from variant + lift
        if lift > -1.0:
            control_roas = variant_roas / (1.0 + lift) if lift != -1.0 else variant_roas
            control_cpi = variant_cpi * (1.0 + lift) if lift > 0 else variant_cpi / (1.0 - lift) if lift < 0 else variant_cpi
            control_ctr = variant_ctr / (1.0 + lift) if lift != -1.0 else variant_ctr
        else:
            control_roas = variant_roas
            control_cpi = variant_cpi
            control_ctr = variant_ctr

        # Rule 1: ROAS Decay
        if control_roas > 0 and variant_roas < control_roas * ROAS_DECAY_RATIO:
            triggered.append(
                f"ROAS_DECAY: variant={variant_roas:.3f} < control={control_roas:.3f}*{ROAS_DECAY_RATIO}"
            )

        # Rule 2: CPI Degradation
        if control_cpi > 0 and variant_cpi > control_cpi * CPI_DEGRADATION_RATIO:
            triggered.append(
                f"CPI_DEGRADATION: variant=${variant_cpi:.2f} > control=${control_cpi:.2f}*{CPI_DEGRADATION_RATIO}"
            )

        # Rule 3: CTR Collapse
        if control_ctr > 0 and variant_ctr < control_ctr * CTR_COLLAPSE_RATIO:
            triggered.append(
                f"CTR_COLLAPSE: variant={variant_ctr:.4f} < control={control_ctr:.4f}*{CTR_COLLAPSE_RATIO}"
            )

        return triggered

    # ── Summary ────────────────────────────────────────────

    def get_kill_summary(
        self, decisions: list[GrowthDecision]
    ) -> dict[str, Any]:
        """Get summary of kill engine decisions."""
        kills = [d for d in decisions if d.decision == GrowthAction.KILL.value]
        watches = [d for d in decisions if d.decision == GrowthAction.WATCH.value]

        # Count triggered rules
        rule_counts: dict[str, int] = {"ROAS_DECAY": 0, "CPI_DEGRADATION": 0, "CTR_COLLAPSE": 0}
        for d in kills:
            for rule in rule_counts:
                if rule in d.reason:
                    rule_counts[rule] += 1

        return {
            "total_evaluated": len(decisions),
            "kills": len(kills),
            "watches": len(watches),
            "kill_rate": round(len(kills) / max(1, len(decisions)), 3),
            "triggered_rules": rule_counts,
            "safety_gate_params": {
                "MIN_SPEND": MIN_SPEND,
                "MIN_INSTALLS": MIN_INSTALLS,
            },
        }