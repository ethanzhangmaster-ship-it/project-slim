"""E13.2.1 Data Ingestion Pipeline — 统一数据接入管道.

核心职责: 将 Meta Ads / Adjust / MAX 三个 Connector 的原始数据
统一接入到 Reality Data Pipeline，进行清洗、标准化和去重。

数据流:
  Connectors → RawEvent → Normalizer → NormalizedEvent → (下游: Attribution)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .models import (
    AttributionType,
    EventStatus,
    NormalizedEvent,
    PipelineConfig,
    PipelineStats,
    RawEvent,
)


# ═══════════════════════════════════════════════════════════════
# Event Validator
# ═══════════════════════════════════════════════════════════════


class EventValidator:
    """事件验证器 — 检查原始事件的有效性."""

    REQUIRED_FIELDS = ["source", "event_type", "product_id", "date"]
    VALID_SOURCES = {"meta_ads", "adjust", "max", "google_ads", "firebase", "internal"}
    VALID_EVENT_TYPES = {
        "spend", "impression", "click", "install", "session",
        "revenue", "purchase", "ad_revenue", "retention",
        "attribution", "reattribution", "custom_event",
    }

    @classmethod
    def validate_raw_event(cls, event: RawEvent) -> list[str]:
        """验证原始事件，返回错误列表."""
        errors: list[str] = []

        if not event.source:
            errors.append("Missing required field: source")
        elif event.source not in cls.VALID_SOURCES:
            errors.append(f"Invalid source: {event.source}")

        if not event.event_type:
            errors.append("Missing required field: event_type")
        elif event.event_type not in cls.VALID_EVENT_TYPES:
            errors.append(f"Invalid event_type: {event.event_type}")

        if not event.product_id:
            errors.append("Missing required field: product_id")

        if not event.date:
            errors.append("Missing required field: date")

        if not event.payload:
            errors.append("Empty payload")

        return errors

    @classmethod
    def validate_normalized_event(cls, event: NormalizedEvent) -> list[str]:
        """验证标准化事件."""
        errors: list[str] = []

        if not event.source:
            errors.append("Missing source")
        if not event.event_type:
            errors.append("Missing event_type")
        if not event.product_id:
            errors.append("Missing product_id")
        if not event.date:
            errors.append("Missing date")

        return errors


# ═══════════════════════════════════════════════════════════════
# Event Normalizer
# ═══════════════════════════════════════════════════════════════


class EventNormalizer:
    """事件标准化器 — 将不同来源的原始事件转换为统一格式.

    支持 Meta Ads, Adjust, MAX 三种来源的标准化.
    """

    # 字段映射: source → (payload_field, metric_name)
    METRIC_MAPPINGS: dict[str, dict[str, str]] = {
        "meta_ads": {
            "spend": "spend",
            "impressions": "impressions",
            "clicks": "clicks",
            "ctr": "ctr",
            "cpm": "cpm",
            "cpc": "cpc",
            "installs": "installs",
            "cpi": "cpi",
            "revenue": "revenue",
            "roas": "roas",
        },
        "adjust": {
            "revenue": "revenue",
            "installs": "installs",
            "sessions": "sessions",
            "d1_retention": "d1_retention",
            "d7_retention": "d7_retention",
            "d30_retention": "d30_retention",
            "payer_rate": "payer_rate",
            "arpu": "arpu",
            "ltv": "ltv",
            "iap_revenue": "iap_revenue",
            "ad_revenue": "ad_revenue",
        },
        "max": {
            "ad_revenue": "ad_revenue",
            "impressions": "impressions",
            "ecpm": "ecpm",
            "fill_rate": "fill_rate",
            "show_rate": "show_rate",
            "requests": "requests",
            "fills": "fills",
            "dau": "dau",
            "arpdau": "arpdau",
            "clicks": "clicks",
        },
    }

    # 维度映射
    DIMENSION_MAPPINGS: dict[str, list[str]] = {
        "meta_ads": ["campaign_id", "adset_id", "creative_id", "campaign_name", "adset_name"],
        "adjust": ["campaign_id", "adgroup_id", "creative_id", "network", "country", "user_id"],
        "max": ["ad_unit_id", "network", "country", "ad_format", "placement"],
    }

    @classmethod
    def normalize(cls, raw_event: RawEvent) -> NormalizedEvent:
        """将 RawEvent 标准化为 NormalizedEvent."""
        source = raw_event.source
        payload = raw_event.payload

        # 提取标准化 metrics
        metrics: dict[str, float] = {}
        source_mappings = cls.METRIC_MAPPINGS.get(source, {})
        for metric_name, payload_field in source_mappings.items():
            raw_value = payload.get(payload_field, 0)
            try:
                metrics[metric_name] = float(raw_value)
            except (ValueError, TypeError):
                metrics[metric_name] = 0.0

        # 提取维度
        dimensions: dict[str, str] = {}
        dim_fields = cls.DIMENSION_MAPPINGS.get(source, [])
        for dim_field in dim_fields:
            value = payload.get(dim_field, "")
            if value:
                dimensions[dim_field] = str(value)

        # 确定事件类型
        event_type = raw_event.event_type
        if source == "meta_ads" and event_type == "spend":
            event_type = "acquisition"
        elif source == "adjust":
            if event_type == "purchase":
                event_type = "iap_revenue"
            elif event_type == "ad_revenue":
                event_type = "iaa_revenue"
        elif source == "max":
            if event_type == "impression":
                event_type = "ad_impression"
            elif event_type == "revenue":
                event_type = "iaa_revenue"

        return NormalizedEvent(
            event_id=str(uuid.uuid4()),
            source_event_id=raw_event.event_id,
            source=source,
            event_type=event_type,
            product_id=raw_event.product_id,
            date=raw_event.date,
            metrics=metrics,
            campaign_id=dimensions.get("campaign_id", ""),
            adset_id=dimensions.get("adset_id", dimensions.get("adgroup_id", "")),
            creative_id=dimensions.get("creative_id", ""),
            user_id=dimensions.get("user_id", ""),
            network=dimensions.get("network", ""),
            country=dimensions.get("country", ""),
            platform=dimensions.get("platform", ""),
            status=EventStatus.NORMALIZED,
            confidence=1.0,
            trace_id=raw_event.trace_id,
            batch_id=raw_event.batch_id,
        )

    @classmethod
    def normalize_batch(cls, raw_events: list[RawEvent]) -> list[NormalizedEvent]:
        """批量标准化."""
        return [cls.normalize(e) for e in raw_events]


# ═══════════════════════════════════════════════════════════════
# Event Deduplicator
# ═══════════════════════════════════════════════════════════════


class EventDeduplicator:
    """事件去重器 — 基于 source + event_id 去重."""

    def __init__(self):
        self._seen_ids: set[str] = set()

    def is_duplicate(self, event: RawEvent) -> bool:
        """检查是否重复事件."""
        key = f"{event.source}:{event.event_id}"
        if key in self._seen_ids:
            return True
        self._seen_ids.add(key)
        return False

    def deduplicate(self, events: list[RawEvent]) -> tuple[list[RawEvent], int]:
        """去重，返回 (去重后事件, 重复数)."""
        unique: list[RawEvent] = []
        duplicates = 0
        for event in events:
            if self.is_duplicate(event):
                duplicates += 1
            else:
                unique.append(event)
        return unique, duplicates

    def reset(self) -> None:
        self._seen_ids.clear()

    @property
    def seen_count(self) -> int:
        return len(self._seen_ids)


# ═══════════════════════════════════════════════════════════════
# Data Ingestion Pipeline
# ═══════════════════════════════════════════════════════════════


class DataIngestionPipeline:
    """E13.2.1 统一数据接入管道.

    职责:
      1. 从 Connector Registry 接收原始事件
      2. 验证事件有效性
      3. 去重
      4. 标准化为 NormalizedEvent
      5. 输出到下游 (Attribution / Feature Store)

    数据流:
      RawEvent[] → validate → deduplicate → normalize → NormalizedEvent[]
    """

    def __init__(self, config: PipelineConfig | None = None):
        self._config = config or PipelineConfig()
        self._validator = EventValidator()
        self._normalizer = EventNormalizer()
        self._deduplicator = EventDeduplicator()
        self._stats = PipelineStats(pipeline_name=self._config.pipeline_name)

        # Internal buffers
        self._raw_events: list[RawEvent] = []
        self._normalized_events: list[NormalizedEvent] = []
        self._error_events: list[RawEvent] = []

    # ── Properties ────────────────────────────────────────────

    @property
    def config(self) -> PipelineConfig:
        return self._config

    @property
    def stats(self) -> PipelineStats:
        return self._stats

    @property
    def raw_count(self) -> int:
        return len(self._raw_events)

    @property
    def normalized_count(self) -> int:
        return len(self._normalized_events)

    @property
    def error_count(self) -> int:
        return len(self._error_events)

    # ── Ingestion ─────────────────────────────────────────────

    def ingest(self, events: list[RawEvent], batch_id: str = "") -> int:
        """接入原始事件.

        Returns:
            int: 成功接入的事件数
        """
        if not events:
            return 0

        batch_id = batch_id or str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)

        # 1. 分配 batch_id
        for event in events:
            if not event.batch_id:
                event.batch_id = batch_id
            event.status = EventStatus.RAW
            event.ingested_at = datetime.now(timezone.utc).isoformat()

        self._raw_events.extend(events)
        self._stats.total_raw_events += len(events)

        # 2. 验证
        valid_events: list[RawEvent] = []
        for event in events:
            errors = self._validator.validate_raw_event(event)
            if errors:
                event.status = EventStatus.ERROR
                self._error_events.append(event)
                self._stats.total_errors += 1
            else:
                valid_events.append(event)

        # 3. 去重
        if self._config.drop_duplicates:
            unique_events, dup_count = self._deduplicator.deduplicate(valid_events)
            self._stats.total_dropped += dup_count
            for e in valid_events:
                if e not in unique_events:
                    e.status = EventStatus.DROPPED
        else:
            unique_events = valid_events

        # 4. 标准化
        normalized = self._normalizer.normalize_batch(unique_events)

        # 5. 验证标准化结果
        final_events: list[NormalizedEvent] = []
        for event in normalized:
            validation_errors = self._validator.validate_normalized_event(event)
            if validation_errors:
                event.validation_errors = validation_errors
                event.status = EventStatus.ERROR
                self._stats.total_errors += 1
            else:
                final_events.append(event)

        self._normalized_events.extend(final_events)
        self._stats.total_normalized += len(final_events)

        # 更新统计
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        self._stats.last_run_at = datetime.now(timezone.utc).isoformat()
        self._stats.last_duration_seconds = duration
        self._stats.total_runs += 1

        return len(final_events)

    def ingest_from_growth_events(
        self, growth_events: list[Any], source: str = "",
    ) -> int:
        """从 E13.1.1 GrowthDataEvent 列表接入数据."""
        raw_events: list[RawEvent] = []

        for ge in growth_events:
            raw_event = RawEvent(
                source=source or ge.source.value if hasattr(ge.source, 'value') else str(ge.source),
                event_type=ge.event_type.value if hasattr(ge.event_type, 'value') else str(ge.event_type),
                product_id=ge.product_id,
                date=ge.date,
                payload={
                    **ge.metrics,
                    "campaign_id": ge.campaign_id,
                    "adset_id": ge.adset_id,
                    "creative_id": ge.creative_id,
                },
            )
            raw_events.append(raw_event)

        return self.ingest(raw_events)

    # ── Output ────────────────────────────────────────────────

    def get_normalized_events(
        self, source: str = "", event_type: str = "", product_id: str = "",
        date: str = "",
    ) -> list[NormalizedEvent]:
        """获取标准化事件，支持过滤."""
        result = list(self._normalized_events)

        if source:
            result = [e for e in result if e.source == source]
        if event_type:
            result = [e for e in result if e.event_type == event_type]
        if product_id:
            result = [e for e in result if e.product_id == product_id]
        if date:
            result = [e for e in result if e.date == date]

        return result

    def get_events_by_creative(self, creative_id: str) -> list[NormalizedEvent]:
        """按 creative_id 获取事件."""
        return [e for e in self._normalized_events if e.creative_id == creative_id]

    def get_events_by_campaign(self, campaign_id: str) -> list[NormalizedEvent]:
        """按 campaign_id 获取事件."""
        return [e for e in self._normalized_events if e.campaign_id == campaign_id]

    def get_events_by_source(self, source: str) -> list[NormalizedEvent]:
        """按 source 获取事件."""
        return [e for e in self._normalized_events if e.source == source]

    def get_errors(self) -> list[RawEvent]:
        """获取所有错误事件."""
        return list(self._error_events)

    # ── Aggregation ───────────────────────────────────────────

    def aggregate_by_source(self) -> dict[str, dict[str, float]]:
        """按 source 聚合指标."""
        result: dict[str, dict[str, float]] = {}

        for event in self._normalized_events:
            source = event.source
            if source not in result:
                result[source] = {"event_count": 0, "total_metric_sum": 0.0}

            result[source]["event_count"] += 1
            result[source]["total_metric_sum"] += sum(event.metrics.values())

        return result

    def aggregate_by_creative(self) -> dict[str, dict[str, Any]]:
        """按 creative_id 聚合指标."""
        result: dict[str, dict[str, Any]] = {}

        for event in self._normalized_events:
            if not event.creative_id:
                continue

            cid = event.creative_id
            if cid not in result:
                result[cid] = {
                    "event_count": 0,
                    "sources": set(),
                    "metrics_sum": {},
                }

            result[cid]["event_count"] += 1
            result[cid]["sources"].add(event.source)

            for key, value in event.metrics.items():
                result[cid]["metrics_sum"][key] = (
                    result[cid]["metrics_sum"].get(key, 0.0) + value
                )

        # Convert sets to lists
        for cid in result:
            result[cid]["sources"] = list(result[cid]["sources"])

        return result

    def aggregate_by_date(self) -> dict[str, int]:
        """按日期聚合事件数."""
        result: dict[str, int] = {}
        for event in self._normalized_events:
            result[event.date] = result.get(event.date, 0) + 1
        return result

    # ── Lifecycle ─────────────────────────────────────────────

    def flush(self) -> None:
        """清空所有缓冲."""
        self._raw_events.clear()
        self._normalized_events.clear()
        self._error_events.clear()
        self._deduplicator.reset()

    def reset(self) -> None:
        """重置 Pipeline."""
        self.flush()
        self._stats = PipelineStats(pipeline_name=self._config.pipeline_name)

    def get_summary(self) -> dict[str, Any]:
        """获取 Pipeline 摘要."""
        return {
            "pipeline_name": self._config.pipeline_name,
            "stats": self._stats.to_dict(),
            "raw_count": self.raw_count,
            "normalized_count": self.normalized_count,
            "error_count": self.error_count,
            "deduplicator_seen": self._deduplicator.seen_count,
            "aggregation": {
                "by_source": self.aggregate_by_source(),
                "by_date": self.aggregate_by_date(),
            },
        }