"""E16.6.2 — App Store reality provider (interface seam).

The App Store Connect API is not wired in this repository yet, so
``AppStoreProvider`` returns a ``unavailable`` shell. The ``client`` seam is left
for a future adapter that calls App Store Connect (sales/metrics + reviews).

When implemented, it should populate the same ``ASORealitySnapshot`` fields as
``GooglePlayProvider`` (installs -> "downloads" normalized upstream by the
normalizer, rating, review_count, impressions, product_page_views, etc.).
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import ASORealitySnapshot, Platform
from .base import ASODataProvider


class AppStoreProvider:
    """App Store Connect reality — stub until the client is bridged."""

    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client

    def fetch(self, game_id: str, *, platform: Platform) -> ASORealitySnapshot:
        if platform != Platform.APP_STORE:
            return ASORealitySnapshot(
                game_id=game_id, platform=platform, source="fallback"
            )
        # Future: real App Store Connect fetch. For now: unavailable shell.
        return ASORealitySnapshot(
            game_id=game_id, platform=platform, source="unavailable"
        )


__all__ = ["AppStoreProvider"]
