"""E11 Phase 1.6 — Facebook Data Quality Validator。

每天自动检查 Facebook 数据质量，确保后续 Adjust/Eagle/Lovart 接入数据可靠。

检查项：
  1. 数据完整率：creative_id、ad_name、spend 等关键字段覆盖率
  2. 素材类型分布：image/video 数量和占比
  3. 投放效果排行：Top 素材按 spend/CTR/installs

Usage:
    validator = DataQualityValidator(storage)
    report = validator.validate()
    print(report.to_summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import FacebookCreativeEntity, CreativeType
from .storage import CreativeStorage


@dataclass
class CompletenessReport:
    """字段完整率报告。"""

    total_entities: int = 0
    fields: dict[str, float] = field(default_factory=dict)  # field_name → coverage %
    details: dict[str, int] = field(default_factory=dict)    # field_name → missing count

    @property
    def overall_score(self) -> float:
        """整体完整率（所有字段平均值）。"""
        if not self.fields:
            return 0.0
        return round(sum(self.fields.values()) / len(self.fields), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "overall_score": self.overall_score,
            "fields": self.fields,
            "details": self.details,
        }


@dataclass
class TypeDistribution:
    """素材类型分布。"""

    total: int = 0
    image_count: int = 0
    video_count: int = 0
    unknown_count: int = 0

    @property
    def image_pct(self) -> float:
        return round(self.image_count / self.total * 100, 1) if self.total > 0 else 0.0

    @property
    def video_pct(self) -> float:
        return round(self.video_count / self.total * 100, 1) if self.total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "image": self.image_count,
            "image_pct": f"{self.image_pct}%",
            "video": self.video_count,
            "video_pct": f"{self.video_pct}%",
            "unknown": self.unknown_count,
        }


@dataclass
class TopPerformer:
    """Top 素材条目。"""

    creative_asset_id: str = ""
    ad_name: str = ""
    creative_type: str = ""
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "creative_asset_id": self.creative_asset_id,
            "ad_name": self.ad_name,
            "creative_type": self.creative_type,
        }


@dataclass
class TopSpender(TopPerformer):
    spend: float = 0.0
    installs: int = 0
    ctr: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "spend": f"${self.spend:,.2f}",
            "installs": self.installs,
            "ctr": f"{self.ctr:.1f}%",
        }


@dataclass
class TopCTR(TopPerformer):
    ctr: float = 0.0
    spend: float = 0.0
    impressions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "ctr": f"{self.ctr:.1f}%",
            "spend": f"${self.spend:,.2f}",
            "impressions": self.impressions,
        }


@dataclass
class QualityReport:
    """数据质量报告。"""

    generated_at: str = ""
    completeness: CompletenessReport = field(default_factory=CompletenessReport)
    type_distribution: TypeDistribution = field(default_factory=TypeDistribution)
    top_spenders: list[TopSpender] = field(default_factory=list)
    top_ctr: list[TopCTR] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_summary(self) -> str:
        """生成可读摘要。"""
        lines = [
            "=" * 60,
            "  Facebook Data Quality Report",
            f"  Generated: {self.generated_at}",
            "=" * 60,
            "",
            f"  Total Entities: {self.completeness.total_entities}",
            f"  Data Completeness: {self.completeness.overall_score:.1%}",
            "",
        ]

        # 字段完整率
        for field_name, coverage in self.completeness.fields.items():
            missing = self.completeness.details.get(field_name, 0)
            lines.append(f"    {field_name}: {coverage:.1%}  (missing: {missing})")

        # 类型分布
        td = self.type_distribution
        lines.extend([
            "",
            f"  Image: {td.image_count} ({td.image_pct}%)",
            f"  Video: {td.video_count} ({td.video_pct}%)",
        ])

        # Top Spenders
        if self.top_spenders:
            lines.extend(["", "  Top 5 by Spend:"])
            for t in self.top_spenders:
                lines.append(
                    f"    #{t.rank} {t.creative_asset_id} "
                    f"| Spend: ${t.spend:,.0f} "
                    f"| Installs: {t.installs} "
                    f"| CTR: {t.ctr:.1f}%"
                )

        # Top CTR
        if self.top_ctr:
            lines.extend(["", "  Top 5 by CTR:"])
            for t in self.top_ctr:
                lines.append(
                    f"    #{t.rank} {t.creative_asset_id} "
                    f"| CTR: {t.ctr:.1f}% "
                    f"| Impressions: {t.impressions:,}"
                )

        # Warnings
        if self.warnings:
            lines.extend(["", "  Warnings:"])
            for w in self.warnings:
                lines.append(f"    ! {w}")

        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "completeness": self.completeness.to_dict(),
            "type_distribution": self.type_distribution.to_dict(),
            "top_spenders": [t.to_dict() for t in self.top_spenders],
            "top_ctr": [t.to_dict() for t in self.top_ctr],
            "warnings": self.warnings,
        }


class DataQualityValidator:
    """Facebook 数据质量验证器。

    检查项：
      1. 数据完整率
      2. 素材类型统计
      3. 投放效果排行

    Usage:
        storage = CreativeStorage("data/creatives")
        validator = DataQualityValidator(storage)
        report = validator.validate()
        print(report.to_summary())
    """

    # 关键字段列表（必须检查完整率）
    CRITICAL_FIELDS = [
        "creative_id",
        "ad_name",
        "spend",
        "impressions",
        "clicks",
        "creative_type",
        "campaign_id",
        "adset_id",
    ]

    # 完整率告警阈值
    COMPLETENESS_WARN_THRESHOLD = 0.95  # 低于 95% 告警
    SAMPLE_SIZE_WARN = 10  # 样本量低于此值告警

    def __init__(self, storage: CreativeStorage) -> None:
        self._storage = storage

    def validate(self, top_n: int = 5) -> QualityReport:
        """执行完整数据质量检查。

        Args:
            top_n: Top N 数量

        Returns:
            QualityReport
        """
        entities = self._storage.list_all()
        report = QualityReport()
        report.generated_at = datetime.now().isoformat()

        if not entities:
            report.warnings.append("No entities found in storage")
            return report

        # 1. 数据完整率
        report.completeness = self._check_completeness(entities)

        # 2. 素材类型分布
        report.type_distribution = self._check_type_distribution(entities)

        # 3. 投放效果排行
        report.top_spenders = self._get_top_spenders(entities, top_n)
        report.top_ctr = self._get_top_ctr(entities, top_n)

        # 4. 告警
        report.warnings = self._generate_warnings(report)

        return report

    def _check_completeness(
        self, entities: list[FacebookCreativeEntity],
    ) -> CompletenessReport:
        """检查字段完整率。"""
        total = len(entities)
        report = CompletenessReport(total_entities=total)

        for field_name in self.CRITICAL_FIELDS:
            present = 0
            for entity in entities:
                value = getattr(entity, field_name, None)
                if field_name == "spend":
                    # spend 为 0 也算有数据（只是没花钱）
                    if value is not None:
                        present += 1
                elif value:
                    present += 1
            coverage = round(present / total, 4) if total > 0 else 0.0
            report.fields[field_name] = coverage
            report.details[field_name] = total - present

        return report

    def _check_type_distribution(
        self, entities: list[FacebookCreativeEntity],
    ) -> TypeDistribution:
        """统计素材类型分布。"""
        dist = TypeDistribution(total=len(entities))
        for entity in entities:
            if entity.is_image:
                dist.image_count += 1
            elif entity.is_video:
                dist.video_count += 1
            else:
                dist.unknown_count += 1
        return dist

    def _get_top_spenders(
        self, entities: list[FacebookCreativeEntity], top_n: int,
    ) -> list[TopSpender]:
        """按 spend 排序 Top N。"""
        sorted_entities = sorted(entities, key=lambda e: e.spend, reverse=True)
        result = []
        for i, entity in enumerate(sorted_entities[:top_n], 1):
            if entity.spend <= 0:
                break
            result.append(TopSpender(
                rank=i,
                creative_asset_id=entity.creative_asset_id,
                ad_name=entity.ad_name,
                creative_type=entity.creative_type.value,
                spend=entity.spend,
                installs=entity.installs,
                ctr=entity.ctr,
            ))
        return result

    def _get_top_ctr(
        self, entities: list[FacebookCreativeEntity], top_n: int,
    ) -> list[TopCTR]:
        """按 CTR 排序 Top N（过滤样本量过小的）。"""
        # 过滤 impressions < 1000 的小样本
        filtered = [e for e in entities if e.impressions >= 1000]
        sorted_entities = sorted(filtered, key=lambda e: e.ctr, reverse=True)
        result = []
        for i, entity in enumerate(sorted_entities[:top_n], 1):
            if entity.ctr <= 0:
                break
            result.append(TopCTR(
                rank=i,
                creative_asset_id=entity.creative_asset_id,
                ad_name=entity.ad_name,
                creative_type=entity.creative_type.value,
                ctr=entity.ctr,
                spend=entity.spend,
                impressions=entity.impressions,
            ))
        return result

    def _generate_warnings(self, report: QualityReport) -> list[str]:
        """生成告警信息。"""
        warnings: list[str] = []

        # 样本量告警
        if report.completeness.total_entities < self.SAMPLE_SIZE_WARN:
            warnings.append(
                f"Low sample size: {report.completeness.total_entities} entities "
                f"(threshold: {self.SAMPLE_SIZE_WARN})"
            )

        # 字段完整率告警
        for field_name, coverage in report.completeness.fields.items():
            if coverage < self.COMPLETENESS_WARN_THRESHOLD:
                warnings.append(
                    f"Low completeness: {field_name} = {coverage:.1%} "
                    f"(threshold: {self.COMPLETENESS_WARN_THRESHOLD:.0%})"
                )

        # 未知类型告警
        if report.type_distribution.unknown_count > 0:
            warnings.append(
                f"Unknown creative types: {report.type_distribution.unknown_count}"
            )

        return warnings

    def __repr__(self) -> str:
        return f"DataQualityValidator(storage={self._storage})"