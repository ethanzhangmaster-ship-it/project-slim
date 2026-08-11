"""
E14.3.3 / E14.3.5 — Executor Provider Resolver (migration bridge)
===============================================================

Minimal, non-destructive re-pointing of the Controlled Execution Layer from the
E13.3.3 MOCK provider dict to the E14.3.1 FROZEN provider contract
(ProviderRegistry + game-scoped SandboxManager + MAX / RemoteConfig adapters).

Design (per the migration spec — REPLACE THE RESOLVER, DO NOT REWRITE THE
EXECUTOR):

    * The orchestrator's `provider_for(change)` is the ONLY seam that changes.
      It now delegates to a pluggable `ProviderResolver`.

    * `LegacyProviderResolver`  (DEFAULT) wraps the original E13.3.3 provider
      dict verbatim. The Executor, its rollback loop, and the Approval Gate keep
      their byte-for-byte behaviour — E13.3.3 stays fully green.

    * `ContractProviderResolver`  holds a `ProviderRegistry` + `game_id` +
      `SandboxMode` and returns the game-isolated, contract-adapter provider
      wrapped in a `_LegacyProviderShim`. The shim exposes the OLD
      apply/rollback/status dict surface the orchestrator already expects, so
      the executor code (rollback, gate, real_api_called=false checks) is
      untouched.

    * `_LegacyProviderShim` converts between the frozen `providers.Change` /
      `ProviderResult` contract and the legacy `executor.Change` / dict surface,
      and forwards the test hooks `set_fail_next` / `_fail_next` so rollback
      injection keeps working.

No contract in monetization/providers is modified. The frozen `CredentialRef`
is never touched — credential isolation (E14.3.5) flows in via the registry.
Pure-Python, stdlib only.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from monetization.executor.models import Change as LegacyChange
from monetization.executor.providers import (
    LevelPlayProvider, MaxProvider, RemoteConfigProvider,
)
from monetization.providers.base import MonetizationProvider
from monetization.providers.models import (
    Change as ContractChange, ProviderResult, SandboxMode,
)
from monetization.providers.registry import ProviderRegistry


class ProviderResolver(ABC):
    """The single seam the Executor calls to obtain a provider for a Change.

    A resolver returns a *legacy-compatible* provider object — i.e. one that
    answers `apply(legacy_change)`, `rollback(legacy_change)`, `status()`,
    `set_fail_next(bool)` and exposes `_fail_next`. The orchestrator code never
    knows whether it is talking to a E13.3.3 Mock or a E14.3.1 contract adapter.
    """

    @abstractmethod
    def provider_for(self, change: LegacyChange, game_id: str = "",
                     sandbox: Optional[SandboxMode] = None) -> Any:
        """Return a legacy-compatible provider for `change`."""
        ...


# --------------------------------------------------------------------------- #
# Legacy resolver (default — zero regression against E13.3.3)
# --------------------------------------------------------------------------- #
class LegacyProviderResolver(ProviderResolver):
    """Wraps the E13.3.3 provider dict verbatim.

    Behaviour is identical to the original
    `ExecutionOrchestrator.providers[change.provider]` lookup, so every existing
    E13.3.3 acceptance case (including the Case-3 rollback injection on
    `providers['RemoteConfig'].set_fail_next(True)`) keeps working unchanged.
    """

    def __init__(self, providers: Optional[Dict[str, Any]] = None):
        self.providers = providers or {
            "MAX": MaxProvider(),
            "LevelPlay": LevelPlayProvider(),
            "RemoteConfig": RemoteConfigProvider(),
        }

    def provider_for(self, change: LegacyChange, game_id: str = "",
                     sandbox: Optional[SandboxMode] = None) -> Any:
        return self.providers[change.provider]


# --------------------------------------------------------------------------- #
# Contract resolver (E14.3.1 frozen contract, game-isolated, E14.3.5 creds)
# --------------------------------------------------------------------------- #
class ContractProviderResolver(ProviderResolver):
    """Routes a legacy Change through the frozen ProviderRegistry and returns a
    `_LegacyProviderShim` around the game-scoped, contract-adapter instance.

    The registry enforces capability routing, per-(game, kind) instance
    isolation, and (when a CredentialResolver is wired in) credential injection
    isolation — all invisible to the Executor.
    """

    def __init__(self, registry: ProviderRegistry,
                 sandbox: SandboxMode = SandboxMode.SIMULATION):
        self.registry = registry
        self.sandbox = sandbox

    def provider_for(self, change: LegacyChange, game_id: str = "",
                     sandbox: Optional[SandboxMode] = None) -> "_LegacyProviderShim":
        sb = sandbox or self.sandbox
        # Bridge legacy -> contract Change (game-scoped, sandbox-tagged). The
        # registry fills `provider` via capability routing and stamps the
        # per-game CredentialRef onto the returned instance.
        contract_change = ContractChange.from_legacy_dict(
            change.to_dict(), game_id=game_id)
        contract_change.sandbox = sb
        prov = self.registry.provider_for(game_id, contract_change, sb)
        return _LegacyProviderShim(prov, game_id=game_id, sandbox=sb)


# --------------------------------------------------------------------------- #
# Shim: contract provider exposed through the legacy dict surface
# --------------------------------------------------------------------------- #
def _result_to_legacy(pr: ProviderResult) -> dict:
    """Render a frozen ProviderResult into the legacy apply/rollback dict the
    orchestrator already understands.

    The orchestrator detects failure via `status == 'simulated_failed'`, so we
    map `success=False -> 'simulated_failed'` and `success=True ->
    'simulated_success'`. The mandatory `real_api_called` key is preserved.
    """
    d = pr.to_dict()
    if d.get("success"):
        d["status"] = "simulated_success"
    else:
        d["status"] = "simulated_failed"
    d.setdefault("provider", "")
    d.setdefault("real_api_called", False)
    return d


class _LegacyProviderShim:
    """Wraps a frozen-contract `MonetizationProvider` so the Executor's existing
    code (apply / rollback / status, `status` / `real_api_called` checks, and
    fault injection via `set_fail_next` / `_fail_next`) works unchanged.

    The shim is intentionally thin: it converts the Change in/out and forwards
    everything else (set_fail_next, _fail_next, name, applied_count, ...) to the
    underlying contract provider via `__getattr__`.
    """

    def __init__(self, provider: MonetizationProvider,
                 game_id: str = "", sandbox: Optional[SandboxMode] = None):
        self._prov = provider
        self.name = provider.name
        self.game_id = game_id
        self.sandbox = sandbox or SandboxMode.SIMULATION

    # ---- change bridge -------------------------------------------------- #
    def _to_contract(self, legacy_change: LegacyChange) -> ContractChange:
        c = ContractChange.from_legacy_dict(legacy_change.to_dict(),
                                            game_id=self.game_id)
        c.sandbox = self.sandbox
        c.provider = self._prov.name
        return c

    # ---- legacy surface (what the orchestrator calls) ------------------- #
    def apply(self, legacy_change: LegacyChange) -> dict:
        pr = self._prov.apply_change(self._to_contract(legacy_change))
        return _result_to_legacy(pr)

    def rollback(self, legacy_change: LegacyChange) -> dict:
        pr = self._prov.rollback_change(self._to_contract(legacy_change))
        return _result_to_legacy(pr)

    def status(self) -> dict:
        return self._prov.health_check().to_dict()

    # ---- forward the rest (set_fail_next / _fail_next / name / ...) ---- #
    def __getattr__(self, name: str):
        # Only reached for names NOT defined on the shim (apply/rollback/status/
        # name/_prov/game_id/sandbox). Fault hooks land here and operate on the
        # real contract provider so rollback injection stays faithful.
        return getattr(self._prov, name)


__all__ = [
    "ProviderResolver", "LegacyProviderResolver", "ContractProviderResolver",
    "_LegacyProviderShim",
]
