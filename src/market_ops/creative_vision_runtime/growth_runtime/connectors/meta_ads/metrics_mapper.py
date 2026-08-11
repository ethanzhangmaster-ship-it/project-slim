"""E13.1.2 Meta Metrics Mapper — Meta 原始字段 → Growth OS 标准字段映射."""

from __future__ import annotations

from typing import Any

from .models import MetaPerformance


class MetaMetricsMapper:
    """Meta 广告指标映射器.

    功能:
      - 将 Meta API 原始 JSON 响应映射为 MetaPerformance 标准模型
      - 处理 Meta 特有的字段命名和结构
      - 计算派生指标 (CTR, CPI, ROAS, etc.)
    """

    # Meta 字段 → 标准字段映射
    FIELD_MAP: dict[str, str] = {
        "spend": "spend",
        "impressions": "impressions",
        "clicks": "clicks",
        "reach": "reach",
        "frequency": "frequency",
        "cpm": "cpm",
        "cpc": "cpc",
        "ctr": "ctr",
        "unique_clicks": "unique_clicks",
        "social_spend": "social_spend",
        "social_impressions": "social_impressions",
    }

    # Meta action type → 标准指标映射
    ACTION_MAP: dict[str, str] = {
        "mobile_app_install": "installs",
        "purchase": "purchases",
        "app_custom_event": "app_custom_events",
        "omni_purchase": "purchases",
    }

    # Ranking 字段
    RANKING_FIELDS: list[str] = [
        "quality_ranking",
        "engagement_rate_ranking",
        "conversion_rate_ranking",
    ]

    @classmethod
    def map_insight(cls, raw_data: dict[str, Any]) -> MetaPerformance:
        """将 Meta Insights API 原始响应映射为 MetaPerformance.

        Args:
            raw_data: Meta API /insights 端点的单条响应

        Returns:
            MetaPerformance 标准模型
        """
        perf = MetaPerformance(
            campaign_id=raw_data.get("campaign_id", ""),
            adset_id=raw_data.get("adset_id", ""),
            creative_id=raw_data.get("ad_id", ""),
            account_id=raw_data.get("account_id", ""),
            date_start=raw_data.get("date_start", ""),
            date_stop=raw_data.get("date_stop", ""),
        )

        # 映射标准字段
        for meta_key, perf_key in cls.FIELD_MAP.items():
            if meta_key in raw_data:
                raw_value = raw_data[meta_key]
                if raw_value is not None:
                    setattr(perf, perf_key, cls._parse_numeric(raw_value))

        # 映射 actions (安装、购买等)
        actions = raw_data.get("actions", [])
        cls._map_actions(perf, actions, raw_data.get("impressions", 0))

        # 映射 action_values (收入)
        action_values = raw_data.get("action_values", [])
        cls._map_action_values(perf, action_values)

        # 映射 cost_per_action_type
        cost_per_action = raw_data.get("cost_per_action_type", [])
        cls._map_cost_per_action(perf, cost_per_action)

        # 映射 ranking
        for ranking_field in cls.RANKING_FIELDS:
            if ranking_field in raw_data:
                setattr(perf, ranking_field, raw_data[ranking_field])

        # 计算派生指标
        cls._compute_derived_metrics(perf)

        return perf

    @classmethod
    def map_insights_batch(cls, raw_data_list: list[dict[str, Any]]) -> list[MetaPerformance]:
        """批量映射."""
        return [cls.map_insight(data) for data in raw_data_list]

    @classmethod
    def _map_actions(cls, perf: MetaPerformance, actions: list[dict[str, Any]], impressions: int) -> None:
        """映射 actions 数组."""
        perf.actions = {}
        for action in actions:
            action_type = action.get("action_type", "")
            value = cls._parse_int(action.get("value", 0))

            perf.actions[action_type] = value

            # 映射到标准字段
            if action_type in cls.ACTION_MAP:
                target_field = cls.ACTION_MAP[action_type]
                setattr(perf, target_field, value)

    @classmethod
    def _map_action_values(cls, perf: MetaPerformance, action_values: list[dict[str, Any]]) -> None:
        """映射 action_values (收入数据)."""
        perf.action_values = {}
        for av in action_values:
            action_type = av.get("action_type", "")
            value = cls._parse_float(av.get("value", 0.0))
            perf.action_values[action_type] = value

            # 购买收入 → revenue
            if action_type in ("purchase", "omni_purchase"):
                perf.revenue += value

    @classmethod
    def _map_cost_per_action(cls, perf: MetaPerformance, cost_per_action: list[dict[str, Any]]) -> None:
        """映射 cost_per_action_type."""
        perf.cost_per_action_type = {}
        for cpa_entry in cost_per_action:
            action_type = cpa_entry.get("action_type", "")
            value = cls._parse_float(cpa_entry.get("value", 0.0))
            perf.cost_per_action_type[action_type] = value

            # 映射到标准字段
            if action_type == "mobile_app_install":
                perf.cpi = value
            elif action_type in ("purchase", "omni_purchase"):
                perf.cpa = value

    @classmethod
    def _compute_derived_metrics(cls, perf: MetaPerformance) -> None:
        """计算派生指标."""
        # CTR
        if perf.impressions > 0 and perf.clicks == 0:
            perf.ctr = 0.0
        elif perf.impressions > 0 and perf.ctr == 0.0:
            perf.ctr = perf.clicks / perf.impressions

        # CPM
        if perf.impressions > 0 and perf.cpm == 0.0:
            perf.cpm = (perf.spend / perf.impressions) * 1000

        # CPC
        if perf.clicks > 0 and perf.cpc == 0.0:
            perf.cpc = perf.spend / perf.clicks

        # CPI
        if perf.installs > 0 and perf.cpi == 0.0:
            perf.cpi = perf.spend / perf.installs

        # CPA
        if perf.purchases > 0 and perf.cpa == 0.0:
            perf.cpa = perf.spend / perf.purchases

        # ROAS
        if perf.spend > 0 and perf.revenue > 0 and perf.roas == 0.0:
            perf.roas = perf.revenue / perf.spend

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _parse_numeric(value: Any) -> float | int:
        """解析数值."""
        if isinstance(value, str):
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except (ValueError, TypeError):
                return 0
        return value

    @staticmethod
    def _parse_float(value: Any) -> float:
        """解析浮点数."""
        if isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    @staticmethod
    def _parse_int(value: Any) -> int:
        """解析整数."""
        if isinstance(value, str):
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        if isinstance(value, (int, float)):
            return int(value)
        return 0