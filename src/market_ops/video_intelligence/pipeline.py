"""Video Intelligence Pipeline Orchestrator.

Wires all 5 phases together:
  1. Fetch videos + metrics from Facebook
  2. Analyze each video via Lovart AI
  3. Aggregate feature statistics across videos
  4. Discover performance patterns
  5. Generate video direction report

Supports partial runs (--skip-fetch, --skip-analysis) for re-processing.

Usage:
    python -m market_ops.video_intelligence.pipeline
    python -m market_ops.video_intelligence.pipeline --skip-fetch
    python -m market_ops.video_intelligence.pipeline --skip-fetch --skip-analysis
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class VideoIntelligencePipeline:
    """Complete video intelligence analysis pipeline."""

    def __init__(
        self,
        output_dir: str | Path | None = None,
        access_token: str | None = None,
        ad_account_id: str | None = None,
        api_version: str = "v22.0",
        lookback_days: int = 365,
        download_videos: bool = True,
        skip_fetch: bool = False,
        skip_analysis: bool = False,
        top_pct: float = 0.2,
        bottom_pct: float = 0.2,
    ) -> None:
        root = Path(output_dir or Path(__file__).resolve().parents[3] / "output" / "video_intelligence")
        self._output_dir = Path(root)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._access_token = access_token
        self._ad_account_id = ad_account_id
        self._api_version = api_version
        self._lookback_days = lookback_days
        self._download_videos = download_videos
        self._skip_fetch = skip_fetch
        self._skip_analysis = skip_analysis
        self._top_pct = top_pct
        self._bottom_pct = bottom_pct

    def run(self) -> dict[str, Any]:
        print("=" * 60)
        print("VIDEO INTELLIGENCE PIPELINE")
        print("=" * 60)

        # Phase 1: Fetch
        if self._skip_fetch:
            print("[Pipeline] Skipping Phase 1 (--skip-fetch)")
            video_records = self._load_json("video_records.json")
            video_metrics = self._load_json("video_metrics.json")
        else:
            from market_ops.video_intelligence.fetcher import VideoFetcher

            fetcher = VideoFetcher(
                access_token=self._access_token,
                ad_account_id=self._ad_account_id,
                api_version=self._api_version,
                output_dir=self._output_dir,
                lookback_days=self._lookback_days,
                download_videos=self._download_videos,
            )
            fetcher.run()
            video_records = self._load_json("video_records.json")
            video_metrics = self._load_json("video_metrics.json")

        if not video_records:
            print("[Pipeline] No video records found. Exiting.")
            return {"error": "no_video_records"}

        # Phase 2: Lovart Analysis
        if self._skip_analysis:
            print("[Pipeline] Skipping Phase 2 (--skip-analysis)")
            video_analyses = self._load_json("analysis/all_video_analysis.json")
            if not video_analyses:
                print("[Pipeline] No cached analysis found, running analysis anyway...")
                video_analyses = self._run_phase2(video_records, video_metrics)
        else:
            video_analyses = self._run_phase2(video_records, video_metrics)

        if not video_analyses:
            print("[Pipeline] No video analyses. Exiting.")
            return {"error": "no_video_analyses"}

        # Phase 3: Feature Statistics
        print("\n" + "-" * 40)
        feature_stats = self._run_phase3(video_analyses, video_metrics)

        # Phase 4: Pattern Analysis
        print("\n" + "-" * 40)
        patterns = self._run_phase4(feature_stats)

        # Phase 5: Direction Report
        print("\n" + "-" * 40)
        report_paths = self._run_phase5(patterns, feature_stats)

        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print(f"  Videos analyzed: {len(video_analyses)}")
        print(f"  Output directory: {self._output_dir}")
        print(f"  Report: {report_paths.get('md_path', 'N/A')}")
        print("=" * 60)

        return {
            "video_count": len(video_records),
            "analyzed_count": len(video_analyses),
            "output_dir": str(self._output_dir),
            "report_md": report_paths.get("md_path", ""),
            "report_json": report_paths.get("json_path", ""),
        }

    def _run_phase2(self, video_records: list[dict], video_metrics: list[dict]) -> list[dict]:
        from market_ops.video_intelligence.lovart_analyzer import LovartVideoAnalyzer

        analyzer = LovartVideoAnalyzer(output_dir=self._output_dir, skip_existing=True)
        return analyzer.run(video_records, video_metrics)

    def _run_phase3(self, video_analyses: list[dict], video_metrics: list[dict]) -> dict:
        from market_ops.video_intelligence.feature_statistics import FeatureStatisticsEngine

        engine = FeatureStatisticsEngine(output_dir=self._output_dir)
        return engine.run(video_analyses, video_metrics, self._top_pct, self._bottom_pct)

    def _run_phase4(self, feature_stats: dict) -> dict:
        from market_ops.video_intelligence.pattern_analyzer import PatternAnalyzer

        analyzer = PatternAnalyzer(output_dir=self._output_dir)
        return analyzer.run(feature_stats)

    def _run_phase5(self, patterns: dict, feature_stats: dict) -> dict:
        from market_ops.video_intelligence.direction_report import DirectionReportGenerator

        generator = DirectionReportGenerator(output_dir=self._output_dir)
        return generator.run(patterns, feature_stats)

    def _load_json(self, relative_path: str) -> list[dict]:
        path = self._output_dir / relative_path
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[Pipeline] Failed to load {path}: {exc}")
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Video Intelligence Pipeline")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    parser.add_argument("--access-token", type=str, default=None, help="Facebook access token")
    parser.add_argument("--ad-account-id", type=str, default=None, help="Facebook ad account ID")
    parser.add_argument("--api-version", type=str, default="v22.0", help="Facebook API version")
    parser.add_argument("--lookback-days", type=int, default=365, help="Lookback days for metrics")
    parser.add_argument("--no-download", action="store_true", help="Skip video download")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip Phase 1 (use cached data)")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip Phase 2 (use cached analysis)")
    parser.add_argument("--top-pct", type=float, default=0.2, help="Top percentage threshold")
    parser.add_argument("--bottom-pct", type=float, default=0.2, help="Bottom percentage threshold")

    args = parser.parse_args()

    pipeline = VideoIntelligencePipeline(
        output_dir=args.output_dir,
        access_token=args.access_token,
        ad_account_id=args.ad_account_id,
        api_version=args.api_version,
        lookback_days=args.lookback_days,
        download_videos=not args.no_download,
        skip_fetch=args.skip_fetch,
        skip_analysis=args.skip_analysis,
        top_pct=args.top_pct,
        bottom_pct=args.bottom_pct,
    )
    result = pipeline.run()
    if result.get("error"):
        print(f"Pipeline error: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
