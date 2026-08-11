from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum


class RollbackStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Version:
    version: str
    build_id: str
    release_date: datetime = field(default_factory=datetime.now)
    installs: int = 0
    active_users: int = 0
    stability: float = 1.0
    crash_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "build_id": self.build_id,
            "release_date": self.release_date.isoformat(),
            "installs": self.installs,
            "active_users": self.active_users,
            "stability": self.stability,
            "crash_rate": self.crash_rate,
        }


@dataclass
class Rollback:
    rollback_id: str
    app_id: str
    from_version: str
    to_version: str
    status: RollbackStatus = RollbackStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    affected_users: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rollback_id": self.rollback_id,
            "app_id": self.app_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "affected_users": self.affected_users,
            "error_message": self.error_message,
        }


class RollbackRelease:
    def __init__(self):
        self._versions: Dict[str, List[Version]] = {}
        self._rollbacks: Dict[str, Rollback] = {}
        self._app_rollbacks: Dict[str, List[str]] = {}

    def rollback(self, app_id: str, version: str) -> Rollback:
        rollback_id = f"rollback_{int(datetime.now().timestamp())}"
        current_version = self._get_current_version(app_id)

        rollback = Rollback(
            rollback_id=rollback_id,
            app_id=app_id,
            from_version=current_version if current_version else "1.0.0",
            to_version=version,
            status=RollbackStatus.IN_PROGRESS,
        )

        self._rollbacks[rollback_id] = rollback
        if app_id not in self._app_rollbacks:
            self._app_rollbacks[app_id] = []
        self._app_rollbacks[app_id].append(rollback_id)

        return rollback

    def _get_current_version(self, app_id: str) -> Optional[str]:
        versions = self.list_versions(app_id)
        return versions[0].version if versions else None

    def get_rollback_status(self, app_id: str) -> Optional[Rollback]:
        if app_id not in self._app_rollbacks:
            return None

        rollback_ids = self._app_rollbacks[app_id]
        for rid in reversed(rollback_ids):
            rollback = self._rollbacks.get(rid)
            if rollback:
                if rollback.status == RollbackStatus.IN_PROGRESS:
                    if len(self._rollbacks) % 6 == 0:
                        rollback.status = RollbackStatus.FAILED
                        rollback.error_message = "Rollback failed due to server error"
                    else:
                        rollback.status = RollbackStatus.COMPLETED
                        rollback.affected_users = 15000
                    rollback.completed_at = datetime.now()
                    self._rollbacks[rid] = rollback
                return rollback

        return None

    def list_versions(self, app_id: str) -> List[Version]:
        if app_id not in self._versions:
            return self._generate_mock_versions(app_id)

        return sorted(
            self._versions[app_id],
            key=lambda v: v.release_date,
            reverse=True,
        )

    def _generate_mock_versions(self, app_id: str) -> List[Version]:
        mock_versions = [
            {"version": "1.2.0", "build_id": "build_120", "installs": 50000, "active_users": 25000, "stability": 0.85, "crash_rate": 0.02},
            {"version": "1.1.0", "build_id": "build_110", "installs": 120000, "active_users": 15000, "stability": 0.95, "crash_rate": 0.005},
            {"version": "1.0.5", "build_id": "build_105", "installs": 80000, "active_users": 5000, "stability": 0.98, "crash_rate": 0.002},
            {"version": "1.0.0", "build_id": "build_100", "installs": 200000, "active_users": 1000, "stability": 0.99, "crash_rate": 0.001},
        ]

        versions = []
        for idx, data in enumerate(mock_versions):
            version = Version(
                release_date=datetime.now() - timedelta(days=idx * 7),
                **data,
            )
            versions.append(version)

        self._versions[app_id] = versions
        return versions

    def get_version_details(self, app_id: str, version: str) -> Optional[Version]:
        versions = self.list_versions(app_id)
        for v in versions:
            if v.version == version:
                return v
        return None