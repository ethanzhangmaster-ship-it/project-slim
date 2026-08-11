"""E16.6.2 — Google Play reality provider + external ASO enrichment.

``GooglePlayProvider`` reuses the E15.2 ``PlayRealityConnector`` (which wraps
``GooglePlayRealClient``) to pull store health + reviews-flavoured metrics.
Google Play's public APIs (and this repo's client) do NOT expose:

* store listing search **impressions** / **product_page_views**
* **keyword rankings**
* store-listing **experiment** results

Those are supplied by ``ExternalASOProvider`` (Sensor Tower / data.ai /
AppTweak / AppMagic) — currently a stub returning an empty shell, wired in so
the connector + normalizer already handle the merge once a real bridge lands.
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import ASORealitySnapshot, Platform
from .base import ASODataProvider


def _build_play_connector(client: Any):
    """Lazily import E15.2's PlayRealityConnector to avoid a hard dependency
    at import time (keeps this layer a clean seam)."""
    from operation.publishing_factory.play_runtime.reality.connector import (
        PlayRealityConnector,
    )

    return PlayRealityConnector(client)


class GooglePlayProvider:
    """Bridges E15.2 Play Reality into the ASO reality snapshot.

    For a non-Google-Play ``platform`` (or when no client/connector is wired)
    it returns a ``fallback`` shell so the connector's merge is unaffected.
    """

    def __init__(
        self,
        play_connector: Optional[Any] = None,
        client: Optional[Any] = None,
    ) -> None:
        self._play = play_connector
        if self._play is None and client is not None:
            self._play = _build_play_connector(client)

    def fetch(self, game_id: str, *, platform: Platform) -> ASORealitySnapshot:
        if platform != Platform.GOOGLE_PLAY:
            return ASORealitySnapshot(
                game_id=game_id, platform=platform, source="fallback"
            )
        if self._play is None:
            return ASORealitySnapshot(
                game_id=game_id, platform=platform, source="fallback"
            )
        try:
            prs = self._play.collect(game_id)
        except Exception:
            return ASORealitySnapshot(
                game_id=game_id, platform=platform, source="fallback"
            )

        return ASORealitySnapshot(
            game_id=game_id,
            platform=platform,
            timestamp=prs.collected_at,
            installs=prs.installs,
            rating=prs.rating_average,
            review_count=prs.review_count,
            extra={
                "negative_review_ratio": prs.negative_review_ratio,
                "sources": dict(prs.sources),
            },
            source=f"google_play:{prs.sources.get('store', 'live')}",
        )


class ExternalASOProvider:
    """Third-party ASO enrichment (impressions / keyword ranks / experiments).

    First version: stub. Returns an empty shell so the connector's merge is a
    no-op until a real bridge (AppTweak / AppMagic / Sensor Tower / data.ai) is
    implemented. The ``client`` seam is left for that future adapter.
    """

    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client

    def fetch(self, game_id: str, *, platform: Platform) -> ASORealitySnapshot:
        # Future: query client for impressions / product_page_views /
        # keyword_rankings and return a populated shell.
        return ASORealitySnapshot(
            game_id=game_id, platform=platform, source="unavailable"
        )


__all__ = ["GooglePlayProvider", "ExternalASOProvider"]
