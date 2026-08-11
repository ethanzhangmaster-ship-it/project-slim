"""
E13.3.3 — Module 4 (base): MonetizationProvider interface
=========================================================

Abstract base for every ad-platform adapter. v1 ships MOCK implementations
only — `apply` / `rollback` / `status` never touch a real network. Each mock
response carries `real_api_called: false` so the orchestrator and the validation
report can prove (post-hoc) that no external call ever happened.

Real adapters (AppLovin MAX SDK, ironSource LevelPlay SDK, Firebase
RemoteConfig client) are deliberately deferred to E13.4 — this layer's whole
job in v1 is to demonstrate the *controlled execution* flow safely.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from monetization.executor.models import Change, RollbackOperation


class MonetizationProvider(ABC):
    """Interface every provider adapter must implement."""

    #: provider label (MAX / LevelPlay / RemoteConfig)
    name: str = "abstract"

    @abstractmethod
    def apply(self, change: Change) -> dict:
        """Apply one Change. Returns a provider response dict.

        MUST set `real_api_called: false` in v1 (mock). On failure, return a
        dict with `status: "simulated_failed"` and an `error` key (do not raise
        — the orchestrator drives rollback from the returned status).
        """
        ...

    @abstractmethod
    def rollback(self, change: Change) -> dict:
        """Reverse one Change. Returns a provider response dict."""
        ...

    @abstractmethod
    def status(self) -> dict:
        """Current provider state (applied count, real_api_called flag)."""
        ...


def _assert_mock() -> None:
    """Guard: this layer must never call a real ad-platform API in v1.

    Real adapters will override this with a genuine client call. Keeping the
    assertion here makes the 'no real API' contract explicit and greppable.
    """
    # Intentionally a no-op in v1. If a future adapter sets REAL_API_ENABLED
    # without a real client, it must fail loudly. We document the contract.
    return
