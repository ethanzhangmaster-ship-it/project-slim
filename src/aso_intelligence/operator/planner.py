"""
E16.6.13 — Operator Planner.

Generates ASOOperationPlan from insights detected by any E16.6 module.
Bridges: Intelligence (6.1), Keyword (6.7), Creative Generator (6.8),
Competitor War Room (6.10), Portfolio Manager (6.12).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_intelligence.operator.models import (
    ASOOperationPlan,
    ASOOperationState,
    RiskCategory,
    ApprovalLevel,
)


class OperatorPlanner:
    """Generate operation plans from ASO insights."""

    # ------------------------------------------------------------------ #
    def plan(
        self,
        game_id: str,
        market: str,
        insight_type: str,
        reason: str,
        *,
        expected_impact: float = 0.0,
        confidence: float = 0.0,
        source_module: str = "aso_intelligence",
        extra: dict = None,
    ) -> ASOOperationPlan:
        """Create a plan from an ASO insight.

        ``insight_type`` determines the action_type and risk level:
          * screenshot_weak → UPDATE_SCREENSHOT (medium)
          * icon_weak → UPDATE_ICON (medium)
          * keyword_opportunity → ADD_KEYWORD (low)
          * competitor_change → CREATE_EXPERIMENT (medium)
          * localization_opportunity → LOCALIZATION_UPDATE (medium)
          * portfolio_high_priority → OPTIMIZE_LISTING (low)
          * cvr_drop → UPDATE_SCREENSHOT (medium)
          * update_strategy → SCHEDULED_UPDATE (varies)
        """
        extra = extra or {}
        action_type, risk_cat, approval = self._classify(insight_type)

        plan = ASOOperationPlan(
            plan_id=str(uuid4()),
            game_id=game_id,
            market=market,
            action_type=action_type,
            reason=reason,
            expected_impact=expected_impact,
            confidence=confidence,
            risk_category=risk_cat,
            required_assets=extra.get("required_assets", []),
            source_modules=[source_module],
            state=ASOOperationState.DETECTED,
            approval_level=approval,
        )
        return plan

    # ------------------------------------------------------------------ #
    def _classify(
        self, insight_type: str
    ) -> tuple:
        """Map insight type → (action_type, RiskCategory, ApprovalLevel)."""
        mapping = {
            "screenshot_weak": (
                "UPDATE_SCREENSHOT", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM,
            ),
            "screenshot_clarity_weak": (
                "UPDATE_SCREENSHOT", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM,
            ),
            "icon_weak": (
                "UPDATE_ICON", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM,
            ),
            "keyword_opportunity": (
                "ADD_KEYWORD", RiskCategory.LOW, ApprovalLevel.AUTO,
            ),
            "keyword_gap": (
                "ADD_KEYWORD", RiskCategory.LOW, ApprovalLevel.AUTO,
            ),
            "competitor_change": (
                "CREATE_EXPERIMENT", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM,
            ),
            "competitor_surge": (
                "URGENT_REVIEW", RiskCategory.HIGH, ApprovalLevel.HUMAN_DECIDE,
            ),
            "localization_opportunity": (
                "LOCALIZATION_UPDATE", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM,
            ),
            "portfolio_high_priority": (
                "OPTIMIZE_LISTING", RiskCategory.LOW, ApprovalLevel.AUTO,
            ),
            "cvr_drop": (
                "UPDATE_SCREENSHOT", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM,
            ),
            "update_strategy_screenshot": (
                "SCHEDULED_SCREENSHOT", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM,
            ),
            "update_strategy_icon": (
                "SCHEDULED_ICON", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM,
            ),
            "update_strategy_keyword": (
                "KEYWORD_REFRESH", RiskCategory.LOW, ApprovalLevel.AUTO,
            ),
            "title_change": (
                "UPDATE_TITLE", RiskCategory.HIGH, ApprovalLevel.HUMAN_DECIDE,
            ),
        }
        key = insight_type.lower().replace(" ", "_")
        if key in mapping:
            return mapping[key]
        # Default: medium risk, human confirm
        return ("INVESTIGATE", RiskCategory.MEDIUM, ApprovalLevel.HUMAN_CONFIRM)


__all__ = ["OperatorPlanner"]
