"""E9.9.5 → E10 Frozen API Contract.

Stable boundary between Growth Control Plane and
Autonomous Growth Layer.

E10 MUST import ONLY from this module:

  from growth_decision.api import GrowthAPI

E10 MUST NOT import internal modules:
  scale_engine, portfolio_manager, risk_controller, etc.

API Endpoints:
  1. get_growth_actions()  — What actions to execute this cycle?
  2. get_portfolio_state() — Current asset pool allocation?
  3. get_risk_status()     — Is it safe to execute?
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market_ops.growth_decision.api_schema import (
    GrowthActionRequest,
    GrowthActionItem,
    GrowthActionResponse,
    PortfolioPoolState,
    PortfolioStateResponse,
    RiskItem,
    RiskStatusResponse,
)
from market_ops.growth_decision.growth_orchestrator import GrowthOrchestrator


class GrowthAPI:
    """Frozen E9.9.5 → E10 API boundary.

    Wraps the GrowthOrchestrator and exposes 3 stable endpoints
    for E10 Autonomous Growth Layer consumption.

    Usage:
        api = GrowthAPI(experiment_results, total_budget=10000)
        actions = api.get_growth_actions()
        portfolio = api.get_portfolio_state()
        risk = api.get_risk_status()
    """

    def __init__(
        self,
        experiment_results: list[dict[str, Any]] | None = None,
        total_budget: float = 10000.0,
    ) -> None:
        """Initialize API and optionally run pipeline.

        Args:
            experiment_results: E9.9 experiment result dicts
            total_budget: Total budget across all creatives
        """
        self._orchestrator = GrowthOrchestrator()
        self._total_budget = total_budget
        self._experiment_results = experiment_results or []

        # Cached pipeline results
        self._decisions: list[Any] = []
        self._portfolios: list[Any] = []
        self._scale_plans: list[Any] = []
        self._risk_reports: list[Any] = []
        self._last_run_at: str = ""

        # Auto-run if experiment results provided
        if experiment_results:
            self.run(experiment_results, total_budget)

    # ═══════════════════════════════════════════════════════
    # Pipeline Execution
    # ═══════════════════════════════════════════════════════

    def run(
        self,
        experiment_results: list[dict[str, Any]] | None = None,
        total_budget: float | None = None,
    ) -> None:
        """Execute the full Growth Control Plane pipeline.

        Args:
            experiment_results: Override experiment results
            total_budget: Override total budget
        """
        if experiment_results is not None:
            self._experiment_results = experiment_results
        if total_budget is not None:
            self._total_budget = total_budget

        result = self._orchestrator.run(
            self._experiment_results, self._total_budget
        )
        self._decisions = result["decisions"]
        self._portfolios = result["portfolios"]
        self._scale_plans = result["scale_plans"]
        self._risk_reports = result["risk_reports"]
        self._last_run_at = datetime.now(timezone.utc).isoformat()

    # ═══════════════════════════════════════════════════════
    # API 1: get_growth_actions()
    # ═══════════════════════════════════════════════════════

    def get_growth_actions(
        self, request: GrowthActionRequest | None = None,
    ) -> GrowthActionResponse:
        """Get all growth actions for the current cycle.

        E10 calls this every scheduling cycle to determine
        what actions need to be executed.

        Safety Gate: if any risk report is blocking,
        returns empty actions list (E10 must halt).

        Returns:
            GrowthActionResponse with SCALE/KILL/WATCH/RETEST actions
        """
        # Safety Gate: if any risk is blocking, return empty
        if any(r.blocking for r in self._risk_reports):
            return GrowthActionResponse(
                timestamp=self._last_run_at,
                actions=[],
            )

        actions = []
        for d in self._decisions:
            # Find associated scale plan
            scale_plan = next(
                (s for s in self._scale_plans if s.creative_id == d.creative_id),
                None,
            )

            # Build reason list
            reasons = [d.winner_level]
            if d.reason:
                reasons.append(d.reason)
            # Check risk
            risk = next(
                (r for r in self._risk_reports if r.creative_id == d.creative_id),
                None,
            )
            if risk:
                risk_level = risk.budget_risk
                if risk.scale_risk != "SAFE":
                    risk_level = risk.scale_risk
                if risk.diversity_risk != "SAFE":
                    risk_level = risk.diversity_risk
                reasons.append(f"risk {risk_level}")

            actions.append(GrowthActionItem(
                creative_id=d.creative_id,
                action=d.decision,
                budget_current=d.budget_before,
                budget_target=scale_plan.target_budget if scale_plan else d.budget_after,
                confidence=d.confidence,
                reason=reasons,
            ))

        return GrowthActionResponse(
            timestamp=self._last_run_at,
            actions=actions,
        )

    # ═══════════════════════════════════════════════════════
    # API 2: get_portfolio_state()
    # ═══════════════════════════════════════════════════════

    def get_portfolio_state(self) -> PortfolioStateResponse:
        """Get current portfolio allocation state.

        E10 uses this for:
          - Automatic budget allocation
          - Lifecycle management
          - Asset health monitoring

        Returns:
            PortfolioStateResponse with 3-pool breakdown
        """
        exploration = PortfolioPoolState()
        growth = PortfolioPoolState()
        harvest = PortfolioPoolState()
        total_assets = len(self._portfolios)
        total_budget = 0.0

        for p in self._portfolios:
            total_budget += p.allocated_budget
            if p.bucket == "EXPLORATION":
                exploration.count += 1
                exploration.budget += p.allocated_budget
            elif p.bucket == "GROWTH":
                growth.count += 1
                growth.budget += p.allocated_budget
            elif p.bucket == "HARVEST":
                harvest.count += 1
                harvest.budget += p.allocated_budget

        # Calculate ratios
        budget_total = max(1.0, total_budget)
        exploration.ratio = round(exploration.budget / budget_total, 3)
        growth.ratio = round(growth.budget / budget_total, 3)
        harvest.ratio = round(harvest.budget / budget_total, 3)

        return PortfolioStateResponse(
            exploration=exploration,
            growth=growth,
            harvest=harvest,
            total_budget=round(total_budget, 2),
            total_assets=total_assets,
            generated_at=self._last_run_at,
        )

    # ═══════════════════════════════════════════════════════
    # API 3: get_risk_status()
    # ═══════════════════════════════════════════════════════

    def get_risk_status(self) -> RiskStatusResponse:
        """Get current risk status for E10 safety gate.

        If blocking=True, E10 MUST STOP ALL AUTOMATION.

        Returns:
            RiskStatusResponse with blocking flag and risk breakdown
        """
        blocking = any(r.blocking for r in self._risk_reports)
        risks: list[RiskItem] = []

        if not self._risk_reports:
            return RiskStatusResponse(
                blocking=False,
                risk_level="SAFE",
                risks=[],
                generated_at=self._last_run_at,
            )

        # Aggregate risk dimensions
        budget_levels = set(r.budget_risk for r in self._risk_reports)
        scale_levels = set(r.scale_risk for r in self._risk_reports)
        diversity_levels = set(r.diversity_risk for r in self._risk_reports)

        def _worst(levels: set[str]) -> str:
            if "CRITICAL" in levels:
                return "CRITICAL"
            if "WARNING" in levels:
                return "WARNING"
            return "SAFE"

        risks.append(RiskItem(
            type="BUDGET",
            level=_worst(budget_levels),
            detail=f"{len(self._risk_reports)} creatives evaluated",
        ))
        risks.append(RiskItem(
            type="SCALE",
            level=_worst(scale_levels),
            detail=f"Max step: {max((r.hhi_score for r in self._risk_reports), default=0):.3f}",
        ))
        risks.append(RiskItem(
            type="DIVERSITY",
            level=_worst(diversity_levels),
            detail=f"HHI: {max((r.hhi_score for r in self._risk_reports), default=0):.3f}",
        ))

        overall = _worst({r.level for r in risks})

        return RiskStatusResponse(
            blocking=blocking,
            risk_level=overall,
            risks=risks,
            generated_at=self._last_run_at,
        )

    # ═══════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════

    @property
    def last_run_at(self) -> str:
        return self._last_run_at

    @property
    def has_data(self) -> bool:
        return bool(self._decisions)