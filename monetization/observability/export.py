"""
E14.5.5 — Metrics Export Interface (Lean)
==========================================

A tiny, pluggable export seam. The DEFAULT implementation streams everything
as JSONL (one line per signal) so it is drop-in compatible with any log
backend. Concrete exporters for CloudWatch / Datadog / Grafana Loki /
Prometheus can be added later by subclassing MetricsExporter — the callers
(the ObservabilityService / Scheduler) never change.

Design note: this is intentionally NOT a database and NOT an HTTP server.
It honours the E13/E14 Lean rule: pure-Python, file-backed, swappable.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from monetization.observability.models import FleetHealthReport


class MetricsExporter(ABC):
    """Pluggable sink for observability metrics."""

    @abstractmethod
    def export(self, health: FleetHealthReport,
               decision_events: List[dict],
               alerts: List[dict],
               day_tag: str = "") -> str:
        """Persist the day's metrics. Returns the destination path."""


class JsonlMetricsExporter(MetricsExporter):
    """Default exporter: one JSON line per metric (game/decision/alert)."""

    def __init__(self, out_dir: str = "observability/metrics"):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def export(self, health: FleetHealthReport,
               decision_events: List[dict],
               alerts: List[dict],
               day_tag: str = "") -> str:
        path = self.dir / f"{day_tag or 'metrics'}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for g in health.games:
                row = g.to_dict()
                row["metric"] = "game_health"
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            for d in decision_events:
                row = dict(d)
                row["metric"] = "decision"
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            for a in alerts:
                row = dict(a)
                row["metric"] = "alert"
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return str(path)


__all__ = ["MetricsExporter", "JsonlMetricsExporter"]
