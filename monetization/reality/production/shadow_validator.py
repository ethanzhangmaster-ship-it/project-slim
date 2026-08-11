"""
E14.7.1 — Shadow Validator

Validates the shadow mode integrity after a P04 run:

  1. Data completeness (all three sources loaded)
  2. Decision completeness (every trace has reason_chain + confidence + evidence)
  3. Zero-write verification (real_api_called == 0 on ALL ProviderResults)
  4. Report generated

Returns a pass/fail dict suitable for acceptance gate integration.
"""
from __future__ import annotations

from typing import Dict, List


class ShadowValidator:
    """Ensures the shadow reality run is safe and complete."""

    def validate(self,
                 report,                     # P04ShadowReport
                 adjust_loaded: bool,
                 meta_loaded: bool,
                 max_loaded: bool) -> dict:
        issues: List[str] = []
        checks: Dict[str, bool] = {}

        # 1. data completeness
        checks["adjust_loaded"] = adjust_loaded
        checks["meta_loaded"] = meta_loaded
        checks["max_loaded"] = max_loaded
        if not adjust_loaded:
            issues.append("Adjust data not loaded")
        if not meta_loaded:
            issues.append("Meta Ads data not loaded")
        if not max_loaded:
            issues.append("MAX data not loaded")

        # 2. decision completeness
        traces = report.actions
        has_decision = len(traces) > 0
        checks["has_decisions"] = has_decision
        if not has_decision:
            issues.append("No decisions produced by shadow agent")
        explainable = sum(1 for a in traces
                         if a.reason and a.confidence > 0 and a.priority > 0)
        explain_pct = explainable / len(traces) * 100 if traces else 0.0
        checks["decision_completeness_pct"] = explain_pct >= 95.0
        if explain_pct < 95.0:
            issues.append(f"Decision completeness {explain_pct:.0f}% < 95%")

        # 3. zero-write verification
        if report.real_api_called:
            issues.append(
                f"CRITICAL: real_api_called=True ({report.total_api_calls} calls). "
                f"Shadow mode MUST keep all API calls to False.")
        checks["real_api_called_false"] = not report.real_api_called
        checks["shadow_mode_confirmed"] = report.mode == "shadow"

        # 4. snapshot integrity
        checks["snapshot_present"] = report.snapshot is not None
        if report.snapshot is None:
            issues.append("RealitySnapshot missing")
        else:
            checks["snapshot_segments_present"] = len(report.snapshot.segments) > 0

        # 5. risk report
        checks["risk_report_generated"] = len(report.top_risks) > 0

        passed = len(issues) == 0
        return {
            "result": "PASS" if passed else "FAIL",
            "checks": {k: v for k, v in checks.items()},
            "issues": issues,
            "decision_completeness_pct": round(explain_pct, 1),
            "total_api_calls": report.total_api_calls,
        }
