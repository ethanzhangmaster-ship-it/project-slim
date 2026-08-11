"""E11.2.3 — LifecycleWorker。

监听 ASSET_MATERIALIZED 和 PERFORMANCE_UPDATED 事件，
管理素材生命周期状态转换。

事件流：
  输入：  ASSET_MATERIALIZED → 状态 NEW → MATCHED
  输入：  PERFORMANCE_UPDATED  → 状态 MATCHED → TESTING → WINNER/FAILED
  输出：  ASSET_WINNER_DETECTED（ROAS 超过阈值）
  输出：  ASSET_FAILED（ROAS 过低）

状态机规则：
  NEW → MATERIALIZED: 自动转 MATCHED
  MATCHED → TESTING:  impressions >= 1000
  TESTING → WINNER:    ROAS >= 1.0
  TESTING → FAILED:    ROAS < 1.0 && spend >= 500
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from market_ops.creative_asset_binding.asset_lifecycle import (
    AssetLifecycleManager,
    AssetLifecycleStatus,
)

from ..events.asset_events import AssetEvent, AssetEventType

if TYPE_CHECKING:
    from ..events.event_bus_adapter import AssetEventBus


class LifecycleWorker:
    """素材生命周期管理 Worker。

    监听事件驱动状态转换：
      - ASSET_MATERIALIZED → NEW → MATCHED
      - PERFORMANCE_UPDATED → MATCHED → TESTING → WINNER/FAILED

    Usage:
        worker = LifecycleWorker(
            lifecycle_path="data/asset_lifecycle.json",
            event_bus=bus,
        )
        bus.subscribe("asset_materialized", worker.on_asset_materialized)
        bus.subscribe("performance_updated", worker.on_performance_updated)
    """

    # 赢家阈值
    WINNER_ROAS_THRESHOLD = 1.0
    TESTING_MIN_IMPRESSIONS = 1000
    FAILED_MIN_SPEND = 500.0

    def __init__(
        self,
        lifecycle_path: str = "data/asset_lifecycle.json",
        event_bus: AssetEventBus | None = None,
    ) -> None:
        self._manager = AssetLifecycleManager(lifecycle_path)
        self._bus = event_bus
        self._winner_count = 0
        self._failed_count = 0

    # ── Event Handlers ───────────────────────────────────

    def on_asset_materialized(self, event: AssetEvent) -> None:
        """处理 ASSET_MATERIALIZED 事件。

        素材实体化完成 → 状态从 NEW 转为 MATCHED。
        """
        asset_id = event.eagle_v_number or event.creative_id
        if not asset_id:
            return

        current = self._manager.get_status(asset_id)
        if current is None or current == AssetLifecycleStatus.NEW:
            self._manager.transition(asset_id, AssetLifecycleStatus.MATCHED, {
                "creative_id": event.creative_id,
                "materialized_at": event.timestamp,
            })

    def on_performance_updated(self, event: AssetEvent) -> None:
        """处理 PERFORMANCE_UPDATED 事件。

        根据性能数据判断状态转换：
          - 首次有数据 → MATCHED → TESTING
          - ROAS >= 阈值  → TESTING → WINNER
          - ROAS < 阈值 && spend >= 500 → TESTING → FAILED

        payload 字段：
          spend, revenue, roas, impressions, installs
        """
        creative_id = event.creative_id
        eagle_v = event.eagle_v_number
        asset_id = eagle_v or creative_id
        if not asset_id:
            return

        payload = event.payload
        roas = float(payload.get("roas", 0))
        spend = float(payload.get("spend", 0))
        impressions = float(payload.get("impressions", 0))
        revenue = float(payload.get("revenue", 0))

        current = self._manager.get_status(asset_id)

        # 新素材（首次性能数据）→ MATCHED → TESTING
        if current is None or current == AssetLifecycleStatus.NEW:
            self._manager.transition(asset_id, AssetLifecycleStatus.MATCHED)

        if impressions >= self.TESTING_MIN_IMPRESSIONS:
            self._manager.transition(asset_id, AssetLifecycleStatus.TESTING, {
                "spend": spend,
                "revenue": revenue,
                "roas": roas,
                "impressions": impressions,
            })

        # TESTING → WINNER
        if roas >= self.WINNER_ROAS_THRESHOLD and spend > 0:
            success = self._manager.transition(
                asset_id, AssetLifecycleStatus.WINNER,
                {
                    "spend": spend,
                    "revenue": revenue,
                    "roas": roas,
                    "impressions": impressions,
                },
            )
            if success:
                self._winner_count += 1
                if self._bus:
                    self._bus.publish(AssetEvent(
                        event_type=AssetEventType.ASSET_WINNER_DETECTED,
                        creative_id=creative_id,
                        eagle_v_number=eagle_v,
                        payload={
                            "spend": spend,
                            "revenue": revenue,
                            "roas": roas,
                            "impressions": impressions,
                            "status": AssetLifecycleStatus.WINNER.value,
                        },
                    ))

        # TESTING → FAILED (低 ROAS + 足够花费)
        elif roas > 0 and roas < self.WINNER_ROAS_THRESHOLD and spend >= self.FAILED_MIN_SPEND:
            success = self._manager.mark_failed(
                asset_id,
                reason=f"low_roas_{roas:.2f}",
            )
            if success:
                self._failed_count += 1
                if self._bus:
                    self._bus.publish(AssetEvent(
                        event_type=AssetEventType.ASSET_FAILED,
                        creative_id=creative_id,
                        eagle_v_number=eagle_v,
                        payload={
                            "spend": spend,
                            "revenue": revenue,
                            "roas": roas,
                            "reason": f"low_roas_{roas:.2f}",
                            "status": AssetLifecycleStatus.FAILED.value,
                        },
                    ))

    # ── Query ────────────────────────────────────────────

    def get_status(self, asset_id: str) -> AssetLifecycleStatus | None:
        return self._manager.get_status(asset_id)

    def get_winners(self) -> list[str]:
        return self._manager.get_winners()

    def get_dna_ready(self) -> list[str]:
        return self._manager.get_dna_ready()

    @property
    def winner_count(self) -> int:
        return self._winner_count

    @property
    def failed_count(self) -> int:
        return self._failed_count

    def to_summary(self) -> str:
        return self._manager.to_summary()

    def __repr__(self) -> str:
        return (
            f"LifecycleWorker(winners={self._winner_count}, "
            f"failed={self._failed_count})"
        )