"""
E16.6.8 — ASO Brief Generator.

Transforms ASO insights (CVR drop, weak screenshot, weak icon) into
structured ``ASOCreativeBrief`` records that drive generation.

Each insight type maps to a specific creative objective + visual direction:
  * CVR drop + screenshot weak → CLARIFY_GAMEPLAY (show core loop)
  * Icon weak → IMPROVE_FIRST_IMPRESSION (character focus)
  * Strong keyword opportunity → TARGET_KEYWORD (keyword-themed visual)
"""

from __future__ import annotations

from typing import Optional

from src.aso_intelligence.creative_generator.models import (
    ASOCreativeBrief,
    BriefObjective,
    StoreAssetType,
)


class ASOBriefGenerator:
    """Generate creative briefs from ASO intelligence signals."""

    # ------------------------------------------------------------------ #
    def generate(
        self,
        game_id: str,
        source_insight: str,
        source_data: dict = None,
        country: str = "US",
    ) -> Optional[ASOCreativeBrief]:
        """Generate a creative brief from an ASO insight.

        ``source_insight`` can be:
          * "screenshot_hook_weak" — first screenshot hook score < 0.5
          * "screenshot_clarity_weak" — gameplay clarity < 0.5
          * "icon_focus_weak" — icon character visibility < 0.4
          * "cvr_drop" — store conversion rate declined
          * "keyword_opportunity" — high-value keyword detected
        """
        insight = (source_insight or "").lower()

        # --- Screenshot hook weak → show rewarding gameplay ---
        if "screenshot" in insight and "hook" in insight:
            return self._brief(
                game_id=game_id,
                asset=StoreAssetType.SCREENSHOT,
                objective=BriefObjective.SHOW_REWARD,
                audience="Casual merge game players",
                country=country,
                key_message="Experience satisfying merges and epic upgrades",
                visual_direction=(
                    "Show merge transformation before/after with clear "
                    "character progression and reward indicators"
                ),
                source=source_insight,
                data=source_data,
            )

        # --- Screenshot clarity weak → clarify gameplay ---
        if "screenshot" in insight and "clarity" in insight:
            return self._brief(
                game_id=game_id,
                asset=StoreAssetType.SCREENSHOT,
                objective=BriefObjective.CLARIFY_GAMEPLAY,
                audience="New players unfamiliar with merge mechanics",
                country=country,
                key_message="Easy to learn, satisfying to master",
                visual_direction=(
                    "Show the core merge loop clearly: 2 items → 1 upgraded item "
                    "with a visible power-up. Keep UI minimal."
                ),
                source=source_insight,
                data=source_data,
            )

        # --- Screenshot weak (general) → CVR-focused ---
        if "screenshot" in insight:
            return self._brief(
                game_id=game_id,
                asset=StoreAssetType.SCREENSHOT,
                objective=BriefObjective.INCREASE_CVR,
                audience="Store browsers looking for fun games",
                country=country,
                key_message="Endless merge fun awaits!",
                visual_direction=(
                    "Bright, colourful screenshot showing the most appealing "
                    "merge moment with clear progression hook"
                ),
                source=source_insight,
                data=source_data,
            )

        # --- Icon weak → first impression ---
        if "icon" in insight:
            return self._brief(
                game_id=game_id,
                asset=StoreAssetType.ICON,
                objective=BriefObjective.IMPROVE_FIRST_IMPRESSION,
                audience="All store visitors",
                country=country,
                key_message="Instantly recognisable character",
                visual_direction=(
                    "Character face taking >50% of icon area, expressive eyes, "
                    "high contrast background, minimal text"
                ),
                source=source_insight,
                data=source_data,
            )

        # --- CVR drop → general screenshot optimisation ---
        if "cvr" in insight:
            return self._brief(
                game_id=game_id,
                asset=StoreAssetType.SCREENSHOT,
                objective=BriefObjective.INCREASE_CVR,
                audience="Store browsers",
                country=country,
                key_message="Compelling reason to install",
                visual_direction=(
                    "Show the most exciting moment in the game with clear "
                    "value proposition and progress indicator"
                ),
                source=source_insight,
                data=source_data,
            )

        # --- Keyword opportunity → keyword-themed ---
        if "keyword" in insight:
            return self._brief(
                game_id=game_id,
                asset=StoreAssetType.SCREENSHOT,
                objective=BriefObjective.TARGET_KEYWORD,
                audience=f"Users searching for {source_data.get('keyword', 'relevant terms')}",
                country=country,
                key_message="Exactly what you're looking for",
                visual_direction=(
                    "Create screenshot that visually represents the keyword's "
                    "intent with matching gameplay moment"
                ),
                source=source_insight,
                data=source_data,
            )

        return None

    # ------------------------------------------------------------------ #
    def _brief(
        self,
        game_id: str,
        asset: StoreAssetType,
        objective: BriefObjective,
        audience: str,
        country: str,
        key_message: str,
        visual_direction: str,
        source: str,
        data: dict = None,
    ) -> ASOCreativeBrief:
        return ASOCreativeBrief(
            game_id=game_id,
            asset_type=asset,
            objective=objective,
            audience=audience,
            country=country,
            key_message=key_message,
            visual_direction=visual_direction,
            source_insight=source,
            source_data=data or {},
        )


__all__ = ["ASOBriefGenerator"]
