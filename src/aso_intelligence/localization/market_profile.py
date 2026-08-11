"""
E16.6.9 — Market Profile Repository.

Built-in market profiles for key IAP game markets. Each profile captures:
  * Player motivation (what drives installs and purchases)
  * Preferred keyword themes
  * Communication tone
  * Monetisation behaviour

Markets: US, JP, KR, DE, FR, BR — extensible via ``register()``.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.localization.models import MarketProfile


# --------------------------------------------------------------------------- #
# Built-in profiles
# --------------------------------------------------------------------------- #
_BUILTIN: Dict[str, MarketProfile] = {
    "US": MarketProfile(
        country="US",
        language="en",
        motivation="achievement",
        preferred_words=["adventure", "collection", "merge", "battle",
                         "epic", "quest", "build", "create", "legendary"],
        avoided_words=[" boring", "grind", "pay"],
        monetization_traits=["high_iap", "reward_ad_acceptable"],
        tone="exciting",
    ),
    "JP": MarketProfile(
        country="JP",
        language="ja",
        motivation="collection",
        preferred_words=["かわいい", "育成", "癒し", "仲間", "冒険",
                         "魔法", "合成", "成長", "集める"],
        avoided_words=["難しい", "課金", "時間がかかる"],
        monetization_traits=["high_iap", "premium_quality",
                             "gacha_friendly"],
        tone="emotional",
    ),
    "KR": MarketProfile(
        country="KR",
        language="ko",
        motivation="progression",
        preferred_words=["성장", "보상", "수집", "강함", "최강",
                         "전투", "진화", "랭킹"],
        avoided_words=["지루한", "사기", "과금"],
        monetization_traits=["competitive_iap", "whale_friendly"],
        tone="professional",
    ),
    "DE": MarketProfile(
        country="DE",
        language="de",
        motivation="strategy",
        preferred_words=["Strategie", "Aufbauen", "Sammeln", "Magie",
                         "Abenteuer", "Rätsel"],
        avoided_words=["Abzocke", "langweilig"],
        monetization_traits=["moderate_iap", "value_conscious"],
        tone="professional",
    ),
    "FR": MarketProfile(
        country="FR",
        language="fr",
        motivation="discovery",
        preferred_words=["magie", "aventure", "collection", "créer",
                         "explorer", "mystère", "charmant"],
        avoided_words=["ennuyeux", "arnaque"],
        monetization_traits=["moderate_iap", "aesthetic_driven"],
        tone="playful",
    ),
    "BR": MarketProfile(
        country="BR",
        language="pt",
        motivation="social",
        preferred_words=["aventura", "magia", "coleção", "amigos",
                         "divertido", "gratuito", "desafio"],
        avoided_words=["chato", "cara"],
        monetization_traits=["reward_ad_heavy", "price_sensitive"],
        tone="playful",
    ),
}


class MarketProfileRepository:
    """Repository of market profiles — built-in + customisable."""

    def __init__(self):
        self._profiles: Dict[str, MarketProfile] = dict(_BUILTIN)

    # ------------------------------------------------------------------ #
    def get(self, country: str) -> Optional[MarketProfile]:
        """Get profile for a country code (case-insensitive)."""
        return self._profiles.get(country.upper())

    def list_available(self) -> List[str]:
        """List all available country codes."""
        return list(self._profiles.keys())

    def register(self, profile: MarketProfile) -> None:
        """Add or override a market profile."""
        self._profiles[profile.country.upper()] = profile

    def customize(
        self,
        country: str,
        **overrides,
    ) -> Optional[MarketProfile]:
        """Create a customised copy of a market profile.

        ``overrides`` can include motivation, preferred_words, tone, etc.
        """
        base = self.get(country)
        if base is None:
            return None

        custom = MarketProfile(
            country=base.country,
            language=base.language,
            motivation=overrides.get("motivation", base.motivation),
            preferred_words=overrides.get(
                "preferred_words", list(base.preferred_words)
            ),
            avoided_words=overrides.get(
                "avoided_words", list(base.avoided_words)
            ),
            monetization_traits=overrides.get(
                "monetization_traits", list(base.monetization_traits)
            ),
            tone=overrides.get("tone", base.tone),
        )
        return custom


__all__ = ["MarketProfileRepository"]
