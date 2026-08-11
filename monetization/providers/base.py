"""
E14.3.1 — Module 1: MonetizationProvider Contract (FROZEN)
==========================================================

The interface every ad-platform / config adapter must implement. This is the
boundary between the *Autonomous Monetization OS* and the *real world*: the
Executor (E13.3.3) and the Runtime Supervisor (E14.2) only ever call:

    provider.apply_change(change)      -> ProviderResult
    provider.rollback_change(change)   -> ProviderResult
    provider.health_check()            -> ProviderResult

They have no knowledge of AppLovin MAX, LevelPlay, Firebase Remote Config, or
the GameFactory Config Server. Swapping a Mock for a real adapter is a
constructor swap — zero change to the call sites.

Contract safety guarantees (asserted in validate_providers.py):
  * `real_api_called` is ALWAYS present on every ProviderResult.
  * In SIMULATION / SHADOW mode `real_api_called` is hard-locked False.
  * A "real" call cannot happen unless (a) the provider is armed with a real
    client AND (b) sandbox == PRODUCTION. The `_production_locked` switch
    enforces this — an adapter that forgets to arm raises immediately.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from monetization.providers.models import (
    CredentialRef, Change, ProviderResult, SandboxMode,
)


class MonetizationProvider(ABC):
    """Interface every provider adapter must implement."""

    #: provider kind label (MAX / LevelPlay / RemoteConfig / GameFactoryConfig)
    name: str = "abstract"

    def __init__(self,
                 sandbox: SandboxMode = SandboxMode.SIMULATION,
                 credential_ref: Optional[CredentialRef] = None):
        self.sandbox = sandbox
        self.credential_ref = credential_ref
        # Per-instance state (isolated per game via the registry).
        self._applied: list = []
        self._rolled_back: list = []
        # Real calls are REFUSED until a real client arms this flag. This is the
        # hard safety net: a mock can never accidentally claim a real call, and a
        # half-implemented real adapter cannot leak a call in simulation mode.
        self._production_locked = True

    # ------------------------------------------------------------------ #
    @abstractmethod
    def apply_change(self, change: Change) -> ProviderResult:
        """Apply one Change. Returns a ProviderResult (never raises on failure;
        signal failure via `success=False`)."""
        ...

    @abstractmethod
    def rollback_change(self, change: Change) -> ProviderResult:
        """Reverse one Change. Returns a ProviderResult."""
        ...

    @abstractmethod
    def health_check(self) -> ProviderResult:
        """Provider liveness / state snapshot. Returns a ProviderResult."""
        ...

    # ------------------------------------------------------------------ #
    # Contract helpers (shared by every adapter)
    # ------------------------------------------------------------------ #
    def _result(self, operation: str, success: bool, *,
                latency_ms: float = 0.0,
                real_api_called: bool = False,
                **extra: Any) -> ProviderResult:
        """Build a ProviderResult, enforcing the real-API contract.

        Raises RuntimeError if a real call is requested while production is
        locked or while not in PRODUCTION sandbox.
        """
        if real_api_called:
            if self._production_locked or self.sandbox != SandboxMode.PRODUCTION:
                raise RuntimeError(
                    "PRODUCTION lock: real API call refused "
                    f"(production_locked={self._production_locked}, "
                    f"sandbox={self.sandbox.value})"
                )
        return ProviderResult(
            provider=self.name,
            operation=operation,
            success=success,
            latency_ms=latency_ms,
            real_api_called=real_api_called,
            **extra,
        )

    def _timed(self, fn, *args, **kwargs):
        """Run fn and return (result, latency_ms)."""
        t0 = time.perf_counter()
        out = fn(*args, **kwargs)
        return out, (time.perf_counter() - t0) * 1000.0

    def applied_count(self) -> int:
        return len(self._applied)

    def rolled_back_count(self) -> int:
        return len(self._rolled_back)


# --------------------------------------------------------------------------- #
# Reference implementation — locks the contract for all future adapters
# --------------------------------------------------------------------------- #
class ReferenceMockProvider(MonetizationProvider):
    """A generic MOCK adapter that satisfies the entire frozen contract for ANY
    change_type. It never calls a real API. It records applied / rolled-back
    changes so isolation + audit properties can be validated.

    This is the reference the real adapters (E14.3.2 AppLovin MAX,
    E14.3.3 Remote Config, GameFactory Config) must mirror. It also demonstrates
    SHADOW semantics: a real READ with no WRITE.
    """

    def __init__(self, sandbox: SandboxMode = SandboxMode.SIMULATION,
                 credential_ref: Optional[CredentialRef] = None,
                 fail_next: bool = False):
        super().__init__(sandbox, credential_ref)
        self._fail_next = fail_next

    # test hook (drives the rollback path)
    def set_fail_next(self, value: bool = True) -> None:
        self._fail_next = value

    # ---- apply -------------------------------------------------------- #
    def apply_change(self, change: Change) -> ProviderResult:
        res, lat = self._timed(self._apply, change)
        return self._result(res.operation, res.success, latency_ms=lat,
                            real_api_called=res.real_api_called,
                            change_id=res.change_id, detail=res.detail,
                            error=res.error, before=res.before, after=res.after,
                            shadow_read_only=res.shadow_read_only)

    def _apply(self, change: Change) -> ProviderResult:
        if self._fail_next:
            self._fail_next = False
            return ProviderResult(
                provider=self.name, operation=change.change_type, success=False,
                latency_ms=0.0, real_api_called=False,
                change_id=change.change_id,
                error="mock injected failure (simulate_fail=True)",
                before=change.old, after=change.old)

        # SHADOW: read the current value, but do NOT write it.
        if self.sandbox == SandboxMode.SHADOW:
            return ProviderResult(
                provider=self.name, operation=change.change_type, success=True,
                latency_ms=0.0, real_api_called=False,
                change_id=change.change_id, shadow_read_only=True,
                before=change.old, after=change.old,
                detail="shadow: read current value, no write performed")

        self._applied.append(change)
        return ProviderResult(
            provider=self.name, operation=change.change_type, success=True,
            latency_ms=0.0, real_api_called=False,
            change_id=change.change_id, before=change.old, after=change.new)

    # ---- rollback ----------------------------------------------------- #
    def rollback_change(self, change: Change) -> ProviderResult:
        res, lat = self._timed(self._rollback, change)
        return self._result(res.operation, res.success, latency_ms=lat,
                            real_api_called=res.real_api_called,
                            change_id=res.change_id, detail=res.detail,
                            before=res.before, after=res.after)

    def _rollback(self, change: Change) -> ProviderResult:
        self._rolled_back.append(change)
        return ProviderResult(
            provider=self.name, operation=change.change_type, success=True,
            latency_ms=0.0, real_api_called=False,
            change_id=change.change_id, before=change.new, after=change.old)

    # ---- health ------------------------------------------------------- #
    def health_check(self) -> ProviderResult:
        res, lat = self._timed(lambda: None)
        return self._result(
            "health_check", True, latency_ms=lat,
            real_api_called=False,
            detail=f"applied={len(self._applied)} "
                   f"rolled_back={len(self._rolled_back)}")
