from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.digest import WeeklyDigest
from market_ops.final_digest import FinalWeeklyDigestBuilder
from market_ops.models import RevenueBreakdownRow


@dataclass(slots=True)
class ForecastValidationReport:
    title: str
    report_date: date
    weekly_window: str
    gate_lines: list[str]
    bias_lines: list[str]
    project_lines: list[str]
    segment_lines: list[str]


class ForecastValidationReportBuilder:
    def __init__(self, digest_builder: FinalWeeklyDigestBuilder) -> None:
        self._digest_builder = digest_builder

    def build(
        self,
        digest: WeeklyDigest,
        revenue_breakdown_rows: list[RevenueBreakdownRow] | None = None,
    ) -> ForecastValidationReport:
        recovery_map = getattr(self._digest_builder, "_latest_recovery_map", {})
        bias_lines = list(getattr(self._digest_builder, "_latest_global_bias_lines", []))
        bias_summary = getattr(self._digest_builder, "_latest_global_bias_summary", {}) or {}
        window_start = digest.report_date - timedelta(days=6)
        previous_start = window_start - timedelta(days=7)
        previous_end = window_start - timedelta(days=1)

        weighted_mape = bias_summary.get("weighted_mape")
        boss_autosend_ready = bool(bias_summary.get("boss_autosend_ready"))
        gate_lines = [
            "Forecast Confidence system: ready",
            "Forecast Pending Validation system: ready",
            "Forecast Accuracy page: ready",
            (
                f"12m mature-cohort weighted MAPE: {weighted_mape:.1%} "
                + ("(pass <10%)" if weighted_mape is not None and weighted_mape < 0.10 else "(fail >=10%)")
                if weighted_mape is not None
                else "12m mature-cohort weighted MAPE: unavailable"
            ),
            (
                f"Boss auto-send gate: {'ready' if boss_autosend_ready else 'blocked'}"
                + (
                    ""
                    if boss_autosend_ready
                    else " until mature-cohort backtest error drops below 10%"
                )
            ),
        ]

        project_lines: list[str] = []
        segment_lines = self._build_segment_lines(
            digest=digest,
            revenue_breakdown_rows=revenue_breakdown_rows or [],
            window_start=window_start,
            window_end=digest.report_date,
            previous_start=previous_start,
            previous_end=previous_end,
        )
        for item in digest.project_items:
            recovery = recovery_map.get(item.game) or recovery_map.get(self._digest_builder._project_key(item.game))
            if not recovery:
                continue
            project_lines.append(item.game)
            project_lines.append(f"Current Actual: {recovery.actual_summary or 'unavailable'}")
            project_lines.append(f"Forecast: {recovery.forecast_summary or 'unavailable'}")
            project_lines.append(
                f"Cohort Maturity: oldest {recovery.cohort_oldest_age_days or 0}d / newest {recovery.cohort_newest_age_days or 0}d"
            )
            project_lines.append(f"Forecast Confidence: {recovery.forecast_confidence or 'Unknown'}")
            if recovery.pending_validation:
                project_lines.append(recovery.pending_validation)
            else:
                project_lines.append("Forecast Validation: mature horizon available")
            if recovery.forecast_accuracy_rows:
                project_lines.extend(f"Current-window validation: {row}" for row in recovery.forecast_accuracy_rows)
            if recovery.history_validation_rows:
                project_lines.extend(f"History backtest: {row}" for row in recovery.history_validation_rows)
            else:
                project_lines.append("History backtest: unavailable")
            project_lines.append(f"Recommendation gate: {recovery.recommendation or 'unavailable'}")

        return ForecastValidationReport(
            title=f"Forecast Validation Report | {digest.report_date.isoformat()}",
            report_date=digest.report_date,
            weekly_window=f"{window_start.isoformat()} ~ {digest.report_date.isoformat()}（上周四到本周三）",
            gate_lines=gate_lines,
            bias_lines=bias_lines or ["Forecast bias report pending."],
            project_lines=project_lines,
            segment_lines=segment_lines,
        )

    def render_markdown(self, report: ForecastValidationReport) -> str:
        lines = [f"# {report.title}", ""]
        lines.append(f"- 周窗口：{report.weekly_window}")

        lines.extend(["", "## Release Gate", ""])
        lines.extend(f"- {line}" for line in report.gate_lines)

        lines.extend(["", "## Forecast Bias", ""])
        lines.extend(f"- {line}" for line in report.bias_lines)

        lines.extend(["", "## Project Validation", ""])
        if report.project_lines:
            for line in report.project_lines:
                prefix = "### " if not any(token in line for token in (":", "：")) else "- "
                lines.append(f"{prefix}{line}")
        else:
            lines.append("- No active project validation rows.")
        lines.extend(["", "## Segment Diagnostics", ""])
        if report.segment_lines:
            for line in report.segment_lines:
                prefix = "### " if not any(token in line for token in (":", "：")) else "- "
                lines.append(f"{prefix}{line}")
        else:
            lines.append("- No current segment diagnostics.")
        lines.append("")
        return "\n".join(lines)

    def save_markdown(self, report: ForecastValidationReport, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"forecast_validation_{report.report_date.strftime('%Y%m%d')}.md"
        path.write_text(self.render_markdown(report), encoding="utf-8")
        return path

    def build_card(self, report: ForecastValidationReport) -> dict[str, Any]:
        sections = [
            self._section("Release Gate", report.gate_lines),
            {"tag": "hr"},
            self._section("Forecast Bias", report.bias_lines),
            {"tag": "hr"},
            self._section("Project Validation", report.project_lines or ["No active project validation rows."]),
            {"tag": "hr"},
            self._section("Segment Diagnostics", report.segment_lines or ["No current segment diagnostics."]),
        ]
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "wathet",
                "title": {"tag": "plain_text", "content": report.title},
            },
            "elements": sections,
        }

    @staticmethod
    def _section(title: str, lines: list[str]) -> dict[str, Any]:
        formatted: list[str] = []
        for line in lines:
            prefix = "### " if not any(token in line for token in (":", "：")) else "- "
            formatted.append(f"{prefix}{line}")
        return {"tag": "div", "text": {"tag": "lark_md", "content": f"**{title}**\n" + "\n".join(formatted)}}

    def _build_segment_lines(
        self,
        digest: WeeklyDigest,
        revenue_breakdown_rows: list[RevenueBreakdownRow],
        window_start: date,
        window_end: date,
        previous_start: date,
        previous_end: date,
    ) -> list[str]:
        if not revenue_breakdown_rows:
            return []

        current_rows = [row for row in revenue_breakdown_rows if window_start <= row.date <= window_end]
        previous_rows = [row for row in revenue_breakdown_rows if previous_start <= row.date <= previous_end]
        lines: list[str] = [
            "Segment diagnostics use revenue_breakdown as explanation only; they do not override the main forecast model."
        ]
        for item in digest.project_items:
            project_key = self._digest_builder._project_key(item.game)
            current_project_rows = [row for row in current_rows if self._digest_builder._project_key(row.game) == project_key]
            previous_project_rows = [row for row in previous_rows if self._digest_builder._project_key(row.game) == project_key]
            if not current_project_rows:
                continue
            current_segments = self._aggregate_segments(current_project_rows)
            previous_segments = self._aggregate_segments(previous_project_rows)
            ranked = sorted(current_segments.items(), key=lambda pair: pair[1]["spend"], reverse=True)
            if not ranked:
                continue

            lines.append(item.game)
            for segment_name, metrics in ranked[:2]:
                roi = metrics["revenue"] / metrics["spend"] if metrics["spend"] else 0.0
                previous_metrics = previous_segments.get(segment_name)
                previous_roi = (
                    previous_metrics["revenue"] / previous_metrics["spend"]
                    if previous_metrics and previous_metrics["spend"]
                    else None
                )
                roi_change = (
                    f"{roi - previous_roi:+.2f}"
                    if previous_roi is not None
                    else "n/a"
                )
                direction = self._segment_direction(roi, previous_roi)
                lines.append(
                    f"{segment_name}: spend {metrics['spend']:.0f}, gross ROI {roi:.2f}, WoW {roi_change}, signal {direction}"
                )

            strongest = max(ranked, key=lambda pair: ((pair[1]["revenue"] / pair[1]["spend"]) if pair[1]["spend"] else -1.0, pair[1]["spend"]))
            weakest = min(ranked, key=lambda pair: ((pair[1]["revenue"] / pair[1]["spend"]) if pair[1]["spend"] else 999.0, -pair[1]["spend"]))
            strongest_roi = strongest[1]["revenue"] / strongest[1]["spend"] if strongest[1]["spend"] else 0.0
            weakest_roi = weakest[1]["revenue"] / weakest[1]["spend"] if weakest[1]["spend"] else 0.0
            lines.append(
                f"Driver summary: strongest {strongest[0]} (ROI {strongest_roi:.2f}); weakest {weakest[0]} (ROI {weakest_roi:.2f})."
            )
        return lines

    @staticmethod
    def _aggregate_segments(rows: list[RevenueBreakdownRow]) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, float]] = {}
        for row in rows:
            if row.cost <= 0:
                continue
            segment_name = f"{ForecastValidationReportBuilder._normalize_store(row.store)} / {ForecastValidationReportBuilder._normalize_partner(row.partner)}"
            bucket = buckets.setdefault(segment_name, {"spend": 0.0, "revenue": 0.0})
            bucket["spend"] += row.cost
            bucket["revenue"] += row.total_revenue_gross
        return buckets

    @staticmethod
    def _normalize_store(value: str) -> str:
        normalized = (value or "").strip().lower()
        mapping = {
            "app_store": "iOS",
            "google_play": "Android",
            "amazon": "Amazon",
        }
        return mapping.get(normalized, value or "Unknown Store")

    @staticmethod
    def _normalize_partner(value: str) -> str:
        normalized = (value or "").strip().lower()
        if "google" in normalized:
            return "Google"
        if "facebook" in normalized or "instagram" in normalized or "off-facebook" in normalized:
            return "Facebook"
        if not value:
            return "Unknown Partner"
        return value

    @staticmethod
    def _segment_direction(current_roi: float, previous_roi: float | None) -> str:
        if previous_roi is None:
            return "new or no prior baseline"
        delta = current_roi - previous_roi
        if delta >= 0.05:
            return "improving"
        if delta <= -0.05:
            return "weakening"
        return "roughly flat"
