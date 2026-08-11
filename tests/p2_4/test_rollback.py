"""P2.4.4 Rollback Engine 测试：能力注册表 / 计划构建 / 执行（成功、ESCALATE）。"""

import pytest

from src.execution.models import ExecutionAction
from src.execution.safe_executor.models import RollbackCapability, RollbackPlan
from src.execution.safe_executor.rollback import (
    RB_ESCALATED,
    RB_SUCCESS,
    DEFAULT_CAPABILITIES,
    RollbackEngine,
    RollbackRegistry,
    RollbackResult,
)
from tests.p2_4.conftest import (
    FailingRollbackProvider,
    MaxProvider,
    PlainProvider,
    RaisingRollbackProvider,
)


class TestDefaultCapabilities:
    def test_three_platforms_present(self):
        providers = {c.provider for c in DEFAULT_CAPABILITIES}
        assert providers == {"max", "meta", "play"}

    def test_max_mapping(self):
        cap = next(c for c in DEFAULT_CAPABILITIES if c.provider == "max")
        assert cap.original_action == "disable_network"
        assert cap.rollback_action == "enable_network"

    def test_meta_mapping(self):
        cap = next(c for c in DEFAULT_CAPABILITIES if c.provider == "meta")
        assert cap.original_action == "pause_campaign"
        assert cap.rollback_action == "active_campaign"

    def test_play_mapping(self):
        cap = next(c for c in DEFAULT_CAPABILITIES if c.provider == "play")
        assert cap.original_action == "create_release"
        assert cap.rollback_action == "delete_draft"


class TestRollbackRegistry:
    def test_lookup_and_supports(self):
        reg = RollbackRegistry()
        cap = reg.lookup("max", "disable_network")
        assert cap is not None and cap.rollback_action == "enable_network"
        assert reg.supports("max", ExecutionAction.DISABLE_NETWORK)
        assert not reg.supports("max", "pause_campaign")
        assert not reg.supports("unknown", "disable_network")

    def test_lookup_accepts_enum(self):
        reg = RollbackRegistry()
        assert reg.lookup("meta", ExecutionAction.PAUSE_CAMPAIGN) is not None

    def test_register_appends(self):
        reg = RollbackRegistry(capabilities=[])
        assert reg.lookup("max", "disable_network") is None
        reg.register(RollbackCapability(
            provider="max", original_action="disable_network",
            rollback_action="enable_network"
        ))
        assert reg.supports("max", "disable_network")

    def test_default_registry_loaded_when_none(self):
        reg = RollbackRegistry()
        assert len(reg.capabilities) == 3


class TestRollbackResult:
    def test_ok_and_escalated(self):
        ok = RollbackResult(
            plan_id="p", execution_id="e", provider="max",
            rollback_action="enable_network", status=RB_SUCCESS,
        )
        assert ok.ok and not ok.escalated
        bad = RollbackResult(
            plan_id="p", execution_id="e", provider="max",
            rollback_action="enable_network", status=RB_ESCALATED, error="x",
        )
        assert bad.escalated and not bad.ok

    def test_to_dict(self):
        r = RollbackResult(
            plan_id="p1", execution_id="e1", provider="max",
            rollback_action="enable_network", status=RB_SUCCESS, detail={"k": 1},
        )
        d = r.to_dict()
        assert d["status"] == RB_SUCCESS
        assert d["detail"] == {"k": 1}


class TestRollbackEngine:
    def test_build_plan_known(self):
        eng = RollbackEngine()
        plan = eng.build_plan("max", "disable_network", {"s": 1}, execution_id="e1", target="p04")
        assert isinstance(plan, RollbackPlan)
        assert plan.rollback_action == "enable_network"
        assert plan.snapshot == {"s": 1}

    def test_build_plan_unknown_returns_none(self):
        eng = RollbackEngine()
        assert eng.build_plan("unknown", "do_thing", {}) is None

    def test_execute_success(self):
        eng = RollbackEngine()
        plan = eng.build_plan("max", "disable_network", {}, execution_id="e1", target="p04")
        res = eng.execute(plan, MaxProvider())
        assert res.status == RB_SUCCESS
        assert res.ok

    def test_execute_provider_without_rollback_escalates(self):
        eng = RollbackEngine()
        plan = eng.build_plan("max", "disable_network", {}, execution_id="e1", target="p04")
        res = eng.execute(plan, PlainProvider())
        assert res.status == RB_ESCALATED
        assert res.escalated

    def test_execute_rollback_returns_failure_escalates(self):
        eng = RollbackEngine()
        plan = eng.build_plan("max", "disable_network", {}, execution_id="e1", target="p04")
        res = eng.execute(plan, FailingRollbackProvider())
        assert res.status == RB_ESCALATED

    def test_execute_rollback_raises_escalates(self):
        eng = RollbackEngine()
        plan = eng.build_plan("max", "disable_network", {}, execution_id="e1", target="p04")
        res = eng.execute(plan, RaisingRollbackProvider())
        assert res.status == RB_ESCALATED
        assert "rollback exploded" in res.error

    def test_execute_non_dict_detail_wrapped(self):
        class RawProvider(MaxProvider):
            def rollback(self, plan):
                return {"success": True, "raw": "done"}

        eng = RollbackEngine()
        plan = eng.build_plan("max", "disable_network", {}, execution_id="e1", target="p04")
        res = eng.execute(plan, RawProvider())
        assert res.status == RB_SUCCESS
        assert res.detail.get("raw") == "done"
