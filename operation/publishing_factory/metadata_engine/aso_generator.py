"""
E15.1.1 — ASO Generator
========================

Deterministic App Store Optimization pack generator.

Produces, from a GameProduct profile:
  - title       (<=30 chars, brand + top keyword)
  - subtitle    (<=30 chars, secondary keyword phrase)
  - keywords    (ranked list, genre-seeded + competitor hints)
  - rationale   (why each piece was chosen — for human review)

No LLM: template + seed tables + competitor hint injection.
The keyword_optimizer (same package) then scores/budgets them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from operation.publishing_factory.catalog.product_profile import GameProduct

_TITLE_MAX = 30
_SUB_MAX = 30

# Seed keyword banks per genre (deterministic).
_SEED_KW: Dict[str, List[str]] = {
    "merge": ["merge", "magic", "dragon", "puzzle", "castle", "combine"],
    "puzzle": ["puzzle", "brain", "match", "logic", "relax", "solve"],
    "idle": ["idle", "tycoon", "clicker", "mine", "factory", "upgrade"],
    "word": ["word", "spell", "vocabulary", "crossword", "letters", "quiz"],
    "casual": ["casual", "fun", "free", "relax", "easy", "game"],
    "simulation": ["sim", "build", "city", "farm", "manage", "tycoon"],
    "action": ["action", "battle", "hero", "fight", "rpg", "war"],
}


@dataclass
class AsoPack:
    game_id: str
    title: str
    subtitle: str
    keywords: List[str] = field(default_factory=list)
    rationale: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "title": self.title,
                "subtitle": self.subtitle, "keywords": list(self.keywords),
                "rationale": dict(self.rationale)}


class AsoGenerator:
    """Builds a store-ready ASO pack (title/subtitle/keywords)."""

    def generate(self, product: GameProduct,
                 competitor_hints: List[str] = None) -> AsoPack:
        name = product.display_name or product.game_id
        seeds = list(_SEED_KW.get(product.genre, _SEED_KW["casual"]))
        if competitor_hints:
            seeds = competitor_hints[:2] + seeds  # top hints first

        # title = brand + #1 keyword, hard-capped
        title = name
        if seeds:
            cand = f"{name}: {seeds[0].title()}"
            title = cand if len(cand) <= _TITLE_MAX else name[:_TITLE_MAX]

        # subtitle = 2nd+3rd keyword phrase
        sub_words = [w.title() for w in seeds[1:3]]
        subtitle = " ".join(sub_words)[:_SUB_MAX]

        rationale = {
            "title": f"brand '{name}' + top keyword '{seeds[0] if seeds else ''}'",
            "subtitle": "secondary keywords " + ", ".join(seeds[1:3]),
            "keywords": f"genre seed bank for '{product.genre}'",
        }
        return AsoPack(game_id=product.game_id, title=title,
                       subtitle=subtitle, keywords=seeds, rationale=rationale)


__all__ = ["AsoGenerator", "AsoPack", "_TITLE_MAX", "_SUB_MAX"]
