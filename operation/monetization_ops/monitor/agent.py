"""E15.2.7 — Monetization Health Monitor (eCPM decline, fill drop, purchase fail)"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class MonetizationHealthReport:
    game_id: str
    healthy: bool = True
    flags: List[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "healthy": self.healthy,
            "flags": self.flags, "details": self.details,
        }


class MonitorAgent:
    def check(self, game_id: str, max_revenue: dict, iap_status: dict) -> MonetizationHealthReport:
        flags = []
        ecpm = max_revenue.get("ecpm", 0)
        fill = max_revenue.get("fill_rate", 0)
        if ecpm < 10.0:
            flags.append("ecpm_below_10")
        if fill < 0.90:
            flags.append("fill_rate_below_90")
        if not iap_status.get("exists", True):
            flags.append("iap_product_missing")
        return MonetizationHealthReport(
            game_id=game_id, healthy=len(flags) == 0,
            flags=flags, details={"ecpm": ecpm, "fill": fill,
                                  "iap_ok": iap_status.get("exists", True)})
