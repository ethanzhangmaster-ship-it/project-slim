"""
E15.1.2 — Opportunity Intake
=============================

Two deterministic opportunity sources:

1. Growth OS drop-in file (data/market_opportunities.json).
   Same integration pattern as the Adjust DAU drop-in: the external
   Growth OS (a separate system) writes structured JSON; the brain
   consumes it. No coupling, no credentials.

2. Fleet-derived opportunities: if a published genre in our own fleet
   shows strong revenue_per_dau / store CVR, that IS a market signal —
   "we already proved this genre monetizes for us".

Output: ranked List[MarketOpportunity] (best first).
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from operation.publishing_factory.catalog.game_registry import GameRegistry

from .models import MarketOpportunity

DEFAULT_DROPIN = "data/market_opportunities.json"

# fleet-derived thresholds (documented constants)
_MIN_RPD = 0.02          # revenue_per_dau >= $0.02 counts as "monetizing"
_MIN_CVR = 0.15          # store cvr >= 15% counts as "converting"


class OpportunityIntake:
    """Collects, dedupes and ranks opportunities."""

    def __init__(self, registry: GameRegistry,
                 dropin_path: str = DEFAULT_DROPIN):
        self.registry = registry
        self.dropin_path = dropin_path

    # ------------------------------------------------------------------ #
    def load_dropin(self) -> List[MarketOpportunity]:
        """Read Growth OS opportunities from the drop-in file (if any)."""
        if not os.path.exists(self.dropin_path):
            return []
        try:
            with open(self.dropin_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return []                     # malformed drop-in never crashes
        items = raw if isinstance(raw, list) else raw.get("opportunities", [])
        out: List[MarketOpportunity] = []
        for d in items:
            if not isinstance(d, dict) or "opportunity_id" not in d:
                continue
            opp = MarketOpportunity.from_dict(d)
            out.append(opp)
        return out

    # ------------------------------------------------------------------ #
    def derive_from_fleet(self) -> List[MarketOpportunity]:
        """Internal signals: genres in our fleet that already monetize.

        Uses GameProduct.metrics keys (all optional):
          revenue_per_dau, store_cvr
        """
        by_genre: Dict[str, List[float]] = {}
        cvr_by_genre: Dict[str, List[float]] = {}
        for g in self.registry.list_all():
            if not g.is_published():
                continue
            rpd = float(g.metrics.get("revenue_per_dau", 0.0))
            cvr = float(g.metrics.get("store_cvr", 0.0))
            if rpd > 0:
                by_genre.setdefault(g.genre, []).append(rpd)
            if cvr > 0:
                cvr_by_genre.setdefault(g.genre, []).append(cvr)

        out: List[MarketOpportunity] = []
        for genre, rpds in sorted(by_genre.items()):
            avg_rpd = sum(rpds) / len(rpds)
            if avg_rpd < _MIN_RPD:
                continue
            cvrs = cvr_by_genre.get(genre, [])
            avg_cvr = (sum(cvrs) / len(cvrs)) if cvrs else 0.0
            # map internal strength into the same 0..1 sub-score space
            ecpm_signal = min(1.0, avg_rpd / 0.10)      # $0.10/DAU -> 1.0
            keyword_trend = min(1.0, avg_cvr / 0.30) if avg_cvr else 0.3
            out.append(MarketOpportunity(
                opportunity_id=f"fleet_{genre}",
                genre=genre,
                theme="",
                source="fleet",
                keyword_trend=round(keyword_trend, 4),
                competition=0.5,                        # unknown -> neutral
                ecpm_signal=round(ecpm_signal, 4),
                ltv_forecast=round(min(1.0, avg_rpd / 0.08), 4),
                notes=(f"fleet-proven: avg revenue_per_dau=${avg_rpd:.3f} "
                       f"over {len(rpds)} published game(s)"),
            ))
        return out

    # ------------------------------------------------------------------ #
    def collect(self) -> List[MarketOpportunity]:
        """Merge drop-in + fleet, dedupe by (genre, theme), rank by score."""
        merged: Dict[str, MarketOpportunity] = {}
        # drop-in first (external market intel outranks internal on ties)
        for opp in self.load_dropin() + self.derive_from_fleet():
            key = f"{opp.genre}|{opp.theme}"
            cur = merged.get(key)
            if cur is None or opp.score() > cur.score():
                merged[key] = opp
        ranked = sorted(merged.values(),
                        key=lambda o: (-o.score(), o.opportunity_id))
        return ranked


__all__ = ["OpportunityIntake", "DEFAULT_DROPIN"]
