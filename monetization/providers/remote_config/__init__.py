"""
E14.3.3 — Remote Config Adapter (frozen contract implementation)
================================================================

Public surface of the Remote Config adapter — the *experience side* of LTV
(ad frequency / reward cooldown / reward multiplier / interstitial interval).
The Executor / Runtime Supervisor import only from here:

    RemoteConfigProvider   — the contract surface (apply/rollback/health)
    RemoteConfigOperation  — config-shaped operation (mapper output)
    ConfigHealth           — health signal
    ConfigGameState        — simulated Remote Config backend (per game)
    ConfigMappingError / ConfigValidationError
    RemoteConfigClient / MockConfigClient / LocalConfigClient /
    FirebaseRemoteConfigClient
    map_change_to_config_op, resolve_key, CONFIG_GENE_MAP,
    validate_config_op, SAFE_BOUNDS, build_health
"""
from monetization.providers.remote_config.config_models import (
    ConfigGameState, ConfigHealth, ConfigMappingError, ConfigOperationType,
    ConfigValidationError, RemoteConfigOperation,
)
from monetization.providers.remote_config.config_client import (
    FirebaseRemoteConfigClient, LocalConfigClient, MockConfigClient,
    RemoteConfigClient,
)
from monetization.providers.remote_config.config_mapper import (
    CONFIG_GENE_MAP, category_for, map_change_to_config_op, resolve_key,
)
from monetization.providers.remote_config.config_validator import (
    SAFE_BOUNDS, is_valid, validate_config_op,
)
from monetization.providers.remote_config.config_health import build_health
from monetization.providers.remote_config.remote_config_provider import (
    RemoteConfigProvider,
)

__all__ = [
    "RemoteConfigProvider", "RemoteConfigOperation", "ConfigOperationType",
    "ConfigHealth", "ConfigGameState", "ConfigMappingError",
    "ConfigValidationError",
    "RemoteConfigClient", "MockConfigClient", "LocalConfigClient",
    "FirebaseRemoteConfigClient",
    "map_change_to_config_op", "resolve_key", "category_for", "CONFIG_GENE_MAP",
    "validate_config_op", "is_valid", "SAFE_BOUNDS", "build_health",
]
