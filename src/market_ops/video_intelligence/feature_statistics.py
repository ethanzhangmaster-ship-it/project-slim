"""Phase 3: Cross-video Feature Statistics Aggregation.

Segment videos by performance:
  - CTR Top 20% / Bottom 20%
  - ROAS Top 20% / Bottom 20%
  - LTV Top 20%

For each segment, count feature occurrences across all analysis dimensions:
  - Hook types, Story structures, Reward types
  - Character gender/age/profession
  - Camera shot/movement, Motion pace
  - Emotion types, CTA types
  - Video style, Color tone/saturation
  - Audio features

Output: feature_statistics.json
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.video_intelligence.models import FeatureCount, SegmentFeatureStats, FeatureStatistics


class FeatureStatisticsEngine:
    """Aggregate feature counts across videos segmented by performance."""

    SEGMENTS = [
        ("ctr_top20", "CTR Top 20%", lambda m: m.get("ctr", 0), True),
        ("ctr_bottom20", "CTR Bottom 20%", lambda m: m.get("ctr", 0), False),
        ("roas_top20", "ROAS Top 20%", lambda m: m.get("roas", 0), True),
        ("roas_bottom20", "ROAS Bottom 20%", lambda m: m.get("roas", 0), False),
        ("ltv_top20", "LTV Top 20%", lambda m: m.get("ltv", 0), True),
    ]

    FEATURE_SECTIONS = [
        "hook", "story", "reward", "character", "camera",
        "motion", "emotion", "cta", "style", "color", "audio",
        "environment",
    ]

    def __init__(self, output_dir: str | Path | None = None) -> None:
        root = Path(output_dir or Path(__file__).resolve().parents[3] / "output" / "video_intelligence")
        self._output_dir = Path(root)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        video_analyses: list[dict],
        video_metrics: list[dict],
        top_pct: float = 0.2,
        bottom_pct: float = 0.2,
    ) -> dict[str, Any]:
        print(f"[Phase 3] FeatureStatistics: Processing {len(video_analyses)} analyses...")

        analysis_map = {a.get("video_id", ""): a for a in video_analyses}
        metrics_map = {m.get("video_id", ""): m for m in video_metrics}

        merged: list[tuple[dict, dict]] = []
        for vid, analysis in analysis_map.items():
            metrics = metrics_map.get(vid)
            if metrics:
                merged.append((analysis, metrics))

        if not merged:
            print("[Phase 3] No merged analysis+metrics data available")
            return {"error": "no_merged_data"}

        segments = {}
        for seg_key, seg_label, metric_fn, top in self.SEGMENTS:
            segment_data = self._build_segment(
                merged, seg_key, seg_label, metric_fn, top, top_pct, bottom_pct
            )
            segments[seg_key] = segment_data

        stats = FeatureStatistics(
            total_videos=len(merged),
            analyzed_at=datetime.now().isoformat(),
            segments=segments,
        )

        stats_data = self._stats_to_dict(stats)
        stats_file = self._output_dir / "feature_statistics.json"
        stats_file.write_text(
            json.dumps(stats_data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"[Phase 3] Done. Saved: {stats_file}")
        return stats_data

    def _build_segment(
        self,
        merged: list[tuple[dict, dict]],
        seg_key: str,
        seg_label: str,
        metric_fn,
        top: bool,
        top_pct: float,
        bottom_pct: float,
    ) -> SegmentFeatureStats:
        sorted_merged = sorted(merged, key=lambda x: metric_fn(x[1]), reverse=top)
        n = max(3, int(len(sorted_merged) * (top_pct if top else bottom_pct)))

        if top:
            segment_items = sorted_merged[:n]
        else:
            segment_items = sorted_merged[:n]

        analyses = [a for a, _ in segment_items]
        video_count = len(analyses)

        stats = SegmentFeatureStats(
            segment_name=seg_key,
            segment_label=seg_label,
            video_count=video_count,
        )

        for section in self.FEATURE_SECTIONS:
            field_map = self._get_section_field_map(section)
            if field_map:
                counts = self._count_features(analyses, section, field_map)
                setattr(stats, f"{section}_counts", counts)
            else:
                counts = self._count_list_features(analyses, section)
                setattr(stats, f"{section}_counts", counts)

        return stats

    def _count_features(
        self, analyses: list[dict], section: str, field_map: dict[str, str]
    ) -> dict[str, FeatureCount]:
        counter: Counter = Counter()
        for a in analyses:
            for field in field_map:
                key = f"{section}_{field}"
                value = a.get(key, "")
                if value and str(value).strip() and str(value).strip().lower() not in ("none", "false", ""):
                    counter[str(value).strip()] += 1

        total = len(analyses)
        return {
            name: FeatureCount(name=name, count=cnt, percentage=round(cnt / total * 100, 1))
            for name, cnt in counter.most_common()
        }

    def _count_list_features(self, analyses: list[dict], section: str) -> dict[str, FeatureCount]:
        counter: Counter = Counter()
        list_fields = self._get_list_fields(section)
        for a in analyses:
            for field in list_fields:
                key = f"{section}_{field}"
                value = a.get(key, [])
                if isinstance(value, list):
                    for item in value:
                        if item and str(item).strip():
                            counter[str(item).strip()] += 1
                elif isinstance(value, str) and value.strip():
                    counter[value.strip()] += 1

        total_analyses = len(analyses)
        return {
            name: FeatureCount(name=name, count=cnt, percentage=round(cnt / total_analyses * 100, 1))
            for name, cnt in counter.most_common()
        }

    @staticmethod
    def _get_section_field_map(section: str) -> dict[str, str]:
        maps = {
            "hook": {"hook_type": "hook_type"},
            "story": {"structure": "structure"},
            "reward": {"reward_type": "reward_type"},
            "character": {"gender": "gender", "age": "age", "profession": "profession"},
            "camera": {"shot_type": "shot_type", "movement": "movement"},
            "motion": {"pace": "pace", "cut_speed": "cut_speed", "action_speed": "action_speed"},
            "cta": {"cta_type": "cta_type", "timing": "timing", "display_style": "display_style"},
            "style": {"video_style": "video_style"},
            "color": {"color_tone": "color_tone", "saturation": "saturation"},
            "environment": {"scene": "scene"},
            "audio": {"tempo": "tempo"},
        }
        return maps.get(section, {})

    @staticmethod
    def _get_list_fields(section: str) -> list[str]:
        list_maps = {
            "hook": ["tags"],
            "emotion": ["emotions"],
            "reward": ["tags"],
            "environment": ["tags"],
            "camera": ["tags"],
            "audio": ["tags"],
            "motion": ["rhythm_changes"],
        }
        return list_maps.get(section, [])

    def _stats_to_dict(self, stats: FeatureStatistics) -> dict[str, Any]:
        segments_dict = {}
        for seg_key, seg in stats.segments.items():
            seg_dict = {
                "segment_name": seg.segment_name,
                "segment_label": seg.segment_label,
                "video_count": seg.video_count,
            }
            for section in self.FEATURE_SECTIONS:
                counts = getattr(seg, f"{section}_counts", {})
                seg_dict[f"{section}_counts"] = {
                    k: {"name": v.name, "count": v.count, "percentage": v.percentage}
                    for k, v in counts.items()
                }
            segments_dict[seg_key] = seg_dict

        return {
            "total_videos": stats.total_videos,
            "analyzed_at": stats.analyzed_at,
            "segments": segments_dict,
        }
