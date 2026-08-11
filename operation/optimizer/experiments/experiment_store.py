"""
E15.2.5+ — ExperimentStore.

Per-account persistence for experiments. Proposes new experiments from
the report's Experiment-layer validated actions (dedup by stable id),
and applies verification results back onto stored definitions.

State: outputs/experiments/<account>.json
Pure bookkeeping — no MAX writes, no LLM.
"""
from __future__ import annotations

import json
import os
from datetime import date as _date
from typing import Any, Dict, List, Optional

from operation.optimizer.experiments.experiment_models import (
    ACTIVE, PROPOSED, ExperimentDefinition, ExperimentVerification,
    exp_id as _exp_id, AB_ELIGIBLE_ACTIONS,
)
from operation.optimizer.intel_models import MonetizationDailyReport

DEFAULT_DIR = os.path.join("outputs", "experiments")


class ExperimentStore:
    def __init__(self, store_dir: str = DEFAULT_DIR) -> None:
        self.dir = store_dir

    # ------------------------------------------------------------------ #
    def _path(self, account: str) -> str:
        return os.path.join(self.dir, f"{account}.json")

    def load(self, account: str) -> Dict[str, ExperimentDefinition]:
        p = self._path(account)
        if not os.path.exists(p):
            return {}
        try:
            with open(p, encoding="utf-8") as f:
                blob = json.load(f)
        except (OSError, ValueError):
            return {}
        return {d["exp_id"]: ExperimentDefinition.from_dict(d)
                for d in blob.get("experiments", [])}

    def save(self, account: str,
             defs: Dict[str, ExperimentDefinition]) -> None:
        os.makedirs(self.dir, exist_ok=True)
        blob = {"account": account,
                "experiments": [d.to_dict() for d in defs.values()]}
        with open(self._path(account), "w", encoding="utf-8") as f:
            json.dump(blob, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    def propose_from_validated(
            self, report: MonetizationDailyReport,
            today: Optional[str] = None) -> List[ExperimentDefinition]:
        """Create PROPOSED A/B experiments for any A/B-eligible validated
        action not already tracked. Returns the newly created ones.

        The A/B representation (variant A/B, expected Revenue/DAU lift) is
        produced by ABExperimentGenerator from the matching IntelSignal
        metrics; this method only persists + dedups by stable id.
        """
        today = today or report.date or _date.today().isoformat()
        existing = self.load(report.account)
        baseline = report.user_metrics or {}
        dau = (baseline or {}).get("dau")
        from operation.optimizer.experiments.experiment_generator import (
            ABExperimentGenerator,
        )
        gen = ABExperimentGenerator()
        all_ab = gen.generate(report, dau=dau)
        created: List[ExperimentDefinition] = []
        for exp in all_ab:
            if exp.exp_id in existing:
                continue
            exp.created_at = today
            exp.launched_at = today
            exp.baseline_user_metrics = baseline
            existing[exp.exp_id] = exp
            created.append(exp)
        # Backfill A/B fields on experiments proposed *before* the A/B
        # increment (stored on disk without variant_a/variant_b). The daily
        # run must render them with the new A/B framing, not blank.
        enriched_any = False
        for exp in existing.values():
            if gen.enrich(exp, report, dau=dau):
                enriched_any = True
        if created or enriched_any:
            self.save(report.account, existing)
        return created

    # ------------------------------------------------------------------ #
    def apply_verifications(
            self, account: str,
            verifications: List[ExperimentVerification]) -> Dict[str, ExperimentDefinition]:
        """Write verification outcomes back onto stored definitions."""
        defs = self.load(account)
        for v in verifications:
            exp = defs.get(v.exp_id)
            if exp is None:
                continue
            exp.status = v.status
            exp.result_note = v.verdict_note
            exp.last_arpdau_guardrail = v.arpdau_guardrail
            exp.last_arpdau_delta_pct = v.arpdau_delta_pct
            if v.status in ("SUCCESS", "FAIL", "INCONCLUSIVE"):
                exp.resolved_at = v.checked_at
        self.save(account, defs)
        return defs

    # ------------------------------------------------------------------ #
    def active(self, account: str) -> List[ExperimentDefinition]:
        """Experiments still in PROPOSED / ACTIVE (open loop)."""
        return [d for d in self.load(account).values()
                if d.status in (PROPOSED, ACTIVE)]

    # ------------------------------------------------------------------ #
    def mark_applied(self, account: str, exp_id: str,
                     applied_at: Optional[str] = None
                     ) -> Optional[ExperimentDefinition]:
        """Operator confirms the change is live in the MAX dashboard.
        Sets the before/after anchor for impact measurement."""
        from operation.optimizer.experiments.experiment_models import APPLIED
        defs = self.load(account)
        exp = defs.get(exp_id)
        if exp is None:
            return None
        exp.applied_at = applied_at or _date.today().isoformat()
        exp.status = APPLIED
        exp.result_note = f"operator marked applied {exp.applied_at}"
        self.save(account, defs)
        return exp

    # ------------------------------------------------------------------ #
    def applied(self, account: str) -> List[ExperimentDefinition]:
        """Experiments with an applied_at anchor, not yet decided."""
        return [d for d in self.load(account).values()
                if d.applied_at and d.decision == ""]
