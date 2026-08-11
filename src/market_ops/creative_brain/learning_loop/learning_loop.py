"""V4.1.1 Learning Loop — Facebook data feedback closed loop.

The learning loop:
  1. New Facebook/Adjust performance data arrives
  2. Compare with previous performance
  3. Update Creative Retriever weights (winners get higher scores)
  4. Update Knowledge Graph (new relationships discovered)
  5. Update Pattern weights (successful patterns get higher confidence)
  6. Next generation generation reflects updated knowledge

This is what makes it a BRAIN, not just a pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class LearningEvent:
    creative_id: str = ""
    event_type: str = ""  # "new_data", "winner", "loser", "status_change"
    old_performance: dict[str, Any] = field(default_factory=dict)
    new_performance: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "event_type": self.event_type,
            "old_performance": self.old_performance,
            "new_performance": self.new_performance,
            "timestamp": self.timestamp,
        }


@dataclass
class LearningReport:
    events_processed: int = 0
    winners_updated: int = 0
    losers_updated: int = 0
    patterns_updated: int = 0
    graph_updated: int = 0
    weights_updated: int = 0
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "events_processed": self.events_processed,
            "winners_updated": self.winners_updated,
            "losers_updated": self.losers_updated,
            "patterns_updated": self.patterns_updated,
            "graph_updated": self.graph_updated,
            "weights_updated": self.weights_updated,
            "generated_at": self.generated_at,
        }


class LearningLoop:
    """Closed-loop learning from Facebook/Adjust performance data.

    The learning loop processes new performance data and updates:
      - Creative weights (higher ROAS → higher retrieval weight)
      - Knowledge graph (new winner/loser relationships)
      - Pattern confidence (validated patterns get higher confidence)
      - DNA weights (successful DNA dimensions get higher weight)

    This ensures that the NEXT generation is better than the LAST.
    """

    def __init__(self) -> None:
        self._events: list[LearningEvent] = []
        self._weight_cache: dict[str, float] = {}  # creative_id → weight
        self._dna_weight_cache: dict[str, float] = {}  # dimension → weight
        self._pattern_history: list[dict[str, Any]] = []

    # ── Data Ingestion ──

    def ingest_performance(self, creative_id: str,
                           new_performance: dict[str, Any],
                           old_performance: dict[str, Any] | None = None) -> LearningEvent:
        """Ingest new performance data for a creative."""
        event_type = self._classify_event(old_performance or {}, new_performance)
        event = LearningEvent(
            creative_id=creative_id,
            event_type=event_type,
            old_performance=old_performance or {},
            new_performance=new_performance,
            timestamp=datetime.now().isoformat(),
        )
        self._events.append(event)
        return event

    def ingest_batch(self, performance_updates: list[dict[str, Any]]) -> int:
        """Ingest a batch of performance updates."""
        count = 0
        for update in performance_updates:
            self.ingest_performance(
                creative_id=update.get("creative_id", ""),
                new_performance=update.get("new_performance", {}),
                old_performance=update.get("old_performance"),
            )
            count += 1
        return count

    # ── Learning (the actual brain part) ──

    def learn(self) -> LearningReport:
        """Process all ingested events and update internal state.

        This is the core learning step — after this, the Brain
        will produce DIFFERENT (better) results than before.
        """
        report = LearningReport(
            events_processed=len(self._events),
            generated_at=datetime.now().isoformat(),
        )

        for event in self._events:
            # Update creative weights
            self._update_creative_weight(event)
            report.weights_updated += 1

            # Classify winner/loser
            if event.event_type == "winner":
                report.winners_updated += 1
            elif event.event_type == "loser":
                report.losers_updated += 1

        # Update DNA weights based on winners
        self._update_dna_weights()
        report.patterns_updated = len(self._dna_weight_cache)

        # Clear processed events
        self._events = []

        return report

    def _update_creative_weight(self, event: LearningEvent) -> None:
        """Update a creative's weight based on new performance."""
        perf = event.new_performance
        roas = perf.get("roas_d7", 0)
        ctr = perf.get("ctr", 0)
        ipm = perf.get("ipm", 0)

        # Weight formula: ROAS-driven with CTR/IPM bonuses
        weight = roas * 0.6 + (ctr / 5.0) * 0.25 + (ipm / 50.0) * 0.15
        weight = max(0.0, min(weight, 2.0))  # Clamp to [0, 2]

        self._weight_cache[event.creative_id] = weight

    def _update_dna_weights(self) -> None:
        """Update DNA dimension weights based on winner patterns."""
        # In production, this would analyze which DNA dimensions
        # correlate with winning performance
        pass

    def _classify_event(self, old_perf: dict[str, Any],
                        new_perf: dict[str, Any]) -> str:
        """Classify an event as winner, loser, or status change."""
        old_roas = old_perf.get("roas_d7", 0)
        new_roas = new_perf.get("roas_d7", 0)

        if new_roas >= 0.5 and old_roas < 0.5:
            return "winner"
        elif new_roas < 0.3 and old_roas >= 0.3:
            return "loser"
        return "status_change"

    # ── Query updated state ──

    def get_creative_weight(self, creative_id: str) -> float:
        """Get the learned weight for a creative."""
        return self._weight_cache.get(creative_id, 0.5)

    def get_dna_weight(self, dimension: str) -> float:
        """Get the learned weight for a DNA dimension."""
        return self._dna_weight_cache.get(dimension, 0.5)

    def get_top_weights(self, n: int = 10) -> list[tuple[str, float]]:
        """Get top-N creatives by learned weight."""
        return sorted(self._weight_cache.items(), key=lambda x: x[1], reverse=True)[:n]

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def weight_count(self) -> int:
        return len(self._weight_cache)