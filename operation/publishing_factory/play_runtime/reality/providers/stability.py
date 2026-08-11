"""StabilityProvider — crash / ANR / vitals 采集.

包裹 GooglePlayRealClient.get_vitals (返回百分比 0-100 或 None)。
API 失败返回 fallback 空壳 (crash_rate=None)，package 级隔离。
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import StabilityMetrics


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class StabilityProvider:
    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client

    def get_stability_metrics(
        self, package_name: str, window_days: int = 7
    ) -> StabilityMetrics:
        if self._client is None:
            return StabilityMetrics(
                package_name=package_name, window_days=window_days, source="fallback"
            )
        try:
            raw = self._client.get_vitals(package_name, window_days=window_days) or {}
        except Exception:
            return StabilityMetrics(
                package_name=package_name, window_days=window_days, source="fallback"
            )

        return StabilityMetrics(
            package_name=package_name,
            crash_rate=_as_float(raw.get("crash_rate")),
            anr_rate=_as_float(raw.get("anr_rate")),
            d1_retention=_as_float(raw.get("d1_retention")),
            window_days=window_days,
            source="live",
        )
