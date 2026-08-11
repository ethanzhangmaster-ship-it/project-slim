from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum


class SyncStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class SyncConfig:
    platform: str
    data_type: str
    sync_interval_seconds: int = 3600
    batch_size: int = 1000
    max_retries: int = 3
    backoff_seconds: int = 60
    enabled: bool = True


@dataclass
class SyncResult:
    sync_id: str
    platform: str
    data_type: str
    status: SyncStatus
    records_synced: int = 0
    records_failed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sync_id": self.sync_id,
            "platform": self.platform,
            "data_type": self.data_type,
            "status": self.status.value,
            "records_synced": self.records_synced,
            "records_failed": self.records_failed,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "error": self.error,
        }


class DataSync:
    def __init__(self):
        self._configs: Dict[str, SyncConfig] = {}
        self._last_sync: Dict[str, datetime] = {}
        self._sync_history: List[SyncResult] = []
        self._sync_handlers: Dict[str, Callable] = {}
        self._running_syncs: Dict[str, bool] = {}

    def add_config(self, config: SyncConfig) -> SyncConfig:
        key = f"{config.platform}_{config.data_type}"
        self._configs[key] = config
        return config

    def get_config(self, platform: str, data_type: str) -> Optional[SyncConfig]:
        return self._configs.get(f"{platform}_{data_type}")

    def register_sync_handler(self, platform: str, data_type: str, handler: Callable):
        self._sync_handlers[f"{platform}_{data_type}"] = handler

    def is_sync_due(self, platform: str, data_type: str) -> bool:
        config = self.get_config(platform, data_type)
        if not config or not config.enabled:
            return False

        last = self._last_sync.get(f"{platform}_{data_type}")
        if not last:
            return True

        delta = datetime.now() - last
        return delta.total_seconds() >= config.sync_interval_seconds

    def sync(self, platform: str, data_type: str) -> SyncResult:
        key = f"{platform}_{data_type}"
        if self._running_syncs.get(key, False):
            return SyncResult(
                sync_id=f"sync_{hash(key + str(datetime.now()))}",
                platform=platform,
                data_type=data_type,
                status=SyncStatus.PENDING,
                error="Sync already running",
            )

        config = self.get_config(platform, data_type)
        if not config:
            return SyncResult(
                sync_id=f"sync_{hash(key + str(datetime.now()))}",
                platform=platform,
                data_type=data_type,
                status=SyncStatus.FAILED,
                error="No sync config found",
            )

        self._running_syncs[key] = True
        sync_id = f"sync_{hash(key + str(datetime.now())) % 100000:05d}"
        result = SyncResult(
            sync_id=sync_id,
            platform=platform,
            data_type=data_type,
            status=SyncStatus.RUNNING,
            start_time=datetime.now(),
        )

        try:
            handler = self._sync_handlers.get(key)
            if handler:
                synced, failed = handler(config)
            else:
                synced, failed = self._mock_sync(config)

            result.records_synced = synced
            result.records_failed = failed
            result.status = SyncStatus.COMPLETED if failed == 0 else SyncStatus.PARTIAL
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.error = str(e)
        finally:
            result.end_time = datetime.now()
            self._running_syncs[key] = False
            self._last_sync[key] = datetime.now()
            self._sync_history.append(result)

        return result

    def _mock_sync(self, config: SyncConfig) -> tuple:
        return config.batch_size, 0

    def sync_all_due(self) -> List[SyncResult]:
        results = []
        for config in self._configs.values():
            if config.enabled and self.is_sync_due(config.platform, config.data_type):
                results.append(self.sync(config.platform, config.data_type))
        return results

    def get_sync_history(self, limit: int = 100) -> List[SyncResult]:
        return self._sync_history[-limit:]

    def get_sync_history_by_platform(self, platform: str, limit: int = 50) -> List[SyncResult]:
        return [s for s in self._sync_history[-limit:] if s.platform == platform]

    def get_stats(self) -> Dict[str, Any]:
        total_syncs = len(self._sync_history)
        successful = sum(1 for s in self._sync_history if s.status == SyncStatus.COMPLETED)
        failed = sum(1 for s in self._sync_history if s.status == SyncStatus.FAILED)
        total_records = sum(s.records_synced for s in self._sync_history)
        avg_duration = sum(s.duration for s in self._sync_history if s.duration) / total_syncs if total_syncs > 0 else 0

        return {
            "total_syncs": total_syncs,
            "successful_syncs": successful,
            "failed_syncs": failed,
            "partial_syncs": total_syncs - successful - failed,
            "total_records_synced": total_records,
            "avg_sync_duration": avg_duration,
            "configured_syncs": len(self._configs),
        }

    def get_latest_sync(self, platform: str, data_type: str) -> Optional[SyncResult]:
        key = f"{platform}_{data_type}"
        for sync in reversed(self._sync_history):
            if sync.platform == platform and sync.data_type == data_type:
                return sync
        return None

    def disable_sync(self, platform: str, data_type: str):
        config = self.get_config(platform, data_type)
        if config:
            config.enabled = False

    def enable_sync(self, platform: str, data_type: str):
        config = self.get_config(platform, data_type)
        if config:
            config.enabled = True
