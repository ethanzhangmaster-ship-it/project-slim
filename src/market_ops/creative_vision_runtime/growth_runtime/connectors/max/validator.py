"""E13.1.4 MAX Validator — MAX 数据质量校验."""

from __future__ import annotations

from typing import Any

from .models import (
    MAXAdUnit,
    MAXPerformance,
    MAXRevenueEvent,
    MAXRevenueSnapshot,
    MAXWaterfallEntry,
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


class MAXRevenueEventValidator:
    """MAXRevenueEvent 校验器.

    校验规则:
      - event_id 不能为空
      - ad_unit_id 不能为空
      - revenue >= 0
      - timestamp 必须存在
      - date 必须存在
    """

    MAX_REVENUE = 1000.0

    @classmethod
    def validate(cls, event: MAXRevenueEvent) -> ValidationResult:
        result = ValidationResult()

        if not event.event_id:
            result.add_error("event_id is required")

        if not event.ad_unit_id:
            result.add_error("ad_unit_id is required")

        if event.revenue < 0:
            result.add_error(f"revenue cannot be negative: {event.revenue}")

        if event.revenue > cls.MAX_REVENUE:
            result.add_warning(f"revenue unusually high: {event.revenue}")

        if not event.timestamp:
            result.add_error("timestamp is required")

        if not event.date:
            result.add_warning("date is empty")

        return result

    @classmethod
    def validate_batch(cls, events: list[MAXRevenueEvent]) -> list[ValidationResult]:
        return [cls.validate(e) for e in events]

    @classmethod
    def filter_valid(cls, events: list[MAXRevenueEvent]) -> list[MAXRevenueEvent]:
        return [e for e in events if cls.validate(e).is_valid]


class MAXPerformanceValidator:
    """MAXPerformance 校验器.

    校验规则:
      - ad_unit_id 不能为空
      - date 必须存在
      - impressions >= 0
      - revenue >= 0
      - ecpm >= 0
      - 0 <= fill_rate <= 1
      - 0 <= show_rate <= 1
    """

    MAX_ECPM = 500.0

    @classmethod
    def validate(cls, perf: MAXPerformance) -> ValidationResult:
        result = ValidationResult()

        if not perf.ad_unit_id:
            result.add_error("ad_unit_id is required")

        if not perf.date:
            result.add_error("date is required")

        if perf.impressions < 0:
            result.add_error(f"impressions cannot be negative: {perf.impressions}")

        if perf.revenue < 0:
            result.add_error(f"revenue cannot be negative: {perf.revenue}")

        if perf.ecpm < 0:
            result.add_error(f"ecpm cannot be negative: {perf.ecpm}")

        if perf.ecpm > cls.MAX_ECPM:
            result.add_warning(f"ecpm unusually high: {perf.ecpm}")

        if perf.fill_rate < 0 or perf.fill_rate > 1.0:
            result.add_error(f"fill_rate out of range [0,1]: {perf.fill_rate}")

        if perf.show_rate < 0 or perf.show_rate > 1.0:
            result.add_error(f"show_rate out of range [0,1]: {perf.show_rate}")

        if perf.requests < 0:
            result.add_error(f"requests cannot be negative: {perf.requests}")

        if perf.fills > perf.requests > 0:
            result.add_warning(f"fills ({perf.fills}) > requests ({perf.requests})")

        if perf.impressions > perf.fills > 0:
            result.add_warning(f"impressions ({perf.impressions}) > fills ({perf.fills})")

        if perf.dau < 0:
            result.add_error(f"dau cannot be negative: {perf.dau}")

        if perf.arpdau < 0:
            result.add_error(f"arpdau cannot be negative: {perf.arpdau}")

        return result

    @classmethod
    def validate_batch(cls, performances: list[MAXPerformance]) -> list[ValidationResult]:
        return [cls.validate(p) for p in performances]

    @classmethod
    def filter_valid(cls, performances: list[MAXPerformance]) -> list[MAXPerformance]:
        return [p for p in performances if cls.validate(p).is_valid]


class MAXRevenueSnapshotValidator:
    """MAXRevenueSnapshot 校验器.

    校验规则:
      - product_id 不能为空
      - date 必须存在
      - total_revenue >= 0
      - total_impressions >= 0
      - ecpm >= 0
      - 0 <= fill_rate <= 1
      - dau >= 0
      - arpdau >= 0
    """

    @classmethod
    def validate(cls, snapshot: MAXRevenueSnapshot) -> ValidationResult:
        result = ValidationResult()

        if not snapshot.product_id:
            result.add_error("product_id is required")

        if not snapshot.date:
            result.add_error("date is required")

        if snapshot.total_revenue < 0:
            result.add_error(f"total_revenue cannot be negative: {snapshot.total_revenue}")

        if snapshot.total_impressions < 0:
            result.add_error(f"total_impressions cannot be negative: {snapshot.total_impressions}")

        if snapshot.ecpm < 0:
            result.add_error(f"ecpm cannot be negative: {snapshot.ecpm}")

        if snapshot.fill_rate < 0 or snapshot.fill_rate > 1.0:
            result.add_error(f"fill_rate out of range [0,1]: {snapshot.fill_rate}")

        if snapshot.dau < 0:
            result.add_error(f"dau cannot be negative: {snapshot.dau}")

        if snapshot.arpdau < 0:
            result.add_error(f"arpdau cannot be negative: {snapshot.arpdau}")

        return result

    @classmethod
    def validate_or_none(
        cls, snapshot: MAXRevenueSnapshot | None,
    ) -> ValidationResult:
        if snapshot is None:
            result = ValidationResult()
            result.add_error("snapshot is None")
            return result
        return cls.validate(snapshot)


class MAXWaterfallValidator:
    """MAXWaterfallEntry 校验器."""

    @classmethod
    def validate(cls, entry: MAXWaterfallEntry) -> ValidationResult:
        result = ValidationResult()

        if not entry.ad_unit_id:
            result.add_error("ad_unit_id is required")

        if entry.impressions < 0:
            result.add_error(f"impressions cannot be negative: {entry.impressions}")

        if entry.revenue < 0:
            result.add_error(f"revenue cannot be negative: {entry.revenue}")

        if entry.ecpm < 0:
            result.add_error(f"ecpm cannot be negative: {entry.ecpm}")

        if entry.is_bidding and entry.win_rate < 0:
            result.add_error(f"win_rate cannot be negative: {entry.win_rate}")

        return result

    @classmethod
    def filter_valid(cls, entries: list[MAXWaterfallEntry]) -> list[MAXWaterfallEntry]:
        return [e for e in entries if cls.validate(e).is_valid]


class MAXAdUnitValidator:
    """MAXAdUnit 校验器."""

    @classmethod
    def validate(cls, ad_unit: MAXAdUnit) -> ValidationResult:
        result = ValidationResult()

        if not ad_unit.ad_unit_id:
            result.add_error("ad_unit_id is required")

        if not ad_unit.name:
            result.add_error("name is required")

        if not ad_unit.app_id:
            result.add_warning("app_id is empty")

        return result