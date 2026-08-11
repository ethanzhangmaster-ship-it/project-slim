"""
E16.6.6 — ASO Revenue Attributor.

Maps organic install events → revenue attribution by keyword, country, and
listing version. Bridges the gap between ASO actions and Adjust/Revenue data.

Pipeline:
    ASOAcquisitionEvent (what installed)
        + Adjust revenue data (how much they paid)
        → ASORevenueAttribution (revenue per source)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.revenue.models import (
    ASOAcquisitionEvent,
    ASORevenueAttribution,
)


class ASORevenueAttributor:
    """Distribute revenue to ASO sources (keyword, country, listing version).

    This is a deterministic model: given acquisition events + per-source revenue
    data, it computes ``ASORevenueAttribution`` for each source key.
    """

    def __init__(self, min_installs: int = 10):
        self.min_installs = min_installs

    # ------------------------------------------------------------------ #
    def _source_key(self, event: ASOAcquisitionEvent) -> str:
        """Primary grouping key: ``keyword:{kw}`` or ``country:{cc}``."""
        if event.keyword:
            return f"keyword:{event.keyword}"
        return f"country:{event.country}"

    def _country_key(self, event: ASOAcquisitionEvent) -> str:
        return f"country:{event.country}"

    # ------------------------------------------------------------------ #
    def attribute_by_keyword(
        self,
        events: List[ASOAcquisitionEvent],
        revenue_map: Dict[str, float],  # keyword → total revenue
        payer_map: Dict[str, int],     # keyword → payer count
        dau_map: Dict[str, int] = None,  # keyword → DAU (optional)
    ) -> List[ASORevenueAttribution]:
        """Attribute revenue by keyword.

        ``revenue_map`` maps a keyword string to total attributed revenue.
        ``payer_map`` maps a keyword string to payer count.
        """
        # Aggregate installs per keyword
        keyword_installs: Dict[str, int] = {}
        for ev in events:
            kw = ev.keyword or "__browse__"
            keyword_installs[kw] = keyword_installs.get(kw, 0) + ev.installs

        attributions: List[ASORevenueAttribution] = []
        for kw, installs in keyword_installs.items():
            if installs < self.min_installs:
                continue

            source_key = f"keyword:{kw}"
            attributions.append(
                ASORevenueAttribution(
                    game_id=events[0].game_id if events else "",
                    source_key=source_key,
                    installs=installs,
                    revenue=revenue_map.get(kw, 0.0),
                    payer_count=payer_map.get(kw, 0),
                    dau=dau_map.get(kw, 0) if dau_map else 0,
                )
            )
        return attributions

    # ------------------------------------------------------------------ #
    def attribute_by_country(
        self,
        events: List[ASOAcquisitionEvent],
        revenue_map: Dict[str, float],  # country code → revenue
        payer_map: Dict[str, int],     # country code → payer count
        dau_map: Dict[str, int] = None,
    ) -> List[ASORevenueAttribution]:
        """Attribute revenue by country."""
        country_installs: Dict[str, int] = {}
        for ev in events:
            country_installs[ev.country] = (
                country_installs.get(ev.country, 0) + ev.installs
            )

        attributions: List[ASORevenueAttribution] = []
        for cc, installs in country_installs.items():
            if installs < self.min_installs:
                continue

            source_key = f"country:{cc}"
            attributions.append(
                ASORevenueAttribution(
                    game_id=events[0].game_id if events else "",
                    source_key=source_key,
                    installs=installs,
                    revenue=revenue_map.get(cc, 0.0),
                    payer_count=payer_map.get(cc, 0),
                    dau=dau_map.get(cc, 0) if dau_map else 0,
                )
            )
        return attributions

    # ------------------------------------------------------------------ #
    def attribute_by_keyword_and_country(
        self,
        events: List[ASOAcquisitionEvent],
        revenue_map: Dict[str, float],  # "keyword:country" → revenue
        payer_map: Dict[str, int],     # "keyword:country" → payers
    ) -> List[ASORevenueAttribution]:
        """Attribute revenue by keyword + country (most granular)."""
        kc_installs: Dict[str, int] = {}
        kc_payers: Dict[str, int] = {}
        for ev in events:
            kc = f"keyword:{ev.keyword or '__browse__'}:country:{ev.country}"
            kc_installs[kc] = kc_installs.get(kc, 0) + ev.installs

        attributions: List[ASORevenueAttribution] = []
        for kc, installs in kc_installs.items():
            if installs < self.min_installs:
                continue
            attributions.append(
                ASORevenueAttribution(
                    game_id=events[0].game_id if events else "",
                    source_key=kc,
                    installs=installs,
                    revenue=revenue_map.get(kc, 0.0),
                    payer_count=payer_map.get(kc, 0),
                )
            )
        return attributions

    # ------------------------------------------------------------------ #
    def total(self, attributions: List[ASORevenueAttribution]) -> float:
        """Sum of attributed revenue across all sources."""
        return round(sum(a.revenue for a in attributions), 2)

    def total_installs(self, attributions: List[ASORevenueAttribution]) -> int:
        return sum(a.installs for a in attributions)

    def total_payers(self, attributions: List[ASORevenueAttribution]) -> int:
        return sum(a.payer_count for a in attributions)


__all__ = ["ASORevenueAttributor"]
