"""E16.6.2 — ASO Reality Provider contracts + null doubles.

Every provider is a thin, deterministic adapter over one external data source.
The contract:

* ``ASODataProvider.fetch(game_id, platform)`` — raw store reality for one game
  on one platform. MUST NOT raise: on any failure return a ``source="fallback"``
  shell so the connector's merge step stays robust (package-level isolation).
* ``ReviewProvider.fetch_reviews(game_id, platform, limit)`` — raw player reviews.

The connector merges every ``ASODataProvider`` and every ``ReviewProvider``;
each provider self-selects its platform and returns a fallback shell otherwise.
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol, runtime_checkable

from ..models import ASORealitySnapshot, Platform, ReviewRecord


@runtime_checkable
class ASODataProvider(Protocol):
    """Supplies the raw store reality for a game on a given platform."""

    def fetch(self, game_id: str, *, platform: Platform) -> ASORealitySnapshot:
        ...


@runtime_checkable
class ReviewProvider(Protocol):
    """Supplies raw player reviews for a game on a given platform."""

    def fetch_reviews(
        self, game_id: str, *, platform: Platform, limit: int = 200
    ) -> List[ReviewRecord]:
        ...


# --------------------------------------------------------------------------- #
# Null doubles — safe defaults so the connector never blows up
# --------------------------------------------------------------------------- #
class NullASODataProvider:
    """Returns a fallback shell for any game/platform (no data source)."""

    def fetch(self, game_id: str, *, platform: Platform) -> ASORealitySnapshot:
        return ASORealitySnapshot(
            game_id=game_id, platform=platform, source="fallback"
        )


class NullReviewProvider:
    """Returns no reviews for any game/platform."""

    def fetch_reviews(
        self, game_id: str, *, platform: Platform, limit: int = 200
    ) -> List[ReviewRecord]:
        return []


__all__ = [
    "ASODataProvider",
    "ReviewProvider",
    "NullASODataProvider",
    "NullReviewProvider",
]
