"""
E15.1.2 — Mock market-opportunity source
=========================================

A curated, deterministic snapshot of overseas-casual-market signals so the
Factory Brain closed loop is demonstrable today. Every record carries the
exact fields ``MarketOpportunity`` expects, plus a ``[MOCK]`` note so it is
never mistaken for real market intelligence.

Swap this out by enabling ``RealMarketSource`` with a real provider adapter
(see ``real_source.py``) — the rest of the pipeline is identical.
"""
from __future__ import annotations

from typing import Dict, List

from .base import MarketSource
from operation.factory_brain.models import MarketOpportunity

# (genre, theme, keyword_trend, competition, ecpm_signal, ltv_forecast, note)
# competition: 0 = empty market, 1 = saturated.
_RAW: List[Dict] = [
    {"opportunity_id": "mock_merge_vampire", "genre": "merge", "theme": "vampire",
     "keyword_trend": 0.85, "competition": 0.25, "ecpm_signal": 0.80,
     "ltv_forecast": 0.75, "target_geos": ["US", "DE", "JP"],
     "notes": "[MOCK] proven in our fleet (Merge Monster) + US casual chart hold"},
    {"opportunity_id": "mock_word_zen", "genre": "word", "theme": "zen",
     "keyword_trend": 0.80, "competition": 0.20, "ecpm_signal": 0.70,
     "ltv_forecast": 0.70, "target_geos": ["US"],
     "notes": "[MOCK] word + relax niche trending on TikTok (1.2M views/wk)"},
    {"opportunity_id": "mock_puzzle_block", "genre": "puzzle", "theme": "block",
     "keyword_trend": 0.70, "competition": 0.35, "ecpm_signal": 0.65,
     "ltv_forecast": 0.60, "target_geos": ["US", "KR"],
     "notes": "[MOCK] block-puzzle evergreen; stable top-50 US casual"},
    {"opportunity_id": "mock_idle_tycoon", "genre": "idle", "theme": "tycoon",
     "keyword_trend": 0.75, "competition": 0.40, "ecpm_signal": 0.60,
     "ltv_forecast": 0.65, "target_geos": ["US", "BR"],
     "notes": "[MOCK] idle-tycoon CPI softening, eCPM holding"},
    {"opportunity_id": "mock_sort_color", "genre": "sort", "theme": "color",
     "keyword_trend": 0.82, "competition": 0.30, "ecpm_signal": 0.70,
     "ltv_forecast": 0.68, "target_geos": ["US"],
     "notes": "[MOCK] sort/color emerging hypercasual->casual migration"},
    {"opportunity_id": "mock_draw_puzzle", "genre": "draw", "theme": "puzzle",
     "keyword_trend": 0.68, "competition": 0.45, "ecpm_signal": 0.60,
     "ltv_forecast": 0.55, "target_geos": ["US", "ID"],
     "notes": "[MOCK] draw-puzzle mid-tier; moderate competition"},
    {"opportunity_id": "mock_cooking_rest", "genre": "cooking", "theme": "restaurant",
     "keyword_trend": 0.72, "competition": 0.50, "ecpm_signal": 0.62,
     "ltv_forecast": 0.60, "target_geos": ["US"],
     "notes": "[MOCK] cooking/restaurant steady; bundle with Hospital Fever"},
    {"opportunity_id": "mock_match_candy", "genre": "match", "theme": "candy",
     "keyword_trend": 0.60, "competition": 0.80, "ecpm_signal": 0.55,
     "ltv_forecast": 0.50, "target_geos": ["US"],
     "notes": "[MOCK] match-3 saturated; low score, deprioritise"},
]


class MockMarketSource(MarketSource):
    """Deterministic stand-in Growth feed. Zero dependencies, always on."""
    name = "mock_market"
    kind = "mock"

    def fetch_raw(self) -> List[dict]:
        return list(_RAW)

    def normalize(self, raw: List[dict]) -> List[MarketOpportunity]:
        out: List[MarketOpportunity] = []
        for d in raw:
            if not isinstance(d, dict) or "opportunity_id" not in d:
                continue
            o = MarketOpportunity.from_dict(d)
            o.source = "growth_os"          # drop-in semantics
            out.append(o)
        return out


__all__ = ["MockMarketSource"]
