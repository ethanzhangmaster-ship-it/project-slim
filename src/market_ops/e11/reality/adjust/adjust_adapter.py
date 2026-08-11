"""E11.6.2 Adjust Adapter — Adjust 原始事件 → RevenueEvent 转换器。

核心转换逻辑：
  AdjustRawEvent → field mapping → RevenueEvent

转换映射：
  Adjust.creative          → RevenueEvent.creative_id
  Adjust.campaign          → RevenueEvent.campaign_id
  Adjust.user_id           → RevenueEvent.user_id
  Adjust.revenue           → RevenueEvent.revenue
  Adjust.revenue_type      → RevenueEvent.product_id (via type prefix)
  Adjust.creative → mapper → RevenueEvent.genome_id

不负责：
  - Adjust API 拉取（P04 已打通）
  - 多平台收入抓取
"""

from __future__ import annotations

from typing import Any

from ..revenue_schema import RevenueEvent, AttributionSource
from .adjust_schema import AdjustRawEvent, RevenueType
from .adjust_mapper import AdjustCreativeMapper


# ═══════════════════════════════════════════════════════════
# AdjustAdapter
# ═══════════════════════════════════════════════════════════

class AdjustAdapter:
    """Adjust 原始事件 → E11 RevenueEvent 转换器。

    将 Adjust 回调 / API 返回的原始事件映射为 E11 统一 RevenueEvent。

    Usage:
        adapter = AdjustAdapter(creative_mapper=AdjustCreativeMapper())
        revenue_event = adapter.parse_event(adjust_raw_event)
    """

    def __init__(
        self,
        creative_mapper: AdjustCreativeMapper | None = None,
    ) -> None:
        self._creative_mapper = creative_mapper or AdjustCreativeMapper()
        self._parse_count: int = 0
        self._error_count: int = 0

    # ── 主入口 ────────────────────────────────────────

    def parse_event(self, adjust_event: AdjustRawEvent) -> RevenueEvent:
        """将单个 AdjustRawEvent 转换为 RevenueEvent。

        Args:
            adjust_event: Adjust 原始事件

        Returns:
            RevenueEvent
        """
        self._parse_count += 1

        # 映射 creative_id → genome_id
        genome_id = ""
        if adjust_event.has_creative:
            genome_id = self._creative_mapper.map_creative(adjust_event.creative)

        # 构建 product_id（含收入类型前缀）
        product_id = self._build_product_id(adjust_event)

        revenue_event = RevenueEvent(
            user_id=adjust_event.user_id,
            creative_id=adjust_event.creative,
            genome_id=genome_id,
            product_id=product_id,
            revenue=adjust_event.revenue,
            currency=adjust_event.currency,
            country=adjust_event.country,
            timestamp=adjust_event.timestamp,
            source=AttributionSource.ADJUST,
        )

        return revenue_event

    def parse_batch(
        self,
        adjust_events: list[AdjustRawEvent],
    ) -> list[RevenueEvent]:
        """批量转换 AdjustRawEvent → RevenueEvent。

        Args:
            adjust_events: Adjust 原始事件列表

        Returns:
            RevenueEvent 列表
        """
        results = []
        for event in adjust_events:
            try:
                result = self.parse_event(event)
                results.append(result)
            except Exception:
                self._error_count += 1
        return results

    def aggregate_user_revenue(
        self,
        events: list[RevenueEvent],
    ) -> dict[str, dict[str, float]]:
        """按用户聚合收入。

        将同一用户的多笔收入事件聚合为：
          {
            "user_123": {
              "iap_revenue": 4.99,
              "ad_revenue": 0.05,
              "total": 5.04
            }
          }

        Args:
            events: RevenueEvent 列表

        Returns:
            {user_id: {"iap_revenue": ..., "ad_revenue": ..., "total": ...}}
        """
        user_aggregates: dict[str, dict[str, float]] = {}

        for event in events:
            if not event.is_valid:
                continue

            uid = event.user_id
            if uid not in user_aggregates:
                user_aggregates[uid] = {
                    "iap_revenue": 0.0,
                    "ad_revenue": 0.0,
                    "total": 0.0,
                }

            # 根据 product_id 前缀判断类型
            if event.product_id.startswith("iap_"):
                user_aggregates[uid]["iap_revenue"] += event.revenue
            elif event.product_id.startswith("ad_"):
                user_aggregates[uid]["ad_revenue"] += event.revenue

            user_aggregates[uid]["total"] += event.revenue

        return user_aggregates

    def aggregate_genome_revenue(
        self,
        events: list[RevenueEvent],
    ) -> dict[str, dict[str, float]]:
        """按 Genome 聚合收入。

        Args:
            events: RevenueEvent 列表

        Returns:
            {genome_id: {"iap_revenue": ..., "ad_revenue": ..., "total": ..., "users": ...}}
        """
        genome_aggregates: dict[str, dict[str, float]] = {}
        genome_users: dict[str, set[str]] = {}

        for event in events:
            if not event.is_valid or not event.has_genome:
                continue

            gid = event.genome_id
            if gid not in genome_aggregates:
                genome_aggregates[gid] = {
                    "iap_revenue": 0.0,
                    "ad_revenue": 0.0,
                    "total": 0.0,
                }
                genome_users[gid] = set()

            if event.product_id.startswith("iap_"):
                genome_aggregates[gid]["iap_revenue"] += event.revenue
            elif event.product_id.startswith("ad_"):
                genome_aggregates[gid]["ad_revenue"] += event.revenue

            genome_aggregates[gid]["total"] += event.revenue
            genome_users[gid].add(event.user_id)

        for gid in genome_aggregates:
            genome_aggregates[gid]["users"] = float(len(genome_users[gid]))

        return genome_aggregates

    # ── 内部 ──────────────────────────────────────────

    @staticmethod
    def _build_product_id(adjust_event: AdjustRawEvent) -> str:
        """根据收入类型构建 product_id。

        IAP  → iap_<event_name>
        AD   → ad_<event_name>
        TOTAL → total_<event_name>
        """
        prefix = adjust_event.revenue_type.value
        name = adjust_event.event_name or "unknown"
        return f"{prefix}_{name}"

    # ── 查询 ──────────────────────────────────────────

    @property
    def parse_count(self) -> int:
        return self._parse_count

    @property
    def error_count(self) -> int:
        return self._error_count

    def __repr__(self) -> str:
        return (
            f"AdjustAdapter(parsed={self._parse_count}, "
            f"errors={self._error_count}, "
            f"mapped_creatives={self._creative_mapper.mapped_count})"
        )