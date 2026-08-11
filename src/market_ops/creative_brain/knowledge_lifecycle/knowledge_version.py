"""V4.3.5 Knowledge Version — versioned snapshots with rollback.

Every knowledge update creates a new version:
  knowledge_v1 → knowledge_v2 → knowledge_v3

Supports rollback to any previous version.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import KnowledgeSnapshot, KnowledgeEvent


class KnowledgeVersion:
    """Versioned knowledge state management with rollback."""

    def __init__(self) -> None:
        self._versions: list[KnowledgeSnapshot] = []
        self._current_idx: int = -1
        self._initial_version = "knowledge_v1.0"

    def snapshot(self, pattern_count: int = 0,
                 active_patterns: list[str] | None = None,
                 deprecated_patterns: list[str] | None = None,
                 graph_node_count: int = 0,
                 graph_edge_count: int = 0,
                 embedding_count: int = 0,
                 retriever_index_version: str = "",
                 confidence_calibration: dict[str, float] | None = None,
                 summary: str = "") -> KnowledgeSnapshot:
        """Create a new knowledge version snapshot.

        Returns the new snapshot with auto-incremented version.
        """
        version_num = len(self._versions) + 1
        version = f"knowledge_v{version_num}.0"

        snapshot = KnowledgeSnapshot(
            version=version,
            timestamp=datetime.now().isoformat(),
            pattern_count=pattern_count,
            active_patterns=active_patterns or [],
            deprecated_patterns=deprecated_patterns or [],
            graph_node_count=graph_node_count,
            graph_edge_count=graph_edge_count,
            embedding_count=embedding_count,
            retriever_index_version=retriever_index_version,
            confidence_calibration=confidence_calibration or {},
            summary=summary,
        )

        self._versions.append(snapshot)
        self._current_idx = len(self._versions) - 1
        return snapshot

    def rollback(self, version: str) -> KnowledgeSnapshot | None:
        """Rollback to a specific version.

        Args:
            version: Version string like "knowledge_v2.0".

        Returns:
            The restored snapshot, or None if version not found.
        """
        for i, snap in enumerate(self._versions):
            if snap.version == version:
                self._current_idx = i
                return snap
        return None

    def rollback_to_previous(self) -> KnowledgeSnapshot | None:
        """Rollback to the immediately previous version."""
        if self._current_idx > 0:
            self._current_idx -= 1
            return self.current
        return None

    @property
    def current(self) -> KnowledgeSnapshot | None:
        """Get current active version."""
        if self._current_idx >= 0 and self._current_idx < len(self._versions):
            return self._versions[self._current_idx]
        return None

    @property
    def latest(self) -> KnowledgeSnapshot | None:
        """Get latest created version."""
        if self._versions:
            return self._versions[-1]
        return None

    def get_version(self, version: str) -> KnowledgeSnapshot | None:
        """Get a specific version by string."""
        for snap in self._versions:
            if snap.version == version:
                return snap
        return None

    def list_versions(self) -> list[dict[str, Any]]:
        """List all versions with summary."""
        return [
            {
                "version": snap.version,
                "timestamp": snap.timestamp,
                "patterns": snap.pattern_count,
                "is_current": (i == self._current_idx),
                "summary": snap.summary,
            }
            for i, snap in enumerate(self._versions)
        ]

    def get_all_versions(self) -> list[KnowledgeSnapshot]:
        """Get all version snapshots."""
        return list(self._versions)

    def compare_versions(self, v1: str, v2: str) -> dict[str, Any]:
        """Compare two versions."""
        snap1 = self.get_version(v1)
        snap2 = self.get_version(v2)
        if not snap1 or not snap2:
            return {"error": "Version not found"}

        return {
            "version_a": v1,
            "version_b": v2,
            "pattern_diff": snap2.pattern_count - snap1.pattern_count,
            "graph_node_diff": snap2.graph_node_count - snap1.graph_node_count,
            "graph_edge_diff": snap2.graph_edge_count - snap1.graph_edge_count,
            "embedding_diff": snap2.embedding_count - snap1.embedding_count,
        }

    @property
    def version_count(self) -> int:
        return len(self._versions)