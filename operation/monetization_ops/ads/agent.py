"""E15.2.2 — Ads Integration Agent (detect gaps, create ad units, validate)"""
from dataclasses import dataclass, field
from typing import List

from operation.monetization_ops.providers.models import (
    AdUnit, AD_REWARDED, AD_INTERSTITIAL, AD_BANNER,
)

REQUIRED_FORMATS = [AD_REWARDED, AD_INTERSTITIAL, AD_BANNER]
REQUIRED_PLATFORMS = ["android", "ios"]


@dataclass
class AdIntegrationReport:
    game_id: str
    units: List[AdUnit] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    valid: bool = False

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "units": [u.to_dict() for u in self.units],
            "missing": self.missing, "valid": self.valid,
        }


class AdsAgent:
    def detect_missing(self, game_id: str, existing_units: List[AdUnit]) -> List[str]:
        covered = {(u.platform, u.format) for u in existing_units}
        missing = []
        for plat in REQUIRED_PLATFORMS:
            for fmt in REQUIRED_FORMATS:
                if (plat, fmt) not in covered:
                    missing.append(f"{plat}/{fmt}")
        return missing

    def create_all(self, game_id: str, network: str = "max") -> List[AdUnit]:
        units = []
        for plat in REQUIRED_PLATFORMS:
            for fmt in REQUIRED_FORMATS:
                placement = f"{fmt}_placement"
                units.append(AdUnit(
                    game_id=game_id, platform=plat, network=network,
                    placement=placement, format=fmt,
                    ad_unit_id=f"{network}_{game_id}_{plat}_{fmt}",
                    status="active"))
        return units

    def validate(self, units: List[AdUnit]) -> AdIntegrationReport:
        # A game must have all 6 units (3 formats × 2 platforms) active
        report = AdIntegrationReport(game_id=units[0].game_id if units else "",
                                     units=units)
        report.missing = self.detect_missing(report.game_id, units)
        report.valid = len(report.missing) == 0 and len(units) >= 6
        return report
