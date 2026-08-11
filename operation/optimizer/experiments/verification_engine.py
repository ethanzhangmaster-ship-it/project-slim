"""
E15.2.5+ — VerificationEngine.

Turns an ExperimentDefinition into a verdict by re-reading each daily
report: did the predicted signal disappear, and did the user-side
guardrail (ARPDAU / ads-per-user) hold?

The operator applies the change in the MAX dashboard; this engine only
*observes* the outcome. Zero MAX writes — Phase 1 contract intact.

Verdict logic
-------------
  inside min horizon (< min_days since launch):
      status = ACTIVE            (still watching, no verdict)
  signal resolved (no longer firing) AND guardrail ok/pending:
      status = SUCCESS
  signal resolved BUT guardrail regression (hurt users):
      status = FAIL
  signal still firing AND past max horizon (lever ineffective / not applied):
      status = FAIL
  signal still firing AND inside max horizon:
      status = ACTIVE            (keep watching)
"""
from __future__ import annotations

from datetime import date as _date
from typing import Any, Dict, List, Optional

from operation.optimizer.experiments.experiment_models import (
    ACTIVE, FAIL, INCONCLUSIVE, PROPOSED, SUCCESS,
    ExperimentDefinition, ExperimentVerification,
)
from operation.optimizer.intel_models import MonetizationDailyReport
from operation.optimizer.user_metrics import UserGuardrail, UserMetrics


def _age_days(first: Optional[str], today: str) -> int:
    if not first:
        return 0
    try:
        f = _date.fromisoformat(first)
        t = _date.fromisoformat(today)
        return max((t - f).days, 0)
    except ValueError:
        return 0


class VerificationEngine:
    def __init__(self, guardrail: Optional[UserGuardrail] = None) -> None:
        self.guardrail = guardrail or UserGuardrail()

    # ------------------------------------------------------------------ #
    def verify(self, report: MonetizationDailyReport,
               exp: ExperimentDefinition,
               baseline_user_metrics: Optional[Dict[str, Any]] = None,
               now_user_metrics: Optional[Dict[str, Any]] = None,
               today: Optional[str] = None) -> ExperimentVerification:
        today = today or report.date or _date.today().isoformat()
        sig = exp.expected_signal or {}
        rule, target = sig.get("rule"), sig.get("target")
        still_firing = any(s.rule == rule and s.target == target
                           for s in report.signals)
        watched_from = exp.launched_at or exp.created_at
        days = _age_days(watched_from, today)

        # ---- user-side guardrail ------------------------------------ #
        base = baseline_user_metrics or exp.baseline_user_metrics or {}
        now = now_user_metrics or report.user_metrics or {}
        if base.get("available") and now.get("available"):
            res = self.guardrail.evaluate(
                UserMetrics.from_dict(base), UserMetrics.from_dict(now))
            arp = res.verdict
            arp_base = float(base.get("arpdau", 0.0) or 0.0)
            arp_now = float(now.get("arpdau", 0.0) or 0.0)
            delta = ((arp_now - arp_base) / arp_base * 100.0) if arp_base else None
        else:
            arp = "pending"
            delta = None

        # ---- guardrail-only experiments (risk hedge, e.g. diversify) -- #
        # No predicted revenue signal is expected to clear; we simply keep
        # watching the user-side guardrail. The operator archives when the
        # hedge is judged satisfactory. Never auto-resolves to SUCCESS/FAIL.
        if exp.verify_mode == "guardrail":
            return ExperimentVerification(
                exp_id=exp.exp_id, account=exp.account, status=ACTIVE,
                checked_at=today, signal_still_firing=False,
                signal_resolved=None, arpdau_guardrail=arp,
                arpdau_delta_pct=delta, days_watched=days,
                verdict_note=(f"risk-hedge experiment (no revenue signal to "
                              f"clear): user guardrail {arp} — keep watching, "
                              f"archive when hedge goal met"))

        # ---- verdict -------------------------------------------------- #
        signal_resolved: Optional[bool]
        if days < exp.min_days:
            status = ACTIVE
            signal_resolved = None
            note = (f"watching ({days}/{exp.min_days}d min); signal "
                    f"{'still firing' if still_firing else 'already gone'}; "
                    f"user guardrail {arp}")
        elif not still_firing:
            if arp == "regression":
                status = FAIL
                note = ("predicted signal resolved but ARPDAU guardrail "
                        "REGRESSED — revenue gain came at user cost")
            else:
                status = SUCCESS
                note = ("predicted signal resolved and user guardrail "
                        f"{arp} — experiment outcome held")
            signal_resolved = True
        else:  # signal still firing
            if days >= exp.max_days:
                status = FAIL
                note = (f"signal still firing after {days}d (>{exp.max_days}d "
                        f"horizon) — lever ineffective or not applied")
                signal_resolved = False
            else:
                status = ACTIVE
                signal_resolved = False
                note = (f"signal still firing ({days}/{exp.max_days}d); "
                        f"user guardrail {arp} — keep watching")

        return ExperimentVerification(
            exp_id=exp.exp_id, account=exp.account, status=status,
            checked_at=today, signal_still_firing=still_firing,
            signal_resolved=signal_resolved, arpdau_guardrail=arp,
            arpdau_delta_pct=delta, days_watched=days, verdict_note=note)

    # ------------------------------------------------------------------ #
    @staticmethod
    def summarize(verifications: List[ExperimentVerification]) -> Dict[str, int]:
        out: Dict[str, int] = {SUCCESS: 0, FAIL: 0, ACTIVE: 0,
                               INCONCLUSIVE: 0, PROPOSED: 0}
        for v in verifications:
            out[v.status] = out.get(v.status, 0) + 1
        return out
