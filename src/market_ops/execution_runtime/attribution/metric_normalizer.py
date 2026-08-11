"""E10.2 Phase 4 — Metric Normalizer.

Normalizes raw platform-specific metrics into the unified
AttributionMetrics schema. Handles field name differences
across platforms.

Mapping:
    Platform     → AttributionMetrics
    ─────────────────────────────────
    spend/cost   → spend
    impressions  → impressions
    clicks       → clicks
    installs     → installs
    revenue      → revenue_d1/d7/d30
    roi          → roi_d7/roi_d30
"""

from __future__ import annotations

from typing import Any

from market_ops.execution_runtime.attribution.base_tracker import AttributionMetrics


class MetricNormalizer:
    """Normalizes platform-specific metrics to AttributionMetrics.

    Stateless. Thread-safe.

    Usage:
        normalizer = MetricNormalizer()
        raw = {"cost": 500, "installs": 200, "revenue": 1200}
        metrics = normalizer.normalize("adjust", "camp_001", raw)
    """

    # ── Platform-specific field mappings ────────────────────
    _FIELD_MAP: dict[str, dict[str, str]] = {
        "adjust": {
            "spend": "cost",
            "impressions": "impressions",
            "clicks": "clicks",
            "installs": "installs",
            "revenue_d7": "revenue",
            "revenue_d30": "revenue",
            "ctr": "ctr",
            "cvr": "conversion_rate",
        },
        "appsflyer": {
            "spend": "cost",
            "impressions": "impressions",
            "clicks": "clicks",
            "installs": "installs",
            "revenue_d7": "af_revenue",
            "revenue_d30": "af_revenue",
            "ctr": "ctr",
            "cvr": "conversion_rate",
        },
        "mock": {
            "spend": "spend",
            "impressions": "impressions",
            "clicks": "clicks",
            "installs": "installs",
            "revenue_d7": "revenue",
            "revenue_d30": "revenue",
            "ctr": "ctr",
            "cvr": "cvr",
        },
    }

    def normalize(
        self,
        source: str,
        campaign_id: str,
        raw_data: dict[str, Any],
    ) -> AttributionMetrics:
        """Normalize raw platform data to AttributionMetrics.

        Args:
            source: Platform name (adjust, appsflyer, mock).
            campaign_id: Campaign identifier.
            raw_data: Raw platform response dict.

        Returns:
            Normalized AttributionMetrics.
        """
        mapping = self._FIELD_MAP.get(source, self._FIELD_MAP["mock"])

        def _get(key: str, default: Any = 0) -> Any:
            """Get a value from raw_data using the source field name."""
            field = mapping.get(key, key)
            return raw_data.get(field, raw_data.get(key, default))

        spend = float(_get("spend"))
        impressions = int(_get("impressions"))
        clicks = int(_get("clicks"))
        installs = int(_get("installs"))
        revenue_d7 = float(_get("revenue_d7"))
        revenue_d30 = float(_get("revenue_d30"))

        # Revenue D1 estimates (30% of D7 if not provided)
        revenue_d1 = float(raw_data.get("revenue_d1", revenue_d7 * 0.3))

        return AttributionMetrics(
            campaign_id=campaign_id,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            conversions=installs,
            revenue_d1=revenue_d1,
            revenue_d7=revenue_d7,
            revenue_d30=revenue_d30,
            roi_d7=round(revenue_d7 / spend, 4) if spend > 0 else 0.0,
            roi_d30=round(revenue_d30 / spend, 4) if spend > 0 else 0.0,
            cpi=round(spend / installs, 2) if installs > 0 else 0.0,
            ctr=round(clicks / impressions, 4) if impressions > 0 else 0.0,
            cvr=round(installs / clicks, 4) if clicks > 0 else 0.0,
            source=source,
            raw_data=raw_data,
        )

    def merge_metrics(self, metrics_list: list[AttributionMetrics]) -> AttributionMetrics:
        """Merge multiple AttributionMetrics into a single aggregated view.

        Averages metrics from multiple sources for a unified view.

        Args:
            metrics_list: List of AttributionMetrics to merge.

        Returns:
            Merged AttributionMetrics with averaged values.
        """
        if not metrics_list:
            return AttributionMetrics()

        if len(metrics_list) == 1:
            return metrics_list[0]

        n = len(metrics_list)
        campaign_id = metrics_list[0].campaign_id
        sources = [m.source for m in metrics_list]

        return AttributionMetrics(
            campaign_id=campaign_id,
            spend=sum(m.spend for m in metrics_list),
            impressions=sum(m.impressions for m in metrics_list),
            clicks=sum(m.clicks for m in metrics_list),
            installs=sum(m.installs for m in metrics_list),
            conversions=sum(m.conversions for m in metrics_list),
            revenue_d1=sum(m.revenue_d1 for m in metrics_list),
            revenue_d7=sum(m.revenue_d7 for m in metrics_list),
            revenue_d30=sum(m.revenue_d30 for m in metrics_list),
            roi_d7=round(sum(m.roi_d7 for m in metrics_list) / n, 4),
            roi_d30=round(sum(m.roi_d30 for m in metrics_list) / n, 4),
            cpi=round(sum(m.cpi for m in metrics_list) / n, 2),
            ctr=round(sum(m.ctr for m in metrics_list) / n, 4),
            cvr=round(sum(m.cvr for m in metrics_list) / n, 4),
            source="merged:" + ",".join(sources),
        )