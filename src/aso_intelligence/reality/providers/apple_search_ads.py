"""E16.6.2 — Apple Search Ads (ASA) keyword reality provider via aso-mcp.

Wraps the ``ASOKeywordResearcher`` (which calls the ``aso-mcp`` Node.js MCP
server via stdio) into an ``ASODataProvider`` so it plugs into the standard
``ASORealityConnector`` merge pipeline.

Integration contract:
  * Self-selects Platform.APP_STORE (ASA is Apple-only).
  * Returns ``source="apple_search_ads:live"`` on success;
    ``source="apple_search_ads:unavailable"`` if aso-mcp is not installed/authenticated;
    ``source="fallback"`` on any other platform.
  * Never raises — failures are folded into the snapshot's source/provenance.

The provider can also be used standalone:
    provider = AppleSearchAdsProvider()
    snap = provider.fetch("merge_witch", platform=Platform.APP_STORE)
    for kr in snap.keyword_rankings:
        print(kr.keyword, kr.volume, kr.difficulty)
"""

from __future__ import annotations

import logging
from typing import Optional

from ..models import ASORealitySnapshot, KeywordRanking, Platform
from .base import ASODataProvider

logger = logging.getLogger(__name__)

# Map aso-mcp popularity (0–100) to KeywordRanking.volume (0.0–1.0)
_POPULARITY_SCALE = 100.0

# Map aso-mcp difficultyScore (0–100) to KeywordRanking.difficulty (0.0–1.0)
_DIFFICULTY_SCALE = 100.0

# Default seed keywords used when no explicit list is provided to the provider.
# These are broad "casual/mobile game" category seeds intended to generate a
# reasonable baseline keyword set before the KeywordAgent refines them further.
_DEFAULT_SEED_KEYWORDS = [
    "merge game",
    "puzzle game",
    "match 3",
    "idle game",
    "tycoon",
    "tap game",
    "relaxing games",
    "brain game",
    "family puzzle",
    "casual game",
]


class AppleSearchAdsProvider:
    """Apple Search Ads keyword data provider via aso-mcp MCP server.

    Implements the ``ASODataProvider`` Protocol (``fetch`` method) so it plugs
    into ``ASORealityConnector`` without changes.
    """

    def __init__(
        self,
        researcher=None,
        seed_keywords: Optional[list[str]] = None,
        min_popularity: int = 6,
        max_difficulty: int = 70,
    ) -> None:
        # Lazy import to avoid hard dependency: caller can inject a researcher
        # and tests can use a mock.
        if researcher is None:
            try:
                from src.market_ops.workspace.aso_keyword_researcher import (
                    ASOKeywordResearcher,
                )
                researcher = ASOKeywordResearcher()
            except Exception as exc:
                logger.warning(
                    "ASOKeywordResearcher import failed, provider will be unavailable: %s",
                    exc,
                )
                researcher = None

        self._researcher = researcher
        self._seed_keywords = seed_keywords or list(_DEFAULT_SEED_KEYWORDS)
        self._min_popularity = min_popularity
        self._max_difficulty = max_difficulty

    # ------------------------------------------------------------------ #
    # ASODataProvider Protocol
    # ------------------------------------------------------------------ #
    def fetch(self, game_id: str, *, platform: Platform) -> ASORealitySnapshot:
        """Fetch keyword rankings from Apple Search Ads via aso-mcp.

        Returns an ``ASORealitySnapshot`` populated with
        ``keyword_rankings``. Self-selects ``Platform.APP_STORE`` and returns
        a fallback shell otherwise.
        """
        if platform != Platform.APP_STORE:
            return ASORealitySnapshot(
                game_id=game_id, platform=platform, source="fallback"
            )

        if self._researcher is None:
            return ASORealitySnapshot(
                game_id=game_id,
                platform=platform,
                source="apple_search_ads:unavailable",
                extra={"reason": "aso keyword researcher not available"},
            )

        # Status check first — avoids spawning aso-mcp if clearly not usable.
        status = self._researcher.check_status()
        if status["status"] != "ready":
            return ASORealitySnapshot(
                game_id=game_id,
                platform=platform,
                source="apple_search_ads:unavailable",
                extra={"status": status},
            )

        try:
            result = self._researcher.research_keywords(
                keywords=self._seed_keywords,
                min_popularity=self._min_popularity,
                max_difficulty=self._max_difficulty,
            )
        except Exception as exc:
            logger.warning(
                "AppleSearchAdsProvider fetch failed for %s: %s",
                game_id,
                exc,
                exc_info=True,
            )
            return ASORealitySnapshot(
                game_id=game_id,
                platform=platform,
                source="apple_search_ads:error",
                extra={"error": str(exc)},
            )

        if not result.success:
            return ASORealitySnapshot(
                game_id=game_id,
                platform=platform,
                source="apple_search_ads:error",
                extra={
                    "error": result.error,
                    "failed_keywords": result.failed_keywords,
                },
            )

        rankings: list[KeywordRanking] = []
        for item in result.items:
            rankings.append(
                KeywordRanking(
                    keyword=item.keyword,
                    volume=round(item.popularity / _POPULARITY_SCALE, 4),
                    difficulty=round(item.difficulty_score / _DIFFICULTY_SCALE, 4),
                )
            )

        return ASORealitySnapshot(
            game_id=game_id,
            platform=platform,
            keyword_rankings=rankings,
            source="apple_search_ads:live",
            extra={
                "seed_keywords": list(self._seed_keywords),
                "failed_keywords": result.failed_keywords,
                "filtered_out": result.filtered_out,
                "total_researched": result.total_researched,
            },
        )

    # ------------------------------------------------------------------ #
    # Convenience utilities
    # ------------------------------------------------------------------ #
    @property
    def is_available(self) -> bool:
        """True if the provider can actually call aso-mcp right now."""
        if self._researcher is None:
            return False
        return self._researcher.check_status()["status"] == "ready"

    def with_seed_keywords(self, keywords: list[str]) -> "AppleSearchAdsProvider":
        """Return a **new** provider that uses the given seed keyword list."""
        return AppleSearchAdsProvider(
            researcher=self._researcher,
            seed_keywords=list(keywords),
            min_popularity=self._min_popularity,
            max_difficulty=self._max_difficulty,
        )


__all__ = ["AppleSearchAdsProvider"]
