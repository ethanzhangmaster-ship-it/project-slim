"""V4.3.5 Lifecycle Engine — unified knowledge lifecycle orchestrator.

Orchestrates the full knowledge lifecycle:
  Promote → Retire → Update Graph → Refresh Embeddings
  → Rebuild Retriever → Rebuild Confidence → Version Snapshot

Sits between Validation (V4.2.1) and Policy (V4.3).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import (
    PatternLifecycle, LifecycleReport, KnowledgeEvent, PatternStatus,
)
from .pattern_promoter import PatternPromoter
from .pattern_retirer import PatternRetirer
from .graph_updater import GraphUpdater
from .trend_updater import TrendUpdater
from .embedding_refresher import EmbeddingRefresher
from .retriever_rebuilder import RetrieverRebuilder
from .confidence_rebuilder import ConfidenceRebuilder
from .knowledge_version import KnowledgeVersion
from .knowledge_snapshot import KnowledgeSnapshotter
from .lineage_tracker import LineageTracker


class LifecycleEngine:
    """Unified knowledge lifecycle orchestrator.

    Connects Validation feedback to Knowledge updates.
    Ensures knowledge evolves with the market.
    """

    def __init__(self) -> None:
        # Core modules
        self.promoter = PatternPromoter()
        self.retirer = PatternRetirer()
        self.graph = GraphUpdater()
        self.trend = TrendUpdater()
        self.embeddings = EmbeddingRefresher()
        self.retriever = RetrieverRebuilder()
        self.confidence = ConfidenceRebuilder()
        self.version = KnowledgeVersion()
        self.snapshotter = KnowledgeSnapshotter()
        self.lineage = LineageTracker()

        self._run_history: list[LifecycleReport] = []

    def run(self, patterns: list[PatternLifecycle],
            graph_updates: list[dict[str, Any]] | None = None,
            embedding_creatives: list[dict[str, Any]] | None = None,
            trend_updates: list[dict[str, Any]] | None = None,
            confidence_feedback: list[dict[str, Any]] | None = None,
            summary: str = "") -> LifecycleReport:
        """Run the full knowledge lifecycle.

        Args:
            patterns: Current pattern states.
            graph_updates: Validation feedback for graph edges.
            embedding_creatives: New creatives to embed.
            trend_updates: Trend ROAS updates.
            confidence_feedback: Confidence calibration feedback.
            summary: Human-readable summary.

        Returns:
            LifecycleReport with all changes.
        """
        events: list[KnowledgeEvent] = []
        promoted: list[PatternLifecycle] = []
        retired: list[PatternLifecycle] = []
        graph_results: list[Any] = []
        calibrations: list[Any] = []

        # 1. Promote patterns
        self.promoter.evaluate_batch(patterns)
        promoted = [
            p for p in patterns if p.status == PatternStatus.PROMOTED
        ]
        if promoted:
            events.append(KnowledgeEvent.PATTERN_PROMOTED)
            for p in promoted:
                self.lineage.record(
                    knowledge_id=p.pattern_id,
                    knowledge_type="pattern",
                    source="validation",
                    source_creative_id=p.supporting_creatives[0] if p.supporting_creatives else "",
                    version_added=self.version.current.version if self.version.current else "",
                )
                self.lineage.add_update(p.pattern_id, f"Promoted from candidate")

        # 2. Retire patterns
        self.retirer.evaluate_batch(patterns)
        retired = [
            p for p in patterns if p.status == PatternStatus.DEPRECATED
        ]
        if retired:
            events.append(KnowledgeEvent.PATTERN_RETIRED)
            for p in retired:
                self.lineage.add_retirement(
                    p.pattern_id,
                    f"ROAS dropped to {p.current_roas}",
                    self.version.current.version if self.version.current else "",
                )

        # 3. Update graph
        if graph_updates:
            self.graph.update_from_validation(graph_updates)
            events.append(KnowledgeEvent.GRAPH_UPDATED)
            graph_results = self.graph.get_update_history()[-len(graph_updates):]

        # 4. Update trends
        if trend_updates:
            self.trend.update_batch(trend_updates)
            events.append(KnowledgeEvent.TREND_UPDATED)

        # 5. Refresh embeddings
        if embedding_creatives:
            self.embeddings.refresh_batch(embedding_creatives)
            events.append(KnowledgeEvent.EMBEDDING_REFRESHED)
            for c in embedding_creatives:
                self.lineage.record(
                    knowledge_id=f"embedding:{c['creative_id']}",
                    knowledge_type="embedding",
                    source="creative",
                    source_creative_id=c["creative_id"],
                    version_added=self.version.current.version if self.version.current else "",
                )

        # 6. Rebuild retriever
        if self.embeddings.embedding_count > 0:
            self.retriever.rebuild(
                self.embeddings.get_all_embeddings(),
                new_version=f"idx_{self.retriever.rebuild_count + 1}",
            )
            events.append(KnowledgeEvent.RETRIEVER_REBUILT)

        # 7. Rebuild confidence
        if confidence_feedback:
            calibrations = self.confidence.calibrate_batch(confidence_feedback)
            events.append(KnowledgeEvent.CONFIDENCE_REBUILT)

        # 8. Version snapshot
        snapshot = self.version.snapshot(
            pattern_count=len(patterns),
            active_patterns=[p.name for p in patterns if p.status in (PatternStatus.ACTIVE, PatternStatus.PROMOTED)],
            deprecated_patterns=[p.name for p in patterns if p.status == PatternStatus.DEPRECATED],
            graph_node_count=self.graph.get_node_count(),
            graph_edge_count=self.graph.get_edge_count(),
            embedding_count=self.embeddings.embedding_count,
            retriever_index_version=self.retriever.index_version,
            confidence_calibration=self.confidence.get_calibration_summary(),
            summary=summary,
        )
        events.append(KnowledgeEvent.VERSION_SNAPSHOT)

        # Build report
        report = LifecycleReport(
            timestamp=datetime.now().isoformat(),
            version_from=self.version.current.version if self.version.current else "",
            version_to=snapshot.version,
            events=events,
            patterns_promoted=len(promoted),
            patterns_retired=len(retired),
            graph_edges_updated=len(graph_results),
            embeddings_refreshed=len(embedding_creatives or []),
            retriever_rebuilt=(KnowledgeEvent.RETRIEVER_REBUILT in events),
            confidence_rebuilt=(KnowledgeEvent.CONFIDENCE_REBUILT in events),
            trends_updated=len(trend_updates or []),
            promoted=promoted,
            retired=retired,
            graph_updates=graph_results,
            calibrations=calibrations,
            snapshot=snapshot,
            summary=summary,
        )

        self._run_history.append(report)
        return report

    def rollback(self, version: str) -> dict[str, Any] | None:
        """Rollback knowledge to a previous version."""
        snapshot = self.version.rollback(version)
        if not snapshot:
            return None

        return {
            "rolled_back_to": version,
            "snapshot": snapshot.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }

    def get_run_history(self) -> list[LifecycleReport]:
        return list(self._run_history)

    def get_status(self) -> dict[str, Any]:
        """Get current lifecycle engine status."""
        return {
            "patterns": {
                "promoted": len(self.promoter.get_promotion_history()),
            },
            "graph": {
                "nodes": self.graph.get_node_count(),
                "edges": self.graph.get_edge_count(),
            },
            "embeddings": {
                "count": self.embeddings.embedding_count,
                "dim": self.embeddings.vector_dim,
            },
            "retriever": {
                "version": self.retriever.index_version,
                "size": self.retriever.index_size,
            },
            "confidence": self.confidence.get_calibration_summary(),
            "version": {
                "current": self.version.current.version if self.version.current else "none",
                "count": self.version.version_count,
            },
            "lineage": {
                "records": self.lineage.record_count,
            },
        }