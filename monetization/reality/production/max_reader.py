"""
E14.7.1 — MAX Reader (sample-backed, pluggable for real API)

Reads AppLovin MAX performance data: eCPM, impressions, revenue, fill rate
per country + ad format. READ-ONLY — never writes to MAX.

In production, replace ``_load()`` with a MAX API client.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class MaxAdUnitSnapshot:
    country: str
    format: str                       # reward | interstitial | banner
    network: str
    date: str
    impressions: int = 0
    ecpm: float = 0.0
    revenue: float = 0.0
    fill_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "country": self.country, "format": self.format,
            "network": self.network, "date": self.date,
            "impressions": self.impressions,
            "ecpm": round(self.ecpm, 2), "revenue": round(self.revenue, 2),
            "fill_rate": round(self.fill_rate, 4),
        }


@dataclass
class MaxTrend:
    country: str
    format: str
    ecpm_7d_pct: float = 0.0         # relative change
    impressions_7d_pct: float = 0.0
    revenue_7d_pct: float = 0.0
    fill_rate_delta: float = 0.0
    note: str = ""

    @property
    def is_risk(self) -> bool:
        return abs(self.ecpm_7d_pct) > 0.10

    def to_dict(self) -> dict:
        return {
            "country": self.country, "format": self.format,
            "ecpm_7d_pct": round(self.ecpm_7d_pct, 4),
            "revenue_7d_pct": round(self.revenue_7d_pct, 4),
            "fill_rate_delta": round(self.fill_rate_delta, 4),
            "risk": self.is_risk, "note": self.note,
        }


class MaxReader:
    """Reads MAX monetization performance data. READ-ONLY."""

    def __init__(self, data_path: Optional[str] = None):
        self._data: dict = {}
        if data_path:
            self._load(data_path)

    def _load(self, path: str) -> None:
        self._data = json.loads(Path(path).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ #
    def daily_snapshots(self) -> List[MaxAdUnitSnapshot]:
        out = []
        units = self._data.get("ad_units_by_country_format", {})
        for key, unit in units.items():
            country = unit["country"]
            fmt = unit["format"]
            network = unit.get("network", "applovin")
            for date, vals in unit.get("daily", {}).items():
                out.append(MaxAdUnitSnapshot(
                    country=country, format=fmt, network=network, date=date,
                    impressions=vals.get("impressions", 0),
                    ecpm=vals.get("ecpm", 0.0),
                    revenue=vals.get("revenue", 0.0),
                    fill_rate=vals.get("fill_rate", 0.0),
                ))
        return sorted(out, key=lambda s: (s.country, s.format, s.date))

    def latest_for_unit(self, country: str, fmt: str) -> Optional[MaxAdUnitSnapshot]:
        snaps = [s for s in self.daily_snapshots()
                 if s.country == country and s.format == fmt]
        return snaps[-1] if snaps else None

    # ------------------------------------------------------------------ #
    def trends(self) -> List[MaxTrend]:
        out = []
        units = self._data.get("ad_units_by_country_format", {})
        for key, unit in units.items():
            tr = unit.get("trend", {})
            if tr:
                out.append(MaxTrend(
                    country=unit["country"], format=unit["format"],
                    ecpm_7d_pct=tr.get("ecpm_7d_pct", 0.0),
                    impressions_7d_pct=tr.get("impressions_7d_pct", 0.0),
                    revenue_7d_pct=tr.get("revenue_7d_pct", 0.0),
                    fill_rate_delta=tr.get("fill_rate_delta", 0.0),
                    note=tr.get("note", ""),
                ))
        return out

    def risk_trends(self) -> List[MaxTrend]:
        return [t for t in self.trends() if t.is_risk]

    # ------------------------------------------------------------------ #
    def aggregate(self) -> dict:
        return self._data.get("aggregate", {})
