"""
E16.6.10 — Change Detection Engine.

Compares two CompetitorSnapshots to detect meaningful changes in:
  1. Icon — hash changed (and heuristic analysis of style shift)
  2. Screenshots — hashes changed (count or individual)
  3. Keywords — added / removed keywords in title or keyword list
  4. Ranking — velocity-based surge detection
"""

from __future__ import annotations

from typing import List, Optional

from src.aso_intelligence.competitor.models import (
    CompetitorSnapshot,
    CompetitorChange,
    CompetitorChangeType,
)


class ChangeDetectionEngine:
    """Detect changes between two competitor snapshots."""

    # ------------------------------------------------------------------ #
    def detect_all(
        self,
        old: CompetitorSnapshot,
        new: CompetitorSnapshot,
    ) -> List[CompetitorChange]:
        """Run all change detectors and return combined results."""
        changes: List[CompetitorChange] = []

        changes.extend(self.detect_icon_change(old, new))
        changes.extend(self.detect_screenshot_change(old, new))
        changes.extend(self.detect_keyword_change(old, new))
        changes.extend(self.detect_title_change(old, new))
        changes.extend(self.detect_ranking_surge(old, new))

        return changes

    # ------------------------------------------------------------------ #
    def detect_icon_change(
        self, old: CompetitorSnapshot, new: CompetitorSnapshot
    ) -> List[CompetitorChange]:
        if old.icon_hash and new.icon_hash and old.icon_hash != new.icon_hash:
            return [
                CompetitorChange(
                    app_id=new.app_id,
                    change_type=CompetitorChangeType.ICON_CHANGE,
                    description=(
                        f"Icon updated — new visual identity detected"
                    ),
                    impact="high",
                    confidence=0.9,
                    old_value=old.icon_hash[:8],
                    new_value=new.icon_hash[:8],
                )
            ]
        return []

    # ------------------------------------------------------------------ #
    def detect_screenshot_change(
        self, old: CompetitorSnapshot, new: CompetitorSnapshot
    ) -> List[CompetitorChange]:
        changes: List[CompetitorChange] = []

        old_hashes = set(old.screenshot_hashes)
        new_hashes = set(new.screenshot_hashes)

        if old.screenshot_hashes and new.screenshot_hashes:
            added = new_hashes - old_hashes
            removed = old_hashes - new_hashes

            if added or removed:
                detail_parts = []
                if added:
                    detail_parts.append(f"{len(added)} new screenshot(s)")
                if removed:
                    detail_parts.append(f"{len(removed)} removed")
                changes.append(
                    CompetitorChange(
                        app_id=new.app_id,
                        change_type=CompetitorChangeType.SCREENSHOT_CHANGE,
                        description=f"Screenshot lineup changed — {', '.join(detail_parts)}",
                        impact="high",
                        confidence=0.85,
                        old_value=str(len(old.screenshot_hashes)),
                        new_value=str(len(new.screenshot_hashes)),
                    )
                )
        return changes

    # ------------------------------------------------------------------ #
    def detect_keyword_change(
        self, old: CompetitorSnapshot, new: CompetitorSnapshot
    ) -> List[CompetitorChange]:
        changes: List[CompetitorChange] = []

        old_kw = set(k.lower() for k in old.keywords)
        new_kw = set(k.lower() for k in new.keywords)

        if old.keywords and new.keywords:
            added = new_kw - old_kw
            removed = old_kw - new_kw

            if added or removed:
                detail = []
                if added:
                    detail.append(f"added: {', '.join(sorted(added)[:3])}")
                if removed:
                    detail.append(f"removed: {', '.join(sorted(removed)[:3])}")
                changes.append(
                    CompetitorChange(
                        app_id=new.app_id,
                        change_type=CompetitorChangeType.KEYWORD_CHANGE,
                        description=f"Keywords changed — {'; '.join(detail)}",
                        impact="medium",
                        confidence=0.8,
                        old_value=", ".join(old.keywords),
                        new_value=", ".join(new.keywords),
                    )
                )
        return changes

    # ------------------------------------------------------------------ #
    def detect_title_change(
        self, old: CompetitorSnapshot, new: CompetitorSnapshot
    ) -> List[CompetitorChange]:
        if old.title and new.title and old.title != new.title:
            return [
                CompetitorChange(
                    app_id=new.app_id,
                    change_type=CompetitorChangeType.TITLE_CHANGE,
                    description=f"Title changed: '{old.title}' → '{new.title}'",
                    impact="high",
                    confidence=0.95,
                    old_value=old.title,
                    new_value=new.title,
                )
            ]
        return []

    # ------------------------------------------------------------------ #
    def detect_ranking_surge(
        self, old: CompetitorSnapshot, new: CompetitorSnapshot
    ) -> List[CompetitorChange]:
        if old.ranking_position <= 0 or new.ranking_position <= 0:
            return []

        rank_change = old.ranking_position - new.ranking_position
        # Only report surges (positive = rising in rank)
        if rank_change >= 20:  # jumped 20+ positions
            return [
                CompetitorChange(
                    app_id=new.app_id,
                    change_type=CompetitorChangeType.RANKING_SURGE,
                    description=(
                        f"Ranking surged: #{old.ranking_position} → "
                        f"#{new.ranking_position} (+{rank_change} positions)"
                    ),
                    impact="high",
                    confidence=0.9,
                    old_value=str(old.ranking_position),
                    new_value=str(new.ranking_position),
                )
            ]
        return []


__all__ = ["ChangeDetectionEngine"]
