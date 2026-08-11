"""
E16.6.9 — Keyword Localization Adapter.

Connects to E16.6.7 Keyword Intelligence. Translates English keywords into
market-specific search intent — not literal translation, but finding what
local players actually search for.

Each market has a mapping of common game keywords to their local equivalents
with estimated search volume, difficulty, and revenue potential.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.aso_intelligence.localization.models import LocalizedKeyword


# For MVP, we use deterministic keyword mappings.
# In production, this would call Sensor Tower / AppTweak API per market.
# Format: (local_keyword, search_volume_estimate, difficulty, revenue_score)
_KEYWORD_MAP: Dict[str, Dict[str, Tuple[str, int, float, float]]] = {
    "US": {
        "merge game": ("merge game", 50000, 0.6, 0.8),
        "puzzle": ("puzzle", 80000, 0.7, 0.5),
        "magic merge": ("magic merge", 15000, 0.3, 0.9),
        "merge puzzle": ("merge puzzle", 25000, 0.4, 0.7),
    },
    "JP": {
        "merge game": ("マージゲーム", 30000, 0.5, 0.7),
        "puzzle": ("パズル", 60000, 0.6, 0.4),
        "magic merge": ("魔法のマージ", 12000, 0.3, 0.85),
        "merge puzzle": ("合成パズル", 18000, 0.4, 0.75),
        "collection": ("収集ゲーム", 20000, 0.4, 0.8),
        "cute game": ("かわいいゲーム", 40000, 0.5, 0.7),
    },
    "KR": {
        "merge game": ("머지 게임", 25000, 0.5, 0.75),
        "puzzle": ("퍼즐", 50000, 0.6, 0.45),
        "magic merge": ("마법 머지", 10000, 0.3, 0.85),
        "merge puzzle": ("합성 퍼즐", 15000, 0.4, 0.7),
        "growth": ("성장 게임", 20000, 0.4, 0.8),
    },
    "DE": {
        "merge game": ("Merge-Spiel", 20000, 0.5, 0.7),
        "puzzle": ("Rätsel", 40000, 0.6, 0.4),
        "magic merge": ("Magisches Merge", 8000, 0.3, 0.8),
    },
    "FR": {
        "merge game": ("jeu de fusion", 15000, 0.5, 0.7),
        "puzzle": ("puzzle", 35000, 0.6, 0.4),
        "magic merge": ("fusion magique", 7000, 0.3, 0.8),
    },
    "BR": {
        "merge game": ("jogo de fusão", 12000, 0.4, 0.6),
        "puzzle": ("quebra-cabeça", 30000, 0.5, 0.35),
        "magic merge": ("fusão mágica", 5000, 0.2, 0.7),
    },
}


class KeywordAdapter:
    """Adapt English keywords to market-specific search intent."""

    def __init__(self, keyword_map: Dict = None):
        self._map = keyword_map or _KEYWORD_MAP

    # ------------------------------------------------------------------ #
    def localize(
        self,
        original_keyword: str,
        market: str,
    ) -> Optional[LocalizedKeyword]:
        """Localise an English keyword for a target market.

        Returns ``None`` if no mapping exists for this market/keyword pair.
        """
        market_up = market.upper()
        market_map = self._map.get(market_up)
        if market_map is None:
            return None

        entry = market_map.get(original_keyword.lower())
        if entry is None:
            return None

        translated, volume, difficulty, revenue = entry
        return LocalizedKeyword(
            original_keyword=original_keyword,
            market=market_up,
            translated_keyword=translated,
            search_volume=volume,
            difficulty=difficulty,
            revenue_score=revenue,
        )

    # ------------------------------------------------------------------ #
    def localize_batch(
        self,
        keywords: List[str],
        market: str,
    ) -> List[LocalizedKeyword]:
        """Localise multiple keywords for one market."""
        results: List[LocalizedKeyword] = []
        for kw in keywords:
            lk = self.localize(kw, market)
            if lk:
                results.append(lk)
        return results

    # ------------------------------------------------------------------ #
    def suggest_keywords(
        self,
        market: str,
        category: str = "merge",
    ) -> List[LocalizedKeyword]:
        """Suggest all available keywords for a market + category.

        For MVP, returns all mapped keywords for the market sorted by
        revenue_score descending. In production, this would query the
        E16.6.7 scoring engine per market.
        """
        market_up = market.upper()
        market_map = self._map.get(market_up)
        if market_map is None:
            return []

        suggestions: List[LocalizedKeyword] = []
        for orig, (trans, vol, diff, rev) in market_map.items():
            suggestions.append(LocalizedKeyword(
                original_keyword=orig,
                market=market_up,
                translated_keyword=trans,
                search_volume=vol,
                difficulty=diff,
                revenue_score=rev,
            ))

        suggestions.sort(key=lambda x: x.revenue_score, reverse=True)
        return suggestions

    # ------------------------------------------------------------------ #
    def register_mapping(
        self,
        market: str,
        original: str,
        translated: str,
        search_volume: int = 0,
        difficulty: float = 0.5,
        revenue_score: float = 0.0,
    ) -> None:
        """Register a new keyword mapping (extensibility seam)."""
        market_up = market.upper()
        if market_up not in self._map:
            self._map[market_up] = {}
        self._map[market_up][original.lower()] = (
            translated, search_volume, difficulty, revenue_score,
        )


__all__ = ["KeywordAdapter"]
