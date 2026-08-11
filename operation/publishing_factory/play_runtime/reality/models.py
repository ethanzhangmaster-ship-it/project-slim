"""E15.2 Reality Layer 数据模型.

统一的 Google Play 运行时快照结构。所有 rate 均为百分比 (0-100)，
与 GooglePlayRealClient.get_vitals 的口径一致。
时间戳统一 datetime.now(timezone.utc)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


@dataclass
class ReleaseStatus:
    """发布轨道状态 (source: GooglePlayRealClient.get_track_status)."""

    package_name: str
    track: str = "production"
    status: Optional[str] = None          # inProgress / completed / halted / draft
    rollout_percentage: Optional[float] = None  # 0-100
    version_code: Optional[int] = None
    version_name: Optional[str] = None
    source: str = "unknown"               # live / fallback
    collected_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "track": self.track,
            "status": self.status,
            "rollout_percentage": self.rollout_percentage,
            "version_code": self.version_code,
            "version_name": self.version_name,
            "source": self.source,
            "collected_at": _iso(self.collected_at),
        }


@dataclass
class StabilityMetrics:
    """稳定性指标 (source: GooglePlayRealClient.get_vitals). rate 为百分比 0-100."""

    package_name: str
    crash_rate: Optional[float] = None    # % , None = 数据不可得
    anr_rate: Optional[float] = None      # %
    d1_retention: Optional[float] = None  # %
    window_days: int = 7
    source: str = "unknown"
    collected_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "crash_rate": self.crash_rate,
            "anr_rate": self.anr_rate,
            "d1_retention": self.d1_retention,
            "window_days": self.window_days,
            "source": self.source,
            "collected_at": _iso(self.collected_at),
        }


@dataclass
class StoreMetrics:
    """商店表现指标 (source: GooglePlayRealClient.get_reviews 聚合)."""

    package_name: str
    rating_average: Optional[float] = None  # 1.0-5.0
    review_count: int = 0
    installs: Optional[int] = None          # Play Console API 无公开安装量时为 None
    negative_review_ratio: Optional[float] = None  # <=2 星占比 0-1
    source: str = "unknown"
    collected_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "rating_average": self.rating_average,
            "review_count": self.review_count,
            "installs": self.installs,
            "negative_review_ratio": self.negative_review_ratio,
            "source": self.source,
            "collected_at": _iso(self.collected_at),
        }


@dataclass
class PlayRealitySnapshot:
    """统一现实快照 — Reality Layer 的唯一出口结构.

    Decision Engine 只消费本结构，不直接触碰任何 Provider / API。
    """

    package_name: str
    version_code: Optional[int] = None
    version_name: Optional[str] = None
    track: str = "production"
    release_state: Optional[str] = None
    rollout_percentage: Optional[float] = None  # 0-100
    crash_rate: Optional[float] = None          # % 0-100
    anr_rate: Optional[float] = None            # % 0-100
    d1_retention: Optional[float] = None        # % 0-100
    installs: Optional[int] = None
    rating_average: Optional[float] = None
    review_count: int = 0
    negative_review_ratio: Optional[float] = None
    sources: Dict[str, str] = field(default_factory=dict)  # {"release": "live", ...}
    collected_at: datetime = field(default_factory=_utcnow)

    @classmethod
    def from_parts(
        cls,
        package_name: str,
        release: Optional[ReleaseStatus] = None,
        stability: Optional[StabilityMetrics] = None,
        store: Optional[StoreMetrics] = None,
    ) -> "PlayRealitySnapshot":
        snap = cls(package_name=package_name)
        if release is not None:
            snap.version_code = release.version_code
            snap.version_name = release.version_name
            snap.track = release.track
            snap.release_state = release.status
            snap.rollout_percentage = release.rollout_percentage
            snap.sources["release"] = release.source
        if stability is not None:
            snap.crash_rate = stability.crash_rate
            snap.anr_rate = stability.anr_rate
            snap.d1_retention = stability.d1_retention
            snap.sources["stability"] = stability.source
        if store is not None:
            snap.installs = store.installs
            snap.rating_average = store.rating_average
            snap.review_count = store.review_count
            snap.negative_review_ratio = store.negative_review_ratio
            snap.sources["store"] = store.source
        return snap

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "version_code": self.version_code,
            "version_name": self.version_name,
            "track": self.track,
            "release_state": self.release_state,
            "rollout_percentage": self.rollout_percentage,
            "crash_rate": self.crash_rate,
            "anr_rate": self.anr_rate,
            "d1_retention": self.d1_retention,
            "installs": self.installs,
            "rating_average": self.rating_average,
            "review_count": self.review_count,
            "negative_review_ratio": self.negative_review_ratio,
            "sources": dict(self.sources),
            "collected_at": _iso(self.collected_at),
        }
