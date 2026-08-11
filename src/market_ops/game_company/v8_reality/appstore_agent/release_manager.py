from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ReleaseStatus(Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    READY_FOR_SALE = "ready_for_sale"
    RELEASED = "released"
    REJECTED = "rejected"
    PENDING_RELEASE = "pending_release"
    PAUSED = "paused"


@dataclass
class Release:
    release_id: str
    app_id: str
    build_id: str
    status: ReleaseStatus = ReleaseStatus.DRAFT
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    review_comments: List[str] = field(default_factory=list)
    phased_release: bool = False
    phased_release_percentage: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "release_id": self.release_id,
            "app_id": self.app_id,
            "build_id": self.build_id,
            "status": self.status.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "review_comments": self.review_comments,
            "phased_release": self.phased_release,
            "phased_release_percentage": self.phased_release_percentage,
        }


class ReleaseManager:
    def __init__(self):
        self._releases: Dict[str, Release] = {}
        self._app_releases: Dict[str, List[str]] = {}

    def create_release(self, app_id: str, build_id: str) -> Release:
        release_id = f"release_{int(datetime.now().timestamp())}"
        release = Release(
            release_id=release_id,
            app_id=app_id,
            build_id=build_id,
            status=ReleaseStatus.DRAFT,
        )

        self._releases[release_id] = release
        if app_id not in self._app_releases:
            self._app_releases[app_id] = []
        self._app_releases[app_id].append(release_id)

        return release

    def submit_for_review(self, app_id: str) -> Optional[Release]:
        if app_id not in self._app_releases:
            return None

        release_ids = self._app_releases[app_id]
        for rid in reversed(release_ids):
            release = self._releases.get(rid)
            if release and release.status in [ReleaseStatus.DRAFT, ReleaseStatus.PAUSED]:
                release.status = ReleaseStatus.PENDING_REVIEW
                release.submitted_at = datetime.now()
                self._releases[rid] = release
                return release

        return None

    def get_release_status(self, app_id: str) -> Optional[Release]:
        if app_id not in self._app_releases:
            return None

        release_ids = self._app_releases[app_id]
        for rid in reversed(release_ids):
            release = self._releases.get(rid)
            if release:
                if release.status == ReleaseStatus.PENDING_REVIEW:
                    release.status = ReleaseStatus.IN_REVIEW
                    self._releases[rid] = release
                elif release.status == ReleaseStatus.IN_REVIEW:
                    if len(self._releases) % 5 == 0:
                        release.status = ReleaseStatus.REJECTED
                        release.review_comments = ["Missing privacy manifest", "Guideline 5.1.1 violation"]
                    else:
                        release.status = ReleaseStatus.READY_FOR_SALE
                    self._releases[rid] = release
                elif release.status == ReleaseStatus.READY_FOR_SALE:
                    release.status = ReleaseStatus.RELEASED
                    release.released_at = datetime.now()
                    self._releases[rid] = release
                return release

        return None

    def pause_release(self, app_id: str) -> bool:
        if app_id not in self._app_releases:
            return False

        release_ids = self._app_releases[app_id]
        for rid in reversed(release_ids):
            release = self._releases.get(rid)
            if release and release.status in [ReleaseStatus.PENDING_RELEASE, ReleaseStatus.RELEASED]:
                release.status = ReleaseStatus.PAUSED
                self._releases[rid] = release
                return True

        return False

    def resume_release(self, app_id: str) -> bool:
        if app_id not in self._app_releases:
            return False

        release_ids = self._app_releases[app_id]
        for rid in reversed(release_ids):
            release = self._releases.get(rid)
            if release and release.status == ReleaseStatus.PAUSED:
                release.status = ReleaseStatus.PENDING_RELEASE
                self._releases[rid] = release
                return True

        return False