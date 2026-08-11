"""E13.1.3 Adjust Value Mapper — 事件/归因/留存 → UserValueSnapshot."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import (
    AdjustEventType,
    AdjustRevenueType,
    AdjustUserEvent,
    AttributionRecord,
    RetentionSnapshot,
    UserValueSnapshot,
)


class AdjustValueMapper:
    """Adjust 用户价值映射器.

    核心职责: 将 Adjust 事件、归因和留存数据聚合为 UserValueSnapshot，
    作为 Growth OS Reality Layer 的标准化输入。
    """

    @classmethod
    def build_snapshot(
        cls,
        events: list[AdjustUserEvent],
        retention: RetentionSnapshot | None = None,
        attributions: list[AttributionRecord] | None = None,
        product_id: str = "",
        date: str = "",
    ) -> UserValueSnapshot:
        """构建 UserValueSnapshot.

        Args:
            events: Adjust 用户事件列表
            retention: 留存快照 (可选)
            attributions: 归因记录 (可选)
            product_id: 产品 ID
            date: 快照日期

        Returns:
            UserValueSnapshot 聚合结果
        """
        attribution_list = attributions or []
        snapshot_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pid = product_id or cls._extract_product_id(events)

        # 用户统计
        user_ids = set(e.user_id for e in events if e.user_id)
        install_events = [e for e in events if e.event_name == AdjustEventType.INSTALL]
        new_users = len(set(e.user_id for e in install_events if e.user_id))

        paying_user_ids = set(
            e.user_id for e in events
            if e.is_revenue_event and e.revenue_type != AdjustRevenueType.IAA and e.user_id
        )

        # 收入统计
        iap_revenue = sum(
            e.revenue for e in events
            if e.revenue_type == AdjustRevenueType.IAP and e.revenue > 0
        )
        ad_revenue = sum(
            e.revenue for e in events
            if e.revenue_type == AdjustRevenueType.IAA and e.revenue > 0
        )
        subscription_revenue = sum(
            e.revenue for e in events
            if e.revenue_type == AdjustRevenueType.SUBSCRIPTION and e.revenue > 0
        )
        total_revenue = iap_revenue + ad_revenue + subscription_revenue

        total_users = len(user_ids)
        paying_users = len(paying_user_ids)

        # 单用户经济学
        arpu = total_revenue / total_users if total_users > 0 else 0.0
        arppu = total_revenue / paying_users if paying_users > 0 else 0.0
        paying_rate = paying_users / total_users if total_users > 0 else 0.0

        # 按网络分组
        by_network = cls._build_network_breakdown(events, attribution_list)

        # 安装数
        installs = len(install_events)

        return UserValueSnapshot(
            product_id=pid,
            date=snapshot_date,
            total_users=total_users,
            new_users=new_users,
            active_users=len(user_ids),
            paying_users=paying_users,
            total_revenue=round(total_revenue, 4),
            iap_revenue=round(iap_revenue, 4),
            ad_revenue=round(ad_revenue, 4),
            subscription_revenue=round(subscription_revenue, 4),
            arpu=round(arpu, 4),
            arppu=round(arppu, 4),
            paying_rate=round(paying_rate, 4),
            retention=retention,
            by_network=by_network,
            installs=installs,
        )

    @classmethod
    def build_snapshots_by_date(
        cls,
        events: list[AdjustUserEvent],
        retention: RetentionSnapshot | None = None,
        attributions: list[AttributionRecord] | None = None,
        product_id: str = "",
    ) -> list[UserValueSnapshot]:
        """按日期拆分构建多个快照.

        Args:
            events: 跨多天的用户事件
            retention: 留存快照
            attributions: 归因记录
            product_id: 产品 ID

        Returns:
            按日期排序的 UserValueSnapshot 列表
        """
        events_by_date: dict[str, list[AdjustUserEvent]] = defaultdict(list)
        for event in events:
            date_key = event.timestamp[:10] if event.timestamp else "unknown"
            events_by_date[date_key].append(event)

        snapshots: list[UserValueSnapshot] = []
        for date_key in sorted(events_by_date.keys()):
            snapshot = cls.build_snapshot(
                events=events_by_date[date_key],
                retention=retention,
                attributions=attributions,
                product_id=product_id,
                date=date_key,
            )
            snapshots.append(snapshot)

        return snapshots

    @classmethod
    def build_snapshot_by_network(
        cls,
        events: list[AdjustUserEvent],
        product_id: str = "",
        date: str = "",
    ) -> dict[str, UserValueSnapshot]:
        """按网络分别构建 UserValueSnapshot.

        Args:
            events: 用户事件列表
            product_id: 产品 ID
            date: 快照日期

        Returns:
            {network_name: UserValueSnapshot} 字典
        """
        events_by_network: dict[str, list[AdjustUserEvent]] = defaultdict(list)
        for event in events:
            network = event.network or "organic"
            events_by_network[network].append(event)

        result: dict[str, UserValueSnapshot] = {}
        for network, net_events in events_by_network.items():
            result[network] = cls.build_snapshot(
                events=net_events,
                product_id=product_id,
                date=date,
            )

        return result

    @classmethod
    def compute_revenue_breakdown(
        cls, events: list[AdjustUserEvent],
    ) -> dict[str, float]:
        """计算收入构成."""
        iap = sum(e.revenue for e in events if e.revenue_type == AdjustRevenueType.IAP)
        iaa = sum(e.revenue for e in events if e.revenue_type == AdjustRevenueType.IAA)
        sub = sum(e.revenue for e in events if e.revenue_type == AdjustRevenueType.SUBSCRIPTION)
        total = iap + iaa + sub

        return {
            "iap": round(iap, 4),
            "iaa": round(iaa, 4),
            "subscription": round(sub, 4),
            "total": round(total, 4),
            "iap_ratio": round(iap / total, 4) if total > 0 else 0.0,
            "iaa_ratio": round(iaa / total, 4) if total > 0 else 0.0,
            "subscription_ratio": round(sub / total, 4) if total > 0 else 0.0,
        }

    @classmethod
    def compute_event_type_counts(
        cls, events: list[AdjustUserEvent],
    ) -> dict[str, int]:
        """统计各事件类型数量."""
        counts: dict[str, int] = defaultdict(int)
        for event in events:
            counts[event.event_name.value] += 1
        return dict(counts)

    # ── Internal Helpers ──────────────────────────────────────

    @classmethod
    def _extract_product_id(cls, events: list[AdjustUserEvent]) -> str:
        """从事件中提取产品 ID."""
        for event in events:
            if event.product_id:
                return event.product_id
        return ""

    @classmethod
    def _build_network_breakdown(
        cls,
        events: list[AdjustUserEvent],
        attributions: list[AttributionRecord],
    ) -> dict[str, dict[str, Any]]:
        """按网络构建收入/用户分解."""
        by_network: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"revenue": 0.0, "users": 0, "installs": 0, "paying_users": 0, "arpu": 0.0},
        )

        network_users: dict[str, set[str]] = defaultdict(set)
        network_payers: dict[str, set[str]] = defaultdict(set)

        for event in events:
            network = event.network or "organic"
            by_network[network]["revenue"] += event.revenue
            if event.user_id:
                network_users[network].add(event.user_id)
            if event.is_revenue_event and event.revenue_type != AdjustRevenueType.IAA and event.user_id:
                network_payers[network].add(event.user_id)
            if event.event_name == AdjustEventType.INSTALL:
                by_network[network]["installs"] += 1

        for network in by_network:
            users = len(network_users[network])
            revenue = by_network[network]["revenue"]
            by_network[network]["users"] = users
            by_network[network]["paying_users"] = len(network_payers[network])
            by_network[network]["arpu"] = round(revenue / users, 4) if users > 0 else 0.0
            by_network[network]["revenue"] = round(revenue, 4)

        return dict(by_network)