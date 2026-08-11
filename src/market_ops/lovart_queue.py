"""Phase 2.1.1: Backward-compatible re-export.

Core modules have moved to market_ops.core/.
Import from there for new code.
"""

from .core.lovart_queue import LovartQueue

__all__ = ["LovartQueue"]