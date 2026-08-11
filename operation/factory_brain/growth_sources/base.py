"""
E15.1.2 — Market-opportunity source adapters (Growth intake connector)
======================================================================

This module is the *local* side of the Growth OS drop-in. The external
Growth OS (a separate system) is supposed to write structured JSON into
``data/market_opportunities.json``; ``OpportunityIntake`` already consumes
that file with **zero coupling**.

Until a real Growth feed is plugged in, this package provides:

  * ``MockMarketSource`` — a curated, deterministic set of realistic
    overseas-casual-market signals. Runs with zero dependencies so the
    Factory Brain closed loop is demonstrable end-to-end *today*.
  * ``RealMarketSource`` — an inert skeleton: reads
    ``credentials/market_sources.json``, and only fires once a provider
    adapter is registered AND enabled with an endpoint. The exact spot
    to map a real market feed (App Store rank, TikTok hashtag volume,
    Sensor Tower, etc.) is a documented seam — no network is ever hit
    unless you configure it.

Design rules (same as the rest of the brain):
  * Deterministic, no LLM.
  * A source NEVER raises — ``fetch()`` swallows faults and returns [].
  * Secrets stay in ``credentials/``; never inlined.
"""
from __future__ import annotations

import abc
from typing import Dict, List

from operation.factory_brain.models import MarketOpportunity


class MarketSource(abc.ABC):
    """A pluggable source of market opportunities.

    Subclasses implement ``fetch_raw`` (return raw records, never raise)
    and ``normalize`` (raw -> MarketOpportunity). ``fetch`` wraps both in
    a fault-tolerant call so a broken source can never crash the pipeline.
    """

    name: str = "abstract"
    kind: str = "abstract"          # "mock" | "real"

    @abc.abstractmethod
    def fetch_raw(self) -> List[dict]:
        """Return raw source records. Must not raise."""

    @abc.abstractmethod
    def normalize(self, raw: List[dict]) -> List[MarketOpportunity]:
        """Turn raw records into MarketOpportunity objects."""

    def fetch(self) -> List[MarketOpportunity]:
        """Safe fetch_raw -> normalize. Returns [] on any failure."""
        try:
            return self.normalize(self.fetch_raw())
        except Exception:           # noqa: BLE001 — sources must be bulletproof
            return []

    def status(self) -> Dict[str, object]:
        """Machine-readable health for the run report / logging."""
        return {"name": self.name, "kind": self.kind, "configured": True}


__all__ = ["MarketSource", "MarketOpportunity"]
