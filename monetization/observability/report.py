"""
E14.5.4 — Daily Operator Report Generator
==========================================

The single most valuable artifact for a human running an AI game factory:
one concise daily brief covering UA actions, monetization health, experiments
and risk — so a single operator can supervise 10–50 games without opening
each one.

It consumes the FleetHealthReport (E14.5.1), the day's DecisionTraces
(E14.5.2) and the emitted Alerts (E14.5.3). No UI: output is a plain
markdown string + structured dict, and the service persists it as
<reports_dir>/<day_tag>.md.
"""
from __future__ import annotations

from typing import List

from monetization.observability.models import (
    DailyReport, DecisionTrace, FleetHealthReport, SubReport,
)


class DailyReportGenerator:
    """Builds the four-section Daily Operation Report."""

    def generate(self, fleet: FleetHealthReport,
                 traces: List[DecisionTrace],
                 alerts: list) -> DailyReport:
        games = fleet.games
        active = len(games)
        executed = sum(1 for t in traces if t.action == "execute")
        blocked = sum(1 for t in traces if t.action == "block")
        experiments = sum(1 for t in traces if t.action == "experiment")
        rolled = sum(1 for t in traces
                     if "rollback" in t.final_action or t.final_action == "failed")

        best = max(games, key=lambda g: g.score) if games else None
        executed_traces = [t for t in traces if t.action == "execute"]
        big = max(executed_traces, key=lambda t: t.priority, default=None) \
            if executed_traces else None

        fdict = fleet.to_dict()
        crit = [a for a in alerts if getattr(a, "level", None) == "critical"]
        warn = [a for a in alerts if getattr(a, "level", None) == "warning"]

        summary_lines = [
            f"Games: {active} active",
            f"Executed: {executed} actions",
            f"Blocked: {blocked} risky actions",
            f"Rolled back: {rolled}",
            f"Best learner: "
            f"{best.game_id if best else 'n/a'} "
            f"(score {best.score:.0f})" if best else "Best learner: n/a",
            f"Biggest opportunity: "
            f"{big.decision if big else 'n/a'} "
            f"(priority {big.priority:.2f})" if big else "Biggest opportunity: n/a",
        ]

        ua = SubReport("UA Action Report", [
            f"execute decisions: {executed}",
            f"experiment decisions: {experiments}",
            f"blocked (high-risk): {blocked}",
        ])
        mon = SubReport("Monetization Report", [
            f"healthy games: {fdict['healthy']}",
            f"degraded: {fdict['degraded']}",
            f"unhealthy: {fdict['unhealthy']}",
            f"isolated: {fdict['isolated']}",
            f"mean fleet score: {fdict['mean_score']}",
        ])
        exp = SubReport("Experiment Report", [
            f"experiments run: {experiments}",
        ])
        risk_lines = [f"critical alerts: {len(crit)}",
                      f"warning alerts: {len(warn)}"]
        for a in (crit[:5] + warn[:5]):
            risk_lines.append(f"  - [{a.level}] {a.message}")
        risk = SubReport("Risk Report", risk_lines)

        return DailyReport(
            date=fleet.generated_at[:10],
            summary="\n".join(summary_lines),
            ua_action=ua, monetization=mon, experiment=exp, risk=risk,
        )


__all__ = ["DailyReportGenerator"]
