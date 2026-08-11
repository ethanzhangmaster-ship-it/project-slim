"""
E16.6.9 — ASO Copy Localization Generator.

This is NOT machine translation. It re-expresses store copy (title,
short description, full description) for each market's cultural context.

Each market's copy is driven by its ``MarketProfile.motivation``:
  * US → achievement (build, conquer, epic)
  * JP → collection (cute, raise, collect)
  * KR → progression (grow, strong, rank)
  * DE → strategy (plan, build, manage)
  * FR → discovery (magic, explore, mystery)
  * BR → social (friends, fun, share)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.localization.models import MarketProfile


# Title re-expression templates by motivation
_TITLE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "achievement": {
        "merge": "Merge {noun}: Build Your {goal}",
        "puzzle": "{noun} Puzzles: Conquer Every Challenge",
        "default": "{noun}: {verb} Your {goal}",
    },
    "collection": {
        "merge": "{adj}な{theme}と一緒に{verb}しよう",
        "puzzle": "{adj}パズルで{theme}を集めよう",
        "default": "{adj}な{theme}{noun}",
    },
    "progression": {
        "merge": "{noun} 합성: 최강의 {goal}로 성장하라",
        "puzzle": "{noun} 퍼즐: {goal}을 정복하라",
        "default": "{noun}: {goal}로의 {verb}",
    },
    "strategy": {
        "merge": "{noun} Merge: {verb} Your {goal} Strategically",
        "default": "{noun}: Master the Art of {theme}",
    },
    "discovery": {
        "merge": "{noun} Fusion: {verb} un Monde Magique",
        "default": "{noun}: {verb} l'Aventure",
    },
    "social": {
        "merge": "{noun}: {verb} com os Amigos",
        "default": "{noun} Divertido: {verb} com {theme}",
    },
}

# Short description templates by motivation
_SHORT_DESC_TEMPLATES: Dict[str, str] = {
    "achievement": (
        "{verb} epic creatures, {build} your {goal}, and become the "
        "ultimate champion in this {adj} {genre} adventure!"
    ),
    "collection": (
        "{adj}な{theme}を集めて、自分だけの{goal}を作りましょう。"
        "毎日新しい発見が待っています。"
    ),
    "progression": (
        "{noun}를 {verb}하고 최강의 {goal}로 성장하세요. "
        "끝없는 {theme}과 보상이 기다립니다!"
    ),
    "strategy": (
        "{verb} your {goal} with clever {theme}. "
        "Plan, {build}, and dominate in this {adj} {genre}."
    ),
    "discovery": (
        "{verb} un monde {adj} de {theme} et de magie. "
        "Chaque {noun} est une nouvelle aventure!"
    ),
    "social": (
        "{verb} com seus amigos, {build} seu {goal} e "
        "descubra um mundo {adj} de {theme}!"
    ),
}


class CopyGenerator:
    """Generate market-specific store copy — not translation, re-expression.

    Uses templates parameterised by game genre and market motivation.
    Callers provide the raw game data (noun, verb, goal, theme, adj, etc.)
    and the generator outputs the market-appropriate version.
    """

    def __init__(self):
        self.title_templates = _TITLE_TEMPLATES
        self.short_desc_templates = _SHORT_DESC_TEMPLATES

    # ------------------------------------------------------------------ #
    def adapt_title(
        self,
        en_title: str,
        profile: MarketProfile,
        genre: str = "merge",
        params: dict = None,
    ) -> str:
        """Generate a market-adapted title.

        ``params`` should contain:
          noun — game subject (e.g. "Witch", "Monster")
          goal — player goal (e.g. "Kingdom", "Empire")
          verb — action verb (e.g. "Build", "Collect")
          theme — game theme (e.g. "Magic", "Monsters")
          adj — adjective (e.g. "Epic", "Cute")
        """
        p = params or {}
        mot = profile.motivation
        templates = self.title_templates.get(mot, self.title_templates["achievement"])
        template = templates.get(genre, templates.get("default", "{noun}"))

        result = template.format(
            noun=p.get("noun", en_title),
            goal=p.get("goal", "Kingdom"),
            verb=p.get("verb", "Build"),
            theme=p.get("theme", "Magic"),
            adj=p.get("adj", "Epic"),
            genre=genre,
        )
        return result

    # ------------------------------------------------------------------ #
    def adapt_short_description(
        self,
        en_desc: str,
        profile: MarketProfile,
        genre: str = "merge",
        params: dict = None,
    ) -> str:
        """Generate a market-adapted short description."""
        p = params or {}
        mot = profile.motivation
        template = self.short_desc_templates.get(
            mot, self.short_desc_templates["achievement"]
        )

        result = template.format(
            noun=p.get("noun", "Creatures"),
            goal=p.get("goal", "Kingdom"),
            verb=p.get("verb", "Collect"),
            build=p.get("build", "build"),
            theme=p.get("theme", "magic"),
            adj=p.get("adj", "epic"),
            genre=genre,
        )
        return result

    # ------------------------------------------------------------------ #
    def adapt_full_description(
        self,
        en_full: str,
        profile: MarketProfile,
        params: dict = None,
    ) -> str:
        """Generate a market-adapted full description.

        For MVP, returns the short description as the full description.
        In production, this would generate a multi-paragraph adaptation.
        """
        return self.adapt_short_description(en_full, profile, params=params)

    # ------------------------------------------------------------------ #
    def adapt_all(
        self,
        en_title: str,
        en_short_desc: str,
        profile: MarketProfile,
        genre: str = "merge",
        params: dict = None,
    ) -> Dict[str, str]:
        """Convenience: adapt title + short desc + full desc for one market."""
        return {
            "title": self.adapt_title(en_title, profile, genre, params),
            "short_description": self.adapt_short_description(
                en_short_desc, profile, genre, params
            ),
            "full_description": self.adapt_full_description(
                en_short_desc, profile, params
            ),
        }


__all__ = ["CopyGenerator"]
