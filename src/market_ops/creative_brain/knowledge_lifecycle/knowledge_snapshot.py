"""V4.3.5 Knowledge Snapshot — capture current knowledge state.

Captures a complete picture of the knowledge state at a point in time:
  - Patterns (active + deprecated)
  - Graph (nodes + edges)
  - Embeddings (count + dimensions)
  - Retriever index version
  - Confidence calibrations

Used by KnowledgeVersion for versioned snapshots.
"""

from __future__ import annotations

from typing import Any

from .schemas import KnowledgeSnapshot


class KnowledgeSnapshotter:
    """Capture current knowledge state as a snapshot."""

    def __init__(self) -> None:
        self._snapshots: list[KnowledgeSnapshot] = []

    def capture(self,
                patterns: list[dict[str, Any]] | None = None,
                graph_updater=None,
                embedding_refresher=None,
                retriever_rebuilder=None,
                confidence_rebuilder=None,
                summary: str = "") -> KnowledgeSnapshot:
        """Capture current knowledge state from all modules.

        Args:
            patterns: Current pattern states.
            graph_updater: GraphUpdater instance.
            embedding_refresher: EmbeddingRefresher instance.
            retriever_rebuilder: RetrieverRebuilder instance.
            confidence_rebuilder: ConfidenceRebuilder instance.
            summary: Human-readable summary.

        Returns:
            KnowledgeSnapshot.
        """
        active = []
        deprecated = []
        pattern_count = 0

        if patterns:
            for p in patterns:
                pattern_count += 1
                if p.get("status") in ("active", "promoted"):
                    active.append(p.get("name", p.get("pattern_id", "")))
                elif p.get("status") in ("deprecated", "retired"):
                    deprecated.append(p.get("name", p.get("pattern_id", "")))

        snapshot = KnowledgeSnapshot(
            version="",
            timestamp="",
            pattern_count=pattern_count,
            active_patterns=active,
            deprecated_patterns=deprecated,
            graph_node_count=graph_updater.get_node_count() if graph_updater else 0,
            graph_edge_count=graph_updater.get_edge_count() if graph_updater else 0,
            embedding_count=embedding_refresher.embedding_count if embedding_refresher else 0,
            retriever_index_version=(
                retriever_rebuilder.index_version if retriever_rebuilder else ""
            ),
            confidence_calibration=(
                confidence_rebuilder.get_calibration_summary() if confidence_rebuilder else {}
            ),
            summary=summary,
        )

        self._snapshots.append(snapshot)
        return snapshot

    def get_snapshots(self) -> list[KnowledgeSnapshot]:
        return list(self._snapshots)

    def get_latest(self) -> KnowledgeSnapshot | None:
        if self._snapshots:
            return self._snapshots[-1]
        return None