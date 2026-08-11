"""V4.3 Policy Report — daily policy report generation.

Outputs daily:
  - Today's strategy
  - Budget allocation
  - Kill reasons
  - Explore ratio
  - Portfolio composition
  - Revenue prediction
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import (
    PolicyReport, DailyProductionPlan, DecisionPolicy, DecisionLog, PolicyAction,
)


class PolicyReportGenerator:
    """Generate daily policy reports."""

    def generate(self, plan: DailyProductionPlan,
                 policy: DecisionPolicy,
                 logs: list[DecisionLog],
                 explore_ratio: float = 0.0,
                 revenue_prediction: float = 0.0) -> PolicyReport:
        """Generate a complete policy report.

        Args:
            plan: Daily production plan.
            policy: Current policy configuration.
            logs: Decision logs for the day.
            explore_ratio: Current exploration ratio.
            revenue_prediction: Predicted revenue.

        Returns:
            PolicyReport with all sections.
        """
        kill_reasons = []
        for log in logs:
            if log.action == PolicyAction.KILL:
                kill_reasons.append({
                    "creative_id": log.creative_id,
                    "reason": log.reason,
                    "overridden": log.overridden_by_risk,
                })

        # Build summary
        summary = self._build_summary(plan, policy, explore_ratio, revenue_prediction)

        return PolicyReport(
            date=datetime.now().strftime("%Y-%m-%d"),
            plan=plan,
            policy_version=policy.version,
            decisions_log=logs,
            kill_reasons=kill_reasons,
            explore_ratio=explore_ratio,
            portfolio_summary=plan.portfolio.to_dict(),
            budget_summary=plan.budget.to_dict(),
            risk_summary=plan.risk_summary,
            revenue_prediction=revenue_prediction,
            summary=summary,
        )

    def _build_summary(self, plan: DailyProductionPlan,
                       policy: DecisionPolicy,
                       explore_ratio: float,
                       revenue_prediction: float) -> str:
        """Build a human-readable summary."""
        lines = [
            f"=== Creative Brain Daily Policy Report ===",
            f"Date: {plan.date}",
            f"Policy Version: {policy.version}",
            f"",
            f"Production Plan:",
            f"  Generate: {plan.generate_count}",
            f"  Retest:   {plan.retest_count}",
            f"  Adapt:    {plan.adapt_count}",
            f"  Kill:     {plan.kill_count}",
            f"  Total:    {plan.total_creatives}",
            f"",
            f"Portfolio:",
            f"  Winner:  {plan.portfolio.categories.get('winner', 0):.0%}",
            f"  Explore: {plan.portfolio.categories.get('explore', 0):.0%}",
            f"  Adapt:   {plan.portfolio.categories.get('adapt', 0):.0%}",
            f"  Retest:  {plan.portfolio.categories.get('retest', 0):.0%}",
            f"",
            f"Explore Ratio: {explore_ratio:.0%}",
            f"Predicted Revenue: ${revenue_prediction:,.2f}",
            f"",
            f"Policy Thresholds:",
            f"  Confidence GO:  {policy.confidence_threshold_go:.0%}",
            f"  Confidence KILL: {policy.confidence_threshold_kill:.0%}",
            f"  ROI GO:         {policy.roi_threshold_go:.1f}",
            f"  ROI KILL:       {policy.roi_threshold_kill:.1f}",
        ]
        return "\n".join(lines)

    def to_markdown(self, report: PolicyReport) -> str:
        """Generate markdown report."""
        lines = [
            f"# Creative Brain Policy Report",
            f"",
            f"**Date:** {report.date}",
            f"**Policy Version:** {report.policy_version}",
            f"",
            f"---",
            f"",
            f"## Production Plan",
            f"",
            f"| Action | Count |",
            f"|--------|-------|",
            f"| Generate | {report.plan.generate_count} |",
            f"| Retest | {report.plan.retest_count} |",
            f"| Adapt | {report.plan.adapt_count} |",
            f"| Kill | {report.plan.kill_count} |",
            f"| **Total** | **{report.plan.total_creatives}** |",
            f"",
            f"---",
            f"",
            f"## Portfolio",
            f"",
            f"| Category | Allocation |",
            f"|----------|------------|",
        ]
        for cat, pct in report.portfolio_summary.get("categories", {}).items():
            lines.append(f"| {cat} | {pct}% |")

        lines.extend([
            f"",
            f"**Explore Ratio:** {report.explore_ratio:.0%}",
            f"",
            f"---",
            f"",
            f"## Kill Reasons",
            f"",
        ])
        for kr in report.kill_reasons[:10]:
            lines.append(
                f"- `{kr['creative_id']}`: {kr['reason']}"
                f"{' [RISK OVERRIDE]' if kr.get('overridden') else ''}"
            )

        lines.extend([
            f"",
            f"---",
            f"",
            f"## Revenue Prediction",
            f"",
            f"${report.revenue_prediction:,.2f}",
            f"",
            f"---",
            f"",
            f"## Summary",
            f"",
            report.summary,
        ])

        return "\n".join(lines)