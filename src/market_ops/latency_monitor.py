"""Phase 2.2A: Backward-compatible re-export.

The latency_monitor has moved to market_ops.observability.observers.latency_observer.
Import from there for new code.
"""

from .observability import LatencyObserver, LatencyMonitor

__all__ = ["LatencyObserver", "LatencyMonitor"]