"""E13.2.2 Revenue Attribution Engine — 收入归因引擎.

核心职责: 建立 Creative → Acquisition → User → Revenue 的完整归因链路，
解决 "一个用户到底属于哪个 Creative" 的核心问题。

归因模型:
  - Last Click: 最后点击归因 (默认)
  - Multi-Touch: 多触点归因 (按权重分配)
  - Probabilistic: 概率归因 (基于统计模型)

数据流:
  NormalizedEvent[] → AttributionEngine → AttributionEdge[] → (下游: Feature Store / Knowledge Graph)
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import (
    AttributionEdge,
    AttributionType,
    EventStatus,
    NormalizedEvent,
    PipelineConfig,
    PipelineStats,
)


# ═══════════════════════════════════════════════════════════════
# Attribution Engine
# ═══════════════════════════════════════════════════════════════


class RevenueAttributionEngine:
    """E13.2.2 收入归因引擎.

    核心功能:
      1. 将用户事件归因到具体 Creative
      2. 计算每个 Creative 的完整收入链路
      3. 生成 AttributionEdge (Creative → User → Revenue)
      4. 支持 Last Click / Multi-Touch / Probabilistic 三种归因模型
    """

    def __init__(self, config: PipelineConfig | None = None):
        self._config = config or PipelineConfig()
        self._stats = PipelineStats(pipeline_name=self._config.pipeline_name)

        # Attribution edges
        self._attribution_edges: list[AttributionEdge] = []

        # User → Creative mapping (用于归因)
        self._user_creative_map: dict[str, str] = {}
        self._user_events: dict[str, list[NormalizedEvent]] = defaultdict(list)
        self._creative_events: dict[str, list[NormalizedEvent]] = defaultdict(list)

        # Revenue aggregation per creative
        self._creative_revenue: dict[str, dict[str, float]] = defaultdict(
            lambda: {"iap_revenue": 0.0, "ad_revenue": 0.0, "total_revenue": 0.0}
        )

    # ── Properties ────────────────────────────────────────────

    @property
    def config(self) -> PipelineConfig:
        return self._config

    @property
    def stats(self) -> PipelineStats:
        return self._stats

    @property
    def attribution_count(self) -> int:
        return len(self._attribution_edges)

    # ── Last Click Attribution ────────────────────────────────

    def _last_click_attribution(
        self, user_events: list[NormalizedEvent],
    ) -> tuple[str, float]:
        """Last Click 归因: 返回 (creative_id, confidence)."""
        # 按时间排序，取最后一个有 creative_id 的事件
        creative_events = [
            e for e in user_events
            if e.has_creative_id and e.source == "meta_ads"
        ]

        if not creative_events:
            # Try adjust attribution
            creative_events = [
                e for e in user_events
                if e.has_creative_id and e.source == "adjust"
            ]

        if not creative_events:
            return ("", 0.0)

        # 最后一个归因事件
        last_event = creative_events[-1]
        return (last_event.creative_id, 1.0)

    # ── Multi-Touch Attribution ───────────────────────────────

    def _multi_touch_attribution(
        self, user_events: list[NormalizedEvent],
    ) -> dict[str, float]:
        """Multi-Touch 归因: 按事件权重分配 credit."""
        creative_events = [e for e in user_events if e.has_creative_id]

        if not creative_events:
            return {}

        # 权重: install > click > impression
        event_weights = {
            "install": 0.4,
            "click": 0.3,
            "impression": 0.2,
            "spend": 0.1,
        }

        creative_weights: dict[str, float] = {}
        for event in creative_events:
            cid = event.creative_id
            weight = event_weights.get(event.event_type, 0.1)
            creative_weights[cid] = creative_weights.get(cid, 0.0) + weight

        # Normalize
        total = sum(creative_weights.values())
        if total > 0:
            for cid in creative_weights:
                creative_weights[cid] = creative_weights[cid] / total

        return creative_weights

    # ── Probabilistic Attribution ─────────────────────────────

    def _probabilistic_attribution(
        self, user_events: list[NormalizedEvent],
    ) -> dict[str, float]:
        """概率归因: 基于事件时间衰减和类型权重."""
        creative_events = [e for e in user_events if e.has_creative_id]

        if not creative_events:
            return {}

        creative_weights: dict[str, float] = {}
        for event in creative_events:
            cid = event.creative_id
            # 简单概率: 1/n 平均分配
            creative_weights[cid] = creative_weights.get(cid, 0.0) + 1.0

        # Normalize
        total = sum(creative_weights.values())
        if total > 0:
            for cid in creative_weights:
                creative_weights[cid] = creative_weights[cid] / total

        return creative_weights

    # ── Attribution Core ──────────────────────────────────────

    def attribute(
        self, events: list[NormalizedEvent],
    ) -> list[AttributionEdge]:
        """执行归因分析.

        Args:
            events: 标准化事件列表

        Returns:
            list[AttributionEdge]: 归因边列表
        """
        if not events:
            return []

        # 1. 按 user_id 分组事件
        user_events: dict[str, list[NormalizedEvent]] = defaultdict(list)
        for event in events:
            user_id = event.user_id
            if not user_id:
                user_id = str(event.metrics.get("user_id", ""))
            if not user_id:
                user_id = str(event.metrics.get("device_id", ""))

            if user_id and user_id != "0" and user_id != "0.0":
                user_events[user_id].append(event)

            # 同时按 creative_id 分组
            if event.has_creative_id:
                self._creative_events[event.creative_id].append(event)

        # 2. 对每个用户执行归因
        new_edges: list[AttributionEdge] = []
        attribution_type = self._config.attribution_type

        for user_id, u_events in user_events.items():
            if attribution_type == AttributionType.MULTI_TOUCH:
                creative_weights = self._multi_touch_attribution(u_events)
                for cid, weight in creative_weights.items():
                    edge = self._build_attribution_edge(
                        creative_id=cid,
                        user_id=str(user_id),
                        user_events=u_events,
                        attribution_type=AttributionType.MULTI_TOUCH,
                        confidence=weight,
                    )
                    new_edges.append(edge)
            elif attribution_type == AttributionType.PROBABILISTIC:
                creative_weights = self._probabilistic_attribution(u_events)
                for cid, weight in creative_weights.items():
                    edge = self._build_attribution_edge(
                        creative_id=cid,
                        user_id=str(user_id),
                        user_events=u_events,
                        attribution_type=AttributionType.PROBABILISTIC,
                        confidence=weight,
                    )
                    new_edges.append(edge)
            else:
                # Last Click (default)
                cid, confidence = self._last_click_attribution(u_events)
                if cid:
                    edge = self._build_attribution_edge(
                        creative_id=cid,
                        user_id=str(user_id),
                        user_events=u_events,
                        attribution_type=AttributionType.LAST_CLICK,
                        confidence=confidence,
                    )
                    new_edges.append(edge)

        # 3. 过滤低置信度
        filtered_edges = [
            e for e in new_edges
            if e.attribution_confidence >= self._config.min_confidence
        ]

        self._attribution_edges.extend(filtered_edges)
        self._stats.attribution_edges += len(filtered_edges)

        if filtered_edges:
            avg_confidence = sum(e.attribution_confidence for e in filtered_edges) / len(filtered_edges)
            self._stats.attribution_confidence_avg = avg_confidence

        return filtered_edges

    def _build_attribution_edge(
        self,
        creative_id: str,
        user_id: str,
        user_events: list[NormalizedEvent],
        attribution_type: AttributionType,
        confidence: float = 1.0,
    ) -> AttributionEdge:
        """构建 AttributionEdge."""
        # 聚合 spend
        spend = sum(
            e.get_metric("spend") for e in user_events
            if e.source == "meta_ads"
        )
        impressions = sum(
            int(e.get_metric("impressions")) for e in user_events
            if e.source == "meta_ads"
        )
        clicks = sum(
            int(e.get_metric("clicks")) for e in user_events
            if e.source == "meta_ads"
        )
        installs = sum(
            int(e.get_metric("installs")) for e in user_events
        )

        # 聚合 revenue
        iap_revenue = sum(
            e.get_metric("iap_revenue") + e.get_metric("revenue")
            for e in user_events
            if e.source == "adjust"
        )
        ad_revenue = sum(
            e.get_metric("ad_revenue")
            for e in user_events
            if e.source in ("max", "adjust")
        )
        total_revenue = iap_revenue + ad_revenue

        # LTV
        d7_ltv = sum(
            e.get_metric("d7_ltv") + e.get_metric("ltv")
            for e in user_events
            if e.source == "adjust"
        )
        d30_ltv = sum(
            e.get_metric("d30_ltv")
            for e in user_events
            if e.source == "adjust"
        )

        # ROAS
        d7_roas = d7_ltv / spend if spend > 0 else 0.0
        d30_roas = d30_ltv / spend if spend > 0 else 0.0

        # Retention
        d1_retention = sum(
            e.get_metric("d1_retention")
            for e in user_events
            if e.source == "adjust"
        )
        d7_retention = sum(
            e.get_metric("d7_retention")
            for e in user_events
            if e.source == "adjust"
        )
        d30_retention = sum(
            e.get_metric("d30_retention")
            for e in user_events
            if e.source == "adjust"
        )

        # Payer
        is_payer = iap_revenue > 0
        payer_rate = 0.0
        if user_events:
            payer_count = sum(
                1 for e in user_events
                if e.get_metric("payer_rate") > 0 or e.get_metric("iap_revenue") > 0
            )
            payer_rate = payer_count / len(user_events) if user_events else 0.0

        # CTR / CPI
        ctr = clicks / impressions if impressions > 0 else 0.0
        cpi = spend / installs if installs > 0 else 0.0

        # Campaign info
        campaign_id = ""
        campaign_name = ""
        network = ""
        for e in user_events:
            if e.campaign_id:
                campaign_id = e.campaign_id
                break
        for e in user_events:
            if e.network:
                network = e.network
                break

        return AttributionEdge(
            creative_id=creative_id,
            user_id=user_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            network=network,
            spend=spend,
            cpi=cpi,
            ctr=ctr,
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            iap_revenue=iap_revenue,
            ad_revenue=ad_revenue,
            total_revenue=total_revenue,
            d7_ltv=d7_ltv,
            d30_ltv=d30_ltv,
            predicted_ltv=d30_ltv * 1.2,  # 简单预测
            d7_roas=d7_roas,
            d30_roas=d30_roas,
            d1_retention=d1_retention,
            d7_retention=d7_retention,
            d30_retention=d30_retention,
            is_payer=is_payer,
            payer_rate=payer_rate,
            attribution_type=attribution_type,
            attribution_confidence=confidence,
            date=user_events[0].date if user_events else "",
        )

    # ── Query ─────────────────────────────────────────────────

    def get_edges_by_creative(self, creative_id: str) -> list[AttributionEdge]:
        """按 creative_id 获取归因边."""
        return [e for e in self._attribution_edges if e.creative_id == creative_id]

    def get_edges_by_campaign(self, campaign_id: str) -> list[AttributionEdge]:
        """按 campaign_id 获取归因边."""
        return [e for e in self._attribution_edges if e.campaign_id == campaign_id]

    def get_edges_by_user(self, user_id: str) -> list[AttributionEdge]:
        """按 user_id 获取归因边."""
        return [e for e in self._attribution_edges if e.user_id == user_id]

    def get_all_edges(self) -> list[AttributionEdge]:
        """获取所有归因边."""
        return list(self._attribution_edges)

    def get_profitable_edges(self) -> list[AttributionEdge]:
        """获取盈利的归因边."""
        return [e for e in self._attribution_edges if e.is_profitable]

    def get_hybrid_edges(self) -> list[AttributionEdge]:
        """获取混合变现的归因边."""
        return [e for e in self._attribution_edges if e.is_hybrid_monetization]

    # ── Aggregation ───────────────────────────────────────────

    def aggregate_by_creative(self) -> dict[str, dict[str, Any]]:
        """按 Creative 聚合归因结果."""
        result: dict[str, dict[str, Any]] = {}
        for edge in self._attribution_edges:
            cid = edge.creative_id
            if cid not in result:
                result[cid] = {
                    "total_spend": 0.0,
                    "total_revenue": 0.0,
                    "total_iap": 0.0,
                    "total_ad": 0.0,
                    "total_installs": 0,
                    "total_impressions": 0,
                    "total_clicks": 0,
                    "user_count": 0,
                    "payer_count": 0,
                    "avg_roas": 0.0,
                    "avg_d7_roas": 0.0,
                    "avg_d30_roas": 0.0,
                    "avg_ltv": 0.0,
                    "avg_confidence": 0.0,
                    "edges": 0,
                }

            r = result[cid]
            r["total_spend"] += edge.spend
            r["total_revenue"] += edge.total_revenue
            r["total_iap"] += edge.iap_revenue
            r["total_ad"] += edge.ad_revenue
            r["total_installs"] += edge.installs
            r["total_impressions"] += edge.impressions
            r["total_clicks"] += edge.clicks
            r["user_count"] += 1
            if edge.is_payer:
                r["payer_count"] += 1
            r["edges"] += 1

        # Compute averages
        for cid, r in result.items():
            count = r["edges"]
            r["avg_roas"] = round(r["total_revenue"] / r["total_spend"], 4) if r["total_spend"] > 0 else 0.0
            if count > 0:
                r["avg_confidence"] = round(
                    sum(e.attribution_confidence for e in self._attribution_edges if e.creative_id == cid) / count, 2
                )
            else:
                r["avg_confidence"] = 0.0

        return result

    def aggregate_by_network(self) -> dict[str, dict[str, float]]:
        """按 Network 聚合归因结果."""
        result: dict[str, dict[str, float]] = defaultdict(
            lambda: {"spend": 0.0, "revenue": 0.0, "installs": 0, "edges": 0}
        )
        for edge in self._attribution_edges:
            r = result[edge.network or "unknown"]
            r["spend"] += edge.spend
            r["revenue"] += edge.total_revenue
            r["installs"] += edge.installs
            r["edges"] += 1
        return dict(result)

    def get_top_creatives_by_roas(self, limit: int = 10) -> list[dict[str, Any]]:
        """按 ROAS 排序的 Top Creatives."""
        agg = self.aggregate_by_creative()
        sorted_creatives = sorted(
            agg.items(),
            key=lambda x: x[1].get("avg_roas", 0),
            reverse=True,
        )
        return [
            {"creative_id": cid, **data}
            for cid, data in sorted_creatives[:limit]
        ]

    def get_top_creatives_by_revenue(self, limit: int = 10) -> list[dict[str, Any]]:
        """按收入排序的 Top Creatives."""
        agg = self.aggregate_by_creative()
        sorted_creatives = sorted(
            agg.items(),
            key=lambda x: x[1].get("total_revenue", 0),
            reverse=True,
        )
        return [
            {"creative_id": cid, **data}
            for cid, data in sorted_creatives[:limit]
        ]

    # ── Lifecycle ─────────────────────────────────────────────

    def flush(self) -> None:
        """清空归因数据."""
        self._attribution_edges.clear()
        self._user_creative_map.clear()
        self._user_events.clear()
        self._creative_events.clear()
        self._creative_revenue.clear()

    def reset(self) -> None:
        """重置引擎."""
        self.flush()
        self._stats = PipelineStats(pipeline_name=self._config.pipeline_name)

    def get_summary(self) -> dict[str, Any]:
        """获取归因摘要."""
        return {
            "attribution_type": self._config.attribution_type.value,
            "total_edges": self.attribution_count,
            "profitable_edges": len(self.get_profitable_edges()),
            "hybrid_edges": len(self.get_hybrid_edges()),
            "unique_creatives": len(self.aggregate_by_creative()),
            "by_network": self.aggregate_by_network(),
            "top_by_roas": self.get_top_creatives_by_roas(5),
            "top_by_revenue": self.get_top_creatives_by_revenue(5),
        }