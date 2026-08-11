"""E15.2 Play Reality Connector — Reality Layer 的统一入口.

collect(package_name) -> PlayRealitySnapshot
- 三个 Provider 各自独立采集, 任一失败不影响其余 (fallback 空壳)
- collect_many 逐包隔离: 单包异常绝不打断整批
- 可选注入 PlayFeatureStore, 采集即自动落库 (历史特征)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .models import PlayRealitySnapshot
from .providers import ReleaseProvider, StabilityProvider, StoreProvider


class PlayRealityConnector:
    def __init__(
        self,
        client: Optional[Any] = None,
        *,
        release_provider: Optional[ReleaseProvider] = None,
        stability_provider: Optional[StabilityProvider] = None,
        store_provider: Optional[StoreProvider] = None,
        feature_store: Optional[Any] = None,
    ) -> None:
        self.release_provider = release_provider or ReleaseProvider(client)
        self.stability_provider = stability_provider or StabilityProvider(client)
        self.store_provider = store_provider or StoreProvider(client)
        self.feature_store = feature_store

    def collect(
        self,
        package_name: str,
        *,
        track: str = "production",
        window_days: int = 7,
        persist: bool = True,
    ) -> PlayRealitySnapshot:
        """采集单包统一快照. Provider 内部已 fallback, 本层不再抛出."""
        release = self.release_provider.get_release_status(package_name, track=track)
        stability = self.stability_provider.get_stability_metrics(
            package_name, window_days=window_days
        )
        store = self.store_provider.get_store_metrics(package_name)

        snapshot = PlayRealitySnapshot.from_parts(
            package_name, release=release, stability=stability, store=store
        )

        if persist and self.feature_store is not None:
            try:
                self.feature_store.record_snapshot(snapshot)
            except Exception:
                pass  # 落库失败不阻断采集主链路

        return snapshot

    def collect_many(
        self,
        package_names: Sequence[str],
        *,
        track: str = "production",
        window_days: int = 7,
        persist: bool = True,
    ) -> Dict[str, Optional[PlayRealitySnapshot]]:
        """逐包采集, package 级隔离: 单包炸掉记 None, 其余照常."""
        results: Dict[str, Optional[PlayRealitySnapshot]] = {}
        for pkg in package_names:
            try:
                results[pkg] = self.collect(
                    pkg, track=track, window_days=window_days, persist=persist
                )
            except Exception:
                results[pkg] = None
        return results
