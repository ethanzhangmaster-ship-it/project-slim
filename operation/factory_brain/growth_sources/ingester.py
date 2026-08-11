"""
E15.1.2 — Market-opportunity ingester
======================================

Runs the configured sources, merges + dedupes by (genre, theme) (keeping
the higher-scored copy), ranks by ``MarketOpportunity.score()``, and writes
the result to the Growth OS drop-in file that ``OpportunityIntake`` already
consumes: ``data/market_opportunities.json``.

Zero coupling preserved: this is just another producer of that file.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List

from .base import MarketSource
from .mock_source import MockMarketSource
from .real_source import RealMarketSource
from .public_chart_source import AppleTopFreeSource
from operation.factory_brain.opportunity_intake import DEFAULT_DROPIN
from operation.factory_brain.models import MarketOpportunity


class MarketOpportunityIngester:
    def __init__(self, sources: List[MarketSource],
                 out_path: str = DEFAULT_DROPIN) -> None:
        self.sources = list(sources)
        self.out_path = out_path

    def run(self, dry_run: bool = False,
            write: bool = True) -> Dict[str, object]:
        """Execute all sources, merge, rank, optionally persist.

        Returns a report dict (statuses + ranked opportunity dicts).
        """
        merged: Dict[str, MarketOpportunity] = {}
        statuses: List[Dict[str, object]] = []
        for src in self.sources:
            try:
                opps = src.fetch()
            except Exception:               # noqa: BLE001
                opps = []
            st = src.status()
            st["count"] = len(opps)
            statuses.append(st)
            for o in opps:
                key = f"{o.genre}|{o.theme}"
                cur = merged.get(key)
                if cur is None or o.score() > cur.score():
                    merged[key] = o

        ranked = sorted(merged.values(),
                        key=lambda o: (-o.score(), o.opportunity_id))
        result: Dict[str, object] = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "sources": statuses,
            "count": len(ranked),
            "opportunities": [o.to_dict() for o in ranked],
        }
        if write and not dry_run and ranked:
            self._write(result["opportunities"])
        return result

    def _write(self, opportunities: List[dict]) -> None:
        path = os.path.abspath(self.out_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(opportunities, fh, indent=2)


def build_default_sources() -> List[MarketSource]:
    """Deterministic sources for CLI default / offline demos.

    ``MockMarketSource`` feeds the pipeline when there is no network;
    ``RealMarketSource`` is the configurable seam for a proprietary feed.
    Use ``build_pipeline_sources()`` to also include public-chart data.
    """
    return [MockMarketSource(), RealMarketSource()]


def build_pipeline_sources() -> List[MarketSource]:
    """Production daily-pipeline sources: mock fallback + public chart + real seam.

    ``AppleTopFreeSource`` runs live-first (cache-fallback) so the pipeline
    has real market intel when network is available; ``MockMarketSource``
    ensures deterministic fallback when it is not. ``RealMarketSource`` is
    the configurable seam for a proprietary feed.
    """
    return [MockMarketSource(), AppleTopFreeSource(), RealMarketSource()]


__all__ = ["MarketOpportunityIngester", "build_default_sources",
           "build_pipeline_sources"]
