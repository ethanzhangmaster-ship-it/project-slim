"""V4.0: Eagle Adapter — wraps existing Creative Mapping Engine.

Bridges Eagle local video library into the Creative Repository.
Reuses existing creative_mapping/engine.py for Facebook ↔ Eagle matching.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class EagleAdapter:
    """Adapter for Eagle local video library → Creative Repository.

    Wraps the existing Creative Mapping Engine (multi-layer matching:
    hash exact, name similarity, token overlap, duration verification).
    """

    def __init__(self, eagle_index_path: str | None = None) -> None:
        self._index_path = eagle_index_path
        self._index: dict[str, Any] = {}

    def load_index(self, index_path: str | None = None) -> dict[str, Any]:
        """Load Eagle video index from JSON file."""
        import json
        path = index_path or self._index_path
        if path and Path(path).exists():
            self._index = json.loads(Path(path).read_text(encoding="utf-8"))
        return self._index

    def match(self, facebook_video_id: str, creative_name: str = "") -> dict[str, Any] | None:
        """Match a Facebook video ID to an Eagle local video.

        Uses the existing Creative Mapping Engine's multi-layer matching:
        1. Exact hash suffix match (highest confidence)
        2. Name similarity + token overlap
        3. Duration verification (via ffprobe)
        """
        try:
            from market_ops.video_intelligence.creative_mapping.engine import match_best

            fb_meta = {
                "fb_duration": None,
                "fb_width": None,
                "fb_height": None,
            }

            result = match_best(creative_name, fb_meta, self._index)
            return result
        except ImportError:
            pass

        # Fallback: simple filename match
        for name, entries in self._index.items():
            if facebook_video_id in name:
                entry = entries[0] if entries else {}
                return {
                    "local_path": entry.get("filepath", ""),
                    "local_filename": entry.get("filename", ""),
                    "confidence": 0.8,
                    "match_method": "id_match",
                }
        return None

    def get_video_path(self, match_result: dict[str, Any]) -> str:
        """Get the local video file path from a match result."""
        return match_result.get("local_path", "")

    @property
    def available(self) -> bool:
        return bool(self._index)