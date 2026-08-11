"""Heartbeat - 工作者心跳监控"""
import asyncio
import time
from typing import Dict, Any
from dataclasses import dataclass, field


@dataclass
class HeartbeatRecord:
    worker_name: str = ""
    last_heartbeat: float = 0.0
    status: str = "active"
    latency: float = 0.0


class HeartbeatMonitor:
    """心跳监控器"""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._records: Dict[str, HeartbeatRecord] = {}
        self._lock = asyncio.Lock()

    async def beat(self, worker_name: str):
        async with self._lock:
            record = self._records.get(worker_name, HeartbeatRecord(worker_name=worker_name))
            record.last_heartbeat = time.time()
            record.status = "active"
            self._records[worker_name] = record

    async def check_status(self) -> Dict[str, Any]:
        async with self._lock:
            results = {}
            now = time.time()
            for name, record in self._records.items():
                if now - record.last_heartbeat > self.timeout:
                    record.status = "dead"
                results[name] = {
                    "status": record.status,
                    "last_heartbeat": record.last_heartbeat,
                    "latency": now - record.last_heartbeat,
                }
            return results

    async def get_dead_workers(self) -> list:
        status = await self.check_status()
        return [name for name, info in status.items() if info["status"] == "dead"]

    async def clear_dead(self):
        async with self._lock:
            now = time.time()
            dead = [name for name, record in self._records.items()
                    if now - record.last_heartbeat > self.timeout]
            for name in dead:
                del self._records[name]
