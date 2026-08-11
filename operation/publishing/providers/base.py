"""
E15.1.1 — PublishingProvider ABC
==================================

Mirrors monetization/providers/base.py MonetizationProvider pattern.
Every store adapter (Google Play, App Store) inherits from this ABC.

Three core methods:
    apply_change(change)    → PublishingResult
    rollback_change(change) → PublishingResult
    health_check()          → PublishingResult

The _result() helper enforces the sandbox safety net:
real_api_called=True is ONLY allowed when sandbox==PRODUCTION AND the
provider is explicitly unlocked.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from monetization.providers.models import CredentialRef, SandboxMode
from operation.publishing.providers.models import (
    OP_HEALTH_CHECK, PublishingChange, PublishingResult,
)


class PublishingProvider(ABC):
    """Abstract publishing provider — one per store platform."""

    name: str = "abstract_publisher"

    def __init__(self,
                 sandbox: SandboxMode = SandboxMode.SIMULATION,
                 credential_ref: Optional[CredentialRef] = None):
        self.sandbox = sandbox
        self.credential_ref = credential_ref
        self._production_locked = True   # safety: must call unlock() to go live

    # ------------------------------------------------------------------ #
    @abstractmethod
    def apply_change(self, change: PublishingChange) -> PublishingResult:
        """Execute one publishing operation. Respects self.sandbox."""

    @abstractmethod
    def rollback_change(self, change: PublishingChange) -> PublishingResult:
        """Undo a previously applied operation."""

    @abstractmethod
    def health_check(self) -> PublishingResult:
        """Check publishing service connectivity + current status."""

    # ------------------------------------------------------------------ #
    # production gate
    # ------------------------------------------------------------------ #
    def unlock(self) -> None:
        """Allow real API calls. Call ONLY when sandbox==PRODUCTION and
        you have confirmed the provider is ready."""
        self._production_locked = False

    def lock(self) -> None:
        """Re-lock (e.g. after an incident or during maintenance)."""
        self._production_locked = True

    # ------------------------------------------------------------------ #
    # helpers (mirrors MonetizationProvider._result / _timed)
    # ------------------------------------------------------------------ #
    def _result(self, operation: str, success: bool, *,
                latency_ms: float = 0.0, real_api_called: bool = False,
                change_id: str = "", detail: str = "", error: str = "",
                before=None, after=None, **extra) -> PublishingResult:
        if real_api_called:
            if self._production_locked:
                raise RuntimeError(
                    f"{self.name}: real_api_called=True but provider is LOCKED. "
                    f"Call unlock() only in PRODUCTION sandbox.")
            if self.sandbox != SandboxMode.PRODUCTION:
                raise RuntimeError(
                    f"{self.name}: real_api_called=True but sandbox="
                    f"{self.sandbox.value} (must be 'production')")
        return PublishingResult(
            provider=self.name, operation=operation, success=success,
            latency_ms=latency_ms, real_api_called=real_api_called,
            change_id=change_id, detail=detail, error=error,
            before=before, after=after, sandbox=self.sandbox.value, extra=extra,
        )

    @staticmethod
    def _timed(fn, *args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = (time.perf_counter() - t0) * 1000.0
        return result, elapsed


__all__ = ["PublishingProvider"]
