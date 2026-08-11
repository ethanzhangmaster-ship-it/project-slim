"""
E14.3.1 — Real Provider Adapter Layer: FROZEN CONTRACT
=======================================================

Public surface of the provider boundary. Everything the Executor / Runtime
Supervisor is allowed to import from here:

    MonetizationProvider     — the interface every adapter implements
    ReferenceMockProvider    — reference impl locking the contract
    Change / ProviderResult  — the data contracts
    SandboxMode / CredentialRef
    ProviderRegistry         — game-scoped routing + isolation
    capability.*             — routing + admission control

Importing anything else (e.g. a real MAX client) is outside the contract.
"""
from monetization.providers.models import (
    CHANGE_TYPES, CredentialRef, Change, ProviderResult, SandboxMode,
)
from monetization.providers.base import (
    MonetizationProvider, ReferenceMockProvider,
)
from monetization.providers.capability import (
    CAPABILITY_TABLE, PROVIDER_GAMEFACTORY_CONFIG, PROVIDER_KINDS,
    PROVIDER_LEVELPLAY, PROVIDER_MAX, PROVIDER_REMOTE_CONFIG, Capability,
    ProviderCapabilities, capabilities_for, is_supported,
    provider_kind_for_change_type,
)
from monetization.providers.registry import ProviderRegistry
from monetization.providers.credential_resolver import (
    CredentialAccessDenied, CredentialContext, CredentialError,
    CredentialNotFound, CredentialResolver, ResolvedCredential,
)

__all__ = [
    # models
    "Change", "ProviderResult", "SandboxMode", "CredentialRef", "CHANGE_TYPES",
    # contract
    "MonetizationProvider", "ReferenceMockProvider",
    # capability
    "Capability", "ProviderCapabilities", "CAPABILITY_TABLE",
    "PROVIDER_MAX", "PROVIDER_LEVELPLAY", "PROVIDER_REMOTE_CONFIG",
    "PROVIDER_GAMEFACTORY_CONFIG", "PROVIDER_KINDS",
    "provider_kind_for_change_type", "capabilities_for", "is_supported",
    # registry
    "ProviderRegistry",
    # credentials (E14.3.5)
    "CredentialResolver", "ResolvedCredential", "CredentialContext",
    "CredentialError", "CredentialAccessDenied", "CredentialNotFound",
]
