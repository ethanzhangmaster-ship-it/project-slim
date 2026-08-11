from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class SyncStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncRecord:
    platform: str
    status: SyncStatus = SyncStatus.PENDING
    synced_count: int = 0
    failed_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "status": self.status.value,
            "synced_count": self.synced_count,
            "failed_count": self.failed_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_message": self.error_message,
        }


class CampaignSync:
    def __init__(self):
        self._platforms = ["meta", "google", "asa", "tiktok"]
        self._sync_records: Dict[str, SyncRecord] = {}
        self._sync_history: List[Dict[str, Any]] = []

    def sync_all_campaigns(self) -> Dict[str, Any]:
        results = {}
        for platform in self._platforms:
            result = self.sync_platform_campaigns(platform)
            results[platform] = result
        return {
            "success": all(r["success"] for r in results.values()),
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

    def sync_platform_campaigns(self, platform: str) -> Dict[str, Any]:
        if platform not in self._platforms:
            return {"success": False, "message": f"Unknown platform: {platform}"}

        record = SyncRecord(
            platform=platform,
            status=SyncStatus.RUNNING,
            start_time=datetime.now(),
        )
        self._sync_records[platform] = record

        try:
            synced_count = self._mock_sync(platform)
            record.status = SyncStatus.COMPLETED
            record.synced_count = synced_count
            record.end_time = datetime.now()

            self._sync_history.append({
                "platform": platform,
                "status": "completed",
                "synced_count": synced_count,
                "timestamp": datetime.now().isoformat(),
            })

            return {
                "success": True,
                "platform": platform,
                "synced_count": synced_count,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            record.status = SyncStatus.FAILED
            record.error_message = str(e)
            record.end_time = datetime.now()

            self._sync_history.append({
                "platform": platform,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })

            return {
                "success": False,
                "platform": platform,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_sync_status(self) -> Dict[str, Any]:
        status = {}
        for platform in self._platforms:
            record = self._sync_records.get(platform)
            if record:
                status[platform] = record.to_dict()
            else:
                status[platform] = {"status": SyncStatus.PENDING.value}
        return status

    def get_sync_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._sync_history[-limit:]

    def _mock_sync(self, platform: str) -> int:
        mock_counts = {
            "meta": 5,
            "google": 8,
            "asa": 3,
            "tiktok": 6,
        }
        return mock_counts.get(platform, 0)