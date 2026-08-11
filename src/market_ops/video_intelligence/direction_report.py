"""Phase 5: Video Direction Report Generator.

Generate a comprehensive report from historical data analysis:
  - Winning video common characteristics (by CTR, ROAS, LTV)
  - Underperforming video common problems
  - Creative elements to retain
  - Creative elements to avoid
  - Next batch production directions (Hook, Character, Story, Camera, Pacing, Reward, CTA)

All conclusions must reference historical data statistics.
Output: video_direction_report.md
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.video_intelligence.models import DirectionItem, DirectionReport


class DirectionReportGenerator:
    """Generate video production direction report from pattern analysis."""

    RATING_STARS = {5: "★★★★★", 4: "★★★★☆", 3: "★★★☆☆", 2: "★★☆☆☆", 1: "★☆☆☆☆"}

    def __init__(self, output_dir: str | Path | None = None) -> None:
        root = Path(output_dir or Path(__file__).resolve().parents[3] / "output" / "video_intelligence")
        self._output_dir = Path(root)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        pattern_analysis: dict,
        feature_statistics: dict,
    ) -> dict[str, Any]:
        print("[Phase 5] DirectionReportGenerator: Building report...")

        patterns_detail = pattern_analysis.get("patterns_detail", [])
        pattern_results = pattern_analysis.get("pattern_results", {})

        winning = [p for p in patterns_detail if p["direction"] == "winning"]
        losing = [p for p in patterns_detail if p["direction"] in ("losing", "losing_only")]

        recommend_items = self._build_recommend_items(winning)
        avoid_items = self._build_avoid_items(losing)

        hook_dirs = self._extract_section_directions("hook", winning, "Hook Type")
        character_dirs = self._extract_section_directions("character", winning, "Character")
        story_dirs = self._extract_section_directions("story", winning, "Story Structure")
        camera_dirs = self._extract_section_directions("camera", winning, "Camera")
        pacing_dirs = self._extract_section_directions("motion", winning, "Pacing")
        reward_dirs = self._extract_section_directions("reward", winning, "Reward")
        cta_dirs = self._extract_section_directions("cta", winning, "CTA")

        report = DirectionReport(
            generated_at=datetime.now().isoformat(),
            total_videos_analyzed=feature_statistics.get("total_videos", 0),
            recommend=recommend_items,
            avoid=avoid_items,
            hook_directions=hook_dirs,
            character_directions=character_dirs,
            story_directions=story_dirs,
            camera_directions=camera_dirs,
            pacing_directions=pacing_dirs,
            reward_directions=reward_dirs,
            cta_directions=cta_dirs,
            pattern_insights=pattern_results,
        )

        md = self._build_markdown(report)
        report_file = self._output_dir / "video_direction_report.md"
        report_file.write_text(md, encoding="utf-8")
        print(f"[Phase 5] Report saved: {report_file}")

        json_file = self._output_dir / "video_direction_report.json"
        json_file.write_text(
            json.dumps(self._report_to_dict(report), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        print(f"[Phase 5] Done.")
        return {"md_path": str(report_file), "json_path": str(json_file)}

    def _build_recommend_items(self, winning: list[dict]) -> list[DirectionItem]:
        items: list[DirectionItem] = []
        sections_seen: set[str] = set()
        for p in sorted(winning, key=lambda x: abs(x["gap"]), reverse=True):
            key = f"{p['section']}.{p['feature']}"
            if key in sections_seen:
                continue
            sections_seen.add(key)

            gap = abs(p["gap"])
            if gap >= 40:
                rating = 5
            elif gap >= 30:
                rating = 4
            elif gap >= 20:
                rating = 3
            else:
                rating = 2

            evidence = f"Top 20%: {p['top_pct']}% vs Bottom 20%: {p['bottom_pct']}% (gap={p['gap']}%)"
            items.append(DirectionItem(
                element=f"{p['section'].title()}: {p['feature_value']}",
                rating=rating,
                description=f"Strongly associated with high {p['metric']} performance",
                data_evidence=evidence,
            ))

        if not items:
            items.append(DirectionItem(
                element="Insufficient data",
                rating=3,
                description="More video analysis data needed for reliable recommendations",
                data_evidence="No statistically significant patterns found",
            ))

        return items[:15]

    def _build_avoid_items(self, losing: list[dict]) -> list[DirectionItem]:
        items: list[DirectionItem] = []
        sections_seen: set[str] = set()
        for p in sorted(losing, key=lambda x: abs(x["gap"]), reverse=True):
            key = f"{p['section']}.{p['feature']}"
            if key in sections_seen:
                continue
            sections_seen.add(key)

            gap = abs(p["gap"])
            if gap >= 40:
                rating = 1
            elif gap >= 30:
                rating = 2
            elif gap >= 20:
                rating = 2
            else:
                rating = 3

            evidence = f"Bottom 20%: {p['bottom_pct']}% vs Top 20%: {p['top_pct']}% (gap={abs(p['gap'])}%)"
            items.append(DirectionItem(
                element=f"{p['section'].title()}: {p['feature_value']}",
                rating=rating,
                description=f"Associated with low {p['metric']} performance",
                data_evidence=evidence,
            ))

        if not items:
            items.append(DirectionItem(
                element="Insufficient data",
                rating=3,
                description="More video analysis data needed for reliable avoidance signals",
                data_evidence="No statistically significant losing patterns found",
            ))

        return items[:10]

    def _extract_section_directions(
        self, section: str, winning: list[dict], label: str
    ) -> list[str]:
        section_items = sorted(
            [p for p in winning if p["section"] == section],
            key=lambda x: abs(x["gap"]),
            reverse=True,
        )
        if not section_items:
            return [f"{label}: Insufficient data to recommend specific directions"]

        seen: set[str] = set()
        result: list[str] = []
        for p in section_items:
            val = p["feature_value"]
            if val not in seen:
                seen.add(val)
                result.append(f"{label}: {val} (present in {p['top_pct']}% of top performers)")
            if len(result) >= 5:
                break
        return result

    def _build_markdown(self, report: DirectionReport) -> str:
        lines: list[str] = []
        lines.append("# Video Production Direction Report\n")
        lines.append(f"> Generated: {report.generated_at}")
        lines.append(f"> Videos Analyzed: {report.total_videos_analyzed}")
        lines.append(f"> Analysis Scope: CTR Top/Bottom 20%, ROAS Top/Bottom 20%, LTV Top 20%\n")

        lines.append("---\n")
        lines.append("## Suggested to Continue (★ = strength level)\n")
        lines.append("| Rating | Element | Description | Data Evidence |")
        lines.append("|--------|---------|-------------|---------------|")
        for item in report.recommend:
            stars = self.RATING_STARS.get(item.rating, "★★★☆☆")
            lines.append(f"| {stars} | {item.element} | {item.description} | {item.data_evidence} |")
        lines.append("")

        lines.append("---\n")
        lines.append("## Suggested to Reduce (☆ = weakness level)\n")
        lines.append("| Rating | Element | Description | Data Evidence |")
        lines.append("|--------|---------|-------------|---------------|")
        for item in report.avoid:
            stars = self.RATING_STARS.get(item.rating, "★★★☆☆")
            lines.append(f"| {stars} | {item.element} | {item.description} | {item.data_evidence} |")
        lines.append("")

        lines.append("---\n")
        lines.append("## Next Batch Production Directions\n")

        sections = [
            ("Hook Type", report.hook_directions),
            ("Character", report.character_directions),
            ("Story Structure", report.story_directions),
            ("Camera & Shot", report.camera_directions),
            ("Pacing & Rhythm", report.pacing_directions),
            ("Reward Display", report.reward_directions),
            ("CTA Strategy", report.cta_directions),
        ]
        for title, directions in sections:
            lines.append(f"### {title}\n")
            for d in directions:
                lines.append(f"- {d}")
            lines.append("")

        lines.append("---\n")
        lines.append("## Pattern Insights by Metric\n")
        for key, result in report.pattern_insights.items():
            if isinstance(result, dict):
                metric = result.get("metric", "")
                segment = result.get("segment", "")
                insight = result.get("insight", "")
                if insight:
                    lines.append(f"### {metric} - {segment}\n")
                    lines.append(f"{insight}\n")

        return "\n".join(lines)

    def _report_to_dict(self, report: DirectionReport) -> dict[str, Any]:
        return {
            "generated_at": report.generated_at,
            "total_videos_analyzed": report.total_videos_analyzed,
            "recommend": [
                {"element": r.element, "rating": r.rating, "description": r.description, "data_evidence": r.data_evidence}
                for r in report.recommend
            ],
            "avoid": [
                {"element": a.element, "rating": a.rating, "description": a.description, "data_evidence": a.data_evidence}
                for a in report.avoid
            ],
            "hook_directions": report.hook_directions,
            "character_directions": report.character_directions,
            "story_directions": report.story_directions,
            "camera_directions": report.camera_directions,
            "pacing_directions": report.pacing_directions,
            "reward_directions": report.reward_directions,
            "cta_directions": report.cta_directions,
            "pattern_insights": report.pattern_insights,
        }
