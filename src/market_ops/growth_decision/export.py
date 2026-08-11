"""E9.9.5: Export Module — Standalone export for Growth Decision outputs.

Exports:
  1. growth_decisions.json    — all growth decisions (SCALE/KILL/WATCH/RETEST)
  2. creative_portfolio.json  — 3-tier portfolio allocation
  3. scale_plans.json         — automated budget scaling plans
  4. risk_reports.json        — E10 safety gate reports
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.growth_decision.schemas import (
    GrowthDecision, CreativePortfolio, ScalePlan, RiskReport, GrowthReport,
)


class GrowthDecisionExporter:
    """Standalone export module for E9.9.5 Growth Decision outputs.

    Usage:
        exporter = GrowthDecisionExporter(output_dir="output/growth_decision")
        paths = exporter.export_all(decisions, portfolios, scale_plans, risk_reports)
    """

    def __init__(
        self,
        output_dir: str | Path = "output/growth_decision",
    ) -> None:
        self._output_dir = Path(output_dir)

    def ensure_output_dir(self) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        return self._output_dir

    # ── File 1: growth_decisions.json ──────────────────────

    def export_decisions(
        self,
        decisions: list[GrowthDecision],
        filename: str = "growth_decisions.json",
    ) -> Path:
        """Export all growth decisions."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        scale_count = sum(1 for d in decisions if d.decision == "SCALE")
        kill_count = sum(1 for d in decisions if d.decision == "KILL")
        watch_count = sum(1 for d in decisions if d.decision == "WATCH")
        retest_count = sum(1 for d in decisions if d.decision == "RETEST")

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_decisions": len(decisions),
            "by_action": {
                "SCALE": scale_count,
                "KILL": kill_count,
                "WATCH": watch_count,
                "RETEST": retest_count,
            },
            "decisions": [d.to_dict() for d in decisions],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 2: creative_portfolio.json ────────────────────

    def export_portfolio(
        self,
        portfolios: list[CreativePortfolio],
        filename: str = "creative_portfolio.json",
    ) -> Path:
        """Export creative portfolio allocations."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        exploration = sum(1 for p in portfolios if p.bucket == "EXPLORATION")
        growth = sum(1 for p in portfolios if p.bucket == "GROWTH")
        harvest = sum(1 for p in portfolios if p.bucket == "HARVEST")

        total = len(portfolios) or 1
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_assets": len(portfolios),
            "allocation": {
                "EXPLORATION": {
                    "count": exploration,
                    "ratio": round(exploration / total, 3),
                },
                "GROWTH": {
                    "count": growth,
                    "ratio": round(growth / total, 3),
                },
                "HARVEST": {
                    "count": harvest,
                    "ratio": round(harvest / total, 3),
                },
            },
            "portfolios": [p.to_dict() for p in portfolios],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 3: scale_plans.json ───────────────────────────

    def export_scale_plans(
        self,
        scale_plans: list[ScalePlan],
        filename: str = "scale_plans.json",
    ) -> Path:
        """Export automated scaling plans."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        active = sum(1 for s in scale_plans if s.status == "ACTIVE")
        paused = sum(1 for s in scale_plans if s.status == "PAUSED")
        stopped = sum(1 for s in scale_plans if s.status == "STOPPED")

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_plans": len(scale_plans),
            "by_status": {
                "ACTIVE": active,
                "PAUSED": paused,
                "STOPPED": stopped,
            },
            "scale_plans": [s.to_dict() for s in scale_plans],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 4: risk_reports.json ──────────────────────────

    def export_risk_reports(
        self,
        risk_reports: list[RiskReport],
        filename: str = "risk_reports.json",
    ) -> Path:
        """Export risk reports for E10 safety gate."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        blocking = sum(1 for r in risk_reports if r.blocking)
        safe = sum(1 for r in risk_reports if r.budget_risk == "SAFE"
                   and r.scale_risk == "SAFE"
                   and r.diversity_risk == "SAFE")

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_reports": len(risk_reports),
            "blocking_count": blocking,
            "safe_count": safe,
            "risk_reports": [r.to_dict() for r in risk_reports],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 5: growth_report.json ─────────────────────────

    def export_growth_report(
        self,
        report: GrowthReport,
        filename: str = "growth_report.json",
    ) -> Path:
        """Export full GrowthReport summary."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        data = report.to_dict()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 6: growth_actions.json ────────────────────────

    def export_growth_actions(
        self,
        decisions: list[GrowthDecision],
        scale_plans: list[ScalePlan],
        filename: str = "growth_actions.json",
    ) -> Path:
        """Export actionable growth items (decisions + scale plans)."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        actions = []
        for d in decisions:
            action_entry = d.to_dict()
            # Attach scale plan if exists
            plan = next((s for s in scale_plans if s.creative_id == d.creative_id), None)
            if plan:
                action_entry["scale_plan"] = plan.to_dict()
            actions.append(action_entry)

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_actions": len(actions),
            "actions": actions,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── Batch Export ───────────────────────────────────────

    def export_all(
        self,
        decisions: list[GrowthDecision],
        portfolios: list[CreativePortfolio],
        scale_plans: list[ScalePlan],
        risk_reports: list[RiskReport],
    ) -> dict[str, str]:
        """Export all 4 output files.

        Returns:
            {file_category: full_path}
        """
        return {
            "growth_decisions": str(self.export_decisions(decisions)),
            "creative_portfolio": str(self.export_portfolio(portfolios)),
            "scale_plans": str(self.export_scale_plans(scale_plans)),
            "risk_reports": str(self.export_risk_reports(risk_reports)),
        }

    # ── Summary ────────────────────────────────────────────

    def get_export_summary(self, paths: dict[str, str]) -> dict[str, Any]:
        """Get summary of exported files with sizes."""
        summary = {}
        for category, path_str in paths.items():
            p = Path(path_str)
            if p.exists():
                summary[category] = {
                    "path": path_str,
                    "size_kb": round(p.stat().st_size / 1024, 1),
                }
            else:
                summary[category] = {"path": path_str, "status": "missing"}
        return summary