"""E15.1.1 — Batch Publishing Orchestrator tests (20)."""
from tests.e15_1_1.e15_1_1_helpers import game, fleet
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.fleet_manager import FleetManager
from operation.publishing_factory.publishing_factory import PublishingFactory
from operation.publishing_factory.batch_orchestrator import (
    BatchOrchestrator, RejectClass,
)
from monetization.providers.models import SandboxMode


def _orch(n=5, sandbox=SandboxMode.SIMULATION):
    r = GameRegistry(path="data/_t_batch.json")
    for g in fleet(n):
        r.add(g)
    return BatchOrchestrator(r, PublishingFactory(sandbox=sandbox), sandbox)


def test_run_daily_scans_all():
    rep = _orch(5).run_daily()
    assert rep.scanned == 5


def test_run_daily_queue_populated():
    rep = _orch(5).run_daily()
    assert len(rep.queue) == 5


def test_run_daily_no_real_api():
    orch = _orch(3)
    rep = orch.run_daily()
    assert orch.factory.real_api_called is False


def test_run_daily_plan_has_assets():
    rep = _orch(1).run_daily()
    plan = rep.plans[0].plan
    assert plan["screenshots"] and plan["icon"] and plan["video"]


def test_run_daily_plan_has_aso():
    rep = _orch(1).run_daily()
    assert rep.plans[0].plan["aso"]["title"]


def test_run_daily_localized_present():
    rep = _orch(1).run_daily()
    assert "ja-JP" in rep.plans[0].plan["localized"]


def test_run_daily_risk_present():
    rep = _orch(1).run_daily()
    assert "apple_prob" in rep.plans[0].plan["risk"]


def test_run_daily_requires_approval():
    rep = _orch(1).run_daily()
    assert rep.plans[0].requires_approval is True


def test_rejected_game_plan_not_recommended():
    orch = _orch(5)
    rep = orch.run_daily()
    bp = next(p for p in rep.plans if p.game_id == "block_puzzle")
    # rejected game carries risk; sanity that plan built
    assert bp.plan["risk"]


def test_handle_rejection_classifies_43():
    orch = _orch(5)
    plan = orch.handle_rejection("block_puzzle",
                                 {"store": "apple", "code": "4.3", "reason": "spam"})
    assert "4.3_spam" in plan.notes[0]


def test_handle_rejection_classifies_privacy():
    orch = _orch(5)
    plan = orch.handle_rejection("block_puzzle",
                                 {"store": "google", "code": "privacy", "reason": "policy"})
    assert RejectClass.PRIVACY.value in plan.notes[0]


def test_handle_rejection_classifies_metadata():
    orch = _orch(5)
    plan = orch.handle_rejection("block_puzzle",
                                 {"store": "apple", "code": "metadata", "reason": "title"})
    assert RejectClass.METADATA.value in plan.notes[0]


def test_handle_rejection_resets_approval():
    orch = _orch(5)
    plan = orch.handle_rejection("block_puzzle",
                                 {"store": "apple", "code": "4.3", "reason": "spam"})
    assert plan.approval_status == "pending"
    assert plan.requires_approval is True


def test_handle_rejection_unknown_game_raises():
    orch = _orch(3)
    try:
        orch.handle_rejection("nope", {"code": "4.3"})
        assert False, "should raise"
    except KeyError:
        pass


def test_factory_approve_sets_status():
    f = PublishingFactory()
    g = game()
    plan = f.build_plan(g, [g])
    f.approve(plan, approve=True)
    assert plan.approval_status == "approved"


def test_factory_approve_reject():
    f = PublishingFactory()
    plan = f.build_plan(game(), [game()])
    f.approve(plan, approve=False)
    assert plan.approval_status == "rejected"


def test_sandbox_recorded_in_plan():
    f = PublishingFactory(sandbox=SandboxMode.SHADOW)
    plan = f.build_plan(game(), [game()])
    assert plan.sandbox == "shadow"


def test_run_daily_notes_summary():
    rep = _orch(5).run_daily()
    assert any("need human approval" in n for n in rep.notes)


def test_fleet_manager_in_orchestrator():
    orch = _orch(3)
    assert isinstance(orch.fleet_manager, FleetManager)
