"""V4.3.5 Lineage Tracker — track knowledge provenance.

Every piece of knowledge knows its origin:
  Dragon Collection → Facebook → Creative 318 → 2026-07-14
  → Reasoning → Validation → Knowledge

Evidence Traceable for every knowledge item.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import LineageRecord


class LineageTracker:
    """Track provenance for all knowledge items."""

    def __init__(self) -> None:
        self._lineages: dict[str, LineageRecord] = {}  # knowledge_id → record
        self._tracking_history: list[dict[str, Any]] = []

    def record(self, knowledge_id: str, knowledge_type: str,
               source: str = "", source_creative_id: str = "",
               version_added: str = "") -> LineageRecord:
        """Create a lineage record for new knowledge.

        Args:
            knowledge_id: Unique knowledge identifier.
            knowledge_type: pattern / graph_edge / trend / embedding.
            source: Origin (facebook / reasoning / validation).
            source_creative_id: Source creative ID.
            version_added: Knowledge version when added.

        Returns:
            LineageRecord.
        """
        record = LineageRecord(
            knowledge_id=knowledge_id,
            knowledge_type=knowledge_type,
            source=source,
            source_creative_id=source_creative_id,
            created_at=datetime.now().isoformat(),
            version_added=version_added,
            full_lineage=[f"Created from {source}"],
        )

        self._lineages[knowledge_id] = record
        self._tracking_history.append({
            "event": "created",
            "knowledge_id": knowledge_id,
            "timestamp": record.created_at,
        })
        return record

    def add_validation(self, knowledge_id: str, result: str,
                       version: str = "") -> LineageRecord | None:
        """Add validation step to lineage.

        Args:
            knowledge_id: Knowledge identifier.
            result: confirmed / rejected / updated.
            version: Version when validated.

        Returns:
            Updated LineageRecord or None if not found.
        """
        if knowledge_id not in self._lineages:
            return None

        record = self._lineages[knowledge_id]
        record.validated_at = datetime.now().isoformat()
        record.validation_result = result
        record.full_lineage.append(f"Validated: {result}")

        self._tracking_history.append({
            "event": "validated",
            "knowledge_id": knowledge_id,
            "result": result,
            "timestamp": record.validated_at,
        })
        return record

    def add_update(self, knowledge_id: str, change: str,
                   version: str = "") -> LineageRecord | None:
        """Add update step to lineage.

        Args:
            knowledge_id: Knowledge identifier.
            change: Description of what changed.
            version: Version when updated.

        Returns:
            Updated LineageRecord or None if not found.
        """
        if knowledge_id not in self._lineages:
            return None

        record = self._lineages[knowledge_id]
        record.full_lineage.append(f"Updated: {change}")

        self._tracking_history.append({
            "event": "updated",
            "knowledge_id": knowledge_id,
            "change": change,
            "timestamp": datetime.now().isoformat(),
        })
        return record

    def add_retirement(self, knowledge_id: str, reason: str,
                       version: str = "") -> LineageRecord | None:
        """Add retirement step to lineage."""
        if knowledge_id not in self._lineages:
            return None

        record = self._lineages[knowledge_id]
        record.version_retired = version
        record.full_lineage.append(f"Retired ({version}): {reason}")

        self._tracking_history.append({
            "event": "retired",
            "knowledge_id": knowledge_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })
        return record

    def get_lineage(self, knowledge_id: str) -> LineageRecord | None:
        """Get full lineage for a knowledge item."""
        return self._lineages.get(knowledge_id)

    def get_all_lineages(self) -> dict[str, LineageRecord]:
        """Get all lineage records."""
        return dict(self._lineages)

    def get_by_type(self, knowledge_type: str) -> list[LineageRecord]:
        """Get all lineages of a specific type."""
        return [
            l for l in self._lineages.values()
            if l.knowledge_type == knowledge_type
        ]

    def get_by_source(self, source: str) -> list[LineageRecord]:
        """Get all lineages from a specific source."""
        return [
            l for l in self._lineages.values()
            if l.source == source
        ]

    def get_unvalidated(self) -> list[LineageRecord]:
        """Get knowledge items that haven't been validated yet."""
        return [
            l for l in self._lineages.values()
            if not l.validated_at
        ]

    def get_tracking_history(self) -> list[dict[str, Any]]:
        return list(self._tracking_history)

    @property
    def record_count(self) -> int:
        return len(self._lineages)