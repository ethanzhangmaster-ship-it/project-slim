"""
E15.1.2 — Product Spec Generator
=================================

MarketOpportunity + SuccessPattern priors  ->  ProductSpec
ProductSpec.to_game_product()              ->  GameProduct (enters fleet)

This is the "AI decides what to build next" step. Fully deterministic:
theme/keyword/monetization choices come from fixed tables + mined
pattern weights, never from an LLM.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from operation.publishing_factory.catalog.product_profile import GameProduct

from .models import MarketOpportunity, ProductSpec, SuccessPattern

# deterministic theme fallback per genre (used when opportunity has none)
_GENRE_THEMES: Dict[str, str] = {
    "merge": "fantasy", "puzzle": "zen", "idle": "tycoon",
    "word": "travel", "casual": "candy", "simulation": "hospital",
    "action": "hero",
}

# deterministic keyword seeds: (genre, theme) -> aso keywords
_THEME_KW: Dict[str, List[str]] = {
    "fantasy": ["magic", "witch", "castle"],
    "zen": ["relax", "calm"],
    "tycoon": ["empire", "profit"],
    "travel": ["journey", "world"],
    "candy": ["sweet", "pop"],
    "hospital": ["doctor", "clinic"],
    "hero": ["battle", "epic"],
    "witch": ["magic", "witch", "spell"],
}

# monetization defaults per genre when no pattern prior exists
_GENRE_MONETIZATION: Dict[str, str] = {
    "merge": "hybrid", "puzzle": "iaa", "idle": "hybrid",
    "word": "iaa", "casual": "iaa", "simulation": "hybrid",
    "action": "hybrid",
}

_MIN_SCORE = 0.35        # opportunities below this are not worth building


class SpecGenerator:
    """Turns ranked opportunities into concrete production orders."""

    def __init__(self, patterns: Optional[List[SuccessPattern]] = None):
        self.patterns = list(patterns or [])

    # ------------------------------------------------------------------ #
    def _prior(self, genre: str, theme: str) -> Optional[SuccessPattern]:
        """Best matching mined pattern (exact genre; theme match preferred)."""
        cands = [p for p in self.patterns if p.genre == genre]
        if not cands:
            return None
        themed = [p for p in cands if p.theme and p.theme == theme]
        pool = themed or cands
        return max(pool, key=lambda p: (p.success_rate, p.sample))

    # ------------------------------------------------------------------ #
    def generate(self, opp: MarketOpportunity,
                 seq: int = 1) -> Optional[ProductSpec]:
        """One opportunity -> one spec (or None if below threshold)."""
        base = opp.score()
        if base < _MIN_SCORE:
            return None

        theme = opp.theme or _GENRE_THEMES.get(opp.genre, "candy")
        prior = self._prior(opp.genre, theme)

        monetization = _GENRE_MONETIZATION.get(opp.genre, "iaa")
        rewarded = True
        starter = monetization in ("iap", "hybrid")
        notes: List[str] = []
        confidence = base
        if prior is not None:
            confidence = round(min(1.0, base * prior.weight), 4)
            if prior.monetization:
                monetization = prior.monetization
            rewarded = prior.rewarded_focus or rewarded
            notes.append(
                f"prior {prior.pattern_id}: success_rate="
                f"{prior.success_rate:.2f} over {prior.sample} game(s), "
                f"weight x{prior.weight:.2f}")

        kw = [f"{opp.genre} {w}" for w in _THEME_KW.get(theme, ["fun"])[:2]]
        kw += _THEME_KW.get(theme, ["fun"])[:3]
        # dedupe, keep order
        seen, keywords = set(), []
        for k in kw:
            if k not in seen:
                seen.add(k)
                keywords.append(k)

        title = f"{opp.genre.title()} {theme.title()}"
        return ProductSpec(
            spec_id=f"spec_{opp.genre}_{theme}_{seq:03d}",
            opportunity_id=opp.opportunity_id,
            genre=opp.genre,
            theme=theme,
            target_geos=list(opp.target_geos),
            monetization=monetization,
            rewarded_focus=rewarded,
            starter_pack=starter,
            aso_keywords=keywords,
            working_title=title,
            confidence=confidence,
            pattern_notes=notes,
        )

    # ------------------------------------------------------------------ #
    def generate_batch(self, opportunities: List[MarketOpportunity],
                       capacity: int = 3) -> List[ProductSpec]:
        """Top-N specs constrained by production capacity."""
        specs: List[ProductSpec] = []
        for i, opp in enumerate(opportunities, start=1):
            if len(specs) >= capacity:
                break
            spec = self.generate(opp, seq=i)
            if spec is not None:
                specs.append(spec)
        return specs

    # ------------------------------------------------------------------ #
    @staticmethod
    def to_game_product(spec: ProductSpec) -> GameProduct:
        """Spec -> fleet-ready GameProduct (status=development)."""
        game_id = spec.spec_id.replace("spec_", "g_")
        return GameProduct(
            game_id=game_id,
            package_name=f"com.leanfactory.{spec.genre}.{spec.theme}",
            display_name=spec.working_title,
            platforms=["google_play", "app_store"],
            genre=spec.genre,
            monetization=spec.monetization,
            status="development",
            keywords=list(spec.aso_keywords),
            locales=["en-US"] + (["ja-JP"] if "JP" in spec.target_geos else []),
        )


__all__ = ["SpecGenerator"]
