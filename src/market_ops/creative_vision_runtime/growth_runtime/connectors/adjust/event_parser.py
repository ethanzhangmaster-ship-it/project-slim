"""E13.1.3 Adjust Event Parser — Adjust 原始事件 → AdjustUserEvent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import AdjustEventType, AdjustRevenueType, AdjustUserEvent


class AdjustEventParser:
    """Adjust 事件解析器.

    将 Adjust 原始 JSON 事件转换为标准 AdjustUserEvent.
    """

    # Adjust 原始事件名 → AdjustEventType 映射
    EVENT_NAME_MAP: dict[str, AdjustEventType] = {
        "install": AdjustEventType.INSTALL,
        "af_install": AdjustEventType.INSTALL,
        "session": AdjustEventType.SESSION,
        "af_session": AdjustEventType.SESSION,
        "reattribution": AdjustEventType.REATTRIBUTION,
        "af_reattribution": AdjustEventType.REATTRIBUTION,
        "tutorial_complete": AdjustEventType.TUTORIAL_COMPLETE,
        "af_tutorial_complete": AdjustEventType.TUTORIAL_COMPLETE,
        "level_complete": AdjustEventType.LEVEL_COMPLETE,
        "af_level_complete": AdjustEventType.LEVEL_COMPLETE,
        "purchase": AdjustEventType.PURCHASE,
        "af_purchase": AdjustEventType.PURCHASE,
        "ad_revenue": AdjustEventType.AD_REVENUE,
        "af_ad_revenue": AdjustEventType.AD_REVENUE,
        "subscription": AdjustEventType.SUBSCRIPTION,
        "af_subscription": AdjustEventType.SUBSCRIPTION,
        "uninstall": AdjustEventType.UNINSTALL,
        "af_uninstall": AdjustEventType.UNINSTALL,
    }

    # Revenue events
    REVENUE_EVENTS: set[AdjustEventType] = {
        AdjustEventType.PURCHASE,
        AdjustEventType.AD_REVENUE,
        AdjustEventType.SUBSCRIPTION,
    }

    @classmethod
    def parse(cls, raw_event: dict[str, Any]) -> AdjustUserEvent:
        """解析单个 Adjust 原始事件.

        Args:
            raw_event: Adjust 原始事件 JSON

        Returns:
            AdjustUserEvent 标准模型
        """
        event_name_raw = raw_event.get("event_name", raw_event.get("event", ""))

        event = AdjustUserEvent(
            event_id=cls._extract_event_id(raw_event),
            user_id=cls._extract_user_id(raw_event),
            product_id=raw_event.get("app_id", raw_event.get("product_id", "")),
            event_name=cls._map_event_name(event_name_raw),
            timestamp=cls._extract_timestamp(raw_event),
            revenue=cls._extract_revenue(raw_event),
            currency=raw_event.get("currency", "USD"),
            revenue_type=cls._determine_revenue_type(event_name_raw, raw_event),
            properties=raw_event.get("properties", raw_event.get("params", {})),
            network=raw_event.get("network", raw_event.get("network_name", "")),
            campaign_id=raw_event.get("campaign_id", raw_event.get("campaign", "")),
            adgroup_id=raw_event.get("adgroup_id", raw_event.get("adgroup", "")),
            creative_id=raw_event.get("creative_id", raw_event.get("creative", "")),
            device_id=raw_event.get("device_id", raw_event.get("idfa", raw_event.get("gps_adid", ""))),
            os_name=raw_event.get("os_name", raw_event.get("platform", "")),
            os_version=raw_event.get("os_version", ""),
            app_version=raw_event.get("app_version", ""),
            country=raw_event.get("country", ""),
            raw_event=raw_event,
        )

        return event

    @classmethod
    def parse_batch(cls, raw_events: list[dict[str, Any]]) -> list[AdjustUserEvent]:
        """批量解析."""
        return [cls.parse(e) for e in raw_events]

    @classmethod
    def filter_by_type(
        cls, events: list[AdjustUserEvent], event_type: AdjustEventType,
    ) -> list[AdjustUserEvent]:
        """按事件类型过滤."""
        return [e for e in events if e.event_name == event_type]

    @classmethod
    def filter_revenue_events(
        cls, events: list[AdjustUserEvent],
    ) -> list[AdjustUserEvent]:
        """过滤收入事件."""
        return [e for e in events if e.is_revenue_event]

    # ── Internal Helpers ──────────────────────────────────────

    @classmethod
    def _map_event_name(cls, raw_name: str) -> AdjustEventType:
        """映射事件名."""
        if not raw_name:
            return AdjustEventType.CUSTOM_EVENT
        return cls.EVENT_NAME_MAP.get(raw_name.lower(), AdjustEventType.CUSTOM_EVENT)

    @classmethod
    def _extract_event_id(cls, raw: dict[str, Any]) -> str:
        return raw.get("event_id", raw.get("event_token", raw.get("id", "")))

    @classmethod
    def _extract_user_id(cls, raw: dict[str, Any]) -> str:
        return raw.get("user_id", raw.get("adid", raw.get("gps_adid", raw.get("idfa", ""))))

    @classmethod
    def _extract_timestamp(cls, raw: dict[str, Any]) -> str:
        ts = raw.get("timestamp", raw.get("created_at", raw.get("time", "")))
        if ts:
            return str(ts)
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _extract_revenue(cls, raw: dict[str, Any]) -> float:
        rev = raw.get("revenue", raw.get("event_revenue", raw.get("value", 0.0)))
        if isinstance(rev, str):
            try:
                return float(rev)
            except (ValueError, TypeError):
                return 0.0
        if isinstance(rev, (int, float)):
            return float(rev)
        return 0.0

    @classmethod
    def _determine_revenue_type(
        cls, event_name: str, raw: dict[str, Any],
    ) -> AdjustRevenueType:
        """确定收入类型."""
        name_lower = event_name.lower()
        if "ad_revenue" in name_lower or "ad_rev" in name_lower:
            return AdjustRevenueType.IAA
        if "subscription" in name_lower or "sub" in name_lower:
            return AdjustRevenueType.SUBSCRIPTION
        if "purchase" in name_lower or "iap" in name_lower:
            return AdjustRevenueType.IAP

        rev_type = raw.get("revenue_type", "")
        if rev_type:
            try:
                return AdjustRevenueType(rev_type.lower())
            except ValueError:
                pass

        return AdjustRevenueType.IAP