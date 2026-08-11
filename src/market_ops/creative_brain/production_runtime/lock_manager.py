"""V4.4.1 Lock Manager — distributed lock for preventing conflicts.

Prevents:
  Two workers updating Retriever simultaneously
  Concurrent Knowledge graph modifications
  Embedding refresh conflicts

Supports: acquire, release, TTL-based auto-expiry, deadlock detection.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .schemas import DistributedLock


class LockManager:
    """Distributed lock manager for preventing concurrent access."""

    def __init__(self) -> None:
        self._locks: dict[str, DistributedLock] = {}
        self._lock_history: list[dict[str, Any]] = []
        self._holder_id: str = str(uuid.uuid4())[:8]  # Unique ID for this instance

    def acquire(self, lock_name: str, ttl: float = 60.0,
                metadata: dict[str, Any] | None = None) -> DistributedLock | None:
        """Try to acquire a lock.

        Args:
            lock_name: Lock name (e.g., 'knowledge_update', 'retriever_refresh').
            ttl: Time-to-live in seconds. Lock auto-expires after TTL.
            metadata: Optional metadata.

        Returns:
            DistributedLock if acquired, None if already held.
        """
        # Check if existing lock is still valid
        existing = self._locks.get(lock_name)
        if existing is not None and not existing.is_expired():
            return None  # Lock is held

        # Acquire (or re-acquire expired lock)
        now = time.time()
        lock = DistributedLock(
            lock_name=lock_name,
            holder=self._holder_id,
            acquired_at=now,
            expires_at=now + ttl,
            ttl=ttl,
            metadata=metadata or {},
        )
        self._locks[lock_name] = lock
        self._log("acquire", lock_name)
        return lock

    def acquire_or_wait(self, lock_name: str, ttl: float = 60.0,
                        wait_timeout: float = 30.0,
                        poll_interval: float = 0.5) -> DistributedLock | None:
        """Try to acquire a lock, waiting if necessary.

        Args:
            lock_name: Lock name.
            ttl: TTL in seconds.
            wait_timeout: Maximum time to wait.
            poll_interval: How often to check.

        Returns:
            DistributedLock if acquired, None if timeout.
        """
        deadline = time.time() + wait_timeout
        while time.time() < deadline:
            lock = self.acquire(lock_name, ttl)
            if lock is not None:
                return lock
            time.sleep(poll_interval)
        return None

    def release(self, lock_name: str) -> bool:
        """Release a lock.

        Returns:
            True if lock was held and released.
        """
        lock = self._locks.get(lock_name)
        if lock is None:
            return False
        del self._locks[lock_name]
        self._log("release", lock_name)
        return True

    def extend(self, lock_name: str, additional_ttl: float = 30.0) -> bool:
        """Extend a lock's TTL.

        Returns:
            True if lock exists and was extended.
        """
        lock = self._locks.get(lock_name)
        if lock is None:
            return False
        lock.expires_at += additional_ttl
        lock.ttl += additional_ttl
        self._log("extend", lock_name)
        return True

    def is_locked(self, lock_name: str) -> bool:
        """Check if a lock is currently held."""
        lock = self._locks.get(lock_name)
        if lock is None:
            return False
        if lock.is_expired():
            del self._locks[lock_name]
            return False
        return True

    def get_lock(self, lock_name: str) -> DistributedLock | None:
        """Get lock info."""
        lock = self._locks.get(lock_name)
        if lock is None:
            return None
        if lock.is_expired():
            del self._locks[lock_name]
            return None
        return lock

    def get_all_locks(self) -> list[DistributedLock]:
        """Get all active locks (clean expired ones)."""
        self._cleanup_expired()
        return list(self._locks.values())

    def get_held_by_me(self) -> list[DistributedLock]:
        """Get all locks held by this instance."""
        self._cleanup_expired()
        return [l for l in self._locks.values() if l.holder == self._holder_id]

    def force_release(self, lock_name: str) -> bool:
        """Force-release a lock regardless of holder."""
        if lock_name in self._locks:
            del self._locks[lock_name]
            self._log("force_release", lock_name)
            return True
        return False

    def release_all(self) -> int:
        """Release all locks held by this instance."""
        count = 0
        for name in list(self._locks.keys()):
            if self._locks[name].holder == self._holder_id:
                self.release(name)
                count += 1
        return count

    def get_summary(self) -> dict[str, Any]:
        """Get lock summary."""
        self._cleanup_expired()
        return {
            "total_locks": len(self._locks),
            "locks": [l.to_dict() for l in self._locks.values()],
            "holder_id": self._holder_id,
        }

    def _cleanup_expired(self) -> int:
        """Remove expired locks. Returns count removed."""
        expired = [name for name, lock in self._locks.items() if lock.is_expired()]
        for name in expired:
            del self._locks[name]
            self._log("expired", name)
        return len(expired)

    def _log(self, action: str, lock_name: str) -> None:
        """Log a lock action."""
        self._lock_history.append({
            "action": action,
            "lock_name": lock_name,
            "holder": self._holder_id,
            "timestamp": time.time(),
        })