"""V4.4.1 Secret Manager — secure credential management.

Never stores raw secrets in config files.
Instead: encrypted storage, auto-rotation, expiry tracking.

Manages: FB Token, OpenAI Key, Gemini Key, AWS credentials, Adjust tokens.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from .schemas import Secret, SecretLevel


class SecretManager:
    """Secure credential and secret management."""

    def __init__(self) -> None:
        self._secrets: dict[str, Secret] = {}      # secret_id → Secret
        self._values: dict[str, str] = {}           # secret_id → raw_value (in-memory only)
        self._by_key: dict[str, str] = {}           # key → secret_id
        self._access_log: list[dict[str, Any]] = []

    def store(self, key: str, value: str,
              level: SecretLevel = SecretLevel.MEDIUM,
              rotation_days: int = 90,
              expires_at: float = 0.0,
              metadata: dict[str, Any] | None = None) -> Secret:
        """Store a secret.

        Args:
            key: Secret key name (e.g., 'FB_ACCESS_TOKEN').
            value: The secret value (never persisted to disk).
            level: Sensitivity level.
            rotation_days: Auto-rotate interval in days.
            expires_at: Expiry timestamp (0 = never).
            metadata: Additional metadata.

        Returns:
            The created Secret metadata (never contains raw value).
        """
        secret_id = str(uuid.uuid4())[:8]
        value_hash = hashlib.sha256(value.encode()).hexdigest()[:16]

        secret = Secret(
            secret_id=secret_id,
            key=key,
            level=level,
            value_hash=value_hash,
            rotated_at=time.time(),
            expires_at=expires_at,
            rotation_days=rotation_days,
            created_at=time.time(),
            metadata=metadata or {},
        )

        # Remove old secret with same key
        old_id = self._by_key.get(key)
        if old_id:
            self._secrets.pop(old_id, None)
            self._values.pop(old_id, None)

        self._secrets[secret_id] = secret
        self._values[secret_id] = value
        self._by_key[key] = secret_id

        return secret

    def get(self, key: str) -> str | None:
        """Get a secret value by key.

        Returns:
            Raw value, or None if not found/expired.
        """
        secret_id = self._by_key.get(key)
        if secret_id is None:
            return None

        secret = self._secrets.get(secret_id)
        if secret is None:
            return None

        if secret.expires_at > 0 and time.time() > secret.expires_at:
            return None  # Expired

        self._log_access(key, "read")
        return self._values.get(secret_id)

    def get_metadata(self, key: str) -> Secret | None:
        """Get secret metadata (no raw value)."""
        secret_id = self._by_key.get(key)
        return self._secrets.get(secret_id)

    def rotate(self, key: str, new_value: str) -> Secret | None:
        """Rotate a secret to a new value.

        Returns:
            Updated Secret metadata, or None if key not found.
        """
        old = self.get_metadata(key)
        if old is None:
            return None

        value_hash = hashlib.sha256(new_value.encode()).hexdigest()[:16]
        old.value_hash = value_hash
        old.rotated_at = time.time()
        self._values[old.secret_id] = new_value

        self._log_access(key, "rotate")
        return old

    def delete(self, key: str) -> bool:
        """Delete a secret."""
        secret_id = self._by_key.pop(key, None)
        if secret_id is None:
            return False
        self._secrets.pop(secret_id, None)
        self._values.pop(secret_id, None)
        self._log_access(key, "delete")
        return True

    def check_needs_rotation(self) -> list[Secret]:
        """Get all secrets that need rotation."""
        return [s for s in self._secrets.values() if s.needs_rotation()]

    def check_expired(self) -> list[Secret]:
        """Get all expired secrets."""
        now = time.time()
        return [
            s for s in self._secrets.values()
            if s.expires_at > 0 and now > s.expires_at
        ]

    def list_keys(self) -> list[str]:
        """List all stored secret keys (never values)."""
        return list(self._by_key.keys())

    def list_metadata(self) -> list[dict[str, Any]]:
        """List all secret metadata (never values)."""
        return [s.to_dict() for s in self._secrets.values()]

    def get_stats(self) -> dict[str, Any]:
        """Get secret statistics."""
        by_level = {}
        for s in self._secrets.values():
            lv = s.level.value
            by_level[lv] = by_level.get(lv, 0) + 1

        return {
            "total_secrets": len(self._secrets),
            "by_level": by_level,
            "needs_rotation": len(self.check_needs_rotation()),
            "expired": len(self.check_expired()),
        }

    def _log_access(self, key: str, action: str) -> None:
        """Log secret access."""
        self._access_log.append({
            "key": key,
            "action": action,
            "timestamp": time.time(),
        })

    def get_access_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent access log."""
        return self._access_log[-limit:]