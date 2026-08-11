"""E16.6.2 — ASO Feature Store: JSONL historical reality + reviews.

Lean principle (per project charter): pure Python + JSONL, no external DB.
Default layout::

    data/aso/snapshots.jsonl   # one ASORealitySnapshot (+ quality) per line
    data/aso/reviews.jsonl     # one ReviewRecord per line
    data/aso/keywords.jsonl    # keyword-ranking rows (trend, used by E16.6.4)

All queries are (game_id, platform) isolated so a game's Android and iOS
reality never cross-contaminate. Append-only; bad lines are skipped.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ASORealitySnapshot, Platform, ReviewRecord

_DEFAULT_DIR = Path("data") / "aso"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ASOFeatureStore:
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else _DEFAULT_DIR
        self.snapshots_path = self.base_dir / "snapshots.jsonl"
        self.reviews_path = self.base_dir / "reviews.jsonl"
        self.keywords_path = self.base_dir / "keywords.jsonl"

    # ------------------------------------------------------------------ #
    # write
    # ------------------------------------------------------------------ #
    def record_snapshot(
        self, snap: ASORealitySnapshot, quality: Any = None
    ) -> None:
        rec = snap.to_dict()
        rec["quality"] = quality.to_dict() if quality is not None else None
        self._append(self.snapshots_path, rec)

    def record_reviews(
        self, game_id: str, platform: Platform, reviews: List[ReviewRecord]
    ) -> int:
        count = 0
        for r in reviews:
            self._append(self.reviews_path, r.to_dict())
            count += 1
        return count

    def record_keywords(
        self, game_id: str, platform: Platform, rankings: List[Any]
    ) -> int:
        count = 0
        for k in rankings:
            rec = k.to_dict() if hasattr(k, "to_dict") else dict(k)
            rec = dict(rec)
            rec["game_id"] = game_id
            rec["platform"] = platform.value
            self._append(self.keywords_path, rec)
            count += 1
        return count

    @staticmethod
    def _append(path: Path, obj: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    # read
    # ------------------------------------------------------------------ #
    @staticmethod
    def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except (json.JSONDecodeError, TypeError):
                    continue  # bad line skipped, rest intact
        return out

    @staticmethod
    def _match(rec: Dict[str, Any], game_id: str, platform: Platform) -> bool:
        return (
            rec.get("game_id") == game_id
            and rec.get("platform") == platform.value
        )

    def history(
        self,
        game_id: str,
        platform: Platform,
        days: Optional[int] = None,
    ) -> List[ASORealitySnapshot]:
        rows = [
            r for r in self._read_jsonl(self.snapshots_path)
            if self._match(r, game_id, platform)
        ]
        rows.sort(key=lambda r: r.get("timestamp", ""))
        if days is not None:
            cutoff = (_utcnow() - timedelta(days=days)).isoformat()
            rows = [r for r in rows if r.get("timestamp", "") >= cutoff]
        return [ASORealitySnapshot.from_dict(r) for r in rows]

    def latest(
        self, game_id: str, platform: Platform
    ) -> Optional[ASORealitySnapshot]:
        rows = self.history(game_id, platform)
        return rows[-1] if rows else None

    def latest_reviews(
        self, game_id: str, platform: Platform, limit: int = 100
    ) -> List[ReviewRecord]:
        rows = [
            r for r in self._read_jsonl(self.reviews_path)
            if self._match(r, game_id, platform)
        ]
        rows.sort(key=lambda r: r.get("reviewed_at") or "")
        rows = rows[-limit:]
        return [ReviewRecord.from_dict(r) for r in rows]


__all__ = ["ASOFeatureStore"]
