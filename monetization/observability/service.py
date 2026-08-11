"""
E14.5 — Observability Service (single daily-collection entry point)
===================================================================

Ties the five E14.5 modules into ONE call a scheduler/worker makes each day:

    service.run_daily_cycle(make_opps, day)  ->
        tick every game  (drives the real runtime loop)
        collect DecisionTraces
        aggregate FleetHealth
        evaluate Alerts
        generate DailyReport
        export JSONL metrics
        flush traces + alerts to disk

The service is the *observer*: it drives ticks (so it can capture cycles for
explainability) but never changes any reliability logic in the supervisor.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from monetization.agent.models import Opportunity
from monetization.observability.alerts import AlertEngine
from monetization.observability.explain import DecisionExplainabilityLog
from monetization.observability.export import JsonlMetricsExporter
from monetization.observability.health import SystemHealthAggregator
from monetization.observability.models import (
    DailyReport, DecisionTrace, FleetHealthReport,
)
from monetization.observability.report import DailyReportGenerator


class ObservabilityService:
    """Owns the daily observability collection for one fleet supervisor."""

    def __init__(self, supervisor,
                 root_dir: str = "observability",
                 provider_health_sources=None):
        self.sup = supervisor
        self.health = SystemHealthAggregator(supervisor, provider_health_sources)
        self.explain = DecisionExplainabilityLog(f"{root_dir}/decision_traces")
        self.alerts = AlertEngine(f"{root_dir}/alerts")
        self.report = DailyReportGenerator()
        self.exporter = JsonlMetricsExporter(f"{root_dir}/metrics")
        self.all_traces: List[DecisionTrace] = []
        self.daily_reports: List[DailyReport] = []

    # ------------------------------------------------------------------ #
    def run_daily_cycle(self,
                        make_opps: Callable[[str, int], List[Opportunity]],
                        day: int,
                        day_tag: str = "",
                        extra_signals: Optional[Dict[str, Dict[str, float]]] = None
                        ) -> dict:
        tag = day_tag or f"d{day}"

        # 1. drive the real runtime loop, capture cycles for explainability
        traces: List[DecisionTrace] = []
        for slug, rt in sorted(self.sup.runtimes.items()):
            cycle = self.sup.tick_one(slug, make_opps(slug, day), day=day)
            if cycle is not None:
                traces.extend(self.explain.record_cycle(slug, cycle.actions))

        # 2. aggregate fleet health
        fleet: FleetHealthReport = self.health.snapshot()

        # 3. external signals (e.g. revenue_drop from Reality Engine)
        for gid, sigs in (extra_signals or {}).items():
            for k, v in sigs.items():
                self.alerts.record_signal(gid, k, v)

        # 4. alerts
        alert_objs = self.alerts.evaluate(fleet)

        # 5. daily report
        report = self.report.generate(fleet, traces, alert_objs)

        # 6. export metrics (JSONL)
        dec_events = [t.to_dict() for t in traces]
        alert_dicts = [a.to_dict() for a in alert_objs]
        metrics_path = self.exporter.export(fleet, dec_events, alert_dicts, tag)

        # 7. flush durable logs
        self.explain.flush(tag)
        self.alerts.flush(tag)

        self.all_traces.extend(traces)
        self.daily_reports.append(report)
        return {
            "day": day,
            "tag": tag,
            "fleet": fleet,
            "traces": traces,
            "alerts": alert_objs,
            "report": report,
            "metrics_path": metrics_path,
        }


__all__ = ["ObservabilityService"]
