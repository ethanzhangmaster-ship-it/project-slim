"""E9.9.5 Module 4: Risk Controller.

Growth Control Plane safety gate. Evaluates three risk dimensions:
  1. Budget Risk:    single creative <= 30% total budget
  2. Scale Risk:     daily increase <= 2x
  3. Diversity Risk: HHI (Herfindahl-Hirschman Index) <= 0.5

Output: RiskReport with blocking flag. If blocking=True, E10 must halt.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from market_ops.growth_decision.schemas import (
    RiskReport, RiskLevel, ScalePlan, GrowthDecision, CreativePortfolio,
)

# ── Risk Thresholds ────────────────────────────────────────

MAX_CREATIVE_BUDGET_RATIO = 0.3    # Single creative <= 30% total
MAX_DAILY_SCALE_MULTIPLIER = 2.0   # Daily increase <= 2x
DIVERSITY_HHI_THRESHOLD = 0.5      # HHI > 0.5 triggers blocking


class RiskController:
    """Evaluates growth risks and generates safety gate reports.

    Usage:
        controller = RiskController()
        reports = controller.evaluate(
            scale_plans=plans,
            portfolios=portfolios,
            total_budget=5000,
        )
    """

    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        scale_plans: list[ScalePlan],
        portfolios: list[CreativePortfolio],
        total_budget: float = 5000.0,
    ) -> list[RiskReport]:
        """Evaluate all three risk dimensions for each creative.

        Args:
            scale_plans: Active scale plans
            portfolios: Portfolio allocations (for archetype distribution)
            total_budget: Total daily budget across all creatives

        Returns:
            List of RiskReport objects (one per creative with scale plan)
        """
        reports = []

        for plan in scale_plans:
            # Find matching portfolio
            portfolio = next(
                (p for p in portfolios if p.creative_id == plan.creative_id),
                None,
            )

            report = self._evaluate_single(
                plan=plan,
                portfolio=portfolio,
                total_budget=total_budget,
                all_portfolios=portfolios,
            )
            reports.append(report)

        return reports

    def evaluate_single(
        self,
        scale_plan: ScalePlan,
        portfolio: CreativePortfolio | None = None,
        total_budget: float = 5000.0,
        all_portfolios: list[CreativePortfolio] | None = None,
    ) -> RiskReport:
        """Evaluate risks for a single creative."""
        return self._evaluate_single(
            plan=scale_plan,
            portfolio=portfolio,
            total_budget=total_budget,
            all_portfolios=all_portfolios or [],
        )

    # ── Single Evaluation ──────────────────────────────────

    def _evaluate_single(
        self,
        plan: ScalePlan,
        portfolio: CreativePortfolio | None,
        total_budget: float,
        all_portfolios: list[CreativePortfolio],
    ) -> RiskReport:
        """Evaluate all risks for a single creative."""
        reasons: list[str] = []
        blocking = False

        # Risk 1: Budget Risk
        budget_risk = self._check_budget_risk(
            plan.target_budget, total_budget
        )
        if budget_risk != RiskLevel.SAFE.value:
            reasons.append(
                f"BUDGET_RISK: {plan.creative_id} budget=${plan.target_budget:.0f} "
                f"exceeds {MAX_CREATIVE_BUDGET_RATIO:.0%} of total=${total_budget:.0f}"
            )
            if budget_risk == RiskLevel.CRITICAL.value:
                blocking = True

        # Risk 2: Scale Risk
        scale_risk = self._check_scale_risk(
            plan.current_budget, plan.target_budget
        )
        if scale_risk != RiskLevel.SAFE.value:
            reasons.append(
                f"SCALE_RISK: {plan.creative_id} increase "
                f"${plan.current_budget:.0f}→${plan.target_budget:.0f} "
                f"exceeds {MAX_DAILY_SCALE_MULTIPLIER}x limit"
            )
            if scale_risk == RiskLevel.CRITICAL.value:
                blocking = True

        # Risk 3: Diversity Risk (HHI)
        hhi = self._calculate_hhi(all_portfolios)
        diversity_risk = self._check_diversity_risk(hhi)
        if diversity_risk != RiskLevel.SAFE.value:
            reasons.append(
                f"DIVERSITY_RISK: HHI={hhi:.3f} exceeds threshold "
                f"{DIVERSITY_HHI_THRESHOLD} (archetype concentration)"
            )
            if diversity_risk == RiskLevel.CRITICAL.value:
                blocking = True

        return RiskReport(
            risk_id=f"RR_{uuid.uuid4().hex[:8]}",
            creative_id=plan.creative_id,
            budget_risk=budget_risk,
            scale_risk=scale_risk,
            diversity_risk=diversity_risk,
            hhi_score=round(hhi, 4),
            blocking=blocking,
            reason="; ".join(reasons) if reasons else "All checks passed",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── Risk 1: Budget Risk ────────────────────────────────

    def _check_budget_risk(
        self, creative_budget: float, total_budget: float
    ) -> str:
        """Check if single creative budget exceeds limit.

        Returns:
            SAFE: within limit
            WARNING: at 25-30%
            CRITICAL: over 30%
        """
        if total_budget <= 0:
            return RiskLevel.SAFE.value

        ratio = creative_budget / total_budget

        if ratio > MAX_CREATIVE_BUDGET_RATIO:
            return RiskLevel.CRITICAL.value
        elif ratio > MAX_CREATIVE_BUDGET_RATIO * 0.85:
            return RiskLevel.WARNING.value
        return RiskLevel.SAFE.value

    # ── Risk 2: Scale Risk ─────────────────────────────────

    def _check_scale_risk(
        self, current_budget: float, target_budget: float
    ) -> str:
        """Check if budget increase exceeds safe limit.

        Returns:
            SAFE: increase <= 2x
            WARNING: increase 1.5-2x
            CRITICAL: increase > 2x
        """
        if current_budget <= 0:
            return RiskLevel.SAFE.value

        multiplier = target_budget / current_budget

        if multiplier > MAX_DAILY_SCALE_MULTIPLIER:
            return RiskLevel.CRITICAL.value
        elif multiplier > MAX_DAILY_SCALE_MULTIPLIER * 0.75:
            return RiskLevel.WARNING.value
        return RiskLevel.SAFE.value

    # ── Risk 3: Diversity Risk (HHI) ───────────────────────

    def _calculate_hhi(
        self, portfolios: list[CreativePortfolio]
    ) -> float:
        """Calculate Herfindahl-Hirschman Index for archetype concentration.

        HHI = Σ(budget_share²) for each archetype.
        HHI = 1.0 means 100% in one archetype.
        HHI → 0 means evenly distributed.

        Args:
            portfolios: All portfolio entries (must have archetype and allocated_budget)

        Returns:
            HHI score (0.0 to 1.0)
        """
        if not portfolios:
            return 0.0

        # Aggregate budget by archetype
        arch_budget: dict[str, float] = {}
        total_budget = 0.0

        for p in portfolios:
            arch = p.archetype or "unknown"
            arch_budget[arch] = arch_budget.get(arch, 0.0) + p.allocated_budget
            total_budget += p.allocated_budget

        if total_budget <= 0:
            return 0.0

        # Calculate HHI
        hhi = sum(
            (budget / total_budget) ** 2
            for budget in arch_budget.values()
        )

        return hhi

    def _check_diversity_risk(self, hhi: float) -> str:
        """Check HHI against threshold.

        Returns:
            SAFE: HHI <= 0.3
            WARNING: 0.3 < HHI <= 0.5
            CRITICAL: HHI > 0.5
        """
        if hhi > DIVERSITY_HHI_THRESHOLD:
            return RiskLevel.CRITICAL.value
        elif hhi > DIVERSITY_HHI_THRESHOLD * 0.6:
            return RiskLevel.WARNING.value
        return RiskLevel.SAFE.value

    # ── Quick Checks (for GrowthOrchestrator) ──────────────

    def is_scale_safe(
        self, current_budget: float, target_budget: float
    ) -> bool:
        """Quick check: is this scale step safe?"""
        return self._check_scale_risk(current_budget, target_budget) == RiskLevel.SAFE.value

    def is_budget_safe(
        self, creative_budget: float, total_budget: float
    ) -> bool:
        """Quick check: is budget allocation safe?"""
        return self._check_budget_risk(creative_budget, total_budget) == RiskLevel.SAFE.value

    def is_diversified(
        self, portfolios: list[CreativePortfolio]
    ) -> bool:
        """Quick check: is portfolio diversified?"""
        hhi = self._calculate_hhi(portfolios)
        return hhi <= DIVERSITY_HHI_THRESHOLD

    # ── Summary ────────────────────────────────────────────

    def get_risk_summary(
        self, reports: list[RiskReport]
    ) -> dict[str, Any]:
        """Get summary of risk evaluation."""
        blocking = sum(1 for r in reports if r.blocking)
        safe = sum(1 for r in reports if not r.blocking)

        budget_risks = {"SAFE": 0, "WARNING": 0, "CRITICAL": 0}
        scale_risks = {"SAFE": 0, "WARNING": 0, "CRITICAL": 0}
        diversity_risks = {"SAFE": 0, "WARNING": 0, "CRITICAL": 0}

        for r in reports:
            budget_risks[r.budget_risk] = budget_risks.get(r.budget_risk, 0) + 1
            scale_risks[r.scale_risk] = scale_risks.get(r.scale_risk, 0) + 1
            diversity_risks[r.diversity_risk] = diversity_risks.get(r.diversity_risk, 0) + 1

        avg_hhi = (
            sum(r.hhi_score for r in reports) / max(1, len(reports))
            if reports else 0.0
        )

        return {
            "total_reports": len(reports),
            "blocking": blocking,
            "safe": safe,
            "blocking_rate": round(blocking / max(1, len(reports)), 3),
            "by_risk_type": {
                "budget_risk": budget_risks,
                "scale_risk": scale_risks,
                "diversity_risk": diversity_risks,
            },
            "avg_hhi": round(avg_hhi, 4),
            "thresholds": {
                "max_creative_budget_ratio": MAX_CREATIVE_BUDGET_RATIO,
                "max_daily_scale_multiplier": MAX_DAILY_SCALE_MULTIPLIER,
                "diversity_hhi_threshold": DIVERSITY_HHI_THRESHOLD,
            },
        }