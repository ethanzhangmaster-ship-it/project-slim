"""V4.2 Trend Reasoner — analyzes DNA trends over time windows.

Answers:
  - Which DNA dimensions are growing/declining?
  - Which patterns are emerging/dying?
  - What trends should inform creative strategy?

Windows: 7 days, 30 days, 90 days.
Platforms: Facebook, Google Play, TikTok, App Store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import TrendDirection
from .models import TrendModel


@dataclass
class TrendReport:
    """Complete trend analysis report."""
    window_days: int = 7
    platform: str = "facebook"
    growing_dna: list[TrendModel] = field(default_factory=list)
    declining_dna: list[TrendModel] = field(default_factory=list)
    emerging_patterns: list[dict[str, Any]] = field(default_factory=list)
    dead_patterns: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_days": self.window_days,
            "platform": self.platform,
            "growing_dna": [t.to_dict() for t in self.growing_dna],
            "declining_dna": [t.to_dict() for t in self.declining_dna],
            "emerging_patterns": self.emerging_patterns,
            "dead_patterns": self.dead_patterns,
            "summary": self.summary,
            "confidence": round(self.confidence, 3),
        }


class TrendReasoner:
    """Analyzes creative DNA trends over time.

    Monitors DNA dimension performance across time windows to detect:
      - Growing DNA (rising ROAS/CTR)
      - Declining DNA (falling ROAS/CTR)
      - Emerging patterns (new combinations gaining traction)
      - Dead patterns (previously effective, now failing)
    """

    # DNA dimensions to track
    TRACKED_DIMENSIONS = [
        "character", "reward", "hook", "gameplay", "camera",
        "style", "palette", "lighting",
    ]

    # Time windows for analysis
    WINDOWS = [7, 30, 90]

    # Platforms
    PLATFORMS = ["facebook", "google_play", "tiktok", "app_store"]

    def __init__(self, retriever=None, pattern_miner=None) -> None:
        self._retriever = retriever
        self._pattern_miner = pattern_miner
        self._history: dict[str, list[dict[str, Any]]] = {}

    def analyze(self, window_days: int = 7,
                platform: str = "facebook",
                creatives: list[dict[str, Any]] | None = None) -> TrendReport:
        """Analyze trends for a given time window and platform.

        Args:
            window_days: Time window (7, 30, or 90 days)
            platform: Platform filter
            creatives: Optional list of creative data to analyze
        """
        if window_days not in self.WINDOWS:
            window_days = 7

        if creatives is None:
            creatives = self._get_creatives(window_days, platform)

        if not creatives:
            return TrendReport(
                window_days=window_days,
                platform=platform,
                summary=f"No creative data for {window_days}d window on {platform}.",
                confidence=0.0,
            )

        # 1. Score each DNA dimension value over time
        dimension_scores = self._compute_dimension_scores(creatives)

        # 2. Compare current vs previous window
        previous_creatives = self._get_previous_window(window_days, platform)
        previous_scores = self._compute_dimension_scores(previous_creatives) if previous_creatives else {}

        # 3. Classify trends
        growing = []
        declining = []
        for dim_key, current in dimension_scores.items():
            previous = previous_scores.get(dim_key, {}).get("score", current.get("score", 0))
            change = self._compute_change(current.get("score", 0), previous)

            trend = TrendModel(
                trend_id=f"trend_{dim_key}_{window_days}d",
                dimension=current.get("dimension", ""),
                value=current.get("value", ""),
                direction=self._classify_direction(change),
                current_score=current.get("score", 0),
                previous_score=previous,
                change_pct=change,
                window_days=window_days,
                sample_count=current.get("count", 0),
                confidence=self._compute_trend_confidence(current.get("count", 0), window_days),
            )

            if trend.direction == TrendDirection.GROWING:
                growing.append(trend)
            elif trend.direction == TrendDirection.DECLINING:
                declining.append(trend)

        # Sort by change magnitude
        growing.sort(key=lambda t: abs(t.change_pct), reverse=True)
        declining.sort(key=lambda t: abs(t.change_pct), reverse=True)

        # 4. Detect emerging and dead patterns
        emerging = self._detect_emerging_patterns(creatives, previous_creatives)
        dead = self._detect_dead_patterns(creatives, previous_creatives)

        # 5. Build summary
        summary = self._build_summary(growing, declining, emerging, dead, window_days)

        confidence = self._compute_report_confidence(
            len(growing) + len(declining), len(creatives)
        )

        return TrendReport(
            window_days=window_days,
            platform=platform,
            growing_dna=growing,
            declining_dna=declining,
            emerging_patterns=emerging,
            dead_patterns=dead,
            summary=summary,
            confidence=confidence,
        )

    def analyze_all_windows(self, platform: str = "facebook") -> dict[int, TrendReport]:
        """Analyze trends across all time windows."""
        return {
            w: self.analyze(window_days=w, platform=platform)
            for w in self.WINDOWS
        }

    def get_growing_dna(self, window_days: int = 7,
                        platform: str = "facebook",
                        top_k: int = 10) -> list[TrendModel]:
        """Get top growing DNA dimensions."""
        report = self.analyze(window_days=window_days, platform=platform)
        return report.growing_dna[:top_k]

    def get_declining_dna(self, window_days: int = 7,
                          platform: str = "facebook",
                          top_k: int = 10) -> list[TrendModel]:
        """Get top declining DNA dimensions."""
        report = self.analyze(window_days=window_days, platform=platform)
        return report.declining_dna[:top_k]

    # ── Private helpers ──

    def _get_creatives(self, window_days: int,
                       platform: str) -> list[dict[str, Any]]:
        """Get creatives for a time window."""
        if self._retriever:
            try:
                results = self._retriever.retrieve_all(top_k=200)
                return [
                    {"dna": r.dna, "performance": r.performance}
                    for r in results
                ]
            except Exception:
                pass
        return []

    def _get_previous_window(self, window_days: int,
                              platform: str) -> list[dict[str, Any]]:
        """Get creatives from the previous time window."""
        # In production, this would query historical data
        return []

    def _compute_dimension_scores(self,
                                   creatives: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Compute performance scores for each DNA dimension value."""
        scores: dict[str, dict[str, Any]] = {}

        for c in creatives:
            dna = c.get("dna", {})
            perf = c.get("performance", {})
            roas = perf.get("roas_d7", 0)

            for dim in self.TRACKED_DIMENSIONS:
                val = dna.get(dim, "")
                if not val:
                    continue
                key = f"{dim}={val}"
                if key not in scores:
                    scores[key] = {
                        "dimension": dim,
                        "value": val,
                        "score": 0.0,
                        "count": 0,
                    }
                scores[key]["score"] += roas
                scores[key]["count"] += 1

        # Average scores
        for key in scores:
            count = scores[key]["count"]
            if count > 0:
                scores[key]["score"] /= count

        return scores

    def _compute_change(self, current: float, previous: float) -> float:
        """Compute percentage change between current and previous."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / abs(previous)) * 100

    def _classify_direction(self, change_pct: float) -> TrendDirection:
        """Classify trend direction based on change percentage."""
        if abs(change_pct) < 5:
            return TrendDirection.STABLE
        if change_pct >= 20:
            return TrendDirection.GROWING
        if change_pct >= 5:
            return TrendDirection.EMERGING
        if change_pct <= -20:
            return TrendDirection.DEAD
        return TrendDirection.DECLINING

    def _compute_trend_confidence(self, sample_count: int,
                                   window_days: int) -> float:
        """Compute confidence in trend detection."""
        if sample_count < 3:
            return 0.2
        if sample_count < 10:
            return 0.5
        if window_days >= 30:
            return min(1.0, sample_count / 30)
        return min(1.0, sample_count / 20)

    def _detect_emerging_patterns(self, current: list[dict[str, Any]],
                                   previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Detect patterns that are newly emerging."""
        if not previous:
            return []

        current_patterns = self._extract_patterns(current)
        previous_patterns = self._extract_patterns(previous)

        emerging = []
        for key, stats in current_patterns.items():
            if key not in previous_patterns and stats["count"] >= 3:
                emerging.append({
                    "pattern": key,
                    "roas": round(stats["roas"], 3),
                    "count": stats["count"],
                    "status": "emerging",
                })

        return sorted(emerging, key=lambda p: p["roas"], reverse=True)[:10]

    def _detect_dead_patterns(self, current: list[dict[str, Any]],
                               previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Detect patterns that were effective but are now failing."""
        if not previous:
            return []

        current_patterns = self._extract_patterns(current)
        previous_patterns = self._extract_patterns(previous)

        dead = []
        for key, prev_stats in previous_patterns.items():
            if prev_stats["roas"] >= 0.5 and prev_stats["count"] >= 5:
                curr_stats = current_patterns.get(key, {"roas": 0, "count": 0})
                if curr_stats["roas"] < 0.3:
                    dead.append({
                        "pattern": key,
                        "previous_roas": round(prev_stats["roas"], 3),
                        "current_roas": round(curr_stats["roas"], 3),
                        "previous_count": prev_stats["count"],
                        "current_count": curr_stats["count"],
                        "status": "dead",
                    })

        return sorted(dead, key=lambda p: p["previous_roas"], reverse=True)[:10]

    def _extract_patterns(self,
                           creatives: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Extract pattern key → stats from creatives."""
        patterns: dict[str, dict[str, Any]] = {}
        for c in creatives:
            dna = c.get("dna", {})
            perf = c.get("performance", {})
            # Build pattern key from character + reward + hook
            parts = []
            for dim in ["character", "reward", "hook"]:
                v = dna.get(dim, "")
                if v:
                    parts.append(f"{dim}={v}")
            key = " | ".join(parts)

            if key not in patterns:
                patterns[key] = {"roas": 0.0, "count": 0}
            patterns[key]["roas"] += perf.get("roas_d7", 0)
            patterns[key]["count"] += 1

        for stats in patterns.values():
            if stats["count"] > 0:
                stats["roas"] /= stats["count"]

        return patterns

    def _build_summary(self, growing: list[TrendModel],
                       declining: list[TrendModel],
                       emerging: list[dict[str, Any]],
                       dead: list[dict[str, Any]],
                       window_days: int) -> str:
        """Build a human-readable trend summary."""
        parts = [f"Trend Analysis ({window_days}d):"]

        if growing:
            top = growing[:3]
            parts.append(
                f"  Growing: {', '.join(f'{t.dimension}={t.value}({t.change_pct:+.0f}%)' for t in top)}"
            )
        if declining:
            top = declining[:3]
            parts.append(
                f"  Declining: {', '.join(f'{t.dimension}={t.value}({t.change_pct:+.0f}%)' for t in top)}"
            )
        if emerging:
            parts.append(f"  Emerging patterns: {len(emerging)}")
        if dead:
            parts.append(f"  Dead patterns: {len(dead)}")

        if not growing and not declining:
            parts.append("  No significant trends detected.")

        return "\n".join(parts)

    def _compute_report_confidence(self, trend_count: int,
                                    total_creatives: int) -> float:
        """Compute overall confidence in the trend report."""
        if total_creatives < 10:
            return 0.2
        if total_creatives < 50:
            return 0.5
        density = min(1.0, trend_count / max(total_creatives * 0.1, 1))
        return min(0.95, 0.5 + density * 0.45)