"""E11.2.3 — MaterializerWorker。

监听 ASSET_MATCHED 事件，将资产绑定写入 entity.json，
发布 ASSET_MATERIALIZED / ASSET_MATERIALIZE_FAILED 事件。

事件流：
  输入：  ASSET_MATCHED
  输出：  ASSET_MATERIALIZED（成功）或 ASSET_MATERIALIZE_FAILED（失败）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from market_ops.creative_repository.assets.asset_materializer import AssetBindingMaterializer
from market_ops.creative_repository.assets.identity_resolver import IdentityResolver

from ..events.asset_events import AssetEvent, AssetEventType

if TYPE_CHECKING:
    from ..events.event_bus_adapter import AssetEventBus


class MaterializerWorker:
    """资产实体化 Worker。

    监听匹配事件，将绑定写入 CreativeEntity 主链路。

    Usage:
        worker = MaterializerWorker(
            creative_storage_root="data/creatives",
            event_bus=bus,
        )
        bus.subscribe("asset_matched", worker.on_asset_matched)
    """

    def __init__(
        self,
        creative_storage_root: str = "data/creatives",
        event_bus: AssetEventBus | None = None,
    ) -> None:
        self._resolver = IdentityResolver(creative_storage_root)
        self._materializer = AssetBindingMaterializer(
            creative_storage_root, self._resolver
        )
        self._bus = event_bus
        self._materialized_count = 0
        self._failed_count = 0

    # ── Event Handler ────────────────────────────────────

    def on_asset_matched(self, event: AssetEvent) -> None:
        """处理 ASSET_MATCHED 事件。

        将匹配结果写入 entity.json。
        """
        creative_id = event.creative_id
        if not creative_id:
            return

        try:
            success = self._materializer.materialize(creative_id)

            if success:
                self._materialized_count += 1
                if self._bus:
                    self._bus.publish(AssetEvent(
                        event_type=AssetEventType.ASSET_MATERIALIZED,
                        creative_id=creative_id,
                        eagle_v_number=event.eagle_v_number,
                        payload={
                            "asset_id": self._resolver.resolve_asset_id(creative_id),
                            "resolved": self._resolver.has_mapping(creative_id),
                        },
                    ))
            else:
                self._failed_count += 1
                if self._bus:
                    self._bus.publish(AssetEvent(
                        event_type=AssetEventType.ASSET_MATERIALIZE_FAILED,
                        creative_id=creative_id,
                        eagle_v_number=event.eagle_v_number,
                        error="assets.json not found or materialize failed",
                    ))

        except Exception as e:
            self._failed_count += 1
            if self._bus:
                self._bus.publish(AssetEvent(
                    event_type=AssetEventType.ASSET_MATERIALIZE_FAILED,
                    creative_id=creative_id,
                    eagle_v_number=event.eagle_v_number,
                    error=f"{type(e).__name__}: {e}",
                ))

    # ── Query ────────────────────────────────────────────

    @property
    def materialized_count(self) -> int:
        return self._materialized_count

    @property
    def failed_count(self) -> int:
        return self._failed_count

    def __repr__(self) -> str:
        return (
            f"MaterializerWorker(materialized={self._materialized_count}, "
            f"failed={self._failed_count})"
        )