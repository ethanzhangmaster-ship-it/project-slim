"""Observability Module for V4.5.5 Production Observability Patch.

Provides full production visibility:
- Dashboard: Daily runtime summary
- Metrics: Runtime, Creative, Performance metrics
- Cost Report: Daily cost and platform analysis
- Creative Report: Winner and DNA reports
- Anomaly: Detection and alerting
"""

from .dashboard import (
    RuntimeDashboard, DailyDashboard,
    GenerationSummary, QueueSummary, CostSummary, PlatformSummary
)

from .metrics import (
    RuntimeMetrics, RuntimeMetricsCollector,
    CreativeMetric, CreativeDailyMetrics, CreativeMetricsCollector,
    PerformanceMetric, CreativePerformance, PerformanceMetricsCollector,
)

from .cost_report import (
    DailyCostReport, DailyCostReporter,
    PlatformCost, PlatformCostAnalysis, PlatformCostAnalyzer,
)

from .creative_report import (
    WinnerEntry, WinnerReporter,
    DNAPattern, WinnerDNA, DNAExtractor,
)

from .anomaly import (
    ThresholdPolicy, ThresholdManager,
    Alert, AlertManager, AlertSeverity, AlertType,
    AnomalyDetector,
)

__all__ = [
    # Dashboard
    "RuntimeDashboard", "DailyDashboard",
    "GenerationSummary", "QueueSummary", "CostSummary", "PlatformSummary",
    # Metrics
    "RuntimeMetrics", "RuntimeMetricsCollector",
    "CreativeMetric", "CreativeDailyMetrics", "CreativeMetricsCollector",
    "PerformanceMetric", "CreativePerformance", "PerformanceMetricsCollector",
    # Cost Report
    "DailyCostReport", "DailyCostReporter",
    "PlatformCost", "PlatformCostAnalysis", "PlatformCostAnalyzer",
    # Creative Report
    "WinnerEntry", "WinnerReporter",
    "DNAPattern", "WinnerDNA", "DNAExtractor",
    # Anomaly
    "ThresholdPolicy", "ThresholdManager",
    "Alert", "AlertManager", "AlertSeverity", "AlertType",
    "AnomalyDetector",
]