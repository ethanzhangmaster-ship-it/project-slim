"""Shared builders for E15.1.2 tests."""
import json
import os

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.product_profile import GameProduct
from operation.publishing_factory.memory import PublishingMemory

from operation.factory_brain import FactoryBrain, MarketOpportunity


def game(game_id="p001", genre="merge", monetization="hybrid",
         status="published", package=None, metrics=None, **kw):
    return GameProduct(
        game_id=game_id,
        package_name=package or f"com.lf.{genre}.theme{game_id[-1]}",
        display_name=kw.pop("display_name", game_id.title()),
        genre=genre, monetization=monetization, status=status,
        metrics=metrics or {}, **kw)


def registry(tmp_path, games=()):
    reg = GameRegistry(path=str(tmp_path / "catalog.json"))
    for g in games:
        reg.add(g)
    return reg


def opportunity(oid="opp1", genre="merge", theme="witch", score_hint=0.7,
                **kw):
    """score_hint drives all sub-scores to land near the hint."""
    return MarketOpportunity(
        opportunity_id=oid, genre=genre, theme=theme,
        keyword_trend=kw.pop("keyword_trend", score_hint),
        competition=kw.pop("competition", 1.0 - score_hint),
        ecpm_signal=kw.pop("ecpm_signal", score_hint),
        ltv_forecast=kw.pop("ltv_forecast", score_hint), **kw)


def write_dropin(tmp_path, opps):
    p = str(tmp_path / "opps.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump([o.to_dict() if hasattr(o, "to_dict") else o
                   for o in opps], fh)
    return p


def brain(tmp_path, games=(), opps=None, memory=None, capacity=3):
    reg = registry(tmp_path, games)
    dropin = (write_dropin(tmp_path, opps) if opps is not None
              else str(tmp_path / "none.json"))
    mem = memory or PublishingMemory(path=str(tmp_path / "pubmem.jsonl"))
    return FactoryBrain(
        reg, memory=mem, dropin_path=dropin,
        portfolio_state=str(tmp_path / "portfolio.json"),
        aso_trials=str(tmp_path / "trials.jsonl"),
        capacity=capacity)
