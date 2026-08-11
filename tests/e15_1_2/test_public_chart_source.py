"""
B — Public-chart (REAL data) market-opportunity source tests
============================================================
Covers AppleTopFreeSource:
  * live fetch via injected client -> real MarketOpportunity records,
  * cache-fallback when live fails but a cache snapshot exists,
  * safe-empty when both live and cache are unavailable (never raises),
  * genre/theme mapping helpers,
  * end-to-end: ingester writes the drop-in file, FactoryBrain consumes it.
All network is faked via an injected client; nothing hits the wire.
"""
from __future__ import annotations

import json
import os
import tempfile

from operation.factory_brain.growth_sources.public_chart_source import (
    AppleTopFreeSource, derive_theme, map_genre,
)
from operation.factory_brain.growth_sources.ingester import (
    MarketOpportunityIngester,
)
from operation.factory_brain.opportunity_intake import OpportunityIntake
from operation.factory_brain.models import MarketOpportunity
from operation.factory_brain import FactoryBrain
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.memory import PublishingMemory


# A faithful Apple RSS envelope (feed.results shape) used as the faked live
# response. Exercises genre mapping + title-keyword theme extraction.
def _rss(geo: str, apps):
    return {"feed": {"results": [
        {"id": f"{geo}{i}", "name": n, "genres": g,
         "genreIds": ["6014", str(7000 + i)], "artistName": "X",
         "url": f"https://x/{geo}/{i}"}
        for i, (n, g) in enumerate(apps, 1)
    ]}}


_US = [
    ("Block Blast!", ["Games", "Puzzle", "Casual"]),
    ("Wordscapes", ["Games", "Word"]),
    ("Merge Mansion", ["Games", "Puzzle", "Casual"]),
    ("Cooking Fever", ["Games", "Simulation"]),
    ("Match Masters", ["Games", "Board"]),
]
_GB = [
    ("Royal Match", ["Games", "Puzzle", "Casual"]),
    ("Wordle!", ["Games", "Word"]),
    ("Candy Crush Saga", ["Games", "Entertainment"]),
]


def test_live_fetch_via_client():
    def client(geo):
        return _rss(geo, _US if geo == "us" else _GB)
    src = AppleTopFreeSource(geos=("us", "gb"), client=client)
    opps = src.fetch()
    assert len(opps) == 8                       # 5 + 3 raw apps
    assert all(o.source == "public_chart" for o in opps)
    # live provenance tag
    assert all("[CHART]" in o.notes for o in opps)
    # mapping sanity: iterate and check known apps by opportunity_id
    ids = {o.opportunity_id: o for o in opps}
    # Wordscapes US, genre=Word -> word, theme=word -> chart_us_word_word
    assert ids["chart_us_word_word"].genre == "word"
    # Merge Mansion US, genre=Puzzle -> puzzle, theme=merge
    assert ids["chart_us_puzzle_merge"].genre == "puzzle"
    # Cooking Fever US, genre=Simulation -> idle, theme=cooking
    assert ids["chart_us_idle_cooking"].genre == "idle"
    # Match Masters US, genre=Board -> match, theme=match
    assert ids["chart_us_match_match"].genre == "match"


def test_cache_fallback_when_live_fails():
    # live raises; a cache snapshot exists -> fallback, tagged [CHART-CACHE]
    def boom(geo):
        raise RuntimeError("network down")
    with tempfile.TemporaryDirectory() as d:
        cache = os.path.join(d, "apple_topfree_us.json")
        json.dump(_rss("us", _US), open(cache, "w"), ensure_ascii=False)
        src = AppleTopFreeSource(geos=("us",),
                                 cache_dir=d, client=boom)
        opps = src.fetch()
        assert len(opps) == 5
        assert all("[CHART-CACHE]" in o.notes for o in opps)


def test_safe_empty_when_no_network_no_cache():
    def boom(geo):
        raise RuntimeError("no network")
    with tempfile.TemporaryDirectory() as d:
        src = AppleTopFreeSource(geos=("us", "gb"),
                                 cache_dir=d, client=boom)
        # must NOT raise; returns empty list
        assert src.fetch() == []


def test_mapping_helpers():
    assert map_genre(["Games", "Puzzle", "Casual"]) == "puzzle"
    assert map_genre(["Games", "Word"]) == "word"
    assert map_genre(["Games", "Simulation"]) == "idle"
    assert map_genre(["Games"]) == "casual"        # no sub-genre -> default
    assert derive_theme("Merge Mansion") == "merge"
    assert derive_theme("Wordscapes") == "word"
    assert derive_theme("Cooking Fever") == "cooking"
    # 'blast' is in THEME_KEYWORDS -> match
    assert derive_theme("Block Blast!") == "match"
    assert derive_theme("SOMEWEIRDNAME").islower()


def test_competition_is_per_genre_share():
    def client(geo):
        # us: 4 puzzle-of-5 -> puzzle competition high
        return _rss(geo, [
            ("P1", ["Games", "Puzzle"]),
            ("P2", ["Games", "Puzzle"]),
            ("P3", ["Games", "Puzzle"]),
            ("P4", ["Games", "Puzzle"]),
            ("W1", ["Games", "Word"]),
        ])
    src = AppleTopFreeSource(geos=("us",), client=client)
    opps = src.fetch()
    puzzle = [o for o in opps if o.genre == "puzzle"]
    word = [o for o in opps if o.genre == "word"]
    assert puzzle and word
    # 4/5 puzzle apps -> competition 0.8 ; 1/5 word -> 0.2
    assert abs(puzzle[0].competition - 0.8) < 1e-6
    assert abs(word[0].competition - 0.2) < 1e-6


def test_ingester_end_to_end_writes_dropin():
    def client(geo):
        return _rss(geo, _US if geo == "us" else _GB)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "market_opportunities.json")
        ing = MarketOpportunityIngester(
            [AppleTopFreeSource(geos=("us", "gb"), client=client)],
            out_path=out)
        res = ing.run()
        assert res["count"] > 0
        assert os.path.exists(out)
        # FactoryBrain zero-coupling consumption
        reg = GameRegistry(path=os.path.join(d, "cat.json"))
        brain = FactoryBrain(
            reg,
            memory=PublishingMemory(path=os.path.join(d, "mem.jsonl")),
            dropin_path=out,
            portfolio_state=os.path.join(d, "pf.json"),
            aso_trials=os.path.join(d, "tr.jsonl"))
        rep = brain.run_daily()
        assert len(rep.opportunities) == res["count"]
        assert rep.real_api_called is False
        # top opportunity should be the highest-ranked chart signal
        assert rep.opportunities[0].source == "public_chart"


def test_default_sources_include_public_chart():
    from operation.factory_brain.growth_sources.ingester import (
        build_default_sources, build_pipeline_sources)
    # build_default_sources is backward-compatible (mock + real)
    default_names = {type(s).__name__ for s in build_default_sources()}
    assert "MockMarketSource" in default_names
    assert "AppleTopFreeSource" not in default_names
    # build_pipeline_sources is the daily production set
    pipe_names = {type(s).__name__ for s in build_pipeline_sources()}
    assert "AppleTopFreeSource" in pipe_names
    assert "MockMarketSource" in pipe_names
    assert "RealMarketSource" in pipe_names
