"""V4.1 DNA Memory — stores DNA records with versioning."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class DNARecord:
    dna_id: str = ""
    creative_id: str = ""
    dna_type: str = ""
    dna_data: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    created_at: str = ""
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna_id": self.dna_id,
            "creative_id": self.creative_id,
            "dna_type": self.dna_type,
            "dna_data": self.dna_data,
            "version": self.version,
            "created_at": self.created_at,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DNARecord:
        return cls(
            dna_id=data.get("dna_id", ""),
            creative_id=data.get("creative_id", ""),
            dna_type=data.get("dna_type", ""),
            dna_data=data.get("dna_data", {}),
            version=data.get("version", 1),
            created_at=data.get("created_at", ""),
            archived=data.get("archived", False),
        )


class DNAMemory:
    """Stores DNA records with versioning."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._dir = Path(storage_dir or "output/creative_brain/memory/dna")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, DNARecord] = {}

    def add(self, dna_id: str, creative_id: str = "",
            dna_type: str = "", dna_data: dict[str, Any] | None = None) -> DNARecord:
        record = DNARecord(
            dna_id=dna_id,
            creative_id=creative_id,
            dna_type=dna_type,
            dna_data=dna_data or {},
            created_at=datetime.now().isoformat(),
        )
        self._cache[dna_id] = record
        self._save(record)
        return record

    def update(self, dna_id: str, **kwargs) -> DNARecord | None:
        record = self._cache.get(dna_id) or self._load(dna_id)
        if not record:
            return None
        for k, v in kwargs.items():
            if hasattr(record, k):
                setattr(record, k, v)
        record.version += 1
        self._save(record)
        return record

    def get(self, dna_id: str) -> DNARecord | None:
        return self._cache.get(dna_id) or self._load(dna_id)

    def search(self, query: dict[str, Any] | None = None) -> list[DNARecord]:
        results = []
        for did in self._list_ids():
            record = self.get(did)
            if record and not record.archived:
                if query:
                    match = True
                    for k, v in query.items():
                        if k == "dna_type" and record.dna_type != v:
                            match = False
                    if match:
                        results.append(record)
                else:
                    results.append(record)
        return results

    def archive(self, dna_id: str) -> bool:
        record = self.get(dna_id)
        if record:
            record.archived = True
            self._save(record)
            return True
        return False

    def _save(self, record: DNARecord) -> None:
        path = self._dir / f"{record.dna_id}.json"
        path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self, dna_id: str) -> DNARecord | None:
        path = self._dir / f"{dna_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            record = DNARecord.from_dict(data)
            self._cache[dna_id] = record
            return record
        return None

    def _list_ids(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.json")]