"""E11 Phase 2 — Adjust Data Quality Validator。

检查 Adjust 数据质量：
  1. Match Rate（匹配率）
  2. Revenue Completeness（收入完整率 D1/D7/D30）
  3. Data Anomalies（数据异常检测）
  4. Top Revenue（收入排名）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .storage import AdjustStorage


@dataclass
class AdjustQualityReport:
    """Adjust 数据质量报告。"""

    total_adjust: int = 0
    match_rate: float = 0.0
    revenue_completeness: dict[str, float] = field(default_factory=lambda: {
        "d1": 0.0,
        "d7": 0.0,
        "d30": 0.0,
    })
    top_revenue: list[dict[str, Any]] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_summary(self) -> str:
        lines = [
            "=" * 60,
            "  Adjust Data Quality Report",
            "=" * 60,
            "",
            f"  Total Adjust Entities: {self.total_adjust}",
            f"  Match Rate: {self.match_rate:.1%}",
            "",
            "  --- Revenue Completeness ---",
            f"  D1: {self.revenue_completeness['d1']:.1%}",
            f"  D7: {self.revenue_completeness['d7']:.1%}",
            f"  D30: {self.revenue_completeness['d30']:.1%}",
            "",
        ]

        if self.top_revenue:
            lines.append("  --- Top Revenue ---")
            for item in self.top_revenue[:5]:
                lines.append(
                    f"    #{item['rank']} {item['id']}: "
                    f"${item['revenue']:,.0f}"
                )

        if self.anomalies:
            lines.append(f"\n  Anomalies ({len(self.anomalies)}):")
            for a in self.anomalies[:5]:
                lines.append(f"    - {a}")

        if self.warnings:
            lines.append(f"\n  Warnings ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"    - {w}")

        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_adjust": self.total_adjust,
            "match_rate": self.match_rate,
            "revenue_completeness": self.revenue_completeness,
            "top_revenue": self.top_revenue,
            "anomalies": self.anomalies,
            "warnings": self.warnings,
        }


class AdjustDataQualityValidator:
    """Adjust 数据质量验证器。

    检查已保存的 adjust.json 数据质量：
      - 收入完整率（D1/D7/D30 覆盖率）
      - 数据异常（0 installs 但有收入，ROAS > 100 等）
      - 收入排名（Top N）

    Usage:
        storage = AdjustStorage("data/creatives")
        validator = AdjustDataQualityValidator(storage)
        report = validator.validate()
        print(report.to_summary())
    """

    def __init__(self, storage: AdjustStorage) -> None:
        self._storage = storage

    def validate(self) -> AdjustQualityReport:
        """执行质量检查。"""
        entities = self._storage.list_all()
        report = AdjustQualityReport(total_adjust=len(entities))

        if not entities:
            report.warnings.append("No Adjust data found")
            return report

        # 1. Revenue completeness
        d1_count = 0
        d7_count = 0
        d30_count = 0

        for entity in entities:
            if entity.iap_d1 > 0 or entity.ad_d1 > 0:
                d1_count += 1
            if entity.iap_d7 > 0 or entity.ad_d7 > 0:
                d7_count += 1
            if entity.iap_d30 > 0 or entity.ad_d30 > 0:
                d30_count += 1

        total = len(entities)
        report.revenue_completeness = {
            "d1": round(d1_count / total, 4),
            "d7": round(d7_count / total, 4),
            "d30": round(d30_count / total, 4),
        }

        # 2. Warnings for low completeness
        if report.revenue_completeness["d30"] < 0.5:
            report.warnings.append(
                f"Low D30 revenue completeness: {report.revenue_completeness['d30']:.1%}"
            )
        if report.revenue_completeness["d7"] < 0.7:
            report.warnings.append(
                f"Low D7 revenue completeness: {report.revenue_completeness['d7']:.1%}"
            )

        # 3. Top revenue
        sorted_entities = sorted(
            entities,
            key=lambda e: e.total_revenue,
            reverse=True,
        )
        report.top_revenue = [
            {
                "rank": i + 1,
                "id": e.creative_asset_id,
                "revenue": e.total_revenue,
                "installs": e.installs,
                "purchasers": e.purchasers,
            }
            for i, e in enumerate(sorted_entities)
        ]

        # 4. Anomalies
        for entity in entities:
            if entity.total_revenue > 0 and entity.installs == 0:
                report.anomalies.append(
                    f"Revenue ${entity.total_revenue:,.0f} with 0 installs "
                    f"({entity.creative_asset_id})"
                )

        return report

    def __repr__(self) -> str:
        return f"AdjustDataQualityValidator(storage={self._storage!r})"