"""E15.2.3 — Simulation Revenue Provider"""
from __future__ import annotations
from typing import Any, Dict, List
from operation.providers.contracts.revenue import RevenueProvider, RevenueRecord


class SimulationRevenueProvider(RevenueProvider):
    name = "simulation_revenue"

    def get_daily_revenue(self, game_id: str, date: str,
                          country: str = "", platform: str = "") -> RevenueRecord:
        return RevenueRecord(
            game_id=game_id, date=date, iaa=245.0, iap=120.0,
            total=365.0, currency="USD", country=country or "US",
            platform=platform or "android", source="max",
        )

    def get_revenue_range(self, game_id: str, start_date: str,
                          end_date: str) -> List[RevenueRecord]:
        return [
            RevenueRecord(
                game_id=game_id, date=f"2026-07-{20+d:02d}",
                iaa=240.0 + d * 5, iap=115.0 + d * 3,
                currency="USD", source="max",
            )
            for d in range(5)
        ]

    def get_ecpm_trend(self, game_id: str, ad_type: str = "rewarded",
                       days: int = 7) -> List[Dict[str, Any]]:
        return [
            {"date": f"2026-07-{20+d:02d}", "ecpm": round(12.0 + d * 0.5, 2)}
            for d in range(days)
        ]

    def health_check(self) -> Dict[str, Any]:
        return {"success": True, "detail": "simulation revenue healthy"}


__all__ = ["SimulationRevenueProvider"]
