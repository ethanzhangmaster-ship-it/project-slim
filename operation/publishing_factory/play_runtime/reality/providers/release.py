"""ReleaseProvider — 发布轨道状态采集.

包裹 GooglePlayRealClient.get_track_status。client 为 None 或 API 失败时
返回 fallback 空壳，绝不让单包异常影响其他包 (package 级隔离)。
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import ReleaseStatus


class ReleaseProvider:
    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client

    def get_release_status(
        self, package_name: str, track: str = "production"
    ) -> ReleaseStatus:
        if self._client is None:
            return ReleaseStatus(
                package_name=package_name, track=track, source="fallback"
            )
        try:
            raw = self._client.get_track_status(package_name, track=track) or {}
        except Exception:
            return ReleaseStatus(
                package_name=package_name, track=track, source="fallback"
            )

        user_fraction = raw.get("user_fraction")
        rollout_percentage = None
        if user_fraction is not None:
            try:
                rollout_percentage = float(user_fraction) * 100.0
            except (TypeError, ValueError):
                rollout_percentage = None

        version_code = raw.get("version_code")
        try:
            version_code = int(version_code) if version_code is not None else None
        except (TypeError, ValueError):
            version_code = None

        return ReleaseStatus(
            package_name=package_name,
            track=track,
            status=raw.get("status"),
            rollout_percentage=rollout_percentage,
            version_code=version_code,
            version_name=raw.get("version_name"),
            source="live",
        )
