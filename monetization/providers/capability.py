"""
E14.3.1 — Module 3: Provider Capability + Routing
==================================================

Declares, per provider kind, which change_types it can serve, and routes a
Change to the correct provider kind. This is the brain that lets the Executor
stay platform-agnostic: it only knows `change_type`; the router maps it to
MAX / LevelPlay / RemoteConfig / GameFactoryConfig.

Routing decisions (per E14.3.2 / E14.3.3 spec):
  * bid_floor, waterfall_priority, revenue_read   -> AppLovin MAX  (mediation)
  * backup_network                                -> LevelPlay (ironSource)
  * reward_frequency, ad_frequency, remote_param  -> Remote Config / GameFactory

Note: waterfall / backup-network historically split MAX vs LevelPlay. We keep
MAX as the primary mediation owner and route backup_network to LevelPlay so the
two SDKs are distinguished. Remote Config owns all *game-side* knobs (frequency,
cooldowns) which must NOT touch the ad platform.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, Set

from monetization.providers.models import CHANGE_TYPES


# Provider kind labels (the four adapters of E14.3)
PROVIDER_MAX = "MAX"
PROVIDER_LEVELPLAY = "LevelPlay"
PROVIDER_REMOTE_CONFIG = "RemoteConfig"
PROVIDER_GAMEFACTORY_CONFIG = "GameFactoryConfig"
PROVIDER_KINDS = (
    PROVIDER_MAX, PROVIDER_LEVELPLAY, PROVIDER_REMOTE_CONFIG,
    PROVIDER_GAMEFACTORY_CONFIG,
)


class Capability(str, Enum):
    BID_FLOOR = "bid_floor"
    WATERFALL_PRIORITY = "waterfall_priority"
    BACKUP_NETWORK = "backup_network"
    REMOTE_PARAM = "remote_param"
    REVENUE_READ = "revenue_read"
    AD_FREQUENCY = "ad_frequency"


@dataclass
class ProviderCapabilities:
    """Declares what a provider kind can do. Used by the registry to (a) select
    the right adapter for a Change and (b) refuse unsupported change_types."""
    kind: str
    capabilities: Set[str] = field(default_factory=set)
    handles_change_types: Set[str] = field(default_factory=set)

    def supports(self, change_type: str) -> bool:
        return change_type in self.handles_change_types

    def to_dict(self) -> dict:
        d = asdict(self)
        d["capabilities"] = sorted(self.capabilities)
        d["handles_change_types"] = sorted(self.handles_change_types)
        return d


# --------------------------------------------------------------------------- #
# Capability table (single source for routing + admission control)
# --------------------------------------------------------------------------- #
CAPABILITY_TABLE: Dict[str, ProviderCapabilities] = {
    PROVIDER_MAX: ProviderCapabilities(
        kind=PROVIDER_MAX,
        capabilities={Capability.BID_FLOOR.value, Capability.WATERFALL_PRIORITY.value,
                      Capability.REVENUE_READ.value},
        handles_change_types={
            "bid_floor", "waterfall_priority", "revenue_read",
        },
    ),
    PROVIDER_LEVELPLAY: ProviderCapabilities(
        kind=PROVIDER_LEVELPLAY,
        capabilities={Capability.BACKUP_NETWORK.value},
        handles_change_types={"backup_network"},
    ),
    PROVIDER_REMOTE_CONFIG: ProviderCapabilities(
        kind=PROVIDER_REMOTE_CONFIG,
        capabilities={Capability.REMOTE_PARAM.value, Capability.AD_FREQUENCY.value},
        handles_change_types={
            "remote_param", "reward_frequency", "ad_frequency",
        },
    ),
    PROVIDER_GAMEFACTORY_CONFIG: ProviderCapabilities(
        kind=PROVIDER_GAMEFACTORY_CONFIG,
        capabilities={Capability.REMOTE_PARAM.value, Capability.AD_FREQUENCY.value},
        handles_change_types={
            "remote_param", "reward_frequency", "ad_frequency",
        },
    ),
}


# change_type -> provider kind (the router)
_ROUTING: Dict[str, str] = {
    "bid_floor": PROVIDER_MAX,
    "waterfall_priority": PROVIDER_MAX,
    "revenue_read": PROVIDER_MAX,
    "backup_network": PROVIDER_LEVELPLAY,
    "remote_param": PROVIDER_REMOTE_CONFIG,
    "reward_frequency": PROVIDER_REMOTE_CONFIG,
    "ad_frequency": PROVIDER_REMOTE_CONFIG,
}


def provider_kind_for_change_type(change_type: str) -> str:
    """Map a change_type to its owning provider kind.

    Raises ValueError for an unknown change_type so mis-routed Changes fail loud,
    never silently.
    """
    if change_type not in CHANGE_TYPES:
        raise ValueError(f"unknown change_type: {change_type!r}")
    kind = _ROUTING.get(change_type)
    if kind is None:
        raise ValueError(f"no provider route for change_type: {change_type!r}")
    return kind


def capabilities_for(kind: str) -> ProviderCapabilities:
    return CAPABILITY_TABLE[kind]


def is_supported(kind: str, change_type: str) -> bool:
    return CAPABILITY_TABLE[kind].supports(change_type)
