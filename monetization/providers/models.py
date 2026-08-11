"""
E14.3.1 — Module 2: Provider Contract Models
=============================================

The frozen data contracts for the *Real Provider Adapter Layer*. This module is
the single source of truth for:

    * Change          — the atomic, provider-tagged, reversible config mutation
    * ProviderResult  — the unified return shape every provider must emit
    * SandboxMode     — simulation | shadow | production (E14.3.4)
    * CredentialRef   — per-game, per-provider credential namespace (E14.3.5)

Design rules (non-negotiable, inherited from the E13.3.3 contract):
  * A ProviderResult ALWAYS certifies `real_api_called`. In simulation / shadow
    mode this is hard-locked to False (enforced in base.py).
  * A Change is fully reversible: it carries `old` and `new`.
  * This module has ZERO dependency on monetization.executor.* — the contract is
    the boundary. The executor is re-pointed here in E14.3.2/3.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


# --------------------------------------------------------------------------- #
# Sandbox modes (E14.3.4)
# --------------------------------------------------------------------------- #
class SandboxMode(str, Enum):
    SIMULATION = "simulation"   # no real API called (current v1 behaviour)
    SHADOW = "shadow"          # real READ, no WRITE (prediction vs reality)
    PRODUCTION = "production"   # real READ + WRITE (armed only with a real client)


# --------------------------------------------------------------------------- #
# Operation / change-type vocabulary
# --------------------------------------------------------------------------- #
CHANGE_BID_FLOOR = "bid_floor"
CHANGE_WATERFALL_PRIORITY = "waterfall_priority"
CHANGE_BACKUP_NETWORK = "backup_network"
CHANGE_REMOTE_PARAM = "remote_param"
CHANGE_REWARD_FREQUENCY = "reward_frequency"
CHANGE_AD_FREQUENCY = "ad_frequency"
CHANGE_REVENUE_READ = "revenue_read"
CHANGE_TYPES = (
    CHANGE_BID_FLOOR, CHANGE_WATERFALL_PRIORITY, CHANGE_BACKUP_NETWORK,
    CHANGE_REMOTE_PARAM, CHANGE_REWARD_FREQUENCY, CHANGE_AD_FREQUENCY,
    CHANGE_REVENUE_READ,
)


# --------------------------------------------------------------------------- #
# Per-game, per-provider credential namespace (E14.3.5)
# --------------------------------------------------------------------------- #
@dataclass
class CredentialRef:
    """Points at a game-scoped credential WITHOUT holding secret material in
    process memory. `key_ref` is a path / secret-store name such as
    `credentials/game_A/max_key`. Never serialize the secret itself here."""
    game_id: str
    provider: str
    key_ref: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Atomic config change
# --------------------------------------------------------------------------- #
@dataclass
class Change:
    """One reversible, provider-tagged config mutation. This is the unit a
    provider applies / rolls back. It is sandboxed (a Change travels with its
    intended SandboxMode) and game-scoped (via game_id / CredentialRef)."""
    target: str                 # e.g. "US_android_reward_applovin_floor"
    change_type: str            # CHANGE_BID_FLOOR / CHANGE_REWARD_FREQUENCY / ...
    old: Any = None
    new: Any = None
    provider: str = ""          # optional; registry fills it via capability routing
    game_id: str = ""           # multi-game isolation key (E14.1 / E14.3.5)
    note: str = ""
    sandbox: SandboxMode = SandboxMode.SIMULATION
    credential_ref: Optional[CredentialRef] = None
    change_id: str = field(default_factory=lambda: f"ch_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sandbox"] = self.sandbox.value
        d["credential_ref"] = self.credential_ref.to_dict() if self.credential_ref else None
        return d

    # ---- bridge to the legacy executor Change (decoupling-safe) ---------- #
    def to_legacy_dict(self) -> dict:
        """Render into the E13.3.3 executor Change shape (no import of that
        module — keeps the contract boundary clean)."""
        return {
            "target": self.target,
            "provider": self.provider or "MAX",
            "change_type": self.change_type,
            "old": self.old,
            "new": self.new,
            "note": self.note,
        }

    @classmethod
    def from_legacy_dict(cls, d: dict, game_id: str = "") -> "Change":
        sandbox = d.get("sandbox", SandboxMode.SIMULATION.value)
        return cls(
            target=d.get("target", ""),
            change_type=d.get("change_type", ""),
            old=d.get("old"),
            new=d.get("new"),
            provider=d.get("provider", ""),
            game_id=game_id,
            note=d.get("note", ""),
            sandbox=SandboxMode(sandbox),
        )


# --------------------------------------------------------------------------- #
# Unified provider result
# --------------------------------------------------------------------------- #
@dataclass
class ProviderResult:
    """Unified return shape for every provider operation, exactly matching the
    frozen contract:

        {
          "provider": "max",
          "operation": "update_bid_floor",
          "success": true,
          "latency_ms": 120,
          "real_api_called": false
        }

    Optional audit fields (`before`/`after`/`detail`/`error`/`change_id`) are
    appended but never break the 5 mandatory keys.
    """
    provider: str
    operation: str
    success: bool
    latency_ms: float
    real_api_called: bool
    change_id: str = ""
    detail: str = ""
    error: str = ""
    before: Any = None
    after: Any = None
    shadow_read_only: bool = False   # True in SHADOW mode (read, no write)
    extra: Dict[str, Any] = field(default_factory=dict)  # optional passthrough (health, etc.)

    def to_dict(self) -> dict:
        d = {
            "provider": self.provider,
            "operation": self.operation,
            "success": self.success,
            "latency_ms": round(self.latency_ms, 3),
            "real_api_called": self.real_api_called,
            "change_id": self.change_id,
            "detail": self.detail,
            "error": self.error,
            "before": self.before,
            "after": self.after,
            "shadow_read_only": self.shadow_read_only,
        }
        # Omit when empty so the 5 mandatory keys stay the frozen contract and
        # E14.3.1 round-trip tests are unaffected.
        if self.extra:
            d["extra"] = self.extra
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ProviderResult":
        return cls(
            provider=d.get("provider", ""),
            operation=d.get("operation", ""),
            success=bool(d.get("success", False)),
            latency_ms=float(d.get("latency_ms", 0.0)),
            real_api_called=bool(d.get("real_api_called", False)),
            change_id=d.get("change_id", ""),
            detail=d.get("detail", ""),
            error=d.get("error", ""),
            before=d.get("before"),
            after=d.get("after"),
            shadow_read_only=bool(d.get("shadow_read_only", False)),
            extra=d.get("extra", {}) or {},
        )
