"""V4.1 Creative Memory — stores creative assets with versioning."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CreativeRecord:
    creative_id: str = ""
    creative_type: str = ""
    source: str = ""
    performance: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_type": self.creative_type,
            "source": self.source,
            "performance": self.performance,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeRecord:
        return cls(
            creative_id=data.get("creative_id", ""),
            creative_type=data.get("creative_type", ""),
            source=data.get("source", ""),
            performance=data.get("performance", {}),
            version=data.get("version", 1),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            archived=data.get("archived", False),
        )


class CreativeMemory:
    """Stores and manages creative records with versioning."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._dir = Path(storage_dir or "output/creative_brain/memory/creatives")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._versions: dict[str, list[CreativeRecord]] = {}

    def add(self, creative_id: str, creative_type: str = "image",
            source: str = "", performance: dict[str, Any] | None = None) -> CreativeRecord:
        now = datetime.now().isoformat()
        record = CreativeRecord(
            creative_id=creative_id,
            creative_type=creative_type,
            source=source,
            performance=performance or {},
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._versions.setdefault(creative_id, []).append(record)
        self._save(record)
        return record

    def update(self, creative_id: str, **kwargs) -> CreativeRecord | None:
        records = self._versions.get(creative_id, [])
        if not records:
            return None
        latest = records[-1]
        new_version = CreativeRecord(
            creative_id=creative_id,
            creative_type=kwargs.get("creative_type", latest.creative_type),
            source=kwargs.get("source", latest.source),
            performance=kwargs.get("performance", latest.performance),
            version=latest.version + 1,
            created_at=latest.created_at,
            updated_at=datetime.now().isoformat(),
        )
        records.append(new_version)
        self._save(new_version)
        return new_version

    def get(self, creative_id: str) -> CreativeRecord | None:
        records = self._versions.get(creative_id, [])
        return records[-1] if records else self._load(creative_id)

    def get_versions(self, creative_id: str) -> list[CreativeRecord]:
        return self._versions.get(creative_id, [])

    def search(self, query: dict[str, Any] | None = None) -> list[CreativeRecord]:
        results = []
        for cid in self._list_ids():
            record = self.get(cid)
            if record and not record.archived:
                if query:
                    match = True
                    for k, v in query.items():
                        if k == "creative_type" and record.creative_type != v:
                            match = False
                        elif k == "source" and record.source != v:
                            match = False
                    if match:
                        results.append(record)
                else:
                    results.append(record)
        return results

    def archive(self, creative_id: str) -> bool:
        record = self.get(creative_id)
        if record:
            record.archived = True
            self._save(record)
            return True
        return False

    def _save(self, record: CreativeRecord) -> None:
        path = self._dir / f"{record.creative_id}.json"
        path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self, creative_id: str) -> CreativeRecord | None:
        path = self._dir / f"{creative_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            record = CreativeRecord.from_dict(data)
            self._versions.setdefault(creative_id, []).append(record)
            return record
        return None

    def _list_ids(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.json")]