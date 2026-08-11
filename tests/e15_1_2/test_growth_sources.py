"""
P2 — Growth source adapter tests
=================================
Covers the local Growth intake connector:
  * MockMarketSource (deterministic, runs today)
  * RealMarketSource (inert skeleton, safe, real-feed seam)
  * MarketOpportunityIngester (merge / dedupe / rank / persist)
  * End-to-end consumption by OpportunityIntake + FactoryBrain
"""
from __future__ import annotations

import json
import os
import tempfile

from operation.factory_brain.growth_sources import (
    MarketOpportunityIngester, MockMarketSource, RealMarketSource,
)
from operation.factory_brain.growth_sources.real_source import (
    PROVIDER_ADAPTERS, register_provider,
)
from operation.factory_brain.opportunity_intake import (
    DEFAULT_DROPIN, OpportunityIntake,
)
from operation.factory_brain.models import MarketOpportunity
from operation.factory_brain import FactoryBrain
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.memory import PublishingMemory


# --------------------------------------------------------------------------- #
def test_mock_source_ranked_desc():
    opps = MockMarketSource().fetch()
    assert len(opps) == 8
    assert all(o.opportunity_id for o in opps)
    assert all(o.source == "growth_os" for o in opps)
    # raw fetch is unsorted; ranking is the ingester's job. Verify the
    # highest-scored opportunity is the proven merge/vampire.
    best = max(opps, key=lambda o: o.score())
    assert best.genre == "merge" and best.theme == "vampire"
    # ingester output is sorted desc by score
    ing = MarketOpportunityIngester([MockMarketSource()])
    ranked = [MarketOpportunity.from_dict(d)
              for d in ing.run(dry_run=True)["opportunities"]]
    scores = [o.score() for o in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0].genre == "merge"


def test_real_not_configured_is_safe():
    # no credentials file at all -> empty, no network, no raise
    src = RealMarketSource(config_path="__does_not_exist__.json")
    assert src.fetch() == []
    assert src.status()["configured"] is False
    # enabled providers present but no adapter registered -> still inert
    with tempfile.TemporaryDirectory() as d:
        cfg = os.path.join(d, "market_sources.json")
        json.dump({"providers": {"appstore_rank": {
            "enabled": True, "endpoint": "https://x.test",
            "api_key_env": "X"}}}, open(cfg, "w"))
        s2 = RealMarketSource(config_path=cfg)
        assert s2.fetch() == []          # adapter missing -> inert
        assert s2.status()["configured"] is False


def test_real_seam_via_injected_client():
    # Prove the real-feed seam works once a provider adapter is registered.
    pid = "fake_provider"
    try:
        def _parse(raw):
            return [{
                "opportunity_id": f"{pid}_{r['genre']}",
                "genre": r["genre"], "theme": r.get("theme", ""),
                "keyword_trend": r["trend"], "competition": r["competition"],
                "ecpm_signal": r["ecpm"], "ltv_forecast": r["ltv"],
                "notes": "seam test",
            } for r in raw.get("results", [])]
        register_provider(pid, _parse)
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "market_sources.json")
            json.dump({"providers": {pid: {
                "enabled": True, "endpoint": "https://x.test",
                "api_key_env": "X"}}}, open(cfg, "w"))
            client = lambda pid_, pconf: {"results": [
                {"genre": "merge", "theme": "seam", "trend": 0.9,
                 "competition": 0.1, "ecpm": 0.9, "ltv": 0.9}]}
            src = RealMarketSource(config_path=cfg, client=client)
            opps = src.fetch()
            assert len(opps) == 1
            assert opps[0].opportunity_id == f"{pid}_merge"
            assert src.status()["configured"] is True
    finally:
        PROVIDER_ADAPTERS.pop(pid, None)


def test_ingester_dry_run_no_write():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "sub", "opps.json")
        ing = MarketOpportunityIngester([MockMarketSource()], out_path=out)
        res = ing.run(dry_run=True)
        assert res["count"] == 8
        assert not os.path.exists(out)        # dry-run must not persist


def test_ingester_write_and_intake_consume():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "market_opportunities.json")
        ing = MarketOpportunityIngester([MockMarketSource()], out_path=out)
        res = ing.run()
        assert res["count"] == 8
        assert os.path.exists(out)
        reg = GameRegistry(path=os.path.join(d, "cat.json"))
        intake = OpportunityIntake(reg, dropin_path=out)
        ranked = intake.collect()
        assert len(ranked) == 8
        assert ranked[0].genre == "merge"


def test_ingester_dedup_keeps_higher_score():
    class LowSource(MockMarketSource):
        def fetch_raw(self):
            # same genre/theme as mock_merge_vampire but weaker
            return [{"opportunity_id": "low", "genre": "merge",
                     "theme": "vampire", "keyword_trend": 0.1,
                     "competition": 0.9, "ecpm_signal": 0.1,
                     "ltv_forecast": 0.1}]
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "opps.json")
        ing = MarketOpportunityIngester(
            [MockMarketSource(), LowSource()], out_path=out)
        res = ing.run()
        # merge/vampire collapsed to ONE entry, keeping the higher score
        merged = {(o["genre"], o["theme"]) for o in res["opportunities"]}
        assert ("merge", "vampire") in merged
        vamp = next(o for o in res["opportunities"]
                    if o["genre"] == "merge" and o["theme"] == "vampire")
        assert vamp["opportunity_id"] == "mock_merge_vampire"  # higher kept
        assert res["count"] == 8          # 8 distinct (genre,theme) pairs


def test_factory_brain_consumes_dropin():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "market_opportunities.json")
        MarketOpportunityIngester([MockMarketSource()], out_path=out).run()
        reg = GameRegistry(path=os.path.join(d, "cat.json"))   # empty fleet
        brain = FactoryBrain(
            reg,
            memory=PublishingMemory(path=os.path.join(d, "mem.jsonl")),
            dropin_path=out,
            portfolio_state=os.path.join(d, "pf.json"),
            aso_trials=os.path.join(d, "tr.jsonl"))
        rep = brain.run_daily()
        assert len(rep.opportunities) == 8
        assert len(rep.specs) >= 1        # top opportunities -> specs
        assert rep.real_api_called is False
        # specs derive from the highest-scored opportunity
        assert rep.specs[0].genre == "merge"
