"""
E15.1.2 — Autonomous Game Factory Brain — Acceptance Gate
==========================================================

Validates the closed loop:

    Growth OS -> Publishing Factory -> Revenue OS -> next game

Sections:
  1. Opportunity Intake (drop-in + fleet)
  2. Product Spec Generator
  3. Portfolio Manager (lifecycle + ROAS ladder)
  4. Success Pattern Miner
  5. ASO Bandit
  6. Store Experiment Planner
  7. FactoryBrain closed loop + safety
  8. Opportunity Predictor (CPI / D30 / D90 ROAS)
  9. Blueprint Generator (core loop / IAA / IAP / meta)
 10. Game Decision Engine (KEEP / SCALE / KILL + payback)
 11. Real Fleet Bridge (Revenue OS -> Factory Brain, IAA mode)

Target: >= 120 checks, 0 failures -> FACTORY BRAIN READY
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.product_profile import GameProduct
from operation.publishing_factory.memory import (
    PublishingMemory, PublishingMemoryEntry,
)
from operation.factory_brain import (
    AsoVariant, FactoryBrain, MarketOpportunity, SuccessPattern, Verdict,
)
from operation.factory_brain.aso_bandit import AsoBandit
from operation.factory_brain.blueprint_generator import BlueprintGenerator
from operation.factory_brain.decision_engine import (
    GameDecisionEngine, payback_days,
)
from operation.factory_brain.opportunity_intake import OpportunityIntake
from operation.factory_brain.opportunity_predictor import OpportunityPredictor
from operation.factory_brain.pattern_miner import PatternMiner
from operation.factory_brain.portfolio_manager import PortfolioManager
from operation.factory_brain.spec_generator import SpecGenerator
from operation.factory_brain.store_experiment_planner import (
    StoreExperimentPlanner,
)

_passed = 0
_failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}" + (f" -- {detail}" if detail else ""))
    else:
        _failed += 1
        print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))


def _game(gid, genre="merge", monetization="hybrid", status="published",
          package=None, metrics=None, platforms=None):
    return GameProduct(
        game_id=gid, package_name=package or f"com.lf.{genre}.{gid}",
        display_name=gid.title(), genre=genre, monetization=monetization,
        status=status, metrics=metrics or {},
        platforms=platforms or ["google_play"])


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="e15_1_2_")
    j = lambda *p: os.path.join(tmp, *p)  # noqa: E731

    # ================================================================= #
    print("\n[1] Opportunity Intake")
    # ================================================================= #
    o = MarketOpportunity("o1", "merge", theme="witch", keyword_trend=0.8,
                          competition=0.3, ecpm_signal=0.7,
                          ltv_forecast=0.6)
    check("score composite", abs(o.score() - 0.71) < 1e-9, f"{o.score()}")
    check("score in [0,1]",
          0.0 <= MarketOpportunity("x", "m", keyword_trend=9,
                                   competition=-3, ecpm_signal=8,
                                   ltv_forecast=7).score() <= 1.0)
    check("competition inverted",
          MarketOpportunity("a", "m", competition=0.0).score()
          > MarketOpportunity("b", "m", competition=1.0).score())
    check("roundtrip dict",
          MarketOpportunity.from_dict(o.to_dict()).theme == "witch")

    reg = GameRegistry(path=j("cat.json"))
    reg.add(_game("w1", metrics={"revenue_per_dau": 0.06,
                                 "store_cvr": 0.2}))
    reg.add(_game("dev1", status="development",
                  metrics={"revenue_per_dau": 0.9}))
    with open(j("opps.json"), "w", encoding="utf-8") as fh:
        json.dump([o.to_dict(),
                   {"opportunity_id": "weak", "genre": "action",
                    "keyword_trend": 0.05, "competition": 0.95,
                    "ecpm_signal": 0.05, "ltv_forecast": 0.05}], fh)
    intake = OpportunityIntake(reg, dropin_path=j("opps.json"))
    check("dropin loaded", len(intake.load_dropin()) == 2)
    check("dropin source tag",
          all(x.source == "growth_os" for x in intake.load_dropin()))
    fleet_opps = intake.derive_from_fleet()
    check("fleet-derived signal", len(fleet_opps) == 1)
    check("fleet source tag", fleet_opps[0].source == "fleet")
    check("unpublished excluded from fleet signals",
          all("dev1" not in x.notes for x in fleet_opps))
    ranked = intake.collect()
    check("collect ranked desc",
          all(ranked[i].score() >= ranked[i + 1].score()
              for i in range(len(ranked) - 1)))
    check("collect dedupes by (genre,theme)",
          len({(x.genre, x.theme) for x in ranked}) == len(ranked))
    missing = OpportunityIntake(reg, dropin_path=j("nope.json"))
    check("missing dropin ok", missing.load_dropin() == [])
    with open(j("bad.json"), "w", encoding="utf-8") as fh:
        fh.write("{broken")
    bad = OpportunityIntake(reg, dropin_path=j("bad.json"))
    check("malformed dropin ok", bad.load_dropin() == [])

    # ================================================================= #
    print("\n[2] Product Spec Generator")
    # ================================================================= #
    gen = SpecGenerator()
    spec = gen.generate(o)
    check("spec generated", spec is not None)
    check("spec genre/theme", spec.genre == "merge" and spec.theme == "witch")
    check("weak opp -> None",
          gen.generate(MarketOpportunity("w", "action", keyword_trend=0.05,
                                         competition=0.95,
                                         ecpm_signal=0.05,
                                         ltv_forecast=0.05)) is None)
    check("theme fallback",
          gen.generate(MarketOpportunity("t", "merge", keyword_trend=0.8,
                                         competition=0.2, ecpm_signal=0.7,
                                         ltv_forecast=0.7)).theme
          == "fantasy")
    d = spec.to_dict()
    check("yaml shape: product",
          set(d["product"]) == {"genre", "theme", "target_geo"})
    check("yaml shape: monetization", "type" in d["monetization"])
    check("yaml shape: aso keywords", isinstance(d["aso"]["keywords"], list))
    check("keywords deduped",
          len(spec.aso_keywords) == len(set(spec.aso_keywords)))
    check("hybrid gets starter_pack", spec.starter_pack is True)

    prior = SuccessPattern("pat_merge_hybrid", "merge", theme="witch",
                           monetization="hybrid", rewarded_focus=True,
                           success_rate=0.18, sample=5, weight=1.45)
    boosted = SpecGenerator(patterns=[prior]).generate(o)
    check("prior boosts confidence", boosted.confidence > spec.confidence,
          f"{spec.confidence} -> {boosted.confidence}")
    check("prior notes attached", bool(boosted.pattern_notes))
    check("confidence capped", boosted.confidence <= 1.0)
    wrong = SuccessPattern("pat_word_iaa", "word", weight=1.5,
                           success_rate=0.5, sample=9)
    check("wrong-genre prior ignored",
          SpecGenerator(patterns=[wrong]).generate(o).pattern_notes == [])

    batch = SpecGenerator().generate_batch(
        [MarketOpportunity(f"b{i}", "merge", theme=f"t{i}",
                           keyword_trend=0.8, competition=0.2,
                           ecpm_signal=0.7, ltv_forecast=0.7)
         for i in range(5)], capacity=3)
    check("batch capacity", len(batch) == 3)
    mixed = SpecGenerator().generate_batch(
        [MarketOpportunity("weakb", "action", keyword_trend=0.05,
                           competition=0.95, ecpm_signal=0.05,
                           ltv_forecast=0.05),
         MarketOpportunity("strongb", "word", theme="zen",
                           keyword_trend=0.8, competition=0.2,
                           ecpm_signal=0.7, ltv_forecast=0.7)], capacity=3)
    check("batch skips weak keeps scanning",
          len(mixed) == 1 and mixed[0].opportunity_id == "strongb")
    prior_iap = SuccessPattern("pat_merge_iap", "merge", theme="witch",
                               monetization="iap", success_rate=0.3,
                               sample=6, weight=1.4)
    check("prior overrides monetization",
          SpecGenerator(patterns=[prior_iap]).generate(o).monetization
          == "iap")
    check("word genre defaults iaa no starter",
          (lambda s: s.monetization == "iaa" and s.starter_pack is False)(
              SpecGenerator().generate(
                  MarketOpportunity("wd", "word", theme="travel",
                                    keyword_trend=0.8, competition=0.2,
                                    ecpm_signal=0.7, ltv_forecast=0.7))))

    gp = SpecGenerator.to_game_product(spec)
    check("to_game_product id", gp.game_id.startswith("g_"))
    check("to_game_product dev status", gp.status == "development")
    check("to_game_product package",
          gp.package_name == "com.leanfactory.merge.witch")
    o_jp = MarketOpportunity("jp", "merge", theme="witch",
                             target_geos=["US", "JP"], keyword_trend=0.8,
                             competition=0.2, ecpm_signal=0.7,
                             ltv_forecast=0.7)
    check("JP geo -> ja-JP locale",
          "ja-JP" in SpecGenerator.to_game_product(
              SpecGenerator().generate(o_jp)).locales)

    # ================================================================= #
    print("\n[3] Portfolio Manager")
    # ================================================================= #
    reg3 = GameRegistry(path=j("cat3.json"))
    for gid, met in [("u1", {"roas": 1.4}), ("u2", {"roas": 0.7}),
                     ("u3", {"roas": 0.2}), ("s1", {"roas": 0.25}),
                     ("mix1", {"ad_revenue_share": 0.9}),
                     ("mix2", {"iap_revenue_share": 0.6}),
                     ("idle1", {})]:
        reg3.add(_game(gid, metrics=met))
    pm = PortfolioManager(reg3, state_path=j("pf.json"))
    for gid in ("u1", "u2", "u3"):
        pm.set_stage(gid, "ua_test")
    pm.set_stage("s1", "scale")
    acts = {dd.game_id: dd.action for dd in pm.daily_decisions()}
    check("ROAS>1 -> increase_budget", acts["u1"] == "increase_budget")
    check("ROAS mid -> keep_optimizing", acts["u2"] == "keep_optimizing")
    check("ROAS<0.3 -> stop_ua", acts["u3"] == "stop_ua")
    check("ROAS<0.3 at scale -> kill", acts["s1"] == "kill")
    check("ad-heavy -> boost_iaa", acts["mix1"] == "boost_iaa")
    check("iap-heavy -> boost_iap", acts["mix2"] == "boost_iap")
    check("no signal -> hold", acts["idle1"] == "hold")
    check("all manual apply",
          all(dd.requires_manual_apply for dd in pm.daily_decisions()))
    check("default stage from status", pm.stage_of("mix1") == "soft_launch")
    check("advance order", PortfolioManager(reg3, state_path=j("pf2.json"))
          .advance("idle1") in ("ua_test",))
    pm.kill("u3")
    check("killed silent",
          "u3" not in {dd.game_id for dd in pm.daily_decisions()})
    pm2 = PortfolioManager(reg3, state_path=j("pf.json"))
    check("stage persisted", pm2.stage_of("s1") == "scale")
    try:
        pm.set_stage("u1", "warp")
        check("invalid stage rejected", False)
    except ValueError:
        check("invalid stage rejected", True)
    summ = pm.portfolio_summary()
    check("summary totals", summ["total"] == 7)
    reg3.add(_game("grey1", metrics={"roas": 0.4}))
    pm.set_stage("grey1", "ua_test")
    grey = next(dd for dd in pm.daily_decisions()
                if dd.game_id == "grey1")
    check("ROAS grey zone -> watch",
          grey.action == "keep_optimizing" and "grey" in grey.reason)
    reg3.add(_game("ready1", status="ready", metrics={}))
    pm.set_stage("ready1", "prototype")
    check("prelaunch ready -> advance",
          next(dd for dd in pm.daily_decisions()
               if dd.game_id == "ready1").action == "advance")
    with open(j("pf_broken.json"), "w", encoding="utf-8") as fh:
        fh.write("{broken")
    pm_broken = PortfolioManager(reg3, state_path=j("pf_broken.json"))
    check("corrupt state file recovers",
          pm_broken.stage_of("mix1") == "soft_launch")
    check("decision snapshot numeric",
          all(isinstance(v, float)
              for dd in pm.daily_decisions()
              for v in dd.metric_snapshot.values()))

    # ================================================================= #
    print("\n[4] Success Pattern Miner")
    # ================================================================= #
    reg4 = GameRegistry(path=j("cat4.json"))
    reg4.add(_game("m1", metrics={"revenue_per_dau": 0.06}))
    reg4.add(_game("m2", metrics={"revenue_per_dau": 0.07}))
    reg4.add(_game("l1", genre="puzzle", monetization="iaa",
                   metrics={"revenue_per_dau": 0.001}))
    reg4.add(_game("l2", genre="puzzle", monetization="iaa",
                   metrics={"revenue_per_dau": 0.002}))
    reg4.add(_game("d1", status="development",
                   metrics={"revenue_per_dau": 0.9}))
    mem4 = PublishingMemory(path=j("mem4.jsonl"))
    mem4.record(PublishingMemoryEntry(game_id="m1", kind="screenshot_style",
                                      key="merge_fantasy", outcome="good",
                                      value=0.25, genre="merge"))
    miner = PatternMiner(reg4, memory=mem4)
    pats = miner.mine()
    check("two patterns mined", len(pats) == 2)
    win = next(p for p in pats if p.pattern_id == "pat_merge_hybrid")
    lose = next(p for p in pats if p.pattern_id == "pat_puzzle_iaa")
    check("winner rate 1.0", win.success_rate == 1.0)
    check("winner weight 1.5", win.weight == 1.5)
    check("loser weight 0.5", lose.weight == 0.5)
    check("unpublished excluded", all(p.sample == 2 for p in pats))
    check("theme recovered from memory", win.theme == "fantasy")
    check("ranked winner first", pats[0] is win)
    check("summary evidence", miner.summarize()["with_evidence"] == 2)

    # ================================================================= #
    print("\n[5] ASO Bandit")
    # ================================================================= #
    bd = AsoBandit(path=j("trials.jsonl"),
                   memory=PublishingMemory(path=j("mem5.jsonl")))
    bd.register(AsoVariant("va", "p1", "title", "Build Your Kingdom"))
    bd.register(AsoVariant("vb", "p1", "title", "Merge Magic Castle"))
    bd.observe("p1", "title", "va", 1000, 180)
    check("still exploring -> None", bd.pick_winner("p1", "title") is None)
    bd.observe("p1", "title", "vb", 1000, 250)
    w = bd.pick_winner("p1", "title", genre="merge")
    check("winner committed", w is not None and w.payload
          == "Merge Magic Castle")
    check("winner cvr", w.cvr() == 0.25)
    check("winner memorized",
          len(bd.memory.recall(kind="aso_variant", genre="merge")) == 1)
    check("register idempotent",
          len(bd.variants("p1", "title")) == 2)
    bd.register(AsoVariant("c1", "p1", "icon", "bold"))
    bd.register(AsoVariant("c2", "p1", "icon", "minimal"))
    bd.observe("p1", "icon", "c1", 600, 60)
    bd.observe("p1", "icon", "c2", 600, 63)
    check("too-close -> no winner", bd.pick_winner("p1", "icon") is None)
    try:
        bd.observe("p1", "title", "va", 10, 20)
        check("invalid observation rejected", False)
    except ValueError:
        check("invalid observation rejected", True)
    check("status exploring flag settles",
          bd.status("p1", "icon")["exploring"] is False,
          "both icon variants >= min impressions")
    check("kind isolation", len(bd.variants("p1", "icon")) == 2)
    bd.register(AsoVariant("solo", "p9", "title", "Only One"))
    bd.observe("p9", "title", "solo", 2000, 400)
    check("single variant -> no winner",
          bd.pick_winner("p9", "title") is None)
    check("game isolation",
          len(bd.variants("p9", "title")) == 1
          and len(bd.variants("p1", "title")) == 2)
    check("additive observation totals",
          bd.variants("p9", "title")[0].impressions == 2000)

    # ================================================================= #
    print("\n[6] Store Experiment Planner")
    # ================================================================= #
    sp = StoreExperimentPlanner()
    dropg = _game("drop1", metrics={"store_cvr": 0.08,
                                    "baseline_cvr": 0.15})
    check("relative drop triggers", sp.needs_experiment(dropg))
    check("absolute floor triggers",
          sp.needs_experiment(_game("d2", metrics={"store_cvr": 0.05})))
    check("healthy no trigger",
          not sp.needs_experiment(_game("h1", metrics={
              "store_cvr": 0.3, "baseline_cvr": 0.25})))
    check("no cvr no trigger", not sp.needs_experiment(_game("n1")))
    plan = sp.plan(dropg)
    check("5 icon variants", len(plan.icon_variants) == 5)
    check("3 screenshot variants", len(plan.screenshot_variants) == 3)
    check("5 copy variants", len(plan.copy_variants) == 5)
    check("manual apply", plan.requires_manual_apply is True)
    check("plan serializable", bool(json.dumps(plan.to_dict())))
    multi = _game("mp", metrics={"store_cvr": 0.05},
                  platforms=["google_play", "app_store"])
    check("per-platform plans",
          {p.store for p in sp.plan_fleet([multi])}
          == {"google_play", "app_store"})

    # ================================================================= #
    print("\n[7] FactoryBrain closed loop + safety")
    # ================================================================= #
    reg7 = GameRegistry(path=j("cat7.json"))
    reg7.add(_game("p1", package="com.lf.merge.vampire",
                   metrics={"revenue_per_dau": 0.08, "roas": 1.4}))
    reg7.add(_game("p2", genre="simulation", monetization="iaa",
                   package="com.lf.simulation.hospital",
                   metrics={"revenue_per_dau": 0.004, "store_cvr": 0.08,
                            "baseline_cvr": 0.15}))
    reg7.add(_game("p3", genre="puzzle", monetization="iaa",
                   package="com.lf.puzzle.block", metrics={"roas": 0.2}))
    with open(j("opps7.json"), "w", encoding="utf-8") as fh:
        json.dump([o.to_dict(),
                   {"opportunity_id": "z", "genre": "word", "theme": "zen",
                    "keyword_trend": 0.5, "competition": 0.5,
                    "ecpm_signal": 0.4, "ltv_forecast": 0.4}], fh)
    brain = FactoryBrain(reg7,
                         memory=PublishingMemory(path=j("mem7.jsonl")),
                         dropin_path=j("opps7.json"),
                         portfolio_state=j("pf7.json"),
                         aso_trials=j("tr7.jsonl"))
    brain.portfolio.set_stage("p1", "ua_test")
    brain.portfolio.set_stage("p3", "ua_test")
    rep = brain.run_daily()
    check("report has opportunities", len(rep.opportunities) >= 2)
    check("report has specs", len(rep.specs) >= 1)
    check("report has decisions", len(rep.decisions) == 3)
    check("report has patterns", len(rep.patterns) >= 1)
    check("store exp for p2",
          any(e.game_id == "p2" for e in rep.store_experiments))
    check("decision p1 scale-up",
          next(dd for dd in rep.decisions
               if dd.game_id == "p1").action == "increase_budget")
    check("decision p3 stop-ua",
          next(dd for dd in rep.decisions
               if dd.game_id == "p3").action == "stop_ua")
    check("real_api_called False", rep.real_api_called is False)
    check("brain property False", brain.real_api_called is False)
    check("report json-serializable", bool(json.dumps(rep.to_dict())))
    n0 = reg7.count()
    rep2 = brain.run_daily(register_specs=True)
    check("register adds to fleet", reg7.count() == n0 + len(rep2.specs))
    check("registered as development",
          all(reg7.get(s.spec_id.replace("spec_", "g_")).status
              == "development" for s in rep2.specs))
    check("registered stage idea",
          all(brain.portfolio.stage_of(s.spec_id.replace("spec_", "g_"))
              == "idea" for s in rep2.specs))
    n1 = reg7.count()
    brain.run_daily(register_specs=True)
    check("re-register idempotent", reg7.count() == n1)
    # fleet ceiling
    regf = GameRegistry(path=j("catf.json"))
    for i in range(50):
        regf.add(_game(f"f{i:03d}", genre="idle",
                       package=f"com.lf.idle.t{i}"))
    brainf = FactoryBrain(regf, dropin_path=j("opps7.json"),
                          portfolio_state=j("pff.json"),
                          aso_trials=j("trf.jsonl"),
                          memory=PublishingMemory(path=j("memf.jsonl")))
    check("50-game ceiling blocks specs",
          brainf.run_daily().specs == [])
    check("50-game decisions complete",
          len(brainf.run_daily().decisions) == 50)
    # dedupe against operated theme
    regd = GameRegistry(path=j("catd.json"))
    regd.add(_game("witch1", package="com.lf.merge.witch"))
    braind = FactoryBrain(regd, dropin_path=j("opps7.json"),
                          portfolio_state=j("pfd.json"),
                          aso_trials=j("trd.jsonl"),
                          memory=PublishingMemory(path=j("memd.jsonl")))
    check("operated (genre,theme) never re-proposed",
          all(not (s.genre == "merge" and s.theme == "witch")
              for s in braind.run_daily().specs))
    # memory loop: screenshot winner -> pattern theme -> spec theme
    memL = PublishingMemory(path=j("memL.jsonl"))
    memL.record(PublishingMemoryEntry(
        game_id="w1", kind="screenshot_style", key="merge_fantasy",
        outcome="good", value=0.3, genre="merge"))
    regL = GameRegistry(path=j("catL.json"))
    regL.add(_game("w1", package="com.lf.merge.a",
                   metrics={"revenue_per_dau": 0.06}))
    regL.add(_game("w2", package="com.lf.merge.b",
                   metrics={"revenue_per_dau": 0.07}))
    brainL = FactoryBrain(regL, memory=memL, dropin_path=j("nope.json"),
                          portfolio_state=j("pfL.json"),
                          aso_trials=j("trL.jsonl"))
    repL = brainL.run_daily()
    patL = next(p for p in repL.patterns
                if p.pattern_id == "pat_merge_hybrid")
    check("memory loop: style winner -> pattern theme",
          patL.theme == "fantasy")
    check("no-dropin runs on fleet signals",
          any(x.source == "fleet" for x in repL.opportunities))
    # empty world
    brainE = FactoryBrain(GameRegistry(path=j("catE.json")),
                          memory=PublishingMemory(path=j("memE.jsonl")),
                          dropin_path=j("nope.json"),
                          portfolio_state=j("pfE.json"),
                          aso_trials=j("trE.jsonl"))
    repE = brainE.run_daily()
    check("empty world no crash",
          repE.decisions == [] and repE.patterns == [])
    check("empty world serializable", bool(json.dumps(repE.to_dict())))
    check("E15.1.1 GameProduct contract reused",
          type(SpecGenerator.to_game_product(spec)).__name__
          == "GameProduct")
    check("report carries predictions", len(rep.predictions) >= 2)
    check("report carries blueprints", len(rep.blueprints) == len(rep.specs))
    check("prediction ids match opportunities",
          {p.opportunity_id for p in rep.predictions}
          == {oo.opportunity_id for oo in rep.opportunities})

    # ================================================================= #
    print("\n[8] Opportunity Predictor")
    # ================================================================= #
    pred = OpportunityPredictor()
    strong = MarketOpportunity("s", "merge", theme="vampire",
                               keyword_trend=0.9, competition=0.1,
                               ecpm_signal=0.9, ltv_forecast=0.9)
    weakp = MarketOpportunity("w", "merge", keyword_trend=0.1,
                              competition=0.9, ecpm_signal=0.1,
                              ltv_forecast=0.1)
    ps, pw = pred.predict(strong), pred.predict(weakp)
    check("prediction ids preserved", ps.opportunity_id == "s")
    check("cpi positive", ps.cpi > 0)
    check("cpi bounded", 0.30 <= pred.predict(weakp).cpi <= 4.00)
    check("competition raises cpi", pw.cpi > ps.cpi)
    check("strong monetization higher D30", ps.d30_roas > pw.d30_roas)
    check("D90 matures over D30", ps.d90_roas >= ps.d30_roas)
    check("payback_ok tracks d90",
          ps.payback_ok == (ps.d90_roas >= 1.0))
    check("confidence in range", 0.0 <= ps.confidence <= 1.0)
    check("predictor deterministic",
          pred.predict(strong).to_dict() == ps.to_dict())
    check("predict_batch length",
          len(pred.predict_batch([strong, weakp])) == 2)
    check("prediction serializable", bool(json.dumps(ps.to_dict())))

    # ================================================================= #
    print("\n[9] Blueprint Generator")
    # ================================================================= #
    bg = BlueprintGenerator()
    sp_h = SpecGenerator().generate(strong)          # merge/vampire, hybrid
    bp = bg.build(sp_h)
    check("blueprint id derived", bp.blueprint_id.startswith("bp_"))
    check("core loop genre-specific",
          bp.core_loop == ["merge", "reward", "unlock"])
    check("hybrid has iaa+iap", bool(bp.iaa) and bool(bp.iap))
    check("meta weaves theme", "vampire" in bp.meta)
    sp_iaa = SpecGenerator().generate(
        MarketOpportunity("wd", "word", theme="travel", keyword_trend=0.8,
                          competition=0.2, ecpm_signal=0.7,
                          ltv_forecast=0.7))
    bp_iaa = bg.build(sp_iaa)
    check("pure-iaa adds banner no iap",
          "banner" in bp_iaa.iaa and bp_iaa.iap == [])
    unknown = BlueprintGenerator().build(
        SpecGenerator().generate(
            MarketOpportunity("rh", "casual", theme="candy",
                              keyword_trend=0.8, competition=0.2,
                              ecpm_signal=0.7, ltv_forecast=0.7)))
    check("known genre has meta", bool(unknown.meta))
    check("blueprint aso passthrough",
          bp.aso_keywords == sp_h.aso_keywords)
    gp_bp = BlueprintGenerator.to_game_product(bp, monetization="hybrid")
    check("blueprint->GameProduct development", gp_bp.status == "development")
    check("blueprint->GameProduct seeds selling points",
          bool(gp_bp.selling_points))
    check("build_batch maps all",
          len(bg.build_batch([sp_h, sp_iaa])) == 2)
    check("blueprint serializable", bool(json.dumps(bp.to_dict())))

    # ================================================================= #
    print("\n[10] Game Decision Engine")
    # ================================================================= #
    de = GameDecisionEngine()
    check("payback zero cpi -> 0", payback_days(0.0, 0.3, 0.4, 0.1) == 0.0)
    check("payback zero arpdau -> never",
          payback_days(1.0, 0.0, 0.4, 0.1) > 365)
    check("payback higher cpi slower",
          payback_days(2.0, 0.3, 0.4, 0.14)
          > payback_days(1.0, 0.3, 0.4, 0.14))
    check("payback better retention faster",
          payback_days(1.0, 0.3, 0.5, 0.2)
          < payback_days(1.0, 0.3, 0.3, 0.06))
    check("no economics -> None",
          de.evaluate(_game("ne", metrics={"d1_retention": 0.4})) is None)
    d_scale = de.evaluate(_game("sc", metrics={
        "cpi": 1.0, "arpdau": 0.35, "d1_retention": 0.42,
        "d7_retention": 0.14, "roas": 1.3}))
    check("scale verdict", d_scale.verdict == Verdict.SCALE.value)
    check("scale budget +30", d_scale.budget_delta_pct == 30.0)
    check("kill bleeding roas",
          de.evaluate(_game("bl", metrics={
              "cpi": 2.0, "arpdau": 0.05, "d1_retention": 0.30,
              "d7_retention": 0.09, "roas": 0.2})).verdict
          == Verdict.KILL.value)
    check("proven-profit not killed by projection",
          de.evaluate(_game("pp", metrics={
              "cpi": 1.0, "arpdau": 0.10, "d1_retention": 0.28,
              "d7_retention": 0.08, "roas": 1.1})).verdict
          == Verdict.KEEP.value)
    check("kill leaky bucket unproven",
          de.evaluate(_game("lk", metrics={
              "cpi": 1.5, "arpdau": 0.10, "d1_retention": 0.15,
              "d7_retention": 0.03, "roas": 0.6})).verdict
          == Verdict.KILL.value)
    check("kill no-payback unproven",
          de.evaluate(_game("np", metrics={
              "cpi": 2.5, "arpdau": 0.02, "d1_retention": 0.30,
              "d7_retention": 0.08, "roas": 0.6})).verdict
          == Verdict.KILL.value)
    d_keep = de.evaluate(_game("kp", metrics={
        "cpi": 1.0, "arpdau": 0.30, "d1_retention": 0.40,
        "d7_retention": 0.14}))
    check("keep unproven fast payback",
          d_keep.verdict == Verdict.KEEP.value and d_keep.payback_days <= 90)
    check("decision manual apply", d_scale.requires_manual_apply is True)
    check("decision snapshot captured",
          d_scale.metric_snapshot.get("cpi") == 1.0)
    regDE = GameRegistry(path=j("catDE.json"))
    regDE.add(_game("has", metrics={
        "cpi": 1.0, "arpdau": 0.35, "d1_retention": 0.42,
        "d7_retention": 0.14, "roas": 1.3}))
    regDE.add(_game("hasnot", metrics={}))
    check("evaluate_fleet skips no-economics",
          len(de.evaluate_fleet(regDE)) == 1)
    check("decision serializable", bool(json.dumps(d_scale.to_dict())))

    # ================================================================= #
    # 11. Real Fleet Bridge (Revenue OS -> Factory Brain, IAA mode)
    # ================================================================= #
    from operation.factory_brain.fleet_bridge import (
        NORTH_STAR_RPD, RealFleetBridge,
    )
    fb_data = os.path.join(tmp, "fb_data")
    fb_metrics = os.path.join(tmp, "fb_metrics")
    os.makedirs(fb_data, exist_ok=True)
    os.makedirs(fb_metrics, exist_ok=True)

    def _mrow(app, day, rev, imps, att, resp):
        return {"day": day, "application": app, "ad_format": "REWARD",
                "country": "us", "network": "MINTEGRAL_BIDDING",
                "impressions": str(imps), "attempts": str(att),
                "responses": str(resp), "ecpm": "0",
                "estimated_revenue": str(rev)}

    fb_rows = []
    for i in range(10):
        day = f"2026-07-{14 + i:02d}"
        fb_rows.append(_mrow("Winner", day, 28.0, 400, 11000, 7500))
        fb_rows.append(_mrow("Zombie", day, 0.011, 10, 1000, 400))
        fb_rows.append(_mrow("Broken", day, 0, 0, 1300, 380))
        fb_rows.append(_mrow("Dead", day, 0, 0, 3, 0))
        fb_rows.append(_mrow("Keeper", day, 2.0, 110, 3600, 2000))
    with open(os.path.join(fb_data, "ACC_report.json"), "w",
              encoding="utf-8") as f:
        json.dump({"account": "ACC", "start": "2026-07-14",
                   "end": "2026-07-23", "rows": fb_rows}, f)
    with open(os.path.join(fb_metrics, "ACC.json"), "w",
              encoding="utf-8") as f:
        json.dump({"dau": 5000, "arpdau_history": [
            {"date": "2026-07-23", "dau": 5000, "arpdau": 0.12,
             "revenue": 600.0}]}, f)

    fbr = RealFleetBridge(data_dir=fb_data, metrics_dir=fb_metrics)
    frep = fbr.build("ACC")
    check("bridge builds report", frep is not None)
    fmap = {v.game_id: v for v in frep.verdicts}
    check("winner -> SCALE", fmap["Winner"].verdict == "scale")
    check("zombie -> KILL", fmap["Zombie"].verdict == "kill")
    check("broken show path -> FIX (not kill)",
          fmap["Broken"].verdict == "fix")
    check("dead traffic -> KILL", fmap["Dead"].verdict == "kill")
    check("low-ecpm carrier -> KEEP", fmap["Keeper"].verdict == "keep")
    check("verdicts sorted scale first",
          frep.verdicts[0].verdict == "scale")
    check("all iaa mode",
          all(v.mode == "iaa" for v in frep.verdicts))
    check("all require manual apply",
          all(v.requires_manual_apply for v in frep.verdicts))
    check("no UA budget in iaa mode",
          all(v.budget_delta_pct == 0.0 for v in frep.verdicts))
    check("north star context met",
          frep.north_star == NORTH_STAR_RPD
          and frep.north_star_met is True)
    check("account dau carried", frep.dau == 5000)
    check("blended ecpm computed", frep.blended_ecpm > 0)
    check("winner trend computed",
          next(g for g in frep.games if g.app == "Winner").trend_pct
          is not None)
    check("bridge real_api locked False", frep.real_api_called is False)
    check("bridge missing account -> skipped",
          fbr.build_all(["ACC", "GONE"]) and
          len(fbr.build_all(["ACC", "GONE"])) == 1)
    fmd = fbr.render_markdown([frep])
    check("markdown has verdict labels",
          all(s in fmd for s in
              ("SCALE 赢家", "KEEP 优化", "FIX 修链路", "KILL 放弃")))
    check("markdown states manual apply",
          "requires_manual_apply" in fmd)
    check("report serialisable",
          bool(json.dumps(frep.to_dict())))
    # dominant-carrier rule: 99% share app whose ecpm == blend
    dom = GameDecisionEngine().evaluate_iaa({
        "app": "dom", "revenue": 100.0, "share": 0.99, "ecpm": 50.0,
        "ecpm_ratio": 1.01, "impressions": 2000, "attempts": 50000,
        "responses": 30000, "attempts_per_day": 5000, "days": 10})
    check("dominant carrier not misjudged (ratio~1.0 -> still SCALE)",
          dom.verdict == "scale")

    # ================================================================= #
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "=" * 50)
    print("  E15.1.2 AUTONOMOUS GAME FACTORY BRAIN")
    result = "FACTORY BRAIN READY" if _failed == 0 else "NOT READY"
    print(f"  Result: {result}")
    print(f"  Passed: {_passed}  Failed: {_failed}")
    print("=" * 50)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
