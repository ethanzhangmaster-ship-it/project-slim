"""
E14.3.3 — Module 1: Remote Config Provider (the Executor-facing surface)
========================================================================

    RemoteConfigProvider(MonetizationProvider)
        apply_change(change)   -> ProviderResult
        rollback_change(change)-> ProviderResult
        health_check()         -> ProviderResult

The Executor (and the Runtime Supervisor) know NOTHING about Firebase Remote
Config or the GameFactory Config Server: no endpoint, no service account, no
`ads.reward_frequency` literal. They hand a `Change` and get a `ProviderResult`.
The three-layer split mirrors the MAX adapter:

    Provider  (this file)        -> contract surface + sandbox + isolation
    Mapper    (config_mapper)     -> Change -> RemoteConfigOperation (gene->key)
    Validator (config_validator)  -> safe-bound guardrail (retention safety)
    Client    (config_client)     -> backend interaction (mock / local / firebase)

Sandbox behaviour (inherited from E14.3.1):
  * SIMULATION  — applies to in-memory state, real_api_called = False.
  * SHADOW      — READ current value, NO publish (publish_calls stays 0).
  * PRODUCTION  — real publish only if the provider is armed (production lock
                  lifted); otherwise refused by base.py's _result guard.

Credential isolation (E14.1 / E14.3.5): each provider owns its own client +
ConfigGameState keyed by game_id, so game_A's config can never touch game_B's.
"""
from __future__ import annotations

from typing import Optional

from monetization.providers.base import MonetizationProvider
from monetization.providers.models import Change, ProviderResult, SandboxMode
from monetization.providers.remote_config.config_client import (
    FirebaseRemoteConfigClient, LocalConfigClient, MockConfigClient,
)
from monetization.providers.remote_config.config_health import build_health
from monetization.providers.remote_config.config_mapper import (
    map_change_to_config_op,
)
from monetization.providers.remote_config.config_models import (
    ConfigMappingError, ConfigValidationError,
)
from monetization.providers.remote_config.config_validator import (
    validate_config_op,
)


class RemoteConfigProvider(MonetizationProvider):
    name = "RemoteConfig"

    def __init__(self, sandbox: SandboxMode = SandboxMode.SIMULATION,
                 credential_ref=None, client=None, game_id: Optional[str] = None,
                 initial_state=None):
        super().__init__(sandbox, credential_ref)
        self.game_id = (game_id
                        or (credential_ref.game_id if credential_ref else None)
                        or "game_unset")
        # Per-game isolated client/state — never shared across games.
        self._client = client or MockConfigClient(game_id=self.game_id,
                                                  state=initial_state)

    # ------------------------------------------------------------------ #
    # Write surface (contract)
    # ------------------------------------------------------------------ #
    def apply_change(self, change: Change) -> ProviderResult:
        d, lat = self._timed(self._apply, change)
        return self._result(
            d["operation"], d["success"], latency_ms=lat,
            real_api_called=d.get("real", False),
            change_id=change.change_id,
            detail=d.get("detail", ""), error=d.get("error", ""),
            before=d.get("before"), after=d.get("after"),
            shadow_read_only=d.get("shadow", False),
            extra=d.get("extra"),
        )

    def _apply(self, change: Change) -> dict:
        try:
            op = map_change_to_config_op(change)
        except ConfigMappingError as e:
            return {"operation": change.change_type, "success": False,
                    "error": str(e)}

        # Retention guardrail — refuse unsafe values before any write.
        try:
            validate_config_op(op)
        except ConfigValidationError as e:
            return {"operation": op.operation, "success": False,
                    "error": str(e), "before": op.old_value, "after": op.old_value}

        # SHADOW: observe the current published value, never publish.
        if self.sandbox == SandboxMode.SHADOW:
            current = self._client.get_config(op.key)
            return {"operation": op.operation, "success": True, "shadow": True,
                    "before": current, "after": current,
                    "extra": {"key": op.key, "proposed": op.new_value},
                    "detail": "shadow: read current value, no publish performed"}

        # SIMULATION / PRODUCTION publish (mock applies to in-memory state).
        real = self._real_flag()
        if real:
            self._client.real_network_calls += 1
        self._client.update_config(op)
        return {"operation": op.operation, "success": True, "real": real,
                "before": op.old_value, "after": op.new_value,
                "extra": {"key": op.key, "category": op.category,
                          "config_version": self._client.config_version()}}

    def rollback_change(self, change: Change) -> ProviderResult:
        d, lat = self._timed(self._rollback, change)
        return self._result(
            d["operation"], d["success"], latency_ms=lat,
            real_api_called=d.get("real", False),
            change_id=change.change_id,
            detail=d.get("detail", ""), error=d.get("error", ""),
            before=d.get("before"), after=d.get("after"),
            extra=d.get("extra"),
        )

    def _rollback(self, change: Change) -> dict:
        try:
            op = map_change_to_config_op(change)
        except ConfigMappingError as e:
            return {"operation": change.change_type, "success": False,
                    "error": str(e)}
        if op.old_value is None:
            return {"operation": op.operation, "success": False,
                    "error": "nothing to roll back (no old value)"}

        real = self._real_flag()
        if real:
            self._client.real_network_calls += 1
        self._client.rollback_config(op)
        return {"operation": op.operation, "success": True, "real": real,
                "before": op.new_value, "after": op.old_value,
                "extra": {"key": op.key,
                          "config_version": self._client.config_version()}}

    # ------------------------------------------------------------------ #
    # Read surface
    # ------------------------------------------------------------------ #
    def get_config(self, key: str):
        return self._client.get_config(key)

    # ------------------------------------------------------------------ #
    # Health (E14.2 Runtime Supervisor)
    # ------------------------------------------------------------------ #
    def health_check(self) -> ProviderResult:
        h, lat = self._timed(lambda: build_health(self._client).to_dict())
        return self._result(
            "health_check", h["status"] == "healthy", latency_ms=lat,
            real_api_called=False,
            extra={"status": h["status"], "backend": h["backend"],
                   "credential_valid": h["credential_valid"],
                   "api_available": h["api_available"],
                   "config_version": h["config_version"]},
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _real_flag(self) -> bool:
        """A real publish only when PRODUCTION sandbox AND unlock armed."""
        return (self.sandbox == SandboxMode.PRODUCTION) and (not self._production_locked)

    # ---- production wiring seams (guarded by base.py lock) -------------- #
    def arm_local_client(self, config_path: str) -> None:
        """Swap in the REAL local GameFactory config client (writes
        gamefactory_config.json). Still gated: base.py refuses a real call
        unless sandbox == PRODUCTION and the production lock is lifted."""
        self._client = LocalConfigClient(self.game_id, config_path,
                                         state=self._client.state)

    def arm_firebase_client(self, credential_json: str,
                            project_id: str = "") -> None:
        """Swap in the Firebase Remote Config seam. NOT wired here; requires a
        real service account and PRODUCTION sandbox to ever fire."""
        self._client = FirebaseRemoteConfigClient(self.game_id, credential_json,
                                                  project_id)
