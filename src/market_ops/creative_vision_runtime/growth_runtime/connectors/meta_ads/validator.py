"""E13.1.2 Meta Ads Validator — Meta 数据质量校验."""

from __future__ import annotations

from typing import Any

from .exceptions import MetaValidationError
from .models import (
    CreativeFatigueSignal,
    MetaAccount,
    MetaCampaign,
    MetaCreative,
    MetaPerformance,
    ScalingOpportunity,
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


class MetaPerformanceValidator:
    """MetaPerformance 数据校验器.

    校验规则:
      - spend >= 0
      - 0 <= ROAS <= 100
      - 0 <= CTR <= 1
      - 日期必须存在
      - impressions >= 0
      - clicks >= 0
      - installs >= 0
    """

    MAX_ROAS = 100.0
    MAX_CTR = 1.0

    @classmethod
    def validate(cls, perf: MetaPerformance) -> ValidationResult:
        result = ValidationResult()

        # 日期校验
        if not perf.date_start:
            result.add_error("date_start is required")
        if not perf.date_stop:
            result.add_error("date_stop is required")

        # spend 不能为负
        if perf.spend < 0:
            result.add_error(f"spend cannot be negative: {perf.spend}")

        # ROAS 范围 0-100
        if perf.roas < 0:
            result.add_error(f"roas cannot be negative: {perf.roas}")
        elif perf.roas > cls.MAX_ROAS:
            result.add_warning(f"roas unusually high: {perf.roas}")

        # CTR 范围 0-1
        if perf.ctr < 0:
            result.add_error(f"ctr cannot be negative: {perf.ctr}")
        elif perf.ctr > cls.MAX_CTR:
            result.add_warning(f"ctr unusually high: {perf.ctr}")

        # impressions >= 0
        if perf.impressions < 0:
            result.add_error(f"impressions cannot be negative: {perf.impressions}")

        # clicks >= 0
        if perf.clicks < 0:
            result.add_error(f"clicks cannot be negative: {perf.clicks}")

        # clicks <= impressions (logically)
        if perf.clicks > perf.impressions > 0:
            result.add_warning(f"clicks ({perf.clicks}) > impressions ({perf.impressions})")

        # installs >= 0
        if perf.installs < 0:
            result.add_error(f"installs cannot be negative: {perf.installs}")

        # installs <= clicks (logically)
        if perf.installs > perf.clicks > 0:
            result.add_warning(f"installs ({perf.installs}) > clicks ({perf.clicks})")

        # frequency >= 0
        if perf.frequency < 0:
            result.add_error(f"frequency cannot be negative: {perf.frequency}")

        # CPM sanity
        if perf.cpm < 0:
            result.add_error(f"cpm cannot be negative: {perf.cpm}")

        # CPI sanity
        if perf.cpi < 0:
            result.add_error(f"cpi cannot be negative: {perf.cpi}")

        return result

    @classmethod
    def validate_batch(cls, performances: list[MetaPerformance]) -> list[ValidationResult]:
        return [cls.validate(p) for p in performances]

    @classmethod
    def validate_or_raise(cls, perf: MetaPerformance) -> None:
        result = cls.validate(perf)
        if not result.is_valid:
            raise MetaValidationError(
                f"Validation failed with {len(result.errors)} errors: {result.errors}"
            )


class MetaCampaignValidator:
    """MetaCampaign 数据校验器."""

    @classmethod
    def validate(cls, campaign: MetaCampaign) -> ValidationResult:
        result = ValidationResult()

        if not campaign.campaign_id:
            result.add_error("campaign_id is required")

        if not campaign.name:
            result.add_error("campaign name is required")

        if campaign.daily_budget < 0:
            result.add_error(f"daily_budget cannot be negative: {campaign.daily_budget}")

        if campaign.lifetime_budget < 0:
            result.add_error(f"lifetime_budget cannot be negative: {campaign.lifetime_budget}")

        return result


class MetaAccountValidator:
    """MetaAccount 数据校验器."""

    @classmethod
    def validate(cls, account: MetaAccount) -> ValidationResult:
        result = ValidationResult()

        if not account.account_id:
            result.add_error("account_id is required")

        if not account.name:
            result.add_error("account name is required")

        if account.balance < 0:
            result.add_warning(f"account balance is negative: {account.balance}")

        return result


class MetaCreativeValidator:
    """MetaCreative 数据校验器."""

    @classmethod
    def validate(cls, creative: MetaCreative) -> ValidationResult:
        result = ValidationResult()

        if not creative.creative_id:
            result.add_error("creative_id is required")

        if not creative.name:
            result.add_error("creative name is required")

        if not creative.image_url and not creative.video_url:
            result.add_warning("creative has no image_url or video_url")

        return result


class CreativeFatigueValidator:
    """CreativeFatigueSignal 校验器."""

    @classmethod
    def validate(cls, signal: CreativeFatigueSignal) -> ValidationResult:
        result = ValidationResult()

        if not signal.creative_id:
            result.add_error("creative_id is required")

        if signal.current_ctr < 0 or signal.current_ctr > 1:
            result.add_error(f"current_ctr out of range: {signal.current_ctr}")

        if signal.current_frequency < 0:
            result.add_error(f"current_frequency cannot be negative: {signal.current_frequency}")

        if signal.fatigue_score < 0:
            result.add_error(f"fatigue_score cannot be negative: {signal.fatigue_score}")

        valid_levels = {"low", "medium", "high", "critical"}
        if signal.fatigue_level not in valid_levels:
            result.add_error(f"invalid fatigue_level: {signal.fatigue_level}")

        return result


class ScalingOpportunityValidator:
    """ScalingOpportunity 校验器."""

    @classmethod
    def validate(cls, opportunity: ScalingOpportunity) -> ValidationResult:
        result = ValidationResult()

        if not opportunity.campaign_id:
            result.add_error("campaign_id is required")

        if opportunity.current_daily_budget < 0:
            result.add_error(f"current_daily_budget cannot be negative: {opportunity.current_daily_budget}")

        if opportunity.suggested_daily_budget < 0:
            result.add_error(f"suggested_daily_budget cannot be negative: {opportunity.suggested_daily_budget}")

        if opportunity.confidence < 0 or opportunity.confidence > 1:
            result.add_error(f"confidence out of range [0,1]: {opportunity.confidence}")

        return result