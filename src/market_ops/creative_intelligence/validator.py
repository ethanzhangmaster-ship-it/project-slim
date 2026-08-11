"""E11 Phase 4.1 — Validator（IAP 版）。

验证分析质量：
  - Winner 率是否在合理范围
  - Clickbait 检测率
  - 维度覆盖率
  - Winner vs Loser 区分度
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import CreativeAnalysis


@dataclass
class ValidationReport:
    """分析质量报告。"""
    total_results: int = 0
    winner_count: int = 0
    iap_quality_count: int = 0
    clickbait_count: int = 0
    avg_analysis_score: float = 0.0
    avg_monetization_score: float = 0.0
    visual_coverage: float = 0.0
    hook_coverage: float = 0.0
    gameplay_coverage: float = 0.0
    monetization_coverage: float = 0.0
    warnings: list[str] = field(default_factory=list)
    is_valid: bool = True

    @property
    def winner_rate(self) -> float:
        if self.total_results == 0:
            return 0.0
        return self.winner_count / self.total_results

    def to_dict(self) -> dict:
        return {
            "total_results": self.total_results,
            "winner_count": self.winner_count,
            "iap_quality_count": self.iap_quality_count,
            "clickbait_count": self.clickbait_count,
            "avg_analysis_score": self.avg_analysis_score,
            "avg_monetization_score": self.avg_monetization_score,
            "visual_coverage": self.visual_coverage,
            "hook_coverage": self.hook_coverage,
            "gameplay_coverage": self.gameplay_coverage,
            "monetization_coverage": self.monetization_coverage,
            "warnings": self.warnings,
            "is_valid": self.is_valid,
        }

    def to_summary(self) -> str:
        lines = [
            "=" * 60,
            "  Analysis Quality Report",
            "=" * 60,
            f"  Total Results:       {self.total_results}",
            f"  Winners:             {self.winner_count} ({self.winner_rate:.1%})",
            f"  IAP Quality:         {self.iap_quality_count}",
            f"  Clickbait Detected:  {self.clickbait_count}",
            f"  Avg Analysis Score:  {self.avg_analysis_score:.1f}",
            f"  Avg Monetization:    {self.avg_monetization_score:.1f}",
            f"  Coverage:",
            f"    Visual:       {self.visual_coverage:.1%}",
            f"    Hook:         {self.hook_coverage:.1%}",
            f"    Gameplay:     {self.gameplay_coverage:.1%}",
            f"    Monetization: {self.monetization_coverage:.1%}",
            "=" * 60,
        ]
        if self.warnings:
            lines.append("\n  Warnings:")
            for w in self.warnings:
                lines.append(f"    - {w}")
        return "\n".join(lines)


class Validator:
    """分析质量验证器。"""

    MIN_WINNER_RATE = 0.05
    MAX_WINNER_RATE = 0.80

    def validate(self, analyses: list[CreativeAnalysis]) -> ValidationReport:
        """验证分析结果。"""
        total = len(analyses)
        if total == 0:
            return ValidationReport(warnings=["No results to validate"], is_valid=False)

        winner_count = sum(1 for a in analyses if a.is_winner)
        iap_quality_count = sum(1 for a in analyses if a.is_iap_quality)
        clickbait_count = sum(1 for a in analyses if a.hook_features.is_clickbait)
        avg_score = sum(a.analysis_score for a in analyses) / total
        avg_monetization = sum(a.monetization_features.monetization_score for a in analyses) / total

        visual_cov = sum(1 for a in analyses if a.visual_features.visual_score > 0) / total
        hook_cov = sum(1 for a in analyses if a.hook_features.hook_type.value != "unknown") / total
        gameplay_cov = sum(1 for a in analyses if a.gameplay_features.gameplay_score > 0) / total
        monetization_cov = sum(1 for a in analyses if a.monetization_features.monetization_score > 0) / total

        warnings: list[str] = []
        winner_rate = winner_count / total

        if winner_rate > self.MAX_WINNER_RATE:
            warnings.append(f"Winner rate too high: {winner_rate:.1%} > {self.MAX_WINNER_RATE:.1%}")
        if winner_rate < self.MIN_WINNER_RATE and total >= 10:
            warnings.append(f"Winner rate too low: {winner_rate:.1%} < {self.MIN_WINNER_RATE:.1%}")
        if total >= 20 and clickbait_count == 0:
            warnings.append("No clickbait detected in 20+ results")
        if visual_cov < 0.5:
            warnings.append(f"Low visual coverage: {visual_cov:.1%}")

        return ValidationReport(
            total_results=total,
            winner_count=winner_count,
            iap_quality_count=iap_quality_count,
            clickbait_count=clickbait_count,
            avg_analysis_score=round(avg_score, 1),
            avg_monetization_score=round(avg_monetization, 1),
            visual_coverage=round(visual_cov, 4),
            hook_coverage=round(hook_cov, 4),
            gameplay_coverage=round(gameplay_cov, 4),
            monetization_coverage=round(monetization_cov, 4),
            warnings=warnings,
            is_valid=len(warnings) == 0,
        )

    def validate_winner_vs_loser(
        self, winners: list[CreativeAnalysis], losers: list[CreativeAnalysis],
    ) -> dict:
        """验证 Winner vs Loser 区分度。"""
        if not winners or not losers:
            return {"distinguishable": False, "reason": "Insufficient data"}

        diff = {}

        # Visual
        w_vis = sum(a.visual_features.visual_score for a in winners) / len(winners)
        l_vis = sum(a.visual_features.visual_score for a in losers) / len(losers)
        diff["visual_score"] = round((w_vis - l_vis) / max(l_vis, 0.01), 2)

        # Hook
        w_hook = sum(a.hook_features.hook_score for a in winners) / len(winners)
        l_hook = sum(a.hook_features.hook_score for a in losers) / len(losers)
        diff["hook_score"] = round((w_hook - l_hook) / max(l_hook, 0.01), 2)

        # Monetization
        w_mon = sum(a.monetization_features.monetization_score for a in winners) / len(winners)
        l_mon = sum(a.monetization_features.monetization_score for a in losers) / len(losers)
        diff["monetization_score"] = round((w_mon - l_mon) / max(l_mon, 0.01), 2)

        # Analysis Score
        w_avg = sum(a.analysis_score for a in winners) / len(winners)
        l_avg = sum(a.analysis_score for a in losers) / len(losers)
        diff["analysis_score"] = round((w_avg - l_avg) / max(l_avg, 0.01), 2)

        significant = sum(1 for v in diff.values() if abs(v) > 0.1)
        distinguishable = significant >= 3

        return {
            "distinguishable": distinguishable,
            "significant_dimensions": significant,
            "differences": diff,
            "winner_avg_score": round(w_avg, 1),
            "loser_avg_score": round(l_avg, 1),
            "winner_avg_monetization": round(w_mon, 1),
            "loser_avg_monetization": round(l_mon, 1),
        }