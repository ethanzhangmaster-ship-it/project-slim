"""
E14.3.5 — Multi-game Credential Isolation
=========================================

The last safety brick before a real production loop. Ten to fifty games each
own their OWN secrets; a token leak or a mis-typed reference in game_A must NEVER
be able to reach game_B's credentials. This module is the *only* code allowed to
turn a `(game_id, provider)` pair into concrete credential material, and it does
so under three hard guarantees:

    1. PATH ISOLATION      — resolution is confined to  <root>/<game_id>/ .
                             `game_id` / `requested_ref` are sanitised; any
                             separator / '..' / absolute path is refused. A
                             realpath containment check is the backstop.

    2. INJECTION ISOLATION — each resolved credential carries a `credential_hash`
                             (sha256 of its payload). game_A's MAX hash and
                             game_B's MAX hash are different objects with
                             different hashes — provider instances cannot share.

    3. NO CROSS-GAME FALLBACK — game_A asking for `requested_ref="game_b/max"`
                             raises `CredentialAccessDenied`. There is no
                             silent fallback to a shared / default credential.

Layout on disk (Lean: plain JSON, no secret store dependency):

    credentials/
    ├── game_a/
    │   ├── max.json            {"app_id": "...", "sdk_key": "...", ...}
    │   ├── remote_config.json  {"project_id": "...", "api_key": "..."}
    │   └── metadata.json       {"slug": "game_a", "bundle_id": "..."}
    └── game_b/
        ├── max.json
        └── remote_config.json

`ResolvedCredential.masked()` is the only representation meant for logs — the
raw secret never leaves this module except through the explicit `.payload`.

Pure-Python, stdlib only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class CredentialError(Exception):
    """Base for all credential resolution failures."""


class CredentialAccessDenied(CredentialError):
    """Raised on any attempt to reach outside a game's own namespace."""


class CredentialNotFound(CredentialError):
    """Raised when a game/provider has no credential file (no fallback)."""


# --------------------------------------------------------------------------- #
# Provider kind -> credential filename
# --------------------------------------------------------------------------- #
_PROVIDER_FILE: Dict[str, str] = {
    "MAX": "max.json",
    "LevelPlay": "levelplay.json",
    "RemoteConfig": "remote_config.json",
    "GameFactoryConfig": "gamefactory_config.json",
}


def _file_for(provider: str) -> str:
    return _PROVIDER_FILE.get(provider, f"{provider.lower()}.json")


def _is_unsafe_segment(seg: str) -> bool:
    """A path segment is unsafe if it is empty, contains a separator, is a
    parent ref, or looks absolute (drive letter / leading slash)."""
    if not seg or seg in (".", ".."):
        return True
    if "/" in seg or "\\" in seg or "\x00" in seg:
        return True
    if ".." in seg:
        return True
    if Path(seg).is_absolute():
        return True
    # windows drive-letter guard (e.g. "C:")
    if len(seg) >= 2 and seg[1] == ":":
        return True
    return False


