"""
E14.3.2 — Module 5: MAX Revenue Read Adapter
=============================================

This is a READ, not an execution. It feeds the Reality Engine the ad-revenue
observations MAX exposes, closing the loop:

    Execution -> Observation -> Fact -> Learning

It works in every sandbox mode (reading is safe), and never mutates state.
The MAX Adapter surfaces it both as a dedicated method (`get_revenue_metrics`)
for the Reality Engine and as a `revenue_read` Change via the contract.
"""
from __future__ import annotations

from typing import Dict

from monetization.providers.max.max_models import RevenueMetrics


class MaxRevenueReader:
    def __init__(self, client):
        self._client = client

    def get_revenue_metrics(self, date: str, geo: str, placement: str) -> RevenueMetrics:
        return self._client.read_revenue(date, geo, placement)

    def to_reality_fact(self, date: str, geo: str, placement: str) -> Dict:
        """Shape the observation into a Reality Engine fact payload."""
        rm = self.get_revenue_metrics(date, geo, placement)
        return {
            "date": rm.date,
            "geo": rm.geo,
            "placement": rm.placement,
            "impressions": rm.impressions,
            "revenue": rm.revenue,
            "ecpm": rm.ecpm,
        }
