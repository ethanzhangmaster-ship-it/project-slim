"""Phase 2.1: Backward-compatible re-export.

Core modules have moved to market_ops.core/.
Import from there for new code.
"""

from .core.creative_generation_manager import CreativeGenerationManager, BatchResult

__all__ = ["CreativeGenerationManager", "BatchResult"]