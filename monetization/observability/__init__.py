"""
E14.5 — Lean Observability Layer
=================================

Lets a human operator supervise a fleet of AI-run games:
  * know each game's health (SystemHealthAggregator)
  * understand WHY a decision was made (DecisionExplainabilityLog)
  * get alerted when something breaks (AlertEngine)
  * read one daily brief (DailyReportGenerator)
  * export metrics as JSONL for any backend (MetricsExporter)

No UI, no DB, no web server — pure Python, file-backed, swappable.
"""
from monetization.observability.models import (
    DailyReport, DecisionTrace, FleetHealthReport, HealthSnapshot,
    MetricsBundle, SubReport,
)
from monetization.observability.health import SystemHealthAggregator
from monetization.observability.explain import DecisionExplainabilityLog
from monetization.observability.alerts import AlertEngine
from monetization.observability.report import DailyReportGenerator
from monetization.observability.export import (
    JsonlMetricsExporter, MetricsExporter,
)
from monetization.observability.service import ObservabilityService

__all__ = [
    "SystemHealthAggregator", "DecisionExplainabilityLog", "AlertEngine",
    "DailyReportGenerator", "MetricsExporter", "JsonlMetricsExporter",
    "ObservabilityService",
    "HealthSnapshot", "FleetHealthReport", "DecisionTrace",
    "DailyReport", "SubReport", "MetricsBundle",
]
