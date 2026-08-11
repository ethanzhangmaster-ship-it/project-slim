from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class BuildStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Build:
    build_id: str
    project_path: str
    status: BuildStatus = BuildStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    version: str = "1.0.0"
    build_number: int = 1
    size_bytes: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "build_id": self.build_id,
            "project_path": self.project_path,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "version": self.version,
            "build_number": self.build_number,
            "size_bytes": self.size_bytes,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class IOSBuilder:
    def __init__(self):
        self._builds: Dict[str, Build] = {}

    def build(self, project_path: str) -> Build:
        build_id = f"ios_build_{int(datetime.now().timestamp())}"
        build = Build(
            build_id=build_id,
            project_path=project_path,
            status=BuildStatus.RUNNING,
            version="1.0.0",
            build_number=len(self._builds) + 1,
        )
        self._builds[build_id] = build
        return build

    def test_build(self, build_path: str) -> Dict[str, Any]:
        return {
            "build_path": build_path,
            "test_results": {
                "passed": 45,
                "failed": 2,
                "skipped": 3,
                "total": 50,
            },
            "coverage": {
                "line": 87.5,
                "function": 92.0,
                "branch": 78.3,
            },
            "duration_seconds": 1245,
        }

    def get_build_status(self, build_id: str) -> Optional[Build]:
        if build_id in self._builds:
            build = self._builds[build_id]
            if build.status == BuildStatus.RUNNING:
                if len(self._builds) % 3 == 0:
                    build.status = BuildStatus.FAILED
                    build.completed_at = datetime.now()
                    build.errors = ["Code signing error", "Provisioning profile expired"]
                else:
                    build.status = BuildStatus.SUCCEEDED
                    build.completed_at = datetime.now()
                    build.size_bytes = 157286400
                self._builds[build_id] = build
            return build
        return None

    def list_builds(self) -> List[Build]:
        return sorted(
            self._builds.values(),
            key=lambda b: b.created_at,
            reverse=True,
        )