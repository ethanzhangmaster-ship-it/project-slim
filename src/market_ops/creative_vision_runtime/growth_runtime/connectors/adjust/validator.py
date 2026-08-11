"""E13.1.3 Adjust Validator — Adjust 数据质量校验."""

from __future__ import annotations

from typing import Any

from .models import (
    AdjustEventType,
    AdjustUserEvent,
    AttributionRecord,
    RetentionSnapshot,
    UserValueSnapshot,
)


class ValidationResult:
    """校验结果."""

    def __init__(self):
        self.is_valid: bool = True
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def add_error(self, message: str) -> None:
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


class AdjustEventValidator:
    """AdjustUserEvent 校验器.

    校验规则:
      - event_id 不能为空
      - event_name 必须是已知类型
      - revenue >= 0
      - timestamp 必须存在
      - 收入事件必须 revenue > 0
    """

    MAX_REVENUE = 100000.0

    @classmethod
    def validate(cls, event: AdjustUserEvent) -> ValidationResult:
        result = ValidationResult()

        # event_id 校验
        if not event.event_id:
            result.add_error("event_id is required")

        # event_name 校验
        if event.event_name not in AdjustEventType:
            result.add_error(f"unknown event_name: {event.event_name}")

        # timestamp 校验
        if not event.timestamp:
            result.add_error("timestamp is required")

        # revenue 不能为负
        if event.revenue < 0:
            result.add_error(f"revenue cannot be negative: {event.revenue}")

        # revenue 异常高
        if event.revenue > cls.MAX_REVENUE:
            result.add_warning(f"revenue unusually high: {event.revenue}")

        # 收入类型事件必须有收入
        revenue_types = {AdjustEventType.PURCHASE, AdjustEventType.AD_REVENUE, AdjustEventType.SUBSCRIPTION}
        if event.event_name in revenue_types and event.revenue <= 0:
            result.add_warning(f"revenue event ({event.event_name.value}) has revenue=0")

        # user_id 建议存在
        if not event.user_id:
            result.add_warning("user_id is empty")

        return result

    @classmethod
    def validate_batch(cls, events: list[AdjustUserEvent]) -> list[ValidationResult]:
        return [cls.validate(e) for e in events]

    @classmethod
    def filter_valid(cls, events: list[AdjustUserEvent]) -> list[AdjustUserEvent]:
        """过滤有效事件."""
        return [e for e in events if cls.validate(e).is_valid]


class AttributionValidator:
    """AttributionRecord 校验器.

    校验规则:
      - user_id 不能为空
      - network 必须是已知网络
      - install_time 必须存在
      - 付费归因必须有 campaign_id
    """

    @classmethod
    def validate(cls, record: AttributionRecord) -> ValidationResult:
        result = ValidationResult()

        if not record.user_id:
            result.add_error("user_id is required")

        if not record.install_time:
            result.add_error("install_time is required")

        if record.is_paid and not record.campaign_id:
            result.add_warning("paid attribution without campaign_id")

        if not record.network:
            result.add_warning("network is not set")

        return result

    @classmethod
    def validate_batch(
        cls, records: list[AttributionRecord],
    ) -> list[ValidationResult]:
        return [cls.validate(r) for r in records]

    @classmethod
    def filter_valid(
        cls, records: list[AttributionRecord],
    ) -> list[AttributionRecord]:
        """过滤有效归因记录."""
        return [r for r in records if cls.validate(r).is_valid]