# --------------------------------------------------------------------------- #
# Resolved credential
# --------------------------------------------------------------------------- #
@dataclass
class ResolvedCredential:
    """A game+provider credential, loaded and fingerprinted.

    `payload` holds the loaded JSON (app_id / sdk_key / project_id / ...).
    `credential_hash` is a stable sha256 fingerprint used to PROVE injection
    isolation (two games -> two different hashes) without comparing secrets.
    """
    game_id: str
    provider: str
    key_ref: str                       # e.g. "credentials/game_a/max.json"
    payload: Dict[str, object] = field(default_factory=dict)
    credential_hash: str = ""

    # keys we never echo back in masked form
    _SECRET_HINTS = ("key", "secret", "token", "password")

    def masked(self) -> dict:
        """Log-safe view: secret-looking values are redacted, others kept."""
        out = {}
        for k, v in self.payload.items():
            if any(h in k.lower() for h in self._SECRET_HINTS) and isinstance(v, str):
                out[k] = (v[:3] + "***") if len(v) > 3 else "***"
            else:
                out[k] = v
        return {
            "game_id": self.game_id,
            "provider": self.provider,
            "key_ref": self.key_ref,
            "credential_hash": self.credential_hash,
            "payload_masked": out,
        }

    def to_dict(self) -> dict:
        return self.masked()


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Resolver
# --------------------------------------------------------------------------- #
class CredentialResolver:
    """Loads per-game credentials from `<root>/<game_id>/<provider>.json`.

    The resolver is the single choke-point for credential access. Every path is
    built from a sanitised `game_id` and confined (realpath) to the game's own
    directory, so there is no code path that reads another game's files.
    """

    def __init__(self, root: str):
        self.root = Path(root)

    # ------------------------------------------------------------------ #
    def _safe_game_dir(self, game_id: str) -> Path:
        """Return the confined directory for a game, or raise if the id is
        unsafe / would escape the credentials root."""
        if _is_unsafe_segment(game_id):
            raise CredentialAccessDenied(
                f"unsafe game_id: {game_id!r}")
        root = self.root.resolve()
        d = (root / game_id).resolve()
        # containment backstop: resolved dir must live directly under root
        if d.parent != root:
            raise CredentialAccessDenied(
                f"path escape blocked for game_id={game_id!r} -> {d}")
        return d

    def _check_requested_ref(self, game_id: str, requested_ref: str) -> None:
        """A caller may pass an explicit `requested_ref` such as 'game_b/max'.
        It MUST resolve to the caller's own game. Anything else is denied with
        NO fallback (core E14.3.5 guarantee #3)."""
        ref = requested_ref.replace("\\", "/").strip("/")
        parts = [p for p in ref.split("/") if p]
        if not parts:
            raise CredentialAccessDenied(f"empty credential_ref: {requested_ref!r}")
        ref_game = parts[0]
        if ref_game != game_id:
            raise CredentialAccessDenied(
                f"cross-game credential access denied: game {game_id!r} "
                f"requested {requested_ref!r} (points at {ref_game!r}); no fallback")
        for seg in parts:
            if _is_unsafe_segment(seg):
                raise CredentialAccessDenied(
                    f"unsafe segment in credential_ref: {requested_ref!r}")

    # ------------------------------------------------------------------ #
    def resolve(self, game_id: str, provider: str,
                requested_ref: Optional[str] = None) -> ResolvedCredential:
        """Load and fingerprint one game's provider credential.

        Raises:
            CredentialAccessDenied — cross-game / traversal attempt.
            CredentialNotFound     — no credential file for this game+provider.
        """
        if requested_ref is not None:
            self._check_requested_ref(game_id, requested_ref)

        game_dir = self._safe_game_dir(game_id)
        fname = _file_for(provider)
        # sanitise the filename segment too (provider is trusted, but be strict)
        if _is_unsafe_segment(fname):
            raise CredentialAccessDenied(f"unsafe provider file: {fname!r}")

        path = (game_dir / fname).resolve()
        if path.parent != game_dir:
            raise CredentialAccessDenied(f"path escape blocked: {path}")
        if not path.is_file():
            raise CredentialNotFound(
                f"no {provider} credential for game {game_id!r} at {path}")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # malformed json is a hard failure, never silent
            raise CredentialError(
                f"malformed credential {path}: {e}") from e
        if not isinstance(payload, dict):
            raise CredentialError(f"credential {path} must be a JSON object")

        key_ref = str(path.relative_to(self.root.resolve()).as_posix())
        return ResolvedCredential(
            game_id=game_id, provider=provider,
            key_ref=f"{self.root.name}/{key_ref}" if self.root.name else key_ref,
            payload=payload, credential_hash=_hash_payload(payload))

    # ------------------------------------------------------------------ #
    def has(self, game_id: str, provider: str) -> bool:
        try:
            game_dir = self._safe_game_dir(game_id)
        except CredentialAccessDenied:
            return False
        return (game_dir / _file_for(provider)).is_file()

    def load_metadata(self, game_id: str) -> dict:
        game_dir = self._safe_game_dir(game_id)
        p = game_dir / "metadata.json"
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def list_games(self) -> List[str]:
        if not self.root.is_dir():
            return []
        return sorted(d.name for d in self.root.iterdir() if d.is_dir())

    def context(self, game_id: str) -> "CredentialContext":
        """A game-scoped view. The context CANNOT reach any other game."""
        # validate the id up-front so an unsafe context fails fast
        self._safe_game_dir(game_id)
        return CredentialContext(game_id=game_id, resolver=self)


# --------------------------------------------------------------------------- #
# Per-game context (attached to a GameRuntime in E14.2)
# --------------------------------------------------------------------------- #
@dataclass
class CredentialContext:
    """A credential view bound to ONE game. Passed into a GameRuntime so that,
    when the supervisor starts 50 games, each runtime carries agent + providers
    + credentials that are all naturally isolated.

    The context is deliberately thin: it forwards to the resolver but pins
    `game_id`, so there is no method that can read another tenant's secrets.
    """
    game_id: str
    resolver: CredentialResolver

    def get(self, provider: str) -> ResolvedCredential:
        return self.resolver.resolve(self.game_id, provider)

    def has(self, provider: str) -> bool:
        return self.resolver.has(self.game_id, provider)

    def metadata(self) -> dict:
        return self.resolver.load_metadata(self.game_id)

    def hash_for(self, provider: str) -> str:
        return self.get(provider).credential_hash


__all__ = [
    "CredentialResolver", "ResolvedCredential", "CredentialContext",
    "CredentialError", "CredentialAccessDenied", "CredentialNotFound",
]
