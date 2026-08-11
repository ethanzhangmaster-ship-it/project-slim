"""E15.0.8 Redis Runtime State — 短生命周期状态管理.

Redis 负责:
  - Scheduler Lock:  避免多实例并发 (SETNX + TTL)
  - Cooldown Cache:   替代 CooldownPolicy._history
  - Worker Heartbeat: 替代内存心跳
  - Runtime State:    通用键值状态

用法:
    redis = RedisStateManager(redis_url="redis://localhost:6379/0")
    redis.connect()
    acquired = redis.acquire_scheduler_lock("growth_scheduler", ttl=3600)
    redis.set_cooldown("campaign_123", "pause", ttl_days=7)
    redis.send_heartbeat("worker_01", "running")
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import redis


class RedisStateManager:
    """Redis 运行时状态管理器.

    属性:
        client:        redis.Redis 客户端
        _redis_url:    Redis 连接 URL
        _worker_id:    Worker 唯一标识
    """

    # Key prefixes
    KEY_SCHEDULER_LOCK = "growth:scheduler:lock"
    KEY_COOLDOWN = "growth:cooldown"
    KEY_WORKER_HEARTBEAT = "growth:worker:heartbeat"
    KEY_RUNTIME_STATE = "growth:runtime:state"

    def __init__(
        self,
        redis_url: str | None = None,
        worker_id: str | None = None,
    ):
        self._redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://localhost:6379/0"
        )
        self._worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self._client: redis.Redis | None = None

    # ── Properties ───────────────────────────────────────────

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    @property
    def worker_id(self) -> str:
        return self._worker_id

    # ── Connection ───────────────────────────────────────────

    def connect(self) -> None:
        """建立 Redis 连接."""
        self._client = redis.Redis.from_url(
            self._redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )
        self._client.ping()

    def close(self) -> None:
        """关闭连接."""
        if self._client:
            self._client.close()
            self._client = None

    def health_check(self) -> dict[str, Any]:
        """Redis 健康检查."""
        if not self.is_connected:
            return {"status": "disconnected", "latency_ms": 0}

        try:
            start = time.monotonic()
            self._client.ping()
            latency = (time.monotonic() - start) * 1000
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "redis_version": self._client.info().get("redis_version", ""),
            }
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "error": str(e)}

    # ═══════════════════════════════════════════════════════════
    # Scheduler Lock
    # ═══════════════════════════════════════════════════════════

    def acquire_scheduler_lock(
        self,
        scheduler_name: str = "default",
        ttl: int = 3600,
    ) -> bool:
        """获取调度器锁 (SETNX).

        避免多实例同时执行调度周期.

        Args:
            scheduler_name: 调度器名称
            ttl:            锁超时时间 (秒)

        Returns:
            True 如果获取成功
        """
        lock_key = f"{self.KEY_SCHEDULER_LOCK}:{scheduler_name}"
        acquired = self.client.set(
            lock_key,
            self._worker_id,
            nx=True,
            ex=ttl,
        )
        return bool(acquired)

    def release_scheduler_lock(self, scheduler_name: str = "default") -> bool:
        """释放调度器锁."""
        lock_key = f"{self.KEY_SCHEDULER_LOCK}:{scheduler_name}"
        # 仅释放自己的锁
        script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        result = self.client.eval(script, 1, lock_key, self._worker_id)
        return bool(result)

    def is_scheduler_locked(self, scheduler_name: str = "default") -> bool:
        """检查调度器锁是否被持有."""
        lock_key = f"{self.KEY_SCHEDULER_LOCK}:{scheduler_name}"
        return self.client.exists(lock_key) > 0

    def get_lock_holder(self, scheduler_name: str = "default") -> str | None:
        """获取锁持有者."""
        lock_key = f"{self.KEY_SCHEDULER_LOCK}:{scheduler_name}"
        return self.client.get(lock_key)

    def extend_scheduler_lock(
        self, scheduler_name: str = "default", ttl: int = 3600,
    ) -> bool:
        """延长锁的 TTL."""
        lock_key = f"{self.KEY_SCHEDULER_LOCK}:{scheduler_name}"
        holder = self.client.get(lock_key)
        if holder == self._worker_id:
            self.client.expire(lock_key, ttl)
            return True
        return False

    # ═══════════════════════════════════════════════════════════
    # Cooldown Cache
    # ═══════════════════════════════════════════════════════════

    def set_cooldown(
        self,
        campaign_id: str,
        action: str,
        ttl_days: int = 7,
    ) -> None:
        """设置冷却时间.

        Args:
            campaign_id: 广告系列 ID
            action:      操作类型
            ttl_days:    冷却天数
        """
        key = f"{self.KEY_COOLDOWN}:{campaign_id}"
        data = {
            "campaign_id": campaign_id,
            "last_action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ttl_days": ttl_days,
        }
        self.client.setex(key, ttl_days * 86400, json.dumps(data))

    def get_cooldown(self, campaign_id: str) -> dict[str, Any] | None:
        """获取冷却状态."""
        key = f"{self.KEY_COOLDOWN}:{campaign_id}"
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None

    def is_in_cooldown(self, campaign_id: str) -> bool:
        """检查是否在冷却期内."""
        return self.client.exists(f"{self.KEY_COOLDOWN}:{campaign_id}") > 0

    def reset_cooldown(self, campaign_id: str) -> bool:
        """重置冷却时间."""
        key = f"{self.KEY_COOLDOWN}:{campaign_id}"
        return bool(self.client.delete(key))

    def get_all_cooldowns(self) -> dict[str, dict[str, Any]]:
        """获取所有冷却状态."""
        result: dict[str, dict[str, Any]] = {}
        for key in self.client.scan_iter(f"{self.KEY_COOLDOWN}:*"):
            data = self.client.get(key)
            if data:
                campaign_id = key.split(":", 2)[-1]
                result[campaign_id] = json.loads(data)
        return result

    # ═══════════════════════════════════════════════════════════
    # Worker Heartbeat
    # ═══════════════════════════════════════════════════════════

    def send_heartbeat(
        self,
        status: str = "running",
        ttl: int = 120,
    ) -> None:
        """发送 Worker 心跳.

        Args:
            status: Worker 状态 (running/idle/error)
            ttl:    心跳超时 (秒)
        """
        key = f"{self.KEY_WORKER_HEARTBEAT}:{self._worker_id}"
        data = {
            "worker_id": self._worker_id,
            "status": status,
            "last_tick": datetime.now(timezone.utc).isoformat(),
        }
        self.client.setex(key, ttl, json.dumps(data))

    def get_heartbeat(self, worker_id: str | None = None) -> dict[str, Any] | None:
        """获取 Worker 心跳."""
        wid = worker_id or self._worker_id
        key = f"{self.KEY_WORKER_HEARTBEAT}:{wid}"
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None

    def is_worker_alive(self, worker_id: str | None = None) -> bool:
        """检查 Worker 是否存活."""
        wid = worker_id or self._worker_id
        return self.client.exists(f"{self.KEY_WORKER_HEARTBEAT}:{wid}") > 0

    def get_all_workers(self) -> list[dict[str, Any]]:
        """获取所有 Worker 状态."""
        workers: list[dict[str, Any]] = []
        for key in self.client.scan_iter(f"{self.KEY_WORKER_HEARTBEAT}:*"):
            data = self.client.get(key)
            if data:
                parsed = json.loads(data)
                parsed["alive"] = True
                workers.append(parsed)
        return workers

    # ═══════════════════════════════════════════════════════════
    # Generic Runtime State
    # ═══════════════════════════════════════════════════════════

    def set_state(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置通用运行时状态."""
        full_key = f"{self.KEY_RUNTIME_STATE}:{key}"
        data = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            self.client.setex(full_key, ttl, data)
        else:
            self.client.set(full_key, data)

    def get_state(self, key: str) -> Any | None:
        """获取通用运行时状态."""
        full_key = f"{self.KEY_RUNTIME_STATE}:{key}"
        data = self.client.get(full_key)
        if data:
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return data
        return None

    def delete_state(self, key: str) -> bool:
        """删除通用运行时状态."""
        full_key = f"{self.KEY_RUNTIME_STATE}:{key}"
        return bool(self.client.delete(full_key))

    def get_state_keys(self, pattern: str = "*") -> list[str]:
        """获取匹配的状态键."""
        full_pattern = f"{self.KEY_RUNTIME_STATE}:{pattern}"
        keys = []
        for key in self.client.scan_iter(full_pattern):
            keys.append(key.replace(f"{self.KEY_RUNTIME_STATE}:", ""))
        return keys

    # ═══════════════════════════════════════════════════════════
    # Stats
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> dict[str, Any]:
        """获取 Redis 状态统计."""
        if not self.is_connected:
            return {"status": "disconnected"}
        info = self.client.info()
        return {
            "status": "connected",
            "worker_id": self._worker_id,
            "redis_version": info.get("redis_version", ""),
            "used_memory_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
            "connected_clients": info.get("connected_clients", 0),
            "keys": {
                "scheduler_lock": sum(1 for _ in self.client.scan_iter(f"{self.KEY_SCHEDULER_LOCK}:*")),
                "cooldown": sum(1 for _ in self.client.scan_iter(f"{self.KEY_COOLDOWN}:*")),
                "heartbeat": sum(1 for _ in self.client.scan_iter(f"{self.KEY_WORKER_HEARTBEAT}:*")),
                "runtime_state": sum(1 for _ in self.client.scan_iter(f"{self.KEY_RUNTIME_STATE}:*")),
            },
        }

    def flush_all(self) -> None:
        """清空所有 growth 前缀的 Redis 键 (危险操作)."""
        for key in self.client.scan_iter("growth:*"):
            self.client.delete(key)

    def __repr__(self) -> str:
        return f"RedisStateManager(worker={self._worker_id}, connected={self.is_connected})"


__all__ = ["RedisStateManager"]