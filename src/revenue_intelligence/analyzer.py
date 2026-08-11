"""
E16.1 — Revenue Delta Engine

Compares a current ``RevenueSnapshot`` against a previous one and produces a
``RevenueDelta`` (period-over-period % change per metric).

Pure, deterministic, no I/O. A ``None`` percentage means the metric was not
comparable (previous value was 0 / missing) — never divide-by-zero.
"""
from __future__ import annotations

from typing import Optional

from .models import RevenueDelta, RevenueSnapshot


def _pct(old: float, new: float) -> Optional[float]:
    """% change new vs old. Returns None when old == 0 (not comparable)."""
    if old is None or old == 0:
        return None
    return round((new - old) / old * 100.0, 2)


class RevenueDeltaEngine:
    """Computes the period-over-period delta between two snapshots."""

    def compare(
        self, current: RevenueSnapshot, previous: RevenueSnapshot
    ) -> RevenueDelta:
        rev_abs = current.revenue_total - previous.revenue_total
        return RevenueDelta(
            game_id=current.game_id,
            current_date=current.date,
            previous_date=previous.date,
            revenue_total_pct=_pct(previous.revenue_total, current.revenue_total),
            iap_revenue_pct=_pct(previous.iap_revenue, current.iap_revenue),
            ad_revenue_pct=_pct(previous.ad_revenue, current.ad_revenue),
            spend_pct=_pct(previous.spend, current.spend),
            roas_pct=_pct(previous.roas, current.roas),
            payer_count_pct=_pct(previous.payer_count, current.payer_count),
            payer_conversion_pct=_pct(
                previous.payer_conversion, current.payer_conversion
            ),
            arppu_pct=_pct(previous.arppu, current.arppu),
            dau_pct=_pct(previous.dau, current.dau),
            retention_d1_pct=_pct(previous.retention_d1, current.retention_d1),
            retention_d7_pct=_pct(previous.retention_d7, current.retention_d7),
            retention_d30_pct=_pct(previous.retention_d30, current.retention_d30),
            revenue_total_abs=round(rev_abs, 4),
        )


__all__ = ["RevenueDeltaEngine", "_pct"]
