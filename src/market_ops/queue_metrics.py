"""Phase 2.2A: Backward-compatible re-export.

The queue_metrics has moved to market_ops.observability.observers.queue_observer.
Import from there for new code.
"""

from .observability import QueueObserver, QueueMetrics

__all__ = ["QueueObserver", "QueueMetrics"]