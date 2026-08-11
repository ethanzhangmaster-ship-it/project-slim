"""V4.1 Performance Memory — stores performance metrics with versioning."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PerformanceRecord:
    record_id: str = ""
    creative_id: str = ""
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpm: float = 0.0
    cpi: float = 0.0
    ipm: float = 0.0
    installs: int = 0
    roas_d1: float = 0.0
    roas_d7: float = 0.0
    roas_d30: float = 0.0
    ltv_d30: float = 0.0
    retention_d1: float = 0.0
    retention_d7: float = 0.0
    version: int = 1
    recorded_at: str = ""
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "creative_id": self.creative_id,
            "spend": self.spend,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": self.ctr,
            "cpm": self.cpm,
            "cpi": self.cpi,
            "ipm": self.ipm,
            "installs": self.installs,
            "roas_d1": self.roas_d1,
            "roas_d7": self.roas_d7,
            "roas_d30": self.roas_d30,
            "ltv_d30": self.ltv_d30,
            "retention_d1": self.retention_d1,
            "retention_d7": self.retention_d7,
            "version": self.version,
            "recorded_at": self.recorded_at,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PerformanceRecord:
        return cls(
            record_id=data.get("record_id", ""),
            creative_id=data.get("creative_id", ""),
            spend=data.get("spend", 0.0),
            impressions=data.get("impressions", 0),
            clicks=data.get("clicks", 0),
            ctr=data.get("ctr", 0.0),
            cpm=data.get("cpm", 0.0),
            cpi=data.get("cpi", 0.0),
            ipm=data.get("ipm", 0.0),
            installs=data.get("installs", 0),
            roas_d1=data.get("roas_d1", 0.0),
            roas_d7=data.get("roas_d7", 0.0),
            roas_d30=data.get("roas_d30", 0.0),
            ltv_d30=data.get("ltv_d30", 0.0),
            retention_d1=data.get("retention_d1", 0.0),
            retention_d7=data.get("retention_d7", 0.0),
            version=data.get("version", 1),
            recorded_at=data.get("recorded_at", ""),
            archived=data.get("archived", False),
        )


class PerformanceMemory:
    """Stores performance records with versioning."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._dir = Path(storage_dir or "output/creative_brain/memory/performance")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, PerformanceRecord] = {}

    def add(self, record_id: str, creative_id: str = "", **metrics) -> PerformanceRecord:
        record = PerformanceRecord(
            record_id=record_id,
            creative_id=creative_id,
            recorded_at=datetime.now().isoformat(),
            **{k: v for k, v in metrics.items() if hasattr(PerformanceRecord, k)},
        )
        self._cache[record_id] = record
        self._save(record)
        return record

    def update(self, record_id: str, **kwargs) -> PerformanceRecord | None:
        record = self._cache.get(record_id) or self._load(record_id)
        if not record:
            return None
        for k, v in kwargs.items():
            if hasattr(record, k):
                setattr(record, k, v)
        record.version += 1
        self._save(record)
        return record

    def get(self, record_id: str) -> PerformanceRecord | None:
        return self._cache.get(record_id) or self._load(record_id)

    def search(self, query: dict[str, Any] | None = None) -> list[PerformanceRecord]:
        results = []
        for rid in self._list_ids():
            record = self.get(rid)
            if record and not record.archived:
                if query:
                    match = True
                    for k, v in query.items():
                        if getattr(record, k, None) != v:
                            match = False
                    if match:
                        results.append(record)
                else:
                    results.append(record)
        return results

    def archive(self, record_id: str) -> bool:
        record = self.get(record_id)
        if record:
            record.archived = True
            self._save(record)
            return True
        return False

    def _save(self, record: PerformanceRecord) -> None:
        path = self._dir / f"{record.record_id}.json"
        path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self, record_id: str) -> PerformanceRecord | None:
        path = self._dir / f"{record_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            record = PerformanceRecord.from_dict(data)
            self._cache[record_id] = record
            return record
        return None

    def _list_ids(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.json")]