from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class AndroidBuildStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AndroidBuild:
    build_id: str
    project_path: str
    status: AndroidBuildStatus = AndroidBuildStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    version_name: str = "1.0.0"
    version_code: int = 1
    apk_size_bytes: int = 0
    bundle_size_bytes: int = 0
    flavor: str = "release"
    abi_filters: List[str] = field(default_factory=lambda: ["armeabi-v7a", "arm64-v8a", "x86_64"])
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "build_id": self.build_id,
            "project_path": self.project_path,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "version_name": self.version_name,
            "version_code": self.version_code,
            "apk_size_bytes": self.apk_size_bytes,
            "bundle_size_bytes": self.bundle_size_bytes,
            "flavor": self.flavor,
            "abi_filters": self.abi_filters,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class AndroidBuilder:
    def __init__(self):
        self._builds: Dict[str, AndroidBuild] = {}

    def build(self, project_path: str) -> AndroidBuild:
        build_id = f"android_build_{int(datetime.now().timestamp())}"
        build = AndroidBuild(
            build_id=build_id,
            project_path=project_path,
            status=AndroidBuildStatus.RUNNING,
            version_name="1.0.0",
            version_code=len(self._builds) + 1,
        )
        self._builds[build_id] = build
        return build

    def test_build(self, build_path: str) -> Dict[str, Any]:
        return {
            "build_path": build_path,
            "test_results": {
                "instrumentation_tests": {
                    "passed": 89,
                    "failed": 1,
                    "skipped": 5,
                    "total": 95,
                },
                "unit_tests": {
                    "passed": 156,
                    "failed": 0,
                    "skipped": 2,
                    "total": 158,
                },
            },
            "coverage": {
                "line": 82.4,
                "function": 88.1,
                "branch": 71.2,
            },
            "lint_warnings": 12,
            "duration_seconds": 1890,
        }

    def get_build_status(self, build_id: str) -> Optional[AndroidBuild]:
        if build_id in self._builds:
            build = self._builds[build_id]
            if build.status == AndroidBuildStatus.RUNNING:
                if len(self._builds) % 4 == 0:
                    build.status = AndroidBuildStatus.FAILED
                    build.completed_at = datetime.now()
                    build.errors = ["Missing keystore", "Gradle sync failed"]
                else:
                    build.status = AndroidBuildStatus.SUCCEEDED
                    build.completed_at = datetime.now()
                    build.apk_size_bytes = 89128960
                    build.bundle_size_bytes = 67108864
                self._builds[build_id] = build
            return build
        return None

    def list_builds(self) -> List[AndroidBuild]:
        return sorted(
            self._builds.values(),
            key=lambda b: b.created_at,
            reverse=True,
        )