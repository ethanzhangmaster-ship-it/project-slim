"""
E14.3.2 — AppLovin MAX Adapter (frozen contract implementation)
==============================================================

Public surface of the MAX adapter. The Executor / Runtime Supervisor import
only from here:

    MaxProvider        — the contract surface (apply/rollback/health)
    MaxOperation       — MAX-shaped operation (mapper output)
    RevenueMetrics     — ad revenue observation
    MaxHealth          — health signal
    MaxGameState       — simulated MAX backend (per game)
    MaxMappingError    — raised on unmappable Change
    MaxClient / MockMaxClient / RealMaxClient
    map_change_to_operation, move_network, build_health, MaxRevenueReader
"""
from monetization.providers.max.max_models import (
    MaxGameState, MaxHealth, MaxMappingError, MaxOperation, MaxOperationType,
    RevenueMetrics,
)
from monetization.providers.max.max_client import (
    MaxClient, MockMaxClient, RealMaxClient,
)
from monetization.providers.max.max_mapper import (
    map_change_to_operation, move_network, parse_priority_change, parse_target,
)
from monetization.providers.max.max_revenue import MaxRevenueReader
from monetization.providers.max.max_health import build_health
from monetization.providers.max.max_provider import MaxProvider

__all__ = [
    "MaxProvider", "MaxOperation", "MaxOperationType", "RevenueMetrics",
    "MaxHealth", "MaxGameState", "MaxMappingError",
    "MaxClient", "MockMaxClient", "RealMaxClient",
    "map_change_to_operation", "move_network", "parse_priority_change",
    "parse_target", "MaxRevenueReader", "build_health",
]
