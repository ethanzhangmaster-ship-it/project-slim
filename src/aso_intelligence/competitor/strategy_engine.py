"""
E16.6.10 — Competitor Strategy Engine.

Diagnoses WHY a competitor is growing and generates counter-strategies.
Connects competitor intelligence into the action pipeline:
  * E16.6.8 Creative Generator — competitive insight → test creative
  * E16.6.7 Keyword Intelligence — competitor keyword → keyword opportunity
  * E16.6.5 Growth Loop — counter-action → experiment
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.aso_intelligence.competitor.models import (
    CompetitorSnapshot,
    CompetitorChange,
    CompetitorChangeType,
    CompetitorDiagnosis,
)


class StrategyEngine:
    """Analyze competitor changes and generate strategic responses."""

    # ------------------------------------------------------------------ #
    def diagnose(
        self,
        app_id: str,
        changes: List[CompetitorChange],
        old: CompetitorSnapshot,
        new: CompetitorSnapshot,
    ) -> CompetitorDiagnosis:
        """Diagnose why a competitor is growing based on detected changes."""
        reasons: List[str] = []
        priority = "medium"
        action = "Monitor"

        change_types = {c.change_type for c in changes}

        if CompetitorChangeType.ICON_CHANGE in change_types:
            reasons.append(
                "Icon updated — potentially improved first impression "
                "and brand recognition"
            )
            action = "CREATE_ICON_EXPERIMENT"
            priority = "high"

        if CompetitorChangeType.SCREENSHOT_CHANGE in change_types:
            reasons.append(
                "Screenshot lineup changed — likely A/B testing new "
                "creative strategy"
            )
            action = "CREATE_SCREENSHOT_EXPERIMENT"
            priority = "high"

        if CompetitorChangeType.TITLE_CHANGE in change_types:
            reasons.append(
                "Title changed — keyword strategy adjustment detected"
            )
            if action == "Monitor":
                action = "EVALUATE_KEYWORD_ADOPTION"
            priority = "high"

        if CompetitorChangeType.KEYWORD_CHANGE in change_types:
            reasons.append(
                "Keywords modified — targeting new search terms"
            )
            priority = "medium"

        if CompetitorChangeType.RANKING_SURGE in change_types:
            reasons.append(
                f"Ranking surged {new.ranking_position - old.ranking_position} "
                f"positions — high growth momentum"
            )
            priority = "high"
            if action == "Monitor":
                action = "URGENT_REVIEW"

        if not reasons:
            reasons.append("No significant listing changes detected")
            action = "Monitor"
            priority = "low"

        # Confidence based on number and clarity of signals
        confidence = min(0.95, 0.5 + len(reasons) * 0.12)

        return CompetitorDiagnosis(
            app_id=app_id,
            possible_reasons=reasons,
            detected_changes=changes,
            confidence=round(confidence, 4),
            recommended_action=action,
            recommended_priority=priority,
        )

    # ------------------------------------------------------------------ #
    def connect_to_creative_generator(
        self, change: CompetitorChange
    ) -> Dict[str, str]:
        """Bridge competitor insight → Creative Generator brief (E16.6.8).

        Returns a dict that can be used to call ASOCreativeGeneratorAgent.
        """
        if change.change_type == CompetitorChangeType.ICON_CHANGE:
            return {
                "source_insight": "competitor_icon_change",
                "description": (
                    f"Competitor {change.app_id} updated icon — "
                    f"test new icon direction"
                ),
            }
        elif change.change_type == CompetitorChangeType.SCREENSHOT_CHANGE:
            return {
                "source_insight": "competitor_screenshot_change",
                "description": (
                    f"Competitor {change.app_id} changed screenshot lineup — "
                    f"test similar creative approach"
                ),
            }
        return {
            "source_insight": "competitor_change",
            "description": f"Competitor {change.app_id} made changes",
        }

    # ------------------------------------------------------------------ #
    def connect_to_keyword_intelligence(
        self, change: CompetitorChange
    ) -> Optional[Dict[str, Any]]:
        """Bridge competitor keyword change → Keyword Intelligence (E16.6.7).

        Returns keyword data that can be fed to ASOKeywordAgent.
        """
        if change.change_type != CompetitorChangeType.TITLE_CHANGE:
            return None

        # Extract potential new keywords from the title change
        old_words = set(change.old_value.lower().split())
        new_words = set(change.new_value.lower().split())
        added = new_words - old_words

        if not added:
            return None

        return {
            "keyword": list(added),
            "source": f"competitor:{change.app_id}",
            "reason": f"Competitor added '{', '.join(added)}' to title",
        }

    # ------------------------------------------------------------------ #
    def generate_action(
        self, diagnosis: CompetitorDiagnosis
    ) -> Dict[str, Any]:
        """Generate a counter-action based on diagnosis."""
        return {
            "game_id": diagnosis.app_id,  # placeholder, caller should override
            "action": diagnosis.recommended_action,
            "priority": diagnosis.recommended_priority,
            "confidence": diagnosis.confidence,
            "reasons": diagnosis.possible_reasons,
        }


__all__ = ["StrategyEngine"]
