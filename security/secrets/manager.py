"""
EP0.1.1 — SecretManager: unified secret reading layer.

All API keys, tokens, and credentials flow through this single entry point.
Hardcoded inline secrets are forbidden — use `secret_manager.get("KEY")`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class SecretManager:
    """Unified secret access — env vars + JSON credential files.

    Priority: env var > credential file > None.

    Usage::

        sm = SecretManager(credentials_dir="credentials")
        sm.get("MAX_REPORT_KEY")       # reads from env or JSON
        sm.validate()                  # checks required keys
    """

    def __init__(
        self,
        credentials_dir: str = "credentials",
        env_prefix: str = "",
        allow_env: bool = True,
    ):
        self._env_prefix = env_prefix
        self._allow_env = allow_env
        self._credentials_dir = Path(credentials_dir)
        self._file_cache: Dict[str, Any] = {}
        self._required_keys: Dict[str, str] = {}
        self._accessed_keys: set[str] = set()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_required(
        self, key: str, description: str = ""
    ) -> None:
        """Declare a key that MUST exist for the system to run."""
        self._required_keys[key] = description

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Optional[str]:
        """Resolve a secret from env or credential files.

        Order: env var > credential JSON file.
        """
        self._accessed_keys.add(key)

        env_key = f"{self._env_prefix}{key}" if self._env_prefix else key

        if self._allow_env:
            val = os.environ.get(env_key)
            if val is not None:
                return val

        val = self._load_from_files(key)
        if val is not None:
            return val

        return default

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Check all registered required keys. Returns list of missing keys."""
        missing: list[str] = []
        for key, desc in self._required_keys.items():
            val = self.get(key)
            if val is None or val == "":
                tag = f"{key} ({desc})" if desc else key
                missing.append(tag)
        return missing

    def validate_or_raise(self) -> None:
        missing = self.validate()
        if missing:
            raise MissingSecretError(
                f"Required secrets missing: {', '.join(missing)}"
            )

    def dump_masked(self) -> Dict[str, str]:
        """Return all accessed keys with masked values (for audit)."""
        result = {}
        for key in sorted(self._accessed_keys):
            val = self.get(key)
            if val is None:
                result[key] = "<MISSING>"
            elif len(val) <= 6:
                result[key] = "***"
            else:
                result[key] = val[:3] + "***" + val[-3:]
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_from_files(self, key: str) -> Optional[str]:
        """Walk credential JSON files looking for key."""
        if not self._credentials_dir.is_dir():
            return None

        for fpath in sorted(self._credentials_dir.rglob("*.json")):
            data = self._read_json_cached(fpath)
            if isinstance(data, dict):
                val = self._extract(data, key)
                if val is not None:
                    return val

        return None

    def _read_json_cached(self, path: Path) -> Any:
        fkey = str(path.resolve())
        if fkey not in self._file_cache:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    self._file_cache[fkey] = json.load(fh)
            except Exception:
                self._file_cache[fkey] = {}
        return self._file_cache[fkey]

    @staticmethod
    def _extract(data: Any, key: str) -> Optional[str]:
        """Recursively search dict for key, return first match."""
        if isinstance(data, dict):
            if key in data:
                v = data[key]
                return str(v) if not isinstance(v, str) else v
            for v in data.values():
                found = SecretManager._extract(v, key)
                if found is not None:
                    return found
        return None


class MissingSecretError(RuntimeError):
    """Raised when required secrets are missing at startup."""
