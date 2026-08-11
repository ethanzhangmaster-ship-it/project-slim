"""E10.1 Mock Platform Adapter — Compatibility re-export.

The original MockPlatformAdapter has been moved to
adapters/mock_adapter.py (E10.2) and now implements
PlatformAdapter ABC.

This file re-exports the class so existing E10.1 imports
continue to work without modification.
"""

from market_ops.execution_runtime.adapters.mock_adapter import MockPlatformAdapter

__all__ = ["MockPlatformAdapter"]
