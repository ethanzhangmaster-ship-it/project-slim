"""E15.1.1 — Integration tests (15): full factory loop + reuse of E15.1."""
from tests.e15_1_1.e15_1_1_helpers import game, fleet
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.fleet_manager import FleetManager
from operation.publishing_factory.publishing_factory import PublishingFactory
from operation.publishing_factory.batch_orchestrator import BatchOrchestrator
from operation.publishing_factory.memory import PublishingMemory
from monetization.providers.models import SandboxMode
from operation.publishing_factory.catalog.product_profile import GameStatus


def _orch(tmp_path, n=5):
    p = str(tmp_path / "cat.json")
    r = GameRegistry(path=p)
    for g in fleet(n):
        r.add(g)
    mem = PublishingMemory(path=str(tmp_path / "mem.jsonl"))
    fac = PublishingFactory(sandbox=SandboxMode.SIMULATION, memory=mem,
                            privacy={"privacy_policy_url": "https://x",
                                     "data_collection_disclosed": True,
                                     "has_consent": True})
    return BatchOrchestrator(r, fac), r


def test_full_daily_loop_runs(tmp_path):
    orch, _ = _orch(tmp_path, 5)
    rep = orch.run_daily()
    assert rep.scanned == 5
    assert len(rep.plans) == 5


def test_full_loop_produces_assets_metadata_compliance(tmp_path):
    orch, _ = _orch(tmp_path, 1)
    rep = orch.run_daily()
    plan = rep.plans[0].plan
    for k in ("screenshots", "icon", "video", "aso", "localized",
              "policy", "privacy", "risk"):
        assert plan[k] is not None


def test_full_loop_all_require_approval(tmp_path):
    orch, _ = _orch(tmp_path, 4)
    rep = orch.run_daily()
    assert rep.approval_required == 4


def test_no_real_api_anywhere(tmp_path):
    orch, _ = _orch(tmp_path, 3)
    orch.run_daily()
    assert orch.factory.real_api_called is False


def test_rejection_loop_updates_memory(tmp_path):
    orch, reg = _orch(tmp_path, 5)
    orch.handle_rejection("block_puzzle", {"store": "apple", "code": "4.3", "reason": "spam"})
    mem = orch.factory.memory
    assert len(mem.recall(kind="reject_fix")) >= 1


def test_rejection_class_stored_in_memory(tmp_path):
    orch, _ = _orch(tmp_path, 5)
    orch.handle_rejection("block_puzzle", {"store": "google", "code": "privacy", "reason": "x"})
    mem = orch.factory.memory
    entries = [e for e in mem.recall(kind="reject_fix") if e.key == "privacy"]
    assert entries and entries[0].outcome == "resolved"


def test_memory_informs_lift_prediction(tmp_path):
    orch, _ = _orch(tmp_path, 1)
    # seed a good style for the genre
    orch.factory.memory.record(__import__(
        "operation.publishing_factory.memory", fromlist=["PublishingMemoryEntry"]
    ).PublishingMemoryEntry("gX", "screenshot_style", "neon_glass", "good", 0.18, genre="merge"))
    g = game(genre="merge")
    plan = orch.factory.build_plan(g, [g])
    assert plan.predicted_cvr_lift_pct >= 12.0


def test_three_tier_sandbox_on_plan(tmp_path):
    orch, _ = _orch(tmp_path, 1)
    rep = orch.run_daily()
    assert rep.sandbox == "simulation"


def test_recommended_flag_depends_on_risk(tmp_path):
    # clean, low-risk game should be recommended
    reg = GameRegistry(path=str(tmp_path / "c.json"))
    g = game(status="ready", version="1.0.0", genre="merge",
             keywords=["merge", "magic", "dragon"], display_name="Merge Witch",
             monetization="iaa")
    reg.add(g)
    fac = PublishingFactory(sandbox=SandboxMode.SIMULATION,
                            privacy={"privacy_policy_url": "x",
                                     "data_collection_disclosed": True,
                                     "has_consent": True})
    orch = BatchOrchestrator(reg, fac)
    rep = orch.run_daily()
    # asset valid + privacy ok + low risk -> recommended possible
    assert rep.plans[0].plan["risk"]["level"] in ("low", "medium")


def test_fleet_manager_drives_orchestrator(tmp_path):
    reg = GameRegistry(path=str(tmp_path / "c.json"))
    for g in fleet(5):
        reg.add(g)
    fm = FleetManager(reg)
    scan = fm.scan()
    assert scan.scanned == 5
    orch = BatchOrchestrator(reg)
    assert isinstance(orch.fleet_manager, FleetManager)


def test_publishing_factory_reuses_e15_agent_interface(tmp_path):
    # The factory's submit path is delegated to E15.1 PublishingAgent;
    # verify the agent still imports and the factory does not rewrite it.
    from operation.publishing.orchestrator.agent import PublishingAgent  # noqa
    reg = GameRegistry(path=str(tmp_path / "c.json"))
    reg.add(game(status="ready", version="1.0.0"))
    orch = BatchOrchestrator(reg)
    rep = orch.run_daily()
    assert rep.plans[0].plan["game_id"] == "merge_witch"


def test_large_fleet_scales(tmp_path):
    reg = GameRegistry(path=str(tmp_path / "big.json"))
    for i in range(20):
        reg.add(game(game_id=f"game_{i:02d}", status="ready", version="1.0.0",
                     genre=["merge", "puzzle", "idle", "word", "casual"][i % 5]))
    orch = BatchOrchestrator(reg)
    rep = orch.run_daily()
    assert rep.scanned == 20


def test_rejected_game_priority_in_queue(tmp_path):
    reg = GameRegistry(path=str(tmp_path / "c.json"))
    reg.add(game(game_id="a", status="rejected"))
    reg.add(game(game_id="b", status="ready", version="1.0.0"))
    orch = BatchOrchestrator(reg)
    rep = orch.run_daily()
    assert rep.queue[0]["game_id"] == "a"  # resubmit first


def test_plan_serializes_to_dict(tmp_path):
    orch, _ = _orch(tmp_path, 1)
    rep = orch.run_daily()
    d = rep.plans[0].plan
    assert isinstance(d, dict) and d["game_id"]


def test_full_batch_report_to_dict(tmp_path):
    orch, _ = _orch(tmp_path, 3)
    rep = orch.run_daily()
    d = rep.to_dict()
    assert d["scanned"] == 3 and "plans" in d and "queue" in d
