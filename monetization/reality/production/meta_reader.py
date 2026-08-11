"""
E14.7.1 — Meta Ads Reader (sample-backed, pluggable for real API)

Reads Meta Ads campaign + creative performance data.
In production, replace ``_load()`` with a Meta Ads API client.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class MetaCreative:
    creative_id: str
    creative_name: str
    format: str                     # video | image | carousel
    platform: str
    spend_7d: float = 0.0
    impressions_7d: int = 0
    clicks_7d: int = 0
    installs_7d: int = 0
    ctr_7d: float = 0.0
    cpi_7d: float = 0.0
    frequency_7d: float = 0.0
    ctr_trend: float = 0.0          # relative change in CTR over window
    note: str = ""

    @property
    def is_fatigued(self) -> bool:
        """Fatigue = CTR declining AND frequency above limit."""
        return self.ctr_trend < -0.15 and self.frequency_7d > 4.0

    def to_dict(self) -> dict:
        return {
            "creative_id": self.creative_id, "creative_name": self.creative_name,
            "format": self.format, "platform": self.platform,
            "spend_7d": self.spend_7d, "impressions_7d": self.impressions_7d,
            "clicks_7d": self.clicks_7d, "installs_7d": self.installs_7d,
            "ctr_7d": round(self.ctr_7d, 4), "cpi_7d": round(self.cpi_7d, 2),
            "frequency_7d": round(self.frequency_7d, 1),
            "ctr_trend": round(self.ctr_trend, 4),
            "fatigued": self.is_fatigued, "note": self.note,
        }


@dataclass
class MetaCampaign:
    campaign_id: str
    campaign_name: str
    platform: str
    country: str
    daily_budget: float = 0.0
    spend_7d: float = 0.0
    impressions_7d: int = 0
    clicks_7d: int = 0
    installs_7d: int = 0
    cpi_7d: float = 0.0

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id, "campaign_name": self.campaign_name,
            "platform": self.platform, "country": self.country,
            "spend_7d": self.spend_7d, "impressions_7d": self.impressions_7d,
            "installs_7d": self.installs_7d, "cpi_7d": round(self.cpi_7d, 2),
        }


class MetaReader:
    """Reads Meta Ads performance data."""

    def __init__(self, data_path: Optional[str] = None):
        self._data: dict = {}
        if data_path:
            self._load(data_path)

    def _load(self, path: str) -> None:
        self._data = json.loads(Path(path).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ #
    def campaigns(self) -> List[MetaCampaign]:
        out = []
        for c in self._data.get("campaigns", []):
            out.append(MetaCampaign(
                campaign_id=c["campaign_id"],
                campaign_name=c.get("campaign_name", ""),
                platform=c.get("platform", ""),
                country=c.get("country", ""),
                daily_budget=c.get("daily_budget", 0.0),
                spend_7d=c.get("spend_7d", 0.0),
                impressions_7d=c.get("impressions_7d", 0),
                clicks_7d=c.get("clicks_7d", 0),
                installs_7d=c.get("installs_7d", 0),
                cpi_7d=c.get("cpi_7d", 0.0),
            ))
        return out

    # ------------------------------------------------------------------ #
    def creatives(self) -> List[MetaCreative]:
        out = []
        for c in self._data.get("creatives", []):
            out.append(MetaCreative(
                creative_id=c["creative_id"],
                creative_name=c.get("creative_name", ""),
                format=c.get("format", ""),
                platform=c.get("platform", ""),
                spend_7d=c.get("spend_7d", 0.0),
                impressions_7d=c.get("impressions_7d", 0),
                clicks_7d=c.get("clicks_7d", 0),
                installs_7d=c.get("installs_7d", 0),
                ctr_7d=c.get("ctr_7d", 0.0),
                cpi_7d=c.get("cpi_7d", 0.0),
                frequency_7d=c.get("frequency_7d", 0.0),
                ctr_trend=c.get("ctr_trend", 0.0),
                note=c.get("note", ""),
            ))
        return out

    def fatigued_creatives(self) -> List[MetaCreative]:
        return [c for c in self.creatives() if c.is_fatigued]

    def top_creatives(self, n: int = 3) -> List[MetaCreative]:
        return sorted(self.creatives(), key=lambda c: c.ctr_7d, reverse=True)[:n]

    # ------------------------------------------------------------------ #
    def aggregate(self) -> dict:
        return self._data.get("aggregate", {})


__all__ = ["MetaReader", "MetaCreative", "MetaCampaign"]
