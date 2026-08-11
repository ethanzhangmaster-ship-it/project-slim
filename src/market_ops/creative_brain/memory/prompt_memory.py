"""V4.1 Prompt Memory — stores generated prompts with versioning."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PromptRecord:
    prompt_id: str = ""
    creative_id: str = ""
    model: str = ""
    positive_prompt: str = ""
    negative_prompt: str = ""
    score: float = 0.0
    strategy: str = ""
    version: int = 1
    created_at: str = ""
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "creative_id": self.creative_id,
            "model": self.model,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "score": self.score,
            "strategy": self.strategy,
            "version": self.version,
            "created_at": self.created_at,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptRecord:
        return cls(
            prompt_id=data.get("prompt_id", ""),
            creative_id=data.get("creative_id", ""),
            model=data.get("model", ""),
            positive_prompt=data.get("positive_prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            score=data.get("score", 0.0),
            strategy=data.get("strategy", ""),
            version=data.get("version", 1),
            created_at=data.get("created_at", ""),
            archived=data.get("archived", False),
        )


class PromptMemory:
    """Stores prompt records with versioning."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._dir = Path(storage_dir or "output/creative_brain/memory/prompts")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, PromptRecord] = {}

    def add(self, prompt_id: str, creative_id: str = "", model: str = "",
            positive_prompt: str = "", negative_prompt: str = "",
            score: float = 0.0, strategy: str = "") -> PromptRecord:
        record = PromptRecord(
            prompt_id=prompt_id,
            creative_id=creative_id,
            model=model,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            score=score,
            strategy=strategy,
            created_at=datetime.now().isoformat(),
        )
        self._cache[prompt_id] = record
        self._save(record)
        return record

    def update(self, prompt_id: str, **kwargs) -> PromptRecord | None:
        record = self._cache.get(prompt_id) or self._load(prompt_id)
        if not record:
            return None
        for k, v in kwargs.items():
            if hasattr(record, k):
                setattr(record, k, v)
        record.version += 1
        self._save(record)
        return record

    def get(self, prompt_id: str) -> PromptRecord | None:
        return self._cache.get(prompt_id) or self._load(prompt_id)

    def search(self, query: dict[str, Any] | None = None) -> list[PromptRecord]:
        results = []
        for pid in self._list_ids():
            record = self.get(pid)
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

    def archive(self, prompt_id: str) -> bool:
        record = self.get(prompt_id)
        if record:
            record.archived = True
            self._save(record)
            return True
        return False

    def _save(self, record: PromptRecord) -> None:
        path = self._dir / f"{record.prompt_id}.json"
        path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self, prompt_id: str) -> PromptRecord | None:
        path = self._dir / f"{prompt_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            record = PromptRecord.from_dict(data)
            self._cache[prompt_id] = record
            return record
        return None

    def _list_ids(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.json")]