"""
E14.3.3 — Module 2: Remote Config Adapter Models
=================================================

Data contracts for the Remote Config adapter — the *experience side* of LTV.
Where MAX moves the money knobs (eCPM / floor / waterfall), Remote Config moves
the player-experience knobs (ad frequency / reward cooldown / reward multiplier /
interstitial interval). These parameters must NEVER touch the ad platform; they
are game-side config the Unity SDK pulls at launch.

    RemoteConfigOperation  — a concrete key/value mutation derived from a Change
    ConfigHealth           — health signal for the Runtime Supervisor
    ConfigGameState        — the simulated Remote Config backend (per game)
    ConfigMappingError     — raised when a Change cannot be mapped to a config key
    ConfigValidationError  — raised when a target value is outside a safe bound

`ConfigGameState` is what the MockConfigClient mutates, so apply/rollback behave
like a real Remote Config backend without any network call.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ConfigOperationType(str, Enum):
    UPDATE_CONFIG = "UPDATE_CONFIG"
    READ_CONFIG = "READ_CONFIG"


@dataclass
class RemoteConfigOperation:
    """A concrete Remote-Config-shaped operation derived from an internal Change.

    `key` is the canonical Remote Config key (e.g. "ads.reward_frequency"); the
    mapper resolves the OS-internal gene/target into it. `old_value` / `new_value`
    are the reversible before/after; `category` tags the knob family for the
    validator (frequency | cooldown | multiplier | interval | generic).
    """
    operation: str
    key: str
    category: str = "generic"
    old_value: Any = None
    new_value: Any = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConfigHealth:
    status: str                 # healthy | degraded | down
    backend: str                # local | firebase | mock
    credential_valid: bool
    api_available: bool
    config_version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConfigGameState:
    """Simulated Remote Config backend for ONE game (never shared).

    Holds the current key/value map plus a monotonically bumped config_version
    so the health signal and the Unity SDK can detect a new published config.
    """
    game_id: str
    values: Dict[str, Any] = field(default_factory=dict)
    version: int = 0

    def get(self, key: str) -> Any:
        return self.values.get(key)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value
        self.version += 1

    def snapshot(self) -> dict:
        return {"game_id": self.game_id, "version": self.version,
                "values": dict(self.values)}

    def config_version(self) -> str:
        return f"v{self.version}"


class ConfigMappingError(ValueError):
    """Raised when a Change cannot be mapped to a Remote Config key."""


class ConfigValidationError(ValueError):
    """Raised when a resolved config value is outside a safe operating bound."""
