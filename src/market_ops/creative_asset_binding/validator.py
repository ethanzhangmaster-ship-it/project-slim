"""E11 Phase 3 — Asset Binding Validator。

验证绑定结果质量：
  1. 整体匹配率
  2. 按素材类型匹配率（视频/图片）
  3. 按匹配方法分布
  4. 低置信度匹配告警
  5. 缺失素材告警
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import AssetBindingResult, BindingMethod, AssetSourceType
from .asset_binding_engine import AssetBindingReport


@dataclass
class AssetBindingQualityReport:
    """绑定质量报告。"""

    total_entities: int = 0
    total_matched: int = 0
    total_missing: int = 0
    overall_match_rate: float = 0.0

    # 按类型
    video_match_rate: float = 0.0
    image_match_rate: float = 0.0

    # 按方法
    exact_id_count: int = 0
    filename_count: int = 0
    visual_hash_count: int = 0
    unknown_count: int = 0

    # 质量
    high_confidence_count: int = 0
    low_confidence_count: int = 0
    low_confidence_ids: list[str] = field(default_factory=list)
    missing_ids: list[str] = field(default_factory=list)

    # 告警
    warnings: list[str] = field(default_factory=list)
    critical: list[str] = field(default_factory=list)

    def to_summary(self) -> str:
        lines = [
            "=" * 60,
            "  Asset Binding Quality Report",
            "=" * 60,
            "",
            f"  Total Entities:    {self.total_entities}",
            f"  Matched:           {self.total_matched}",
            f"  Missing:           {self.total_missing}",
            f"  Overall Rate:      {self.overall_match_rate:.1%}",
            "",
            "  --- Match Rate by Type ---",
            f"  Video:             {self.video_match_rate:.1%}",
            f"  Image:             {self.image_match_rate:.1%}",
            "",
            "  --- By Method ---",
            f"  Exact ID:          {self.exact_id_count}",
            f"  Filename:          {self.filename_count}",
            f"  Visual Hash:       {self.visual_hash_count}",
            f"  Unknown:           {self.unknown_count}",
            "",
            "  --- Confidence ---",
            f"  High Confidence:   {self.high_confidence_count}",
            f"  Low Confidence:    {self.low_confidence_count}",
        ]

        if self.low_confidence_ids:
            lines.append(f"\n  Low Confidence IDs ({len(self.low_confidence_ids)}):")
            for cid in self.low_confidence_ids[:5]:
                lines.append(f"    - {cid}")

        if self.missing_ids:
            lines.append(f"\n  Missing IDs ({len(self.missing_ids)}):")
            for cid in self.missing_ids[:5]:
                lines.append(f"    - {cid}")

        if self.warnings:
            lines.append(f"\n  Warnings ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"    - {w}")

        if self.critical:
            lines.append(f"\n  CRITICAL ({len(self.critical)}):")
            for c in self.critical[:5]:
                lines.append(f"    - {c}")

        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "total_matched": self.total_matched,
            "total_missing": self.total_missing,
            "overall_match_rate": self.overall_match_rate,
            "video_match_rate": self.video_match_rate,
            "image_match_rate": self.image_match_rate,
            "exact_id_count": self.exact_id_count,
            "filename_count": self.filename_count,
            "visual_hash_count": self.visual_hash_count,
            "unknown_count": self.unknown_count,
            "high_confidence_count": self.high_confidence_count,
            "low_confidence_count": self.low_confidence_count,
            "low_confidence_ids": self.low_confidence_ids,
            "missing_ids": self.missing_ids,
            "warnings": self.warnings,
            "critical": self.critical,
        }


class AssetBindingValidator:
    """绑定质量验证器。

    Usage:
        validator = AssetBindingValidator()
        quality = validator.validate(report)
        print(quality.to_summary())
    """

    # 质量阈值
    MIN_MATCH_RATE = 0.80           # 最低整体匹配率
    MIN_EXACT_ID_RATE = 0.50        # 最低精确 ID 匹配占比
    MAX_LOW_CONFIDENCE_RATE = 0.10  # 最高低置信度占比

    def validate(self, report: AssetBindingReport) -> AssetBindingQualityReport:
        """验证绑定质量。"""
        quality = AssetBindingQualityReport(
            total_entities=report.total_entities,
            total_matched=report.total_matched,
            total_missing=report.total_missing,
            overall_match_rate=report.overall_match_rate,
            video_match_rate=report.video_match_rate,
            image_match_rate=report.image_match_rate,
        )

        # 按方法统计
        quality.exact_id_count = report.by_method.get(BindingMethod.EXACT_ID.value, 0)
        quality.filename_count = report.by_method.get(BindingMethod.FILENAME.value, 0)
        quality.visual_hash_count = report.by_method.get(BindingMethod.VISUAL_HASH.value, 0)
        quality.unknown_count = report.by_method.get(BindingMethod.UNKNOWN.value, 0)

        # 按置信度统计
        for r in report.results:
            if r.is_high_confidence:
                quality.high_confidence_count += 1
            elif r.is_low_confidence:
                quality.low_confidence_count += 1
                quality.low_confidence_ids.append(r.creative_asset_id)

        # 缺失 ID
        quality.missing_ids = [
            r.creative_asset_id for r in report.results if not r.matched
        ]

        # 质量检查
        self._check_overall_match_rate(quality)
        self._check_exact_id_rate(quality)
        self._check_low_confidence_rate(quality)
        self._check_video_match_rate(quality)
        self._check_image_match_rate(quality)
        self._check_missing_count(quality)

        return quality

    def _check_overall_match_rate(self, q: AssetBindingQualityReport) -> None:
        if q.total_entities > 0 and q.overall_match_rate < self.MIN_MATCH_RATE:
            q.critical.append(
                f"Overall match rate ({q.overall_match_rate:.1%}) below minimum ({self.MIN_MATCH_RATE:.0%})"
            )

    def _check_exact_id_rate(self, q: AssetBindingQualityReport) -> None:
        if q.total_matched > 0:
            exact_rate = q.exact_id_count / q.total_matched
            if exact_rate < self.MIN_EXACT_ID_RATE:
                q.warnings.append(
                    f"Exact ID match rate ({exact_rate:.1%}) below {self.MIN_EXACT_ID_RATE:.0%}, "
                    f"too many fallback matches"
                )

    def _check_low_confidence_rate(self, q: AssetBindingQualityReport) -> None:
        if q.total_matched > 0:
            low_rate = q.low_confidence_count / q.total_matched
            if low_rate > self.MAX_LOW_CONFIDENCE_RATE:
                q.warnings.append(
                    f"Low confidence rate ({low_rate:.1%}) exceeds {self.MAX_LOW_CONFIDENCE_RATE:.0%}"
                )

    def _check_video_match_rate(self, q: AssetBindingQualityReport) -> None:
        if q.video_match_rate < self.MIN_MATCH_RATE and q.video_match_rate > 0:
            q.warnings.append(
                f"Video match rate ({q.video_match_rate:.1%}) below {self.MIN_MATCH_RATE:.0%}"
            )

    def _check_image_match_rate(self, q: AssetBindingQualityReport) -> None:
        if q.image_match_rate < self.MIN_MATCH_RATE and q.image_match_rate > 0:
            q.warnings.append(
                f"Image match rate ({q.image_match_rate:.1%}) below {self.MIN_MATCH_RATE:.0%}"
            )

    def _check_missing_count(self, q: AssetBindingQualityReport) -> None:
        if q.total_missing > 0 and q.total_entities > 0:
            missing_rate = q.total_missing / q.total_entities
            if missing_rate > 0.2:
                q.critical.append(
                    f"Too many missing assets: {q.total_missing}/{q.total_entities} ({missing_rate:.1%})"
                )

    def __repr__(self) -> str:
        return "AssetBindingValidator()"