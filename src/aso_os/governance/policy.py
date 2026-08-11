"""
E16.6.14 — ASO OS Governance: policies & approval routing.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_os.kernel.models import ASOGrowthScore


# Auto-approved sources (Level 1)
_AUTO_SOURCES = {"aso_keyword", "aso_intelligence", "aso_portfolio"}
# Needs human decision (Level 3)
_HUMAN_DECIDE_SOURCES = {"aso_competitor", "aso_update_strategy"}


class GovernancePolicy:
    """System-wide ASO policies."""

    MAX_CONCURRENT_EXPERIMENTS = 3
    MIN_COOLDOWN_DAYS = 14

    def check_concurrent_limit(
        self, active_count: int
    ) -> bool:
        return active_count < self.MAX_CONCURRENT_EXPERIMENTS

    def check_cooldown(
        self, days_since_update: int
    ) -> bool:
        return days_since_update >= self.MIN_COOLDOWN_DAYS

    def get_policies(self) -> Dict[str, Any]:
        return {
            "max_concurrent_experiments": self.MAX_CONCURRENT_EXPERIMENTS,
            "min_cooldown_days": self.MIN_COOLDOWN_DAYS,
            "auto_sources": sorted(_AUTO_SOURCES),
            "human_decide_sources": sorted(_HUMAN_DECIDE_SOURCES),
        }


class SystemApproval:
    """Approval routing — maps source modules to approval levels."""

    @staticmethod
    def needs_approval(score: ASOGrowthScore) -> str:
        """Returns 'auto' / 'human_confirm' / 'human_decide'."""
        source = score.source
        if source in _HUMAN_DECIDE_SOURCES:
            return "human_decide"
        if source in _AUTO_SOURCES:
            return "auto"
        return "human_confirm"

    @staticmethod
    def can_auto_execute(score: ASOGrowthScore) -> bool:
        return score.source in _AUTO_SOURCES


__all__ = ["GovernancePolicy", "SystemApproval"]
