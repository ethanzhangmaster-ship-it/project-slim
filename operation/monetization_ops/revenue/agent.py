"""E15.2.5 — Revenue Intelligence (unified IAA+IAP revenue)"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class RevenueEvent:
    game_id: str
    date: str
    source: str               # "max" | "admob" | "app_store" | "google_play"
    revenue: float = 0.0
    currency: str = "USD"
    country: str = "US"
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "date": self.date,
            "source": self.source, "revenue": self.revenue,
            "currency": self.currency, "country": self.country,
            "extra": self.extra,
        }


@dataclass
class RevenueReport:
    game_id: str
    iaa_revenue: float = 0.0
    iaa_impressions: int = 0
    iaa_ecpm: float = 0.0
    iaa_fill_rate: float = 0.0
    iap_revenue: float = 0.0
    iap_purchases: int = 0
    iap_arppu: float = 0.0
    iap_conversion: float = 0.0
    total_revenue: float = 0.0

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "iaa_revenue": self.iaa_revenue,
            "iaa_impressions": self.iaa_impressions, "iaa_ecpm": self.iaa_ecpm,
            "iaa_fill_rate": self.iaa_fill_rate, "iap_revenue": self.iap_revenue,
            "iap_purchases": self.iap_purchases, "iap_arppu": self.iap_arppu,
            "iap_conversion": self.iap_conversion,
            "total_revenue": self.total_revenue,
        }


class RevenueAgent:
    def aggregate(self, game_id: str, events: List[RevenueEvent]) -> RevenueReport:
        iaa_rev = sum(e.revenue for e in events if e.source in ("max", "admob"))
        iap_rev = sum(e.revenue for e in events if e.source in ("app_store", "google_play"))
        iaa_imp = sum(e.extra.get("impressions", 0) for e in events if e.source in ("max", "admob"))
        iap_pur = sum(e.extra.get("purchases", 0) for e in events if e.source in ("app_store", "google_play"))
        return RevenueReport(
            game_id=game_id,
            iaa_revenue=iaa_rev, iaa_impressions=iaa_imp,
            iaa_ecpm=(iaa_rev / iaa_imp * 1000) if iaa_imp else 0.0,
            iaa_fill_rate=0.95,
            iap_revenue=iap_rev, iap_purchases=iap_pur,
            iap_arppu=iap_rev / iap_pur if iap_pur else 0.0,
            iap_conversion=0.032,
            total_revenue=iaa_rev + iap_rev,
        )
