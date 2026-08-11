"""
E14.3.1 — Module 4: Provider Registry (multi-game, isolated)
============================================================

Owns provider *instances* and enforces two things the rest of the OS relies on:

  1. Platform-agnostic routing — the caller hands in a `game_id` + `Change`,
     the registry returns the correct, fully-built provider. The caller never
     names MAX / LevelPlay / RemoteConfig directly.

  2. Credential + state isolation (E14.1 / E14.3.5) — each (game_id, kind)
     pair gets its OWN provider instance carrying its OWN CredentialRef. A token
     leak or state bleed in game_A can never reach game_B.

The registry is sandbox-aware: every instance is created in the requested
SandboxMode (simulation by default), so the "no real API" guarantee travels
with the instance, not with global config.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from monetization.providers.base import MonetizationProvider, ReferenceMockProvider
from monetization.providers.capability import (
    PROVIDER_GAMEFACTORY_CONFIG, PROVIDER_LEVELPLAY, PROVIDER_MAX,
    PROVIDER_REMOTE_CONFIG, provider_kind_for_change_type,
)
from monetization.providers.credential_resolver import (
    CredentialNotFound, CredentialResolver,
)
from monetization.providers.models import (
    Change, CredentialRef, ProviderResult, SandboxMode,
)


# A factory builds a provider for a given sandbox + credential ref.
ProviderFactory = Callable[[SandboxMode, Optional[CredentialRef]], MonetizationProvider]


class ProviderRegistry:
    """Game-scoped provider registry with capability routing + isolation.

    Optionally credential-aware (E14.3.5): pass a `CredentialResolver` and every
    instance is built with its game's real CredentialRef and stamped with a
    `credential_hash`, so two games' MAX providers are provably distinct. When
    no resolver is supplied the registry behaves exactly as in E14.3.1 (mock,
    zero real credentials) — full backward compatibility.
    """

    def __init__(self, credential_resolver: Optional[CredentialResolver] = None):
        self._factories: Dict[str, ProviderFactory] = {}
        self._instances: Dict[tuple, MonetizationProvider] = {}
        self._cred_resolver = credential_resolver
        # default the four kinds to the reference mock so the OS is runnable
        # end-to-end with zero real credentials (E14.3.1).
        self.register_defaults()

    # ------------------------------------------------------------------ #
    def register(self, kind: str, factory: ProviderFactory) -> None:
        self._factories[kind] = factory

    def register_defaults(self) -> None:
        for kind in (PROVIDER_MAX, PROVIDER_LEVELPLAY,
                     PROVIDER_REMOTE_CONFIG, PROVIDER_GAMEFACTORY_CONFIG):
            self.register(kind, lambda sb, cr, _k=kind: ReferenceMockProvider(sb, cr))

    # ------------------------------------------------------------------ #
    def instance(self, game_id: str, kind: str,
                 sandbox: SandboxMode = SandboxMode.SIMULATION) -> MonetizationProvider:
        """Return (creating + caching) the isolated provider for one game+kind.

        Identity isolation: game_A's MAX instance is a DIFFERENT object from
        game_B's MAX instance, each with its own CredentialRef(game_id=...).
        """
        key = (game_id, kind)
        if key not in self._instances:
            factory = self._factories[kind]
            # E14.3.5: when a resolver is present, load the game's own credential
            # and fingerprint it; otherwise fall back to the E14.3.1 symbolic ref.
            cred_hash = ""
            resolved = None
            if self._cred_resolver is not None:
                try:
                    resolved = self._cred_resolver.resolve(game_id, kind)
                    cred = CredentialRef(game_id=game_id, provider=kind,
                                         key_ref=resolved.key_ref)
                    cred_hash = resolved.credential_hash
                except CredentialNotFound:
                    # A game may legitimately not use every provider; keep the
                    # symbolic ref so the mock stays runnable, but no hash.
                    cred = CredentialRef(game_id=game_id, provider=kind,
                                         key_ref=f"credentials/{game_id}/{kind}_key")
            else:
                cred = CredentialRef(game_id=game_id, provider=kind,
                                     key_ref=f"credentials/{game_id}/{kind}_key")
            prov = factory(sandbox, cred)
            # Stamp the kind onto the instance so ProviderResult.provider and
            # health labels are correct even for the generic reference mock.
            prov.name = kind
            # E14.3.5 injection isolation: hash + resolved credential live on the
            # instance (the frozen CredentialRef contract is left untouched).
            prov.credential_hash = cred_hash
            prov.resolved_credential = resolved
            self._instances[key] = prov
        return self._instances[key]

    def provider_for(self, game_id: str, change: Change,
                     sandbox: Optional[SandboxMode] = None) -> MonetizationProvider:
        """Route a Change to the correct provider, sandbox-aware.

        The caller never names the platform. If `change.provider` is empty we
        fill it from the capability router; otherwise we honour the explicit tag
        (useful for overrides / shadow experiments).
        """
        kind = (change.provider or
                provider_kind_for_change_type(change.change_type))
        sb = sandbox or change.sandbox
        prov = self.instance(game_id, kind, sb)
        # keep the Change self-describing
        change.provider = kind
        change.credential_ref = prov.credential_ref
        return prov

    # ------------------------------------------------------------------ #
    def all_for_game(self, game_id: str,
                     sandbox: SandboxMode = SandboxMode.SIMULATION) -> List[MonetizationProvider]:
        return [self.instance(game_id, k, sandbox) for k in self._factories]

    def health_all(self, game_id: str,
                   sandbox: SandboxMode = SandboxMode.SIMULATION) -> List[ProviderResult]:
        return [p.health_check() for p in self.all_for_game(game_id, sandbox)]

    def reset_game(self, game_id: str) -> None:
        """Drop all cached instances for a game (used by recovery / restart)."""
        self._instances = {k: v for k, v in self._instances.items()
                           if k[0] != game_id}

    # ------------------------------------------------------------------ #
    # E14.3.5 credential helpers
    # ------------------------------------------------------------------ #
    def credential_hash_for(self, game_id: str, kind: str,
                            sandbox: SandboxMode = SandboxMode.SIMULATION) -> str:
        """Return the credential fingerprint of a game+kind instance ("" if the
        registry is not credential-aware or the game has no such credential)."""
        return getattr(self.instance(game_id, kind, sandbox), "credential_hash", "")
