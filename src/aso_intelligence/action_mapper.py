"""
E16.6.1 — ASO Action Mapper: ASOInsight -> GrowthAction.

Translates each discovered ASO insight into a single, executor-ready
``GrowthAction`` whose ``action`` field carries an ``ASOAction`` enum member.
This is the seam that lets the ASO Brain (third Brain) inject recommendations
into the SAME ``DecisionValidator`` / Growth Executor pipeline as the Revenue
Brain (E16.1) and Economy Brain (E16.2).

The ASO Agent never executes — it only emits. The Growth Decision Layer gates
and routes.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.revenue_intelligence.models import GrowthAction

from .models import ASOAction, ASOInsight, ASOInsightType


# insight type -> (ASOAction, default title verb)
_INSIGHT_ACTION: Dict[ASOInsightType, ASOAction] = {
    ASOInsightType.LISTING_CONVERSION_DROP: ASOAction.UPDATE_SCREENSHOT,
    ASOInsightType.LISTING_FATIGUE: ASOAction.UPDATE_SCREENSHOT,
    ASOInsightType.MISSING_KEYWORD: ASOAction.ADD_KEYWORD,
    ASOInsightType.KEYWORD_OPPORTUNITY: ASOAction.ADD_KEYWORD,
    ASOInsightType.REVIEW_KEYWORD_SIGNAL: ASOAction.ADD_KEYWORD,
    ASOInsightType.SCREENSHOT_WEAK: ASOAction.UPDATE_SCREENSHOT,
    ASOInsightType.ICON_OPTIMIZATION: ASOAction.UPDATE_ICON,
    ASOInsightType.COMPETITOR_CHANGE: ASOAction.CREATE_EXPERIMENT,
}


class ASOActionMapper:
    """Maps ASOInsight objects into GrowthActions."""

    def to_action(self, insight: ASOInsight) -> Optional[GrowthAction]:
        action_enum = _INSIGHT_ACTION.get(insight.insight_type)
        if action_enum is None:
            return None

        evidence = dict(insight.evidence)
        evidence["insight_type"] = insight.insight_type.value
        kw = evidence.get("keyword")
        title = insight.recommendation or insight.description
        if kw and action_enum in (ASOAction.ADD_KEYWORD, ASOAction.REMOVE_KEYWORD):
            title = f"ASO: add keyword '{kw}'"

        return GrowthAction(
            game_id=insight.game_id,
            action=action_enum,
            title=title[:160],
            rationale=insight.description,
            evidence=evidence,
            confidence=insight.confidence,
            impact_score=insight.impact_score,
            source="aso_intelligence",
        )

    def map_all(self, insights: List[ASOInsight]) -> List[GrowthAction]:
        actions: List[GrowthAction] = []
        for ins in insights:
            a = self.to_action(ins)
            if a is not None:
                actions.append(a)
        return actions


__all__ = ["ASOActionMapper", "_INSIGHT_ACTION"]
