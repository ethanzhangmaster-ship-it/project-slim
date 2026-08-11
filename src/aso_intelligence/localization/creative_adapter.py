"""
E16.6.9 — ASO Creative Adaptation (Screenshot / Visual Localization).

Connects to E16.6.8 Creative Generator. Adapts creative briefs for
different market preferences:

  * US → wide scenes, achievement moments, "CREATE YOUR EMPIRE"
  * JP → character expressions, collection moments, cute emotional triggers
  * KR → progression visuals, growth numbers, "최강의 왕국"
  * DE → strategic gameplay, clear UI, value demonstration
  * FR → discovery, magical scenes, charming aesthetics
  * BR → social gameplay, fun moments, vibrant colours
"""

from __future__ import annotations

from typing import Optional

from src.aso_intelligence.localization.models import (
    MarketProfile,
    LocalizedCreativeBrief,
)


class CreativeAdapter:
    """Adapt creative direction for different markets."""

    # ------------------------------------------------------------------ #
    def adapt_brief(
        self,
        original_brief_text: str,
        profile: MarketProfile,
    ) -> LocalizedCreativeBrief:
        """Generate a market-specific creative brief.

        The output drives E16.6.8's asset generation for this market.
        """
        mot = profile.motivation
        country = profile.country

        if mot == "achievement":
            return self._achievement_brief(country)
        elif mot == "collection":
            return self._collection_brief(country)
        elif mot == "progression":
            return self._progression_brief(country)
        elif mot == "strategy":
            return self._strategy_brief(country)
        elif mot == "discovery":
            return self._discovery_brief(country)
        elif mot == "social":
            return self._social_brief(country)
        else:
            return self._default_brief(country)

    # ------------------------------------------------------------------ #
    def _achievement_brief(self, country: str) -> LocalizedCreativeBrief:
        return LocalizedCreativeBrief(
            country=country,
            visual_direction=(
                "Wide gameplay scene showing character after major upgrade, "
                "with visible progress indicators and achievement badges. "
                "Epic scale with dramatic lighting."
            ),
            copy_style="Exciting, action-oriented, first-person empowerment",
            emotional_trigger="Pride and accomplishment",
            notes="US Primary: Show CREATE YOUR EMPIRE. Large scenes.",
        )

    def _collection_brief(self, country: str) -> LocalizedCreativeBrief:
        return LocalizedCreativeBrief(
            country=country,
            visual_direction=(
                "Close-up character expression with visible emotion. "
                "Show collection screen with multiple cute characters. "
                "Warm, soft color palette. Focus on character face >50% frame."
            ),
            copy_style="Emotional, warm, relationship-focused",
            emotional_trigger="Kawaii / attachment / healing",
            notes="JP Primary: かわいい仲間を集めよう. Character expressions.",
        )

    def _progression_brief(self, country: str) -> LocalizedCreativeBrief:
        return LocalizedCreativeBrief(
            country=country,
            visual_direction=(
                "Show numerical growth indicators (level, power score, "
                "ranking position). Before/after comparison with clear "
                "stat improvements. Bold colours, strong contrast."
            ),
            copy_style="Professional, competitive, goal-oriented",
            emotional_trigger="Competitive drive / status",
            notes="KR Primary: 최강의王国. Growth numbers visible.",
        )

    def _strategy_brief(self, country: str) -> LocalizedCreativeBrief:
        return LocalizedCreativeBrief(
            country=country,
            visual_direction=(
                "Clean UI screenshot showing strategic depth. "
                "Multiple upgrade paths visible. Resource management display. "
                "Clear value proposition with efficiency indicators."
            ),
            copy_style="Informative, value-focused, rational",
            emotional_trigger="Cleverness and mastery",
            notes="DE Primary: Strategic gameplay with clear UI.",
        )

    def _discovery_brief(self, country: str) -> LocalizedCreativeBrief:
        return LocalizedCreativeBrief(
            country=country,
            visual_direction=(
                "Show mysterious or unexplored game world. "
                "Magical elements with glowing effects. "
                "Sense of wonder and exploration. Artistic, charming style."
            ),
            copy_style="Poetic, evocative, wonder-filled",
            emotional_trigger="Curiosity and wonder",
            notes="FR Primary: Discovery and magic. Charming aesthetics.",
        )

    def _social_brief(self, country: str) -> LocalizedCreativeBrief:
        return LocalizedCreativeBrief(
            country=country,
            visual_direction=(
                "Show multiple characters interacting. "
                "Bright, vibrant colours. Social features visible "
                "(gifting, co-op, chat). Fun, casual atmosphere."
            ),
            copy_style="Friendly, inclusive, community-focused",
            emotional_trigger="Belonging and shared fun",
            notes="BR Primary: Social gameplay with friends.",
        )

    def _default_brief(self, country: str) -> LocalizedCreativeBrief:
        return LocalizedCreativeBrief(
            country=country,
            visual_direction="Core gameplay loop shown clearly",
            copy_style="Clear, benefit-focused",
            emotional_trigger="Interest",
        )


__all__ = ["CreativeAdapter"]
