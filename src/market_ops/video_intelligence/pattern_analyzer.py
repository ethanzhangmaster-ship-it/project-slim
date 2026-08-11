"""Phase 4: Pattern Analyzer - Discover performance patterns from feature statistics.

Compare Top vs Bottom segments for each metric (CTR, ROAS, LTV) to identify:
  - What features correlate with high performance?
  - What features correlate with low performance?
  - What are the differentiating factors?

Each insight must be data-grounded, referencing actual feature counts and percentages.

Output: pattern_analysis.json
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.video_intelligence.models import PatternResult


class PatternAnalyzer:
    """Discover performance patterns by comparing Top vs Bottom segments."""

    FEATURE_SECTIONS = [
        "hook", "story", "reward", "character", "camera",
        "motion", "emotion", "cta", "style", "color", "audio",
        "environment",
    ]

    COMPARISONS = [
        ("ctr_top20", "ctr_bottom20", "CTR"),
        ("roas_top20", "roas_bottom20", "ROAS"),
        ("ltv_top20", "ltv_bottom20", "LTV"),
    ]

    def __init__(self, output_dir: str | Path | None = None) -> None:
        root = Path(output_dir or Path(__file__).resolve().parents[3] / "output" / "video_intelligence")
        self._output_dir = Path(root)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, feature_statistics: dict) -> dict[str, Any]:
        print("[Phase 4] PatternAnalyzer: Discovering patterns...")

        segments = feature_statistics.get("segments", {})
        patterns: dict[str, PatternResult] = {}
        all_differentiated = []

        for top_key, bottom_key, metric_name in self.COMPARISONS:
            top_seg = segments.get(top_key, {})
            bottom_seg = segments.get(bottom_key, {})

            if not top_seg or not bottom_seg:
                continue

            top_count = top_seg.get("video_count", 0)
            bottom_count = bottom_seg.get("video_count", 0)

            for section in self.FEATURE_SECTIONS:
                top_counts = top_seg.get(f"{section}_counts", {})
                bottom_counts = bottom_seg.get(f"{section}_counts", {})

                for feature_name, top_data in top_counts.items():
                    top_pct = top_data.get("percentage", 0)
                    bottom_data = bottom_counts.get(feature_name, {})
                    bottom_pct = bottom_data.get("percentage", 0) if bottom_data else 0

                    gap = top_pct - bottom_pct

                    if abs(gap) >= 15 and top_pct >= 20:
                        direction = "winning" if gap > 0 else "losing"
                        key = f"{metric_name}_{direction}_{section}_{feature_name}"

                        all_differentiated.append({
                            "metric": metric_name,
                            "direction": direction,
                            "section": section,
                            "feature": feature_name,
                            "feature_value": top_data.get("name", feature_name),
                            "top_pct": top_pct,
                            "bottom_pct": bottom_pct,
                            "gap": round(gap, 1),
                            "top_count": top_data.get("count", 0),
                            "bottom_count": bottom_data.get("count", 0),
                        })

                for feature_name, bottom_data in bottom_counts.items():
                    if feature_name in top_counts:
                        continue
                    bottom_pct = bottom_data.get("percentage", 0)
                    if bottom_pct >= 25:
                        key = f"{metric_name}_losing_only_{section}_{feature_name}"
                        all_differentiated.append({
                            "metric": metric_name,
                            "direction": "losing_only",
                            "section": section,
                            "feature": feature_name,
                            "feature_value": bottom_data.get("name", feature_name),
                            "top_pct": 0,
                            "bottom_pct": bottom_pct,
                            "gap": round(-bottom_pct, 1),
                            "top_count": 0,
                            "bottom_count": bottom_data.get("count", 0),
                        })

        summary = self._build_summary(all_differentiated, segments)
        summary["patterns_detail"] = all_differentiated

        pattern_file = self._output_dir / "pattern_analysis.json"
        pattern_file.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"[Phase 4] Done. {len(all_differentiated)} differentiating features found")
        print(f"[Phase 4] Saved: {pattern_file}")
        return summary

    def _build_summary(
        self, patterns: list[dict], segments: dict
    ) -> dict[str, Any]:
        winning_by_metric: dict[str, list[dict]] = {}
        losing_by_metric: dict[str, list[dict]] = {}

        for p in patterns:
            metric = p["metric"]
            if p["direction"] in ("winning",):
                winning_by_metric.setdefault(metric, []).append(p)
            elif p["direction"] in ("losing", "losing_only"):
                losing_by_metric.setdefault(metric, []).append(p)

        pattern_results = {}
        for metric in ("CTR", "ROAS", "LTV"):
            winners = winning_by_metric.get(metric, [])
            losers = losing_by_metric.get(metric, [])

            top_features = [f"{w['section']}.{w['feature']}" for w in winners[:10]]
            bottom_features = [f"{l['section']}.{l['feature']}" for l in losers[:10]]

            top_detail = {f"{w['section']}_{w['feature']}": w for w in winners}
            bottom_detail = {f"{l['section']}_{l['feature']}": l for l in losers}

            top_insight = self._build_insight(metric, "high", winners, "top")
            bottom_insight = self._build_insight(metric, "low", losers, "bottom")

            pattern_results[f"{metric}_top"] = asdict(PatternResult(
                metric=metric,
                segment="top20",
                common_features=top_features,
                feature_detail=top_detail,
                insight=top_insight,
            ))

            pattern_results[f"{metric}_bottom"] = asdict(PatternResult(
                metric=metric,
                segment="bottom20",
                common_features=bottom_features,
                feature_detail=bottom_detail,
                insight=bottom_insight,
            ))

        return {
            "analyzed_at": datetime.now().isoformat(),
            "total_differentiated_features": len(patterns),
            "pattern_results": pattern_results,
        }

    @staticmethod
    def _build_insight(
        metric: str, which: str, items: list[dict], segment: str
    ) -> str:
        if not items:
            return f"No significant patterns found for {metric} {segment}20%."

        items.sort(key=lambda x: abs(x["gap"]), reverse=True)
        top3 = items[:3]
        parts = [f"{metric} {segment}20% common characteristics:"]
        for item in top3:
            parts.append(
                f"- {item['section']}.{item['feature']}: "
                f"{item['top_pct']}% vs {item['bottom_pct']}% (gap={item['gap']}%)"
            )
        return "\n".join(parts)
