"""
E14.7.1 — Adjust Reader (sample-backed, pluggable for real API)

Reads Adjust data: daily installs/sessions/revenue by platform,
cohort retention, and payer conversion.

In production, replace ``_load()`` with an Adjust API client.
The public interface (``daily_snapshots()``, ``cohorts()``, ``trends()``)
stays the same.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class AdjustDailySnapshot:
    date: str
    platform: str
    installs: int = 0
    sessions: int = 0
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    dau: int = 0

    @property
    def arpdau(self) -> float:
        return ((self.iap_revenue + self.ad_revenue) / self.dau) if self.dau else 0.0

    def to_dict(self) -> dict:
        return {
            "date": self.date, "platform": self.platform,
            "installs": self.installs, "sessions": self.sessions,
            "iap_revenue": self.iap_revenue, "ad_revenue": self.ad_revenue,
            "dau": self.dau, "arpdau": round(self.arpdau, 4),
        }


@dataclass
class AdjustCohort:
    platform: str
    d1: float = 0.0
    d3: float = 0.0
    d7: float = 0.0
    d30: float = 0.0
    d120: float = 0.0
    payer_d7: float = 0.0
    payer_d30: float = 0.0

    def to_dict(self) -> dict:
        return {
            "platform": self.platform, "d1": self.d1, "d3": self.d3,
            "d7": self.d7, "d30": self.d30, "d120": self.d120,
            "payer_d7": self.payer_d7, "payer_d30": self.payer_d30,
        }


@dataclass
class AdjustTrends:
    platform: str
    installs_7d_pct: float = 0.0
    arpdau: float = 0.0
    payer_conversion: float = 0.0

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "installs_7d_pct": self.installs_7d_pct,
            "arpdau": self.arpdau,
            "payer_conversion": self.payer_conversion,
        }


class AdjustReader:
    """Reads Adjust analytics data. File-backed for v1; swap to API later."""

    def __init__(self, data_path: Optional[str] = None):
        self._data: dict = {}
        if data_path:
            self._load(data_path)

    def _load(self, path: str) -> None:
        self._data = json.loads(Path(path).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ #
    def daily_snapshots(self) -> List[AdjustDailySnapshot]:
        out = []
        daily = self._data.get("daily", {})
        for date, platforms in sorted(daily.items()):
            for platform, vals in platforms.items():
                out.append(AdjustDailySnapshot(
                    date=date, platform=platform,
                    installs=vals.get("installs", 0),
                    sessions=vals.get("sessions", 0),
                    iap_revenue=vals.get("iap_revenue", 0.0),
                    ad_revenue=vals.get("ad_revenue", 0.0),
                    dau=vals.get("dau", 0),
                ))
        return out

    def latest_snapshot(self, platform: str) -> Optional[AdjustDailySnapshot]:
        snaps = [s for s in self.daily_snapshots() if s.platform == platform]
        return snaps[-1] if snaps else None

    # ------------------------------------------------------------------ #
    def cohorts(self) -> List[AdjustCohort]:
        out = []
        coh = self._data.get("cohorts", {})
        for platform, vals in coh.items():
            out.append(AdjustCohort(
                platform=platform,
                d1=vals.get("d1", 0.0), d3=vals.get("d3", 0.0),
                d7=vals.get("d7", 0.0), d30=vals.get("d30", 0.0),
                d120=vals.get("d120", 0.0),
                payer_d7=vals.get("payer_d7", 0.0),
                payer_d30=vals.get("payer_d30", 0.0),
            ))
        return out

    # ------------------------------------------------------------------ #
    def trends(self) -> List[AdjustTrends]:
        out = []
        tr = self._data.get("trends", {})
        for platform in ("ios", "android"):
            out.append(AdjustTrends(
                platform=platform,
                installs_7d_pct=tr.get(f"{platform}_installs_7d_pct", 0.0),
                arpdau=tr.get(f"{platform}_arpdau", 0.0),
                payer_conversion=tr.get(f"{platform}_payer_conversion", 0.0),
            ))
        return out


__all__ = ["AdjustReader", "AdjustDailySnapshot", "AdjustCohort", "AdjustTrends"]
