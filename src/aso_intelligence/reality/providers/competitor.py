"""E16.6.2 — Competitor reality provider.

Reuses E16.6.1's first-version ``NullCompetitorProvider`` (the same object the
manual ``collector`` path uses), so the connector can call the established
``load_competitors(game_id, period) -> List[CompetitorSnapshot]`` contract.

Future versions implement ``CompetitorProvider`` against Sensor Tower /
data.ai / AppTweak / AppMagic and return real ``CompetitorSnapshot`` rows.
"""

from __future__ import annotations

from ...collector import NullCompetitorProvider  # E16.6.1 first-version

__all__ = ["NullCompetitorProvider"]