class RetentionValidator:
    """RetentionSnapshot 校验器.

    校验规则:
      - product_id 不能为空
      - cohort_date 必须存在
      - cohort_size > 0
      - 所有留存率 0-1 之间
      - 留存率递减 (d1 >= d3 >= d7 >= d14 >= d30)
    """

    @classmethod
    def validate(cls, snapshot: RetentionSnapshot) -> ValidationResult:
        result = ValidationResult()

        if not snapshot.product_id:
            result.add_error("product_id is required")

        if not snapshot.cohort_date:
            result.add_error("cohort_date is required")

        if snapshot.cohort_size <= 0:
            result.add_error(f"cohort_size must be > 0: {snapshot.cohort_size}")

        rates = [
            ("d1", snapshot.d1),
            ("d3", snapshot.d3),
            ("d7", snapshot.d7),
            ("d14", snapshot.d14),
            ("d30", snapshot.d30),
            ("d60", snapshot.d60),
            ("d90", snapshot.d90),
        ]

        for name, rate in rates:
            if rate < 0 or rate > 1.0:
                result.add_error(f"{name} retention out of range [0,1]: {rate}")

        # 递减检查 (仅警告)
        prev = 1.0
        for name, rate in rates:
            if rate > prev:
                result.add_warning(f"{name} retention ({rate}) > previous ({prev})")
            prev = rate if rate > 0 else prev

        return result

    @classmethod
    def validate_or_none(
        cls, snapshot: RetentionSnapshot | None,
    ) -> ValidationResult:
        if snapshot is None:
            result = ValidationResult()
            result.add_warning("retention snapshot is None")
            return result
        return cls.validate(snapshot)


class UserValueValidator:
    """UserValueSnapshot 校验器.

    校验规则:
      - product_id 不能为空
      - date 必须存在
      - total_users >= 0
      - total_revenue >= 0
      - paying_users <= total_users
      - arpu/arppu 合理性
      - paying_rate 0-1 之间
    """

    MAX_ARPU = 1000.0
    MAX_ARPPU = 10000.0

    @classmethod
    def validate(cls, snapshot: UserValueSnapshot) -> ValidationResult:
        result = ValidationResult()

        if not snapshot.product_id:
            result.add_error("product_id is required")

        if not snapshot.date:
            result.add_error("date is required")

        if snapshot.total_users < 0:
            result.add_error(f"total_users cannot be negative: {snapshot.total_users}")

        if snapshot.total_revenue < 0:
            result.add_error(f"total_revenue cannot be negative: {snapshot.total_revenue}")

        if snapshot.paying_users > snapshot.total_users:
            result.add_error(
                f"paying_users ({snapshot.paying_users}) > total_users ({snapshot.total_users})"
            )

        if snapshot.paying_rate < 0 or snapshot.paying_rate > 1.0:
            result.add_error(f"paying_rate out of range [0,1]: {snapshot.paying_rate}")

        if snapshot.arpu < 0:
            result.add_error(f"arpu cannot be negative: {snapshot.arpu}")

        if snapshot.arppu < 0:
            result.add_error(f"arppu cannot be negative: {snapshot.arppu}")

        if snapshot.arpu > cls.MAX_ARPU:
            result.add_warning(f"arpu unusually high: {snapshot.arpu}")

        if snapshot.arppu > cls.MAX_ARPPU:
            result.add_warning(f"arppu unusually high: {snapshot.arppu}")

        return result

    @classmethod
    def validate_or_none(
        cls, snapshot: UserValueSnapshot | None,
    ) -> ValidationResult:
        if snapshot is None:
            result = ValidationResult()
            result.add_error("snapshot is None")
            return result
        return cls.validate(snapshot)


class APIResponseValidator:
    """Adjust API 响应校验器."""

    @classmethod
    def validate_raw_response(
        cls, raw_response: dict[str, Any],
    ) -> ValidationResult:
        """校验 Adjust API 原始响应."""
        result = ValidationResult()

        if not raw_response:
            result.add_error("response is empty")
            return result

        # 检查错误字段
        error = raw_response.get("error", raw_response.get("errors", ""))
        if error:
            result.add_error(f"API error: {error}")

        # 检查数据字段
        data = raw_response.get("data", raw_response.get("results", raw_response.get("events", [])))
        if not isinstance(data, list):
            result.add_warning("data field is not a list")

        return result

    @classmethod
    def validate_event_list(
        cls, events: list[dict[str, Any]],
    ) -> ValidationResult:
        """校验事件列表."""
        result = ValidationResult()

        if not events:
            result.add_warning("event list is empty")
            return result

        if not isinstance(events, list):
            result.add_error("events is not a list")
            return result

        # 抽样校验前 10 条
        for i, event in enumerate(events[:10]):
            if not isinstance(event, dict):
                result.add_error(f"event[{i}] is not a dict")
                continue
            if not event.get("event_name") and not event.get("event"):
                result.add_warning(f"event[{i}] missing event_name")

        return result