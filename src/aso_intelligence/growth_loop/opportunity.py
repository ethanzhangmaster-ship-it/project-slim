"""
E16.6.5 — ASO Opportunity Aggregator.

Combines signals from three source modules into ranked growth opportunities:

* ``aso_reality`` — CVR drops, install declines, ranking changes (E16.6.2)
* ``creative_optimization`` — visual feature weakness (E16.6.3)
* ``experiment_memory`` — historical pattern validation (E16.6.4)

Each ``ASOOpportunity`` records which sources contributed and at what
confidence, so the Priority Engine can make informed trade-offs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.aso_intelligence.growth_loop.models import ASOOpportunity


# Minimum signal strength to consider
_MIN_SIGNAL = 0.05


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Signal helpers
# --------------------------------------------------------------------------- #
def _screenshot_opportunities(
    game_id: str,
    screenshot_hook: Optional[float],
    screenshot_clarity: Optional[float],
    creative_confidence: float,
) -> List[ASOOpportunity]:
    """Create opportunities from Creative Optimization signals."""
    ops: List[ASOOpportunity] = []

    # Hook Score weak (< 0.5)
    if screenshot_hook is not None and screenshot_hook < 0.5:
        weakness = 1.0 - screenshot_hook  # 0.5 → 0.5, 0.3 → 0.7
        opp = ASOOpportunity(
            opportunity_id=f"scr_hook_{game_id}",
            game_id=game_id,
            title="First Screenshot Hook Score Weak",
            description=(
                f"First screenshot hook score is {screenshot_hook:.2f}, "
                f"below 0.5 threshold."
            ),
            source_signals={
                "creative_optimization": weakness * creative_confidence,
            },
            impact=round(weakness * 0.8, 4),
            confidence=creative_confidence,
            revenue_potential=0.7,
            urgency=0.6,
            cost=0.5,
            suggested_action="UPDATE_SCREENSHOT",
        )
        opp.compute_priority()
        ops.append(opp)

    # Gameplay Clarity weak
    if screenshot_clarity is not None and screenshot_clarity < 0.5:
        weakness = 1.0 - screenshot_clarity
        opp = ASOOpportunity(
            opportunity_id=f"scr_clarity_{game_id}",
            game_id=game_id,
            title="Screenshot Gameplay Clarity Low",
            description=(
                f"Screenshot gameplay clarity is {screenshot_clarity:.2f}, "
                f"below 0.5 threshold."
            ),
            source_signals={
                "creative_optimization": weakness * creative_confidence,
            },
            impact=round(weakness * 0.7, 4),
            confidence=creative_confidence,
            revenue_potential=0.6,
            urgency=0.5,
            cost=0.5,
            suggested_action="UPDATE_SCREENSHOT",
        )
        opp.compute_priority()
        ops.append(opp)

    return ops


def _icon_opportunities(
    game_id: str,
    icon_focus: Optional[float],
    creative_confidence: float,
) -> List[ASOOpportunity]:
    """Create opportunities from Icon feature weakness."""
    ops: List[ASOOpportunity] = []
    if icon_focus is not None and icon_focus < 0.4:
        weakness = 1.0 - icon_focus
        opp = ASOOpportunity(
            opportunity_id=f"icon_focus_{game_id}",
            game_id=game_id,
            title="Icon Character Focus Weak",
            description=(
                f"Icon character visibility is {icon_focus:.2f}, "
                f"below 0.4 threshold."
            ),
            source_signals={
                "creative_optimization": weakness * creative_confidence,
            },
            impact=round(weakness * 0.75, 4),
            confidence=creative_confidence,
            revenue_potential=0.65,
            urgency=0.4,
            cost=0.4,
            suggested_action="UPDATE_ICON",
        )
        opp.compute_priority()
        ops.append(opp)
    return ops


def _reality_opportunities(
    game_id: str,
    cvr_drop: Optional[float],
    install_drop: Optional[float],
    ranking_drop: Optional[float],
) -> List[ASOOpportunity]:
    """Create opportunities from Reality signals (CVR/install/ranking changes)."""
    ops: List[ASOOpportunity] = []

    if cvr_drop is not None and cvr_drop > _MIN_SIGNAL:
        opp = ASOOpportunity(
            opportunity_id=f"cvr_drop_{game_id}",
            game_id=game_id,
            title="Store CVR Declining",
            description=(
                f"Store conversion rate dropped by {cvr_drop:.1%}."
            ),
            source_signals={"aso_reality": min(cvr_drop * 2.0, 1.0)},
            impact=round(min(cvr_drop * 1.5, 1.0), 4),
            confidence=0.85,
            revenue_potential=0.8,
            urgency=round(min(cvr_drop * 3.0, 1.0), 4),
            cost=0.5,
            suggested_action="UPDATE_SCREENSHOT",
        )
        opp.compute_priority()
        ops.append(opp)

    if install_drop is not None and install_drop > _MIN_SIGNAL:
        opp = ASOOpportunity(
            opportunity_id=f"install_drop_{game_id}",
            game_id=game_id,
            title="Store Installs Declining",
            description=(f"Installs dropped by {install_drop:.1%}."),
            source_signals={"aso_reality": min(install_drop * 1.5, 1.0)},
            impact=round(min(install_drop * 1.2, 1.0), 4),
            confidence=0.8,
            revenue_potential=0.75,
            urgency=round(min(install_drop * 2.0, 1.0), 4),
            cost=0.5,
            suggested_action="UPDATE_SCREENSHOT",
        )
        opp.compute_priority()
        ops.append(opp)

    if ranking_drop is not None and ranking_drop > _MIN_SIGNAL:
        opp = ASOOpportunity(
            opportunity_id=f"rank_drop_{game_id}",
            game_id=game_id,
            title="Category Ranking Dropped",
            description=(
                f"Category rank worsened by {ranking_drop:.1%}."
            ),
            source_signals={"aso_reality": min(ranking_drop * 1.2, 1.0)},
            impact=round(min(ranking_drop, 0.8), 4),
            confidence=0.75,
            revenue_potential=0.6,
            urgency=round(min(ranking_drop * 2.0, 1.0), 4),
            cost=0.5,
            suggested_action="UPDATE_ICON",
        )
        opp.compute_priority()
        ops.append(opp)

    return ops


def _memory_opportunities(
    game_id: str,
    historical_patterns: List[Any],
) -> List[ASOOpportunity]:
    """Create opportunities from Experiment Memory validated patterns."""
    ops: List[ASOOpportunity] = []
    for pat in historical_patterns:
        confidence = getattr(pat, "confidence", 0.0)
        reward = getattr(pat, "reward", 0.0)
        sample_size = getattr(pat, "sample_size", 0)
        action = getattr(pat, "action", "")
        condition = getattr(pat, "condition", "")
        category = getattr(pat, "category", "")

        if confidence < 0.1 or reward <= 0:
            continue

        # Historical pattern validated — high confidence boost
        opp = ASOOpportunity(
            opportunity_id=f"pattern_{getattr(pat, 'pattern_id', '')}",
            game_id=game_id,
            title=f"Validated Pattern: {action} for {condition}",
            description=(
                f"Historical pattern ({category}) yields {reward:+.1%} "
                f"revenue uplift (n={sample_size})."
            ),
            source_signals={
                "experiment_memory": confidence * min(reward * 5.0, 1.0),
            },
            impact=round(min(reward * 1.5, 0.95), 4),
            confidence=confidence,
            revenue_potential=round(min(reward * 2.0, 1.0), 4),
            urgency=0.5,
            cost=0.3,  # validated patterns are lower cost
            suggested_action=action,
        )
        opp.compute_priority()
        ops.append(opp)

    return ops


# --------------------------------------------------------------------------- #
# Aggregator
# --------------------------------------------------------------------------- #
class ASOOpportunityAggregator:
    """Aggregate signals from all ASO modules into ranked opportunities."""

    def aggregate(
        self,
        game_id: str,
        *,
        # Reality signals
        cvr_drop: Optional[float] = None,
        install_drop: Optional[float] = None,
        ranking_drop: Optional[float] = None,
        # Creative signals
        screenshot_hook: Optional[float] = None,
        screenshot_clarity: Optional[float] = None,
        icon_focus: Optional[float] = None,
        creative_confidence: float = 0.8,
        # Memory signals
        historical_patterns: Optional[List[Any]] = None,
    ) -> List[ASOOpportunity]:
        """Collect and return all detected opportunities."""
        ops: List[ASOOpportunity] = []

        ops.extend(_reality_opportunities(
            game_id, cvr_drop, install_drop, ranking_drop
        ))
        ops.extend(_screenshot_opportunities(
            game_id, screenshot_hook, screenshot_clarity, creative_confidence
        ))
        ops.extend(_icon_opportunities(
            game_id, icon_focus, creative_confidence
        ))
        if historical_patterns:
            ops.extend(_memory_opportunities(
                game_id, historical_patterns
            ))

        # Sort by priority descending
        ops.sort(key=lambda o: o.priority_score, reverse=True)
        return ops


__all__ = ["ASOOpportunityAggregator"]
