"""E16.6.2 — ASONormalizer: raw reality -> E16.6.1 analysis-ready ASOSnapshot.

Cross-platform standardization:
* Google Play ``installs`` == Apple ``downloads`` -> unified ``installs``.
* ``product_page_views`` (else ``impressions``) -> E16.6.1 ``store_visits``.

Creative DNA (screenshot hook/clarity, icon focal strength) is deliberately
**not** synthesized here — that is E16.6.3 (ASO Creative Optimization). Raw
asset URLs and keyword rankings are preserved under ``ASOSnapshot.extra`` so the
later layer can enrich them without re-fetching, and so the E16.6.1
``ListingAnalyzer`` does not fire on absent creative scores.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import ASOSnapshot  # E16.6.1
from .models import ASORealitySnapshot, ReviewRecord


class ASONormalizer:
    # ------------------------------------------------------------------ #
    @staticmethod
    def to_aso_snapshot(
        reality: ASORealitySnapshot,
        reviews: Optional[List[ReviewRecord]] = None,
    ) -> ASOSnapshot:
        store_visits = reality.product_page_views
        if store_visits is None:
            store_visits = reality.impressions

        return ASOSnapshot(
            game_id=reality.game_id,
            platform=reality.platform.value,
            date=reality.timestamp.date().isoformat(),
            store_visits=int(store_visits or 0),
            installs=int(reality.installs or 0),
            conversion_rate=reality.conversion_rate,
            rating=float(reality.rating or 0.0),
            review_count=int(reality.review_count or 0),
            ranking=reality.category_rank,
            title=reality.title,
            short_description=reality.short_description,
            keywords=[],  # intent keywords are supplied at analyze() time
            screenshots=[],  # creative DNA enriched in E16.6.3
            icon={},  # creative DNA enriched in E16.6.3
            extra={
                "impressions": reality.impressions,
                "product_page_views": reality.product_page_views,
                "raw_screenshots": list(reality.screenshots),
                "icon_url": reality.icon_url,
                "keyword_rankings": [
                    k.to_dict() for k in reality.keyword_rankings
                ],
                "source": reality.source,
                "review_count_raw": len(reviews or []),
            },
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def merge(snapshots: List[ASORealitySnapshot]) -> ASORealitySnapshot:
        """Merge several provider snapshots.

        Non-None scalar fields win (later provider overrides earlier); lists
        (screenshots / keyword_rankings) are concatenated; ``extra`` dicts are
        merged. Empty / fallback shells are skipped entirely.
        """
        real = [s for s in snapshots if s is not None and not s.is_empty()]
        if not real:
            base = snapshots[0] if snapshots else None
            if base is None:
                raise ValueError("ASONormalizer.merge: no snapshots to merge")
            return ASORealitySnapshot(
                game_id=base.game_id,
                platform=base.platform,
                timestamp=base.timestamp,
                source="fallback",
            )

        merged = ASORealitySnapshot(
            game_id=real[0].game_id,
            platform=real[0].platform,
            timestamp=max(s.timestamp for s in real),
        )
        scalar_fields = (
            "impressions",
            "product_page_views",
            "installs",
            "conversion_rate",
            "category_rank",
            "rating",
            "review_count",
            "title",
            "short_description",
            "icon_url",
            "source",
        )
        for s in real:
            for f in scalar_fields:
                v = getattr(s, f, None)
                if v is not None and v != "":
                    setattr(merged, f, v)
            for u in s.screenshots:
                if u not in merged.screenshots:
                    merged.screenshots.append(u)
            if s.keyword_rankings:
                merged.keyword_rankings.extend(s.keyword_rankings)
            if s.extra:
                merged.extra.update(s.extra)
        return merged


__all__ = ["ASONormalizer"]
