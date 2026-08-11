"""Phase 2.2A: Backward-compatible re-export.

The generation_dashboard has moved to market_ops.observability.dashboard.
Import from there for new code.
"""

from .observability import GenerationDashboard

__all__ = ["GenerationDashboard"]