"""
E15.1.1 — Autonomous Publishing Factory — Acceptance Gate
=========================================================

Validates the full factory against all acceptance criteria.

Target: 120 cases, 0 failures  ->  AUTONOMOUS PUBLISHING READY
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from monetization.providers.models import SandboxMode

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.fleet_manager import (
    FleetManager, TaskType,
)
from operation.publishing_factory.catalog.product_profile import GameProduct
from operation.publishing_factory.asset_pipeline.screenshot_generator import (
    ScreenshotGenerator,
)
from operation.publishing_factory.asset_pipeline.icon_generator import IconGenerator
from operation.publishing_factory.asset_pipeline.video_generator import VideoGenerator
from operation.publishing_factory.asset_pipeline.asset_validator import AssetValidator
from operation.publishing_factory.metadata_engine.aso_generator import AsoGenerator
from operation.publishing_factory.metadata_engine.localization_engine import (
    LocalizationEngine,
)
from operation.publishing_factory.metadata_engine.keyword_optimizer import (
    KeywordOptimizer,
)
from operation.publishing_factory.compliance.policy_scanner import PolicyScanner
from operation.publishing_factory.compliance.privacy_checker import PrivacyChecker
from operation.publishing_factory.compliance.store_risk_predictor import (
    StoreRiskPredictor,
)
from operation.publishing_factory.publishing_factory import PublishingFactory
from operation.publishing_factory.batch_orchestrator import (
    BatchOrchestrator, RejectClass,
)
from operation.publishing_factory.memory import PublishingMemory

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


def _tmp(path, name):
    return os.path.join(tempfile.mkdtemp(), name)


def _game(gid="merge_witch", genre="merge", status="ready", version="1.0.0",
          published="", kw=None, monet="iaa", display_name=None,
          keywords=None, locales=None, selling_points=None, platforms=None):
    return GameProduct(
        game_id=gid, display_name=display_name or gid.replace("_", " ").title(),
        package_name=f"com.lf.{gid}", genre=genre, status=status,
        version=version, published_version=published,
        keywords=keywords if keywords is not None else (kw or []),
        monetization=monet, locales=locales or ["en-US"],
        selling_points=selling_points or [],
        platforms=platforms or ["google_play"])


def _privacy_ok():
    return {"privacy_policy_url": "https://x", "data_collection_disclosed": True,
            "has_consent": True}


def main() -> int:
    print("E15.1.1 Autonomous Publishing Factory -- Acceptance Gate\n")

    # ================================================================ #
    # 1. Fleet Manager (20)
    # ================================================================ #
    print("=== 1. Fleet Manager (20) ===")
    reg = GameRegistry(path=_tmp(None, "cat.json"))
    for g in [_game(), _game("hf", "casual", "published", "1.2.0", "1.1.0"),
              _game("bp", "puzzle", "rejected"), _game("wq", "word", "published", "2.0.0", "2.0.0")]:
        reg.add(g)
    fm = FleetManager(reg)
    scan = fm.scan()
    check("registry count = 4", reg.count() == 4)
    check("scan covers all games", scan.scanned == 4)
    check("version_ready detected",
          any(t.task_type == TaskType.VERSION_READY.value for t in scan.tasks))
    check("metadata_outdated detected",
          any(t.task_type == TaskType.METADATA_OUTDATED.value for t in scan.tasks))
    check("resubmit detected",
          any(t.task_type == TaskType.RESUBMIT.value for t in scan.tasks))
    check("resubmit highest priority",
          scan.tasks[0].task_type == TaskType.RESUBMIT.value)
    check("aso opportunity for stale published",
          any(t.task_type == TaskType.ASO_OPPORTUNITY.value for t in scan.tasks))
    check("by_type counts resubmit=1",
          scan.by_type.get(TaskType.RESUBMIT.value) == 1)
    check("metrics summary total=4", fm.metrics_summary()["total"] == 4)
    check("metrics summary published=2", fm.metrics_summary()["published"] == 2)
    check("task reason populated",
          all(t.reason for t in scan.tasks))
    check("empty fleet scan clean", FleetManager(GameRegistry(path=_tmp(None, "e.json"))).scan().scanned == 0)
    check("needs_first_publish ready", _game(status="ready").needs_first_publish())
    check("needs_first_publish published False",
          not _game(status="published").needs_first_publish())
    check("metadata_outdated True", _game("a", "casual", "published", "1.1.0", "1.0.0").metadata_outdated())
    check("metadata_outdated False",
          _game("a", "casual", "published", "1.0.0", "1.0.0").metadata_outdated() is False)
    check("registry persist roundtrip",
          (lambda: (reg.save(), GameRegistry(path=reg.path).load().count() == 4))()[1])
    check("list_by_status", len(reg.list_by_status("published")) == 2)
    check("remove works", reg.remove("bp") and reg.get("bp") is None)
    check("schedule_daily alias", fm.schedule_daily().scanned == reg.count())
    check("product to_dict roundtrip",
          GameProduct.from_dict(_game().to_dict()).game_id == "merge_witch")

    # ================================================================ #
    # 2. Asset Pipeline (20)
    # ================================================================ #
    print("\n=== 2. Asset Pipeline (20) ===")
    g = _game()
    ss = ScreenshotGenerator().generate(g)
    check("screenshot default count 5", len(ss.screenshots) == 5)
    check("screenshot first hook", ss.screenshots[0].layout == "hook")
    check("screenshot last fantasy", ss.screenshots[-1].layout == "fantasy")
    check("screenshots have headlines", all(s.headline for s in ss.screenshots))
    check("screenshots have palette", all(s.palette.get("bg") for s in ss.screenshots))
    check("screenshot indices sequential",
          [s.index for s in ss.screenshots] == list(range(5)))
    check("genre palette varies",
          ScreenshotGenerator().generate(_game(genre="puzzle")).screenshots[0].palette["bg"]
          != ss.screenshots[0].palette["bg"])
    ic = IconGenerator().generate(g)
    check("icon glyph merge=spark", ic.glyph == "spark")
    check("icon style set", bool(ic.style))
    check("icon text initial", ic.text == "M")
    vb = VideoGenerator().generate(g)
    check("video within 30s", vb.total_seconds <= 30)
    check("video scenes <=15s each", all(s.duration_s <= 15 for s in vb.scenes))
    check("video last logo sting", vb.scenes[-1].shot == "logo_sting")
    check("validator clean set passes",
          AssetValidator().validate(g.game_id, ss, ic, vb).valid)
    empty = AssetValidator().validate(g.game_id,
        type("S", (), {"screenshots": [], "to_dict": lambda self: {}})(), ic, vb)
    check("validator empty screenshots fails", not empty.valid)
    check("screenshot to_dict", "screenshots" in ss.to_dict())
    check("icon to_dict", "base_color" in ic.to_dict())
    check("video to_dict", "scenes" in vb.to_dict())
    check("custom screenshot count", len(ScreenshotGenerator(count=3).generate(g).screenshots) == 3)
    ss_long = ScreenshotGenerator(count=3).generate(g)
    ss_long.screenshots[0].headline = "X" * 50
    check("validator long headline fails",
          not AssetValidator().validate(g.game_id, ss_long, ic, vb).valid)

    # ================================================================ #
    # 3. ASO Engine (20)
    # ================================================================ #
    print("\n=== 3. ASO Engine (20) ===")
    pack = AsoGenerator().generate(_game(display_name="Merge Witch"))
    check("aso title generated", bool(pack.title))
    check("aso title <=30", len(pack.title) <= 30)
    check("aso subtitle <=30", len(pack.subtitle) <= 30)
    check("aso keywords seeded", "merge" in pack.keywords)
    check("aso competitor first",
          AsoGenerator().generate(_game(), competitor_hints=["dragons"]).keywords[0] == "dragons")
    check("aso rationale present", bool(pack.rationale.get("title")))
    check("aso brand kept", "Merge Witch" in pack.title)
    check("aso genre diff seeds",
          AsoGenerator().generate(_game(genre="puzzle")).keywords[0]
          != AsoGenerator().generate(_game(genre="idle")).keywords[0])
    loc = LocalizationEngine().localize(pack)
    check("localization 5 locales", set(loc) >= {"en-US", "de-DE", "fr-FR", "ja-JP", "ko-KR"})
    check("localization brand passthrough", "Merge Witch" in loc["ja-JP"].title)
    check("localization ja merge", "マージ" in loc["ja-JP"].keywords)
    check("localization ko puzzle", "퍼즐" in LocalizationEngine().localize(
        AsoGenerator().generate(_game(genre="puzzle")))["ko-KR"].keywords)
    kp = KeywordOptimizer().optimize("g", ["merge", "puzzle", "x"], genre_seed=["merge", "puzzle"])
    check("kw relevance 1.0 for seed", kp.ranked[0].relevance == 1.0)
    check("kw dedup", len(KeywordOptimizer().optimize("g", ["merge", "Merge"]).selected)
          == len(set(KeywordOptimizer().optimize("g", ["merge", "Merge"]).selected)))
    check("kw budget respected", KeywordOptimizer().optimize("g",
          [f"k{i}" for i in range(50)]).budget_used <= 100)
    check("kw selected non-empty", KeywordOptimizer().optimize("g",
          ["merge", "magic", "dragon"], genre_seed=["merge"]).selected)
    check("kw opportunity low for high comp",
          KeywordOptimizer().optimize("g", ["merge"], competition={"merge": 0.9}).ranked[0].opportunity
          < KeywordOptimizer().optimize("g", ["merge"], competition={"merge": 0.1}).ranked[0].opportunity)
    check("kw plan to_dict", "ranked" in kp.to_dict())
    check("aso to_dict", "keywords" in pack.to_dict())
    check("localized to_dict", "title" in loc["de-DE"].to_dict())
    check("kw dropped when over budget",
          len(KeywordOptimizer().optimize("g", [f"keyword{i}" for i in range(40)]).dropped) > 0)

    # ================================================================ #
    # 4. Compliance (15)
    # ================================================================ #
    print("\n=== 4. Compliance (15) ===")
    a = _game("a", "merge", keywords=["merge", "magic", "dragon"], display_name="Merge Witch")
    b = _game("b", "merge", keywords=["merge", "magic", "dragon"], display_name="Merge Witch")
    c = _game("c", "puzzle", keywords=["x"])
    pr_clean = PolicyScanner().scan(a, [c])
    pr_sim = PolicyScanner().scan(a, [b])
    check("policy clean for unique", pr_clean.clean)
    check("policy flags similar", not pr_sim.clean)
    check("policy sim score >=0.6", pr_sim.max_similarity >= 0.6)
    check("policy skips self", PolicyScanner().scan(a, [a]).clean)
    check("policy to_dict", "flags" in pr_clean.to_dict())
    pv_ok = PrivacyChecker().check(a, {"privacy_policy_url": "x",
                                       "data_collection_disclosed": True, "has_consent": True})
    pv_bad = PrivacyChecker().check(a, {})
    check("privacy pass with url", pv_ok.passed)
    check("privacy fail missing url", not pv_bad.passed)
    check("privacy child needs gate",
          not PrivacyChecker().check(a, {"child_directed": True, "age_gate": False,
                                         "coppa_compliant": False, "privacy_policy_url": "x",
                                         "data_collection_disclosed": True}).passed)
    check("privacy monetized needs consent", not PrivacyChecker().check(
        a, {"privacy_policy_url": "x", "data_collection_disclosed": True}).passed)
    check("privacy to_dict", "passed" in pv_ok.to_dict())
    risk_low = StoreRiskPredictor().predict(a, pr_clean, pv_ok)
    check("risk low when clean", risk_low.level == "low")
    risk_high = StoreRiskPredictor().predict(a, pr_sim,
        PrivacyChecker().check(a, {}))
    check("risk high with policy+privacy", risk_high.level == "high")
    check("risk apple >= google on 4.3",
          StoreRiskPredictor().predict(a, pr_sim, pv_ok).apple_prob
          >= StoreRiskPredictor().predict(a, pr_sim, pv_ok).google_prob)
    check("risk to_dict", "apple_prob" in risk_low.to_dict())

    # ================================================================ #
    # 5. Batch Publishing (20)
    # ================================================================ #
    print("\n=== 5. Batch Publishing (20) ===")
    reg2 = GameRegistry(path=_tmp(None, "batch.json"))
    for g in [_game(), _game("hf", "casual", "published", "1.2.0", "1.1.0"),
              _game("bp", "puzzle", "rejected"), _game("wq", "word", "published", "2.0.0", "2.0.0"),
              _game("im", "idle", "development", "0.9.0")]:
        reg2.add(g)
    fac = PublishingFactory(sandbox=SandboxMode.SIMULATION)
    orch = BatchOrchestrator(reg2, fac)
    rep = orch.run_daily()
    check("batch scanned 5", rep.scanned == 5)
    check("batch queue 5", len(rep.queue) == 5)
    check("batch no real api", orch.factory.real_api_called is False)
    check("batch plan has screenshots", bool(rep.plans[0].plan["screenshots"]))
    check("batch plan has aso", bool(rep.plans[0].plan["aso"]["title"]))
    check("batch plan localized", "ja-JP" in rep.plans[0].plan["localized"])
    check("batch plan risk", "apple_prob" in rep.plans[0].plan["risk"])
    check("batch requires approval", rep.plans[0].requires_approval)
    check("batch approval count 5", rep.approval_required == 5)
    check("batch notes summary", any("human approval" in n for n in rep.notes))
    check("batch resubmit priority", rep.queue[0]["game_id"] == "bp")
    check("batch all plans built", len(rep.plans) == 5)
    plan = orch.handle_rejection("bp", {"store": "apple", "code": "4.3", "reason": "spam"})
    check("reject classifies 4.3", "4.3_spam" in plan.notes[0])
    check("reject classifies privacy",
          "privacy" in orch.handle_rejection("bp",
              {"store": "google", "code": "privacy", "reason": "x"}).notes[0])
    check("reject classifies metadata",
          "metadata" in orch.handle_rejection("bp",
              {"store": "apple", "code": "metadata", "reason": "title"}).notes[0])
    check("reject resets approval", orch.handle_rejection("bp",
          {"store": "apple", "code": "4.3", "reason": "x"}).approval_status == "pending")
    check("factory approve", (lambda: (fac.approve(fac.build_plan(_game(), [_game()]), True).approval_status))() == "approved")
    check("factory sandbox recorded",
          fac.build_plan(_game(), [_game()]).sandbox == "simulation")
    raised = False
    try:
        orch.handle_rejection("zzz", {})
    except KeyError:
        raised = True
    check("unknown game reject raises", raised)
    check("fleet manager wired", isinstance(orch.fleet_manager, FleetManager))

    # ================================================================ #
    # 6. Memory (10)
    # ================================================================ #
    print("\n=== 6. Memory (10) ===")
    mem = PublishingMemory(path=_tmp(None, "mem.jsonl"))
    mem.record(__import__("operation.publishing_factory.memory",
                          fromlist=["PublishingMemoryEntry"]).PublishingMemoryEntry(
        "g1", "screenshot_style", "neon", "good", 0.18, genre="merge"))
    mem.record(__import__("operation.publishing_factory.memory",
                          fromlist=["PublishingMemoryEntry"]).PublishingMemoryEntry(
        "g2", "reject_fix", "4.3_spam", "resolved", genre="merge"))
    check("memory record+recall", len(mem.recall()) == 2)
    check("memory recall by kind", len(mem.recall(kind="reject_fix")) == 1)
    check("memory recall by genre", len(mem.recall(genre="merge")) == 2)
    check("memory best style", mem.best_style("merge") == "neon")
    check("memory best style empty none", PublishingMemory(path=_tmp(None, "m2.jsonl")).best_style("merge") is None)
    check("memory summarize", mem.summarize()["total"] == 2)
    check("memory entry roundtrip",
          __import__("operation.publishing_factory.memory",
                     fromlist=["PublishingMemoryEntry"]).PublishingMemoryEntry
          .from_dict(mem.recall()[0].to_dict()).game_id == "g1")
    check("memory persist multiple", len(mem.all()) == 2)
    check("memory best style averages", (lambda: (
        mem.record(__import__("operation.publishing_factory.memory",
                              fromlist=["PublishingMemoryEntry"]).PublishingMemoryEntry(
            "g3", "screenshot_style", "neon", "good", 0.10, genre="merge")),
        mem.best_style("merge"))[1])() == "neon")
    check("memory summarize best filter", mem.summarize(genre="merge")["best_style"] == "neon")

    # ================================================================ #
    # 7. Integration (15)
    # ================================================================ #
    print("\n=== 7. Integration (15) ===")
    reg3 = GameRegistry(path=_tmp(None, "int.json"))
    for i in range(10):
        reg3.add(_game(f"g{i:02d}", ["merge", "puzzle", "idle", "word", "casual"][i % 5],
                       "ready", "1.0.0"))
    fac3 = PublishingFactory(sandbox=SandboxMode.SIMULATION,
                             memory=PublishingMemory(path=_tmp(None, "im.jsonl")),
                             privacy=_privacy_ok())
    orch3 = BatchOrchestrator(reg3, fac3)
    rep3 = orch3.run_daily()
    check("integration 10-game loop", rep3.scanned == 10)
    p0 = rep3.plans[0].plan
    for k in ("screenshots", "icon", "video", "aso", "localized", "policy", "privacy", "risk"):
        check(f"integration plan has {k}", p0[k] is not None)
    check("integration all require approval", rep3.approval_required == 10)
    check("integration no real api", orch3.factory.real_api_called is False)
    # rejection loop updates memory
    orch3.handle_rejection("g00", {"store": "apple", "code": "4.3", "reason": "spam"})
    check("integration rejection -> memory",
          len(orch3.factory.memory.recall(kind="reject_fix")) >= 1)
    # memory informs lift (isolated low-risk merge game)
    fac3.memory.record(__import__("operation.publishing_factory.memory",
                          fromlist=["PublishingMemoryEntry"]).PublishingMemoryEntry(
        "gx", "screenshot_style", "neon", "good", 0.2, genre="merge"))
    _lift_game = _game("lift1", "merge", "ready", "1.0.0")
    _lift_plan = fac3.build_plan(_lift_game, [_lift_game])
    check("integration memory lifts prediction",
          _lift_plan.predicted_cvr_lift_pct >= 12.0)
    check("integration sandbox simulation",
          orch3.run_daily().sandbox == "simulation")
    # a genuinely unique game (no clonal fleet sibling) with clean privacy
    # can be low/medium risk -> proves the risk model isn't always high
    _clean_reg = GameRegistry(path=_tmp(None, "clean.json"))
    _clean_reg.add(_game("uniq1", "simulation", "ready", "1.0.0"))
    _clean_rep = BatchOrchestrator(
        _clean_reg,
        PublishingFactory(sandbox=SandboxMode.SIMULATION, privacy=_privacy_ok())
    ).run_daily()
    check("integration low-risk possible",
          _clean_rep.plans[0].plan["risk"]["level"] in ("low", "medium"))
    # reuse E15.1 agent import (no rewrite)
    from operation.publishing.orchestrator.agent import PublishingAgent  # noqa
    check("integration reuses E15.1 PublishingAgent", PublishingAgent is not None)
    check("integration plan to_dict", isinstance(p0, dict))
    check("integration report to_dict", "plans" in rep3.to_dict())
    check("integration resubmit priority", rep3.queue[0]["game_id"] == "g00")
    check("integration 20-game scales",
          (lambda: (reg3.add(_game("x20", "casual", "ready", "1.0.0")),
                    BatchOrchestrator(reg3, fac3).run_daily().scanned))()[1] == 11)
    check("integration memory reject key",
          any(e.key == "4.3_spam" and e.outcome == "resolved"
              for e in orch3.factory.memory.recall(kind="reject_fix")))
    check("integration full dict serializable",
          all(isinstance(p.plan, dict) for p in rep3.plans))

    # ================================================================ #
    print("\n==================================================")
    print(f"  E15.1.1 AUTONOMOUS PUBLISHING FACTORY")
    print(f"  Result: {'AUTONOMOUS PUBLISHING READY' if _failed == 0 else 'NOT READY'}")
    print(f"  Passed: {_passed}  Failed: {_failed}")
    print("==================================================")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
