"""
E14.3.3 — Module 3: Remote Config Client (backend seam)
========================================================

The third layer of the adapter. Split from the Provider so the *real* config
backend is a single, gated, replaceable seam. Three clients:

    MockConfigClient    — in-memory simulation of the Remote Config backend.
                          Used in SIMULATION / SHADOW and all local validation.
    LocalConfigClient   — REAL, usable client: publishes to a local
                          `gamefactory_config.json` your Unity SDK reads at
                          launch. It is a genuine write, so it is only ever
                          reached when the owning provider is armed for
                          PRODUCTION (base.py `_production_locked` lifted).
    FirebaseRemoteConfigClient — the future Firebase REST seam. NOT wired here;
                          raises until armed with real credentials + PRODUCTION.

The clients track write_calls / publish_calls / real_network_calls so the
sandbox guarantees (SIMULATION write=0-real, SHADOW publish=0) are observable
in tests.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from monetization.providers.remote_config.config_models import (
    ConfigGameState, RemoteConfigOperation,
)


class RemoteConfigClient(ABC):
    @abstractmethod
    def update_config(self, op: RemoteConfigOperation) -> dict:
        ...

    @abstractmethod
    def rollback_config(self, op: RemoteConfigOperation) -> dict:
        ...

    @abstractmethod
    def get_config(self, key: str) -> Any:
        ...

    @abstractmethod
    def check_credential(self) -> bool:
        ...

    @abstractmethod
    def ping(self) -> bool:
        ...

    @abstractmethod
    def config_version(self) -> str:
        ...


class MockConfigClient(RemoteConfigClient):
    """In-memory stand-in for the Remote Config backend. Mutates ConfigGameState
    only — never publishes anything externally."""

    backend = "mock"

    def __init__(self, game_id: str, state: Optional[ConfigGameState] = None):
        self.game_id = game_id
        self.state = state or ConfigGameState(game_id=game_id)
        self._credential_valid = True
        self._api_available = True
        # observability for sandbox guarantees
        self.write_calls = 0
        self.publish_calls = 0
        self.real_network_calls = 0

    def update_config(self, op: RemoteConfigOperation) -> dict:
        self.write_calls += 1
        self.publish_calls += 1
        self.state.set(op.key, op.new_value)
        return {"ok": True, "key": op.key, "value": op.new_value,
                "version": self.state.config_version()}

    def rollback_config(self, op: RemoteConfigOperation) -> dict:
        self.write_calls += 1
        self.publish_calls += 1
        self.state.set(op.key, op.old_value)
        return {"ok": True, "key": op.key, "value": op.old_value,
                "version": self.state.config_version()}

    def get_config(self, key: str) -> Any:
        return self.state.get(key)

    def check_credential(self) -> bool:
        return self._credential_valid

    def ping(self) -> bool:
        return self._api_available

    def config_version(self) -> str:
        return self.state.config_version()

    # test/integration hooks
    def set_credential_valid(self, v: bool) -> None:
        self._credential_valid = v

    def set_api_available(self, v: bool) -> None:
        self._api_available = v


class LocalConfigClient(RemoteConfigClient):
    """REAL, usable client that publishes to a local `gamefactory_config.json`.

    This is the GameFactory Config Server path — a genuine file write your Unity
    SDK pulls at launch. It is safe (local, no ad-platform), but it IS a real
    effect, so the owning RemoteConfigProvider only reaches it when armed for
    PRODUCTION. It keeps an in-memory ConfigGameState mirror for fast reads.
    """

    backend = "local"

    def __init__(self, game_id: str, config_path: str,
                 state: Optional[ConfigGameState] = None):
        self.game_id = game_id
        self.config_path = Path(config_path)
        self.state = state or ConfigGameState(game_id=game_id)
        self.write_calls = 0
        self.publish_calls = 0
        self.real_network_calls = 0
        self._load()

    def _load(self) -> None:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.state.values = dict(data.get("values", data))
                self.state.version = int(data.get("version", self.state.version))
            except (ValueError, OSError):
                pass

    def _publish(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"game_id": self.game_id, "version": self.state.version,
                   "values": dict(self.state.values)}
        self.config_path.write_text(json.dumps(payload, indent=2),
                                    encoding="utf-8")

    def update_config(self, op: RemoteConfigOperation) -> dict:
        self.write_calls += 1
        self.state.set(op.key, op.new_value)
        self._publish()
        self.publish_calls += 1
        return {"ok": True, "key": op.key, "value": op.new_value,
                "version": self.state.config_version()}

    def rollback_config(self, op: RemoteConfigOperation) -> dict:
        self.write_calls += 1
        self.state.set(op.key, op.old_value)
        self._publish()
        self.publish_calls += 1
        return {"ok": True, "key": op.key, "value": op.old_value,
                "version": self.state.config_version()}

    def get_config(self, key: str) -> Any:
        return self.state.get(key)

    def check_credential(self) -> bool:
        # local backend: "credential" == writable target directory
        return True

    def ping(self) -> bool:
        return True

    def config_version(self) -> str:
        return self.state.config_version()


class FirebaseRemoteConfigClient(RemoteConfigClient):
    """Network seam for Firebase Remote Config REST API.

    DELIBERATELY NOT WIRED in this environment. Wiring requires the real service
    account credential + project id, and is only ever invoked when the owning
    RemoteConfigProvider is armed for PRODUCTION. Every mutating method raises
    until then, so a half-configured deployment fails loud, never silent.
    """

    backend = "firebase"
    FIREBASE_RC_BASE = "https://firebaseremoteconfig.googleapis.com/v1"

    def __init__(self, game_id: str, credential_json: str,
                 project_id: str = "", endpoint: str = FIREBASE_RC_BASE):
        self.game_id = game_id
        self.credential_json = credential_json
        self.project_id = project_id
        self.endpoint = endpoint.rstrip("/")

    def _not_wired(self) -> None:
        raise NotImplementedError(
            "FirebaseRemoteConfigClient is not wired in this environment. Arm a "
            "production client only with a real Firebase service account and a "
            "PRODUCTION sandbox."
        )

    def update_config(self, op: RemoteConfigOperation) -> dict:
        self._not_wired()

    def rollback_config(self, op: RemoteConfigOperation) -> dict:
        self._not_wired()

    def get_config(self, key: str) -> Any:
        self._not_wired()

    def check_credential(self) -> bool:
        return bool(self.credential_json)

    def ping(self) -> bool:
        return False

    def config_version(self) -> str:
        return "unknown"
