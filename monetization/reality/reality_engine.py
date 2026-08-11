"""
E13.3.1 — Reality Engine (orchestrator)
========================================

Ties the four modules into the continuous fact-generation layer:

    ingest(event)  -> GameEventStream  (append + optional JSONL log)
         |
    update()       -> SegmentEngine.segment_aggregate(stream)
         |
                    -> FactBuilder.build_reality_facts
         |
    store.put(facts) -> MetricStore (memory + JSON file)

    detect()       -> reuses E13.2.8 Opportunity Detector on base-grain facts
                     (this is the input seam for E13.3.2 Strategy Engine)

Lean: no database. Stream + store persist to local files when paths given.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from monetization.facts import MonetizationFact
from monetization.reality.event_stream import GameEventStream
from monetization.reality.fact_builder import build_reality_facts
from monetization.reality.metric_store import MetricStore
from monetization.reality.segment_engine import RichAggregatedData, segment_aggregate


class RealityEngine:
    def __init__(self, store: Optional[MetricStore] = None,
                 persist_path: Optional[str | Path] = None,
                 log_path: Optional[str | Path] = None):
        self.stream = GameEventStream(persist_path=log_path)
        self.store = store or MetricStore()
        self._rich: Optional[RichAggregatedData] = None

    # -- ingestion ------------------------------------------------------- #
    def ingest(self, event: dict) -> bool:
        return self.stream.ingest(event)

    def ingest_batch(self, events) -> int:
        return self.stream.ingest_batch(events)

    # -- fact generation ------------------------------------------------- #
    def update(self) -> List[MonetizationFact]:
        """Re-aggregate the current stream and refresh the store."""
        self._rich = segment_aggregate(self.stream.events())
        daily, seg = build_reality_facts(self._rich)
        self.store.put(daily)
        self.store.put(seg)
        return daily + seg

    # -- read ------------------------------------------------------------ #
    def get_facts(self) -> List[MonetizationFact]:
        return self.store.all()

    def daily_facts(self) -> List[MonetizationFact]:
        """Base-grain facts (traffic_source / user_cohort == 'unknown')."""
        return [f for f in self.store.all()
                if (f.traffic_source in (None, "unknown")
                    and f.user_cohort in (None, "unknown"))]

    def segment_facts(self) -> List[MonetizationFact]:
        """Fine-grain facts carrying a real traffic_source / user_cohort."""
        return [f for f in self.store.all()
                if f.traffic_source not in (None, "unknown")
                or f.user_cohort not in (None, "unknown")]

    # -- E13.3.2 seam ---------------------------------------------------- #
    def detect(self):
        """Run the E13.2.8 Opportunity Detector on base-grain facts.
        Returns a list of Opportunity objects (detection-only)."""
        from optimization.opportunity_detector import detect_opportunities
        return detect_opportunities(self.daily_facts())

    # -- persistence ----------------------------------------------------- #
    def save(self, path: str | Path) -> None:
        self.store.save(path)

    def load(self, path: str | Path) -> int:
        return self.store.load(path)

    def flush_log(self, path: str | Path) -> None:
        self.stream.flush_log(path)
