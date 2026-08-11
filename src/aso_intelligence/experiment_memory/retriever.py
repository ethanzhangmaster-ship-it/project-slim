"""
E16.6.4 — ASO Pattern Retriever (the "future decision" booster).

Closes the ASO Evolution Loop: when the ASO Analyzer detects a problem (e.g.
"Screenshot weak"), it asks the retriever for precedent. The retriever matches
historical ``ASOPattern`` records stored for the game's category + the detected
condition, ranks them by score, and — if a validated pattern exists — returns a
``GrowthAction`` whose confidence is *boosted* by the historical evidence.

This is how E16.6.4 plugs back into the shared Growth Decision Layer (E16.1 /
E13.3): a memory-validated ASO move enters the same Decision Validator /
Executor pipeline as every other Brain agent's action.

Pipeline:

    ASO Analyzer  →  Action (draft)
            ↓
    Pattern Retriever  →  historical confidence boost
            ↓
    GrowthAction (ASOAction, confidence = "historical pattern validated")
            ↓
    E16.1 Decision Validator  →  E13.3 Executor
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOExperimentAction,
    ASOPattern,
)
from src.aso_intelligence.experiment_memory.experiment_store import ASOExperimentStore
from src.aso_intelligence.experiment_memory.scorer import ASOPatternScorer
from src.aso_intelligence.models import ASOAction
from src.revenue_intelligence.models import GrowthAction


# Map an experiment action (E16.6.4 vocabulary) → the shared ASOAction enum
# that the Growth Decision Layer understands.
_ACTION_TO_ASO: Dict[str, ASOAction] = {
    ASOExperimentAction.UPDATE_ICON.value: ASOAction.UPDATE_ICON,
    ASOExperimentAction.UPDATE_SCREENSHOT.value: ASOAction.UPDATE_SCREENSHOT,
    ASOExperimentAction.UPDATE_TITLE.value: ASOAction.UPDATE_TITLE,
    ASOExperimentAction.ADD_KEYWORD.value: ASOAction.ADD_KEYWORD,
}


def _as_enum_value(action: object) -> str:
    """Normalise an action argument (str | Enum) to its string value."""
    if isinstance(action, Enum):
        return action.value
    return str(action)


class ASOPatternRetriever:
    """Retrieves & ranks historical ASO patterns, and emits validated actions."""

    def __init__(
        self,
        store: ASOExperimentStore,
        scorer: Optional[ASOPatternScorer] = None,
    ):
        self.store = store
        self.scorer = scorer or ASOPatternScorer()

    # ------------------------------------------------------------------ #
    def _match(
        self,
        pattern: ASOPattern,
        category: Optional[str],
        condition: Optional[str],
        action: Optional[str],
    ) -> bool:
        cat_ok = category is None or pattern.category == category
        # substring both ways, case-insensitive, so "screenshot" matches
        # "SCREENSHOT_WEAK" and vice-versa
        if condition is None:
            cond_ok = True
        else:
            cq = condition.lower()
            cp = pattern.condition.lower()
            cond_ok = (cq in cp) or (cp in cq)
        act_ok = action is None or _as_enum_value(action) == pattern.action
        return cat_ok and cond_ok and act_ok

    def retrieve(
        self,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        action: Optional[object] = None,
    ) -> List[ASOPattern]:
        """Return stored patterns matching the query, ranked by score (best first)."""
        action_val = _as_enum_value(action) if action is not None else None
        matched = [
            p
            for p in self.store.load_patterns()
            if self._match(p, category, condition, action_val)
        ]
        return self.scorer.rank(matched)

    def recommend(
        self,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        action: Optional[object] = None,
    ) -> Optional[ASOPattern]:
        """Best matching pattern, or ``None`` if nothing is recorded."""
        ranked = self.retrieve(category, condition, action)
        return ranked[0] if ranked else None

    def recommend_confidence(
        self,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        action: Optional[object] = None,
    ) -> float:
        """Confidence of the best precedent (0.0 if none)."""
        pat = self.recommend(category, condition, action)
        return pat.confidence if pat else 0.0

    # ------------------------------------------------------------------ #
    def recommend_action(
        self,
        game_id: str,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        action: Optional[object] = None,
        *,
        source: str = "aso_experiment_memory",
    ) -> Optional[GrowthAction]:
        """Emit a memory-validated ``GrowthAction`` (or ``None``).

        The returned action's confidence is the historical pattern's
        confidence — i.e. the ASO Analyzer's draft gets a *boost* when a
        precedent exists. Routes straight into E16.1's Decision Validator.
        """
        pat = self.recommend(category, condition, action)
        if pat is None:
            return None

        aso_action = _ACTION_TO_ASO.get(
            pat.action, ASOAction.UPDATE_SCREENSHOT
        )
        impact = round(min(100.0, 40.0 + max(0.0, pat.reward) * 100.0), 2)

        return GrowthAction(
            game_id=game_id,
            action=aso_action,
            title=f"Apply validated ASO pattern: {pat.computed_id()}",
            rationale=(
                f"historical pattern validated "
                f"(n={pat.sample_size}, success {pat.success_rate:.0%}, "
                f"reward {pat.reward:+.1%}, LTV-aware)"
            ),
            evidence={
                "pattern_id": pat.computed_id(),
                "sample_size": pat.sample_size,
                "success_rate": pat.success_rate,
                "reward": pat.reward,
            },
            confidence=round(pat.confidence, 4),
            impact_score=impact,
            source=source,
        )


__all__ = ["ASOPatternRetriever"]
