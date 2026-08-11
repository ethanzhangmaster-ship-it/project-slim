"""E16.6.2 — Review providers (raw player voice).

``GooglePlayReviewProvider`` wraps a ``GooglePlayRealClient.get_reviews``-shaped
client (the same client the E15.2 ``StoreProvider`` uses) and maps each raw
review into a ``ReviewRecord``. ``AppStoreReviewProvider`` is the iOS seam
(stub until App Store Connect reviews are bridged).
"""

from __future__ import annotations

from typing import Any, List, Optional

from ..models import Platform, ReviewRecord
from .base import ReviewProvider


class GooglePlayReviewProvider:
    """Google Play reviews via a ``get_reviews``-shaped client."""

    def __init__(
        self, client: Optional[Any] = None, max_reviews: int = 200
    ) -> None:
        self._client = client
        self._max = max_reviews

    def fetch_reviews(
        self, game_id: str, *, platform: Platform, limit: int = 200
    ) -> List[ReviewRecord]:
        if platform != Platform.GOOGLE_PLAY or self._client is None:
            return []
        try:
            raw = (
                self._client.get_reviews(game_id, max_results=max(limit, self._max))
                or {}
            )
        except Exception:
            return []
        out: List[ReviewRecord] = []
        for r in raw.get("reviews") or []:
            star = r.get("star_rating")
            try:
                star = float(star)
            except (TypeError, ValueError):
                star = 0.0
            out.append(
                ReviewRecord(
                    game_id=game_id,
                    platform=platform,
                    rating=star,
                    text=r.get("text", ""),
                    author=r.get("author", ""),
                    source="google_play",
                )
            )
        return out


class AppStoreReviewProvider:
    """App Store reviews — stub until the client is bridged."""

    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client

    def fetch_reviews(
        self, game_id: str, *, platform: Platform, limit: int = 200
    ) -> List[ReviewRecord]:
        # Future: App Store Connect reviews.
        return []


__all__ = ["GooglePlayReviewProvider", "AppStoreReviewProvider"]
